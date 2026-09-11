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
    # Configurables por env var (no solo hardcodeados) para que un corpus mas
    # grande o una maquina mas lenta puedan subir estos limites sin editar
    # codigo -- ver hallazgo de revision sobre el timeout fijo de 5s.
    connect_timeout = int(os.getenv("DB_CONNECT_TIMEOUT_S", "5"))
    statement_timeout_ms = int(os.getenv("DB_STATEMENT_TIMEOUT_MS", "5000"))
    conn = psycopg.connect(
        database_url,
        autocommit=True,
        connect_timeout=connect_timeout,
        options=f"-c statement_timeout={statement_timeout_ms}",
    )
    try:
        register_vector(conn)
    except Exception:
        conn.close()
        raise
    return conn
