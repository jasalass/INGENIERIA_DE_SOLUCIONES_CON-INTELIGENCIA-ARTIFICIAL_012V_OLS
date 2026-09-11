"""Regresiones offline: procedencia, fragmento padre y límites del contexto."""

import json
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from etapa3_producto.app import ROOT, create_app
from etapa3_producto.build_document_context import extract_context
from etapa3_producto.contracts import Filters, Generation
from etapa3_producto.document_context import MANIFEST, load_document_context
from etapa3_producto.vector_backend import VectorBackend


class DocumentContextTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        def invoke(prompt):
            self.calls.append(prompt.to_messages())
            return AIMessage(content=json.dumps({"answer": "Texto [doc-21719-p1]", "cited_chunk_ids": ["doc-21719-p1"]}))
        self.search = MagicMock(return_value=[{"chunk_id": "art-1", "texto": "Artículo 1", "articulo": "1", "nivel1": "primero", "ley_referenciada": "19.628", "fuente": "BCN", "distancia": .2}])
        self.backend = VectorBackend(ROOT / "etapa1_datos/data/processed/chunks.json", search_fn=self.search, model_client=RunnableLambda(invoke))

    def test_parent_is_reproducible_from_actual_pdf(self):
        self.assertEqual(json.loads(MANIFEST.read_text(encoding="utf-8")), extract_context(ROOT / "docs/Ley-21719_13-DIC-2024.pdf"))
        source = load_document_context()
        self.assertIn("19.628", source.texto)
        self.assertIn("21.719", source.texto)
        self.assertEqual(source.pagina_pdf, 1)

    def test_changed_pdf_fails_closed(self):
        with patch("etapa3_producto.document_context.hashlib.sha256") as digest:
            digest.return_value.hexdigest.return_value = "different"
            with self.assertRaises(RuntimeError):
                load_document_context()

    def test_general_retrieval_adds_parent_without_relabeling_articles(self):
        sources = self.backend.retrieve("De qué trata la ley 21.719?", 1, Filters())
        self.assertEqual([s.chunk_id for s in sources], ["art-1", "doc-21719-p1"])
        self.assertEqual(sources[0].ley_referenciada, "19.628")
        self.assertEqual(sources[0].documento_origen, "21.719")
        self.assertIsNone(sources[1].score)  # parent is not a ranked vector
        self.search.assert_called_once()

    def test_parent_does_not_bypass_filters_or_empty_retrieval(self):
        for query, filters in [("artículo 1", Filters()), ("general", Filters(ambito="transitorio")), ("general", Filters(articulo="1"))]:
            self.assertEqual(len(self.backend.retrieve(query, 1, filters)), 1)
        self.search.return_value = []
        self.assertEqual(self.backend.retrieve("ley 21.719", 3, Filters()), [])

    def test_prompt_receives_origin_relation_and_literal_parent(self):
        # generate() ahora usa el prompt/contexto de Juan (etapa2_rag.rag.chain
        # + prompts.build_context): CONTEXTO va en el mensaje humano, no en
        # JSON dentro del system prompt como antes -- se verifica que la
        # relacion con la ley de fondo (ley_referenciada) y el fragmento
        # "portada" literal igual lleguen al LLM.
        sources = self.backend.retrieve("ley 21.719", 3, Filters())
        self.backend.generate("De qué trata", [], sources)
        context_text = self.calls[-1][1].content
        self.assertIn("modifica la Ley 19.628", context_text)
        self.assertIn("21.719", context_text)
        self.assertIn(self.backend.document_context.texto, context_text)

    def test_parent_citation_resolves_to_actual_pdf_page(self):
        client = TestClient(create_app(self.backend, mode="live"))
        with patch.object(self.backend, "plan_query", return_value={"kind": "document", "query": "ley 21.719"}):
            response = client.post("/chat", json={"message": "De qué trata la ley 21.719"})
        self.assertEqual(response.status_code, 200)
        source = response.json()["sources"][0]
        self.assertEqual(source["url"], "/api/source.pdf#page=1")
        self.assertIn("Página 1", source["label"])

    def test_parent_cannot_be_cited_when_not_in_retrieved_set(self):
        client = TestClient(create_app(self.backend, mode="live"))
        with patch.object(self.backend, "generate", return_value=Generation(answer="[doc-21719-p1]", cited_chunk_ids=["doc-21719-p1"])):
            self.assertEqual(client.post("/chat", json={"message": "artículo 1"}).status_code, 503)


if __name__ == "__main__":
    unittest.main()
