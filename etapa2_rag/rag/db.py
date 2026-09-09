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
    conn = psycopg.connect(database_url, autocommit=True)
    register_vector(conn)
    return conn
