"""Actualiza la web desde este PC y publica el resultado en GitHub.

Oleista bloquea las peticiones desde los servidores de GitHub, por eso la tarea corre aquí.

Uso:
    python pc/actualizar.py             # solo si Oleista ha publicado precios nuevos
    python pc/actualizar.py --completa  # también publica noticias aunque no haya precios nuevos
"""
import msvcrt
import os
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
REGISTRO = RAIZ / "pc" / "registro.log"
BLOQUEO = RAIZ / "pc" / "actualizar.lock"
ESPERA_TURNO_S = 600
URL_WEB = "https://manurml.github.io/web_oliva"
MAX_BYTES_REGISTRO = 500_000
SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def ejecutar(registro, *orden: str) -> int:
    entorno = os.environ | {"PYTHONIOENCODING": "utf-8", "SITIO_URL": URL_WEB, "CONTACTO_BOT": URL_WEB}
    r = subprocess.run(orden, cwd=RAIZ, env=entorno, stdin=subprocess.DEVNULL, stdout=registro,
                       stderr=subprocess.STDOUT, creationflags=SIN_VENTANA)
    return r.returncode


def esperar_turno(bloqueo, segundos: int = ESPERA_TURNO_S) -> bool:
    """Evita dos ejecuciones a la vez (al encender pueden coincidir varias tareas). Windows libera el bloqueo si el proceso muere."""
    fin = time.monotonic() + segundos
    while True:
        try:
            msvcrt.locking(bloqueo.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            if time.monotonic() >= fin:
                return False
            time.sleep(min(5, segundos))


def main() -> int:
    with BLOQUEO.open("a") as bloqueo:
        if not esperar_turno(bloqueo):
            with REGISTRO.open("a", encoding="utf-8") as registro:
                print(f"\n=== {datetime.now():%Y-%m-%d %H:%M} Otra actualización sigue en curso; se omite esta", file=registro)
            return 1
        return actualizar()


def actualizar() -> int:
    if REGISTRO.exists() and REGISTRO.stat().st_size > MAX_BYTES_REGISTRO:
        REGISTRO.unlink()
    with REGISTRO.open("a", encoding="utf-8") as registro:
        print(f"\n=== {datetime.now():%Y-%m-%d %H:%M} {' '.join(sys.argv[1:])}", file=registro, flush=True)
        python = sys.executable.replace("pythonw.exe", "python.exe")
        codigo = publicar_web(registro, python)
        # Después de publicar, para que el enlace de las historias ya funcione. Su fallo no afecta a la web.
        if not codigo and ejecutar(registro, python, "-m", "services.agent_instagram"):
            print("AVISO: no se pudo preparar el contenido de Instagram; se reintentará", file=registro)
    return codigo


def publicar_web(registro, python: str) -> int:
    if ejecutar(registro, "git", "pull", "--ff-only", "--quiet"):
        print("ERROR: no se pudo sincronizar con GitHub; no se actualiza nada", file=registro)
        return 1
    orden = [python, "diario.py"] + ([] if "--completa" in sys.argv else ["--si-hay-cambios"])
    if ejecutar(registro, *orden):
        print("ERROR: falló diario.py; no se publica nada", file=registro)
        return 1
    ejecutar(registro, "git", "add", "datos", "docs")
    if not ejecutar(registro, "git", "diff", "--cached", "--quiet"):
        print("Sin cambios que publicar", file=registro)
        return 0
    if ejecutar(registro, "git", "commit", "--quiet", "-m", f"Actualización diaria {date.today()}"):
        print("ERROR: no se pudo crear el commit", file=registro)
        return 1
    if ejecutar(registro, "git", "push", "--quiet"):
        print("ERROR: no se pudo subir a GitHub", file=registro)
        return 1
    print("Publicado", file=registro)
    return 0


if __name__ == "__main__":
    sys.exit(main())
