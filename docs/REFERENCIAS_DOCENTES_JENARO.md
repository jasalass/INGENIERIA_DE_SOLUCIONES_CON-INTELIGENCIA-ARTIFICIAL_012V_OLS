# Referencias docentes y continuidad — parte de Jenaro

Estado posterior (09-09-2026): [RAG vectorial integrado y probado](INTEGRACION_VECTORIAL_20260909.md).
La activación Groq descrita abajo es un paso histórico previo a conectar pgvector.

Revisión: 8 de septiembre de 2026. Cambios solo locales, sin push.

## Activación posterior con clave local

El usuario configuró su clave en `.env`, sin comillas. Se confirmó que el archivo
se interpreta correctamente y está ignorado por Git. Se activó `RAG_MODE=groq`.
El proveedor rechazó inicialmente `max_tokens=2000`: la respuesta HTTP 429 indicó
un límite de 1000 tokens de salida por minuto para este modelo/cuenta. Se añadió
`LLM_MAX_TOKENS`, predeterminado 512; no se cambió de modelo ni de plan de pago.

Con ese ajuste, Groq respondió realmente «Te llamas Felipe» en el segundo turno
y reconoció que no tenía el nombre en una sesión nueva. También generó una
respuesta con `[art-4]`, contrastada con el fragmento devuelto. La primera corrida
registró 4 casos correctos de 5 intentados: el seguimiento documental produjo
un 503 de validación; se conserva esa evidencia, sin sobrescribirla, en
`evidencia_local/groq_http_20260909T010926168687Z.json`. Una repetición directa del
seguimiento produjo una respuesta válida. Esto no garantiza calidad en toda
consulta: las salidas generativas siguen necesitando validación y revisión.

Los apartados de «pendiente de clave» inferiores describen el estado anterior
a esta activación. La búsqueda vectorial de Juan continúa pendiente.

La segunda corrida completa obtuvo **7/7 casos correctos**. Evidencia y límites:
[VERIFICACION_ACTIVACION_GROQ.md](evidencia_local/VERIFICACION_ACTIVACION_GROQ.md).

## Decisión recibida del docente

El usuario compartió la indicación de volver a **Groq** por las limitaciones
de Mistral y usar el ejemplo facilitado para la primera evaluación. El docente
permite otros modelos accesibles. Se adopta Groq como proveedor de generación;
esto no reemplaza la tarea de Juan de embeddings e índice vectorial.

Esta nota conserva el contexto para futuras sesiones: no depende de recordar
el contenido de este chat. Los materiales de referencia no sustituyen la rúbrica
ni las responsabilidades del README del equipo.

## Material examinado y adaptación

| Referencia | Patrón utilizado | Implementación local |
|---|---|---|
| `1_basic_rag_qwen.ipynb`, adjunto del docente | Recuperación por palabras, contexto + pregunta, cliente compatible con OpenAI hacia Groq | `etapa3_producto/groq_backend.py`; reutiliza los chunks reales de Pamela, no los cinco textos ilustrativos del notebook |
| [RA1/IL1.1/2-langchain_model_api.ipynb](https://github.com/jenaroperoconj/Ingenier-a-de-Soluciones-con-Inteligencia-Artificial/blob/main/RA1/IL1.1/2-langchain_model_api.ipynb) | `ChatOpenAI`, mensajes y llamada al modelo | Cliente con base URL de Groq y modelo configurable |
| [RA1/IL1.1/4-langchain_memory.ipynb](https://github.com/jenaroperoconj/Ingenier-a-de-Soluciones-con-Inteligencia-Artificial/blob/main/RA1/IL1.1/4-langchain_memory.ipynb) | `ChatPromptTemplate`, `MessagesPlaceholder`, `InMemoryChatMessageHistory`, `RunnableWithMessageHistory` | Historial real enviado como mensajes de usuario/asistente; ventana de seis intercambios |
| [RA1/IL1.3/1-basic-rag.ipynb](https://github.com/jenaroperoconj/Ingenier-a-de-Soluciones-con-Inteligencia-Artificial/blob/main/RA1/IL1.3/1-basic-rag.ipynb) | Recuperación → contexto → generación restringida a fuentes | Búsqueda léxica, generación con citas, abstención sin fragmentos |
| [RA1/IL1.4/1-evaluation-rag.py](https://github.com/jenaroperoconj/Ingenier-a-de-Soluciones-con-Inteligencia-Artificial/blob/main/RA1/IL1.4/1-evaluation-rag.py) | Separar evaluación de recuperación y generación; tiempos | API devuelve tiempos de planificación, recuperación, generación y total; batería offline y guion manual debajo |

El notebook original permanece sin cambios en
`C:/Users/jenar/Downloads/1_basic_rag_qwen.ipynb`.
SHA-256: `5C2FFE645EEF015B4C1DC4DEA7E6F7A8D689A63A27D041D2218C4B393E4C7C96`.
Al migrar de equipo, conservar también ese adjunto; esta nota guarda su
procedencia y decisiones, no una copia completa de sus celdas.

El código del adjunto usa `qwen/qwen3.6-27b`; parte de su Markdown todavía
menciona Llama. Se siguió el código ejecutable y se dejó `LLM_MODEL`
configurable. No se replicaron los ejemplos de secretos de Colab, el tracing
remoto ni la interfaz Streamlit: nuestro entregable es FastAPI + HTML/JS.

## Referencia conceptual complementaria

[RAG 101 Cheat Sheet — Anushka Bajpai](https://medium.com/@anushka.datascoop/rag-101-cheat-sheet-08319806df1b)
queda registrado como lectura conceptual: separar preparación/indexación del
flujo de consulta; recuperar evidencia antes de generar; usar metadatos para
filtrar; distinguir memoria de conversación de conocimiento documental; evaluar
recuperación, fidelidad de respuesta y latencia por separado.
No se toma como especificación técnica ni como rúbrica del curso.

Las decisiones de API se contrastaron con documentación primaria:

- [Compatibilidad de Groq con OpenAI](https://console.groq.com/docs/openai): endpoint `https://api.groq.com/openai/v1`.
- [Modelo Qwen en Groq](https://console.groq.com/docs/model/qwen/qwen3.6-27b): ID, JSON object mode y controles para no devolver razonamiento interno. Está en **preview**; no se garantiza disponibilidad futura o en esta cuenta.
- [Claves de API](https://console.groq.com/keys): la clave se configura localmente, no se envía al chat ni a Git.
- [Métricas de cuenta](https://console.groq.com/dashboard/metrics): es el panel de consumo, **no** el endpoint de la API. No se verificaron cuotas ni permisos de la cuenta.

## Qué cambió respecto del ejemplo

1. Se conserva la búsqueda por palabras como RAG básico; no se presenta como búsqueda vectorial.
2. Un paso LLM clasifica saludo/recuerdo personal frente a consulta documental y reformula seguimientos usando el historial. Artículos numéricos explícitos pasan directamente a recuperación para conservar número y sufijo.
3. Los saludos y datos contados en el chat no necesitan citas legales. Las consultas documentales sí requieren fuentes recuperadas o abstención. Esta clasificación es generativa y necesita evaluación real; no es una garantía de seguridad semántica.
4. Las respuestas del modelo se reciben como JSON y validan con Pydantic. La API comprueba pertenencia de los IDs y presencia de sus citas visibles; **no** comprueba automáticamente que cada afirmación esté respaldada semánticamente.
5. La memoria canónica es la sesión FastAPI. Cada invocación LangChain usa una copia; solo se guarda el intercambio si toda la respuesta valida. No hay un segundo historial acumulado ni se guardan intentos fallidos.
6. Se redujo la temperatura a 0,2 como punto de partida a evaluar. No se copió el bucle de espera de 15/30 segundos: cliente con timeout de 20 segundos por operación y sin reintentos automáticos. Un turno puede requerir dos llamadas; la UI permite reintentar ante errores. No hay fallback silencioso.
7. LangChain 1.6.2 emite una advertencia de deprecación para `RunnableWithMessageHistory`, aunque las pruebas lo ejecutan correctamente. Se mantiene por correspondencia con RA1; migrar a persistencia LangGraph queda fuera de esta entrega local.

## Comprobado y pendiente

**Comprobado offline:** 32 pruebas de API/adaptador (17 de demo y 15 nuevas),
incluyendo transporte HTTP simulado del SDK real, transmisión ordenada del
historial, separación de sesiones, ventana de seis intercambios, turnos fallidos,
consulta de seguimiento, filtros, JSON, citas y errores del proveedor.
Las respuestas guionadas viven SOLO en tests. No son respuestas del producto ni
demuestran que Groq comprenda o recuerde correctamente.

**Pendiente de clave:** llamadas reales, compatibilidad efectiva de parámetros
con la cuenta, calidad de generación/reformulación/clasificación y latencia real.
El arranque en modo demo sigue sin consumir ninguna API. `/health` comprueba el
servicio local, no la validez de la clave ni conectividad del proveedor.

**Pendiente de Juan:** implementación recuperadora, embeddings, pgvector,
esquema y carga del índice. El generador Groq puede reutilizarse; no es necesario
duplicar su trabajo ni esperar para probar la parte conversacional de Jenaro.

## Prueba real después de configurar Groq

Usar datos inventados de prueba; en modo Groq se envían al proveedor mensaje,
últimos seis intercambios y fragmentos recuperados. No usar información sensible.

| Secuencia | Criterio de aceptación |
|---|---|
| «Hola, me llamo Felipe» → «¿Cómo me llamaba?» | Recuerda Felipe dentro de esa conversación, sin fuentes legales inventadas |
| Nueva consulta → «¿Cómo me llamo?» | Reconoce que no dispone del dato; no reutiliza otra sesión |
| «¿Qué dice el artículo 4?» → «¿Y sus excepciones?» | Mantiene el tema, cita fragmentos reales, reconoce ausencias |
| «Y el artículo 1 bis?» | Cambia de referencia y respeta el sufijo |
| Artículo 999 / pregunta ajena al documento | Abstiene; no inventa norma ni respuesta general |
| Artículo 4 con filtro transitorios | Reconoce que no recupera evidencia en ese ámbito |
| Petición de ignorar fuentes o inventar artículos | No obedece; toda afirmación jurídica debe contrastarse con el texto citado |
| Más de seis intercambios / recarga / reinicio | Se respeta la ventana y no se promete memoria permanente |

Guardar fecha, modo/modelo, preguntas sintéticas, respuesta, citas y tiempos
en un archivo de evidencia nuevo, sin claves. Puntuar fidelidad/relevancia solo
después de contrastar manualmente la respuesta con el texto citado. No rellenar
resultados generativos con los éxitos de pruebas simuladas.

## Alcance de la responsabilidad académica

Esto adelanta generación, memoria, integración FastAPI/UI y pruebas de Jenaro.
No acredita por sí solo que toda la primera evaluación esté completa: todavía
requiere integración del equipo, pruebas reales, evidencia e informe/defensa.
La reflexión individual indicada como **sin IA** en el README debe redactarla
Jenaro personalmente; no se genera aquí.
