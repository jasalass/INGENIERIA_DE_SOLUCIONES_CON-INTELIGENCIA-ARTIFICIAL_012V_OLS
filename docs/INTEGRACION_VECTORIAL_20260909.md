# Integración local del RAG — 09-09-2026

Corrección posterior: una prueba del usuario detectó confusión entre documento
fuente y ley modificada. Se incorporaron procedencia estructurada y un fragmento
padre citable de página 1; ver [guía vigente](../etapa3_producto/README.md).
Los 11 casos originales de este informe no cubrían la pregunta general exacta.

Estado: funcional en `http://localhost:8080`, rama `codex/etapa3-producto-local`
sobre `f82fdd8`. Cambios sin commit ni push. Credenciales exclusivamente en `.env`
ignorado por Git; no se reproducen en este informe.

## Resultado

Se integró el retrieval de Juan con la API, interfaz y orquestación conversacional
de Jenaro. Mistral (`mistral-embed`) genera vectores de 1024 dimensiones;
PostgreSQL/pgvector recupera fragmentos y Groq (`qwen/qwen3.6-27b`) genera la
respuesta utilizando fuentes e historial. No hay fallback silencioso a búsqueda
léxica en modo `live`.

| Comprobación | Resultado y evidencia |
| --- | --- |
| Índice y corpus | 140/140 filas, textos y metadatos coincidentes; todos los vectores finitos, no nulos y de 1024 dimensiones. [Auditoría](evidencia_local/index_audit_20260909T163607122077Z.json). |
| Tests sin proveedores | 43/43: API, memoria, citas, adaptadores, validaciones de embeddings y SQL parametrizado. |
| HTTP con proveedores reales | 11/11 casos correctos a través de Nginx y FastAPI. [Respuestas completas](evidencia_local/live_http_20260909T164034218896Z.json). |
| Dependencias y sintaxis | `pip check`, `compileall`, `node --check` y `git diff --check` correctos. |
| Navegador y reconstrucción final | Interfaz conectada mostrando modo vectorial; inspección visual de inicio, sin reponer el pie eliminado. API y base saludables tras reconstruir. PDF mediante GET: HTTP 200. Auditoría ejecutada también dentro del contenedor: 140/140. |

El corpus original no fue modificado. SHA-256 de `chunks.json`:
`7510ffff94c7b63e46cfa29691ec6cfe0825fb0ed18393abb1797caf3dea7390`.

## Casos reales y revisión de respuestas

1. Presentación con nombre ficticio: saludo correcto.
2. Pregunta posterior por nombre: respondió «Te llamas Felipe».
3. Otra sesión: reconoció que no disponía del nombre.
4. Artículo 4: respuesta y cita `[art-4]` coherentes con el texto recuperado.
5. Seguimiento «¿Y eso cómo funciona?»: reformuló conservando el artículo 4;
   se abstuvo de inventar un procedimiento que ese fragmento no detalla.
6. Artículo 999: sin fuentes, abstención.
7. Artículo 4 permanente con filtro transitorio: sin resultados, abstención.
8. Pregunta general por derechos: recuperación semántica de artículo 4 y
   artículo 14 ter; los derechos resumidos aparecen en las fuentes devueltas.
9. Artículo 1 bis: cita al sufijo correcto, sin confundirlo con artículo 1.
10. Consulta transitoria: respuesta sustentada en `transitorio-primero`.
11. Pregunta sobre pizza: abstención, sin inventar una receta desde el corpus.

Estas comprobaciones funcionales y la revisión de estos ejemplos no constituyen
una evaluación jurídica exhaustiva ni garantizan fidelidad en toda pregunta.
Se conserva la evidencia previa de demo/Groq; no se presenta como evidencia
de esta integración vectorial.

## Integración y atribución

- Pamela: corpus y metadatos originales preservados.
- Juan: se reutilizan esquema, embeddings, indexador y función `search()`.
  Se ajustaron imports, validación dimensional, tiempos de espera, transacciones
  por lote, metadatos completos y filtros que distinguen artículos con sufijo.
- Jenaro: adaptador `VectorBackend`, FastAPI, frontend, citas, memoria y generación
  Groq/LangChain. `answer_question()` de Juan permanece como alternativa CLI:
  no se llama desde la API porque su contrato de salida no preserva las fuentes
  completas ni coincide con el formato de citas del producto.

La consulta usa distancia coseno exacta para los 140 fragmentos. No depende del
índice IVFFlat creado antes de insertar datos, ni de su recall bajo filtros.
La distinción entre recuperación exacta y aproximada se documenta en
[pgvector](https://github.com/pgvector/pgvector). La similitud mostrada es
`1 - distancia`, no una probabilidad de que la respuesta sea correcta.

Las guías `fastapi-patterns` y `postgres-patterns` orientaron la validación del
contrato HTTP, consultas parametrizadas, límites de espera y transacciones.
La correspondencia docente y los patrones LangChain se mantienen en
[referencias de Jenaro](REFERENCIAS_DOCENTES_JENARO.md).

## Operación y límites

- [Guía reproducible de instalación y pruebas](../etapa3_producto/README.md).
- [Arquitectura y contrato implementado](../etapa3_producto/INTEGRACION_JUAN.md).
- Docker mantiene frontend, API y base en puertos exclusivamente de loopback.
  La base tiene volumen persistente; no ejecutar `docker compose down -v`.
- Memoria temporal por conversación: últimos seis intercambios, TTL de una hora,
  hasta cien sesiones, un worker. Recargar el navegador pierde el identificador;
  reiniciar la API pierde su memoria. No es historial persistente de usuarios.
- `/api/health` comprueba disponibilidad del proceso, no el proveedor ni que el
  índice esté completo. `audit_index` verifica la base sin consumir APIs externas.
- Límite de salida de 512 tokens, sin reintentos automáticos del modelo. Las cuotas
  y disponibilidad de Mistral/Groq pueden producir errores aunque Docker esté sano.
- LangChain advierte deprecación de `RunnableWithMessageHistory`; funciona en
  las versiones fijadas y conserva el patrón docente. Migrar su persistencia
  debe tratarse como trabajo futuro, no cambiar dependencias sin repetir tests.
- Mistral recibe textos/preguntas para embeddings; Groq recibe preguntas, historial
  y fragmentos necesarios. No utilizar datos personales reales en la demo.
- Corpus de ley modificatoria, no texto consolidado; puede no contener un artículo
  completo ni toda información necesaria. El aviso eliminado del pie no se repuso.
- La configuración local no equivale a despliegue público: faltan autenticación,
  endurecimiento y almacenamiento de sesiones para ese alcance.

## Pendiente del equipo

Revisar las respuestas y la atribución de cambios con Juan, consolidar el informe
técnico y diagrama, preparar la defensa y decidir cuándo publicar. Cada integrante
debe escribir personalmente su reflexión, cuyo requisito indica sin uso de IA.
