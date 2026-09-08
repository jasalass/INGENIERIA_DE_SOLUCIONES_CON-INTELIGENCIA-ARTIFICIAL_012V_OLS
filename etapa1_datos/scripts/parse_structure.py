"""
Fase 3 del pipeline de datos (Etapa 1): recorre el texto limpio
(02_clean_text.txt) y reconstruye la jerarquia real de la ley, generando
una lista de "entradas" (nivel1 o articulo real) con toda su jerarquia
resuelta.

Jerarquia del documento (confirmada inspeccionando el texto real, no
solo el enunciado del curso):

  - DISPOSICIONES TRANSITORIAS es un separador que aparece UNA vez y
    divide el documento en dos zonas: "permanente" (antes) y
    "transitorio" (despues).
  - "Articulo primero/segundo/.../octavo.-" (numeracion en palabras)
    tiene DOS roles distintos segun la zona:
      * En la zona permanente: son 3 articulos de la LEY MODIFICATORIA.
        El "Articulo primero" es un envoltorio que dice "Introduzcanse
        las siguientes modificaciones en la ley N 19.628" y le siguen
        Titulos y Articulos NUEVOS (numeracion en digitos) anidados
        adentro. El "Articulo segundo" y "tercero" en cambio NO tienen
        nada anidado: son modificaciones puntuales autocontenidas a
        otras leyes (20.285 y 19.496).
      * En la zona transitoria: cada "Articulo primero/.../octavo" es
        una disposicion transitoria completa en si misma (no envuelve
        nada), asi que se trata igual que un articulo real.
    Por eso el codigo trata CUALQUIER "Articulo <palabra>.-" como el
    cierre de la entrada anterior y el inicio de una entrada nueva
    propia (no solo como un cambio de contexto) -- funciona para los 3
    casos de arriba sin necesitar reglas separadas.
  - "Titulo N" (numero romano) NO es una entrada citable por si sola
    (es solo un encabezado de seccion, sin contenido normativo), asi
    que solo actualiza el contexto ambiente (numero y nombre de titulo)
    para las entradas que le sigan, y no genera su propia entrada.
    Ojo: los titulos NO son correlativos (no existe un "Titulo III"
    nuevo en este documento -- ver justificacion_chunking.md).
  - "Articulo N deg.- Nombre. Cuerpo..." (numeracion en digitos, con
    posible sufijo bis/ter) es el articulo real de fondo: cierra la
    entrada anterior y abre una entrada nueva con todo el contexto
    ambiente vigente (nivel1, ambito, ley_referenciada, titulo).
  - Cualquier parrafo que no matchee ninguno de los patrones anteriores
    se considera un inciso mas de la entrada actualmente abierta (o se
    descarta si todavia no se abrio ninguna entrada, como el bloque de
    titulo/metadata al inicio del documento).
"""

import json
import re

CLEAN_TEXT_PATH = "etapa1_datos/data/interim/02_clean_text.txt"
OUTPUT_PATH = "etapa1_datos/data/processed/articulos_detectados.json"

NIVEL1_WORDS = ["primero", "segundo", "tercero", "cuarto", "quinto", "sexto", "séptimo", "octavo"]

# Formula de cierre que todo Diario Oficial repite despues del ultimo
# articulo/disposicion transitoria: "Habiendose cumplido con lo
# establecido en el N 1 del Articulo 93 de la Constitucion... por
# tanto promulguese...", seguida de firmas y (en este caso) el fallo
# del Tribunal Constitucional. Nada de eso es texto de la ley -- sin
# este corte, se pegaba como incisos del ultimo articulo transitorio.
CIERRE_RE = re.compile(r"^Habi[eé]ndose cumplido")

# Instrucciones de redaccion legislativa a nivel superior, del tipo
# "2) Reemplazase el articulo 1 por el siguiente:", "9) En el articulo
# 17:" o "15) Derogase el Titulo Final.". Son meta-texto (le dicen al
# Diario Oficial que operacion de edicion hacer), no contenido
# normativo de la ley -- y sin reconocerlas, su texto quedaba pegado
# como incisos falsos del ultimo articulo real detectado (paso con
# "Articulo 1 bis", que se inflo con instrucciones que le seguian, y
# con "art-16-sexies", que se quedo pegado con "9) En el articulo
# 17:"). Se identifican por el patron "N) VERBO" o "N) En el articulo"
# al inicio de parrafo -- los items internos de una lista real dentro
# de un articulo (ej. una enumeracion de infracciones) no usan estos
# patrones, asi que no se confunden.
#
# Se reviso el listado completo de instrucciones del documento (16 en
# total) para armar esta lista de verbos; se agregaron "Derogase" y la
# forma plural "Eliminanse" que faltaban en una primera version.
INSTRUCCION_VERBOS = (
    r"Agr[ée]ga(?:se|nse)|Incorp[óo]ra(?:se|nse)|Intercala(?:se|nse)|"
    r"Reempl[áa]za(?:se|nse)|Sustit[úu]ye(?:se|nse)|Supr[íi]me(?:se|nse)|"
    r"Introd[úu]cense|Elim[íi]na(?:se|nse)|Der[oó]ga(?:se|nse)"
)
INSTRUCCION_RE = re.compile(
    r"^\d+\)\s*(?:(?:" + INSTRUCCION_VERBOS + r")|En el art[ií]culo)", re.IGNORECASE
)

TRANSITORIAS_RE = re.compile(r"^DISPOSICIONES TRANSITORIAS$")
NIVEL1_RE = re.compile(r'^"?Art[ií]culo (' + "|".join(NIVEL1_WORDS) + r")\.-\s*(.*)$", re.DOTALL)
TITULO_RE = re.compile(r'^"?T[ií]tulo\s+([IVXLC]+)\b\s*(.*)$', re.DOTALL)
# Sufijos latinos usados para insertar articulos nuevos entre dos ya
# existentes sin tener que renumerar toda la ley (ej. "Articulo 14
# quater.-" va entre el 14 y el 15). Se encontraron los primeros 7 de
# la serie en este documento (bis...nonies); se agrega "decies" por si
# el equipo actualiza el PDF a una version con mas inserciones.
ARTICULO_SUFIJOS = r"bis|ter|qu[aá]ter|quinquies|sexies|septies|octies|nonies|decies"
NIVEL3_RE = re.compile(
    r'^"?Art[ií]culo\s+(\d+)\s*°?\s*(' + ARTICULO_SUFIJOS + r')?\s*\.-\s*(.*)$', re.DOTALL
)
LEY_REF_RE = re.compile(r"ley N[°º]?\s*([\d.]+)", re.IGNORECASE)
NOMBRE_RE = re.compile(r"^([^.]*)\.")


class Parser:
    def __init__(self):
        self.entries = []
        self.current_entry = None
        self.en_transitorias = False
        self.nivel1 = None
        self.ambito = None
        self.ley_referenciada = None
        self.titulo_numero = None
        self.titulo_nombre = None
        self.terminado = False

    def flush(self):
        if self.current_entry is not None:
            self.entries.append(self.current_entry)
        self.current_entry = None

    def handle_transitorias(self):
        self.flush()
        self.en_transitorias = True

    def handle_nivel1(self, match):
        self.flush()
        self.nivel1 = match.group(1)
        self.ambito = "transitorio" if self.en_transitorias else "permanente"
        ley_match = LEY_REF_RE.search(match.group(2))
        self.ley_referenciada = ley_match.group(1) if ley_match else None
        # Un nivel1 nuevo cierra cualquier Titulo que estuviera vigente.
        self.titulo_numero = None
        self.titulo_nombre = None

        prefix = "transitorio" if self.en_transitorias else "nivel1"
        self.current_entry = self._new_entry(
            entry_id=f"{prefix}-{self.nivel1}",
            paragraph=match.string,
            articulo=None,
            articulo_sufijo=None,
            articulo_nombre=None,
        )

    def handle_titulo(self, match):
        self.flush()
        self.titulo_numero = match.group(1)
        self.titulo_nombre = match.group(2).strip()

    def handle_nivel3(self, match):
        self.flush()
        numero, sufijo, resto = match.group(1), match.group(2), match.group(3)
        nombre_match = NOMBRE_RE.match(resto)
        articulo_nombre = nombre_match.group(1).strip() if nombre_match else None

        entry_id = f"art-{numero}" + (f"-{sufijo}" if sufijo else "")
        self.current_entry = self._new_entry(
            entry_id=entry_id,
            paragraph=match.string,
            articulo=numero,
            articulo_sufijo=sufijo,
            articulo_nombre=articulo_nombre,
        )

    def handle_instruccion(self, paragraph):
        """Las instrucciones que terminan en ":" solo anuncian un
        articulo/titulo nuevo que viene citado aparte (ya capturado por
        handle_nivel3/handle_titulo) -- ahi basta con cerrar la entrada
        anterior. Las que NO terminan en ":" llevan su propio cambio
        completo en la misma frase (ej. el cambio de nombre de la ley,
        o "Derogase el Titulo Final.") y no aparecen en ningun otro
        lado del documento -- si no se guardan aqui, se pierden."""
        self.flush()
        if paragraph.rstrip().endswith(":"):
            return
        numero_match = re.match(r"^(\d+)\)", paragraph)
        numero = numero_match.group(1) if numero_match else "0"
        self.current_entry = self._new_entry(
            entry_id=f"instruccion-{numero}",
            paragraph=paragraph,
            articulo=None,
            articulo_sufijo=None,
            articulo_nombre=None,
        )

    def handle_continuation(self, paragraph):
        if self.current_entry is not None:
            self.current_entry["incisos"].append(paragraph)

    def _new_entry(self, entry_id, paragraph, articulo, articulo_sufijo, articulo_nombre):
        return {
            "id": entry_id,
            "nivel1": self.nivel1,
            "ambito": self.ambito,
            "ley_referenciada": self.ley_referenciada,
            "titulo_numero": self.titulo_numero,
            "titulo_nombre": self.titulo_nombre,
            "articulo": articulo,
            "articulo_sufijo": articulo_sufijo,
            "articulo_nombre": articulo_nombre,
            "incisos": [paragraph],
        }

    def feed(self, paragraph):
        if CIERRE_RE.match(paragraph):
            self.flush()
            self.terminado = True
            return
        if INSTRUCCION_RE.match(paragraph):
            self.handle_instruccion(paragraph)
            return
        if TRANSITORIAS_RE.match(paragraph):
            self.handle_transitorias()
            return
        match = NIVEL1_RE.match(paragraph)
        if match:
            self.handle_nivel1(match)
            return
        match = TITULO_RE.match(paragraph)
        if match:
            self.handle_titulo(match)
            return
        match = NIVEL3_RE.match(paragraph)
        if match:
            self.handle_nivel3(match)
            return
        self.handle_continuation(paragraph)

    def parse(self, clean_text):
        for raw_paragraph in clean_text.split("\n\n"):
            if self.terminado:
                break
            paragraph = raw_paragraph.strip()
            if paragraph:
                self.feed(paragraph)
        self.flush()
        return self.entries


def main():
    with open(CLEAN_TEXT_PATH, encoding="utf-8") as f:
        clean_text = f.read()

    entries = Parser().parse(clean_text)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)

    nivel1_count = sum(1 for e in entries if e["articulo"] is None)
    articulo_count = sum(1 for e in entries if e["articulo"] is not None)
    titulos = sorted({e["titulo_numero"] for e in entries if e["titulo_numero"]})

    print(f"Entradas totales: {len(entries)}")
    print(f"  - nivel1 (Articulo primero/segundo/...): {nivel1_count}")
    print(f"  - articulos reales (Articulo N deg.-): {articulo_count}")
    print(f"Titulos detectados: {titulos}")
    print(f"Guardado en {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
