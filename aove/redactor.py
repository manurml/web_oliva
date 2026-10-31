"""Selección de las mejores noticias y redacción de artículos originales con Gemini."""
import logging
import os
from typing import Literal

from pydantic import BaseModel

from aove.modelos import Noticia
from aove.web import fecha_larga
from services.agent_aove import gemini

log = logging.getLogger(__name__)

SISTEMA = """Eres el redactor jefe de una web española de información sobre el sector del aceite de oliva virgen extra (AOVE), dirigida a agricultores, almazaras, cooperativas, envasadores y profesionales del sector.

Escribes en español de España, con estilo periodístico claro, riguroso y cercano."""

REGLAS_REDACCION = """Normas obligatorias:
- Escribe un artículo ORIGINAL con tus propias palabras y tu propia estructura. No copies frases de la fuente ni parafrasees párrafo a párrafo; sintetiza, ordena y aporta contexto.
- Usa solo datos que aparezcan en la fuente. No inventes cifras, fechas, nombres ni citas. Si algo es una estimación u opinión de la fuente, dilo.
- Cita la fuente de forma natural en el texto (p. ej. "según recoge {fuente}").
- Extensión: 450-700 palabras, en 4-7 párrafos con 2-3 subtítulos.
- Titular informativo de menos de 90 caracteres, sin clickbait. Entradilla de 1-2 frases.
- 3 claves breves (una línea cada una) con lo esencial para el lector profesional.
- 2-4 etiquetas temáticas cortas en minúscula (p. ej. "precios", "campaña 2026/27", "mercado")."""


class Seleccion(BaseModel):
    ids: list[int]
    motivo: str


class Bloque(BaseModel):
    tipo: Literal["subtitulo", "parrafo"]
    texto: str


class Articulo(BaseModel):
    titulo: str
    entradilla: str
    claves: list[str]
    bloques: list[Bloque]
    etiquetas: list[str]


def disponible() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY"))


def elegir(candidatas: list[Noticia], n: int) -> list[Noticia]:
    """Pide a Gemini las n noticias más relevantes. Sin clave de API o si falla, elige las más recientes."""
    if len(candidatas) <= n:
        return candidatas
    por_fecha = sorted(candidatas, key=lambda c: (c.fecha, -c.orden), reverse=True)
    if not disponible():
        return por_fecha[:n]
    listado = "\n\n".join(
        f"[{i}] {c.fuente} · {c.fecha}\nTítulo: {c.titulo}\nResumen: {c.resumen or 'no disponible'}"
        for i, c in enumerate(por_fecha)
    )
    try:
        sel, _ = gemini.pedir(
            f"""Estas son las noticias candidatas de hoy, recogidas de InfaOliva y Oleista:

{listado}

Elige las {n} noticias más valiosas para publicar hoy. Prioriza: actualidad e impacto en el mercado y los precios del AOVE, novedad (no contenido atemporal tipo guía o receta), utilidad para el profesional del sector, y variedad (si hay dos de calidad parecida, mejor de fuentes o temas distintos).
Devuelve sus números en "ids" (exactamente {n}) y en "motivo" una frase breve.""",
            SISTEMA,
            Seleccion,
        )
    except gemini.ErrorGemini as e:
        log.warning("No se pudo seleccionar con Gemini; se usan las más recientes: %s", e)
        return por_fecha[:n]
    elegidas = [por_fecha[i] for i in dict.fromkeys(sel.ids) if 0 <= i < len(por_fecha)][:n]
    log.info("Selección de Gemini: %s (%s)", [e.titulo for e in elegidas], sel.motivo)
    return elegidas or por_fecha[:n]


def redactar(noticia: Noticia) -> Articulo:
    """Si quedan cifras o fechas que no están en la fuente, falla: la noticia sigue candidata y no se publica."""
    fuente = f"""Fuente: {noticia.fuente}
Fecha de la noticia original: {fecha_larga(noticia.fecha)}
Título original: {noticia.titulo}

Texto original:
<<<
{noticia.texto}
>>>"""

    def comprobar(a: Articulo) -> set[str]:
        salida = " ".join([a.titulo, a.entradilla, *a.claves, *(b.texto for b in a.bloques)])
        return gemini.sin_respaldo_en(salida, fuente)

    articulo, sin_respaldo = gemini.pedir(f"{REGLAS_REDACCION.format(fuente=noticia.fuente)}\n\n{fuente}", SISTEMA, Articulo, comprobar)
    if sin_respaldo:
        raise gemini.ErrorGemini(f"Cifras o fechas que no están en la fuente: {sin_respaldo}")
    return articulo


def breve_sin_ia(noticia: Noticia) -> Articulo:
    """Alternativa sin clave de API: ficha breve con el resumen que ofrece la propia fuente y enlace."""
    resumen = noticia.resumen or noticia.texto.split("\n\n")[0][:280]
    return Articulo(
        titulo=noticia.titulo,
        entradilla=resumen,
        claves=[],
        bloques=[Bloque(tipo="parrafo", texto=f"{noticia.fuente} publica esta información. Consulta el artículo completo en la fuente original.")],
        etiquetas=["breve"],
    )
