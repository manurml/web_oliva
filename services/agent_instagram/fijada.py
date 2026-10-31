"""Publicación fijada del perfil: explica qué es la cuenta. Texto fijo, sin Gemini, y coherente con plantillas/acerca.html."""
from pathlib import Path

from services.agent_instagram import imagenes

PIE = """Si trabajas con aceite de oliva, aquí tienes los precios y las noticias del sector sin tener que buscarlos.

Publicamos las cotizaciones en origen del virgen extra, el virgen y el lampante en España, Andalucía, Italia y Grecia, cada vez que hay datos nuevos, siempre con la fecha de cada dato.

Los precios proceden de las cotizaciones publicadas por Oleista. Las noticias son de elaboración propia, a partir de publicaciones del sector, y citan su fuente.

Son precios orientativos, a granel: no son una oferta de compra o venta ni una recomendación. Los textos se elaboran con ayuda de inteligencia artificial.

¿Te dedicas al olivar, a una almazara o a una cooperativa? Cuéntanos en comentarios qué dato te gustaría ver aquí.

Más datos en el enlace de la biografía.

#AOVE #AceiteDeOliva #PreciosDelAceite #Olivar #Almazara
"""

DIAPOSITIVAS = [
    {"archivo": "publicacion/1-portada.png", "antetitulo": "Qué es esta cuenta", "titulo": "Los precios y las noticias del aceite de oliva, en un vistazo.",
     "puntos": ["Para agricultores, almazaras, cooperativas y profesionales del sector."], "desliza": True},
    {"archivo": "publicacion/2-contenido.png", "antetitulo": "Qué encontrarás", "titulo": "Datos claros, cuando hay datos nuevos",
     "puntos": ["Precios en origen del virgen extra, el virgen y el lampante.", "España, Andalucía, Italia y Grecia.",
                "Gráficas para ver la tendencia.", "Noticias del sector, explicadas."], "desliza": True},
    {"archivo": "publicacion/3-fuentes.png", "antetitulo": "De dónde sale", "titulo": "Siempre con su fuente y su fecha",
     "puntos": ["Precios: cotizaciones publicadas por Oleista.", "Noticias: elaboración propia a partir de publicaciones del sector.",
                "Textos elaborados con ayuda de inteligencia artificial."], "desliza": True},
    {"archivo": "publicacion/4-cierre.png", "antetitulo": "Para tenerlo en cuenta", "titulo": "Información, no asesoramiento",
     "puntos": ["Precios orientativos, a granel.", "No son una oferta de compra o venta ni una recomendación.",
                "Síguenos y encuentra más datos en el enlace de la biografía."], "desliza": False},
]


def generar(destino: Path) -> None:
    imagenes.borrar_piezas(destino)
    piezas = [{**d, "vista": "lista", "tam": imagenes.CARRUSEL} for d in DIAPOSITIVAS]
    imagenes.pintar(destino, piezas)
    (destino / "texto_publicacion.txt").write_text(PIE, encoding="utf-8")
    guia = ["CÓMO SUBIRLO", "", f"1. Sube las {len(piezas)} imágenes de la carpeta publicacion/, en orden.",
            "2. Pega como pie el contenido de texto_publicacion.txt.",
            "3. Pega el texto alternativo de cada imagen (Configuración avanzada > Accesibilidad):"]
    guia += [f"   - {Path(d['archivo']).name}: {d['titulo']}. {' '.join(d['puntos'])}" for d in DIAPOSITIVAS]
    guia += ["4. Ya publicada, pulsa los tres puntos de la publicación > Fijar en tu perfil."]
    (destino / "como_subirlo.txt").write_text("\n".join(guia) + "\n", encoding="utf-8")
