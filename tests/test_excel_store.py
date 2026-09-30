import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openpyxl import Workbook

from facturacion import excel_store


def _nueva_factura(hora, factura="F-001", nit="900111222", cufe="cufe-1"):
    return dict(
        fecha_remision=dt.date(2026, 9, 8),
        nit=nit,
        proveedor="Proveedor SAS",
        factura=factura,
        valor_sin_iva=100000.0,
        observacion="",
        cufe=cufe,
    )


def test_inserta_en_pestana_del_dia_con_encabezados():
    wb = Workbook()
    fecha = dt.date(2026, 9, 8)
    excel_store.insertar_factura(wb, fecha, dt.time(10, 0, 0), _nueva_factura(dt.time(10, 0, 0)))

    hoja = wb["08-09-2026"]
    assert hoja["A1"].value == "Consecutivo"
    assert hoja.cell(row=2, column=excel_store.config.COL_FACTURA).value == "F-001"


def test_insercion_cronologica():
    wb = Workbook()
    fecha = dt.date(2026, 9, 8)
    excel_store.insertar_factura(wb, fecha, dt.time(10, 0, 0), _nueva_factura(dt.time(10, 0, 0), factura="F-A"))
    excel_store.insertar_factura(wb, fecha, dt.time(14, 0, 0), _nueva_factura(dt.time(14, 0, 0), factura="F-C"))
    # Esta debe insertarse en medio de las dos anteriores.
    excel_store.insertar_factura(wb, fecha, dt.time(12, 0, 0), _nueva_factura(dt.time(12, 0, 0), factura="F-B"))

    hoja = wb["08-09-2026"]
    facturas_en_orden = [
        hoja.cell(row=fila, column=excel_store.config.COL_FACTURA).value for fila in range(2, hoja.max_row + 1)
    ]
    assert facturas_en_orden == ["F-A", "F-B", "F-C"]


def test_duplicado_se_detecta_en_cualquier_pestana():
    wb = Workbook()
    excel_store.insertar_factura(
        wb, dt.date(2026, 9, 1), dt.time(9, 0, 0), _nueva_factura(dt.time(9, 0, 0), factura="F-999", cufe="cufe-999")
    )

    # Buscar por mismo CUFE, reportado el día 3 (otra pestaña).
    encontrado = excel_store.buscar_duplicado(wb, "F-999", "900111222", "cufe-999")
    assert encontrado == "01-09-2026"

    no_encontrado = excel_store.buscar_duplicado(wb, "F-000", "900999999", "otro-cufe")
    assert no_encontrado is None
