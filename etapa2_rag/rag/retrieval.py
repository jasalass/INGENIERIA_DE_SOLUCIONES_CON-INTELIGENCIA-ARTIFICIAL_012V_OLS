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

from .db import get_connection
from .embeddings import embed_query

FILTERABLE_FIELDS = {"articulo", "articulo_sufijo", "titulo_numero", "ambito"}

BASE_SELECT = """
SELECT chunk_id, articulo, articulo_sufijo, articulo_nombre, titulo_numero,
       titulo_nombre, ambito, parte, texto, fuente, nivel1, ley_referenciada,
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
    if not 1 <= top_k <= 20:
        raise ValueError("top_k debe estar entre 1 y 20")
    if set(filtros or {}) - FILTERABLE_FIELDS:
        raise ValueError("Filtro no permitido")
    # register_vector() (rag/db.py) solo sabe convertir numpy.ndarray al
    # tipo `vector` de pgvector -- una lista plana de Python se manda
    # como double precision[] y pgvector la rechaza en el operador `<=>`.
    query_embedding = np.array(embed_query(query))

    where_clauses = []
    params: dict = {"query_embedding": query_embedding, "top_k": top_k}

    for campo, valor in (filtros or {}).items():
        if campo not in FILTERABLE_FIELDS:
            raise ValueError(f"Filtro no permitido: {campo!r} (validos: {FILTERABLE_FIELDS})")
        if valor is None:
            where_clauses.append(f"{campo} IS NULL")
        else:
            where_clauses.append(f"{campo} = %({campo})s")
            params[campo] = valor

    sql = BASE_SELECT
    if where_clauses:
        sql += "WHERE " + " AND ".join(where_clauses) + "\n"
    sql += "ORDER BY distancia ASC, chunk_id ASC LIMIT %(top_k)s"

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            # No se fuerza "SET LOCAL enable_indexscan = off": eso apagaba
            # TODOS los index scans de la consulta, incluidos los btree de
            # articulo/titulo_numero/ambito que existen justo para estos
            # filtros, no solo el ivfflat del vector. El ranking exacto por
            # coseno (sin perdida de recall del ANN) se logra en su lugar no
            # creando el indice ivfflat mientras el corpus sea chico -- ver
            # sql/001_schema.sql.
            cur.execute(sql, params)
            columnas = [desc.name for desc in cur.description]
            filas = cur.fetchall()
    finally:
        conn.close()

    return [dict(zip(columnas, fila)) for fila in filas]
