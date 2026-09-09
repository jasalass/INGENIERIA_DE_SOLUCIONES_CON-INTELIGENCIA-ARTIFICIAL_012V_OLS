"""
Orquestacion del RAG: retrieval + prompt + LLM.

answer_question() es el contrato que consume la API de Jenaro (Etapa 3):
recibe la pregunta y el historial de la conversacion, y devuelve la
respuesta junto con las fuentes usadas (chunk, articulo, distancia) para
la trazabilidad que pide IE6.

El LLM de chat se configura igual que docs/RA1 (ChatOpenAI apuntando a
un proveedor compatible con la API de OpenAI via LLM_BASE_URL/LLM_API_KEY),
para reusar las mismas variables de entorno que el resto del curso.
"""

import os

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .prompts import SYSTEM_PROMPT, USER_TEMPLATE, build_context
from .retrieval import search

TOP_K = 5


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        base_url=os.getenv("LLM_BASE_URL", "https://api.mistral.ai/v1"),
        api_key=os.environ["LLM_API_KEY"],
        model=os.getenv("LLM_MODEL", "mistral-small-latest"),
        temperature=0.1,
    )


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


def answer_question(
    question: str,
    history: list[dict] | None = None,
    filtros: dict | None = None,
) -> dict:
    chunks = search(question, top_k=TOP_K, filtros=filtros)
    contexto = build_context(chunks)

    messages = [SystemMessage(content=SYSTEM_PROMPT)]
    messages.extend(_history_to_messages(history or []))
    messages.append(HumanMessage(content=USER_TEMPLATE.format(contexto=contexto, pregunta=question)))

    llm = _get_llm()
    respuesta = llm.invoke(messages)

    fuentes = [
        {
            "chunk_id": c["chunk_id"],
            "articulo": c["articulo"],
            "titulo_nombre": c["titulo_nombre"],
            "distancia": c["distancia"],
        }
        for c in chunks
    ]

    return {"answer": respuesta.content, "sources": fuentes}
