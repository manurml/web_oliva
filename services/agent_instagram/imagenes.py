"""Pinta las piezas con plantillas/instagram.html y las convierte en PNG con Edge o Chrome sin ventana."""
import os
import shutil
import subprocess
import tempfile
from datetime import date, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

import config
from aove import web

CARRUSEL = (1080, 1350)
HISTORIA = (1080, 1920)
NAVEGADORES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
]
SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _navegador() -> str:
    for ruta in NAVEGADORES:
        if os.path.exists(ruta):
            return ruta
    raise RuntimeError("No se encuentra Edge ni Chrome para generar las imágenes")


def porcentaje(v: dict | None) -> str:
    if not v:
        return "sin dato"
    if v["signo"] == "igual":
        return "sin cambios"
    return f"{'+' if v['pct'] > 0 else '−'}{abs(v['pct']):.1f}\u00a0%".replace(".", ",")


def _grafica(puntos: list[tuple[str, float]]) -> dict:
    """Línea de los últimos 90 días, con el eje ajustado a los datos: importa el cambio, no el nivel."""
    limite = (date.fromisoformat(puntos[-1][0]) - timedelta(days=90)).isoformat()
    puntos = [p for p in puntos if p[0] >= limite]
    ancho, alto, izq, der, arr, aba = 920, 640, 110, 150, 30, 60
    valores = [v for _, v in puntos]
    bajo, alto_v = min(valores), max(valores)
    margen = max((alto_v - bajo) * 0.12, 0.02)
    y0, y1 = bajo - margen, alto_v + margen
    x = lambda i: izq + i * (ancho - izq - der) / max(len(puntos) - 1, 1)
    y = lambda v: arr + (y1 - v) * (alto - arr - aba) / (y1 - y0)
    fin = len(puntos) - 1
    return {
        "ancho": ancho, "alto": alto, "izq": izq, "der": ancho - der, "base": alto - aba,
        "linea": " ".join(f"{x(i):.1f},{y(v):.1f}" for i, (_, v) in enumerate(puntos)),
        "marcas": [{"y": round(y(m), 1), "texto": web.euros(m, 2)} for m in (y0 + (y1 - y0) * f for f in (.1, .5, .9))],
        "fin": {"x": round(x(fin), 1), "y": round(y(valores[fin]), 1), "texto": web.euros(valores[fin], 2)},
        "desde": web.fecha_corta(puntos[0][0]), "hasta": web.fecha_corta(puntos[-1][0]),
    }


def _piezas(textos: dict, articulo: dict | None) -> list[dict]:
    grafica, resumen, _ = web.preparar_precios()
    fila = lambda r: {"region": r["region"], "tipo": {"AOVE": "Virgen extra"}.get(r["tipo"], r["tipo"]), "valor": web.euros(r["valor"]),
                      "fecha": web.fecha_corta(r["fecha"]), "semana": porcentaje(r["semana"]),
                      "signo": r["semana"]["signo"] if r["semana"] else "igual"}
    aove = next(r for r in resumen if r["region"] == "España" and r["tipo"] == "AOVE")
    principal = {"valor": web.euros(aove["valor"]), "fecha": web.fecha_larga(aove["fecha"]), "semana": porcentaje(aove["semana"]),
                 "mes": porcentaje(aove["mes"]), "signo_semana": aove["semana"]["signo"] if aove["semana"] else "igual",
                 "signo_mes": aove["mes"]["signo"] if aove["mes"] else "igual"}
    mercados = [fila(r) for r in resumen if r["tipo"] == "AOVE"]
    tipos = [fila(r) for r in resumen if r["region"] == "España"]
    linea = _grafica(grafica["España"]["AOVE"])

    piezas = [
        {"archivo": "publicacion/1-portada.png", "vista": "portada", "tam": CARRUSEL, "alt": f"Virgen extra en España: {principal['valor']} €/kg el {principal['fecha']}. {textos['gancho']}"},
        {"archivo": "publicacion/2-grafica.png", "vista": "grafica", "tam": CARRUSEL, "alt": f"Gráfica del precio del virgen extra en España del {linea['desde']} al {linea['hasta']}, hasta {linea['fin']['texto']} €/kg."},
        {"archivo": "publicacion/3-mercados.png", "vista": "tabla", "tam": CARRUSEL, "titulo": "Virgen extra por mercado", "filas": mercados, "columna": "region",
         "alt": "Virgen extra: " + "; ".join(f"{f['region']}, {f['valor']} €/kg" for f in mercados) + "."},
        {"archivo": "publicacion/4-calidades.png", "vista": "tabla", "tam": CARRUSEL, "titulo": "Las tres calidades en España", "filas": tipos, "columna": "tipo",
         "alt": "España: " + "; ".join(f"{f['tipo']}, {f['valor']} €/kg" for f in tipos) + "."},
    ]
    if articulo:
        piezas.append({"archivo": "publicacion/5-noticia.png", "vista": "noticia", "tam": CARRUSEL, "alt": textos["noticia_titulo"]})
    piezas += [
        {"archivo": f"publicacion/{len(piezas) + 1}-cierre.png", "vista": "cierre", "tam": CARRUSEL, "alt": "Sigue a AOVE al Día. Más datos en el enlace de la biografía."},
        {"archivo": "historias/1-precio.png", "vista": "portada", "tam": HISTORIA, "alt": ""},
    ]
    if articulo:
        piezas.append({"archivo": "historias/2-noticia.png", "vista": "noticia", "tam": HISTORIA, "alt": ""})
    piezas.append({"archivo": f"historias/{3 if articulo else 2}-encuesta.png", "vista": "encuesta", "tam": HISTORIA, "alt": ""})
    for p in piezas:
        p.update(principal=principal, linea=linea, textos=textos)
    return piezas


def generar(destino: Path, textos: dict, articulo: dict | None) -> list[dict]:
    """Devuelve las piezas creadas. Comprueba cada PNG: un fallo del navegador no debe dejar una imagen a medias."""
    navegador = _navegador()
    entorno = Environment(loader=FileSystemLoader(config.PLANTILLAS), autoescape=select_autoescape(["html"]))
    plantilla = entorno.get_template("instagram.html")
    piezas = _piezas(textos, articulo)
    (destino / "publicacion").mkdir(parents=True, exist_ok=True)
    (destino / "historias").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for p in piezas:
            html = Path(tmp) / "pieza.html"
            html.write_text(plantilla.render(logo=(config.ESTATICOS / "logo-oscuro.png").as_uri(), web=config.INSTAGRAM_WEB, **p), encoding="utf-8")
            salida = destino / p["archivo"]
            salida.unlink(missing_ok=True)
            subprocess.run([navegador, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={tmp}/perfil",
                            "--force-device-scale-factor=1", f"--window-size={p['tam'][0]},{p['tam'][1]}", "--virtual-time-budget=5000",
                            f"--screenshot={salida}", html.as_uri()], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=120, creationflags=SIN_VENTANA, check=False)
            if not salida.exists() or salida.stat().st_size < 10_000:
                raise RuntimeError(f"No se pudo generar {p['archivo']}")
    return piezas


def borrar_piezas(destino: Path) -> None:
    for carpeta in ("publicacion", "historias"):
        shutil.rmtree(destino / carpeta, ignore_errors=True)
