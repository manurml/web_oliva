"""Persistencia en ficheros JSON dentro de datos/ (se versionan con git: son el histórico)."""
import json
from datetime import date, timedelta
from pathlib import Path

import config
from aove.modelos import Noticia, Precio

PRECIOS = config.DATOS / "precios.json"
VISTOS = config.DATOS / "noticias_vistas.json"
ARTICULOS = config.DATOS / "articulos"


def _leer(ruta: Path, defecto):
    if ruta.exists():
        return json.loads(ruta.read_text(encoding="utf-8"))
    return defecto


def _escribir(ruta: Path, datos) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")


# ---------- Precios ----------
# Estructura: {"Oleista|España|AOVE": {"fuente":..,"region":..,"tipo":..,"puntos":{"2026-10-22": 3.138}, "notas": {...}}}

def cargar_precios() -> dict:
    return _leer(PRECIOS, {})


def guardar_precios(precios: list[Precio]) -> int:
    series = cargar_precios()
    """Guarda los precios y devuelve cuántos son nuevos o corregidos respecto a lo guardado."""
    cambios = 0
    for p in precios:
        clave = f"{p.fuente}|{p.region}|{p.tipo}"
        s = series.setdefault(clave, {"fuente": p.fuente, "region": p.region, "tipo": p.tipo, "puntos": {}, "notas": {}})
        if p.eur_kg is None:
            s["notas"][p.fecha] = p.nota
            continue
        if s["puntos"].get(p.fecha) != p.eur_kg:
            cambios += 1
            s["puntos"][p.fecha] = p.eur_kg
            s["notas"].pop(p.fecha, None)
    _escribir(PRECIOS, series)
    return cambios


# ---------- Noticias ----------
# {url: {"estado": "candidata"|"antigua"|"descartada"|"publicada", "noticia": {...}}}

def cargar_vistas() -> dict:
    return _leer(VISTOS, {})


def guardar_vistas(vistas: dict) -> None:
    # Este fichero se publica en el repositorio: nunca guarda el texto de las fuentes.
    # Se descarga de nuevo al redactar (diario._con_texto).
    limite = (date.today() - timedelta(days=config.DIAS_MAX_ANTIGUEDAD)).isoformat()
    for v in vistas.values():
        if v["estado"] == "candidata" and v["noticia"]["fecha"] < limite:
            v["estado"] = "antigua"
        v["noticia"]["texto"] = ""
    _escribir(VISTOS, vistas)


def candidatas(vistas: dict, desde: str) -> list[Noticia]:
    return [Noticia(**v["noticia"]) for v in vistas.values()
            if v["estado"] == "candidata" and v["noticia"]["fecha"] >= desde]


# ---------- Artículos publicados ----------

def guardar_articulo(articulo: dict) -> None:
    _escribir(ARTICULOS / f"{articulo['slug']}.json", articulo)


def cargar_articulos() -> list[dict]:
    if not ARTICULOS.exists():
        return []
    arts = [json.loads(p.read_text(encoding="utf-8")) for p in ARTICULOS.glob("*.json")]
    return sorted(arts, key=lambda a: (a["fecha_publicacion"], a["slug"]), reverse=True)
