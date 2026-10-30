"""Convierte la respuesta de Gemini al formato de datos/articulos y la guarda."""
import re
import unicodedata
from datetime import date

from aove import almacen
from services.agent_aove.contexto import Contexto
from services.agent_aove.gemini import ArticuloGemini

TIPO = "analisis"
URL_PRECIOS = "https://oleista.com/es/precios"


def ya_publicado(hoy: date) -> bool:
    return any(a.get("tipo") == TIPO and a["fecha_publicacion"] == hoy.isoformat() for a in almacen.cargar_articulos())


def _slug(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:80]


def _bloques(markdown: str) -> list[dict]:
    """Las plantillas pintan subtítulos y párrafos como texto, sin interpretar HTML."""
    bloques = []
    for parte in re.split(r"\n\s*\n", markdown.strip()):
        for linea in parte.splitlines() if parte.lstrip().startswith("#") else [" ".join(parte.split())]:
            linea = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", linea).replace("**", "").replace("__", "").strip()
            if not linea:
                continue
            if linea.startswith("#"):
                bloques.append({"tipo": "subtitulo", "texto": linea.lstrip("# ")})
            else:
                bloques.append({"tipo": "parrafo", "texto": linea})
    return bloques


def guardar(articulo: ArticuloGemini, datos: Contexto, hoy: date, estado: str) -> dict:
    base = nombre = f"{hoy.isoformat()}-{_slug(articulo.slug or articulo.titulo)}"
    n = 2
    while (almacen.ARTICULOS / f"{nombre}.json").exists():
        nombre, n = f"{base}-{n}", n + 1
    registro = {
        "slug": nombre,
        "tipo": TIPO,
        "estado": estado,
        "fecha_publicacion": hoy.isoformat(),
        "redactado_con_ia": True,
        "titulo": articulo.titulo,
        "entradilla": articulo.resumen,
        "meta_descripcion": articulo.meta_descripcion,
        "contenido_markdown": articulo.contenido_markdown,
        "bloques": _bloques(articulo.contenido_markdown),
        "claves": [],
        "etiquetas": articulo.etiquetas,
        "fuente": {"nombre": "Oleista", "url": URL_PRECIOS, "titulo": "Cotizaciones del aceite de oliva", "fecha": datos.fecha_precios},
    }
    almacen.guardar_articulo(registro)
    return registro
