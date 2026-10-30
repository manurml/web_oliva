"""Actualiza la web desde este PC y publica el resultado en GitHub.

Oleista bloquea las peticiones desde los servidores de GitHub, por eso la tarea corre aquí.

Uso:
    python pc/actualizar.py             # solo si Oleista ha publicado precios nuevos
    python pc/actualizar.py --completa  # también publica noticias aunque no haya precios nuevos
"""
import os
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
REGISTRO = RAIZ / "pc" / "registro.log"
URL_WEB = "https://manurml.github.io/web_oliva"
MAX_BYTES_REGISTRO = 500_000
SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def ejecutar(registro, *orden: str) -> int:
    entorno = os.environ | {"PYTHONIOENCODING": "utf-8", "SITIO_URL": URL_WEB, "CONTACTO_BOT": URL_WEB}
    r = subprocess.run(orden, cwd=RAIZ, env=entorno, stdin=subprocess.DEVNULL, stdout=registro,
                       stderr=subprocess.STDOUT, creationflags=SIN_VENTANA)
    return r.returncode


def main() -> int:
    if REGISTRO.exists() and REGISTRO.stat().st_size > MAX_BYTES_REGISTRO:
        REGISTRO.unlink()
    with REGISTRO.open("a", encoding="utf-8") as registro:
        print(f"\n=== {datetime.now():%Y-%m-%d %H:%M} {' '.join(sys.argv[1:])}", file=registro, flush=True)
        if ejecutar(registro, "git", "pull", "--ff-only", "--quiet"):
            print("ERROR: no se pudo sincronizar con GitHub; no se actualiza nada", file=registro)
            return 1
        python = sys.executable.replace("pythonw.exe", "python.exe")
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
