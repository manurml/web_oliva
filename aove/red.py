"""Descargas educadas: respeta robots.txt, identifica al bot y espacia las peticiones."""
import time
import urllib.robotparser
from urllib.parse import urlsplit, quote, urlunsplit

import requests
import truststore

import config

# Valida certificados con el almacén del sistema: el de Python no reconoce el del MAPA.
truststore.inject_into_ssl()

_sesion = requests.Session()
_sesion.headers.update({"User-Agent": config.USER_AGENT, "Accept-Language": "es-ES,es;q=0.9"})
_robots: dict[str, urllib.robotparser.RobotFileParser] = {}
_ultima_peticion = 0.0


class BloqueadoPorRobots(Exception):
    pass


def normalizar(url: str) -> str:
    """Codifica caracteres raros de la ruta (InfaOliva usa '<br>' y ':' en sus URLs)."""
    p = urlsplit(url)
    return urlunsplit((p.scheme, p.netloc, quote(p.path, safe="/%-._~"), p.query, ""))


def _permitido(url: str) -> bool:
    p = urlsplit(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = _sesion.get(base + "/robots.txt", timeout=config.TIMEOUT)
            rp.parse(r.text.splitlines() if r.ok else [])
        except requests.RequestException:
            rp.parse([])
        _robots[base] = rp
    return _robots[base].can_fetch(config.USER_AGENT, url)


def _pedir(url: str) -> requests.Response:
    global _ultima_peticion
    url = normalizar(url)
    if not _permitido(url):
        raise BloqueadoPorRobots(url)
    espera = config.PAUSA_ENTRE_PETICIONES - (time.monotonic() - _ultima_peticion)
    if espera > 0:
        time.sleep(espera)
    r = _sesion.get(url, timeout=config.TIMEOUT)
    _ultima_peticion = time.monotonic()
    r.raise_for_status()
    return r


def descargar_bytes(url: str) -> bytes:
    return _pedir(url).content


def descargar(url: str) -> str:
    r = _pedir(url)
    r.encoding = r.apparent_encoding if not r.encoding or r.encoding.lower() == "iso-8859-1" else r.encoding
    return r.text
