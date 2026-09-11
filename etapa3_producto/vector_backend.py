"""Adaptación de retrieval + generación de Juan (etapa2_rag) al contrato de
API/sesiones/memoria de Jenaro.

Ni el recuperador ni la generación se duplican: `retrieve()` llama a
`etapa2_rag.rag.retrieval.search()` (Mistral + pgvector) y `generate()`
llama a `etapa2_rag.rag.chain.generate_answer()` (prompts + LLM) -- ambos
tal como los definió/probó la Etapa 2. Esta clase solo adapta filtros de
artículo/sufijo y el formato Source/Generation que usa la API; `plan_query`
(clasificación conversación/documento) y `converse` (charla personal) se
heredan de GroqBackend sin cambios, porque eso sí es responsabilidad de la
Etapa 3 ("maneja contexto conversacional").
"""

import os
from pathlib import Path

from etapa2_rag.rag.chain import generate_answer
from etapa2_rag.rag.retrieval import search
from .contracts import Filters, Generation, Source, Turn
from .demo import parse_article_reference
from .groq_backend import GroqBackend
from .document_context import with_document_context


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
        article, suffix = parse_article_reference(query)
        if article:
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
        return with_document_context(sources, self.document_context, filters, explicit_article=bool(article))

    def generate(self, question: str, history: list[Turn], sources: list[Source]) -> Generation:
        chunks = [s.model_dump() for s in sources]
        history_dicts = [{"role": t.role, "content": t.content} for t in history]
        result = generate_answer(question, history_dicts, chunks, llm=self.llm)
        return Generation.model_validate(result)


def create_backend():
    return VectorBackend(Path(__file__).resolve().parents[1] / "etapa1_datos/data/processed/chunks.json")
