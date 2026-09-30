"""Extracción best-effort desde el PDF de la factura, cuando no hay XML.

El formato del PDF varía según el software de facturación de cada proveedor
(Siigo, Alegra, Facture, etc.), así que esta extracción es mucho menos
confiable que la del XML. Por diseño, cualquier dato que venga de aquí se
trata como "requiere revisión manual" en vez de registrarse automáticamente
(ver extractor.py).
"""

import re
from dataclasses import dataclass

from pypdf import PdfReader
import io

PATRON_CUFE = re.compile(r"CUFE[:\s]*([a-f0-9]{80,100})", re.IGNORECASE)
PATRON_NIT = re.compile(r"NIT[:\s.]*([\d.]{6,15}-?\d?)", re.IGNORECASE)
# "N°. HVA 54" es el formato más común visto en las representaciones gráficas
# de Siigo. Se evita coincidir con la palabra "electrónica" (que suele aparecer
# justo antes, en "Factura electrónica de venta") exigiendo el símbolo N°/No.
PATRON_FACTURA = re.compile(r"N[°ºo]\.?\s*([A-Z]{2,6}\s*-?\s*\d{1,10})", re.IGNORECASE)
PATRON_VALOR = re.compile(r"(?:Subtotal|Valor sin iva|Base gravable)[:\s]*\$?\s*([\d.,]+)", re.IGNORECASE)


@dataclass
class DatosFacturaPdf:
    numero_factura: str | None = None
    cufe: str | None = None
    nit_proveedor: str | None = None
    valor_sin_iva: float | None = None


def _texto_del_pdf(contenido_pdf: bytes) -> str:
    lector = PdfReader(io.BytesIO(contenido_pdf))
    return "\n".join(pagina.extract_text() or "" for pagina in lector.pages)


def _a_float(texto_valor: str) -> float | None:
    limpio = texto_valor.replace(".", "").replace(",", ".")
    try:
        return float(limpio)
    except ValueError:
        return None


def extraer_de_texto(texto: str) -> DatosFacturaPdf:
    cufe = PATRON_CUFE.search(texto)
    nit = PATRON_NIT.search(texto)
    factura = PATRON_FACTURA.search(texto)
    valor = PATRON_VALOR.search(texto)

    return DatosFacturaPdf(
        numero_factura=re.sub(r"\s+", "", factura.group(1)) if factura else None,
        cufe=cufe.group(1) if cufe else None,
        nit_proveedor=nit.group(1).replace(".", "") if nit else None,
        valor_sin_iva=_a_float(valor.group(1)) if valor else None,
    )


def extraer_de_pdf(contenido_pdf: bytes) -> DatosFacturaPdf:
    return extraer_de_texto(_texto_del_pdf(contenido_pdf))
