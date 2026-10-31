"""Configuración de la web. Cambia aquí nombre, fuentes y parámetros."""
import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
DATOS = RAIZ / "datos"
SALIDA = RAIZ / "docs"          # GitHub Pages publica esta carpeta
PLANTILLAS = RAIZ / "plantillas"
ESTATICOS = RAIZ / "estaticos"

SITIO_NOMBRE = "AOVE al Día"
SITIO_LEMA = "Noticias y precios del aceite de oliva virgen extra, cada mañana"
# URL pública final (p. ej. https://usuario.github.io/web_oliva). Se usa en enlaces canónicos.
SITIO_URL = os.environ.get("SITIO_URL", "").rstrip("/")

# Identificación honesta del bot ante las webs que se consultan.
# Pon tu web o email de contacto en la variable CONTACTO_BOT para que las fuentes puedan escribirte.
USER_AGENT = f"AOVEalDiaBot/1.0 (+{os.environ.get('CONTACTO_BOT', 'sin-contacto')})"
PAUSA_ENTRE_PETICIONES = 2.0     # segundos, para no sobrecargar las fuentes
TIMEOUT = 30

# Noticias
NOTICIAS_POR_DIA = 2
DIAS_MAX_ANTIGUEDAD = 30         # no se reescriben noticias más antiguas (las fuentes publican pocas al mes)
MAX_PAGINAS_NUEVAS_POR_FUENTE = 25

# Redacción de noticias y análisis diario con Gemini (necesita GEMINI_API_KEY)
GEMINI_MODELO = os.environ.get("GEMINI_MODELO", "gemini-3.8-flash")
GEMINI_MODELO_RESERVA = os.environ.get("GEMINI_MODELO_RESERVA", "gemini-3.5-flash-lite")  # si el principal está saturado
AGENTE_ESTADO = os.environ.get("AGENTE_ESTADO", "published")  # "published" o "draft"
AGENTE_DIAS_MAX_DATOS = 7        # con precios más antiguos no se publica
AGENTE_MAX_NOTICIAS = 8
AGENTE_INTENTOS = 4
AGENTE_ESPERA_S = 20
AGENTE_TIMEOUT_MS = 120_000

# Precios. InfaOliva indica en su web: "Queda prohibida la publicación de la
# información facilitada por INFAOLIVA ... utilizando el propio nombre de
# INFAOLIVA sin autorización previa". Actívalo solo si tienes su autorización.
PUBLICAR_PRECIOS_INFAOLIVA = os.environ.get("PUBLICAR_PRECIOS_INFAOLIVA", "0") == "1"
