"""
Indexa etapa1_datos/data/processed/chunks.json (140 chunks, Etapa 1 -
Pamela) en la tabla `chunks` de Postgres+pgvector.

Requiere MISTRAL_API_KEY (embeddings) y DATABASE_URL (conexion a la BD
del contenedor levantado por `docker compose up -d` en este directorio).

Uso: desde etapa2_rag/, `python scripts/build_index.py`
"""

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from rag.db import get_connection  # noqa: E402
from rag.embeddings import embed_documents  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CHUNKS_PATH = REPO_ROOT / "etapa1_datos" / "data" / "processed" / "chunks.json"

# Evita mandar 140 textos en una sola llamada a la API de embeddings.
BATCH_SIZE = 20

UPSERT_SQL = """
INSERT INTO chunks (
    chunk_id, id, nivel1, ley_referenciada, ambito, titulo_numero,
    titulo_nombre, articulo, articulo_sufijo, articulo_nombre, parte,
    texto, fecha_publicacion, fecha_promulgacion, fuente, embedding
) VALUES (
    %(chunk_id)s, %(id)s, %(nivel1)s, %(ley_referenciada)s, %(ambito)s,
    %(titulo_numero)s, %(titulo_nombre)s, %(articulo)s, %(articulo_sufijo)s,
    %(articulo_nombre)s, %(parte)s, %(texto)s, %(fecha_publicacion)s,
    %(fecha_promulgacion)s, %(fuente)s, %(embedding)s
)
ON CONFLICT (chunk_id) DO UPDATE SET
    texto = EXCLUDED.texto,
    embedding = EXCLUDED.embedding,
    articulo = EXCLUDED.articulo,
    titulo_numero = EXCLUDED.titulo_numero,
    titulo_nombre = EXCLUDED.titulo_nombre,
    ambito = EXCLUDED.ambito,
    fecha_publicacion = EXCLUDED.fecha_publicacion,
    fecha_promulgacion = EXCLUDED.fecha_promulgacion,
    fuente = EXCLUDED.fuente;
"""


def batched(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


def main() -> None:
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        chunks = json.load(f)

    print(f"Cargados {len(chunks)} chunks desde {CHUNKS_PATH}")

    conn = get_connection()
    indexados = 0

    for batch in batched(chunks, BATCH_SIZE):
        textos = [c["texto"] for c in batch]
        vectores = embed_documents(textos)

        with conn.cursor() as cur:
            for chunk, vector in zip(batch, vectores):
                # numpy.array: register_vector() (rag/db.py) solo sabe
                # convertir arrays de numpy al tipo `vector` de pgvector.
                params = {**chunk, "embedding": np.array(vector)}
                cur.execute(UPSERT_SQL, params)

        indexados += len(batch)
        print(f"  Indexados {indexados}/{len(chunks)}")

    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM chunks")
        total = cur.fetchone()[0]
    conn.close()

    print(f"Listo. Filas en la tabla chunks: {total}")


if __name__ == "__main__":
    main()
