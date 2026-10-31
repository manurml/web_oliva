"""Precios y artículos guardados -> textos con Gemini -> carrusel e historias en instagram/AAAA-MM-DD/.

No publica nada: deja el paquete listo para subirlo a mano. Solo genera si hay precios o artículos nuevos.

Uso:
    python -m services.agent_instagram                 # genera si hay novedades
    python -m services.agent_instagram --forzar        # genera aunque no las haya
    python -m services.agent_instagram --solo-imagenes # repite las imágenes de hoy con los textos ya guardados
    python -m services.agent_instagram --seco          # muestra el contexto, sin llamar a Gemini
    python -m services.agent_instagram --reenviar      # vuelve a mandar por correo el paquete de hoy
    python -m services.agent_instagram --fijada        # prepara y envía la publicación fijada del perfil
"""
import argparse
import json
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

import config
from aove import almacen, web
from services.agent_aove import gemini
from services.agent_instagram import contenido, correo, fijada, imagenes

log = logging.getLogger("agente_instagram")
ESTADO = config.INSTAGRAM / "estado.json"


def _leer_estado() -> dict:
    return json.loads(ESTADO.read_text(encoding="utf-8")) if ESTADO.exists() else {"huella": "", "articulos": []}


def _enviar_pendiente(estado: dict) -> None:
    """El paquete sigue pendiente hasta que el envío funciona, aunque no haya novedades."""
    if estado.get("correo_pendiente") and correo.enviar(config.INSTAGRAM / estado["correo_pendiente"]):
        estado["correo_pendiente"] = ""
        ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")


def _huella(resumen: list[dict], articulo: dict | None) -> str:
    """Identifica lo que se va a contar: cambia con un precio nuevo o un artículo nuevo."""
    return "|".join([*(f"{r['region']},{r['tipo']},{r['fecha']},{r['valor']}" for r in resumen), articulo["slug"] if articulo else ""])


def _guardar_textos(destino: Path, textos: dict, piezas: list[dict], articulo: dict | None) -> None:
    (destino / "texto_publicacion.txt").write_text(f"{textos['texto']}\n\n{' '.join(textos['hashtags'])}\n", encoding="utf-8")
    fotos = [p for p in piezas if p["archivo"].startswith("publicacion/")]
    historias = [p for p in piezas if p["archivo"].startswith("historias/")]
    guia = ["CÓMO SUBIRLO", "", "PUBLICACIÓN (carrusel)",
            f"1. Sube las {len(fotos)} imágenes de la carpeta publicacion/, en orden.",
            "2. Pega como pie el contenido de texto_publicacion.txt.",
            "3. Pega el texto alternativo de cada imagen (Configuración avanzada > Accesibilidad):"]
    guia += [f"   - {Path(p['archivo']).name}: {p['alt']}" for p in fotos]
    guia += ["", "HISTORIAS"]
    for p in historias:
        if p["vista"] == "noticia":
            guia.append(f"- {Path(p['archivo']).name}: añade un sticker de enlace a {config.INSTAGRAM_WEB}/articulos/{articulo['slug']}.html")
        elif p["vista"] == "encuesta":
            guia.append(f"- {Path(p['archivo']).name}: añade en el hueco un sticker de encuesta con «{textos['encuesta_opciones'][0]}» y «{textos['encuesta_opciones'][1]}».")
        else:
            guia.append(f"- {Path(p['archivo']).name}: añade un sticker de enlace a {config.INSTAGRAM_WEB}/precios.html")
    (destino / "como_subirlo.txt").write_text("\n".join(guia) + "\n", encoding="utf-8")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--forzar", action="store_true")
    ap.add_argument("--solo-imagenes", action="store_true")
    ap.add_argument("--seco", action="store_true")
    ap.add_argument("--reenviar", action="store_true")
    ap.add_argument("--fijada", action="store_true")
    args = ap.parse_args()

    if args.fijada:
        carpeta = config.INSTAGRAM / "fijada"
        fijada.generar(carpeta)
        log.info("Publicación fijada lista en %s", carpeta)
        return 0 if correo.enviar(carpeta, "AOVE al Día: publicación fijada para Instagram") else 1

    hoy = date.today()
    destino = config.INSTAGRAM / hoy.isoformat()
    estado = _leer_estado()
    if args.reenviar:
        if not (destino / "texto_publicacion.txt").exists():
            log.error("Hoy no hay ningún paquete que enviar")
            return 1
        return 0 if correo.enviar(destino) else 1
    _, resumen, _ = web.preparar_precios()
    if not resumen:
        log.error("No hay precios guardados")
        return 1
    fecha_precios = max(r["fecha"] for r in resumen)
    if fecha_precios < (hoy - timedelta(days=config.AGENTE_DIAS_MAX_DATOS)).isoformat():
        log.warning("El último precio es del %s, demasiado antiguo: no se genera contenido", fecha_precios)
        return 0

    if args.solo_imagenes:
        guardado = json.loads((destino / "textos.json").read_text(encoding="utf-8"))
        slug = guardado["articulo"]
        articulo = next((a for a in almacen.cargar_articulos() if a["slug"] == slug), None)
        imagenes.borrar_piezas(destino)
        _guardar_textos(destino, guardado["textos"], imagenes.generar(destino, guardado["textos"], articulo), articulo)
        log.info("Imágenes repetidas en %s", destino)
        return 0

    # El artículo ya usado hoy cuenta como disponible: si llega un precio nuevo por la tarde, el paquete lo mantiene.
    usados = [s for s in estado["articulos"] if estado.get("fecha") != hoy.isoformat() or s != estado.get("articulo")]
    articulo = contenido.elegir_articulo(hoy, usados)
    huella = _huella(resumen, articulo)
    datos = contenido.preparar_contexto(hoy, articulo)
    if args.seco:
        print(datos)
        return 0
    if huella == estado["huella"] and not args.forzar:
        log.info("Sin precios ni artículos nuevos: no se genera contenido")
        _enviar_pendiente(estado)
        return 0

    try:
        textos = contenido.redactar(datos, articulo is not None).model_dump()
        imagenes.borrar_piezas(destino)
        piezas = imagenes.generar(destino, textos, articulo)
    except (gemini.ErrorGemini, RuntimeError, OSError) as e:
        # No se guarda la huella: se reintenta en la siguiente ejecución.
        log.error("No se pudo preparar el contenido de Instagram: %s", e)
        return 1
    _guardar_textos(destino, textos, piezas, articulo)
    (destino / "textos.json").write_text(json.dumps({"textos": textos, "articulo": articulo["slug"] if articulo else ""}, ensure_ascii=False, indent=1), encoding="utf-8")
    slug = articulo["slug"] if articulo else None
    estado = {"huella": huella, "fecha": hoy.isoformat(), "articulo": slug, "correo_pendiente": hoy.isoformat(),
              "articulos": list(dict.fromkeys([*estado["articulos"], *([slug] if slug else [])]))}
    ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=1), encoding="utf-8")
    log.info("Contenido de Instagram listo en %s (%d piezas)", destino, len(piezas))
    _enviar_pendiente(estado)
    return 0


if __name__ == "__main__":
    sys.exit(main())
