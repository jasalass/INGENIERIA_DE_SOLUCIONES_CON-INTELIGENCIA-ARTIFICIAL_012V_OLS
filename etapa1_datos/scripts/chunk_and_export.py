"""
Fase 4 del pipeline de datos (Etapa 1): convierte las 90 entradas de
articulos_detectados.json (Fase 3) en el chunks.json final -- el
entregable que recibe Juan para indexar en pgvector.

Regla base: 1 entrada (articulo real, o nivel1/transitorio) = 1 chunk.
Es la unidad correcta porque Juan necesita filtrar por articulo via SQL
y citar "segun el articulo N" en las respuestas -- partir un articulo
en trozos de tamano fijo rompería esa trazabilidad.

Excepcion, con umbral concreto (1 token en espanol equivale aprox. a 4
caracteres, razonable para gemini-embedding-001):
  - Articulo largo (>2000 caracteres): se parte por inciso, agrupando
    incisos consecutivos hasta acercarse a ~1500 caracteres por
    sub-chunk sin cortar un inciso a la mitad, con overlap de 1 inciso
    entre sub-chunks consecutivos (se repite el ultimo inciso del grupo
    anterior al inicio del siguiente) para no perder contexto en la
    frontera. Cada sub-chunk conserva el mismo "articulo" pero agrega
    "parte": "1/2", "2/2", etc.
  - Articulo muy corto (<150 caracteres): NO se fusiona con el vecino
    -- fusionar mezclaria dos numeros de articulo en un mismo chunk y
    rompería el filtro SQL por articulo de Juan. Se deja como chunk
    propio aunque sea corto (se documenta esta decision en
    justificacion_chunking.md).
"""

import json
import re

ARTICULOS_PATH = "etapa1_datos/data/processed/articulos_detectados.json"
METADATA_PATH = "etapa1_datos/data/interim/metadata.json"
OUTPUT_PATH = "etapa1_datos/data/processed/chunks.json"

UMBRAL_LARGO = 2000
TAMANO_OBJETIVO = 1500
UMBRAL_CORTO = 150

MESES = {
    "ENE": "01", "FEB": "02", "MAR": "03", "ABR": "04", "MAY": "05", "JUN": "06",
    "JUL": "07", "AGO": "08", "SEP": "09", "OCT": "10", "NOV": "11", "DIC": "12",
}
FECHA_RE = re.compile(r"^(\d{1,2})-(\w{3})-(\d{4})$")


def fecha_a_iso(fecha_str):
    """Convierte "13-DIC-2024" a "2024-12-13". Si el formato no calza
    (o el campo es None), devuelve None en vez de fallar -- el pipeline
    no deberia romperse por un dato de fecha faltante."""
    if not fecha_str:
        return None
    match = FECHA_RE.match(fecha_str.upper())
    if not match:
        return None
    dia, mes_abbr, anio = match.groups()
    mes = MESES.get(mes_abbr)
    if not mes:
        return None
    return f"{anio}-{mes}-{dia.zfill(2)}"


def agrupar_con_overlap(incisos, tamano_objetivo):
    """Agrupa incisos consecutivos hasta acercarse a tamano_objetivo
    caracteres, sin cortar un inciso a la mitad. Cada grupo nuevo
    empieza repitiendo el ultimo inciso del grupo anterior (overlap de
    1 inciso) para no perder contexto en la frontera entre sub-chunks."""
    grupos = []
    grupo_actual = []
    largo_actual = 0

    for inciso in incisos:
        si_cabe = largo_actual + len(inciso) <= tamano_objetivo
        if grupo_actual and not si_cabe:
            grupos.append(grupo_actual)
            grupo_actual = [grupo_actual[-1], inciso]
            largo_actual = len(grupo_actual[0]) + len(inciso)
        else:
            grupo_actual.append(inciso)
            largo_actual += len(inciso)

    if grupo_actual:
        grupos.append(grupo_actual)
    return grupos


def construir_sub_chunks(entry):
    """Devuelve una lista de (texto, parte) para una entrada: un solo
    elemento si cabe en el umbral, o varios con overlap si es un
    articulo largo."""
    texto_completo = "\n\n".join(entry["incisos"])

    if len(texto_completo) <= UMBRAL_LARGO:
        return [(texto_completo, "1/1")]

    grupos = agrupar_con_overlap(entry["incisos"], TAMANO_OBJETIVO)
    total = len(grupos)
    return [("\n\n".join(grupo), f"{i + 1}/{total}") for i, grupo in enumerate(grupos)]


def construir_chunks(entries, metadata):
    fecha_publicacion = fecha_a_iso(metadata.get("fecha_publicacion"))
    fecha_promulgacion = fecha_a_iso(metadata.get("fecha_promulgacion"))
    fuente = metadata.get("fuente")

    chunks = []
    for entry in entries:
        sub_chunks = construir_sub_chunks(entry)
        for texto, parte in sub_chunks:
            sufijo_id = "" if parte == "1/1" else f"-p{parte.split('/')[0]}"
            chunks.append({
                "id": entry["id"],
                "chunk_id": f"{entry['id']}{sufijo_id}",
                "nivel1": entry["nivel1"],
                "ley_referenciada": entry["ley_referenciada"],
                "ambito": entry["ambito"],
                "titulo_numero": entry["titulo_numero"],
                "titulo_nombre": entry["titulo_nombre"],
                "articulo": entry["articulo"],
                "articulo_sufijo": entry["articulo_sufijo"],
                "articulo_nombre": entry["articulo_nombre"],
                "parte": parte,
                "texto": texto,
                "fecha_publicacion": fecha_publicacion,
                "fecha_promulgacion": fecha_promulgacion,
                "fuente": fuente,
            })
    return chunks


def main():
    with open(ARTICULOS_PATH, encoding="utf-8") as f:
        entries = json.load(f)
    with open(METADATA_PATH, encoding="utf-8") as f:
        metadata = json.load(f)

    chunks = construir_chunks(entries, metadata)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False, indent=2)

    largos = [c for c in chunks if c["parte"] != "1/1"]
    cortos = [c for c in chunks if len(c["texto"]) < UMBRAL_CORTO]

    print(f"Chunks generados: {len(chunks)} (a partir de {len(entries)} entradas)")
    print(f"  - sub-chunks por articulo largo: {len(largos)}")
    print(f"  - chunks muy cortos (<{UMBRAL_CORTO} chars, se dejan igual): {len(cortos)}")
    print(f"Guardado en {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
