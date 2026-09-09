import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from etapa3_producto.app import ROOT, create_app
from etapa3_producto.contracts import Generation
from etapa3_producto.demo import DemoBackend


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app(mode="demo"))

    def ask(self, message="¿Qué dice el artículo 4?", **kwargs):
        return self.client.post("/api/chat", json={"message": message, **kwargs})

    def test_health_exposes_simulation(self):
        health = self.client.get("/api/health").json()
        self.assertEqual(health["mode"], "demo")
        self.assertEqual(health["generation"], "literal_excerpts")

    def test_article_sources_and_literal_evidence(self):
        result = self.ask().json()
        self.assertFalse(result["insufficient_context"])
        self.assertTrue(result["sources"])
        for source in result["sources"]:
            self.assertEqual(source["articulo"], "4")
            self.assertIn(source["texto"][:650], result["answer"])
            self.assertIn(f"[{source['chunk_id']}]", result["answer"])

    def test_bis_is_not_base_article(self):
        result = self.ask("¿Qué dice el artículo 1 bis?").json()
        self.assertTrue(result["sources"])
        self.assertTrue(all(s["articulo"] == "1" and s["articulo_sufijo"] == "bis" for s in result["sources"]))

    def test_transitory_filter_and_labels(self):
        result = self.ask("¿Qué disposiciones se aplican?", filters={"ambito": "transitorio"}).json()
        self.assertTrue(result["sources"])
        self.assertTrue(all(s["ambito"] == "transitorio" and "transitoria" in s["label"] for s in result["sources"]))

    def test_nonexistent_article_abstains(self):
        result = self.ask("¿Qué dice el artículo 999?").json()
        self.assertTrue(result["insufficient_context"])
        self.assertEqual(result["sources"], [])

    def test_unrelated_query_does_not_fabricate(self):
        result = self.ask("Receta pizza margarita").json()
        self.assertTrue(result["insufficient_context"])

    def test_followup_preserves_topic(self):
        first = self.ask().json()
        second = self.ask("¿Y eso cómo funciona?", conversation_id=first["conversation_id"]).json()
        # Normalización de puntuación se cubre con una pregunta natural.
        self.assertIn("artículo 4", second["retrieval_query"])
        self.assertEqual(second["turn_count"], 2)

    def test_new_article_changes_topic(self):
        first = self.ask().json()
        second = self.ask("Y el artículo 1 bis?", conversation_id=first["conversation_id"]).json()
        self.assertNotIn("artículo 4", second["retrieval_query"])
        self.assertEqual(second["sources"][0]["articulo_sufijo"], "bis")

    def test_separate_conversations(self):
        first = self.ask().json()
        second = self.ask("Explica más").json()
        self.assertNotEqual(first["conversation_id"], second["conversation_id"])
        self.assertNotIn("artículo 4", second["retrieval_query"])

    def test_delete_and_unknown_conversation(self):
        first = self.ask().json()
        self.assertEqual(self.client.delete(f"/api/conversations/{first['conversation_id']}").status_code, 204)
        self.assertEqual(self.ask(conversation_id=first["conversation_id"]).status_code, 404)

    def test_expiration(self):
        with patch("etapa3_producto.app.time.monotonic", return_value=100):
            first = self.ask().json()
        with patch("etapa3_producto.app.time.monotonic", return_value=4000):
            self.assertEqual(self.ask(conversation_id=first["conversation_id"]).status_code, 404)

    def test_validation(self):
        for payload in ({"message": "  "}, {"message": "a" * 2001}, {"message": "hola", "top_k": 99}, {"message": "hola", "filters": {"ambito": "otro"}}, {"message": "hola", "conversation_id": "invalid"}):
            with self.subTest(payload=str(payload)[:70]):
                self.assertEqual(self.client.post("/chat", json=payload).status_code, 422)

    def test_pdf_and_static(self):
        self.assertIn("Modo", self.client.get("/app.js").text)
        response = self.client.get("/api/source.pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertIn("text/html", self.client.get("/").headers["content-type"])

    def test_capacity_does_not_evict_active_session(self):
        client = TestClient(create_app(mode="demo", capacity=1))
        first = client.post("/chat", json={"message": "artículo 4"}).json()
        self.assertEqual(client.post("/chat", json={"message": "artículo 1"}).status_code, 503)
        self.assertEqual(client.post("/chat", json={"message": "Y eso?", "conversation_id": first["conversation_id"]}).status_code, 200)

    def test_upstream_failure_does_not_append_turn_or_leak_error(self):
        backend = DemoBackend(ROOT / "etapa1_datos/data/processed/chunks.json")
        client = TestClient(create_app(backend, mode="demo"))
        first = client.post("/chat", json={"message": "artículo 4"}).json()
        with patch.object(backend, "generate", side_effect=RuntimeError("private-provider-detail")):
            failed = client.post("/chat", json={"message": "Y eso?", "conversation_id": first["conversation_id"]})
        self.assertEqual(failed.status_code, 503)
        self.assertNotIn("private-provider-detail", failed.text)
        again = client.post("/chat", json={"message": "Y eso?", "conversation_id": first["conversation_id"]}).json()
        self.assertEqual(again["turn_count"], 2)

    def test_hallucinated_citation_rejected(self):
        backend = DemoBackend(ROOT / "etapa1_datos/data/processed/chunks.json")
        client = TestClient(create_app(backend, mode="demo"))
        with patch.object(backend, "generate", return_value=Generation(answer="Inventado", cited_chunk_ids=["art-999"])):
            self.assertEqual(client.post("/chat", json={"message": "artículo 4"}).status_code, 503)

    def test_live_never_silently_uses_demo(self):
        with patch.dict(os.environ, {"RAG_BACKEND_FACTORY": ""}):
            with self.assertRaises(RuntimeError):
                create_app(mode="live")


if __name__ == "__main__":
    unittest.main()
