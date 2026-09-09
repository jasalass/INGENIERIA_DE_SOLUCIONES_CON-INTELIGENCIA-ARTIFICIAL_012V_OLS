# Corrección: identidad del documento en el RAG

## Fallo observado

El usuario preguntó «De qué trata la ley 21.719?» y recibió una abstención
incorrecta: el modelo atribuyó el contexto exclusivamente a la Ley 19.628.
La corrida anterior de 11 casos no cubría esta pregunta. Tener proveedores
conectados y citas válidas no demuestra que la interpretación sea correcta.

## Contraste con el original

Se extrajo y se inspeccionó visualmente la primera página del PDF local.
Su título identifica la Ley 21.719, protección y tratamiento de datos personales
y creación de la Agencia. El encabezado del artículo primero menciona
expresamente las modificaciones a la Ley 19.628. No son dos PDFs intercambiados.
El PDF servido por HTTP coincide byte a byte con el original local.

El corpus conserva artículos internos e incluso el encabezado introductorio
en `nivel1-primero`, pero el ranking no lo entrega necesariamente en una
pregunta general. El título no acompañaba sistemáticamente a los resultados.
La serialización para generar respuestas
reducía además las fuentes a ID, etiqueta y texto, sin procedencia estructurada.

## Cambios locales

- Separar `documento_origen` de `ley_referenciada` en el contexto del LLM y
  conservar `nivel1` y `ambito`. No renombrar falsamente artículos de la 19.628.
- Derivar `document_context.json` de título y encabezado de página 1 mediante
  `build_document_context.py`, con normalización de espacios y omisión marcada.
  No se escribió una respuesta fija ni se añadieron hechos desde conocimiento del modelo.
- Guardar SHA-256 del PDF y rechazar un manifiesto desactualizado al arrancar.
- Ampliar búsquedas generales no vacías con esta fuente padre, adicional a los
  `top_k` resultados. El fragmento padre es contexto documental, **no un nuevo
  vector rankeado**. Los filtros y artículos específicos no reciben esa ampliación.
- Permitir citar `doc-21719-p1`, mostrar procedencia y enlazar a `#page=1`.
- Pedir al planificador que no convierta una consulta general en un artículo
  específico ni altere números de leyes al reformular.

El índice sigue teniendo 140 filas; no fue necesario regenerar embeddings.
PDF y dataset originales conservan sus huellas. La auditoría posterior está en
[index_audit_20260909T224236671932Z.json](evidencia_local/index_audit_20260909T224236671932Z.json).

## Verificación

**Corrida final: 16/16 casos HTTP correctos**, contra Docker reconstruido con
el prompt final. [Respuestas y fuentes completas](evidencia_local/live_http_20260909T225324179138Z.json).
Incluye las cinco regresiones nuevas y los once casos anteriores. Son pruebas
funcionales de esta ejecución, no una garantía de respuestas futuras idénticas.

Primera corrida: [8 de 9 casos intentados](evidencia_local/live_http_20260909T224518328958Z.json).
Pasaron las cinco regresiones nuevas y los tres casos de memoria. El artículo 4
produjo un rechazo de validación (HTTP 503). Una comprobación aislada del generador
reprodujo el defecto: declaró `art-4` en la lista de fuentes pero omitió la cita
visible en `answer`. Se mantuvo el rechazo conservador y se aclaró el prompt:
listar IDs no sustituye escribir las citas junto a las afirmaciones. La prueba
aislada posterior devolvió citas visibles. No se ocultó ni reemplazó la evidencia
de la corrida fallida.

- **Build:** imagen Docker reconstruida; API y base saludables.
- **Tests offline:** 50/50, incluidos 7 nuevos de extracción reproducible,
  huella, procedencia, filtros, contexto del prompt y validación de citas.
- **Sintaxis/dependencias:** compileall, node --check y pip check correctos.
- **Tipos/lint/cobertura:** pyright, ruff y coverage no configurados/instalados;
  no se afirma comprobación estática completa ni porcentaje de cobertura.
- **Seguridad:** 0 archivos de código de etapa 3 con las claves/contraseña
  configuradas; `.env` continúa ignorado. Sin cambios al PDF ni a etapa 1.
- **Navegador:** pregunta exacta enviada en una sesión propia; respuesta sobre
  protección/tratamiento y Agencia, cita desplegable con texto original y
  enlace al PDF en página 1. No se borró la conversación del usuario en Opera.
- **Regresión real:** cinco casos nuevos: pregunta exacta, relación de leyes,
  resumen del PDF, número sin separador y ley desconocida. Se repiten también
  los once casos anteriores; el JSON conserva las respuestas, no solo contadores.

Las guías PDF y verification-loop guiaron el contraste con el original y las
comprobaciones de implementación. Las pruebas funcionales no equivalen a una
evaluación jurídica exhaustiva ni garantizan toda futura respuesta del LLM.

### Hallazgo de fidelidad pendiente, fuera de esta corrección de procedencia

La revisión manual de la corrida final detectó que el resumen del artículo 1 bis
dice «titulares chilenos», mientras la fuente dice «titulares que se encuentren
en Chile». No son equivalentes: nacionalidad frente a ubicación. Su check pasó
porque verifica artículo/sufijo/cita, no esa distinción semántica. Por tanto,
**16/16 checks funcionales no significa 16 respuestas jurídicamente perfectas**.
Debe cubrirse en la siguiente revisión de fidelidad antes de presentar la
demostración como confiable para consultas legales. La pregunta general y las
respuestas sobre procedencia sí se contrastaron con título y encabezado originales.

## Repetición

Ver la [guía de arranque y pruebas](../etapa3_producto/README.md).
Recargar el chat tras la actualización e iniciar una conversación nueva.
La indexación no se repite. Cambios sin commit ni push.
