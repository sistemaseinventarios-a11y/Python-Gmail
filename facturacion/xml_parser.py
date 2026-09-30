"""Extracción de datos de facturas/notas crédito electrónicas colombianas (UBL 2.1 / DIAN).

Prioridad de fuente de datos (ver Prompt_Facturacion_Electronica_Actual.docx):
1. XML dentro del zip/adjunto (este módulo).
2. PDF adjunto (pdf_parser.py) si no hay XML.
3. Asunto/cuerpo del correo, como último recurso.

Este módulo NUNCA inventa valores: si un campo no aparece en el XML, queda en None
y le corresponde al llamador decidir si intenta el siguiente nivel de la cascada.
"""

from dataclasses import dataclass
from xml.etree import ElementTree as ET


@dataclass
class DatosFactura:
    numero_factura: str | None = None
    cufe: str | None = None
    fecha_emision: str | None = None  # YYYY-MM-DD, tal como viene en el XML
    nit_proveedor: str | None = None
    nombre_proveedor: str | None = None
    valor_sin_iva: float | None = None
    es_nota_credito: bool = False


def _local_tag(elemento):
    tag = elemento.tag
    return tag.split("}", 1)[1] if "}" in tag else tag


def _sin_bom_inicial(texto: str) -> str:
    """Quita un BOM (\\ufeff) y espacios en blanco antes de "<?xml".

    Algunos proveedores dejan un BOM colado dentro del CDATA del
    AttachedDocument; si queda antes de la declaración "<?xml ...?>",
    ET.fromstring falla con "XML or text declaration not at start of entity"
    aunque el contenido en sí sea válido.
    """
    return texto.lstrip("﻿ \t\r\n")


def _buscar_texto(raiz, nombre_local):
    """Devuelve el texto del primer elemento cuyo tag local coincida, ignorando namespaces."""
    for nodo in raiz.iter():
        if _local_tag(nodo) == nombre_local and nodo.text and nodo.text.strip():
            return nodo.text.strip()
    return None


def _buscar_float(raiz, nombre_local):
    texto = _buscar_texto(raiz, nombre_local)
    if texto is None:
        return None
    try:
        return float(texto)
    except ValueError:
        return None


def _extraer_nit_proveedor(raiz):
    """NIT y nombre del proveedor desde cac:AccountingSupplierParty."""
    for nodo in raiz.iter():
        if _local_tag(nodo) == "AccountingSupplierParty":
            nit = None
            nombre = None
            for sub in nodo.iter():
                etiqueta = _local_tag(sub)
                if etiqueta == "CompanyID" and sub.text and sub.text.strip():
                    nit = sub.text.strip()
                elif etiqueta == "RegistrationName" and sub.text and sub.text.strip():
                    nombre = sub.text.strip()
            return nit, nombre
    return None, None


def _desenvolver_attached_document(raiz):
    """Si el XML es un AttachedDocument de la DIAN, extrae el Invoice/CreditNote embebido.

    Muchos proveedores envían el "documento adjunto" (AttachedDocument) con la factura
    real incrustada como texto/CDATA dentro de cac:Attachment. Si no se desenvuelve,
    los campos de negocio (NIT, CUFE, valores) no se encuentran.
    """
    if _local_tag(raiz) != "AttachedDocument":
        return raiz

    for nodo in raiz.iter():
        if _local_tag(nodo) == "Description" and nodo.text and "<Invoice" in nodo.text:
            return ET.fromstring(_sin_bom_inicial(nodo.text))
        if _local_tag(nodo) == "Description" and nodo.text and "<CreditNote" in nodo.text:
            return ET.fromstring(_sin_bom_inicial(nodo.text))
    return raiz


def parsear_xml_factura(contenido_xml: bytes) -> DatosFactura:
    # bytes.lstrip acepta bytes de la marca BOM UTF-8 y de espacios en blanco;
    # protege igual que _sin_bom_inicial pero a nivel de bytes crudos.
    contenido_xml = contenido_xml.lstrip(b"\xef\xbb\xbf \t\r\n")
    raiz = ET.fromstring(contenido_xml)
    raiz = _desenvolver_attached_document(raiz)

    es_nota_credito = _local_tag(raiz) == "CreditNote"

    nit, nombre = _extraer_nit_proveedor(raiz)

    valor_sin_iva = _buscar_float(raiz, "TaxExclusiveAmount")
    if valor_sin_iva in (None, 0.0):
        valor_line_extension = _buscar_float(raiz, "LineExtensionAmount")
        valor_payable = _buscar_float(raiz, "PayableAmount")
        # Si TaxExclusiveAmount no vino o vino en 0, usar LineExtensionAmount,
        # pero solo si no se aleja de forma anómala del total a pagar.
        if valor_line_extension is not None:
            if valor_payable is None or valor_line_extension <= valor_payable * 1.01:
                valor_sin_iva = valor_line_extension

    return DatosFactura(
        numero_factura=_buscar_texto(raiz, "ID"),
        cufe=_buscar_texto(raiz, "UUID"),
        fecha_emision=_buscar_texto(raiz, "IssueDate"),
        nit_proveedor=nit,
        nombre_proveedor=nombre,
        valor_sin_iva=valor_sin_iva,
        es_nota_credito=es_nota_credito,
    )
