#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
error_handler.py
Manejador centralizado de errores para el workflow PACS.
Ante cualquier error crítico:
  1. Toma captura de pantalla completa
  2. Consulta los datos del registro 'En Proceso' en BD
  3. Envía mensaje de texto a Telegram (descripción + datos)
  4. Envía la captura de pantalla a Telegram
  5. Marca el registro como 'Error' en BD
  6. Termina el script con sys.exit(1)
"""

import sys
import os
import logging
import mysql.connector
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# ─── Configuración BD ───────────────────────────────────────────────────────
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "ris"
}

# ─── Ruta raíz del proyecto ──────────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent.parent  # → rpa_framework/
sys.path.insert(0, str(ROOT_DIR))


def _get_telegram():
    """Importa las funciones de Telegram de manera robusta."""
    try:
        from utils.telegram_manager import enviar_alerta_todos, enviar_foto_todos
        return enviar_alerta_todos, enviar_foto_todos
    except ImportError:
        pass
    try:
        from rpa_framework.utils.telegram_manager import enviar_alerta_todos, enviar_foto_todos
        return enviar_alerta_todos, enviar_foto_todos
    except ImportError:
        pass
    # Fallback: funciones nulas
    def _noop(*a, **kw): pass
    return _noop, _noop


def _tomar_screenshot():
    """Toma captura de pantalla completa. Devuelve la ruta del archivo o None."""
    try:
        import pyautogui
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        ruta = str(ROOT_DIR / "log" / f"error_{ts}.png")
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        pyautogui.screenshot(ruta)
        logger.info(f"Screenshot guardado en: {ruta}")
        return ruta
    except Exception as e:
        logger.error(f"No se pudo tomar screenshot: {e}")
        return None


def _consultar_registro():
    """Consulta el registro 'En Proceso' desde la BD. Devuelve dict o None."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        query = """
        SELECT inicio, doctor_detectado, numero_documento, fecha_agendada,
               patologia_critica, patologia_critica_detectada, examen, URL
        FROM ris.registro_acciones
        WHERE estado = 'En Proceso'
        LIMIT 1
        """
        cursor.execute(query)
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return row
    except Exception as e:
        logger.error(f"Error consultando registro en BD: {e}")
        return None


def _marcar_error(script_name, error_description):
    """Actualiza el registro 'En Proceso' a 'Error' en BD."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        obs = f"[{script_name}] {error_description}"[:500]  # limitar largo
        query = """
        UPDATE ris.registro_acciones
        SET estado = 'Error', diagnostico = CONCAT(IFNULL(diagnostico,''), ' | ERROR: ', %s), `update` = NOW()
        WHERE estado = 'En Proceso'
        """
        cursor.execute(query, (obs,))
        conn.commit()
        rows_affected = cursor.rowcount
        cursor.close()
        conn.close()
        logger.info(f"Registro marcado como 'Error' ({rows_affected} filas afectadas).")
    except Exception as e:
        logger.error(f"Error actualizando estado en BD: {e}")


def _formatear_mensaje(script_name, error_description, record_data):
    """Genera el texto del mensaje Telegram con formato HTML."""
    lineas = [
        f"🚨 <b>ERROR en {script_name}</b>",
        "",
        f"📋 <b>Problema:</b>",
        f"{error_description}",
        "",
    ]

    if record_data:
        lineas.append("─── <b>Datos del Registro</b> ───")

        labels = {
            "inicio":                   "🕐 Inicio",
            "doctor_detectado":         "👨‍⚕️ Doctor",
            "numero_documento":         "🪪 N° Documento",
            "fecha_agendada":           "📅 Fecha agendada",
            "patologia_critica":        "⚠️ Patología crítica",
            "patologia_critica_detectada": "🔬 Patología detectada",
            "examen":                   "🩻 Examen",
            "URL":                      "🔗 URL",
        }

        for campo, etiqueta in labels.items():
            valor = record_data.get(campo)
            if valor is not None and str(valor).strip() not in ("", "None", "null"):
                lineas.append(f"  {etiqueta}: <code>{valor}</code>")
    else:
        lineas.append("<i>⚠️ No se encontró registro con estado 'En Proceso'.</i>")

    return "\n".join(lineas)


def handle_error_and_exit(script_name: str, error_description: str):
    """
    Punto de entrada único para errores críticos en el workflow PACS.

    Pasos:
      1. Toma screenshot completo
      2. Consulta datos del registro en BD
      3. Envía mensaje de texto a Telegram (descripción + datos)
      4. Envía el screenshot a Telegram
      5. Marca el registro como 'Error' en BD
      6. sys.exit(1)
    """
    print(f"\n[ERROR_HANDLER] ERROR CRÍTICO en '{script_name}': {error_description}", flush=True)
    logger.error(f"❌ [{script_name}] {error_description}")

    # 1. Screenshot
    screenshot_path = _tomar_screenshot()

    # 2. Datos del registro
    record_data = _consultar_registro()

    # 3. Mensaje de texto
    mensaje = _formatear_mensaje(script_name, error_description, record_data)

    # 4. Enviar a Telegram
    enviar_alerta_todos, enviar_foto_todos = _get_telegram()

    try:
        # Siempre enviar el texto primero (sin límite de chars)
        enviar_alerta_todos(mensaje)
        logger.info("Mensaje de texto enviado a Telegram.")
    except Exception as e:
        logger.error(f"Error enviando texto a Telegram: {e}")

    try:
        # Enviar la imagen como foto separada con caption corto
        if screenshot_path and os.path.exists(screenshot_path):
            caption = f"📸 Captura del error en <b>{script_name}</b>"
            enviar_foto_todos(screenshot_path, caption)
            logger.info("Screenshot enviado a Telegram.")
    except Exception as e:
        logger.error(f"Error enviando foto a Telegram: {e}")

    # 5. Marcar como Error en BD
    _marcar_error(script_name, error_description)

    # 6. Salir
    sys.exit(1)
