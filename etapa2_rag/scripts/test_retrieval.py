"""
Prueba manual del pipeline retrieval + generacion (Etapa 2). No es un
test automatizado con asserts: imprime resultados para revision manual,
igual que validate_chunks.py en la Etapa 1 -- el criterio de exito es
revisar a ojo que las fuentes citadas correspondan al articulo correcto.

Preguntas elegidas para cubrir:
  - Preguntas directas sobre articulos/temas concretos (deben citar el
    articulo correcto).
  - Una pregunta fuera de alcance a proposito: los derechos ARCO del
    Titulo III de la Ley 19.628, que esta ley NO modifica y por lo tanto
    no existe en el dataset (ver "Limitaciones conocidas" en
    etapa1_datos/justificacion_chunking.md) -- el sistema debe decir que
    no tiene informacion suficiente, no inventar una respuesta.
  - Una pregunta general/ambigua.

Requiere MISTRAL_API_KEY, LLM_API_KEY y DATABASE_URL configurados, y la
tabla `chunks` ya indexada (scripts/build_index.py).

Uso: desde etapa2_rag/, `python scripts/test_retrieval.py`
"""

import sys
import time
from pathlib import Path

# La consola de Windows usa cp1252 por defecto y no puede imprimir
# algunos caracteres Unicode que devuelve el LLM (ej. espacios finos
# u203f); forzar UTF-8 en stdout evita que el script reviente al
# imprimir una respuesta valida.
sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from rag.chain import answer_question  # noqa: E402

PREGUNTAS = [
    "¿Qué derechos tiene el titular de datos personales según la ley?",
    "¿Qué se entiende por dato personal sensible?",
    "¿Cuáles son las obligaciones del responsable de datos personales?",
    "¿Qué dice el artículo 4 de la ley?",
    "¿Qué establece el Título III sobre los derechos ARCO?",  # fuera de alcance a propósito
    "¿Cuáles son las sanciones por incumplir la ley?",
    "¿Qué rol cumple la Agencia de Protección de Datos Personales?",
    "¿Cómo se relaciona esta ley con la ley 19.628?",
]


def main() -> None:
    for i, pregunta in enumerate(PREGUNTAS):
        if i > 0:
            # Espaciar las llamadas: el tier gratuito de Groq limita
            # tokens/minuto y 8 preguntas seguidas con contexto largo lo
            # supera.
            time.sleep(8)
        resultado = answer_question(pregunta)
        print("=" * 80)
        print(f"PREGUNTA: {pregunta}")
        print(f"RESPUESTA:\n{resultado['answer']}")
        print("\nFUENTES:")
        for f in resultado["sources"]:
            print(f"  - {f['chunk_id']} (articulo {f['articulo']}, distancia={f['distancia']:.4f})")
        print()


if __name__ == "__main__":
    main()
