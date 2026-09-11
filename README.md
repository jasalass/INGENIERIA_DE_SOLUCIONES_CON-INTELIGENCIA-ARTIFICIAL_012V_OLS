# Asistente RAG — Ley N°21.719 (Protección de Datos Personales, Chile)

Evaluación Parcial N°1 — ISY0101 Ingeniería de Soluciones con IA.
Sistema RAG (Retrieval-Augmented Generation) que responde consultas sobre la Ley N°21.719 con respuestas trazables a artículos, expuesto vía API y consumido desde una interfaz de chat en navegador.

📐 **[Diagrama de arquitectura](docs/arquitectura.html)** — preparación del índice y flujo de una consulta, paso a paso (IE4/IE7).

## Equipo

- Juan Salas
- Pamela Alvarez
- Jenaro Marín

## Arquitectura y flujo de una consulta

```
Navegador (frontend/, nginx :8080)
   │  POST /api/chat {message, conversation_id, filters}
   ▼
FastAPI (app.py, :8000)
   │  1. plan_query()          — Groq clasifica: ¿pregunta sobre la ley o charla personal?  [Jenaro]
   │  2a. kind=document → retrieve()
   │        embed_query() (Mistral) + search() (pgvector, filtros SQL)                       [Juan]
   │      → generate_answer() (prompts + LLM, JSON con cita [chunk_id])                       [Juan]
   │  2b. kind=conversation → converse() (responde con el historial de la sesión)              [Jenaro]
   │  3. Validación: citas visibles, chunk_id existente, sin razonamiento interno              [Jenaro]
   ▼
ChatResponse {answer, sources, insufficient_context, ...} → se pinta en el chat
```

La base de conocimiento (`etapa1_datos/data/processed/chunks.json`, 140 chunks) se indexa una sola vez en Postgres+pgvector (`etapa2_rag/scripts/build_index.py`); el flujo de arriba corre en cada consulta.

## Reparto de tareas (plan original)

| Etapa | Responsable | Alcance planificado |
|---|---|---|
| 1 — Datos | Pamela | Fuentes → ingesta/preprocesamiento → chunking |
| 2 — Motor RAG | Juan | Embeddings → base vectorial → retrieval → prompts/generación |
| 3 — Producto | Jenaro | Orquestación LLM (contexto conversacional) → API → interfaz de chat |
| Transversal | Los 3 | Arquitectura, informe, README, reflexión individual, defensa oral |

## Qué hizo cada uno, en detalle

### Pamela — Etapa 1: Datos (`etapa1_datos/`) — ✅ completa

Pipeline de 5 fases, documentado a fondo en [`etapa1_datos/justificacion_chunking.md`](etapa1_datos/justificacion_chunking.md):

| Script | Qué hace |
|---|---|
| [`scripts/extract_pdf.py`](etapa1_datos/scripts/extract_pdf.py) | Extrae el texto con PyMuPDF desde [`docs/Ley-21719_13-DIC-2024.pdf`](docs/Ley-21719_13-DIC-2024.pdf) + metadatos de fecha (publicación/promulgación) por regex. |
| [`scripts/clean_text.py`](etapa1_datos/scripts/clean_text.py) | Limpia headers/footers/anotaciones marginales del Diario Oficial y reconstruye párrafos. |
| [`scripts/parse_structure.py`](etapa1_datos/scripts/parse_structure.py) | Reconstruye la jerarquía real de la ley (es **modificatoria**, no consolidada): niveles "Artículo primero/segundo/...", Títulos, artículos reales (con sufijos bis/ter/etc.) e instrucciones legislativas autocontenidas. |
| [`scripts/chunk_and_export.py`](etapa1_datos/scripts/chunk_and_export.py) | Regla base **1 artículo = 1 chunk** (necesaria para filtrar por artículo vía SQL y citar la fuente); solo se subdivide por inciso, con overlap de 1 inciso, cuando un artículo supera 2000 caracteres. |
| [`scripts/validate_chunks.py`](etapa1_datos/scripts/validate_chunks.py) | Checklist de verificación: conteo cruzado independiente, muestra manual, trazabilidad de longitud. |

**Resultado**: `data/processed/chunks.json` — 140 chunks (79 artículos reales + 11 nivel1/transitorios + 5 instrucciones autocontenidas), con metadatos por chunk (`articulo`, `titulo_numero`, `titulo_nombre`, `ambito`, `ley_referenciada`, `parte`, fechas, `fuente`). Conteo de artículos verificado por dos métodos independientes (coinciden en 79); 0 chunks vacíos o sospechosamente cortos.

**Limitación documentada a propósito**: al ser una ley modificatoria, secciones que esta ley no modifica —como el Título III de la Ley 19.628— no existen en el dataset. El sistema debe responder que está fuera de alcance en vez de inventar contenido; es el caso de prueba anti-alucinación de todo el sistema (ver artículo 999 en las pruebas).

### Juan — Etapa 2: Motor RAG (`etapa2_rag/`) — ✅ completa, es lo que usa el producto real

| Archivo | Qué hace |
|---|---|
| [`docker-compose.yml`](etapa2_rag/docker-compose.yml) | Contenedor `pgvector/pgvector:pg16` standalone (para indexar/probar sin levantar la API completa). |
| [`sql/001_schema.sql`](etapa2_rag/sql/001_schema.sql) | Tabla `chunks` (una columna por campo de `chunks.json` + `embedding vector(1024)`) e índices btree por `articulo`/`titulo_numero`/`ambito`. No crea índice `ivfflat` (aproximado) mientras el corpus sea chico — ver comentario en el archivo sobre cuándo reactivarlo. |
| [`rag/db.py`](etapa2_rag/rag/db.py) | Conexión a Postgres (`register_vector` para el tipo `vector`), con `connect_timeout`/`statement_timeout` configurables por variable de entorno. |
| [`rag/embeddings.py`](etapa2_rag/rag/embeddings.py) | `mistral-embed` (API de Mistral, 1024 dimensiones) vía HTTP directo; valida cantidad, orden y finitud de los vectores devueltos. |
| [`rag/retrieval.py`](etapa2_rag/rag/retrieval.py) | `search(query, top_k, filtros)`: embebe la consulta y ordena por distancia coseno (`<=>`), con `WHERE` dinámico por artículo/sufijo/título/ámbito. |
| [`rag/prompts.py`](etapa2_rag/rag/prompts.py) | `SYSTEM_PROMPT` (responder solo con el contexto, citar `[chunk_id]` tal cual, no confundir la ley modificatoria con la ley de fondo, declarar `insufficient_context`), `build_context()` (arma el bloque de contexto con la relación entre leyes), `extract_cited_chunk_ids()` (deriva las citas reales del texto de la respuesta, nunca confía en lo que diga el LLM), `parse_json_response()` (tolera `<think>` y bloques de código). |
| [`rag/chain.py`](etapa2_rag/rag/chain.py) | `generate_answer(question, history, chunks, llm=None)`: la función de generación reutilizable — **este es el contrato que consume la API de Jenaro** (`etapa3_producto/vector_backend.py`). `answer_question()` es la versión de un solo paso (retrieval + generación) para el script de prueba standalone. |
| [`scripts/build_index.py`](etapa2_rag/scripts/build_index.py) | Indexa `chunks.json` en pgvector (upsert por `chunk_id`, lotes atómicos de 20, `ANALYZE` al final). Carga `.env` de la raíz del repo, con fallback a un `etapa2_rag/.env` propio. |
| [`scripts/test_retrieval.py`](etapa2_rag/scripts/test_retrieval.py) | 8 preguntas de prueba standalone, incluyendo una fuera de alcance a propósito, para verificar que el motor no alucina sin necesidad de levantar la API. |

**Por qué Mistral y no Gemini para embeddings**: se intentó primero `gemini-embedding-001`, pero la cuenta de Google devolvía `API_KEY_SERVICE_BLOCKED` en el 100% de las llamadas (probado con 3 keys, 2 métodos de auth, 2 versiones de API, distintos modelos, y hasta un `ListModels` de solo lectura) — bloqueo de cuenta/proyecto de Google, no arreglable desde el código. Groq (el proveedor de chat) tampoco ofrece embeddings. `mistral-embed` funcionó al primer intento.

### Jenaro — Etapa 3: Producto (`etapa3_producto/`) — ✅ completa

| Archivo | Qué hace |
|---|---|
| [`app.py`](etapa3_producto/app.py) | API FastAPI. Endpoints `POST /api/chat`, `GET /api/health`, `DELETE /api/conversations/{id}`, sirve `docs/Ley-21719_13-DIC-2024.pdf` y el frontend estático. Maneja sesiones en memoria (historial acotado a 6 intercambios, TTL, capacidad máxima), arma el pipeline `plan_query → retrieve/converse → generate` con `RunnableLambda`, y valida la respuesta antes de devolverla (citas visibles, sin chunk_id inventado, sin razonamiento `<think>` filtrado). |
| [`contracts.py`](etapa3_producto/contracts.py) | Modelos Pydantic compartidos: `Filters`, `ChatRequest`, `Source` (con `label`/`url` calculados), `Turn`, `Generation`, `QueryPlan`, `ChatResponse`, y el protocolo `Backend` (`retrieve`/`generate`). |
| [`demo.py`](etapa3_producto/demo.py) | `DemoBackend`: búsqueda léxica simple sin LLM (modo `demo`, para probar sin gastar cuota). También define `normalize()` y `parse_article_reference()` — el único lugar donde se detecta si una pregunta menciona un artículo explícito, usado por los 3 backends. |
| [`groq_backend.py`](etapa3_producto/groq_backend.py) | `GroqBackend(DemoBackend)`: agrega clasificación (`plan_query`, LLM con historial), charla personal (`converse`) y generación propia con búsqueda léxica (modo `groq`, sin pgvector — solo para probar el LLM sin la base de datos). |
| [`vector_backend.py`](etapa3_producto/vector_backend.py) | `VectorBackend(GroqBackend)`: **el backend real** (modo `live`). `retrieve()` llama a `etapa2_rag.rag.retrieval.search()`; `generate()` llama a `etapa2_rag.rag.chain.generate_answer()`. `plan_query`/`converse` se heredan de `GroqBackend` sin cambios (clasificar conversación vs. documento y responder charla personal es responsabilidad de esta etapa). |
| [`document_context.py`](etapa3_producto/document_context.py) + [`document_context.json`](etapa3_producto/document_context.json) + [`build_document_context.py`](etapa3_producto/build_document_context.py) | Agregan un chunk "portada" (página 1 del PDF, con título y encabezado) a los resultados cuando la búsqueda es general y no hay filtros — así el asistente puede explicar de qué trata el documento y por qué modifica la Ley 19.628. Falla cerrado si el PDF cambia (verifica su hash). |
| [`frontend/`](etapa3_producto/frontend/) | Interfaz de chat (HTML/CSS/JS plano, sin build ni dependencias externas) — `citations.js` convierte `[chunk_id]` en números de cita clicables. |
| [`Dockerfile`](etapa3_producto/Dockerfile), [`nginx.conf`](etapa3_producto/nginx.conf) | Imagen de la API y configuración del proxy del frontend. |
| [`audit_index.py`](etapa3_producto/audit_index.py) | Compara en solo lectura el índice de Postgres contra `chunks.json` (conteo, IDs, metadata exacta, vectores válidos de 1024 dimensiones) — sin llamadas externas. |
| [`evidence.py`](etapa3_producto/evidence.py), [`live_smoke.py`](etapa3_producto/live_smoke.py) | Capturan evidencia HTTP real contra la API levantada (`evidence.py` en modo demo; `live_smoke.py`, opt-in con `--run-live`, contra Groq/pgvector reales) — resultados en `docs/evidencia_local/`. |
| [`tests/`](etapa3_producto/tests/) | 50 tests Python (`unittest`/`pytest`) + 6 tests JavaScript (`node:test`) para `citations.js`. |

### Revisión de código e integración final (Juan, con asistencia de IA declarada)

Tras integrar el trabajo de Jenaro, una revisión de código encontró que la generación de la Etapa 3 se había reimplementado en paralelo a la de la Etapa 2 (dos prompts, dos formatos de cita) en vez de consumirla como estaba planificado. Se corrigió sin descartar el trabajo de nadie:

1. **`generate_answer()` (Juan) ahora es lo que llama la API real** — `VectorBackend.generate()` (Jenaro) invoca directamente la función de generación de la Etapa 2, en vez de tener su propio prompt paralelo. Para esto, `chain.py`/`prompts.py` se ampliaron: contexto con la relación entre leyes (necesario para explicar por qué aparece la Ley 19.628), salida en JSON (mismo protocolo que ya usaba `GroqBackend`, así se puede inyectar el mismo cliente LLM en los tests), y derivación de citas desde el propio texto de la respuesta.
2. **Detección de "¿menciona un artículo?" unificada** en `parse_article_reference()` (`demo.py`) — antes 3 regex ligeramente distintos en 3 archivos, que podían no coincidir entre sí y fallaban con un typo plausible sin espacio ("artículo 1bis").
3. **`plan_query()` ya no se salta el clasificador LLM** con un regex cuando la pregunta mencionaba un artículo — eso podía enrutar mal un mensaje conversacional que solo lo mencionaba de pasada. Ahora siempre clasifica con el LLM (que tiene el historial).
4. **Validación de citas tolerante** a espacios/mayúsculas (antes un `"[id]" in texto` literal podía rechazar una respuesta correcta).
5. **Lock de `/chat` acotado** solo al diccionario de sesiones — antes envolvía también la llamada de red a Groq/Mistral, serializando conversaciones sin relación entre sí.
6. **`etapa2_rag/`**: se quitó `SET LOCAL enable_indexscan = off` (apagaba también los índices btree de metadatos, no solo el vectorial); timeouts de conexión ahora configurables por variable de entorno; se quitó el rechazo duro de `MISTRAL_BASE_URL`/`MODEL` no-default (la validación de dimensión ya protege el índice); `build_index.py` vuelve a soportar un `.env` propio de `etapa2_rag/`.
7. `compose.yaml` no tenía política de reinicio (`restart`) en ninguno de sus 3 servicios — se agregó `unless-stopped`.

Validado de punta a punta contra el sistema real (Docker levantado, 140/140 chunks indexados, `docker compose exec api python -m etapa3_producto.audit_index` con `passed: true`): preguntas generales, artículo con sufijo sin espacio ("1bis"), artículo inexistente (abstención), memoria conversacional, y la relación Ley 21.719/Ley 19.628 — todo correcto. Los 50 tests Python + 6 JS pasan (se actualizaron 3 tests que verificaban el formato de prompt anterior).

## Cómo ejecutar

Ver **[INSTALACION.md](INSTALACION.md)** para la guía completa (requisitos, `.env`, arranque con Docker, pruebas manuales y automatizadas, problemas comunes). Resumen rápido:

```bash
docker compose up -d --build --wait
docker compose exec -T api python etapa2_rag/scripts/build_index.py
docker compose exec -T api python -m etapa3_producto.audit_index
```
Chat en **http://localhost:8080**, API interactiva en **http://localhost:8000/docs**.

### Etapa 1 — regenerar los chunks (opcional, ya están generados en el repo)
```bash
python etapa1_datos/scripts/extract_pdf.py
python etapa1_datos/scripts/clean_text.py
python etapa1_datos/scripts/parse_structure.py
python etapa1_datos/scripts/chunk_and_export.py
python etapa1_datos/scripts/validate_chunks.py
```

### Etapa 2 — indexar y probar standalone (sin levantar la API/frontend)
```bash
cd etapa2_rag
docker compose up -d          # levanta Postgres+pgvector en localhost:5433
python scripts/build_index.py # indexa los 140 chunks (requiere MISTRAL_API_KEY)
python scripts/test_retrieval.py  # prueba retrieval + generación (requiere LLM_API_KEY)
cd ..
```
> No levantar `etapa2_rag/docker-compose.yml` y el `compose.yaml` de la raíz al mismo tiempo — ambos usan el puerto 5433 para Postgres.

### Tests automatizados
```bash
pip install -r etapa3_producto/requirements-dev.txt
python -m pytest etapa3_producto/tests/
node --test etapa3_producto/tests/test_citations.cjs
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

Python, LangChain (`langchain-core`/`langchain-openai`), embeddings `mistral-embed` (API de Mistral, 1024 dims), PostgreSQL + pgvector (Docker, imagen `pgvector/pgvector:pg16`), LLM de chat Groq (`qwen/qwen3.6-27b`, API compatible con OpenAI), FastAPI, frontend HTML/JS/CSS plano servido vía nginx, `compose.yaml` con servicios `db` (pgvector), `api` (FastAPI) y `frontend` (nginx).

## Limitaciones conocidas

- La ley es modificatoria: secciones no tocadas por la Ley 21.719 (ej. Título III de la Ley 19.628) no existen en el dataset — el sistema debe abstenerse, no inventar.
- Memoria de sesión en proceso (un solo worker): se pierde si se reinicia la API.
- Sin autenticación — no exponer este servicio públicamente tal como está.
- Vigencia diferida: el dataset no distingue qué artículos están vigentes hoy vs. en el futuro (ver `etapa1_datos/justificacion_chunking.md`).
