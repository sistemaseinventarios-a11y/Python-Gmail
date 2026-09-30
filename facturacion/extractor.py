"""Orquesta la cascada de extracción (XML > PDF > asunto/cuerpo) para un correo
ya clasificado como candidato, y decide si el resultado es lo bastante
confiable para registrar automáticamente o si debe ir a revisión manual.

Reglas de confianza (acordadas para la versión desatendida de este proceso):
- XML con los 4 campos clave (factura, nit, cufe, valor) -> automático.
- Cualquier otra fuente (PDF, asunto/cuerpo) o XML incompleto -> revisión manual.
- Nota crédito de Siigo -> siempre revisión manual, porque la notificación no
  trae CUFE ni valor, y confirmar a qué factura aplica requiere criterio humano.
"""

import re
from dataclasses import dataclass

from . import adjuntos, classifier, pdf_parser, xml_parser
from .classifier import Categoria, ResultadoClasificacion
from .mail_client import CorreoRecibido

PATRON_CUFE_EN_TEXTO = re.compile(r"\b([a-f0-9]{80,100})\b", re.IGNORECASE)

CAMPOS_CLAVE = ("numero_factura", "nit_proveedor", "cufe", "valor_sin_iva")


@dataclass
class ResultadoExtraccion:
    categoria: Categoria
    numero_factura: str | None = None
    nit: str | None = None
    proveedor: str | None = None
    cufe: str | None = None
    valor_sin_iva: float | None = None
    fecha_emision: str | None = None
    es_nota_credito: bool = False
    fuente_datos: str | None = None  # "xml" | "pdf" | "asunto_cuerpo" | None
    contenido_adjunto: bytes | None = None
    extension_adjunto: str | None = None  # "zip" | "pdf"
    requiere_revision: bool = True
    motivo_revision: str | None = None


def _primer_adjunto(correo: CorreoRecibido, sufijo: str):
    for adjunto in correo.adjuntos:
        if adjunto.nombre_archivo.lower().endswith(sufijo):
            return adjunto
    return None


def _desde_xml(contenido_xml: bytes) -> tuple[xml_parser.DatosFactura, list[str]]:
    datos = xml_parser.parsear_xml_factura(contenido_xml)
    faltantes = [campo for campo in CAMPOS_CLAVE if getattr(datos, campo) in (None, "")]
    return datos, faltantes


def _desde_asunto_cuerpo(correo: CorreoRecibido) -> pdf_parser.DatosFacturaPdf:
    texto = f"{correo.asunto}\n{correo.cuerpo_texto}"
    coincidencia_cufe = PATRON_CUFE_EN_TEXTO.search(texto)
    return pdf_parser.DatosFacturaPdf(cufe=coincidencia_cufe.group(1) if coincidencia_cufe else None)


def extraer(correo: CorreoRecibido, clasificacion: ResultadoClasificacion) -> ResultadoExtraccion:
    if clasificacion.categoria == Categoria.NO_FACTURA:
        return ResultadoExtraccion(categoria=Categoria.NO_FACTURA, requiere_revision=False)

    if clasificacion.categoria == Categoria.NOTA_CREDITO_CANDIDATA:
        datos_nc = classifier.parsear_nota_credito_siigo(correo.asunto) or {}
        return ResultadoExtraccion(
            categoria=Categoria.NOTA_CREDITO_CANDIDATA,
            numero_factura=datos_nc.get("numero_nc"),
            nit=datos_nc.get("nit"),
            proveedor=datos_nc.get("proveedor"),
            es_nota_credito=True,
            fuente_datos="asunto_cuerpo",
            requiere_revision=True,
            motivo_revision="Nota crédito: requiere confirmar manualmente a qué factura aplica (la notificación no trae CUFE ni valor)",
        )

    # Categoria.FACTURA_CANDIDATA: intentar zip -> pdf/xml sueltos -> asunto/cuerpo.
    adjunto_zip = _primer_adjunto(correo, ".zip")
    if adjunto_zip is not None:
        contenido = adjuntos.extraer_xml_y_pdf(adjunto_zip.contenido)
        if contenido.xml is not None:
            datos, faltantes = _desde_xml(contenido.xml)
            resultado = ResultadoExtraccion(
                categoria=Categoria.FACTURA_CANDIDATA,
                numero_factura=datos.numero_factura,
                nit=datos.nit_proveedor,
                proveedor=datos.nombre_proveedor,
                cufe=datos.cufe,
                valor_sin_iva=datos.valor_sin_iva,
                fecha_emision=datos.fecha_emision,
                es_nota_credito=datos.es_nota_credito,
                fuente_datos="xml",
                contenido_adjunto=adjunto_zip.contenido,
                extension_adjunto="zip",
                requiere_revision=bool(faltantes),
                motivo_revision=f"El XML no trae: {', '.join(faltantes)}" if faltantes else None,
            )
            return resultado

        if contenido.pdf is not None:
            datos_pdf = pdf_parser.extraer_de_pdf(contenido.pdf)
            return ResultadoExtraccion(
                categoria=Categoria.FACTURA_CANDIDATA,
                numero_factura=datos_pdf.numero_factura,
                nit=datos_pdf.nit_proveedor,
                cufe=datos_pdf.cufe,
                valor_sin_iva=datos_pdf.valor_sin_iva,
                fuente_datos="pdf",
                contenido_adjunto=adjunto_zip.contenido,
                extension_adjunto="zip",
                requiere_revision=True,
                motivo_revision="El zip no trae XML; datos extraídos del PDF (baja confianza)",
            )

    adjunto_pdf_suelto = _primer_adjunto(correo, ".pdf")
    if adjunto_pdf_suelto is not None:
        datos_pdf = pdf_parser.extraer_de_pdf(adjunto_pdf_suelto.contenido)
        return ResultadoExtraccion(
            categoria=Categoria.FACTURA_CANDIDATA,
            numero_factura=datos_pdf.numero_factura,
            nit=datos_pdf.nit_proveedor,
            cufe=datos_pdf.cufe,
            valor_sin_iva=datos_pdf.valor_sin_iva,
            fuente_datos="pdf",
            contenido_adjunto=adjunto_pdf_suelto.contenido,
            extension_adjunto="pdf",
            requiere_revision=True,
            motivo_revision="Adjunto PDF suelto (sin zip/XML); baja confianza",
        )

    adjunto_xml_suelto = _primer_adjunto(correo, ".xml")
    if adjunto_xml_suelto is not None:
        datos, faltantes = _desde_xml(adjunto_xml_suelto.contenido)
        return ResultadoExtraccion(
            categoria=Categoria.FACTURA_CANDIDATA,
            numero_factura=datos.numero_factura,
            nit=datos.nit_proveedor,
            proveedor=datos.nombre_proveedor,
            cufe=datos.cufe,
            valor_sin_iva=datos.valor_sin_iva,
            fecha_emision=datos.fecha_emision,
            es_nota_credito=datos.es_nota_credito,
            fuente_datos="xml",
            contenido_adjunto=adjunto_xml_suelto.contenido,
            extension_adjunto="xml",
            requiere_revision=bool(faltantes),
            motivo_revision=f"El XML no trae: {', '.join(faltantes)}" if faltantes else None,
        )

    datos_texto = _desde_asunto_cuerpo(correo)
    return ResultadoExtraccion(
        categoria=Categoria.FACTURA_CANDIDATA,
        cufe=datos_texto.cufe,
        fuente_datos="asunto_cuerpo",
        requiere_revision=True,
        motivo_revision="Sin adjunto legible; solo se pudo revisar el asunto/cuerpo del correo",
    )
