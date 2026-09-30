"""Registro de qué correos ya se procesaron, para no repetir trabajo cada 30 min.

Es un archivo JSON local (no vive en Drive): es un detalle interno de esta
instalación, no un documento que el equipo deba revisar.
"""

import json
import os


def cargar(ruta: str) -> dict:
    if not os.path.exists(ruta):
        return {}
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def guardar(ruta: str, estado: dict) -> None:
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)


def ya_procesado(estado: dict, id_mensaje: str) -> bool:
    return id_mensaje in estado


def marcar(estado: dict, id_mensaje: str, resultado: str, detalle: str = "") -> None:
    estado[id_mensaje] = {"resultado": resultado, "detalle": detalle}
