"""Configuración compartida: rutas y esquema de columnas del Excel de control."""

import os

from dotenv import load_dotenv

load_dotenv()

ZONA_HORARIA_COLOMBIA = "America/Bogota"

# Carpeta local sincronizada por "Google Drive para escritorio" donde se crean
# las subcarpetas por día con los ZIP/PDF de cada factura.
CARPETA_DRIVE_LOCAL = os.getenv("CARPETA_DRIVE_LOCAL")

# Ruta completa del Excel de control (Consolidado 2026.xlsx), que puede vivir
# en otra ubicación de Drive distinta a la carpeta de adjuntos.
RUTA_EXCEL_CONTROL = os.getenv("RUTA_EXCEL_CONTROL")

# Columnas A-N según el esquema del documento de referencia.
ENCABEZADOS = [
    "Consecutivo",
    "Hora de Recepción",
    "Fecha recepción FE",
    "Fecha remisión FR",
    "Nit",
    "Proveedor",
    "Factura",
    "Valor sin iva",
    "Proyecto/Centro de costo",
    "Estado",
    "Responsable actual",
    "Estado Houston",
    "Observación",
    "Codigo Cufe",
]

COL_HORA_RECEPCION = 2
COL_FECHA_RECEPCION = 3
COL_FECHA_REMISION = 4
COL_NIT = 5
COL_PROVEEDOR = 6
COL_FACTURA = 7
COL_VALOR_SIN_IVA = 8
COL_ESTADO_HOUSTON = 12
COL_OBSERVACION = 13
COL_CUFE = 14

ESTADO_HOUSTON_PROCESADO = "PROCESADO"
