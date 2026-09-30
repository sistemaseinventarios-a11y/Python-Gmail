import io
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from facturacion.adjuntos import extraer_xml_y_pdf


def _crear_zip(archivos: dict) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for nombre, contenido in archivos.items():
            zf.writestr(nombre, contenido)
    return buffer.getvalue()


def test_extrae_xml_y_pdf_del_zip():
    zip_bytes = _crear_zip({"ad12345.xml": b"<Invoice></Invoice>", "fv12345.pdf": b"%PDF-1.4 contenido"})
    resultado = extraer_xml_y_pdf(zip_bytes)
    assert resultado.xml == b"<Invoice></Invoice>"
    assert resultado.pdf == b"%PDF-1.4 contenido"
    assert resultado.nombre_xml == "ad12345.xml"
    assert resultado.nombre_pdf == "fv12345.pdf"


def test_zip_sin_xml_solo_trae_pdf():
    zip_bytes = _crear_zip({"cuenta_cobro.pdf": b"%PDF-1.4 solo pdf"})
    resultado = extraer_xml_y_pdf(zip_bytes)
    assert resultado.xml is None
    assert resultado.pdf == b"%PDF-1.4 solo pdf"
