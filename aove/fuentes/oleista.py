"""Oleista: noticias (blog y análisis de mercado) y precios diarios en origen."""
import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from aove.modelos import Noticia, Precio
from aove.red import descargar

BASE = "https://oleista.com"
PORTADA = BASE + "/es"
PRECIOS = BASE + "/es/precios"
FUENTE = "Oleista"

REGIONES = {"Spain": "España", "Andalucia": "Andalucía", "Italy": "Italia", "Greece": "Grecia"}
TIPOS = {
    "aceite de oliva virgen extra": "AOVE",
    "aceite de oliva virgen": "Virgen",
    "lampante": "Lampante",
}


def enlaces_noticias() -> list[str]:
    """URLs de artículos enlazados desde la portada, en el orden en que aparecen."""
    sopa = BeautifulSoup(descargar(PORTADA), "lxml")
    vistos: list[str] = []
    for a in sopa.select("a[href]"):
        href = a["href"]
        if re.match(r"^/es/(blog|mercado)/[^/?#]+$", href):
            url = urljoin(BASE, href)
            if url not in vistos:
                vistos.append(url)
    return vistos


def leer_noticia(url: str, orden: int) -> Noticia | None:
    sopa = BeautifulSoup(descargar(url), "lxml")
    articulo = {}
    for s in sopa.select('script[type="application/ld+json"]'):
        try:
            datos = json.loads(s.string or "")
        except json.JSONDecodeError:
            continue
        for nodo in datos if isinstance(datos, list) else datos.get("@graph", [datos]):
            if isinstance(nodo, dict) and nodo.get("@type") in ("Article", "NewsArticle", "BlogPosting"):
                articulo = nodo
    h1 = sopa.find("h1")
    titulo = articulo.get("headline") or (h1.get_text(" ", strip=True) if h1 else "")
    cuerpo = sopa.select_one(".art-body") or sopa.select_one(".blogArticle")
    if not titulo or not cuerpo:
        return None
    texto = "\n\n".join(t.get_text(" ", strip=True) for t in cuerpo.find_all(["h2", "h3", "p", "li"]))
    meta = sopa.find("meta", attrs={"name": "description"})
    return Noticia(
        url=url,
        fuente=FUENTE,
        titulo=titulo,
        fecha=(articulo.get("datePublished") or "")[:10],
        resumen=meta["content"] if meta and meta.get("content") else "",
        texto=texto,
        orden=orden,
    )


_SERIE = re.compile(r"var priceData\d+=JSON\.parse\('(\[.*?\])'\);seriesData\.push\(\{name:'([^']+)'")
_GRAFICO = re.compile(r'querySelector\("#combinedChart(\w+)"\)')


def precios() -> list[Precio]:
    """Series diarias (~3 meses) de AOVE, Virgen y Lampante por región. Valores en €/t -> €/kg."""
    sopa = BeautifulSoup(descargar(PRECIOS), "lxml")
    resultado: list[Precio] = []
    for script in sopa.find_all("script"):
        codigo = script.string or ""
        grafico = _GRAFICO.search(codigo)
        if not grafico:
            continue
        region = REGIONES.get(grafico.group(1), grafico.group(1))
        for puntos, nombre in _SERIE.findall(codigo):
            tipo = TIPOS.get(nombre.strip().lower(), nombre)
            for p in json.loads(puntos):
                resultado.append(Precio(FUENTE, region, tipo, p["x"], round(float(p["y"]) / 1000, 3)))
    return resultado
