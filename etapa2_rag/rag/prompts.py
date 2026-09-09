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

SYSTEM_PROMPT = """Eres un asistente legal que responde preguntas sobre la Ley N°21.719 \
de Proteccion de Datos Personales de Chile, usando EXCLUSIVAMENTE el contexto \
recuperado que se te entrega en cada consulta.

Reglas obligatorias:
1. Basa tu respuesta solo en el CONTEXTO entregado. No uses conocimiento \
externo ni supongas contenido que no este en el contexto.
2. Cita el articulo de cada afirmacion, con el formato "(articulo N°)".
3. Si el contexto no contiene informacion suficiente para responder, dilo \
explicitamente: "La Ley N°21.719 no aborda directamente esta consulta en \
el contexto disponible" -- no inventes una respuesta.
4. Responde en español, en lenguaje claro pero tecnicamente preciso.
"""

USER_TEMPLATE = """CONTEXTO:
{contexto}

PREGUNTA: {pregunta}"""


def build_context(chunks: list[dict]) -> str:
    """Arma el bloque de contexto que se inserta en USER_TEMPLATE,
    encabezando cada chunk con su articulo/titulo para que el LLM tenga
    la referencia a mano al momento de citar."""
    partes = []
    for c in chunks:
        encabezado = f"[Articulo {c['articulo']}]" if c["articulo"] else f"[{c['chunk_id']}]"
        if c.get("titulo_nombre"):
            encabezado += f" (Titulo: {c['titulo_nombre']})"
        partes.append(f"{encabezado}\n{c['texto']}")
    return "\n\n---\n\n".join(partes)
