"""
Fase 1 del pipeline de datos (Etapa 1): extrae el texto crudo y los metadatos
de fecha desde el PDF oficial de la Ley N°21.719.

Por que PyMuPDF (pymupdf, importado como `fitz`) y no pdfplumber/pypdf/pdftotext:
- No depende de un binario externo (pdftotext), asi el pipeline corre igual
  en cualquier maquina del equipo o dentro de un contenedor Docker.
- page.get_text("text") extrae en orden de lectura (no preserva columnas),
  lo que evita que el texto de una columna se corte a la mitad por culpa
  de otra columna en medio de la pagina.

Ojo con las anotaciones marginales: el PDF trae al costado de algunos
articulos el historial de modificaciones (ej. "Ley 21806 Art. 54 N°1 a)
D.O. 05.02.2026"). Como esas anotaciones estan a la misma altura que la
linea de texto principal, get_text("text") las deja pegadas al final de
esa linea, separadas por un salto grande de espacios (4 o mas). Esta
extraccion NO las filtra a proposito -- eso se hace en la Fase 2
(clean_text.py), donde se corta cada linea en el primer salto de 3+
espacios. Mantener la extraccion "cruda" tal cual sale del PDF permite
revisar despues si el filtro de limpieza esta funcionando bien.
"""

import json
import re

import pymupdf as fitz

PDF_PATH = "docs/Ley-21719_13-DIC-2024.pdf"
RAW_TEXT_PATH = "etapa1_datos/data/interim/01_raw_text.txt"
METADATA_PATH = "etapa1_datos/data/interim/metadata.json"


def extract_raw_text(pdf_path):
    """Concatena el texto de todas las paginas, separandolas con un
    marcador propio [PAGE_BREAK] para poder rastrear despues en que
    pagina del PDF esta cada articulo, si hiciera falta."""
    doc = fitz.open(pdf_path)
    pages_text = [page.get_text("text") for page in doc]
    return "\n[PAGE_BREAK]\n".join(pages_text)


def extract_metadata(pdf_path):
    """La pagina 1 del PDF trae las fechas de publicacion/promulgacion
    como texto plano (ej. "Fecha Publicacion: 13-DIC-2024"). Se extraen
    con regex en vez de escribirlas a mano en el codigo, para que el
    pipeline siga funcionando si el equipo reemplaza el PDF por otra
    version de la ley."""
    doc = fitz.open(pdf_path)
    first_page_text = doc[0].get_text("text")

    pub_match = re.search(r"Fecha Publicaci[oó]n:\s*([\d]{1,2}-\w{3}-\d{4})", first_page_text)
    promul_match = re.search(r"Fecha Promulgaci[oó]n:\s*([\d]{1,2}-\w{3}-\d{4})", first_page_text)

    return {
        "fecha_publicacion": pub_match.group(1) if pub_match else None,
        "fecha_promulgacion": promul_match.group(1) if promul_match else None,
        "fuente": "Biblioteca del Congreso Nacional (leychile.cl)",
    }


def main():
    # encoding="utf-8" explicito en ambos archivos: la consola de Windows
    # usa cp1252 por defecto y puede mostrar mal los acentos al imprimir,
    # pero el archivo en si queda correctamente codificado en UTF-8.
    raw_text = extract_raw_text(PDF_PATH)
    with open(RAW_TEXT_PATH, "w", encoding="utf-8") as f:
        f.write(raw_text)

    metadata = extract_metadata(PDF_PATH)
    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"Texto crudo guardado en {RAW_TEXT_PATH} ({len(raw_text)} caracteres)")
    print(f"Metadatos: {metadata}")


if __name__ == "__main__":
    main()
