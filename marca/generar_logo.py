"""Genera en estaticos/ los logos e iconos a partir del PNG original de logo/ (necesita Pillow y NumPy).

Uso: python marca/generar_logo.py
"""
from pathlib import Path

import numpy as np
from PIL import Image

RAIZ = Path(__file__).resolve().parent.parent
ORIGEN = RAIZ / "logo" / "Logo minimalista AOVE al Día.png"
DESTINO = RAIZ / "estaticos"

# Tramos horizontales del original: símbolo, "AOVE" y "al Día"
FIN_SIMBOLO = 620
FIN_AOVE = 1420
# Colores del texto sobre fondo claro: los originales (blanco y oliva claro) no se leerían
TINTA = (0x1e, 0x2a, 0x1e)
OLIVA = (0x5f, 0x6b, 0x12)
ALTO_LOGO = 176  # 4 veces el alto de la cabecera
ICONOS = {"favicon-32.png": 32, "apple-touch-icon.png": 180, "icono-192.png": 192, "icono-512.png": 512}
PROPORCION_SIMBOLO = 0.66  # dentro de la zona segura de los iconos adaptables


def sin_fondo(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Convierte el fondo en transparencia y recupera el color real de los bordes suavizados."""
    fondo = np.median(rgb[:40].reshape(-1, 3), axis=0)
    distancia = np.linalg.norm(rgb - fondo, axis=2)
    alfa = np.clip((distancia - 16) / 50, 0, 1)
    limpio = (rgb - (1 - alfa[..., None]) * fondo) / np.maximum(alfa[..., None], 1e-3)
    return np.dstack([np.clip(limpio, 0, 255), alfa * 255]).astype("uint8"), fondo


def recortar(imagen: Image.Image) -> Image.Image:
    return imagen.crop(imagen.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox())


def main() -> None:
    rgb = np.asarray(Image.open(ORIGEN).convert("RGB"), dtype=float)
    rgba, fondo = sin_fondo(rgb)

    oscuro = recortar(Image.fromarray(rgba))
    claro = rgba.copy()
    claro[:, FIN_SIMBOLO:FIN_AOVE, :3] = TINTA
    claro[:, FIN_AOVE:, :3] = OLIVA
    claro = recortar(Image.fromarray(claro))

    for nombre, logo in (("logo-oscuro.png", oscuro), ("logo-claro.png", claro)):
        ancho = round(logo.width * ALTO_LOGO / logo.height)
        logo.resize((ancho, ALTO_LOGO), Image.LANCZOS).save(DESTINO / nombre, optimize=True)
        print(nombre, ancho, ALTO_LOGO)

    simbolo = recortar(Image.fromarray(rgba[:, :FIN_SIMBOLO]))
    color = tuple(int(c) for c in fondo)
    for nombre, lado in ICONOS.items():
        escala = lado * PROPORCION_SIMBOLO / max(simbolo.size)
        pequeno = simbolo.resize((round(simbolo.width * escala), round(simbolo.height * escala)), Image.LANCZOS)
        icono = Image.new("RGBA", (lado, lado), (*color, 255))
        icono.alpha_composite(pequeno, ((lado - pequeno.width) // 2, (lado - pequeno.height) // 2))
        icono.convert("RGB").save(DESTINO / nombre, optimize=True)
    print("fondo de los iconos: #%02x%02x%02x" % color)


if __name__ == "__main__":
    main()
