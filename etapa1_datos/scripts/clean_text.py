"""
Fase 2 del pipeline de datos (Etapa 1): limpia y normaliza el texto crudo
de 01_raw_text.txt para dejar un texto corrido apto para detectar la
estructura de la ley en la Fase 3.

Se trabaja linea por linea, en este orden:
  1. Descartar el marcador [PAGE_BREAK] que agrega extract_pdf.py.
  2. Descartar las lineas de footer, que en este PDF son SIEMPRE dos
     lineas separadas (se confirmo inspeccionando el texto crudo):
       "Biblioteca del Congreso Nacional de Chile - www.leychile.cl - ..."
       "pagina N de 56"
  3. Descartar la linea de header, que es la linea exacta "Ley 21719"
     (aparece sola, una vez por pagina).
  4. Cortar anotaciones marginales: se verifico que TODAS quedan
     precedidas por un salto de 3+ espacios en la misma linea que el
     texto principal, sin ningun falso positivo en el resto del
     documento -- por eso es seguro cortar ahi cualquier linea.
  5. Descartar lineas que quedaron vacias tras el corte del paso 4
     (eran anotaciones que ocupaban la linea completa).
  6. Normalizar el simbolo de grado (o/°) a uno solo: °.
  7. Reconstruir parrafos: decidir entre cada dos lineas sobrevivientes
     si van unidas por un espacio (misma oracion cortada por el ancho
     de pagina) o por un salto de parrafo real "\n\n" (la siguiente
     linea empieza un articulo, titulo, o inciso nuevo).
  8. Colapsar espacios multiples remanentes.
"""

import re

RAW_TEXT_PATH = "etapa1_datos/data/interim/01_raw_text.txt"
CLEAN_TEXT_PATH = "etapa1_datos/data/interim/02_clean_text.txt"

# Ancla al INICIO de la linea (tras strip): asi no se confunde con una
# mencion a "la Biblioteca del Congreso" dentro de un articulo, si la
# hubiera.
FOOTER_SOURCE_RE = re.compile(r"^Biblioteca del Congreso Nacional", re.IGNORECASE)
FOOTER_PAGE_RE = re.compile(r"^p[aá]gina \d+ de \d+$", re.IGNORECASE)

# Corta la linea en el primer salto de 3+ espacios (anotacion marginal
# que viene DESPUES de texto real en la misma linea).
MARGIN_GAP_RE = re.compile(r"\s{3,}\S")

# Caso aparte: cuando la anotacion ocupa la linea COMPLETA (solo
# indentacion + "Art. 31" o "D.O. 11.07.2025", sin texto real antes),
# no hay ningun salto de 3+ espacios que detectar -- hay que reconocer
# el patron entero de la linea y descartarla directamente.
MARGIN_ONLY_RE = re.compile(
    r"^(Ley \d{4,5}|Art\.\s?\d+.*|D\.O\.\s?\d{2}\.\d{2}\.\d{4})$"
)

# Que cuenta como "empieza algo nuevo" (articulo/titulo/inciso de lista),
# para decidir un salto de parrafo real en vez de una simple continuacion
# de oracion cortada por el ancho de pagina.
NEW_BLOCK_RE = re.compile(r'^"?(Art[ií]culo|T[ií]tulo|[a-z]\)|\d+\))')


def is_page_break_marker(line):
    return line.strip() == "[PAGE_BREAK]"


def is_footer_line(line):
    stripped = line.strip()
    return bool(FOOTER_SOURCE_RE.match(stripped) or FOOTER_PAGE_RE.match(stripped))


def is_header_line(line):
    return line.strip() == "Ley 21719"


def strip_margin_annotation(line):
    """Corta en el primer salto de 3+ espacios, pero SOLO buscando a
    partir del primer caracter no-espacio: los articulos vienen con
    sangria inicial (varios espacios de indentacion), y sin este
    resguardo esa sangria se confunde con el salto que separa el texto
    de una anotacion marginal, borrando la linea completa."""
    indent_end = len(line) - len(line.lstrip(" "))
    match = MARGIN_GAP_RE.search(line, indent_end)
    return line[: match.start()] if match else line


def filter_lines(raw_text):
    """Pasos 1-6: devuelve la lista de lineas de texto real que
    sobreviven la limpieza (sin footer/header/anotaciones/vacias)."""
    kept = []
    for raw_line in raw_text.splitlines():
        if is_page_break_marker(raw_line) or is_footer_line(raw_line) or is_header_line(raw_line):
            continue
        if MARGIN_ONLY_RE.match(raw_line.strip()):
            continue
        line = strip_margin_annotation(raw_line)
        line = line.replace("º", "°")
        if not line.strip():
            continue
        kept.append(line.rstrip())
    return kept


def is_paragraph_break(prev_line, next_line):
    """True si next_line inicia un bloque nuevo (articulo/titulo/item de
    lista), o si prev_line termina una oracion (., :, ;) y next_line
    arranca con mayuscula -- en ambos casos va un salto de parrafo real
    en vez de solo unir con un espacio."""
    next_stripped = next_line.strip()
    if NEW_BLOCK_RE.match(next_stripped):
        return True
    ends_sentence = prev_line.rstrip().endswith((".", ":", ";"))
    starts_upper = bool(next_stripped) and next_stripped[0].isupper()
    return ends_sentence and starts_upper


def join_lines(lines):
    """Reconstruye parrafos uniendo lineas consecutivas con un espacio
    (continuacion de la misma oracion) o con "\n\n" (parrafo nuevo)."""
    if not lines:
        return ""
    result = lines[0]
    for prev, curr in zip(lines, lines[1:]):
        separator = "\n\n" if is_paragraph_break(prev, curr) else " "
        result += separator + curr
    return result


def clean(raw_text):
    lines = filter_lines(raw_text)
    joined = join_lines(lines)
    return re.sub(r"[ \t]{2,}", " ", joined)


def main():
    with open(RAW_TEXT_PATH, encoding="utf-8") as f:
        raw_text = f.read()

    clean_text = clean(raw_text)

    with open(CLEAN_TEXT_PATH, "w", encoding="utf-8") as f:
        f.write(clean_text)

    print(
        f"Texto limpio guardado en {CLEAN_TEXT_PATH} "
        f"({len(clean_text)} caracteres, {len(raw_text) - len(clean_text)} "
        f"caracteres menos que el crudo)"
    )


if __name__ == "__main__":
    main()
