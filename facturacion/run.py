"""Punto de entrada: una corrida completa del proceso de facturación electrónica.

Pensado para ejecutarse cada 30 min desde el Programador de tareas de Windows.
Cada corrida:
1. Calcula la ventana de tiempo a revisar (desde la última corrida exitosa).
2. Trae y clasifica cada correo nuevo de esa ventana.
3. Para las facturas/notas crédito candidatas, intenta extraer los datos
   (XML > PDF > asunto/cuerpo) y verifica duplicados contra TODO el Excel.
4. Registra automáticamente solo los casos inequívocos (XML completo, sin
   duplicado); todo lo demás va a la cola de revisión manual.
5. Dej a un log con el resumen de la corrida.

Nada de esto borra correos, adjuntos, ni sobrescribe filas existentes del
Excel de control (ver las "Prohibiciones absolutas" del documento de
referencia).
"""

import datetime as dt
import os
import traceback

from . import config, drive_folder, excel_store, extractor, mail_client, review_queue, state
from .classifier import Categoria, clasificar

RUTA_ESTADO = os.path.join(os.path.dirname(__file__), "..", "estado", "procesados.json")
RUTA_LOG = os.path.join(os.path.dirname(__file__), "..", "estado", "log_corridas.txt")
VENTANA_INICIAL_HORAS = int(os.getenv("VENTANA_INICIAL_HORAS", "24"))

OFFSET_COLOMBIA = dt.timedelta(hours=-5)


def _a_hora_colombia(fecha_hora_utc: dt.datetime) -> dt.datetime:
    return fecha_hora_utc + OFFSET_COLOMBIA


def _registrar_log(lineas: list[str]) -> None:
    os.makedirs(os.path.dirname(RUTA_LOG), exist_ok=True)
    with open(RUTA_LOG, "a", encoding="utf-8") as f:
        f.write(f"\n=== Corrida {dt.datetime.now().isoformat(timespec='seconds')} ===\n")
        for linea in lineas:
            f.write(linea + "\n")


def _guardar_pendiente(correo, resultado: extractor.ResultadoExtraccion, motivo: str) -> None:
    hora_colombia = _a_hora_colombia(correo.fecha_hora_utc)
    ruta_archivo = ""
    if resultado.contenido_adjunto and resultado.extension_adjunto:
        carpeta = drive_folder.carpeta_pendientes_del_dia(config.CARPETA_DRIVE_LOCAL, hora_colombia.date())
        ruta_archivo = drive_folder.guardar_archivo(
            carpeta,
            resultado.numero_factura or "SINNUMERO",
            resultado.proveedor or "SINPROVEEDOR",
            resultado.contenido_adjunto,
            resultado.extension_adjunto,
        )

    review_queue.agregar_pendiente(
        config.RUTA_COLA_REVISION,
        dict(
            fecha_deteccion=dt.date.today(),
            hora_recepcion=hora_colombia.time(),
            remitente=correo.remitente,
            asunto=correo.asunto,
            categoria=resultado.categoria.value,
            motivo=motivo,
            factura=resultado.numero_factura,
            nit=resultado.nit,
            proveedor=resultado.proveedor,
            valor_sin_iva=resultado.valor_sin_iva,
            cufe=resultado.cufe,
            fuente_datos=resultado.fuente_datos,
            archivo_guardado=ruta_archivo,
            id_mensaje=correo.id_mensaje,
        ),
    )


def _procesar_correo(correo, wb_excel) -> str:
    """Devuelve una descripción corta del resultado, para el log de la corrida."""
    clasificacion = clasificar(correo)

    if clasificacion.categoria == Categoria.NO_FACTURA:
        return f"NO_FACTURA: {correo.asunto!r} ({clasificacion.motivo})"

    resultado = extractor.extraer(correo, clasificacion)

    if resultado.requiere_revision:
        _guardar_pendiente(correo, resultado, resultado.motivo_revision or "Requiere revisión")
        return f"PENDIENTE_REVISION: {correo.asunto!r} — {resultado.motivo_revision}"

    # Solo llega aquí una factura con XML completo (ver extractor.extraer).
    pestana_existente = excel_store.buscar_duplicado(wb_excel, resultado.numero_factura, resultado.nit, resultado.cufe)
    if pestana_existente:
        return f"DUPLICADO: factura {resultado.numero_factura} ya está en la pestaña {pestana_existente}"

    hora_colombia = _a_hora_colombia(correo.fecha_hora_utc)
    fecha_remision = None
    if resultado.fecha_emision:
        try:
            fecha_remision = dt.date.fromisoformat(resultado.fecha_emision)
        except ValueError:
            fecha_remision = None

    carpeta_dia = drive_folder.carpeta_del_dia(config.CARPETA_DRIVE_LOCAL, hora_colombia.date())
    ruta_archivo = drive_folder.guardar_archivo(
        carpeta_dia, resultado.numero_factura, resultado.proveedor or "PROVEEDOR", resultado.contenido_adjunto, resultado.extension_adjunto
    )

    observacion = "Nota crédito" if resultado.es_nota_credito else ""

    excel_store.insertar_factura(
        wb_excel,
        hora_colombia.date(),
        hora_colombia.time(),
        dict(
            fecha_remision=fecha_remision,
            nit=resultado.nit,
            proveedor=resultado.proveedor,
            factura=resultado.numero_factura,
            valor_sin_iva=resultado.valor_sin_iva,
            observacion=observacion,
            cufe=resultado.cufe,
        ),
    )
    excel_store.guardar(wb_excel, config.RUTA_EXCEL_CONTROL)

    return f"REGISTRADA: factura {resultado.numero_factura} de {resultado.proveedor} guardada en {ruta_archivo}"


def ejecutar_corrida() -> None:
    estado = state.cargar(RUTA_ESTADO)
    ahora = dt.datetime.now(dt.timezone.utc)
    epoch_fin = int(ahora.timestamp())

    ultima_corrida = estado.get("_ultima_corrida_epoch")
    epoch_inicio = ultima_corrida if ultima_corrida else epoch_fin - VENTANA_INICIAL_HORAS * 3600

    conexion = mail_client.conectar()
    lineas_log = [
        f"Ventana: {dt.datetime.fromtimestamp(epoch_inicio, dt.timezone.utc)} a "
        f"{dt.datetime.fromtimestamp(epoch_fin, dt.timezone.utc)} (UTC)"
    ]

    try:
        ids = mail_client.obtener_ids_en_ventana(conexion, epoch_inicio, epoch_fin)
        lineas_log.append(f"Correos encontrados en la ventana (antes de filtrar por hora exacta): {len(ids)}")

        wb_excel = excel_store.abrir_o_crear_workbook(config.RUTA_EXCEL_CONTROL)

        for id_imap in ids:
            correo = mail_client.obtener_mensaje_completo(conexion, id_imap)

            if correo.fecha_hora_utc.replace(tzinfo=dt.timezone.utc).timestamp() < epoch_inicio:
                continue  # SINCE/BEFORE de IMAP trabaja por día calendario, no por hora exacta.

            if state.ya_procesado(estado, correo.id_mensaje):
                continue

            try:
                resultado_texto = _procesar_correo(correo, wb_excel)
                state.marcar(estado, correo.id_mensaje, "ok", resultado_texto)
            except Exception as error:  # noqa: BLE001 — un correo problemático no debe tumbar la corrida
                detalle_error = f"{error}\n{traceback.format_exc()}"
                _guardar_pendiente(
                    correo,
                    extractor.ResultadoExtraccion(categoria=Categoria.FACTURA_CANDIDATA),
                    f"Error inesperado procesando este correo: {error}",
                )
                state.marcar(estado, correo.id_mensaje, "error", detalle_error)
                resultado_texto = f"ERROR: {correo.asunto!r} — {error}"

            lineas_log.append(resultado_texto)

        estado["_ultima_corrida_epoch"] = epoch_fin
    finally:
        conexion.logout()
        state.guardar(RUTA_ESTADO, estado)
        _registrar_log(lineas_log)


if __name__ == "__main__":
    ejecutar_corrida()
