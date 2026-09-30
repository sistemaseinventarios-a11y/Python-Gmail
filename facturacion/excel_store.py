"""Lectura/escritura del Excel de control (una pestaña por día, columnas A-N).

Reglas clave del documento de referencia que este módulo aplica:
- Duplicados: comparar contra TODAS las pestañas, no solo la del día (ver `buscar_duplicado`).
- Insertar cada factura en el orden cronológico correcto dentro de su pestaña.
- No alterar el formato visual: mismo formato de hora/fecha/número en todas las filas,
  sin colores ni negritas.
- Nunca sobrescribir filas existentes; solo se agregan filas nuevas.
"""

import datetime as dt
import os
import shutil

from openpyxl import Workbook, load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from . import config

FORMATO_HORA = "hh:mm:ss"
FORMATO_FECHA = "dd/mm/yyyy"
FORMATO_VALOR = "#,##0.00"

# Fragmentos (en minúsculas) usados para ubicar cada columna leyendo el
# encabezado real de cada pestaña, en vez de asumir una posición fija.
# Esto es necesario porque las pestañas antiguas tienen 13 columnas (sin
# "Hora de Recepción"), corriendo todo lo demás una posición a la izquierda.
_FRAGMENTOS_ENCABEZADO = {
    "factura": ["factura"],
    "nit": ["nit"],
    "cufe": ["cufe"],
}


def abrir_o_crear_workbook(ruta: str) -> Workbook:
    if os.path.exists(ruta):
        return load_workbook(ruta)
    return Workbook()


def _nombre_pestana(fecha: dt.date) -> str:
    return fecha.strftime("%d-%m-%Y")


def obtener_o_crear_pestana_dia(wb: Workbook, fecha: dt.date) -> Worksheet:
    nombre = _nombre_pestana(fecha)
    if nombre in wb.sheetnames:
        return wb[nombre]

    # La primera vez que se crea el workbook, openpyxl trae una hoja "Sheet" vacía por defecto.
    if wb.sheetnames == ["Sheet"] and wb["Sheet"].max_row == 1 and wb["Sheet"].max_column == 1 and wb["Sheet"]["A1"].value is None:
        hoja = wb["Sheet"]
        hoja.title = nombre
    else:
        hoja = wb.create_sheet(title=nombre)

    # Se escribe celda por celda (en vez de `append`) porque la hoja "Sheet" por
    # defecto de un Workbook nuevo arrastra un renglón fantasma que hace que
    # `append` empiece a escribir en la fila 2, dejando la 1 vacía.
    for columna, encabezado in enumerate(config.ENCABEZADOS, start=1):
        hoja.cell(row=1, column=columna, value=encabezado)
    return hoja


def _encontrar_columna(hoja: Worksheet, fragmentos: list[str]) -> int | None:
    """Busca en la fila 1 (encabezado) una celda cuyo texto contenga alguno de los fragmentos."""
    for celda in hoja[1]:
        valor = celda.value
        if not valor:
            continue
        texto = str(valor).strip().lower()
        if any(fragmento in texto for fragmento in fragmentos):
            return celda.column
    return None


def buscar_duplicado(wb: Workbook, numero_factura: str, nit: str | None, cufe: str | None):
    """Busca (numero_factura + nit) o el mismo cufe en TODAS las pestañas de día.

    Las columnas se ubican leyendo el encabezado real de cada pestaña (no una
    posición fija), porque las pestañas antiguas de 13 columnas corren la
    columna "Factura" de G a F respecto al esquema actual.

    Devuelve el nombre de la pestaña donde ya está registrada, o None si no existe.
    """
    for nombre_hoja in wb.sheetnames:
        hoja = wb[nombre_hoja]
        if hoja.max_row < 2:
            continue

        col_factura = _encontrar_columna(hoja, _FRAGMENTOS_ENCABEZADO["factura"])
        col_nit = _encontrar_columna(hoja, _FRAGMENTOS_ENCABEZADO["nit"])
        col_cufe = _encontrar_columna(hoja, _FRAGMENTOS_ENCABEZADO["cufe"])

        if col_factura is None and col_cufe is None:
            # Pestaña sin encabezados reconocibles (ej. una hoja ajena al
            # esquema de facturación): se ignora en vez de arriesgar un falso
            # positivo o negativo.
            continue

        for fila in hoja.iter_rows(min_row=2):
            factura_existente = fila[col_factura - 1].value if col_factura else None
            nit_existente = fila[col_nit - 1].value if col_nit else None
            cufe_existente = fila[col_cufe - 1].value if col_cufe else None

            if cufe and cufe_existente and str(cufe_existente).strip() == str(cufe).strip():
                return nombre_hoja
            if (
                factura_existente
                and str(factura_existente).strip() == str(numero_factura).strip()
                and nit
                and nit_existente
                and str(nit_existente).strip() == str(nit).strip()
            ):
                return nombre_hoja
    return None


def _indice_insercion_cronologico(hoja: Worksheet, hora_recepcion: dt.time) -> int:
    """Índice de fila (1-based, respecto a las filas de datos) donde debe ir la nueva factura."""
    fila_insercion = hoja.max_row + 1  # por defecto, al final
    for idx in range(2, hoja.max_row + 1):
        valor_hora = hoja.cell(row=idx, column=config.COL_HORA_RECEPCION).value
        if valor_hora is None:
            continue
        hora_existente = valor_hora if isinstance(valor_hora, dt.time) else None
        if hora_existente and hora_recepcion < hora_existente:
            fila_insercion = idx
            break
    return fila_insercion


def insertar_factura(wb: Workbook, fecha_recepcion: dt.date, hora_recepcion: dt.time, datos: dict) -> None:
    """Inserta una fila nueva en la pestaña del día, en la posición cronológica correcta.

    `datos` debe traer: fecha_remision, nit, proveedor, factura, valor_sin_iva,
    estado_houston, observacion, cufe.
    """
    hoja = obtener_o_crear_pestana_dia(wb, fecha_recepcion)
    fila_destino = _indice_insercion_cronologico(hoja, hora_recepcion)

    if fila_destino <= hoja.max_row:
        hoja.insert_rows(fila_destino)

    valores = [
        None,  # Consecutivo: se deja vacío, igual que el resto de filas
        hora_recepcion,
        fecha_recepcion,
        datos.get("fecha_remision"),
        datos.get("nit"),
        datos.get("proveedor"),
        datos.get("factura"),
        datos.get("valor_sin_iva"),
        None,  # Proyecto/Centro de costo
        None,  # Estado
        None,  # Responsable actual
        datos.get("estado_houston", config.ESTADO_HOUSTON_PROCESADO),
        datos.get("observacion"),
        datos.get("cufe"),
    ]
    for columna, valor in enumerate(valores, start=1):
        hoja.cell(row=fila_destino, column=columna, value=valor)

    hoja.cell(row=fila_destino, column=config.COL_HORA_RECEPCION).number_format = FORMATO_HORA
    hoja.cell(row=fila_destino, column=config.COL_FECHA_RECEPCION).number_format = FORMATO_FECHA
    hoja.cell(row=fila_destino, column=config.COL_FECHA_REMISION).number_format = FORMATO_FECHA
    hoja.cell(row=fila_destino, column=config.COL_VALOR_SIN_IVA).number_format = FORMATO_VALOR


def respaldar(ruta: str) -> str | None:
    """Copia el Excel actual a una subcarpeta 'backups' con fecha/hora, antes de tocarlo.

    Devuelve la ruta del respaldo, o None si el archivo todavía no existía
    (primera corrida, nada que respaldar).
    """
    if not os.path.exists(ruta):
        return None

    carpeta_backups = os.path.join(os.path.dirname(ruta), "backups")
    os.makedirs(carpeta_backups, exist_ok=True)

    nombre_base = os.path.splitext(os.path.basename(ruta))[0]
    marca_tiempo = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta_respaldo = os.path.join(carpeta_backups, f"{nombre_base}_{marca_tiempo}.xlsx")
    shutil.copy2(ruta, ruta_respaldo)
    return ruta_respaldo


def guardar(wb: Workbook, ruta: str) -> None:
    respaldar(ruta)
    wb.save(ruta)
