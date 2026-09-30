import datetime as dt
import io
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from facturacion import extractor
from facturacion.classifier import Categoria, clasificar
from facturacion.mail_client import Adjunto, CorreoRecibido

XML_VALIDO = b"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
    <cbc:ID>ABC001</cbc:ID>
    <cbc:UUID>cufe-valido</cbc:UUID>
    <cbc:IssueDate>2026-09-08</cbc:IssueDate>
    <cac:AccountingSupplierParty>
        <cac:Party>
            <cac:PartyTaxScheme>
                <cbc:RegistrationName>Proveedor SAS</cbc:RegistrationName>
                <cbc:CompanyID>900111222</cbc:CompanyID>
            </cac:PartyTaxScheme>
        </cac:Party>
    </cac:AccountingSupplierParty>
    <cac:LegalMonetaryTotal>
        <cbc:TaxExclusiveAmount>50000.00</cbc:TaxExclusiveAmount>
        <cbc:PayableAmount>59500.00</cbc:PayableAmount>
    </cac:LegalMonetaryTotal>
</Invoice>
"""


def _zip_con(archivos: dict) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for nombre, contenido in archivos.items():
            zf.writestr(nombre, contenido)
    return buffer.getvalue()


def _correo(asunto="Factura", adjuntos=None, cuerpo=""):
    return CorreoRecibido(
        id_mensaje="<x@y.com>",
        id_imap=b"1",
        asunto=asunto,
        remitente="proveedor@ejemplo.com",
        fecha_hora_utc=dt.datetime(2026, 9, 8, 15, 0, 0),
        cuerpo_texto=cuerpo,
        adjuntos=adjuntos or [],
    )


def test_factura_con_xml_completo_no_requiere_revision():
    zip_bytes = _zip_con({"ad001.xml": XML_VALIDO, "fv001.pdf": b"%PDF fake"})
    correo = _correo(adjuntos=[Adjunto("factura.zip", zip_bytes)])
    resultado = extractor.extraer(correo, clasificar(correo))

    assert resultado.fuente_datos == "xml"
    assert resultado.numero_factura == "ABC001"
    assert resultado.cufe == "cufe-valido"
    assert resultado.requiere_revision is False


def test_factura_con_xml_incompleto_requiere_revision():
    xml_incompleto = XML_VALIDO.replace(b"<cbc:UUID>cufe-valido</cbc:UUID>", b"")
    zip_bytes = _zip_con({"ad001.xml": xml_incompleto})
    correo = _correo(adjuntos=[Adjunto("factura.zip", zip_bytes)])
    resultado = extractor.extraer(correo, clasificar(correo))

    assert resultado.fuente_datos == "xml"
    assert resultado.requiere_revision is True
    assert "cufe" in resultado.motivo_revision


def test_zip_sin_xml_cae_a_pdf_y_requiere_revision():
    zip_bytes = _zip_con({"cuenta_cobro.pdf": b"%PDF fake sin datos"})
    correo = _correo(adjuntos=[Adjunto("factura.zip", zip_bytes)])
    resultado = extractor.extraer(correo, clasificar(correo))

    assert resultado.fuente_datos == "pdf"
    assert resultado.requiere_revision is True


def test_nota_credito_siempre_requiere_revision():
    correo = _correo(asunto="900111222;Proveedor SAS;NC-05;91;Proveedor SAS")
    resultado = extractor.extraer(correo, clasificar(correo))

    assert resultado.categoria == Categoria.NOTA_CREDITO_CANDIDATA
    assert resultado.numero_factura == "NC-05"
    assert resultado.nit == "900111222"
    assert resultado.requiere_revision is True


def test_no_factura_no_requiere_revision():
    correo = _correo(asunto="Boletín semanal")
    resultado = extractor.extraer(correo, clasificar(correo))

    assert resultado.categoria == Categoria.NO_FACTURA
    assert resultado.requiere_revision is False
