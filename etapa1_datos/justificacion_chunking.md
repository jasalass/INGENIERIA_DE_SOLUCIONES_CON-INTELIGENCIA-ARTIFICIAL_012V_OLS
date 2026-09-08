# Justificación de la estrategia de chunking — Ley N°21.719

Etapa 1 (Datos) — Asistente RAG sobre la Ley N°21.719. Este documento explica cómo se obtuvo, limpió, estructuró y fragmentó el texto de la ley, y por qué se tomó cada decisión.

## 1. Fuente y extracción de texto

**Fuente**: `Docs/Ley-21719_13-DIC-2024.pdf`, publicación oficial de la Biblioteca del Congreso Nacional (leychile.cl), 56 páginas.

**Método**: extracción con **PyMuPDF** (`pymupdf`, importado como `fitz`), usando `page.get_text("text")` por página. Se descartó `pdftotext -layout` (que preserva columnas) y `pdfplumber`/`pypdf` por lo siguiente:

- El documento trae, junto a algunos artículos, anotaciones marginales de historial de modificación en una columna aparte (ej. `Ley 21806 Art. 54 N°1 a) D.O. 05.02.2026`). Extraer preservando el layout de columnas intercala esas anotaciones a mitad de oración del artículo. `get_text("text")` extrae en orden de lectura por línea, dejando la anotación al final de la misma línea del texto principal, separada por un salto de espacios — mucho más fácil de filtrar en la limpieza.
- No depende de un binario externo (`pdftotext`), por lo que el pipeline es reproducible en cualquier máquina del equipo o dentro de un contenedor Docker.

De la página 1 se extraen además, por regex, las fechas de publicación (`13-DIC-2024`) y promulgación (`25-NOV-2024`), en vez de escribirlas a mano, para que el pipeline siga funcionando si se reemplaza el PDF por otra versión de la ley.

## 2. Limpieza y normalización

Se procesó línea por línea, en este orden:

1. **Anotaciones marginales**: se verificó empíricamente que las 30 anotaciones marginales del documento quedan siempre precedidas por un salto de 4 o más espacios en la misma línea que el texto principal, **sin ningún falso positivo** en el resto del documento — por eso se corta cualquier línea en el primer salto de 3+ espacios encontrado después del primer carácter no-espacio (se excluye la sangría inicial de línea para no confundirla con este salto).
2. **Anotaciones que ocupan la línea completa** (ej. `"Art. 31"`, `"D.O. 11.07.2025"` solos): se reconoce el patrón completo de la línea y se descarta.
3. **Footer**: dos líneas repetidas por página — `"Biblioteca del Congreso Nacional..."` y `"página N de 56"` — se descartan por patrón.
4. **Header**: la línea exacta `"Ley 21719"`, repetida una vez por página.
5. **Normalización**: el símbolo de grado (`º`/`°`) se unifica a uno solo; espacios múltiples se colapsan.
6. **Reconstrucción de párrafos**: dos líneas consecutivas se unen con un espacio si son la misma oración cortada por el ancho de página, o con un salto de párrafo si la siguiente línea inicia un artículo, título, o ítem de lista, o si la anterior termina en `.`/`:`/`;` y la siguiente empieza con mayúscula.

Resultado: 165.867 caracteres crudos → 153.591 caracteres limpios.

## 3. Detección de estructura jerárquica

El documento tiene una jerarquía de ley modificatoria, no de ley consolidada:

- **`DISPOSICIONES TRANSITORIAS`**: separador único que divide el documento en zona "permanente" y "transitoria".
- **`Artículo primero/segundo/.../octavo.-`** (en palabras): en la zona permanente son 3 artículos de la ley modificatoria (el primero envuelve un bloque grande de Títulos/Artículos nuevos que modifican la Ley 19.628; el segundo y tercero son modificaciones autocontenidas a las leyes 20.285 y 19.496). En la zona transitoria, cada uno es una disposición transitoria completa en sí misma. El parser trata ambos casos igual: cierran la entrada anterior y abren una propia.
- **`Título N`** (numeral romano): actualiza el contexto ambiente (número y nombre) pero no genera entrada propia — es un encabezado sin contenido normativo. **Los títulos no son correlativos**: no existe un "Título III" nuevo en este documento (solo se le hace referencia cruzada), porque esa sección de la Ley 19.628 no fue modificada por esta ley.
- **`Artículo N°.- Nombre. Cuerpo...`** (en dígitos, con sufijos latinos `bis, ter, quáter, quinquies, sexies, septies, octies, nonies`): es el artículo real de fondo.
- **Instrucciones de redacción legislativa** (ej. `"2) Reemplázase el artículo 1° por el siguiente:"`, `"9) En el artículo 17:"`, `"15) Derógase el Título Final."`): son meta-texto administrativo, no contenido normativo. Las que terminan en `:` solo anuncian un artículo/título que se captura aparte; las que no (5 casos: cambio de nombre de la ley, dos epígrafes agregados, la derogación del Título Final, y la eliminación de dos incisos de un artículo transitorio) llevan su propio cambio completo en la misma frase y se guardan como chunk propio bajo el id `instruccion-N`, porque no aparecen en ningún otro lugar del documento.
- **Cláusula de cierre del Diario Oficial** (`"Habiéndose cumplido con lo establecido en el..."`): fórmula de promulgación, firmas y fallo del Tribunal Constitucional — se detecta y se corta ahí el parseo, para no pegarla como incisos falsos del último artículo transitorio.

**Ejemplos de match / no-match** (la condición clave es que el patrón esté al **inicio de párrafo**, lo que descarta automáticamente las referencias cruzadas a mitad de oración):

| Texto | ¿Encabezado real? | Por qué |
|---|---|---|
| `Artículo 11.- Consentimiento del titular...` | Sí | Inicio de párrafo, dígito + `.-` |
| `...de conformidad con el artículo 11 de esta ley` | No | Está a mitad de oración, no al inicio de párrafo |
| `Título I De los derechos del titular...` | Sí | Inicio de párrafo, "Título" + numeral romano |
| `...con las normas del Título III de esta ley` | No | Referencia cruzada a mitad de oración |
| `9) En el artículo 17:` | Instrucción (se descarta el contenido siguiente) | Anuncia una edición puntual, termina en `:` |
| `15) Derógase el Título Final.` | Instrucción autocontenida (se guarda como chunk) | Lleva el cambio completo en la misma frase, no termina en `:` |

## 4. Estrategia de chunking

**Regla base: 1 entrada (artículo real, nivel1, o instrucción autocontenida) = 1 chunk.** Es la unidad correcta porque el motor RAG (Etapa 2) necesita filtrar por artículo vía SQL y citar "según el artículo N" en las respuestas — partir un artículo en trozos de tamaño fijo rompería esa trazabilidad.

Excepciones, con umbral concreto (1 token en español ≈ 4 caracteres, razonable para `gemini-embedding-001`):

- **Artículo largo (>2000 caracteres)**: se parte por inciso, agrupando incisos consecutivos hasta ~1500 caracteres por sub-chunk **sin cortar un inciso a la mitad** (por eso algún sub-chunk puede superar levemente los 1500 caracteres cuando un solo inciso ya es largo — 1500 es un objetivo, no un límite duro), con **overlap de 1 inciso** entre sub-chunks consecutivos (se repite el último inciso del grupo anterior al inicio del siguiente) para no perder contexto en la frontera. Cada sub-chunk conserva el mismo `articulo` pero agrega `parte: "1/2"`, `"2/2"`, etc.
- **Entrada muy corta (<150 caracteres)**: no se fusiona con la vecina — fusionar mezclaría dos artículos distintos en un mismo chunk y rompería el filtro SQL por artículo. Se deja como chunk propio aunque sea corto (7 casos en este documento: las 3 modificaciones autocontenidas a otras leyes y 4 de las 5 instrucciones autocontenidas).

## 5. Esquema de metadatos por chunk

```json
{
  "id": "art-4",
  "chunk_id": "art-4",
  "nivel1": "primero",
  "ley_referenciada": "19.628",
  "ambito": "permanente",
  "titulo_numero": "I",
  "titulo_nombre": "De los derechos del titular de datos personales",
  "articulo": "4",
  "articulo_sufijo": null,
  "articulo_nombre": "Derechos del titular de datos",
  "parte": "1/1",
  "texto": "Artículo 4°.- Derechos del titular de datos. Toda persona...",
  "fecha_publicacion": "2024-12-13",
  "fecha_promulgacion": "2024-11-25",
  "fuente": "Biblioteca del Congreso Nacional (leychile.cl)"
}
```

| Campo | Para qué lo usa Juan (retrieval/SQL) | Para qué lo usa Jenaro (respuesta) |
|---|---|---|
| `articulo`, `articulo_sufijo` | Filtro exacto por artículo | Cita "según el artículo N°" |
| `titulo_numero`, `titulo_nombre` | Filtro por tema/sección | Contexto de la respuesta ("en el Título de...") |
| `ambito` | Excluir disposiciones transitorias si no aportan | Aclarar si es una norma permanente o transitoria |
| `parte` | Saber si el chunk es un fragmento parcial de un artículo largo | Evitar citar un fragmento como si fuera el artículo completo |
| `ley_referenciada` | Distinguir a qué ley modifica (19.628, 20.285, 19.496) | Aclarar contexto legal |
| `fecha_publicacion`, `fecha_promulgacion`, `fuente` | — | Trazabilidad/citación de la fuente oficial |

## 6. Limitaciones conocidas

1. **Esta ley es modificatoria, no consolidada**: el PDF solo contiene el texto *nuevo* que se inserta o reemplaza en la Ley 19.628 (y ediciones puntuales a las leyes 20.285 y 19.496). El **Título III** de la Ley 19.628 no fue tocado por esta ley, así que su texto **no existe en este dataset** — si un usuario pregunta por un artículo de esa sección, el sistema debe responder que está fuera del alcance de la Ley 21.719, no inventar una respuesta.
2. **Modificaciones parciales a artículos existentes no quedan capturadas como texto propio**: por ejemplo, el `Artículo 2°` (definiciones) de la Ley 19.628 solo recibe reemplazos de literales sueltos (ej. "Introdúcense las siguientes modificaciones en los literales del artículo 2°..."), no una reescritura completa citable como `Artículo 2°.- Definiciones...`. Este dataset no reconstruye el artículo consolidado resultante, solo reproduce el texto que la ley modificatoria cita íntegramente.
3. **Vigencia diferida**: partes de la ley entran en vigor en fechas distintas (hasta el 01-DIC-2026 según los metadatos del propio documento). Este dataset no distingue qué artículos están vigentes hoy vs. en el futuro — todos los chunks representan el texto tal como quedará una vez que la ley esté completamente en vigor.
4. **Alcance del proyecto**: dado que el objetivo declarado es "responder consultas sobre la Ley N°21.719" (no sobre toda la legislación de protección de datos consolidada), estas limitaciones son una decisión de alcance consciente, no un defecto a corregir en esta etapa.

## 7. Verificación

- Conteo de artículos reales del pipeline (79) coincide exactamente con un conteo de referencia independiente (regex distinta sobre el texto limpio, sin reusar el parser).
- 0 chunks con texto vacío o sospechosamente corto (<20 caracteres).
- Trazabilidad de longitud: 153.591 caracteres en el texto limpio vs. 153.422 caracteres sumados en los 140 chunks finales — diferencia mínima (~0.1%), a pesar de que el overlap duplica texto y el preámbulo/instrucciones descartadas restan texto; que ambos efectos casi se cancelen respalda que no se perdió una porción significativa del contenido.
- Sin IDs duplicados ni entradas vacías en `articulos_detectados.json`.

**Resultado final**: 95 entradas (79 artículos reales + 11 nivel1/transitorios + 5 instrucciones autocontenidas) → **140 chunks** en `data/processed/chunks.json`.
