"""Lectura de la bandeja de facturaelectronica@disico.com.co por IMAP.

Solo lectura: este módulo nunca borra correos ni adjuntos, ni envía nada
(coincide con las "Prohibiciones absolutas" del documento de referencia).
"""

import datetime as dt
import email
import imaplib
import os
from dataclasses import dataclass, field
from email.header import decode_header
from email.message import Message
from email.utils import parsedate_to_datetime

IMAP_SERVER = "imap.gmail.com"


@dataclass
class Adjunto:
    nombre_archivo: str
    contenido: bytes


@dataclass
class CorreoRecibido:
    id_mensaje: str  # Message-Id real del correo (para trazabilidad y para no reprocesar)
    id_imap: bytes  # ID interno de IMAP en esta sesión (usado solo para el FETCH)
    asunto: str
    remitente: str
    fecha_hora_utc: dt.datetime
    cuerpo_texto: str
    adjuntos: list[Adjunto] = field(default_factory=list)


def _decodificar(texto: str) -> str:
    partes = decode_header(texto or "")
    resultado = ""
    for valor, codificacion in partes:
        if isinstance(valor, bytes):
            resultado += valor.decode(codificacion or "utf-8", errors="ignore")
        else:
            resultado += valor
    return resultado


def conectar() -> imaplib.IMAP4_SSL:
    usuario = os.getenv("GMAIL_USER")
    contrasena = os.getenv("GMAIL_APP_PASSWORD")
    if not usuario or not contrasena:
        raise SystemExit("Faltan GMAIL_USER o GMAIL_APP_PASSWORD en el archivo .env")

    conexion = imaplib.IMAP4_SSL(IMAP_SERVER)
    conexion.login(usuario, contrasena)
    return conexion


def obtener_ids_en_ventana(conexion: imaplib.IMAP4_SSL, epoch_inicio: int, epoch_fin: int) -> list[bytes]:
    """Todos los IDs de mensajes cuya fecha esté en [epoch_inicio, epoch_fin).

    Usa el criterio SINCE/BEFORE de IMAP (que trabaja por día calendario, no por
    hora exacta) y luego filtra por fecha/hora real de cada mensaje, para evitar
    perder o incluir de más correos en los bordes del rango.
    """
    conexion.select("INBOX", readonly=True)

    fecha_desde = dt.datetime.utcfromtimestamp(epoch_inicio).strftime("%d-%b-%Y")
    fecha_hasta = (dt.datetime.utcfromtimestamp(epoch_fin) + dt.timedelta(days=1)).strftime("%d-%b-%Y")

    _, datos = conexion.search(None, f'(SINCE "{fecha_desde}" BEFORE "{fecha_hasta}")')
    return datos[0].split()


def _extraer_cuerpo_y_adjuntos(mensaje: Message) -> tuple[str, list[Adjunto]]:
    cuerpo = ""
    adjuntos = []

    if mensaje.is_multipart():
        for parte in mensaje.walk():
            disposicion = str(parte.get("Content-Disposition", ""))
            nombre = parte.get_filename()

            if nombre:
                contenido = parte.get_payload(decode=True)
                if contenido:
                    adjuntos.append(Adjunto(nombre_archivo=_decodificar(nombre), contenido=contenido))
            elif parte.get_content_type() == "text/plain" and "attachment" not in disposicion:
                carga = parte.get_payload(decode=True)
                if carga:
                    cuerpo += carga.decode(parte.get_content_charset() or "utf-8", errors="ignore")
    else:
        carga = mensaje.get_payload(decode=True)
        if carga:
            cuerpo = carga.decode(mensaje.get_content_charset() or "utf-8", errors="ignore")

    return cuerpo, adjuntos


def obtener_mensaje_completo(conexion: imaplib.IMAP4_SSL, id_imap: bytes) -> CorreoRecibido:
    _, datos = conexion.fetch(id_imap, "(RFC822)")
    mensaje = email.message_from_bytes(datos[0][1])

    fecha_hora = parsedate_to_datetime(mensaje.get("Date"))
    if fecha_hora.tzinfo is not None:
        fecha_hora_utc = fecha_hora.astimezone(dt.timezone.utc).replace(tzinfo=None)
    else:
        fecha_hora_utc = fecha_hora

    cuerpo, adjuntos = _extraer_cuerpo_y_adjuntos(mensaje)

    return CorreoRecibido(
        id_mensaje=mensaje.get("Message-Id", "").strip(),
        id_imap=id_imap,
        asunto=_decodificar(mensaje.get("Subject", "")),
        remitente=_decodificar(mensaje.get("From", "")),
        fecha_hora_utc=fecha_hora_utc,
        cuerpo_texto=cuerpo,
        adjuntos=adjuntos,
    )
