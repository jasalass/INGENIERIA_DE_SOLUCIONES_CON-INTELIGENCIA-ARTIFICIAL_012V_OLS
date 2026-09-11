"""
Wrapper del modelo de embeddings.

Se usa `mistral-embed` (API de Mistral, 1024 dimensiones) en vez de
Gemini `gemini-embedding-001` (768 dims, lo que usa docs/RA1/IL1.3) por
un problema de cuenta ajeno al codigo: la Generative Language API de
Google devolvia 401/403 (`API_KEY_SERVICE_BLOCKED`) para TODAS las
llamadas -- probado con 3 API keys distintas, 2 metodos de autenticacion
(`Authorization: Bearer` y `X-goog-api-key`), 2 versiones de la API
(`v1`/`v1beta`) y hasta una llamada de solo lectura (`ListModels`).
Ninguna combinacion funciono, lo que descarta un problema de key o de
codigo -- es un bloqueo de la cuenta/proyecto de Google que solo se
resuelve desde Cloud Console.

Groq (el proveedor de chat de este proyecto) tampoco sirve: no expone
ningun modelo de embeddings (confirmado consultando GET /v1/models),
igual que documenta docs/RA1/IL1.3/README.md.

Se implementa con una llamada HTTP directa (`requests`) en vez de
`langchain-mistralai` para no agregar una dependencia mas solo para
esto -- el endpoint de Mistral es compatible con la forma de la API de
OpenAI (POST /embeddings con {"model", "input"}).
"""

import os
import math

import requests

EMBEDDING_DIM = 1024

MISTRAL_BASE_URL = os.getenv("MISTRAL_BASE_URL", "https://api.mistral.ai/v1")
MISTRAL_EMBED_MODEL = os.getenv("MISTRAL_EMBED_MODEL", "mistral-embed")


class EmbeddingProviderError(RuntimeError):
    provider = "Mistral"

    def __init__(self, status_code):
        self.status_code = status_code
        super().__init__("No se pudo obtener el embedding de Mistral")


def _post_embeddings(texts: list[str]) -> list[list[float]]:
    if not texts or any(not text.strip() for text in texts):
        raise ValueError("Textos vacíos para embeddings")
    # No se rechaza aqui un MISTRAL_BASE_URL/MODEL distinto del default --eso
    # bloqueaba probar contra un endpoint propio/mock, contradiciendo que
    # ambos se leen como variables de entorno configurables (arriba). La
    # protección real del índice de 1024 dimensiones es la validación de
    # `EMBEDDING_DIM` más abajo, que rechaza cualquier vector que no calce,
    # sea cual sea el proveedor/modelo configurado.
    response = requests.post(
        f"{MISTRAL_BASE_URL}/embeddings",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {os.environ['MISTRAL_API_KEY']}",
        },
        json={"model": MISTRAL_EMBED_MODEL, "input": texts},
        timeout=(5, 15),
    )
    if not response.ok:
        raise EmbeddingProviderError(response.status_code)
    data = response.json()["data"]
    # La API devuelve los embeddings en el mismo orden que `texts`, pero
    # se ordena explicito por "index" para no depender de esa garantia.
    data.sort(key=lambda item: item["index"])
    if [item["index"] for item in data] != list(range(len(texts))):
        raise ValueError("Cantidad/orden inválido de embeddings")
    vectors = [item["embedding"] for item in data]
    if any(len(v) != EMBEDDING_DIM or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in v) or not any(v) for v in vectors):
        raise ValueError("Embedding inválido: se requieren 1024 valores finitos no nulos")
    return vectors


def embed_documents(texts: list[str]) -> list[list[float]]:
    return _post_embeddings(texts)


def embed_query(text: str) -> list[float]:
    return _post_embeddings([text])[0]
