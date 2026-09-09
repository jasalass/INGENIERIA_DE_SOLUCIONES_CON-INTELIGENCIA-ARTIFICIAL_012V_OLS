# Asistente RAG — Ley N°21.719 (Protección de Datos Personales, Chile)

Evaluación Parcial N°1 — ISY0101 Ingeniería de Soluciones con IA.
Sistema RAG (Retrieval-Augmented Generation) que responde consultas sobre la Ley N°21.719 con respuestas trazables a artículos, expuesto vía API y consumido desde una interfaz de chat en navegador.

## Equipo

- Juan Salas
- Pamela Alvarez
- Jenaro Marín

## Reparto de tareas

### Etapa 1 — Datos (Pamela)
Fuentes → Ingesta/preprocesamiento → Chunking

- Obtener el texto oficial de la Ley N°21.719
- Extracción de texto y limpieza/normalización
- Detección de estructura (títulos, artículos, incisos) y metadatos (artículo, título, fecha)
- Definir y justificar estrategia de chunking (tamaño, overlap)
- Entregable: dataset limpio + chunks con metadatos (JSON) + justificación documentada

### Etapa 2 — Motor RAG (Juan)
Embeddings → Base vectorial → Retrieval → Prompts

- Generar embeddings de los chunks (`mistral-embed`, API de Mistral)
- Indexar en base de datos vectorial (PostgreSQL + pgvector, en contenedor Docker separado)
- Implementar función de retrieval (top-k, filtros por metadatos vía SQL: artículo, tema, fecha)
- Formular y justificar prompts optimizados para el caso
- Entregable: pipeline de indexado + retrieval + set de prompts documentados

### Etapa 3 — Producto (Jenaro)
Generación aumentada → API → Interfaz de chat

- Orquestación LLM (LangChain): integra retrieval + generación, cita artículos, maneja contexto conversacional
- API backend (FastAPI) que expone el RAG y consulta al contenedor de pgvector
- Interfaz de chat en navegador conectada a la API
- Pruebas de coherencia (datos recuperados ↔ respuesta) y evidencia de funcionamiento
- Entregable: API + UI funcional + evidencia de pruebas

### Transversal (los 3)
- Diagrama de arquitectura completo
- Informe técnico (máx. 5 páginas, APA)
- README de instalación/ejecución (Docker)
- Reflexión individual de cada integrante (sin uso de IA)
- Preparación y ensayo de la defensa oral (20 min)

## Estado de avance

### Etapa 1 — Datos (Pamela) — ✅ completa

Pipeline de 5 fases en [`etapa1_datos/`](etapa1_datos/), documentado a fondo en [`etapa1_datos/justificacion_chunking.md`](etapa1_datos/justificacion_chunking.md):

1. [`scripts/extract_pdf.py`](etapa1_datos/scripts/extract_pdf.py) — extrae el texto con PyMuPDF (`fitz`) desde [`docs/Ley-21719_13-DIC-2024.pdf`](docs/Ley-21719_13-DIC-2024.pdf) + metadatos de fecha (publicación/promulgación) por regex.
2. [`scripts/clean_text.py`](etapa1_datos/scripts/clean_text.py) — limpia headers/footers/anotaciones marginales del Diario Oficial y reconstruye párrafos.
3. [`scripts/parse_structure.py`](etapa1_datos/scripts/parse_structure.py) — reconstruye la jerarquía real de la ley (es una ley **modificatoria**, no consolidada): niveles "Artículo primero/segundo/...", Títulos, artículos reales (con sufijos bis/ter/etc.) e instrucciones legislativas autocontenidas.
4. [`scripts/chunk_and_export.py`](etapa1_datos/scripts/chunk_and_export.py) — regla base **1 artículo = 1 chunk** (necesaria para que Etapa 2 filtre por artículo vía SQL y cite la fuente); solo se subdivide por inciso, con overlap de 1 inciso, cuando un artículo supera 2000 caracteres.
5. [`scripts/validate_chunks.py`](etapa1_datos/scripts/validate_chunks.py) — checklist de verificación (conteo cruzado independiente, muestra manual, trazabilidad de longitud).

**Resultado**: [`data/processed/chunks.json`](etapa1_datos/data/processed/chunks.json) — **140 chunks** (79 artículos reales + 11 nivel1/transitorios + 5 instrucciones autocontenidas), con metadatos por chunk (`articulo`, `titulo_numero`, `titulo_nombre`, `ambito`, `ley_referenciada`, `parte`, `fecha_publicacion`, `fecha_promulgacion`, `fuente`). Conteo de artículos verificado por dos métodos independientes (coinciden en 79); 0 chunks vacíos o sospechosamente cortos.

**Limitación documentada a propósito** (relevante para Etapa 2 y para el informe): al ser una ley modificatoria, secciones que esta ley no modifica —como el Título III de la Ley 19.628— **no existen en el dataset**. El sistema debe responder que está fuera de alcance en vez de inventar contenido; es el caso de prueba anti-alucinación de la Etapa 2.

### Etapa 2 — Motor RAG (Juan) — ✅ completa, validada de punta a punta

Código en [`etapa2_rag/`](etapa2_rag/):

- [`docker-compose.yml`](etapa2_rag/docker-compose.yml) — contenedor `pgvector/pgvector:pg16`, con [`sql/001_schema.sql`](etapa2_rag/sql/001_schema.sql) montado como init script (se aplica solo al crear el volumen).
- **Esquema** ([`sql/001_schema.sql`](etapa2_rag/sql/001_schema.sql)): tabla `chunks` con una columna por cada campo del `chunks.json` de Pamela + `embedding vector(1024)`; índice `ivfflat` (distancia coseno) sobre `embedding` e índices btree sobre `articulo`/`titulo_numero`/`ambito` para los filtros SQL.
- [`rag/embeddings.py`](etapa2_rag/rag/embeddings.py) — `mistral-embed` (API de Mistral, 1024 dimensiones) vía HTTP directo (`requests`).
- [`rag/retrieval.py`](etapa2_rag/rag/retrieval.py) — `search(query, top_k, filtros)`: embebe la consulta y ordena por distancia coseno (`<=>`), con `WHERE` dinámico por artículo/título/ámbito.
- [`rag/prompts.py`](etapa2_rag/rag/prompts.py) — system prompt que obliga a responder solo con el contexto recuperado, citar el artículo de cada afirmación, y declarar explícitamente cuando el contexto no alcanza (evita alucinar sobre las secciones no cubiertas por esta ley).
- [`rag/chain.py`](etapa2_rag/rag/chain.py) — `answer_question(question, history, filtros)`: retrieval + LLM (`ChatOpenAI` vía `LLM_BASE_URL`/`LLM_API_KEY`, actualmente Groq `openai/gpt-oss-20b`), devuelve `{"answer": ..., "sources": [...]}` — **este es el contrato que la API de Jenaro debe importar y consumir**.
- [`scripts/build_index.py`](etapa2_rag/scripts/build_index.py) — indexa `chunks.json` en pgvector (upsert por `chunk_id`, en lotes de 20).
- [`scripts/test_retrieval.py`](etapa2_rag/scripts/test_retrieval.py) — 8 preguntas de prueba, incluyendo una fuera de alcance a propósito (Título III / derechos ARCO) para verificar que el sistema no alucina.

**Por qué Mistral y no Gemini para embeddings**: se intentó primero `gemini-embedding-001` (igual que `docs/RA1/IL1.3`), pero la cuenta de Google devolvía `API_KEY_SERVICE_BLOCKED` en el 100% de las llamadas (probado con 3 keys, 2 métodos de auth, 2 versiones de API, distintos modelos, y hasta un `ListModels` de solo lectura) — es un bloqueo de cuenta/proyecto de Google, no arreglable desde el código. Groq (el proveedor de chat) tampoco sirve para embeddings: confirmado consultando `GET /v1/models`, no tiene ninguno. `mistral-embed` funcionó al primer intento. Justificar este cambio de proveedor en el informe (IE3/IE8) — es una decisión de arquitectura real, no solo una elección arbitraria.

**Validado de punta a punta en esta máquina** (no solo sintaxis/mocks):
- Contenedor `pgvector` levantado, esquema aplicado, **140/140 chunks indexados** con embeddings reales de `mistral-embed`.
- `scripts/test_retrieval.py` corrido completo (8/8 preguntas): respuestas coherentes y citadas correctamente a sus artículos (ej. "derechos del titular" → cita art. 4, 10, 14, 3, 5; "sanciones" → cita art. 35 con la tabla de multas correcta). El caso anti-alucinación (Título III / derechos ARCO, que no existe en el dataset) respondió correctamente que la ley no aborda esa consulta, en vez de inventar.
- **Limitación encontrada y sin resolver todavía**: preguntas que piden un artículo puntual por número (ej. *"¿Qué dice el artículo 4?"*) a veces no recuperan ese artículo exacto por similitud semántica pura (el retrieval trajo art-1/42/23/44/47, no art-4) y el sistema responde "no aborda esta consulta" en vez de citarlo — aunque el artículo sí existe en el dataset (se ve en la primera pregunta, donde sí se citó bien). Mejora pendiente: detectar un número de artículo explícito en la pregunta y aplicar `filtros={"articulo": "N"}` automáticamente en vez de depender solo de la búsqueda semántica. Vale la pena mencionarlo en el informe como limitación conocida (IE6).
- Nota de infraestructura: el tier gratuito de Groq limita tokens/minuto — `test_retrieval.py` espacía las preguntas con `time.sleep(8)` para no toparse con el rate limit en una corrida de 8 preguntas seguidas.

### Etapa 3 — Producto (Jenaro) — pendiente

## Cómo ejecutar

### Requisitos
- Python 3.12, Docker Desktop
- Copiar [`.env.example`](.env.example) a `.env` y completar `MISTRAL_API_KEY` ([console.mistral.ai/api-keys](https://console.mistral.ai/api-keys), embeddings) y `LLM_API_KEY` ([console.groq.com/keys](https://console.groq.com/keys), chat)
- `pip install -r requirements.txt`

### Etapa 1 — regenerar los chunks (opcional, ya están generados en el repo)
```bash
python etapa1_datos/scripts/extract_pdf.py
python etapa1_datos/scripts/clean_text.py
python etapa1_datos/scripts/parse_structure.py
python etapa1_datos/scripts/chunk_and_export.py
python etapa1_datos/scripts/validate_chunks.py
```

### Etapa 2 — levantar pgvector e indexar
```bash
cd etapa2_rag
docker compose up -d          # levanta Postgres+pgvector en localhost:5433
python scripts/build_index.py # indexa los 140 chunks (requiere MISTRAL_API_KEY)
python scripts/test_retrieval.py  # prueba retrieval + generación (requiere LLM_API_KEY)
```

## Calendario (1 semana — todo listo el día 6, entrega día 7)

| Día | Pamela | Juan | Jenaro | Checkpoint |
|---|---|---|---|---|
| 1 | Descarga texto oficial, inicia extracción/limpieza | Deja entorno listo (API keys, contenedor Postgres+pgvector) + pipeline de embeddings | Scaffold del repo + esqueleto API/UI de chat | Alcance del caso y diagrama de arquitectura v0 definidos entre los 3 |
| 2 | Limpieza completa + segmentación por artículos + chunking justificado | Prueba pipeline de embeddings con chunks dummy | Endpoint `/chat` mock + UI conectada | Pamela entrega chunks + metadatos (JSON) a Juan |
| 3 | Documenta chunking, apoya en prompts | Embeddings reales → indexado en pgvector → función de retrieval | Conecta UI a endpoint mock + memoria conversacional | Retrieval probado con 3-4 preguntas |
| 4 | Tabla de trazabilidad pregunta→chunks→respuesta + avanza informe | Prompts + integración LLM vía LangChain | Conecta endpoint real (retrieval → LLM → respuesta) con la UI | Demo end-to-end con 5 preguntas |
| 5 | Cierra diagrama de arquitectura + sigue informe | Maneja casos límite (evitar alucinaciones fuera de alcance) | Pulido UI (loading state, mostrar artículo citado) | Batería de 10-15 preguntas probada, evidencia capturada |
| 6 | Informe técnico completo, reflexión individual | Informe técnico completo, reflexión individual | README + verificación de repo desde cero, reflexión individual | Repo, informe y presentación en estado entregable — nada pendiente |
| 7 | — | — | — | Solo entrega: envío por AVA + correo al docente |

## Stack técnico

Python, LangChain, embeddings `mistral-embed` (API de Mistral, 1024 dims), PostgreSQL + pgvector (vector store, en contenedor Docker propio, imagen `pgvector/pgvector:pg16`), LLM de chat Groq (`openai/gpt-oss-20b`, API compatible con OpenAI), FastAPI (backend, consulta al contenedor de pgvector), frontend HTML/JS simple, docker-compose con servicios `db` (pgvector), `api` y `frontend` para levantar todo el sistema con un solo comando.


