"""Contratos de integración, sin llamadas externas ni escritura en la base."""

import unittest
from contextlib import nullcontext
from unittest.mock import MagicMock, patch

import numpy as np
from fastapi.testclient import TestClient
from langchain_core.runnables import RunnableLambda

from etapa2_rag.rag import embeddings, retrieval
from etapa3_producto.app import ROOT, create_app
from etapa3_producto.contracts import Filters, Generation
from etapa3_producto.vector_backend import VectorBackend


class VectorTests(unittest.TestCase):
    def setUp(self):
        self.search = MagicMock(return_value=[])
        self.backend = VectorBackend(ROOT / "etapa1_datos/data/processed/chunks.json", search_fn=self.search, model_client=RunnableLambda(lambda value: value))

    def test_exact_articles_preserve_number_and_suffix(self):
        for question, number, suffix in (("artículo 4", "4", None), ("Artículo N° 1 bis", "1", "bis"), ("artículo 12 ter", "12", "ter")):
            self.backend.retrieve(question, 3, Filters())
            self.assertEqual(self.search.call_args.kwargs["filtros"], {"articulo": number, "articulo_sufijo": suffix})

    def test_scope_and_suffix_reach_sql_filters(self):
        self.backend.retrieve("artículo 4", 2, Filters(ambito="transitorio"))
        self.assertEqual(self.search.call_args.kwargs["filtros"]["ambito"], "transitorio")
        self.assertIsNone(self.search.call_args.kwargs["filtros"]["articulo_sufijo"])

    def test_conflicting_filters_abstain_without_network(self):
        for filters in (Filters(articulo="12"), Filters(articulo_sufijo="bis")):
            self.assertEqual(self.backend.retrieve("artículo 4", 3, filters), [])
        self.search.assert_not_called()

    def test_general_question_reaches_semantic_search(self):
        self.backend.retrieve("¿Qué derechos tengo sobre mis datos?", 3, Filters())
        self.search.assert_called_once_with("¿Qué derechos tengo sobre mis datos?", top_k=3, filtros={})

    def test_full_source_metadata_and_score(self):
        self.search.return_value = [{"chunk_id": "transitorio-primero", "texto": "Texto", "fuente": "BCN", "nivel1": "primero", "ambito": "transitorio", "ley_referenciada": "19.628", "distancia": 0.2}]
        result = self.backend.retrieve("transitorios", 3, Filters())[0]
        self.assertEqual(result.label, "Disposición transitoria: primero")
        self.assertEqual(result.score, 0.8)
        self.assertEqual(result.ley_referenciada, "19.628")

    def test_live_citation_guard_still_applies(self):
        self.search.return_value = [{"chunk_id": "art-4", "texto": "Texto", "fuente": "BCN", "distancia": 0.1}]
        client = TestClient(create_app(self.backend, mode="live"))
        with patch.object(self.backend, "generate", return_value=Generation(answer="Texto sin cita", cited_chunk_ids=["art-4"])):
            self.assertEqual(client.post("/chat", json={"message": "artículo 4"}).status_code, 503)
        health = client.get("/health").json()
        self.assertEqual(health["retrieval"], "pgvector_cosine_exact")
        self.assertEqual(health["generation"], "groq")

    def test_invalid_sql_filter_rejected_before_embedding(self):
        with patch.object(retrieval, "embed_query") as embed:
            for kwargs in ({"filtros": {"unsafe; DROP TABLE chunks": "x"}}, {"top_k": 0}, {"top_k": 21}):
                with self.assertRaises(ValueError):
                    retrieval.search("pregunta", **kwargs)
            embed.assert_not_called()

    def test_sql_parameterization_null_and_exact_ranking(self):
        conn = MagicMock()
        conn.transaction.return_value = nullcontext()
        cur = conn.cursor.return_value.__enter__.return_value
        cur.description = []
        cur.fetchall.return_value = []
        with patch.object(retrieval, "get_connection", return_value=conn), patch.object(retrieval, "embed_query", return_value=[1.0] * 1024):
            retrieval.search("query", filtros={"articulo": "4' OR '1'='1", "articulo_sufijo": None})
        sql, params = cur.execute.call_args.args
        self.assertIn("articulo_sufijo IS NULL", sql)
        self.assertNotIn("OR '1'", sql)
        self.assertEqual(params["articulo"], "4' OR '1'='1")
        self.assertIsInstance(params["query_embedding"], np.ndarray)
        self.assertEqual(cur.execute.call_args_list[0].args[0], "SET LOCAL enable_indexscan = off")
        conn.close.assert_called_once()

    def test_embeddings_reject_wrong_dimension_count_and_nan(self):
        for data in ([{"index": 0, "embedding": [1.0]}], [], [{"index": 0, "embedding": [float("nan")] * 1024}], [{"index": 0, "embedding": [0.0] * 1024}]):
            response = MagicMock(ok=True)
            response.json.return_value = {"data": data}
            with patch.object(embeddings.requests, "post", return_value=response):
                with self.assertRaises(ValueError):
                    embeddings.embed_query("texto")

    def test_embedding_http_error_does_not_leak_provider_body(self):
        response = MagicMock(ok=False, status_code=429)
        with patch.object(embeddings.requests, "post", return_value=response):
            with self.assertRaises(embeddings.EmbeddingProviderError) as caught:
                embeddings.embed_query("texto")
        self.assertEqual(caught.exception.status_code, 429)
        self.assertEqual(caught.exception.provider, "Mistral")


if __name__ == "__main__":
    unittest.main()
