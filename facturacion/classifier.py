"""Clasificación inicial de cada correo (paso 3 del procedimiento de referencia).

Esta primera pasada solo decide si un correo es CANDIDATO a factura/nota crédito
o si claramente no lo es. La distinción final entre "factura nueva" y
"duplicado" se resuelve después, comparando contra el Excel de control
(ver excel_store.buscar_duplicado) — no aquí, porque eso requiere haber
extraído ya el número de factura/NIT/CUFE.

Ante cualquier ambigüedad este módulo prefiere clasificar como candidata
(para que el caso llegue a la cola de revisión) en vez de descartarla
silenciosamente como "no factura": la meta del proceso es cero facturas
escapadas.
"""

import re
from dataclasses import dataclass
from enum import Enum

from .mail_client import CorreoRecibido

# Notificación de nota crédito de Siigo: <NIT>;<Proveedor>;<NumeroNC>;91;<Proveedor>
PATRON_NOTA_CREDITO_SIIGO = re.compile(r"^\s*\d+;[^;]*;[^;]*;91;[^;]*\s*$")

REMITENTES_RUIDO_CONOCIDO = (
    "mailer-daemon",
    "postmaster",
)

ASUNTOS_NO_FACTURA_CONOCIDOS = (
    "delivery status notification",
    "undeliverable",
    "certificado de retencion",
    "certificado de retención",
    "reteica",
)


class Categoria(Enum):
    FACTURA_CANDIDATA = "factura_candidata"
    NOTA_CREDITO_CANDIDATA = "nota_credito_candidata"
    NO_FACTURA = "no_factura"


@dataclass
class ResultadoClasificacion:
    categoria: Categoria
    motivo: str


def _tiene_adjunto_relevante(correo: CorreoRecibido) -> bool:
    for adjunto in correo.adjuntos:
        nombre = adjunto.nombre_archivo.lower()
        if nombre.endswith(".zip") or nombre.endswith(".pdf") or nombre.endswith(".xml"):
            return True
    return False


def clasificar(correo: CorreoRecibido) -> ResultadoClasificacion:
    asunto_normalizado = (correo.asunto or "").strip().lower()
    remitente_normalizado = (correo.remitente or "").strip().lower()

    if PATRON_NOTA_CREDITO_SIIGO.match(correo.asunto or ""):
        return ResultadoClasificacion(
            Categoria.NOTA_CREDITO_CANDIDATA, "Asunto coincide con el formato de nota crédito de Siigo (código 91)"
        )

    if _tiene_adjunto_relevante(correo):
        return ResultadoClasificacion(
            Categoria.FACTURA_CANDIDATA, "Trae adjunto .zip/.pdf/.xml que podría ser una factura"
        )

    if any(patron in remitente_normalizado for patron in REMITENTES_RUIDO_CONOCIDO):
        return ResultadoClasificacion(Categoria.NO_FACTURA, "Remitente de notificación automática de entrega")

    if any(patron in asunto_normalizado for patron in ASUNTOS_NO_FACTURA_CONOCIDOS):
        return ResultadoClasificacion(Categoria.NO_FACTURA, "Asunto coincide con un tipo de correo conocido sin factura")

    # Cualquier otro caso sin adjunto ni coincidencia clara: se descarta como
    # "no factura" solo cuando no hay ningún indicio de documento adjunto.
    # Nota: a diferencia del agente de IA original (que podía reabrir el
    # correo con "format: full" para confirmar), este script ve directamente
    # el mensaje completo por IMAP, así que si no hay adjunto aquí, no lo hay.
    return ResultadoClasificacion(Categoria.NO_FACTURA, "Sin adjunto relevante ni coincidencia con patrones conocidos")


def parsear_nota_credito_siigo(asunto: str) -> dict | None:
    """Extrae NIT/proveedor/número de la notificación de nota crédito de Siigo."""
    if not PATRON_NOTA_CREDITO_SIIGO.match(asunto or ""):
        return None
    partes = [p.strip() for p in asunto.strip().split(";")]
    if len(partes) < 5:
        return None
    return {
        "nit": partes[0],
        "proveedor": partes[1],
        "numero_nc": partes[2],
        "codigo_documento": partes[3],
    }
