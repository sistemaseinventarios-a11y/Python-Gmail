import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openpyxl import Workbook, load_workbook

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


def test_duplicado_se_detecta_en_pestana_antigua_de_13_columnas():
    """Pestañas antiguas no tienen 'Hora de Recepción': todo se corre una columna a la izquierda."""
    wb = Workbook()
    hoja_antigua = wb.active
    hoja_antigua.title = "01-01-2026"
    encabezados_antiguos = [h for h in excel_store.config.ENCABEZADOS if h != "Hora de Recepción"]
    for col, encabezado in enumerate(encabezados_antiguos, start=1):
        hoja_antigua.cell(row=1, column=col, value=encabezado)
    # "Factura" queda en la columna F (6) en vez de G (7) en este formato antiguo.
    hoja_antigua.cell(row=2, column=6, value="F-OLD")
    hoja_antigua.cell(row=2, column=4, value="900555666")  # Nit en columna D
    hoja_antigua.cell(row=2, column=13, value="cufe-old")  # Codigo Cufe en la última columna

    encontrado = excel_store.buscar_duplicado(wb, "F-OLD", "900555666", "cufe-old")
    assert encontrado == "01-01-2026"


def test_respaldo_se_crea_antes_de_guardar(tmp_path):
    ruta = tmp_path / "Consolidado 2026.xlsx"
    wb = Workbook()
    excel_store.insertar_factura(
        wb, dt.date(2026, 9, 8), dt.time(10, 0, 0), _nueva_factura(dt.time(10, 0, 0))
    )
    excel_store.guardar(wb, str(ruta))
    assert not (tmp_path / "backups").exists()  # primera vez: no había nada que respaldar

    # Segunda corrida: ahora sí debe respaldar el archivo antes de sobrescribirlo.
    wb2 = load_workbook(ruta)
    excel_store.insertar_factura(
        wb2, dt.date(2026, 9, 8), dt.time(11, 0, 0), _nueva_factura(dt.time(11, 0, 0), factura="F-002")
    )
    excel_store.guardar(wb2, str(ruta))

    carpeta_backups = tmp_path / "backups"
    assert carpeta_backups.exists()
    assert len(list(carpeta_backups.glob("*.xlsx"))) == 1
