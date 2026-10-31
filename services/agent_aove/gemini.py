"""Cliente de Gemini con salida JSON validada, reintentos y comprobación de cifras."""
import logging
import os
import re
import time
from datetime import date

from google import genai
from google.genai import errors, types
from pydantic import BaseModel, Field, ValidationError

import config
from services.agent_aove.contexto import Contexto

log = logging.getLogger("agente_aove")

SISTEMA = """Eres periodista agrícola especializado en el mercado del aceite de oliva virgen extra (AOVE). Escribes para agricultores, almazaras, cooperativas y profesionales de la gastronomía, en español de España, con tono periodístico, profesional y atractivo.

Reglas obligatorias:
- Usa solo las cifras, fechas y precios del contexto. No inventes ni estimes ninguno, y no calcules cifras nuevas.
- No atribuyas causas a un movimiento de precios salvo que el contexto las indique; preséntalas como hipótesis si las mencionas.
- Di siempre a qué fecha corresponde un precio; no digas "hoy" si el dato es de otro día.
- No afirmes efectos en el sector, opiniones ni conclusiones que el contexto no respalde. Nunca rellenes con datos de memoria.
- Cita las fuentes de forma natural. No copies frases de las noticias: usa solo sus titulares y resúmenes.
- No des recomendaciones de compra o venta.
- Selecciona: usa solo los 3-6 datos más relevantes para el enfoque. Nunca enumeres todos los mercados ni todos los rangos.
- El artículo debe tratar de verdad sobre el enfoque del día.
- Evita frases vacías ("afronta nuevos retos", "cobra un papel protagonista").
- Escribe las fechas como en el contexto ("27 de octubre de 2026"), nunca en formato numérico. Escribe "una caída del 1,7 %", no "del -1,7 %". No uses verbos de subida ("alcanzó") para un precio que baja.

Formato:
- "titulo": informativo, menos de 90 caracteres.
- "slug": minúsculas, sin acentos, con guiones.
- "resumen": 1-2 frases.
- "contenido_markdown": 350-600 palabras, párrafos con 2-3 subtítulos "## ". Sin título principal.
- "etiquetas": 2-4 en minúscula.
- "meta_descripcion": menos de 155 caracteres."""

# Un enfoque por día, rotando, para no repetir el mismo artículo.
ENFOQUES = [
    "tendencia reciente de los precios del virgen extra",
    "comparación entre mercados: España, Andalucía, Italia y Grecia",
    "diferencia de precio entre virgen extra, virgen y lampante",
    "lectura de las noticias recientes del sector",
]


class ArticuloGemini(BaseModel):
    titulo: str
    slug: str
    resumen: str
    contenido_markdown: str
    etiquetas: list[str] = Field(default_factory=list)
    meta_descripcion: str


class ErrorGemini(Exception):
    pass


def _cliente() -> genai.Client:
    clave = os.environ.get("GEMINI_API_KEY")
    if not clave:
        raise ErrorGemini("Falta GEMINI_API_KEY. Crea la clave en https://aistudio.google.com/apikey")
    return genai.Client(api_key=clave, http_options=types.HttpOptions(timeout=config.AGENTE_TIMEOUT_MS))


def _numeros(texto: str) -> set[str]:
    """Cifras con decimales y porcentajes enteros, normalizados: '3.138' -> '3,138'; '40 %' -> '40%'."""
    decimales = {n.replace(".", ",") for n in re.findall(r"\d+[.,]\d+", texto)}
    return decimales | {f"{n}%" for n in re.findall(r"(?<![\d.,])(\d+)\s?%", texto)}


def _fechas(texto: str) -> set[str]:
    """Años y fechas ('27 de octubre'). Una fecha numérica nunca está en el contexto, así que se rechaza."""
    return ({f"{d} de {m.lower()}" for d, m in re.findall(r"\b(\d{1,2}) de ([a-zA-Zñáéíóú]+)", texto)}
            | set(re.findall(r"\b(?:19|20)\d{2}\b", texto))
            | set(re.findall(r"\b\d{1,4}[-/]\d{1,2}[-/]\d{1,4}\b", texto)))


def sin_respaldo_en(salida: str, contexto: str) -> set[str]:
    permitidas = _numeros(contexto)
    # Un precio redondeado a menos decimales también es válido: 3,138 -> 3,14 y 3,1.
    for n in [x for x in permitidas if "%" not in x]:
        valor = float(n.replace(",", "."))
        permitidas |= {f"{valor:.2f}".replace(".", ","), f"{valor:.1f}".replace(".", ",")}
    return (_numeros(salida) - permitidas) | (_fechas(salida) - _fechas(contexto))


def cifras_sin_respaldo(articulo: ArticuloGemini, contexto: str) -> set[str]:
    return sin_respaldo_en(f"{articulo.titulo} {articulo.resumen} {articulo.contenido_markdown}", contexto)


def redactar(datos: Contexto, hoy: date) -> tuple[ArticuloGemini, set[str]]:
    """Devuelve el artículo y las cifras sin respaldo que queden tras los reintentos."""
    enfoque = ENFOQUES[hoy.toordinal() % len(ENFOQUES)]
    log.info("Enfoque de hoy: %s", enfoque)
    instrucciones = f"Enfoque de hoy: {enfoque}.\n\nContexto:\n<<<\n{datos.texto}\n>>>"
    return pedir(instrucciones, SISTEMA, ArticuloGemini, lambda a: cifras_sin_respaldo(a, datos.texto))


def pedir(instrucciones: str, sistema: str, formato: type[BaseModel], comprobar=lambda _: set()) -> tuple:
    """Devuelve la respuesta validada y los problemas de `comprobar` que queden tras los reintentos."""
    cliente = _cliente()
    ajustes = types.GenerateContentConfig(
        system_instruction=sistema,
        response_mime_type="application/json",
        response_schema=formato,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    articulo = None
    sin_respaldo: set[str] = set()
    for intento in range(1, config.AGENTE_INTENTOS + 1):
        modelo = config.GEMINI_MODELO if intento <= 2 else config.GEMINI_MODELO_RESERVA
        log.info("Intento %d con %s", intento, modelo)
        try:
            r = cliente.models.generate_content(model=modelo, contents=instrucciones, config=ajustes)
            articulo = formato.model_validate_json(r.text or "")
        except ValidationError:
            log.warning("Intento %d: el JSON no es válido", intento)
        except errors.ClientError as e:
            if e.code != 429:  # clave o petición incorrecta: reintentar no lo arregla
                raise ErrorGemini(f"Gemini rechazó la petición ({e.code}): {e.message}") from e
            log.warning("Intento %d: límite del plan gratuito alcanzado", intento)
        except (errors.ServerError, OSError) as e:
            log.warning("Intento %d: fallo temporal: %s", intento, e)
        except Exception as e:
            if "timeout" not in type(e).__name__.lower():
                raise
            log.warning("Intento %d: tiempo de espera agotado", intento)
        else:
            sin_respaldo = comprobar(articulo)
            if not sin_respaldo:
                return articulo, set()
            log.warning("Intento %d: cifras sin respaldo: %s", intento, sin_respaldo)
        if intento < config.AGENTE_INTENTOS:
            time.sleep(config.AGENTE_ESPERA_S * intento)
    if articulo is None:
        raise ErrorGemini(f"Gemini no devolvió una respuesta válida tras {config.AGENTE_INTENTOS} intentos")
    return articulo, sin_respaldo
