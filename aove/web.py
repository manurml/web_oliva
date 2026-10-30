"""Genera la web estática (docs/) a partir de datos/ con plantillas Jinja2."""
import json
import shutil
from datetime import date, datetime, timedelta

from jinja2 import Environment, FileSystemLoader, select_autoescape

import config
from aove import almacen

ORDEN_TIPOS = ["AOVE", "Virgen", "Lampante"]
ORDEN_REGIONES = ["España", "Andalucía", "Italia", "Grecia"]
MESES = "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split()


def fecha_larga(iso: str) -> str:
    if not iso:
        return ""
    d = date.fromisoformat(iso[:10])
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def fecha_corta(iso: str) -> str:
    d = date.fromisoformat(iso[:10])
    return f"{d.day} {MESES[d.month - 1][:3]}"


def euros(v: float | None, dec: int = 3) -> str:
    return "—" if v is None else f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _valor_hace(puntos: list[tuple[str, float]], dias: int) -> float | None:
    """Último valor con fecha <= (última fecha - dias)."""
    limite = (date.fromisoformat(puntos[-1][0]) - timedelta(days=dias)).isoformat()
    previos = [v for f, v in puntos if f <= limite]
    return previos[-1] if previos else None


def _variacion(actual: float, anterior: float | None) -> dict | None:
    if anterior is None or anterior == 0:
        return None
    pct = (actual - anterior) / anterior * 100
    return {"pct": pct, "abs": actual - anterior, "signo": "sube" if pct > 0.05 else "baja" if pct < -0.05 else "igual"}


def preparar_precios() -> tuple[dict, list[dict], list[dict]]:
    """Devuelve (datos para la gráfica, resumen por región/tipo, notas de InfaOliva)."""
    series = almacen.cargar_precios()
    grafica: dict[str, dict] = {}
    resumen: list[dict] = []
    otras: list[dict] = []
    for s in series.values():
        if s["fuente"] == "InfaOliva" and not config.PUBLICAR_PRECIOS_INFAOLIVA:
            continue
        puntos = sorted(s["puntos"].items())
        if s["fuente"] != "Oleista":
            # Tabla del día (InfaOliva): último dato, sea precio o nota tipo "Sin cierre de operaciones"
            fecha = max([*s["puntos"], *s["notas"]], default="")
            otras.append({"fuente": s["fuente"], "region": s["region"], "tipo": s["tipo"], "fecha": fecha,
                          "valor": s["puntos"].get(fecha), "nota": s["notas"].get(fecha, "")})
            continue
        # Sin mercado en fin de semana: Oleista rellena sábados y domingos con valores repetidos o desfasados.
        puntos = [(f, v) for f, v in puntos if date.fromisoformat(f).weekday() < 5]
        if not puntos:
            continue
        grafica.setdefault(s["region"], {})[s["tipo"]] = puntos
        f, v = puntos[-1]
        resumen.append({
            "region": s["region"], "tipo": s["tipo"], "fecha": f, "valor": v,
            "dia": _variacion(v, puntos[-2][1] if len(puntos) > 1 else None),
            "semana": _variacion(v, _valor_hace(puntos, 7)),
            "mes": _variacion(v, _valor_hace(puntos, 30)),
            "min30": min(x for d, x in puntos if d >= (date.fromisoformat(f) - timedelta(days=30)).isoformat()),
            "max30": max(x for d, x in puntos if d >= (date.fromisoformat(f) - timedelta(days=30)).isoformat()),
        })
    clave = lambda r: (ORDEN_REGIONES.index(r["region"]) if r["region"] in ORDEN_REGIONES else 99,
                       ORDEN_TIPOS.index(r["tipo"]) if r["tipo"] in ORDEN_TIPOS else 99)
    resumen.sort(key=clave)
    grafica = {r: grafica[r] for r in sorted(grafica, key=lambda r: ORDEN_REGIONES.index(r) if r in ORDEN_REGIONES else 99)}
    return grafica, resumen, otras


def construir() -> None:
    env = Environment(loader=FileSystemLoader(config.PLANTILLAS), autoescape=select_autoescape(["html"]))
    env.filters["fecha_larga"] = fecha_larga
    env.filters["euros"] = euros
    env.filters["fecha_corta"] = fecha_corta

    grafica, resumen, otras = preparar_precios()
    articulos = almacen.cargar_articulos()
    fecha_precios = max((r["fecha"] for r in resumen), default="")
    comun = {
        "sitio": {"nombre": config.SITIO_NOMBRE, "lema": config.SITIO_LEMA, "url": config.SITIO_URL},
        "generado": f"{fecha_larga(date.today().isoformat())}, a las {datetime.now():%H:%M}",
        "anio": date.today().year,
        "version": datetime.now().strftime("%Y%m%d%H%M"),
    }

    if config.SALIDA.exists():
        shutil.rmtree(config.SALIDA)
    (config.SALIDA / "articulos").mkdir(parents=True)
    shutil.copytree(config.ESTATICOS, config.SALIDA / "estaticos")
    (config.SALIDA / ".nojekyll").write_text("")

    def pagina(plantilla: str, destino: str, raiz: str, **ctx) -> None:
        html = env.get_template(plantilla).render(**comun, raiz=raiz, **ctx)
        (config.SALIDA / destino).write_text(html, encoding="utf-8")

    datos_grafica = json.dumps(grafica, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    ctx_precios = dict(resumen=resumen, otras=otras, fecha_precios=fecha_precios, datos_grafica=datos_grafica,
                       regiones=list(grafica))
    pagina("index.html", "index.html", "", articulos=articulos[:7], **ctx_precios)
    pagina("precios.html", "precios.html", "", **ctx_precios)
    pagina("archivo.html", "articulos/index.html", "../", articulos=articulos)
    pagina("acerca.html", "acerca.html", "")
    for i, a in enumerate(articulos):
        relacionados = [x for x in articulos if x["slug"] != a["slug"]][:3]
        pagina("articulo.html", f"articulos/{a['slug']}.html", "../", a=a, relacionados=relacionados,
               resumen=[r for r in resumen if r["region"] == "España"])
