-- Esquema de la Etapa 2 (Motor RAG). Se aplica automaticamente al crear
-- el volumen de Postgres por primera vez (ver docker-compose.yml).
--
-- Las columnas replican 1:1 los campos de etapa1_datos/data/processed/chunks.json
-- (140 chunks producidos por Pamela) para poder insertar cada chunk sin
-- transformarlo. `embedding` se agrega como columna propia de esta etapa.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id            TEXT PRIMARY KEY,
    id                  TEXT NOT NULL,
    nivel1              TEXT,
    ley_referenciada    TEXT,
    ambito              TEXT,
    titulo_numero       TEXT,
    titulo_nombre       TEXT,
    articulo            TEXT,
    articulo_sufijo     TEXT,
    articulo_nombre     TEXT,
    parte               TEXT,
    texto               TEXT NOT NULL,
    fecha_publicacion   DATE,
    fecha_promulgacion  DATE,
    fuente              TEXT,
    -- mistral-embed (API de Mistral) devuelve vectores de 1024
    -- dimensiones. Se uso en vez de gemini-embedding-001 (768 dims,
    -- docs/RA1/IL1.3) porque la cuenta de Google quedo bloqueada a
    -- nivel de proyecto (API_KEY_SERVICE_BLOCKED) -- ver rag/embeddings.py.
    embedding           vector(1024) NOT NULL
);

-- Con 140 chunks, un sequential scan ya es rapido (no hace falta un
-- indice aproximado). Se agrega igual un indice ivfflat para dejar el
-- patron correcto documentado si el corpus crece (ej. se agregan
-- reglamentos u otras leyes). lists=10 es razonable para un corpus
-- chico -- valores muy altos con pocas filas degradan la calidad del
-- indice en vez de mejorarla.
CREATE INDEX IF NOT EXISTS chunks_embedding_idx
    ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 10);

-- Indices para los filtros de metadatos que usa rag/retrieval.py
-- (busqueda acotada por articulo, titulo o ambito antes de rankear por
-- similitud).
CREATE INDEX IF NOT EXISTS chunks_articulo_idx ON chunks (articulo);
CREATE INDEX IF NOT EXISTS chunks_titulo_numero_idx ON chunks (titulo_numero);
CREATE INDEX IF NOT EXISTS chunks_ambito_idx ON chunks (ambito);
