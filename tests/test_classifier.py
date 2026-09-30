import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from facturacion.classifier import Categoria, clasificar, parsear_nota_credito_siigo
from facturacion.mail_client import Adjunto, CorreoRecibido


def _correo(asunto="", remitente="proveedor@ejemplo.com", adjuntos=None):
    return CorreoRecibido(
        id_mensaje="<abc@ejemplo.com>",
        id_imap=b"1",
        asunto=asunto,
        remitente=remitente,
        fecha_hora_utc=dt.datetime(2026, 9, 8, 15, 0, 0),
        cuerpo_texto="",
        adjuntos=adjuntos or [],
    )


def test_factura_candidata_por_adjunto_zip():
    correo = _correo(asunto="Factura electrónica", adjuntos=[Adjunto("z123.zip", b"contenido")])
    resultado = clasificar(correo)
    assert resultado.categoria == Categoria.FACTURA_CANDIDATA


def test_nota_credito_por_formato_siigo():
    correo = _correo(asunto="900123456;Proveedor SAS;NC-001;91;Proveedor SAS")
    resultado = clasificar(correo)
    assert resultado.categoria == Categoria.NOTA_CREDITO_CANDIDATA

    datos = parsear_nota_credito_siigo(correo.asunto)
    assert datos["nit"] == "900123456"
    assert datos["numero_nc"] == "NC-001"


def test_no_factura_sin_adjunto_ni_patron():
    correo = _correo(asunto="Boletín informativo de la semana")
    resultado = clasificar(correo)
    assert resultado.categoria == Categoria.NO_FACTURA


def test_no_factura_por_remitente_mailer_daemon():
    correo = _correo(asunto="Delivery Status Notification (Failure)", remitente="Mail Delivery Subsystem <mailer-daemon@google.com>")
    resultado = clasificar(correo)
    assert resultado.categoria == Categoria.NO_FACTURA
