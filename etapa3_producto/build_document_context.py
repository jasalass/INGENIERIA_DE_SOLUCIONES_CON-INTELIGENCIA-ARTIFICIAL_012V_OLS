"""Deriva dos extractos literales de página 1; no modifica PDF, chunks ni índice.

Ejecutar desde Windows: python -m etapa3_producto.build_document_context.
Requiere pymupdf del requirements.txt raíz; no necesario en el servidor.
"""

import hashlib
import json
import re

import pymupdf

from .document_context import MANIFEST, ROOT


def extract_context(pdf):
    with pymupdf.open(pdf) as document:
        text = re.sub(r"\s+", " ", document[0].get_text()).strip()
    title = re.search(r"LEY NÚM\. 21\.719.*?(?= Teniendo presente)", text)
    relation = re.search(r"Artículo primero\.-.*?vida privada:", text)
    if not title or not relation or "19.628" not in relation[0]:
        raise ValueError("Cambió la estructura del PDF: revisar la extracción, no inventar contexto")
    return {
        "pdf_sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
        "method": "Página 1: título y encabezado del artículo primero; solo normalización de espacios. Extractos separados, no texto continuo.",
        "source": {
            "chunk_id": "doc-21719-p1", "documento_origen": "21.719",
            "pagina_pdf": 1, "fuente": "Biblioteca del Congreso Nacional (leychile.cl)",
            "texto": title[0] + "\n\n[…]\n\n" + relation[0],
            "titulo_nombre": "Título del documento y encabezado del artículo primero",
        },
    }


if __name__ == "__main__":
    result = extract_context(ROOT / "docs/Ley-21719_13-DIC-2024.pdf")
    MANIFEST.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Contexto derivado: {MANIFEST.name}; PDF original intacto")
