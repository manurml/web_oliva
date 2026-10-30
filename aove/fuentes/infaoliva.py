"""InfaOliva: noticias de 'Actualidad' y tabla diaria de precios en origen de su portada.

No se usa su endpoint /funciones/ajax.php porque su robots.txt lo excluye; el
histórico de precios se construye guardando la tabla de cada día.
"""
import re
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from aove.modelos import Noticia, Precio
from aove.red import descargar

BASE = "https://www.infaoliva.com/"
FUENTE = "InfaOliva"
LISTADOS = ["actualidad/", "actualidad/articulos-de-opinion/", "actualidad/jornadas-y-eventos/",
            "actualidad/premios/", "actualidad/ferias/"]
MESES = {m: i for i, m in enumerate(
    "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split(), 1)}
_FECHA_TITULO = re.compile(r"^\s*(\d{1,2})\s+(?:de\s+)?([a-záéíóú]+)\s+(?:de\s+)?(\d{4})\s*$", re.I)


def _separar_fecha(h3) -> tuple[str, str]:
    """Las tarjetas suelen ser '16 octubre 2025<br>Título'. Devuelve (fecha ISO o '', título)."""
    partes = [p.strip() for p in h3.get_text("\n").split("\n") if p.strip()]
    if len(partes) > 1 and (m := _FECHA_TITULO.match(partes[0])) and m.group(2).lower() in MESES:
        f = date(int(m.group(3)), MESES[m.group(2).lower()], int(m.group(1)))
        return f.isoformat(), " ".join(partes[1:])
    return "", " ".join(partes)


def enlaces_noticias() -> list[tuple[str, str, str]]:
    """(url, título, fecha) de las entradas en HTML de 'Actualidad' (se omiten los PDF)."""
    vistos: dict[str, tuple[str, str, str]] = {}
    for listado in LISTADOS:
        sopa = BeautifulSoup(descargar(BASE + listado), "lxml")
        _recoger(sopa, vistos)
    return list(vistos.values())


def _recoger(sopa, vistos: dict) -> None:
    for a in sopa.select("article a[href]"):
        href = a["href"]
        h3 = a.find("h3")
        if not h3 or not href.endswith(".html") or "actualidad/" not in href:
            continue
        url = urljoin(BASE, href)
        fecha, titulo = _separar_fecha(h3)
        vistos.setdefault(url, (url, titulo, fecha))


def leer_noticia(url: str, titulo: str, fecha: str, orden: int) -> Noticia | None:
    sopa = BeautifulSoup(descargar(url), "lxml")
    cuerpo = sopa.select_one("article")
    if not cuerpo:
        return None
    h1 = cuerpo.find("h1")
    texto = "\n\n".join(t.get_text(" ", strip=True) for t in cuerpo.find_all(["h2", "h3", "p", "li", "blockquote"]))
    texto = texto.replace("Volver", "").strip()
    if len(texto) < 200:
        return None
    return Noticia(
        url=url,
        fuente=FUENTE,
        titulo=h1.get_text(" ", strip=True) if h1 else titulo,
        fecha=fecha,
        resumen="",
        texto=texto,
        orden=orden,
    )


def _numero(txt: str) -> float | None:
    m = re.search(r"\d+(?:[.,]\d+)*", txt)
    if not m:
        return None
    n = m.group(0)
    # InfaOliva publica '2.800 €' (€/t con punto de miles) o '4,108' (€/kg)
    if re.fullmatch(r"\d{1,2}\.\d{3}", n):
        return round(float(n.replace(".", "")) / 1000, 3)
    return round(float(n.replace(".", "").replace(",", ".")), 3)


def precios() -> list[Precio]:
    sopa = BeautifulSoup(descargar(BASE), "lxml")
    bloque = sopa.select_one("#observatorio")
    if not bloque:
        return []
    fecha_txt = bloque.select_one("p.small strong")
    if not fecha_txt or not (m := re.search(r"(\d{2})/(\d{2})/(\d{4})", fecha_txt.get_text())):
        return []
    fecha = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    resultado = []
    for fila in bloque.select("table tbody tr"):
        celdas = [c.get_text(" ", strip=True) for c in fila.find_all("td")]
        if len(celdas) < 3:
            continue
        categoria, variedad, valor = celdas[:3]
        tipo = categoria.replace("Aceite de oliva virgen", "Virgen").replace("Aceite de oliva lampante", "Lampante")
        eur = _numero(valor)
        resultado.append(Precio(FUENTE, f"Origen ({variedad})", tipo, fecha, eur, "" if eur else valor))
    return resultado
