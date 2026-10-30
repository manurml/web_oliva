"""Tarea diaria: precios + noticias + artículos + regeneración de la web.

Uso:
    python diario.py                  # todo
    python diario.py --si-hay-cambios # todo, pero solo si Oleista ha publicado precios nuevos
    python diario.py --solo-web       # solo regenera la web con los datos guardados
"""
import argparse
import logging
import re
import unicodedata
from datetime import date, timedelta

import config
from aove import almacen, redactor, web
from aove.fuentes import infaoliva, oleista
from aove.red import BloqueadoPorRobots

log = logging.getLogger("diario")


def _actualizar_fuente(nombre: str, funcion) -> int:
    """Devuelve cuántos precios han cambiado (0 también si la fuente falla)."""
    try:
        precios = funcion()
        cambios = almacen.guardar_precios(precios)
        log.info("%s: %d precios leídos, %d nuevos o corregidos", nombre, len(precios), cambios)
        return cambios
    except Exception:
        log.exception("No se pudieron leer los precios de %s", nombre)
        return 0


def _clasificar(vistas: dict, noticia, primera_vez: bool) -> None:
    if not noticia.fecha:
        # Sin fecha en la fuente: en la primera ejecución se asume antigua; después, fecha = día en que aparece.
        noticia.fecha = "" if primera_vez else date.today().isoformat()
    # Las que superan DIAS_MAX_ANTIGUEDAD pasan a "antigua" al guardar (almacen.guardar_vistas).
    vistas[noticia.url] = {"estado": "candidata" if noticia.fecha else "antigua", "noticia": noticia.a_dict()}


def recoger_noticias(vistas: dict) -> None:
    primera_vez = not vistas
    desde = (date.today() - timedelta(days=config.DIAS_MAX_ANTIGUEDAD)).isoformat()

    try:
        nuevas = [u for u in oleista.enlaces_noticias() if u not in vistas][: config.MAX_PAGINAS_NUEVAS_POR_FUENTE]
        for orden, url in enumerate(nuevas):
            try:
                if n := oleista.leer_noticia(url, orden):
                    _clasificar(vistas, n, primera_vez)
            except BloqueadoPorRobots:
                log.warning("robots.txt no permite %s", url)
            except Exception:
                log.exception("Error leyendo %s", url)
    except Exception:
        log.exception("No se pudo leer el listado de Oleista")

    try:
        enlaces = [e for e in infaoliva.enlaces_noticias() if e[0] not in vistas]
        for orden, (url, titulo, fecha) in enumerate(enlaces):
            if (fecha and fecha < desde) or (not fecha and primera_vez):
                vistas[url] = {"estado": "antigua", "noticia": {"url": url, "fuente": infaoliva.FUENTE, "titulo": titulo,
                                                              "fecha": fecha, "resumen": "", "texto": "", "orden": orden}}
                continue
            if orden >= config.MAX_PAGINAS_NUEVAS_POR_FUENTE:
                break
            try:
                if n := infaoliva.leer_noticia(url, titulo, fecha, orden):
                    _clasificar(vistas, n, primera_vez)
                else:
                    vistas[url] = {"estado": "descartada", "noticia": {"url": url, "fuente": infaoliva.FUENTE, "titulo": titulo,
                                                                       "fecha": fecha, "resumen": "", "texto": "", "orden": orden}}
            except Exception:
                log.exception("Error leyendo %s", url)
    except Exception:
        log.exception("No se pudo leer el listado de InfaOliva")


def slug(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:80]


def _con_texto(noticia):
    """Descarga el texto de la fuente justo antes de redactar; no se guarda en datos/."""
    if noticia.fuente == infaoliva.FUENTE:
        leida = infaoliva.leer_noticia(noticia.url, noticia.titulo, noticia.fecha, noticia.orden)
    else:
        leida = oleista.leer_noticia(noticia.url, noticia.orden)
    if not leida:
        raise ValueError(f"Sin texto en {noticia.url}")
    noticia.texto = leida.texto
    return noticia


def publicar_articulos(vistas: dict) -> None:
    # La tarea puede ejecutarse varias veces al día: los artículos solo se publican una vez.
    if any(a["fecha_publicacion"] == date.today().isoformat() and a.get("tipo") != "analisis" for a in almacen.cargar_articulos()):
        log.info("Los artículos de hoy ya están publicados")
        return
    desde =(date.today() - timedelta(days=config.DIAS_MAX_ANTIGUEDAD)).isoformat()
    pool = almacen.candidatas(vistas, desde)
    log.info("%d noticias candidatas", len(pool))
    if not pool:
        return
    con_ia = redactor.disponible()
    if not con_ia:
        log.warning("Sin ANTHROPIC_API_KEY: se publican fichas breves en lugar de artículos redactados")
    for noticia in redactor.elegir(pool, config.NOTICIAS_POR_DIA):
        try:
            noticia = _con_texto(noticia)
            art = redactor.redactar(noticia) if con_ia else redactor.breve_sin_ia(noticia)
        except Exception:
            log.exception("No se pudo redactar %s", noticia.url)
            continue
        hoy = date.today().isoformat()
        base = nombre = f"{hoy}-{slug(art.titulo)}"
        n = 2
        while (almacen.ARTICULOS / f"{nombre}.json").exists():
            nombre, n = f"{base}-{n}", n + 1
        datos = art.model_dump() | {
            "slug": nombre,
            "fecha_publicacion": hoy,
            "redactado_con_ia": con_ia,
            "fuente": {"nombre": noticia.fuente, "url": noticia.url, "titulo": noticia.titulo, "fecha": noticia.fecha},
        }
        almacen.guardar_articulo(datos)
        vistas[noticia.url]["estado"] = "publicada"
        log.info("Publicado: %s", art.titulo)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo-web", action="store_true")
    ap.add_argument("--si-hay-cambios", action="store_true")
    args = ap.parse_args()
    if not args.solo_web:
        cambios = _actualizar_fuente("Oleista", oleista.precios)
        if args.si_hay_cambios and not cambios:
            log.info("Oleista no ha publicado precios nuevos: no se actualiza nada")
            return
        _actualizar_fuente("InfaOliva", infaoliva.precios)
        vistas = almacen.cargar_vistas()
        recoger_noticias(vistas)
        almacen.guardar_vistas(vistas)
        publicar_articulos(vistas)
        almacen.guardar_vistas(vistas)
    web.construir()
    log.info("Web generada en %s", config.SALIDA)


if __name__ == "__main__":
    main()
