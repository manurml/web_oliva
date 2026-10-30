"""Selección de las mejores noticias y redacción de artículos originales con Claude."""
import logging
import os
from typing import Literal

import anthropic
from pydantic import BaseModel

import config
from aove.modelos import Noticia

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
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def _cliente() -> anthropic.Anthropic:
    return anthropic.Anthropic(max_retries=4)


def _pedir(contenido: str, formato: type[BaseModel], esfuerzo: str):
    r = _cliente().beta.messages.parse(
        model=config.MODELO_CLAUDE,
        max_tokens=16000,
        system=SISTEMA,
        messages=[{"role": "user", "content": contenido}],
        output_config={"effort": esfuerzo},
        output_format=formato,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if r.stop_reason == "refusal" or r.parsed_output is None:
        raise RuntimeError(f"Claude no devolvió resultado (stop_reason={r.stop_reason})")
    return r.parsed_output


def elegir(candidatas: list[Noticia], n: int) -> list[Noticia]:
    """Pide a Claude las n noticias más relevantes. Sin clave de API, elige las más recientes."""
    if len(candidatas) <= n:
        return candidatas
    por_fecha = sorted(candidatas, key=lambda c: (c.fecha, -c.orden), reverse=True)
    if not disponible():
        return por_fecha[:n]
    listado = "\n\n".join(
        f"[{i}] {c.fuente} · {c.fecha}\nTítulo: {c.titulo}\nResumen: {c.resumen or 'no disponible'}"
        for i, c in enumerate(por_fecha)
    )
    sel = _pedir(
        f"""Estas son las noticias candidatas de hoy, recogidas de InfaOliva y Oleista:

{listado}

Elige las {n} noticias más valiosas para publicar hoy. Prioriza: actualidad e impacto en el mercado y los precios del AOVE, novedad (no contenido atemporal tipo guía o receta), utilidad para el profesional del sector, y variedad (si hay dos de calidad parecida, mejor de fuentes o temas distintos).
Devuelve sus números en "ids" (exactamente {n}) y en "motivo" una frase breve.""",
        Seleccion,
        "low",
    )
    elegidas = [por_fecha[i] for i in dict.fromkeys(sel.ids) if 0 <= i < len(por_fecha)][:n]
    log.info("Selección de Claude: %s (%s)", [e.titulo for e in elegidas], sel.motivo)
    return elegidas or por_fecha[:n]


def redactar(noticia: Noticia) -> Articulo:
    return _pedir(
        f"""{REGLAS_REDACCION.format(fuente=noticia.fuente)}

Fuente: {noticia.fuente}
Fecha de la noticia original: {noticia.fecha}
Título original: {noticia.titulo}

Texto original:
<<<
{noticia.texto}
>>>""",
        Articulo,
        "high",
    )


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
