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

- Generar embeddings de los chunks (Gemini `gemini-embedding-001`)
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

Python, LangChain, embeddings Gemini (`gemini-embedding-001`), PostgreSQL + pgvector (vector store, en contenedor Docker propio, imagen `pgvector/pgvector:pg16`), FastAPI (backend, consulta al contenedor de pgvector), frontend HTML/JS simple, docker-compose con servicios `db` (pgvector), `api` y `frontend` para levantar todo el sistema con un solo comando.


