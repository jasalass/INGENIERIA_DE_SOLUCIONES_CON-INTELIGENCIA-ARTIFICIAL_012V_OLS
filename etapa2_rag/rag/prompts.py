"""
Prompt del asistente RAG sobre la Ley N°21.719.

Reglas justificadas en el informe tecnico (IE2 - formulacion de prompts):

1. Responder solo con el contexto recuperado. La ley es MODIFICATORIA,
   no consolidada: hay secciones (ej. Titulo III de la Ley 19.628) que
   esta ley no toca y por lo tanto NO existen en el dataset -- ver
   "Limitaciones conocidas" en etapa1_datos/justificacion_chunking.md.
   Si el LLM usara conocimiento general en vez de solo el contexto,
   inventaria contenido de esas secciones inexistentes en el dataset.
2. Citar el articulo de origen de cada afirmacion, para trazabilidad
   (IE6 - coherencia entre datos recuperados y respuesta).
3. Decir explicitamente cuando el contexto no alcanza, en vez de
   alucinar una respuesta.
"""

import json
import re

SYSTEM_PROMPT = """Eres un asistente legal que responde preguntas sobre la Ley N°21.719 \
de Proteccion de Datos Personales de Chile, usando EXCLUSIVAMENTE el contexto \
recuperado que se te entrega en cada consulta.

Reglas obligatorias:
1. Basa tu respuesta solo en el CONTEXTO entregado. No uses conocimiento \
externo ni supongas contenido que no este en el contexto.
2. Cada fragmento del CONTEXTO empieza con un identificador entre corchetes, \
ej. "[art-4]". Cita cada afirmacion escribiendo ESE identificador exacto entre \
corchetes dentro del texto de tu respuesta (ej. "...datos [art-4]."). No lo \
reformules ni escribas "(articulo N)" en su lugar -- debe ser copiado tal cual.
3. Si un fragmento indica que modifica otra ley (ej. "[modifica la Ley 19.628]"), \
esa es la ley de fondo; la Ley N°21.719 es la norma que introduce el cambio, no \
un documento aparte -- no las confundas ni las presentes como fuentes distintas.
4. Si el contexto no contiene informacion suficiente para responder, dilo \
explicitamente en tu respuesta y marca insufficient_context en true -- no \
inventes una respuesta ni un identificador.
5. Responde en español, en lenguaje claro pero tecnicamente preciso.
6. Devuelve SOLO un objeto JSON (sin texto ni bloque de codigo alrededor) con \
las claves: answer (tu respuesta en texto, con las citas [chunk_id] incluidas \
dentro), cited_chunk_ids (lista de los identificadores citados) e \
insufficient_context (booleano).
"""

USER_TEMPLATE = """CONTEXTO:
{contexto}

PREGUNTA: {pregunta}"""


def build_context(chunks: list[dict]) -> str:
    """Arma el bloque de contexto que se inserta en USER_TEMPLATE,
    encabezando cada chunk con su chunk_id exacto (el identificador que el
    LLM debe citar tal cual, ver SYSTEM_PROMPT), su articulo/titulo como
    referencia legible, y la ley que modifica/su ambito -- sin esto el LLM
    no tiene forma de explicar por que aparece, ej., la Ley 19.628 dentro
    de una respuesta sobre la Ley 21.719 (son la misma norma modificatoria,
    no dos leyes distintas)."""
    partes = []
    for c in chunks:
        encabezado = f"[{c['chunk_id']}]"
        if c.get("articulo"):
            sufijo = f" {c['articulo_sufijo']}" if c.get("articulo_sufijo") else ""
            encabezado += f" Articulo {c['articulo']}{sufijo}"
        if c.get("titulo_nombre"):
            encabezado += f" (Titulo: {c['titulo_nombre']})"
        if c.get("ley_referenciada"):
            encabezado += f" [modifica la Ley {c['ley_referenciada']}]"
        if c.get("ambito") == "transitorio":
            encabezado += " [disposicion transitoria]"
        partes.append(f"{encabezado}\n{c['texto']}")
    return "\n\n---\n\n".join(partes)


def parse_json_response(content: str) -> dict:
    """Extrae el objeto JSON de la respuesta del LLM, tolerando que venga
    envuelto en un bloque de codigo markdown o precedido de razonamiento en
    <think>...</think> (algunos modelos servidos por Groq lo devuelven pese
    a pedir explicitamente que no lo hagan, ver _get_llm() en chain.py)."""
    if not isinstance(content, str):
        raise ValueError("Contenido no textual")
    cleaned = re.sub(r"^\s*<think>.*?</think>", "", content, flags=re.DOTALL | re.IGNORECASE).strip()
    if re.search(r"</?think\b", cleaned, re.IGNORECASE):
        raise ValueError("Razonamiento incompleto")
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
    value = json.loads(cleaned)
    if not isinstance(value, dict):
        raise ValueError("Se esperaba un objeto JSON")
    return value


def extract_cited_chunk_ids(answer: str, available_ids: list[str]) -> list[str]:
    """Devuelve los chunk_id de `available_ids` que aparecen citados como
    "[chunk_id]" en `answer` (tolerando espacios/mayusculas), en el orden
    en que aparecen. Al derivar las citas del propio texto (en vez de
    pedirle al LLM una lista aparte en JSON) se garantiza por construccion
    que nunca se "cite" un chunk que no fue recuperado."""
    posiciones = []
    for chunk_id in available_ids:
        match = re.search(rf"\[\s*{re.escape(chunk_id)}\s*\]", answer, re.IGNORECASE)
        if match:
            posiciones.append((match.start(), chunk_id))
    posiciones.sort(key=lambda item: item[0])
    vistos = dict.fromkeys(chunk_id for _, chunk_id in posiciones)
    return list(vistos)
