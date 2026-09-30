import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from facturacion.xml_parser import parsear_xml_factura

XML_FACTURA_EJEMPLO = b"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
    <cbc:ID>SETP990001</cbc:ID>
    <cbc:UUID schemeName="CUFE-SHA384">abc123cufe</cbc:UUID>
    <cbc:IssueDate>2026-09-08</cbc:IssueDate>
    <cac:AccountingSupplierParty>
        <cac:Party>
            <cac:PartyTaxScheme>
                <cbc:RegistrationName>Proveedor de Prueba SAS</cbc:RegistrationName>
                <cbc:CompanyID>900123456</cbc:CompanyID>
            </cac:PartyTaxScheme>
        </cac:Party>
    </cac:AccountingSupplierParty>
    <cac:LegalMonetaryTotal>
        <cbc:LineExtensionAmount>100000.00</cbc:LineExtensionAmount>
        <cbc:TaxExclusiveAmount>100000.00</cbc:TaxExclusiveAmount>
        <cbc:TaxInclusiveAmount>119000.00</cbc:TaxInclusiveAmount>
        <cbc:PayableAmount>119000.00</cbc:PayableAmount>
    </cac:LegalMonetaryTotal>
</Invoice>
"""


def test_parsea_campos_basicos():
    datos = parsear_xml_factura(XML_FACTURA_EJEMPLO)
    assert datos.numero_factura == "SETP990001"
    assert datos.cufe == "abc123cufe"
    assert datos.fecha_emision == "2026-09-08"
    assert datos.nit_proveedor == "900123456"
    assert datos.nombre_proveedor == "Proveedor de Prueba SAS"
    assert datos.valor_sin_iva == 100000.00
    assert datos.es_nota_credito is False


def test_fallback_a_line_extension_amount_si_tax_exclusive_es_cero():
    xml_con_cero = XML_FACTURA_EJEMPLO.replace(
        b"<cbc:TaxExclusiveAmount>100000.00</cbc:TaxExclusiveAmount>",
        b"<cbc:TaxExclusiveAmount>0</cbc:TaxExclusiveAmount>",
    )
    datos = parsear_xml_factura(xml_con_cero)
    assert datos.valor_sin_iva == 100000.00


def test_detecta_nota_credito():
    xml_nc = XML_FACTURA_EJEMPLO.replace(b"Invoice", b"CreditNote")
    datos = parsear_xml_factura(xml_nc)
    assert datos.es_nota_credito is True
