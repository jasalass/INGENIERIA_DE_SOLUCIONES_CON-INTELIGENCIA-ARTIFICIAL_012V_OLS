"""
Orquestacion del RAG: retrieval + prompt + LLM.

generate_answer() es la funcion reutilizable: recibe chunks YA recuperados
(por retrieval.search(), o el equivalente que arme el llamador a partir de
sus propios `Source`) y produce {"answer", "cited_chunk_ids",
"insufficient_context"} -- este es el contrato que consume la API de
Jenaro (etapa3_producto/vector_backend.py): retrieval y generacion son
ambos de esta Etapa 2, la API solo orquesta sesiones/HTTP/frontend
alrededor.

Se pide salida JSON al LLM (no texto plano) para poder inyectar el mismo
cliente LLM que ya usa GroqBackend para clasificar/conversar (bound con
response_format=json_object) -- asi la Etapa 3 no necesita mantener dos
clientes LLM distintos, y los tests existentes que inyectan un
`model_client` falso siguen funcionando igual. Aun asi, las citas nunca se
confian ciegamente del campo cited_chunk_ids que devuelve el LLM: se
recalculan buscando que identificadores de los recuperados aparecen
realmente escritos como "[chunk_id]" en el texto de la respuesta (ver
extract_cited_chunk_ids en prompts.py), para que sea imposible "citar" un
chunk que no se le paso como contexto aunque el LLM se equivoque en esa
lista.

answer_question() es la version de un solo paso (retrieval + generate_answer)
usada por scripts/test_retrieval.py para probar el motor de forma standalone.
"""

import os

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI

from .prompts import SYSTEM_PROMPT, USER_TEMPLATE, build_context, extract_cited_chunk_ids, parse_json_response
from .retrieval import search

TOP_K = 5


def _get_llm() -> ChatOpenAI:
    model = os.getenv("LLM_MODEL", "mistral-small-latest")
    # Algunos modelos servidos por Groq (ej. la familia qwen) devuelven su
    # razonamiento interno salvo que se pida explicitamente ocultarlo; sin
    # esto, el <think>...</think> se cuela en la respuesta (parse_json_response
    # lo recorta igual como red de seguridad si el proveedor no soporta esta
    # opcion).
    options = {"extra_body": {"reasoning_effort": "none", "reasoning_format": "hidden"}} if model.startswith("qwen/") else {}
    return ChatOpenAI(
        base_url=os.getenv("LLM_BASE_URL", "https://api.mistral.ai/v1"),
        api_key=os.environ["LLM_API_KEY"],
        model=model,
        temperature=0.1,
        **options,
    ).bind(response_format={"type": "json_object"})


def _history_to_messages(history: list[dict]) -> list:
    """Convierte el historial [{"role": "user"|"assistant", "content": str}, ...]
    que manda la API en mensajes de LangChain, para dar contexto
    conversacional a la siguiente pregunta (ver docs/RA1/IL1.1/4-langchain_memory.ipynb)."""
    messages = []
    for turno in history:
        if turno["role"] == "user":
            messages.append(HumanMessage(content=turno["content"]))
        elif turno["role"] == "assistant":
            messages.append(AIMessage(content=turno["content"]))
    return messages


def generate_answer(question: str, history: list[dict] | None, chunks: list[dict], *, llm=None) -> dict:
    """Genera la respuesta a partir de chunks ya recuperados (dicts con al
    menos chunk_id/texto/articulo/articulo_sufijo/titulo_nombre -- el mismo
    shape que devuelve retrieval.search(), o el `Source.model_dump()`
    equivalente). No hace retrieval por su cuenta, para que un llamador que
    ya recupero sources (ej. la API, con su propio top_k/filtros) no tenga
    que buscar dos veces.

    `llm` es inyectable (mismo patron que GroqBackend._invoke): si no se
    pasa, se crea un ChatOpenAI real leyendo LLM_BASE_URL/LLM_API_KEY/LLM_MODEL.
    """
    if not chunks:
        return {"answer": "La Ley N°21.719 no aborda directamente esta consulta en el contexto disponible.", "cited_chunk_ids": [], "insufficient_context": True}

    contexto = build_context(chunks)
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", USER_TEMPLATE),
    ])
    chain = prompt | (llm or _get_llm())
    respuesta = chain.invoke({
        "contexto": contexto,
        "pregunta": question,
        "chat_history": _history_to_messages(history or []),
    })
    parsed = parse_json_response(respuesta.content)

    answer = parsed.get("answer", "")
    available_ids = [c["chunk_id"] for c in chunks]
    cited = extract_cited_chunk_ids(answer, available_ids)
    insufficient = bool(parsed.get("insufficient_context")) or not cited
    return {"answer": answer, "cited_chunk_ids": cited, "insufficient_context": insufficient}


def answer_question(
    question: str,
    history: list[dict] | None = None,
    filtros: dict | None = None,
) -> dict:
    chunks = search(question, top_k=TOP_K, filtros=filtros)
    generation = generate_answer(question, history, chunks)

    by_id = {c["chunk_id"]: c for c in chunks}
    fuentes = [
        {
            "chunk_id": chunk_id,
            "articulo": by_id[chunk_id]["articulo"],
            "titulo_nombre": by_id[chunk_id]["titulo_nombre"],
            "distancia": by_id[chunk_id]["distancia"],
        }
        for chunk_id in generation["cited_chunk_ids"]
    ] or [
        {
            "chunk_id": c["chunk_id"],
            "articulo": c["articulo"],
            "titulo_nombre": c["titulo_nombre"],
            "distancia": c["distancia"],
        }
        for c in chunks
    ]

    return {"answer": generation["answer"], "sources": fuentes}
