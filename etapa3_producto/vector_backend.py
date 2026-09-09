"""Adaptación de search() de Juan al contrato de API/citas/memoria de Jenaro.

No duplica el recuperador: usa Mistral + pgvector de etapa2_rag. La generación
mantiene el cliente Groq probado y el historial RA1; chain.py queda como demo CLI.
"""

import os
import re
from pathlib import Path

from etapa2_rag.rag.retrieval import search
from .contracts import Filters, Source
from .demo import normalize
from .groq_backend import GroqBackend
from .document_context import with_document_context

ARTICLE = re.compile(r"articulo\s*(?:n[°ºo.]?\s*)?(\d+)(?:\s*[°º])?(?:\s+(bis|ter|quater|quinquies|sexies|septies|octies|nonies))?\b")


class VectorBackend(GroqBackend):
    retrieval_name = "pgvector_cosine_exact"
    generation_name = "groq"

    def __init__(self, chunks_path: Path, *, model_client=None, search_fn=None):
        super().__init__(chunks_path, model_client=model_client)
        if search_fn is None:
            if not os.getenv("MISTRAL_API_KEY") or not os.getenv("DATABASE_URL"):
                raise RuntimeError("Modo live requiere MISTRAL_API_KEY y DATABASE_URL; sin fallback")
        self.search_fn = search_fn or search

    def retrieve(self, query: str, top_k: int, filters: Filters) -> list[Source]:
        selected = filters.model_dump(exclude_none=True)
        match = ARTICLE.search(normalize(query))
        if match:
            article, suffix = match.groups()
            # Un filtro explícito contradictorio debe producir cero resultados,
            # no ignorarse silenciosamente ni buscar otro artículo.
            if filters.articulo and filters.articulo != article:
                return []
            if filters.articulo_sufijo and filters.articulo_sufijo != suffix:
                return []
            selected.update(articulo=article, articulo_sufijo=suffix)
        elif filters.articulo and not filters.articulo_sufijo:
            selected["articulo_sufijo"] = None
        rows = self.search_fn(query, top_k=top_k, filtros=selected)
        # score es similitud coseno, no probabilidad ni medida de certeza jurídica.
        sources = [Source.model_validate({**row, "score": 1.0 - float(row["distancia"])}) for row in rows]
        return with_document_context(sources, self.document_context, filters, explicit_article=bool(match))


def create_backend():
    return VectorBackend(Path(__file__).resolve().parents[1] / "etapa1_datos/data/processed/chunks.json")
