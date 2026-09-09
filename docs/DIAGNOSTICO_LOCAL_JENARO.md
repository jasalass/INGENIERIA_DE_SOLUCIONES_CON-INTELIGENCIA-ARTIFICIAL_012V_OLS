# Preparación local y responsabilidades de Jenaro

Revisión: 2026-09-08. Base: `main`, commit `158c8c44fe453c2d4805135eef3cb6a5e139543f`.
Entrega indicada por Jenaro: viernes; se interpreta como 11-09-2026. Hora y rúbrica por confirmar.

**Actualización posterior del 08-09-2026:** se implementó y probó localmente la etapa 3 en modo demo, en la rama `codex/etapa3-producto-local`, sin push. Ver [guía del producto](../etapa3_producto/README.md) y [evidencia de pruebas](evidencia_local/README.md). Las tablas siguientes conservan el diagnóstico inicial anterior a esa implementación. El motor real de Juan y las credenciales siguen pendientes.

**Nueva referencia docente:** se añadió generación Groq y memoria con los patrones
de RA1. Hay 32 pruebas offline correctas; las llamadas reales requieren una clave
local. No es necesario esperar el índice de Juan para probar generación/memoria.
Ver [correspondencia con el notebook y las RA](REFERENCIAS_DOCENTES_JENARO.md).

## Estado comprobado

Repositorio clonado en `universidad/ingenieria-soluciones-ia`, separado del proyecto de Machine Learning.
Se consultó previamente `../docs/migracion/CONTINUIDAD.md` del workspace Universidad.

| Componente | Evidencia / estado |
|---|---|
| Datos de Pamela | PDF, scripts, texto limpio, metadatos, artículos y chunks disponibles en `main`. |
| Reproducción de datos | Pipeline ejecutado en memoria: texto crudo, metadatos, texto limpio, entradas y chunks coinciden con los archivos versionados. No se sobrescribieron fuentes ni resultados del equipo. |
| Conteos | 95 entradas, 79 artículos numerados y 140 chunks; `chunk_id` único y ningún texto vacío. |
| Python | Entorno `.venv` creado con Python 3.13.6 y `pymupdf==1.28.2`; `pip check` sin incompatibilidades. `.venv/` está ignorado por Git. |
| Docker | Motor Linux iniciado; servidor 29.2.1 y Compose v5.0.2 disponibles. |
| Imagen de base de datos | Descargada `pgvector/pgvector:pg16`, digest `sha256:ccc6e83d6e35e931dc7c5def2022729d5a6c370318d099181995567ff1fb4d6b`. No se creó todavía una base ni un contenedor del proyecto. |
| Motor de Juan | No aparece en las ramas remotas consultadas (`main`, `etapa1-datos`). Puede existir trabajo sin publicar. |
| Producto de Jenaro | Todavía no hay API, frontend, orquestador LangChain ni pruebas de producto. |
| Despliegue | No hay Dockerfiles, Compose, esquema SQL, indexador ni configuración de aplicación. |
| Dependencias | `requirements.txt` solo declara PyMuPDF; no instala el stack de producto. |

El sistema completo todavía no puede arrancar: faltan componentes de aplicación. La validación de los datos no prueba recuperación semántica ni calidad de respuestas.

## Lo que corresponde a Jenaro según el README

1. Integrar retrieval y generación con LangChain, citas y contexto conversacional.
2. Implementar API FastAPI conectada al motor RAG y a pgvector.
3. Crear chat HTML/JS conectado a la API, con estado de carga, errores y fuentes citadas.
4. Comprobar coherencia entre fragmentos recuperados y respuesta; guardar evidencia real de las pruebas.
5. Participar en diagrama de arquitectura, informe APA de máximo cinco páginas y defensa de veinte minutos. El calendario asigna a Jenaro README de ejecución y comprobación desde cero.

El README exige que la reflexión individual sea **sin uso de IA**: debe escribirla personalmente cada integrante.

## Dependencias que hay que acordar con Juan

- Rama o archivos con su indexador, retrieval, esquema SQL y prompts; comando para ejecutarlos.
- Nombre de tabla/colección, campos y forma de devolver resultados, incluidos puntuación/distancia y metadatos.
- Modelo de embeddings `gemini-embedding-001`, dimensión, normalización y configuración de documentos/consultas consistentes.
- Filtros admitidos: artículo, sufijo, ámbito, título/tema y fecha. El dataset no tiene un campo literal `tema`; deben acordar cómo representarlo.
- Modelo de **generación** y proveedor. El README solo especifica embeddings; ese modelo no genera respuestas de chat.
- Propiedad de la plantilla de prompt y de la invocación del LLM: el calendario menciona integración LangChain tanto para Juan como para Jenaro. Propuesta: Juan entrega retrieval y prompts; Jenaro arma la cadena, historial y API.

Propuesta de contrato, todavía no implementada ni acordada:

```text
retrieve(consulta, top_k, filtros)
  -> lista de {chunk_id, texto, metadatos, score_o_distancia}

POST /chat
  entrada: {message, conversation_id?, filters?}
  salida: {answer, conversation_id, sources: [...], insufficient_context}
```

Cada fuente debe conservar `chunk_id`, `articulo`, `articulo_sufijo`, `nivel1`, `ambito`, `ley_referenciada`, `parte` y `fuente`. `id` se repite entre partes de un mismo artículo; usar `chunk_id` como identificador del fragmento.

No construir citas con `articulo` solamente: los transitorios y las instrucciones tienen ese campo nulo; los artículos bis/ter requieren sufijo. La documentación de Pamela advierte que el corpus es modificatorio, tiene cobertura parcial y no modela vigencia por artículo. La API debe reconocer esos límites y evitar presentar contexto ausente como recuperado.

## Compatibilidad a resolver antes de indexar

Gemini Embedding 001 devuelve 3072 dimensiones por defecto. Los índices HNSW/IVFFlat sobre el tipo `vector` de pgvector admiten hasta 2000 dimensiones; esto no equivale a un límite general de almacenamiento. Propuesta para acordar con Juan: 768 dimensiones y normalización consistente. Otra opción es conservar 3072 con búsqueda exacta para este corpus pequeño o diseñar explícitamente indexación con `halfvec`.

Fuentes técnicas consultadas:

- [Embeddings de Gemini: dimensiones, normalización y tipos de tarea](https://ai.google.dev/gemini-api/docs/embeddings).
- [pgvector: límites y alternativas de indexación](https://github.com/pgvector/pgvector).
- [Crear y administrar claves de Gemini](https://ai.google.dev/gemini-api/docs/api-key).

## Qué puede preparar Codex y qué necesita aportar Jenaro

| Necesidad | Codex puede preparar | Aporte de Jenaro/equipo |
|---|---|---|
| Infraestructura local | Dependencias, imágenes, Compose, Dockerfiles y diagnóstico. | Ningún servidor remoto es imprescindible para una demo local. |
| API y chat | FastAPI, frontend, historial, fuentes, manejo de errores y pruebas. Puede avanzar con un retrieval simulado claramente identificado hasta integrar el real. | Confirmar contrato y avances de Juan. |
| Acceso a modelos | Integración del SDK y configuración por variables de entorno. | Clave de API de una cuenta/proyecto del equipo con acceso y cuota; configurarla localmente, no pegarla en chat ni subirla a Git. Confirmar proveedor/modelo generativo. |
| Corpus | Ya está disponible; no es necesario traer nuevamente el PDF ni el JSON. | Validar preguntas y respuestas esperadas con Pamela y el docente. |
| Requisitos académicos | Contrastar implementación y pruebas con los criterios. | Enunciado/rúbrica oficial de esta evaluación, plantilla si existe, hora de entrega y restricciones adicionales. |
| Evidencia y documentación | Casos de prueba, resultados, capturas, guía y diagrama del sistema implementado. | Ensayo/defensa y reflexión individual escrita personalmente. |

No se necesitan cookies de Google/Colab, sesiones del navegador ni credenciales personales de compañeros. Las credenciales de la futura base local se pueden generar durante su configuración; no es necesario copiarlas de otra máquina.

## Secuencia propuesta hasta el viernes

- Martes 08: acordar contrato con Juan, proveedor de generación y requisitos; crear base de API/UI y Compose.
- Miércoles 09: integrar retrieval real y LLM; obtener una demo completa con cinco preguntas.
- Jueves 10: ejecutar 10–15 casos, incluyendo seguimiento conversacional, falta de evidencia, transitorios, sufijos y errores de proveedor; capturar resultados y probar instalación desde cero; cerrar documentación.
- Viernes 11: margen para revisión final y entrega a la hora oficial.

La prioridad es cerrar cuanto antes las dependencias de Juan y el acceso al modelo. Un chat con respuestas simuladas permite desarrollar la UI, pero no cumple la evidencia de RAG real.

## Comprobaciones locales repetibles

Desde la raíz del repositorio clonado, en PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -X utf8 etapa1_datos/scripts/validate_chunks.py
docker info
docker compose version
```

El validador imprime observaciones para revisión manual; no es una batería de aserciones. La comprobación de reproducción completa de esta revisión comparó en memoria las funciones de extracción, limpieza, parseo y chunking con cada archivo versionado. Los scripts de generación originales escriben rutas fijas: no ejecutarlos sobre los resultados del equipo si se pretende preservar esa evidencia.
