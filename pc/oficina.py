"""Oficina de agentes: servidor local que muestra el estado real del proyecto y permite lanzar el proceso.

Solo escucha en este PC. No guarda nada propio: lee pc/registro.log, el bloqueo de actualizar.py y datos/.

Uso: doble clic en pc/abrir_oficina.bat, o python pc/oficina.py
"""
import json
import msvcrt
import re
import secrets
import subprocess
import sys
import time
import webbrowser
import winreg
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
import config  # noqa: E402
from aove import almacen, web  # noqa: E402

PUERTO = 8770
ORIGEN = f"http://127.0.0.1:{PUERTO}"
PAGINA = Path(__file__).with_name("oficina.html")
REGISTRO = RAIZ / "pc" / "registro.log"
BLOQUEO = RAIZ / "pc" / "actualizar.lock"
ULTIMA = RAIZ / "pc" / "ultima_ejecucion.txt"
TAREA = "AOVE al Dia - actualizacion diaria"
TOKEN = secrets.token_urlsafe(24)  # impide que otra web abierta en el navegador lance el proceso
SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)
LINEAS_REGISTRO = 60
_cache: dict[str, tuple[float, object]] = {}


def _cacheado(clave: str, segundos: float, funcion):
    momento, valor = _cache.get(clave, (0.0, None))
    if time.monotonic() - momento > segundos:
        valor = funcion()
        _cache[clave] = (time.monotonic(), valor)
    return valor


def en_curso() -> bool:
    """Lo sabe por el bloqueo de actualizar.py, así que también detecta las ejecuciones de la tarea programada."""
    if not BLOQUEO.exists():
        return False
    with BLOQUEO.open("a") as f:
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            return True
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    return False


def ultimo_bloque(texto: str) -> list[str]:
    lineas = texto.splitlines()
    inicios = [i for i, l in enumerate(lineas) if l.startswith("=== ")]
    return [l for l in lineas[inicios[-1]:] if "LF will be replaced" not in l] if inicios else []


def _ultima(lineas: list[str], patron: str) -> str:
    return next((l for l in reversed(lineas) if re.search(patron, l)), "")


def _mensaje(linea: str) -> str:
    """Quita fecha, nivel y módulo de una línea del registro."""
    return re.sub(r"^\S+ \S+ [A-Z]+ [\w.]+: ", "", linea)[:160]


def analizar(lineas: list[str], activo: bool) -> list[dict]:
    """Traduce el registro de la última ejecución a etapas. Cada una: pendiente, activa, hecha, aviso, error u omitida."""
    t = "\n".join(lineas)
    hay = lambda patron: re.search(patron, t, re.M) is not None
    sin_precios = hay(r"no ha publicado precios nuevos")
    sin_novedades = hay(r"Sin precios ni artículos nuevos")
    fallo_ig = hay(r"AVISO: no se pudo preparar|No se pudo preparar el contenido")

    def etapa(id_, nombre, agente, fin, detalle="", estado="hecha"):
        return {"id": id_, "nombre": nombre, "agente": agente, "fin": fin, "detalle": detalle, "estado": estado}

    articulos = re.findall(r"INFO diario: Publicado: (.+)", t)
    leidos = _ultima(lineas, r"Oleista: \d+ precios")
    etapas = [
        etapa("sincroniza", "Sincronizar", "precios", hay(r"diario:|no se pudo sincronizar"),
              "No se pudo sincronizar con GitHub" if hay(r"no se pudo sincronizar") else "Al día con GitHub",
              "error" if hay(r"no se pudo sincronizar") else "hecha"),
        etapa("precios", "Leer precios", "precios", hay(r"InfaOliva: \d+ precios|No se pudieron leer los precios de InfaOliva") or sin_precios,
              _mensaje(leidos) or "No se pudieron leer los precios de Oleista",
              "aviso" if hay(r"No se pudieron leer") else "hecha"),
    ]
    if sin_precios:
        etapas += [etapa("noticias", "Redactar noticias", "noticias", True, "Sin precios nuevos", "omitida"),
                   etapa("web", "Generar web", "precios", True, "Sin precios nuevos", "omitida"),
                   etapa("github", "Subir a GitHub", "precios", hay(r"^Sin cambios que publicar|^Publicado$"), "Sin cambios", "omitida")]
    else:
        detalle = f"{len(articulos)} publicados: {articulos[-1]}" if articulos else _mensaje(_ultima(lineas, r"noticias candidatas|artículos de hoy ya"))
        sin_clave = hay(r"Sin GEMINI_API_KEY")
        etapas += [etapa("noticias", "Redactar noticias", "noticias", hay(r"Web generada"), "Sin clave de Gemini: fichas breves" if sin_clave else detalle, "aviso" if sin_clave else "hecha"),
                   etapa("web", "Generar web", "precios", hay(r"Web generada"), "docs/ regenerado"),
                   etapa("github", "Subir a GitHub", "precios", hay(r"^Publicado$|^Sin cambios que publicar|ERROR: no se pudo (crear|subir)"),
                         "No se pudo subir a GitHub" if hay(r"ERROR: no se pudo (crear|subir)") else "Sin cambios" if hay(r"^Sin cambios") else "Publicado",
                         "error" if hay(r"ERROR: no se pudo (crear|subir)") else "hecha")]
    etapas.append(etapa("instagram", "Crear Instagram", "instagram", hay(r"Contenido de Instagram listo") or sin_novedades or fallo_ig,
                        "No se pudo preparar el contenido" if fallo_ig else "Sin novedades" if sin_novedades else _mensaje(_ultima(lineas, r"Contenido de Instagram listo")),
                        "error" if fallo_ig else "omitida" if sin_novedades else "hecha"))
    sin_envio = hay(r"no se envía por correo|No se pudo enviar el correo")
    etapas.append(etapa("correo", "Enviar correo", "instagram", hay(r"enviado por correo") or sin_envio or sin_novedades or fallo_ig,
                        "Correo no enviado: revisa la clave de Gmail" if sin_envio else "Enviado" if hay(r"enviado por correo") else "Nada que enviar",
                        "aviso" if sin_envio else "hecha" if hay(r"enviado por correo") else "omitida"))

    actividad = _mensaje(lineas[-1]) if lineas else ""
    parado = hay(r"falló diario\.py") and not activo
    encontrada = False
    for e in etapas:
        terminada = e.pop("fin")
        if terminada and not encontrada:
            continue
        if encontrada or not lineas:
            e.update(estado="pendiente", detalle="")
        elif activo:
            e.update(estado="activa", detalle=actividad)
            encontrada = True
        else:
            e.update(estado="error" if parado else "pendiente", detalle="El proceso falló aquí" if parado else "No llegó a ejecutarse")
            encontrada = True
    return etapas


def _proxima() -> str:
    orden = f"$i = Get-ScheduledTaskInfo -TaskName '{TAREA}' -ErrorAction Stop; $i.NextRunTime.ToString('yyyy-MM-ddTHH:mm')"
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", orden], capture_output=True, text=True, timeout=20, creationflags=SIN_VENTANA)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _git() -> dict:
    def ejecutar(*args):
        return subprocess.run(["git", *args], cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20, creationflags=SIN_VENTANA).stdout
    try:
        rama = ejecutar("status", "-sb").splitlines()[0]
        cambios = [l for l in ejecutar("status", "--short", "--", ".", ":!docs", ":!datos").splitlines() if l.strip()]
        adelanto = re.search(r"ahead (\d+)", rama)
        return {"sin_subir": int(adelanto.group(1)) if adelanto else 0, "sin_commit": len(cambios)}
    except (OSError, IndexError, subprocess.SubprocessError):
        return {"sin_subir": None, "sin_commit": None}


def _clave(nombre: str) -> bool:
    """Solo dice si existe; el valor nunca sale de aquí."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return bool(winreg.QueryValueEx(k, nombre)[0])
    except OSError:
        return False


def _datos() -> dict:
    _, resumen, _ = web.preparar_precios()
    variacion = lambda v: None if not v else {"pct": v["pct"], "signo": v["signo"]}
    precios = [{"region": r["region"], "tipo": r["tipo"], "valor": r["valor"], "fecha": r["fecha"],
                "semana": variacion(r["semana"]), "mes": variacion(r["mes"])} for r in resumen]
    articulos = almacen.cargar_articulos()
    return {"precios": precios, "total_articulos": len(articulos),
            "articulos": [{"titulo": a["titulo"], "fecha": a["fecha_publicacion"], "analisis": a.get("tipo") == "analisis",
                           "ficha": not a.get("redactado_con_ia"), "slug": a["slug"]} for a in articulos[:4]]}


def _instagram() -> dict | None:
    carpetas = sorted(p for p in config.INSTAGRAM.glob("*") if p.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.name)) if config.INSTAGRAM.exists() else []
    if not carpetas:
        return None
    c = carpetas[-1]
    pie = c / "texto_publicacion.txt"
    return {"fecha": c.name, "pie": pie.read_text(encoding="utf-8") if pie.exists() else "",
            "publicacion": [f"/instagram/{c.name}/publicacion/{f.name}" for f in sorted((c / "publicacion").glob("*.png"))],
            "historias": [f"/instagram/{c.name}/historias/{f.name}" for f in sorted((c / "historias").glob("*.png"))]}


def estado() -> dict:
    texto = REGISTRO.read_text(encoding="utf-8", errors="replace") if REGISTRO.exists() else ""
    lineas = ultimo_bloque(texto)
    activo = en_curso()
    cabecera = re.match(r"=== (\d{4}-\d{2}-\d{2} \d{2}:\d{2})", lineas[0]) if lineas else None
    return {
        "activo": activo,
        "inicio": cabecera.group(1) if cabecera else "",
        "etapas": analizar(lineas, activo),
        "registro": lineas[-LINEAS_REGISTRO:],
        "datos": _cacheado("datos", 3 if activo else 15, _datos),
        "instagram": _cacheado("instagram", 3 if activo else 15, _instagram),
        "git": _cacheado("git", 20, _git),
        "proxima": _cacheado("proxima", 60, _proxima),
        "hecho_hoy": ULTIMA.exists() and ULTIMA.read_text(encoding="utf-8").strip() == date.today().isoformat(),
        "claves": _cacheado("claves", 30, lambda: {"gemini": _clave("GEMINI_API_KEY"), "gmail": _clave("GMAIL_CLAVE_APP") and _clave("GMAIL_USUARIO")}),
        "web": f"https://{config.INSTAGRAM_WEB}/",
    }


def lanzar() -> bool:
    if en_curso():
        return False
    python = sys.executable.replace("pythonw.exe", "python.exe")
    subprocess.Popen([python, str(RAIZ / "pc" / "actualizar.py"), "--completa", "--forzar"], cwd=RAIZ, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=SIN_VENTANA)
    return True


class Manejador(BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:
        pass

    def _responder(self, codigo: int, cuerpo: bytes, tipo: str) -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _json(self, codigo: int, datos: dict) -> None:
        self._responder(codigo, json.dumps(datos, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def _host_valido(self) -> bool:
        return self.headers.get("Host") == f"127.0.0.1:{PUERTO}"  # evita que otra web se haga pasar por este servidor

    def do_GET(self) -> None:
        if not self._host_valido():
            return self._json(403, {"error": "Host no permitido"})
        ruta = self.path.split("?")[0]
        if ruta == "/":
            return self._responder(200, PAGINA.read_text(encoding="utf-8").replace("__TOKEN__", TOKEN).encode("utf-8"), "text/html; charset=utf-8")
        if ruta == "/api/estado":
            return self._json(200, estado())
        if ruta in ("/logo-claro.png", "/logo-oscuro.png", "/icono.png"):
            nombre = "favicon-32.png" if ruta == "/icono.png" else ruta[1:]
            return self._responder(200, (config.ESTATICOS / nombre).read_bytes(), "image/png")
        m = re.fullmatch(r"/instagram/(\d{4}-\d{2}-\d{2})/(publicacion|historias)/([\w-]+\.png)", ruta)
        if m and (archivo := config.INSTAGRAM.joinpath(*m.groups())).is_file():
            return self._responder(200, archivo.read_bytes(), "image/png")
        self._json(404, {"error": "No encontrado"})

    def do_POST(self) -> None:
        if not self._host_valido() or self.headers.get("Origin") != ORIGEN or not secrets.compare_digest(self.headers.get("X-Token", ""), TOKEN):
            return self._json(403, {"error": "Petición no permitida"})
        if self.path != "/api/ejecutar":
            return self._json(404, {"error": "No encontrado"})
        if lanzar():
            return self._json(202, {"ok": True})
        self._json(409, {"error": "Ya hay una ejecución en curso"})


def main() -> None:
    try:
        servidor = ThreadingHTTPServer(("127.0.0.1", PUERTO), Manejador)
    except OSError:
        webbrowser.open(f"{ORIGEN}/")  # ya estaba abierta
        return
    print(f"Oficina de agentes en {ORIGEN}/  (cierra esta ventana para apagarla)")
    webbrowser.open(f"{ORIGEN}/")
    servidor.serve_forever()


if __name__ == "__main__":
    main()
