"""
Recuperacion semantica sobre la tabla `chunks` (Postgres+pgvector).

search() calcula el embedding de la consulta y ordena los chunks por
distancia coseno (`<=>` es el operador de pgvector para distancia
coseno). Los filtros de metadatos (articulo, titulo_numero, ambito) se
arman como WHERE dinamico -- es lo que permite acotar la busqueda antes
de rankear por similitud (ej. "solo dentro del articulo 12"), tal como
pide la infografia del proyecto (docs/infografia.jpeg, paso 5: "Filtros
por metadatos").
"""

import numpy as np

from rag.db import get_connection
from rag.embeddings import embed_query

FILTERABLE_FIELDS = {"articulo", "titulo_numero", "ambito"}

BASE_SELECT = """
SELECT chunk_id, articulo, articulo_sufijo, articulo_nombre, titulo_numero,
       titulo_nombre, ambito, parte, texto, fuente,
       fecha_publicacion, fecha_promulgacion,
       embedding <=> %(query_embedding)s AS distancia
FROM chunks
"""


def search(query: str, top_k: int = 5, filtros: dict | None = None) -> list[dict]:
    """Devuelve hasta `top_k` chunks ordenados por similitud a `query`.

    `filtros` es un dict opcional con claves en FILTERABLE_FIELDS
    (ej. {"articulo": "12"}) para acotar la busqueda por metadatos antes
    de rankear por distancia coseno.
    """
    # register_vector() (rag/db.py) solo sabe convertir numpy.ndarray al
    # tipo `vector` de pgvector -- una lista plana de Python se manda
    # como double precision[] y pgvector la rechaza en el operador `<=>`.
    query_embedding = np.array(embed_query(query))

    where_clauses = []
    params: dict = {"query_embedding": query_embedding, "top_k": top_k}

    for campo, valor in (filtros or {}).items():
        if campo not in FILTERABLE_FIELDS:
            raise ValueError(f"Filtro no permitido: {campo!r} (validos: {FILTERABLE_FIELDS})")
        where_clauses.append(f"{campo} = %({campo})s")
        params[campo] = valor

    sql = BASE_SELECT
    if where_clauses:
        sql += "WHERE " + " AND ".join(where_clauses) + "\n"
    sql += "ORDER BY distancia ASC LIMIT %(top_k)s"

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            columnas = [desc.name for desc in cur.description]
            filas = cur.fetchall()
    finally:
        conn.close()

    return [dict(zip(columnas, fila)) for fila in filas]
