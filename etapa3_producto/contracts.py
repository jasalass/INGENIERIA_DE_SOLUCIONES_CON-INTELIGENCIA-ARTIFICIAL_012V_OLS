"""Contrato de integración: el adaptador real implementará Backend."""

from typing import Literal, Protocol
from pydantic import BaseModel, ConfigDict, Field


class Filters(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    articulo: str | None = Field(default=None, min_length=1, max_length=20)
    articulo_sufijo: str | None = Field(default=None, min_length=1, max_length=20)
    ambito: Literal["permanente", "transitorio"] | None = None


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    message: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    filters: Filters = Field(default_factory=Filters)
    top_k: int = Field(default=3, ge=1, le=5)


class Source(BaseModel):
    chunk_id: str
    texto: str
    documento_origen: str = "21.719"
    pagina_pdf: int | None = Field(default=None, ge=1)
    articulo: str | None = None
    articulo_sufijo: str | None = None
    nivel1: str | None = None
    ambito: str | None = None
    ley_referenciada: str | None = None
    parte: str = "1/1"
    fuente: str
    titulo_nombre: str | None = None
    score: float | None = None

    @property
    def label(self) -> str:
        if self.pagina_pdf:
            return f"Documento Ley {self.documento_origen} · Página {self.pagina_pdf}"
        if self.articulo:
            suffix = f" {self.articulo_sufijo}" if self.articulo_sufijo else ""
            law = f" · Ley {self.ley_referenciada}" if self.ley_referenciada else ""
            return f"Artículo {self.articulo}{suffix}{law}"
        if self.ambito == "transitorio":
            return f"Disposición transitoria: {self.nivel1}"
        return f"Disposición: {self.chunk_id}"


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class Generation(BaseModel):
    answer: str = Field(min_length=1, max_length=16000)
    cited_chunk_ids: list[str]
    insufficient_context: bool = False


class QueryPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["document", "conversation"]
    query: str = Field(min_length=1, max_length=2000)


class Backend(Protocol):
    def retrieve(self, query: str, top_k: int, filters: Filters) -> list[Source]: ...

    def generate(self, question: str, history: list[Turn], sources: list[Source]) -> Generation: ...


class ChatResponse(BaseModel):
    answer: str
    conversation_id: str
    mode: Literal["demo", "groq", "live"]
    sources: list[dict]
    insufficient_context: bool
    retrieval_query: str
    turn_count: int
    answer_kind: Literal["document", "conversation"] = "document"
    timings_ms: dict[str, float] = Field(default_factory=dict)
