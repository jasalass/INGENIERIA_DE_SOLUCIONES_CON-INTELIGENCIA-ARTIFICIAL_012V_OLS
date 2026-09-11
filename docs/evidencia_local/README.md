# Evidencia de producto local — 08-09-2026

Rama local: `codex/etapa3-producto-local`, sobre `158c8c4`. Cambios sin push.

## Estado más reciente: RAG vectorial activo (09-09-2026)

Corrección posterior de procedencia: **50/50 pruebas offline y 16/16 casos HTTP
en la corrida final**, incluyendo preguntas generales por la Ley 21.719.
Ver [informe y fallo intermedio conservado](../CORRECCION_CONTEXTO_DOCUMENTAL_20260909.md)
y [evidencia final](live_http_20260909T225324179138Z.json).
Los conteos que siguen corresponden al estado previo a esa corrección.

Sobre `f82fdd8`, sin push: **43/43 pruebas offline, 140/140 fragmentos auditados
y 11/11 casos HTTP reales** con Mistral, pgvector y Groq. Ver el
[informe de integración](../INTEGRACION_VECTORIAL_20260909.md), la
[auditoría del índice](index_audit_20260909T163607122077Z.json) y la
[corrida HTTP](live_http_20260909T164034218896Z.json).
Los apartados siguientes conservan evidencia histórica, no el modo activo.

## Estado anterior: Groq activo

Clave local aportada por el usuario, sin publicar. Máximo de salida ajustado a
512 tokens. **33/33 pruebas offline y 7/7 casos HTTP en la segunda corrida real**;
la primera corrida registró 4/5 con un rechazo de validación conservado.
Ver [informe de verificación](VERIFICACION_ACTIVACION_GROQ.md) y
[evidencia HTTP completa](groq_http_20260909T011249432805Z.json).
Los apartados inferiores conservan el estado previo, cuando solo había demo.

## Actualización: integración Groq preparada (08-09-2026, hora Chile)

- **32/32 pruebas offline**: las 17 originales y 15 del adaptador Groq/memoria.
  Incluyen comprobación de mensajes enviados, ventana de historial, separación
  de sesiones, turnos fallidos, filtros, citas, JSON y formato HTTP del SDK real
  mediante `httpx.MockTransport`. No se contactó Groq ni se usó una clave real.
- **11/11 casos HTTP** repetidos contra Docker actualizado en modo demo:
  [demo_http_20260909T005504209395Z.json](demo_http_20260909T005504209395Z.json).
  El nombre de archivo usa UTC; en Chile todavía era 8 de septiembre.
- API y frontend saludables, `pip check` correcto. El modo activo continúa
  siendo demo. Falta prueba generativa real; no interpretar respuestas de tests
  como evidencia de que el modelo recordó nombres o respondió con fidelidad.
- Las capturas y comprobaciones de navegador siguientes pertenecen a la revisión
  anterior de demo. No son capturas de Groq en funcionamiento.

Referencias y guion pendiente: [nota docente](../REFERENCIAS_DOCENTES_JENARO.md).

## Alcance

API + UI + orquestación LangChain de **demostración**. Busca coincidencias de palabras y devuelve extractos literales del JSON del equipo. No usa embeddings, pgvector ni LLM; los resultados no acreditan precisión jurídica ni evaluación de generación aumentada real.

## Resultados comprobados

- **17/17 pruebas de API**: validación, fuentes, artículo bis, transitorios, abstención, seguimiento/cambio de tema, separación/borrado/expiración de sesiones, límite de capacidad, fallo de proveedor sin guardar turno, rechazo de cita no recuperada y rechazo de modo live sin adaptador.
- **11/11 casos HTTP** contra `http://localhost:8080`, atravesando Nginx y FastAPI en Docker. Resultados completos en [demo_http_20260908T230446474133Z.json](demo_http_20260908T230446474133Z.json).
- Navegador: envío por botón y Enter, expansión de fuentes, seguimiento «¿Y eso cómo funciona?» conservando artículo 1 bis y mostrando turno 2, Nueva consulta y filtro de transitorios.
- Vista móvil: viewport de 390 × 844; ancho del documento de 390 px, sin desbordamiento horizontal. Viewport restaurado al finalizar la prueba.
- Recuperación de conexión observada durante la recreación del contenedor API; la UI muestra desconexión y vuelve a habilitar envío cuando el servicio responde.
- `pip check` correcto y sintaxis JavaScript comprobada con `node --check`.

## Capturas

- [Inicio de la demo](01_inicio_demo.png).
- [Conversación con cita a artículo 1 bis](02_conversacion_demo.png).
- [Consulta en móvil](03_movil_demo.png).

## Repetición

Desde la raíz del clon, instalar `etapa3_producto/requirements-dev.txt`, arrancar Docker Compose y ejecutar:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s etapa3_producto/tests -v
.\.venv\Scripts\python.exe -m etapa3_producto.evidence
```

El guion HTTP genera un archivo nuevo con fecha; no sustituye este resultado. Crea y borra solo sus conversaciones de prueba. Para la entrega final se necesita una segunda evaluación end-to-end con el motor real y respuestas revisadas contra las fuentes por el equipo.
