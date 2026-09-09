"""Demo determinista: coincidencia de palabras y extractos literales. Sin LLM."""

import json
import re
import unicodedata
from pathlib import Path
from .contracts import Filters, Generation, Source, Turn


def normalize(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")


STOP = set("a al algo como con cual cuales cuando de del el en es esta este estos la las le lo los me mi para por que quien se si sin sobre su sus tiene un una y ley articulo dice decir puedes favor mas explica explicar".split())


class DemoBackend:
    def __init__(self, chunks_path: Path):
        self.chunks = [Source.model_validate(c) for c in json.loads(chunks_path.read_text(encoding="utf-8"))]

    def retrieve(self, query: str, top_k: int, filters: Filters) -> list[Source]:
        words = set(re.findall(r"[a-z]{3,}", normalize(query))) - STOP
        match = re.search(r"articulo\s+(\d+)(?:\s+(bis|ter|quater|quinquies|sexies|septies|octies|nonies))?\b", normalize(query))
        candidates = []
        for chunk in self.chunks:
            if any(getattr(chunk, key) != value for key, value in filters.model_dump(exclude_none=True).items()):
                continue
            if match and (chunk.articulo != match[1] or normalize(chunk.articulo_sufijo or "") != (match[2] or "")):
                continue
            terms = set(re.findall(r"[a-z]{3,}", normalize(chunk.texto)))
            score = len(words & terms)
            # Una petición de vista general del ámbito seleccionado no exige
            # que la palabra «disposiciones» aparezca en cada fragmento.
            if filters.ambito and "disposiciones" in words:
                score = max(score, 1)
            if match or score >= 1 or filters.articulo:
                candidates.append(chunk.model_copy(update={"score": float(score)}))
        return sorted(candidates, key=lambda c: (-c.score, c.chunk_id))[:top_k]

    def generate(self, question: str, history: list[Turn], sources: list[Source]) -> Generation:
        if not sources:
            return Generation(answer="No encontré fragmentos para esta consulta en la búsqueda de demostración. Prueba indicando un artículo o reformulando la pregunta. Esto no demuestra que la ley no trate el tema.", cited_chunk_ids=[], insufficient_context=True)
        excerpts = [f"{source.label} [{source.chunk_id}]\n«{source.texto[:650]}{'…' if len(source.texto) > 650 else ''}»" for source in sources]
        return Generation(answer="Demostración: estos son extractos literales seleccionados por coincidencia de palabras. No se ha generado una respuesta con IA.\n\n" + "\n\n".join(excerpts), cited_chunk_ids=[s.chunk_id for s in sources])
