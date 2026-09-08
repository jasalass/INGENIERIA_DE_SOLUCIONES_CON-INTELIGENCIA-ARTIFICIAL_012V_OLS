"""
Fase 5 del pipeline de datos (Etapa 1): checklist de verificacion sobre
chunks.json antes de entregarselo a Juan. No "arregla" nada -- solo
imprime un reporte para revision manual.

Chequeos, en este orden:
  1. Conteo de articulos reales (por "id") vs. un conteo de referencia
     independiente, calculado con una regex simple sobre el texto
     limpio (no reutiliza el parser de la Fase 3 a proposito: si el
     parser tuviera un bug, comparar contra si mismo no lo detectaria).
  2. Numeros de Titulo unicos detectados vs. los observados a mano.
  3. Textos vacios o sospechosamente cortos (<20 caracteres) -- no
     deberia haber ninguno a esta altura del pipeline.
  4. Muestra fija de chunks para inspeccion visual: el mas largo, el
     mas corto, uno "bis", uno transitorio y uno "normal".
  5. Trazabilidad de longitud: cuanto texto de 02_clean_text.txt quedo
     fuera de cualquier chunk (preambulo, instrucciones descartadas
     tipo "En el articulo N:", etc.) -- se espera una diferencia
     visible y se documenta por que en justificacion_chunking.md, pero
     no deberia ser la mayoria del documento.
"""

import json
import re

CLEAN_TEXT_PATH = "etapa1_datos/data/interim/02_clean_text.txt"
CHUNKS_PATH = "etapa1_datos/data/processed/chunks.json"

UMBRAL_CORTO_SOSPECHOSO = 20


def contar_articulos_referencia(clean_text):
    """Conteo independiente (no usa parse_structure.py) de encabezados
    reales "Articulo N deg.-", para detectar si el parser se comio
    alguno o inflo el conteo por error."""
    patron = re.compile(r'(?m)^ ?"?Art[ií]culo\s+\d+\s*°?\s*\S*\s*\.-')
    return len(patron.findall(clean_text))


def chequear_textos_cortos(chunks):
    return [c for c in chunks if len(c["texto"].strip()) < UMBRAL_CORTO_SOSPECHOSO]


def mostrar_muestra(chunks):
    por_largo = sorted(chunks, key=lambda c: len(c["texto"]))
    mas_corto = por_largo[0]
    mas_largo = por_largo[-1]
    con_bis = next((c for c in chunks if c["articulo_sufijo"] == "bis"), None)
    transitorio = next((c for c in chunks if c["ambito"] == "transitorio"), None)
    normal = next(
        (c for c in chunks if c["articulo"] and not c["articulo_sufijo"] and c["parte"] == "1/1"),
        None,
    )

    etiquetas = [
        ("MAS CORTO", mas_corto),
        ("MAS LARGO", mas_largo),
        ("CON SUFIJO BIS", con_bis),
        ("TRANSITORIO", transitorio),
        ("NORMAL", normal),
    ]
    print("\n--- Muestra para inspeccion manual ---")
    for etiqueta, chunk in etiquetas:
        if chunk is None:
            print(f"[{etiqueta}] no encontrado")
            continue
        print(f"\n[{etiqueta}] {chunk['chunk_id']} ({len(chunk['texto'])} caracteres)")
        print(f"  articulo={chunk['articulo']} titulo={chunk['titulo_numero']} ambito={chunk['ambito']}")
        print(f"  texto: {chunk['texto'][:150]}...")


def chequear_trazabilidad(clean_text, chunks):
    largo_clean = len(clean_text)
    largo_chunks = sum(len(c["texto"]) for c in chunks)
    # Los chunks largos duplican texto por el overlap de 1 inciso entre
    # sub-chunks -- hay que descontarlo para comparar contra el texto
    # limpio original, que no tiene esa duplicacion.
    print("\n--- Trazabilidad de longitud ---")
    print(f"Caracteres en 02_clean_text.txt: {largo_clean}")
    print(f"Caracteres sumados en chunks.json (incluye overlap duplicado): {largo_chunks}")
    print(
        "Diferencia esperada: preambulo/titulo de la ley (no pertenece a ningun "
        "articulo), instrucciones de redaccion descartadas (ej. \"9) En el "
        "articulo 17:\"), y el overlap de 1 inciso en articulos largos que "
        "duplica texto a proposito."
    )


def main():
    with open(CLEAN_TEXT_PATH, encoding="utf-8") as f:
        clean_text = f.read()
    with open(CHUNKS_PATH, encoding="utf-8") as f:
        chunks = json.load(f)

    ids_unicos = {c["id"] for c in chunks}
    articulos_reales = {c["id"] for c in chunks if c["articulo"]}
    referencia = contar_articulos_referencia(clean_text)

    print(f"Chunks totales: {len(chunks)}")
    print(f"Entradas (id) unicas: {len(ids_unicos)}")
    print(f"Articulos reales (id con numero de articulo): {len(articulos_reales)}")
    print(f"Conteo de referencia independiente (regex sobre texto limpio): {referencia}")
    if len(articulos_reales) != referencia:
        print(
            f"  AVISO: diferencia de {abs(len(articulos_reales) - referencia)} -- "
            "revisar manualmente cual de los dos conteos esta mal."
        )

    titulos = sorted({c["titulo_numero"] for c in chunks if c["titulo_numero"]})
    print(f"\nTitulos detectados: {titulos}")

    cortos = chequear_textos_cortos(chunks)
    print(f"\nChunks con texto sospechosamente corto (<{UMBRAL_CORTO_SOSPECHOSO} chars): {len(cortos)}")
    for c in cortos:
        print(f"  {c['chunk_id']}: {c['texto']!r}")

    mostrar_muestra(chunks)
    chequear_trazabilidad(clean_text, chunks)


if __name__ == "__main__":
    main()
