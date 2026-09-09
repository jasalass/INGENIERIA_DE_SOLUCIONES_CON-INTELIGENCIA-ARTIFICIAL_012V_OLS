"""
Conexion a Postgres+pgvector (contenedor levantado por docker-compose.yml).

register_vector() le enseña a psycopg3 a convertir listas de floats de
Python al tipo `vector` de la extension pgvector (y de vuelta), asi
retrieval.py y build_index.py pueden pasar/leer embeddings como listas
comunes sin serializar nada a mano.
"""

import os

import psycopg
from pgvector.psycopg import register_vector


def get_connection() -> psycopg.Connection:
    database_url = os.environ["DATABASE_URL"]
    conn = psycopg.connect(database_url, autocommit=True, connect_timeout=5,
                           options="-c statement_timeout=5000")
    try:
        register_vector(conn)
    except Exception:
        conn.close()
        raise
    return conn
