"""Extracción de XML/PDF desde un adjunto .zip de factura electrónica."""

import io
import zipfile
from dataclasses import dataclass


@dataclass
class ContenidoZip:
    xml: bytes | None = None
    pdf: bytes | None = None
    nombre_xml: str | None = None
    nombre_pdf: str | None = None


def extraer_xml_y_pdf(contenido_zip: bytes) -> ContenidoZip:
    resultado = ContenidoZip()
    with zipfile.ZipFile(io.BytesIO(contenido_zip)) as zf:
        for nombre in zf.namelist():
            nombre_min = nombre.lower()
            if nombre_min.endswith(".xml") and resultado.xml is None:
                resultado.xml = zf.read(nombre)
                resultado.nombre_xml = nombre
            elif nombre_min.endswith(".pdf") and resultado.pdf is None:
                resultado.pdf = zf.read(nombre)
                resultado.nombre_pdf = nombre
    return resultado
