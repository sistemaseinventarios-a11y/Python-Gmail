import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from facturacion.pdf_parser import extraer_de_texto

TEXTO_EJEMPLO_SIIGO = """
Factura electrónica de venta
N°. HVA 54
CUFE:
76972bd422ce239d44380b4ab702e3deb65347132a613ae5b748896fc7dd0b040949e947211513e9dc0670563ff4eee1
Nit: 900123456-7
Subtotal: $ 1.275.000,00
"""


def test_extrae_numero_factura_sin_confundir_con_electronica():
    datos = extraer_de_texto(TEXTO_EJEMPLO_SIIGO)
    assert datos.numero_factura == "HVA54"


def test_extrae_cufe():
    datos = extraer_de_texto(TEXTO_EJEMPLO_SIIGO)
    assert datos.cufe == "76972bd422ce239d44380b4ab702e3deb65347132a613ae5b748896fc7dd0b040949e947211513e9dc0670563ff4eee1"


def test_extrae_valor_con_formato_colombiano():
    datos = extraer_de_texto(TEXTO_EJEMPLO_SIIGO)
    assert datos.valor_sin_iva == 1275000.00


def test_campos_ausentes_quedan_en_none():
    datos = extraer_de_texto("Un texto cualquiera sin datos de factura.")
    assert datos.numero_factura is None
    assert datos.cufe is None
    assert datos.nit_proveedor is None
    assert datos.valor_sin_iva is None
