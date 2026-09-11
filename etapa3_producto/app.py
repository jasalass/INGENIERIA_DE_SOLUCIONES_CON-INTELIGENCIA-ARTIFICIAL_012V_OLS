"""FastAPI + orquestación LangChain. Ejecutar un solo worker para memoria local."""

import importlib
import logging
import os
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.runnables import RunnableLambda
from langsmith import tracing_context
from dotenv import load_dotenv
from .contracts import Backend, ChatRequest, ChatResponse, Generation, QueryPlan, Source, Turn
from .demo import DemoBackend, normalize, parse_article_reference

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=False)
LOGGER = logging.getLogger(__name__)


def _has_visible_citation(answer: str, chunk_id: str) -> bool:
    """True si `chunk_id` aparece citado como "[chunk_id]" en la respuesta,
    tolerando espacios dentro de los corchetes y variantes de mayúscula
    (un modelo puede escribir "[ id]" o "[ID]" sin que la cita deje de ser
    válida) -- antes se exigia coincidencia exacta de substring, y una
    variante de formato asi de menor rechazaba una respuesta correcta."""
    return re.search(rf"\[\s*{re.escape(chunk_id)}\s*\]", answer, re.IGNORECASE) is not None


@dataclass
class Conversation:
    turns: list[Turn] = field(default_factory=list)
    query: str = ""
    count: int = 0
    updated: float = field(default_factory=time.monotonic)


def create_app(backend: Backend | None = None, *, mode: str | None = None, ttl: float = 3600, capacity: int = 100) -> FastAPI:
    selected_mode = mode or os.getenv("RAG_MODE", "demo")
    if selected_mode not in {"demo", "groq", "live"}:
        raise RuntimeError("RAG_MODE debe ser demo, groq o live")
    if backend is None:
        if selected_mode == "demo":
            backend = DemoBackend(ROOT / "etapa1_datos/data/processed/chunks.json")
        elif selected_mode == "groq":
            from .groq_backend import GroqBackend
            backend = GroqBackend(ROOT / "etapa1_datos/data/processed/chunks.json")
        else:
            factory = os.getenv("RAG_BACKEND_FACTORY", "")
            if not factory or ":" not in factory:
                raise RuntimeError("Modo live requiere RAG_BACKEND_FACTORY=modulo:factory; no hay fallback a demo")
            module, name = factory.split(":", 1)
            backend = getattr(importlib.import_module(module), name)()

    api = FastAPI(title="Asistente Ley 21.719", version="0.2.0", description="Demo: sin LLM. Groq: generación y memoria con búsqueda léxica. Live: adaptador del equipo.")
    sessions: dict[str, Conversation] = {}
    lock = threading.RLock()

    def prune():
        for key in [key for key, value in sessions.items() if time.monotonic() - value.updated > ttl]:
            del sessions[key]

    def retrieve_step(state):
        started = time.perf_counter()
        planner = getattr(backend, "plan_query", None)
        state["kind"] = "document"
        if planner:
            plan = QueryPlan.model_validate(planner(state["request"].message, state["history"]))
            state["query"], state["kind"] = plan.query, plan.kind
        state["timings"]["planning"] = round((time.perf_counter() - started) * 1000, 2)
        started = time.perf_counter()
        state["sources"] = [] if state["kind"] == "conversation" else [Source.model_validate(s) for s in backend.retrieve(state["query"], state["request"].top_k, state["request"].filters)]
        state["timings"]["retrieval"] = round((time.perf_counter() - started) * 1000, 2)
        return state

    def generate_step(state):
        started = time.perf_counter()
        if state["kind"] == "conversation":
            generation = backend.converse(state["request"].message, state["history"])
        else:
            generation = backend.generate(state["request"].message, state["history"], state["sources"])
        state["generation"] = Generation.model_validate(generation)
        state["timings"]["generation"] = round((time.perf_counter() - started) * 1000, 2)
        return state

    chain = RunnableLambda(retrieve_step) | RunnableLambda(generate_step)

    @api.middleware("http")
    async def headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'" if not request.url.path.startswith("/docs") else "frame-ancestors 'none'"
        return response

    @api.get("/health")
    @api.get("/api/health", include_in_schema=False)
    def health():
        return {"status": "ok", "mode": selected_mode, "retrieval": getattr(backend, "retrieval_name", {"demo": "lexical_demo", "groq": "lexical", "live": "adapter"}[selected_mode]), "generation": getattr(backend, "generation_name", {"demo": "literal_excerpts", "groq": "groq", "live": "adapter"}[selected_mode]), "model": getattr(backend, "model_name", None), "memory": "in_process", "memory_exchanges": 6, "session_ttl_seconds": ttl, "provider_reachable": "not_checked"}

    @api.post("/chat", response_model=ChatResponse)
    @api.post("/api/chat", response_model=ChatResponse, include_in_schema=False)
    def chat(request: ChatRequest):
        # El lock solo protege el diccionario `sessions` compartido (altas,
        # bajas, lectura del historial) -- NO envuelve la llamada de red a
        # Groq/Mistral (chain.invoke, mas abajo, fuera del lock). Antes lo
        # envolvia todo: dos conversaciones sin relacion entre si se
        # bloqueaban una a la otra mientras cualquiera de las dos esperaba
        # al proveedor (hasta ~20s), pudiendo hacer que el frontend de la
        # otra conversacion agotara su propio timeout sin motivo real.
        # Limitacion que queda: si el MISMO conversation_id recibe dos
        # requests concurrentes, ambos pueden leer el mismo historial antes
        # de que el primero termine (se pierde la serializacion estricta que
        # tenia el lock unico) -- aceptable para el prototipo de un solo
        # worker que ya documentaba este archivo; un cliente normal no
        # manda dos mensajes a la vez para la misma conversación.
        with lock:
            prune()
            cid = request.conversation_id or uuid.uuid4().hex
            if request.conversation_id and cid not in sessions:
                raise HTTPException(404, "La conversación expiró o el servidor se reinició. Inicia una nueva consulta.")
            if cid not in sessions and len(sessions) >= capacity:
                raise HTTPException(503, "Se alcanzó el límite de conversaciones. Intenta más tarde.")
            session = sessions.setdefault(cid, Conversation())
            history_snapshot = list(session.turns)
            query = request.message
            # Regla explícita de demo; se reemplazará por reformulación con LLM.
            if not hasattr(backend, "plan_query") and session.query and re.match(r"^(y\b|ese\b|esa\b|eso\b|amplia\b|explica mas\b|continua\b)", normalize(query).lstrip("¿¡ \t\n")) and not parse_article_reference(query)[0]:
                query = f"{session.query[:2000]}\nSeguimiento: {request.message}"

        started = time.perf_counter()
        try:
            with tracing_context(enabled=False):
                result = chain.invoke({"request": request, "query": query, "history": history_snapshot, "sources": [], "timings": {}})
            generation = result["generation"]
            by_id = {s.chunk_id: s for s in result["sources"]}
            if len(by_id) != len(result["sources"]):
                raise ValueError("El adaptador devolvió chunk_id duplicados")
            if not set(generation.cited_chunk_ids).issubset(by_id):
                raise ValueError("La generación citó un chunk no recuperado")
            if result["kind"] == "document" and not generation.insufficient_context and not generation.cited_chunk_ids:
                raise ValueError("Respuesta sin fuentes ni abstención")
            if selected_mode in {"groq", "live"} and any(not _has_visible_citation(generation.answer, key) for key in generation.cited_chunk_ids):
                raise ValueError("Falta cita visible en la respuesta")
            if re.search(r"</?think\b", generation.answer, re.IGNORECASE):
                raise ValueError("Razonamiento interno en respuesta")
            cited = [by_id[key] for key in dict.fromkeys(generation.cited_chunk_ids)]
        except Exception as exc:
            # No registrar prompts ni posibles credenciales de excepciones externas.
            LOGGER.warning("Fallo del adaptador RAG: %s", type(exc).__name__)
            status = getattr(exc, "status_code", None)
            if status == 429:
                provider = "Mistral" if getattr(exc, "provider", None) == "Mistral" else "Groq"
                raise HTTPException(503, f"{provider} alcanzó un límite de uso. Espera un momento y vuelve a intentar; no se guardó este turno.", headers={"Retry-After": "30"}) from None
            if status in {401, 403}:
                raise HTTPException(503, "El proveedor rechazó el acceso. Revisa la clave local y sus permisos; no se guardó este turno.") from None
            if status == 404:
                raise HTTPException(503, "El proveedor no encontró el modelo configurado. Revisa LLM_MODEL; no se guardó este turno.") from None
            raise HTTPException(503, "No se pudo completar la consulta. Intenta nuevamente; no se guardó este turno.") from None

        with lock:
            session = sessions.get(cid)
            if session is None:
                raise HTTPException(404, "La conversación expiró mientras se generaba la respuesta. Intenta de nuevo.")
            session.turns = (session.turns + [Turn(role="user", content=request.message), Turn(role="assistant", content=generation.answer)])[-12:]
            session.query = result["query"]
            session.count += 1
            session.updated = time.monotonic()
            turn_count = session.count
        result["timings"]["total"] = round((time.perf_counter() - started) * 1000, 2)
        return ChatResponse(answer=generation.answer, conversation_id=cid, mode=selected_mode, sources=[{**s.model_dump(), "label": s.label, "url": "/api/source.pdf" + (f"#page={s.pagina_pdf}" if s.pagina_pdf else "")} for s in cited], insufficient_context=generation.insufficient_context, retrieval_query=result["query"], turn_count=turn_count, answer_kind=result["kind"], timings_ms=result["timings"])

    @api.delete("/api/conversations/{conversation_id}", status_code=204)
    def delete_conversation(conversation_id: str):
        with lock:
            sessions.pop(conversation_id, None)
        return Response(status_code=204)

    @api.get("/api/source.pdf", include_in_schema=False)
    def source_pdf():
        return FileResponse(ROOT / "docs/Ley-21719_13-DIC-2024.pdf", media_type="application/pdf")

    api.mount("/", StaticFiles(directory=ROOT / "etapa3_producto/frontend", html=True), name="frontend")
    return api


app = create_app()
