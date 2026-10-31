"""Envía por Gmail el paquete del día. La cuenta y la clave van en variables de entorno: el repositorio es público."""
import logging
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

log = logging.getLogger("agente_instagram")

SERVIDOR = "smtp.gmail.com"
PUERTO = 465
TIMEOUT_S = 120


def crear_mensaje(paquete: Path, cuenta: str, asunto: str | None = None) -> EmailMessage:
    mensaje = EmailMessage()
    mensaje["Subject"] = asunto or f"AOVE al Día: contenido de Instagram del {paquete.name}"
    mensaje["From"] = cuenta
    mensaje["To"] = cuenta
    pie = (paquete / "texto_publicacion.txt").read_text(encoding="utf-8")
    guia = (paquete / "como_subirlo.txt").read_text(encoding="utf-8")
    mensaje.set_content(f"PIE DE LA PUBLICACIÓN (copia desde aquí)\n\n{pie}\n----------\n\n{guia}")
    # Con prefijo y en orden: al guardarlas en el móvil se distinguen el carrusel y las historias.
    for carpeta, prefijo in (("publicacion", "carrusel"), ("historias", "historia")):
        for imagen in sorted((paquete / carpeta).glob("*.png")):
            mensaje.add_attachment(imagen.read_bytes(), maintype="image", subtype="png", filename=f"{prefijo}-{imagen.name}")
    return mensaje


def enviar(paquete: Path, asunto: str | None = None) -> bool:
    """Devuelve True si se ha enviado. Un fallo nunca interrumpe el agente: se reintenta en la siguiente ejecución."""
    cuenta = os.environ.get("GMAIL_USUARIO")
    clave = os.environ.get("GMAIL_CLAVE_APP", "").replace(" ", "")
    if not cuenta or not clave:
        log.warning("Faltan GMAIL_USUARIO o GMAIL_CLAVE_APP: el contenido de Instagram no se envía por correo")
        return False
    try:
        mensaje = crear_mensaje(paquete, cuenta, asunto)
        with smtplib.SMTP_SSL(SERVIDOR, PUERTO, timeout=TIMEOUT_S) as smtp:
            smtp.login(cuenta, clave)
            smtp.send_message(mensaje)
    except (smtplib.SMTPException, OSError) as e:
        log.warning("No se pudo enviar el correo de Instagram: %s", e)
        return False
    log.info("Contenido de Instagram enviado por correo")
    return True
