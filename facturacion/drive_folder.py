"""Guardado de ZIP/PDF en la carpeta de Drive sincronizada localmente.

Una subcarpeta por día dentro de CARPETA_DRIVE_LOCAL, tal como pide el
documento de referencia. Los casos que van a la cola de revisión se guardan
aparte, en una subcarpeta "_Pendientes_revision", para no perderlos pero sin
mezclarlos con las facturas ya confirmadas.
"""

import datetime as dt
import os
import re

NOMBRE_CARPETA_PENDIENTES = "_Pendientes_revision"


def _nombre_seguro(texto: str) -> str:
    """Quita caracteres inválidos para nombres de archivo/carpeta en Windows."""
    return re.sub(r'[<>:"/\\|?*]', "_", texto).strip()


def carpeta_del_dia(carpeta_base: str, fecha: dt.date) -> str:
    ruta = os.path.join(carpeta_base, fecha.strftime("%d-%m-%Y"))
    os.makedirs(ruta, exist_ok=True)
    return ruta


def carpeta_pendientes_del_dia(carpeta_base: str, fecha: dt.date) -> str:
    ruta = os.path.join(carpeta_base, NOMBRE_CARPETA_PENDIENTES, fecha.strftime("%d-%m-%Y"))
    os.makedirs(ruta, exist_ok=True)
    return ruta


def guardar_archivo(carpeta_destino: str, numero_factura: str, proveedor: str, contenido: bytes, extension: str) -> str:
    """Guarda el archivo como FACTURA_<numero>_<proveedor_corto>.<ext> y devuelve la ruta final.

    Si el nombre ya existe (por ejemplo, un reintento tras un corte a mitad de
    corrida), se le agrega un sufijo numérico en vez de sobrescribir el
    archivo existente.
    """
    proveedor_corto = _nombre_seguro(proveedor)[:30] or "PROVEEDOR"
    numero_seguro = _nombre_seguro(numero_factura) or "SINNUMERO"
    nombre_base = f"FACTURA_{numero_seguro}_{proveedor_corto}"

    ruta_destino = os.path.join(carpeta_destino, f"{nombre_base}.{extension}")
    contador = 1
    while os.path.exists(ruta_destino):
        ruta_destino = os.path.join(carpeta_destino, f"{nombre_base}_{contador}.{extension}")
        contador += 1

    with open(ruta_destino, "wb") as f:
        f.write(contenido)
    return ruta_destino
