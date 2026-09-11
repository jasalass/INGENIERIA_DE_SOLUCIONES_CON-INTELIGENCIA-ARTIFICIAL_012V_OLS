"""Pruebas OFFLINE: respuestas guionadas, no evidencia de calidad de Groq."""

import json
import os
import unittest
from unittest.mock import patch

import httpx
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI

from etapa3_producto.app import ROOT, create_app
from etapa3_producto.contracts import Filters
from etapa3_producto.groq_backend import GroqBackend, parse_json_response

CHUNKS = ROOT / "etapa1_datos/data/processed/chunks.json"


def plan(query="saludo", kind="conversation"):
    return {"kind": kind, "query": query}


def answer(text, ids=None, insufficient=False):
    return {"answer": text, "cited_chunk_ids": ids or [], "insufficient_context": insufficient}


class GroqTests(unittest.TestCase):
    def make_client(self, outputs):
        self.calls = []
        self.outputs = list(outputs)

        def invoke(prompt):
            self.calls.append(prompt.to_messages())
            output = self.outputs.pop(0)
            if isinstance(output, Exception):
                raise output
            return AIMessage(content=output if isinstance(output, str) else json.dumps(output))

        self.backend = GroqBackend(CHUNKS, model_client=RunnableLambda(invoke))
        return TestClient(create_app(self.backend, mode="groq"))

    def test_history_passed_as_messages_for_name_recall(self):
        client = self.make_client([plan(), answer("Hola Felipe"), plan(), answer("Me dijiste que te llamas Felipe.")])
        first = client.post("/chat", json={"message": "Hola, me llamo Felipe"}).json()
        second = client.post("/chat", json={"message": "¿Cómo me llamaba?", "conversation_id": first["conversation_id"]}).json()
        self.assertEqual(second["answer_kind"], "conversation")
        self.assertEqual(second["sources"], [])
        self.assertEqual(second["turn_count"], 2)
        for call in self.calls[2:]:
            self.assertEqual([m.type for m in call], ["system", "human", "ai", "human"])
            self.assertEqual(call[1].content, "Hola, me llamo Felipe")
            self.assertEqual(call[2].content, "Hola Felipe")
        self.assertIn("total", second["timings_ms"])

    def test_new_session_does_not_receive_other_users_history(self):
        client = self.make_client([plan(), answer("Hola Felipe"), plan(), answer("No consta tu nombre", insufficient=True)])
        first = client.post("/chat", json={"message": "Me llamo Felipe"}).json()
        second = client.post("/chat", json={"message": "¿Cómo me llamo?"}).json()
        self.assertNotEqual(first["conversation_id"], second["conversation_id"])
        self.assertEqual(len(self.calls[-1]), 2)
        self.assertTrue(second["insufficient_context"])

    def test_memory_window_is_bounded_to_six_exchanges(self):
        client = self.make_client([value for _ in range(8) for value in (plan(), answer("Entendido"))])
        cid = None
        for i in range(8):
            result = client.post("/chat", json={"message": f"Mi preferencia es {i}", "conversation_id": cid}).json()
            cid = result["conversation_id"]
        self.assertEqual(len(self.calls[-1]), 14)  # system + 12 history + current
        self.assertEqual(self.calls[-1][1].content, "Mi preferencia es 1")
        self.assertEqual(result["turn_count"], 8)

    def test_failed_generation_is_not_saved_in_history(self):
        client = self.make_client([plan(), answer("Hola"), plan(), "not json", plan(), answer("Hola de nuevo")])
        first = client.post("/chat", json={"message": "Hola"}).json()
        cid = first["conversation_id"]
        self.assertEqual(client.post("/chat", json={"message": "MENSAJE FALLIDO", "conversation_id": cid}).status_code, 503)
        result = client.post("/chat", json={"message": "Otra vez hola", "conversation_id": cid}).json()
        self.assertEqual(result["turn_count"], 2)
        self.assertNotIn("MENSAJE FALLIDO", " ".join(m.content for m in self.calls[-1]))

    def test_article_and_followup_use_retrieved_evidence(self):
        client = self.make_client([])
        source = self.backend.retrieve("artículo 4", 1, Filters())[0]
        self.outputs.extend([
            plan("¿Qué dice el artículo 4?", "document"),
            answer(f"Extracto [{source.chunk_id}]", [source.chunk_id]),
            plan("Excepciones del artículo 4", "document"),
            answer(f"Consulta [{source.chunk_id}]", [source.chunk_id]),
        ])
        first = client.post("/chat", json={"message": "¿Qué dice el artículo 4?"}).json()
        second = client.post("/chat", json={"message": "¿Y sus excepciones?", "conversation_id": first["conversation_id"]}).json()
        self.assertEqual(second["retrieval_query"], "Excepciones del artículo 4")
        self.assertEqual(second["answer_kind"], "document")
        self.assertEqual(second["sources"][0]["chunk_id"], source.chunk_id)
        context = json.loads(self.calls[-1][0].content.split("Fragmentos recuperados (JSON):\n", 1)[1])
        self.assertEqual(context[0]["texto"], source.texto)

    def test_explicit_article_reference_still_uses_classifier(self):
        # plan_query ya no se salta el clasificador con un regex (ver
        # groq_backend.py) -- eso podia clasificar como "document" un
        # mensaje que solo menciona un articulo de pasada. Ahora el
        # clasificador SIEMPRE se llama (con historial), y solo se corrige
        # la reformulacion si perdiera el numero de articulo explicito.
        client = self.make_client([plan("artículo 999", "document")])
        result = client.post("/chat", json={"message": "artículo 999"}).json()
        self.assertTrue(result["insufficient_context"])
        self.assertEqual(len(self.calls), 1)

    def test_explicit_article_respects_transitory_filter(self):
        client = self.make_client([plan("artículo 4", "document")])
        result = client.post("/chat", json={"message": "artículo 4", "filters": {"ambito": "transitorio"}}).json()
        self.assertTrue(result["insufficient_context"])
        self.assertEqual(result["sources"], [])

    def test_missing_and_invented_citations_are_rejected(self):
        for output in (answer("Sin citas"), answer("[inventado]", ["inventado"])):
            client = self.make_client([plan("artículo 4", "document"), output])
            self.assertEqual(client.post("/chat", json={"message": "artículo 4"}).status_code, 503)

    def test_citation_must_also_be_visible(self):
        client = self.make_client([])
        source = self.backend.retrieve("artículo 4", 1, Filters())[0]
        self.outputs.extend([plan("artículo 4", "document"), answer("Sin cita visible", [source.chunk_id])])
        self.assertEqual(client.post("/chat", json={"message": "artículo 4"}).status_code, 503)

    def test_conversation_cannot_attach_document_citations(self):
        client = self.make_client([plan(), answer("Felipe [art-4]", ["art-4"])])
        self.assertEqual(client.post("/chat", json={"message": "Mi nombre es Felipe"}).status_code, 503)

    def test_provider_errors_are_safe_and_do_not_fallback(self):
        for status in (401, 403, 404, 429):
            error = RuntimeError("PRIVATE_KEY_AND_PROVIDER_DETAIL")
            error.status_code = status
            client = self.make_client([error])
            response = client.post("/chat", json={"message": "hola"})
            self.assertEqual(response.status_code, 503)
            self.assertNotIn("PRIVATE", response.text)
            if status == 429:
                self.assertEqual(response.headers["retry-after"], "30")

    def test_no_key_and_wrong_endpoint_fail_at_startup(self):
        with patch.dict(os.environ, {"LLM_API_KEY": "", "GROQ_API_KEY": ""}):
            with self.assertRaisesRegex(RuntimeError, "requiere LLM_API_KEY"):
                create_app(mode="groq")
        with patch.dict(os.environ, {"LLM_API_KEY": "fake-test-key", "LLM_BASE_URL": "https://example.com"}):
            with self.assertRaisesRegex(RuntimeError, "LLM_BASE_URL"):
                create_app(mode="groq")

    def test_json_cleanup_and_no_thinking_leak(self):
        self.assertEqual(parse_json_response('<think>private</think>```json\n{"answer":"ok"}\n```'), {"answer": "ok"})
        for text in ('<think>unfinished', '[]', 'not json'):
            with self.assertRaises(ValueError):
                parse_json_response(text)
        client = self.make_client([plan(), answer("<think>private</think>Hola")])
        self.assertEqual(client.post("/chat", json={"message": "hola"}).status_code, 503)

    def test_real_sdk_request_shape_via_mock_transport(self):
        captured = []

        def transport(request):
            captured.append((str(request.url), json.loads(request.content)))
            return httpx.Response(200, json={"id": "test", "object": "chat.completion", "created": 0, "model": "qwen/qwen3.6-27b", "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps(plan())}}]})

        with httpx.Client(transport=httpx.MockTransport(transport)) as http_client:
            def model_factory(**kwargs):
                return ChatOpenAI(**kwargs, http_client=http_client)
            with patch.dict(os.environ, {"LLM_API_KEY": "fake-test-key", "LLM_BASE_URL": "https://api.groq.com/openai/v1", "LLM_MODEL": "qwen/qwen3.6-27b"}), patch("etapa3_producto.groq_backend.ChatOpenAI", side_effect=model_factory):
                backend = GroqBackend(CHUNKS)
                self.assertEqual(backend.plan_query("hola", []).kind, "conversation")
        url, body = captured[0]
        self.assertEqual(url, "https://api.groq.com/openai/v1/chat/completions")
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertEqual(body["reasoning_effort"], "none")
        self.assertEqual(body["reasoning_format"], "hidden")
        self.assertEqual(body["model"], "qwen/qwen3.6-27b")
        self.assertEqual(body.get("max_completion_tokens", body.get("max_tokens")), 512)
        self.assertEqual(body["messages"][-1], {"content": "hola", "role": "user"})

    def test_health_does_not_claim_vector_search_or_verified_access(self):
        client = self.make_client([])
        health = client.get("/health").json()
        self.assertEqual(health["retrieval"], "lexical")
        self.assertEqual(health["generation"], "groq")
        self.assertEqual(health["provider_reachable"], "not_checked")

    def test_invalid_output_token_limit_fails_early(self):
        for value in ("0", "2001", "not-a-number"):
            with patch.dict(os.environ, {"LLM_MAX_TOKENS": value}):
                with self.assertRaises((RuntimeError, ValueError)):
                    GroqBackend(CHUNKS, model_client=RunnableLambda(lambda x: x))


if __name__ == "__main__":
    unittest.main()
