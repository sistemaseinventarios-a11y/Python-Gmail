import email
import imaplib
import os
from email.header import decode_header

from dotenv import load_dotenv

IMAP_SERVER = "imap.gmail.com"
CANTIDAD_CORREOS = 5


def decodificar(texto):
    partes = decode_header(texto)
    resultado = ""
    for valor, codificacion in partes:
        if isinstance(valor, bytes):
            resultado += valor.decode(codificacion or "utf-8", errors="ignore")
        else:
            resultado += valor
    return resultado


def conectar(usuario, contrasena):
    conexion = imaplib.IMAP4_SSL(IMAP_SERVER)
    conexion.login(usuario, contrasena)
    return conexion


def obtener_ultimos_correos(conexion, cantidad):
    conexion.select("INBOX")
    _, datos = conexion.search(None, "ALL")
    ids_correos = datos[0].split()
    ultimos_ids = ids_correos[-cantidad:]
    return list(reversed(ultimos_ids))


def mostrar_correo(conexion, id_correo):
    _, datos = conexion.fetch(id_correo, "(RFC822)")
    mensaje = email.message_from_bytes(datos[0][1])

    asunto = decodificar(mensaje.get("Subject", "(sin asunto)"))
    remitente = decodificar(mensaje.get("From", "(desconocido)"))

    print(f"De: {remitente}")
    print(f"Asunto: {asunto}")
    print("-" * 60)


def main():
    load_dotenv()
    usuario = os.getenv("GMAIL_USER")
    contrasena = os.getenv("GMAIL_APP_PASSWORD")

    if not usuario or not contrasena:
        raise SystemExit(
            "Faltan GMAIL_USER o GMAIL_APP_PASSWORD. Configúralos en tu archivo .env"
        )

    conexion = conectar(usuario, contrasena)
    try:
        for id_correo in obtener_ultimos_correos(conexion, CANTIDAD_CORREOS):
            mostrar_correo(conexion, id_correo)
    finally:
        conexion.close()
        conexion.logout()


if __name__ == "__main__":
    main()
