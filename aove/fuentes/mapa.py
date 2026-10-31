"""Boletín semanal del Ministerio de Agricultura (PDF). Su aviso legal permite reutilizarlo citando la fuente y la fecha."""
import io
import re
from datetime import date

from bs4 import BeautifulSoup
from pypdf import PdfReader

from aove.modelos import Precio
from aove.red import descargar, descargar_bytes

FUENTE = "MAPA"
RSS = "https://www.mapa.gob.es/es/agricultura/temas/producciones-agricolas/aceite-oliva-y-aceituna-mesa/evolucion_precios_ao_vegetales/rssboletinsemanaldepreciosdeaceitedeoliva"
# El PDF desordena las etiquetas al extraer el texto: las tablas se identifican por su posición y se validan.
TIPOS = ["AOVE", "Virgen", "Lampante"]
SIGLAS = {"AOVE": "AOVE", "AOV": "Virgen", "AOL": "Lampante"}
NACIONALES = {"AOVE": "virgen extra (AOVE)", "Virgen": "virgen (AOV)", "Lampante": "lampante (AOL)"}
REGIONES = {"Andalucía": "Andalucía", "Castilla-La Mancha": "Castilla-La Mancha", "Cataluña": "Cataluña", "Extremadura": "Extremadura", "ESPAÑA": "España"}
_FILA = re.compile(r"^(Andalucía|Castilla-La Mancha|Cataluña|Extremadura|ESPAÑA) ((?:[\d.,]+ ){4}[\d.,]+) ", re.M)
_INTERNACIONAL = re.compile(r"^(AOVE|AOV|AOL|AOR) (s/c|[\d.,]+)\b", re.M)
# Italia, Grecia, Portugal y Túnez, en este orden: si cambia, no se puede saber de qué país es cada fila.
FORMA_INTERNACIONAL = [("Italia", "AOVE"), ("Italia", "AOV"), ("Italia", "AOL"), ("Italia", "AOR"), ("Grecia", "AOVE"), ("Grecia", "AOV"),
                       ("Grecia", "AOL"), ("Portugal", "AOVE"), ("Túnez", "AOVE"), ("Túnez", "AOL")]


def _numero(texto: str) -> float:
    return float(texto.replace(".", "").replace(",", "."))


def _domingo(semana: str) -> str:
    """'2026/43' -> último día de esa semana. El boletín numera las semanas como la ISO; sus fechas escritas traen erratas."""
    anio, numero = semana.split("/")
    return date.fromisocalendar(int(anio), int(numero), 7).isoformat()


def _pagina(paginas: list[str], *textos: str) -> str:
    for p in paginas:
        if all(t in p for t in textos):
            return p
    raise ValueError(f"El boletín no trae una página con {textos}")


def leer_regiones(paginas: list[str]) -> list[Precio]:
    """Últimas 5 semanas de España y sus comunidades, comprobadas con la tabla nacional del propio boletín."""
    texto = _pagina(paginas, "PRECIOS CCAA", "Últimas 5 Semanas")
    semanas = re.search(r"(\d{4}/\d{2}) (\d{4}/\d{2}) (\d{4}/\d{2}) (\d{4}/\d{2}) (\d{4}/\d{2})", texto)
    if not semanas:
        raise ValueError("El boletín no indica las semanas")
    nacional = _pagina(paginas, "PRECIOS NACIONALES", "Aceite de oliva virgen extra (AOVE)")
    resultado: list[Precio] = []
    indice = 0
    for nombre, valores in _FILA.findall(texto):
        if indice >= len(TIPOS):
            raise ValueError("El boletín trae más tablas de las esperadas")
        tipo = TIPOS[indice]
        numeros = [_numero(v) for v in valores.split()]
        resultado += [Precio(FUENTE, REGIONES[nombre], tipo, _domingo(s), round(v / 100, 4)) for s, v in zip(semanas.groups(), numeros)]
        if nombre == "ESPAÑA":
            if not re.search(rf"{re.escape(NACIONALES[tipo])} [\d.,]+ {re.escape(valores.split()[-1])} ", nacional):
                raise ValueError(f"{tipo}: la tabla regional no coincide con la nacional")
            indice += 1
    if indice != len(TIPOS):
        raise ValueError(f"Se esperaban {len(TIPOS)} tablas y hay {indice}")
    return resultado


def leer_internacional(paginas: list[str]) -> list[Precio]:
    texto = _pagina(paginas, "INTERNACIONALES", "Última Semana publicada")
    semana = re.search(r"SEMANA (\d{1,2})/(\d{4})", texto)
    filas = _INTERNACIONAL.findall(texto)
    if not semana or [f[0] for f in filas] != [s for _, s in FORMA_INTERNACIONAL]:
        raise ValueError("Ha cambiado la tabla internacional del boletín")
    fecha = _domingo(f"{semana.group(2)}/{semana.group(1)}")
    resultado = []
    for (pais, sigla), (_, valor) in zip(FORMA_INTERNACIONAL, filas):
        if sigla in SIGLAS:
            sin_dato = valor == "s/c"
            resultado.append(Precio(FUENTE, pais, SIGLAS[sigla], fecha, None if sin_dato else round(_numero(valor) / 100, 4), "Sin cotización" if sin_dato else ""))
    return resultado


def enlace_boletin() -> str:
    enlace = BeautifulSoup(descargar(RSS), "xml").select_one("item link")
    if not enlace:
        raise ValueError("El RSS del MAPA no trae ningún boletín")
    return enlace.get_text(strip=True)


def precios() -> list[Precio]:
    lector = PdfReader(io.BytesIO(descargar_bytes(enlace_boletin())))
    paginas = [p.extract_text() or "" for p in lector.pages]
    return leer_regiones(paginas) + leer_internacional(paginas)
