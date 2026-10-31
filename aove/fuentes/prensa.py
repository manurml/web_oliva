"""Noticias de la prensa especializada: Mercacei, Olimerca y Óleo Revista.

Sus avisos legales restringen la reproducción y no hay permiso expreso: es una decisión del dueño del proyecto.
Por eso solo sirven de materia prima para artículos propios que las citan y enlazan, y nunca se publican como fichas.
"""
import json
import re
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from aove.modelos import Noticia
from aove.red import descargar

MINIMO_TEXTO = 200
MESES = {m: i for i, m in enumerate("enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split(), 1)}


def _fecha_texto(texto: str) -> str:
    if m := re.search(r"(\d{1,2}) de ([a-z]+) de (\d{4})", texto.lower()):
        if m.group(2) in MESES:
            return date(int(m.group(3)), MESES[m.group(2)], int(m.group(1))).isoformat()
    if m := re.search(r"\b(\d{2})[./](\d{2})[./](\d{4})\b", texto):
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
    return ""


def _enlaces(portada: str, patron: str) -> list[str]:
    sopa = BeautifulSoup(descargar(portada), "lxml")
    urls = (urljoin(portada, a["href"]) for a in sopa.select("a[href]"))
    return list(dict.fromkeys(u for u in urls if re.match(patron, u)))


def _noticia(url, fuente, titulo, fecha, resumen, texto, orden) -> Noticia | None:
    """Sin título, fecha o texto suficiente no hay artículo fiable que escribir."""
    if not titulo or not fecha or len(texto) < MINIMO_TEXTO:
        return None
    return Noticia(url=url, fuente=fuente, titulo=titulo, fecha=fecha, resumen=resumen, texto=texto, orden=orden)


def _parrafos(nodo) -> str:
    return "\n\n".join(t for t in (p.get_text(" ", strip=True) for p in nodo.find_all(["h2", "h3", "p", "li"])) if t)


def _texto_de(sopa, selector: str) -> str:
    nodo = sopa.select_one(selector)
    return nodo.get_text(" ", strip=True) if nodo else ""


def _enlaces_mercacei() -> list[str]:
    return _enlaces("https://www.mercacei.com/", r"https://www\.mercacei\.com/noticia/\d+/")


def _leer_mercacei(url: str, orden: int) -> Noticia | None:
    sopa = BeautifulSoup(descargar(url), "lxml")
    cuerpo = sopa.select_one(".dentroNoticia")
    if not cuerpo:
        return None
    entradilla = _texto_de(sopa, ".entradilla")
    return _noticia(url, "Mercacei", _texto_de(sopa, "h1"), _fecha_texto(_texto_de(sopa, ".fecha_publicacion")), entradilla, _parrafos(cuerpo), orden)


def _enlaces_olimerca() -> list[str]:
    return _enlaces("https://www.olimerca.com/", r"https://www\.olimerca\.com/noticiadet/")


def _leer_olimerca(url: str, orden: int) -> Noticia | None:
    sopa = BeautifulSoup(descargar(url), "lxml")
    cuerpo = sopa.select_one(".article-body")
    if not cuerpo:
        return None
    return _noticia(url, "Olimerca", _texto_de(sopa, "h1"), _fecha_texto(_texto_de(sopa, ".article-header")), "", _parrafos(cuerpo) or cuerpo.get_text(" ", strip=True), orden)


def _enlaces_oleo() -> list[str]:
    feed = BeautifulSoup(descargar("https://www.oleorevista.com/feed/all"), "xml")
    return list(dict.fromkeys(i.link.get_text(strip=True) for i in feed.find_all("item") if i.link))


def _titular_ld(sopa) -> str:
    """En Óleo Revista el h1 es el nombre de la web: el titular está en sus datos estructurados."""
    for s in sopa.select('script[type="application/ld+json"]'):
        try:
            datos = json.loads(s.string or "")
        except json.JSONDecodeError:
            continue
        for nodo in datos if isinstance(datos, list) else [datos]:
            if isinstance(nodo, dict) and nodo.get("headline"):
                return nodo["headline"]
    return ""


def _leer_oleo(url: str, orden: int) -> Noticia | None:
    sopa = BeautifulSoup(descargar(url), "lxml")
    cuerpo = sopa.select_one(".article_content")
    if not cuerpo:
        return None
    return _noticia(url, "Óleo Revista", _titular_ld(sopa), _fecha_texto(_texto_de(sopa, ".article-info-wrapper")),
                    _texto_de(sopa, ".article_subtitle"), _parrafos(cuerpo) or cuerpo.get_text(" ", strip=True), orden)


FUENTES = {
    "Mercacei": (_enlaces_mercacei, _leer_mercacei),
    "Olimerca": (_enlaces_olimerca, _leer_olimerca),
    "Óleo Revista": (_enlaces_oleo, _leer_oleo),
}
