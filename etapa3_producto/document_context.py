"""Contexto padre citable del PDF; complemento del retrieval, no respuesta fija."""

import hashlib
import json
from pathlib import Path

from .contracts import Filters, Source

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path(__file__).with_name("document_context.json")


def load_document_context() -> Source:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    pdf = ROOT / "docs/Ley-21719_13-DIC-2024.pdf"
    if hashlib.sha256(pdf.read_bytes()).hexdigest() != manifest["pdf_sha256"]:
        raise RuntimeError("El PDF cambió: regenerar y revisar su contexto documental")
    return Source.model_validate(manifest["source"])


def with_document_context(sources: list[Source], parent: Source, filters: Filters, *, explicit_article: bool) -> list[Source]:
    # No ampliar silenciosamente búsquedas acotadas ni ocultar una búsqueda vacía.
    if not sources or explicit_article or filters.model_dump(exclude_none=True):
        return sources
    return [*sources, parent] if parent.chunk_id not in {s.chunk_id for s in sources} else sources
