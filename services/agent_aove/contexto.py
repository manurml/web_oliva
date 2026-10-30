"""Reúne los datos que puede usar el artículo. Solo lee lo ya guardado: no hace peticiones a las fuentes."""
from dataclasses import dataclass
from datetime import date, timedelta

import config
from aove import almacen, web


@dataclass
class Contexto:
    texto: str
    fecha_precios: str


def _pct(v: dict | None) -> str:
    return "sin dato" if not v else f"{v['pct']:+.1f} %".replace(".", ",")


def recopilar(hoy: date) -> Contexto:
    # preparar_precios ya excluye InfaOliva salvo autorización (config.PUBLICAR_PRECIOS_INFAOLIVA).
    _, resumen, _ = web.preparar_precios()
    if not resumen:
        return Contexto("", "")
    fecha_precios = max(p["fecha"] for p in resumen)

    lineas = [f"Fecha de hoy: {web.fecha_larga(hoy.isoformat())}", f"Último dato de precios: {web.fecha_larga(fecha_precios)}", "",
              "PRECIOS EN ORIGEN, A GRANEL, EN €/KG (fuente: Oleista)"]
    for p in resumen:
        lineas.append(
            f"- {p['region']}, {p['tipo']}: {web.euros(p['valor'])} el {web.fecha_larga(p['fecha'])}. Variación: sesión anterior {_pct(p['dia'])}, "
            f"semana {_pct(p['semana'])}, mes {_pct(p['mes'])}. Rango de 30 días: {web.euros(p['min30'])} a {web.euros(p['max30'])}."
        )

    desde = (hoy - timedelta(days=config.DIAS_MAX_ANTIGUEDAD)).isoformat()
    noticias = sorted((v["noticia"] for v in almacen.cargar_vistas().values() if v["noticia"]["fecha"] >= desde),
                      key=lambda n: n["fecha"], reverse=True)[:config.AGENTE_MAX_NOTICIAS]
    lineas += ["", "NOTICIAS RECIENTES DEL SECTOR"]
    lineas += [f"- {web.fecha_larga(n['fecha'])}, {n['fuente']}: {n['titulo']}. {n['resumen']}".rstrip() for n in noticias] or ["- Ninguna"]
    return Contexto("\n".join(lineas), fecha_precios)
