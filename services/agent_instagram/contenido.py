"""Decide de qué hablar y pide a Gemini los textos. Las cifras de las imágenes salen de los datos, no de Gemini."""
import re
from datetime import date, timedelta

from pydantic import BaseModel, field_validator

from aove import almacen
from services.agent_aove import contexto, gemini

SISTEMA = """Eres community manager de "AOVE al Día", una cuenta de Instagram sobre el mercado del aceite de oliva virgen extra para agricultores, almazaras, cooperativas y profesionales. Escribes en español de España: cercano, claro y riguroso, nunca sensacionalista.

Reglas obligatorias:
- Usa solo cifras, fechas y hechos del contexto. No inventes ni estimes nada y no calcules cifras nuevas.
- Di siempre a qué fecha corresponde un precio. No digas "hoy" ni "ayer" para un precio: usa su fecha.
- No atribuyas causas a un movimiento de precios salvo que el contexto las indique.
- No des recomendaciones de compra o venta ni predigas precios.
- Cita la fuente de cada precio que uses: Oleista o, para la referencia semanal, el Ministerio de Agricultura con su semana. No copies frases de las noticias.
- Evita frases vacías y clickbait ("no vas a creer", "atención"). Escribe "una caída del 1,7 %", no "del -1,7 %".
- Nada de negritas ni markdown: Instagram no los muestra.

Campos:
- "gancho": titular de la portada del carrusel, 25-60 caracteres. Incluye una cifra concreta del contexto y dice qué ha pasado, no de qué trata (bien: "El virgen extra cede un 6,5 % en un mes"; mal: "Nuevos precios en origen").
- "texto": pie de la publicación, 400-900 caracteres. No es un resumen ni repite el artículo: cuenta una sola idea, la más interesante del día, con 2 o 3 datos como máximo (las imágenes ya traen las tablas). La primera línea engancha por sí sola (menos de 110 caracteres, es lo que se ve sin pulsar "más") y lleva un dato. Después, párrafos de 1-2 frases separados por una línea en blanco. Cierra con una pregunta concreta al lector y con "Más datos en el enlace de la biografía". Máximo 3 emojis, sobrios. Sin hashtags ni enlaces.
- "hashtags": 3-5 hashtags en español, específicos del aceite de oliva y del tema del día.
- "noticia_titulo": la noticia del día en menos de 70 caracteres. Vacío si el contexto no trae NOTICIA DEL DÍA.
- "noticia_puntos": 2-3 ideas de la noticia, cada una de menos de 110 caracteres. Vacío si no hay noticia.
- "encuesta_pregunta": pregunta para el sector que se responda con la encuesta de las historias, menos de 80 caracteres. Sobre experiencia u opinión, no sobre comprar o vender.
- "encuesta_opciones": exactamente 2 respuestas de menos de 20 caracteres."""


class Textos(BaseModel):
    gancho: str
    texto: str
    hashtags: list[str]
    noticia_titulo: str
    noticia_puntos: list[str]
    encuesta_pregunta: str
    encuesta_opciones: list[str]

    @field_validator("hashtags")
    @classmethod
    def _con_almohadilla(cls, valores: list[str]) -> list[str]:
        return [f"#{v.strip().lstrip('#')}" for v in valores]

    @field_validator("encuesta_pregunta")
    @classmethod
    def _con_interrogacion(cls, valor: str) -> str:
        valor = valor.strip()
        return valor if valor.startswith("¿") or "?" not in valor else f"¿{valor}"


def elegir_articulo(hoy: date, usados: list[str]) -> dict | None:
    """Solo artículos propios y redactados: las fichas breves repiten el resumen de la fuente. Prefiere noticias al análisis."""
    desde = (hoy - timedelta(days=2)).isoformat()
    aptos = [a for a in almacen.cargar_articulos()
             if a.get("redactado_con_ia") and a.get("estado", "published") == "published"
             and a["fecha_publicacion"] >= desde and a["slug"] not in usados]
    return next((a for a in aptos if a.get("tipo") != "analisis"), aptos[0] if aptos else None)


def preparar_contexto(hoy: date, articulo: dict | None) -> str:
    texto = contexto.recopilar(hoy).texto
    if not texto or not articulo:
        return texto
    cuerpo = "\n".join(b["texto"] for b in articulo.get("bloques", []))[:5000]
    return f"{texto}\n\nNOTICIA DEL DÍA\nTítulo: {articulo['titulo']}\nEntradilla: {articulo.get('entradilla', '')}\n{cuerpo}"


def _problemas(t: Textos, datos: str, con_noticia: bool) -> set[str]:
    """Longitudes que rompen el diseño o que Instagram recorta, y cifras sin respaldo."""
    problemas = set()
    if not 15 <= len(t.gancho) <= 70:
        problemas.add(f"gancho de {len(t.gancho)} caracteres")
    if not re.search(r"\d", t.gancho):
        problemas.add("gancho sin ninguna cifra")
    if not 200 <= len(t.texto) <= 1100:
        problemas.add(f"texto de {len(t.texto)} caracteres; debe tener 400-900")
    if len(t.texto.splitlines()[0]) > 125:
        problemas.add("primera línea demasiado larga")
    if len(re.findall(r"\d,\d{2,3}\b", t.texto)) > 3:
        problemas.add("demasiados precios en el texto: las tablas ya están en las imágenes")
    if re.search(r"(?<![\d\w])-\d", t.texto):
        problemas.add('porcentaje negativo: escribe "una caída del 1,7 %"')
    if "#" in t.texto or "http" in t.texto:
        problemas.add("hashtags o enlaces en el texto")
    if not 3 <= len(t.hashtags) <= 5 or not all(re.fullmatch(r"#\w+", h) for h in t.hashtags):
        problemas.add(f"hashtags no válidos: {t.hashtags}")
    if not t.encuesta_pregunta or len(t.encuesta_pregunta) > 90:
        problemas.add("pregunta de la encuesta")
    if len(t.encuesta_opciones) != 2 or any(not 0 < len(o) <= 24 for o in t.encuesta_opciones):
        problemas.add(f"opciones de la encuesta: {t.encuesta_opciones}")
    if con_noticia and (not t.noticia_titulo or len(t.noticia_titulo) > 80 or not 2 <= len(t.noticia_puntos) <= 3
                        or any(len(p) > 125 for p in t.noticia_puntos)):
        problemas.add("noticia demasiado larga o incompleta")
    salida = " ".join([t.gancho, t.texto, t.noticia_titulo, *t.noticia_puntos, t.encuesta_pregunta, *t.encuesta_opciones])
    return problemas | gemini.sin_respaldo_en(salida, datos)


def redactar(datos: str, con_noticia: bool) -> Textos:
    textos, problemas = gemini.pedir(f"Contexto:\n<<<\n{datos}\n>>>", SISTEMA, Textos, lambda t: _problemas(t, datos, con_noticia))
    if problemas:
        raise gemini.ErrorGemini(f"Los textos de Instagram no pasan la revisión: {problemas}")
    return textos
