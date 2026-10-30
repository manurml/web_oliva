"""Orquestación: precios y noticias guardados -> Gemini -> artículo en datos/articulos -> web.

Uso:
    python -m services.agent_aove            # genera el artículo de hoy y regenera la web
    python -m services.agent_aove --borrador # lo guarda como borrador, sin mostrarlo en la web
    python -m services.agent_aove --seco     # muestra el contexto que se enviaría, sin llamar a Gemini
"""
import argparse
import logging
import sys
from datetime import date, timedelta

import config
from aove import almacen, web
from services.agent_aove import contexto, gemini, publicacion

log = logging.getLogger("agente_aove")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--borrador", action="store_true")
    ap.add_argument("--seco", action="store_true")
    args = ap.parse_args()

    hoy = date.today()
    if publicacion.ya_publicado(hoy) and not args.seco:
        log.info("El análisis de hoy ya existe: no se genera otro")
        return 0
    datos = contexto.recopilar(hoy)
    if not datos.texto:
        log.error("No hay precios guardados: no se puede escribir el artículo")
        return 1
    if args.seco:
        print(datos.texto)
        return 0
    if datos.fecha_precios < (hoy - timedelta(days=config.AGENTE_DIAS_MAX_DATOS)).isoformat():
        log.warning("El último precio es del %s, demasiado antiguo: no se publica", datos.fecha_precios)
        return 0

    try:
        articulo, sin_respaldo = gemini.redactar(datos, hoy)
    except gemini.ErrorGemini as e:
        log.error("%s", e)
        return 1

    # Una cifra que no está en los datos nunca llega a publicarse sola.
    estado = "draft" if args.borrador or sin_respaldo else config.AGENTE_ESTADO
    if sin_respaldo:
        log.warning("Cifras sin respaldo en los datos %s: se guarda como borrador", sin_respaldo)
    guardado = publicacion.guardar(articulo, datos, hoy, estado)
    log.info("Artículo guardado (%s): datos/articulos/%s.json", estado, guardado["slug"])
    web.construir()
    log.info("Web generada en %s (%d artículos en total)", config.SALIDA, len(almacen.cargar_articulos()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
