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
    """Toma captura de pantalla completa de forma resiliente. Devuelve la ruta del archivo o None."""
    try:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        ruta = str(ROOT_DIR / "log" / f"error_{ts}.png")
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        
        # 1. Intentar con safe_screenshot (mss)
        try:
            from utils.screen_utils import safe_screenshot
        except ImportError:
            try:
                from rpa_framework.utils.screen_utils import safe_screenshot
            except ImportError:
                safe_screenshot = None
                
        if safe_screenshot:
            img = safe_screenshot(filepath=ruta)
            if img:
                logger.info(f"Screenshot guardado con safe_screenshot en: {ruta}")
                return ruta

        # 2. Fallback con pyautogui
        import pyautogui
        pyautogui.screenshot(ruta)
        logger.info(f"Screenshot guardado con pyautogui en: {ruta}")
        return ruta
    except Exception as e:
        logger.error(f"No se pudo tomar screenshot: {e}")
        return None


def _consultar_registro(record_id=None):
    """Consulta el registro 'En Proceso' o por ID desde la BD. Devuelve dict o None."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        if record_id:
            query = """
            SELECT id, inicio, doctor_detectado, numero_documento, fecha_agendada,
                   patologia_critica, patologia_critica_detectada, examen, URL,
                   resolucion_pantalla
            FROM ris.registro_acciones
            WHERE id = %s
            LIMIT 1
            """
            cursor.execute(query, (record_id,))
            row = cursor.fetchone()
        else:
            query = """
            SELECT id, inicio, doctor_detectado, numero_documento, fecha_agendada,
                   patologia_critica, patologia_critica_detectada, examen, URL,
                   resolucion_pantalla
            FROM ris.registro_acciones
            WHERE estado = 'En Proceso'
            ORDER BY id DESC
            LIMIT 1
            """
            cursor.execute(query)
            row = cursor.fetchone()

            # Si no se encontró en 'En Proceso', fallback al último registro de registro_acciones
            if not row:
                cursor.execute("""
                SELECT id, inicio, doctor_detectado, numero_documento, fecha_agendada,
                       patologia_critica, patologia_critica_detectada, examen, URL,
                       resolucion_pantalla
                FROM ris.registro_acciones
                ORDER BY id DESC
                LIMIT 1
                """)
                row = cursor.fetchone()

        cursor.close()
        conn.close()
        return row
    except Exception as e:
        logger.error(f"Error consultando registro en BD: {e}")
        return None


def _marcar_error(script_name, error_description, record_id=None):
    """Actualiza el registro a 'Error' en BD por record_id o 'En Proceso'."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        obs = f"[{script_name}] {error_description}"[:500]  # limitar largo
        if record_id:
            query = """
            UPDATE ris.registro_acciones
            SET estado = 'Error', observacion = %s, `update` = NOW()
            WHERE id = %s
            """
            cursor.execute(query, (obs, record_id))
        else:
            query = """
            UPDATE ris.registro_acciones
            SET estado = 'Error', observacion = %s, `update` = NOW()
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
    """Genera el texto del mensaje Telegram con formato HTML incluyendo resolución de pantalla."""
    rec_id = record_data.get("id") if (record_data and isinstance(record_data, dict)) else None
    id_header = f" (Fila #{rec_id})" if rec_id else ""
    lineas = [
        f"🚨 <b>ERROR en {script_name}</b>{id_header}",
        "",
        f"📋 <b>Problema:</b>",
        f"{error_description}",
        "",
    ]

    # Obtener resolución actual como fallback si no está en BD
    resolucion_actual = None
    try:
        from utils.screen_utils import get_screen_resolution
        resolucion_actual = get_screen_resolution()
    except Exception:
        try:
            from rpa_framework.utils.screen_utils import get_screen_resolution
            resolucion_actual = get_screen_resolution()
        except Exception:
            resolucion_actual = "1920x1080"

    if record_data:
        lineas.append("─── <b>Datos del Registro</b> ───")

        if not record_data.get("resolucion_pantalla") and resolucion_actual:
            record_data["resolucion_pantalla"] = resolucion_actual

        labels = {
            "id":                       "🆔 ID Fila BD",
            "inicio":                   "🕐 Inicio",
            "resolucion_pantalla":      "🖥️ Resolución",
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
        if resolucion_actual:
            lineas.append(f"🖥️ <b>Resolución de pantalla:</b> <code>{resolucion_actual}</code>")
        lineas.append("<i>⚠️ No se encontró registro en la base de datos.</i>")

    return "\n".join(lineas)


def _marcar_estado(script_name, descripcion, nuevo_estado='Aprobacion_Pendiente', record_id=None):
    """Actualiza el registro al estado especificado en BD por record_id o 'En Proceso'."""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        obs = f"[{script_name}] {descripcion}"[:500]
        if record_id:
            query = """
            UPDATE ris.registro_acciones
            SET estado = %s, observacion = %s, `update` = NOW()
            WHERE id = %s
            """
            cursor.execute(query, (nuevo_estado, obs, record_id))
        else:
            query = """
            UPDATE ris.registro_acciones
            SET estado = %s, observacion = %s, `update` = NOW()
            WHERE estado = 'En Proceso'
            """
            cursor.execute(query, (nuevo_estado, obs))
        conn.commit()
        rows_affected = cursor.rowcount
        cursor.close()
        conn.close()
        logger.info(f"Registro marcado como '{nuevo_estado}' ({rows_affected} filas afectadas).")
    except Exception as e:
        logger.error(f"Error actualizando estado a {nuevo_estado} en BD: {e}")


def notificar_aprobacion_pendiente(script_name: str, descripcion: str, record_id: int = None):
    """
    Notifica a Telegram que el caso finalizó su flujo pero quedó pendiente
    de aprobación/validación visual en RIS/PACS, y marca el registro en BD
    como 'Aprobacion_Pendiente' sin abortar el proceso.
    """
    record_data = _consultar_registro(record_id=record_id)
    rec_id = record_data.get("id") if record_data else record_id

    id_log = f" (ID Fila BD: #{rec_id})" if rec_id else ""
    print(f"\n[ERROR_HANDLER] APROBACIÓN PENDIENTE en '{script_name}'{id_log}: {descripcion}", flush=True)
    logger.warning(f"⚠️ [{script_name}]{id_log} {descripcion}")

    screenshot_path = _tomar_screenshot()

    # Formatear mensaje con encabezado claro
    mensaje = _formatear_mensaje(script_name, f"⚠️ <b>Validación no confirmada:</b> {descripcion}", record_data)
    if rec_id:
        mensaje = mensaje.replace(f"🚨 <b>ERROR en {script_name}</b> (Fila #{rec_id})", f"🚨 <b>APROBACIÓN PENDIENTE en {script_name}</b> (Fila #{rec_id})")
    mensaje = mensaje.replace(f"🚨 <b>ERROR en {script_name}</b>", f"🚨 <b>APROBACIÓN PENDIENTE en {script_name}</b>")

    enviar_alerta_todos, enviar_foto_todos = _get_telegram()

    try:
        import inspect
        sig = inspect.signature(enviar_alerta_todos)
        if "record_id" in sig.parameters:
            enviar_alerta_todos(mensaje, record_id=rec_id)
        else:
            enviar_alerta_todos(mensaje)
        logger.info("Notificación de Aprobación Pendiente enviada a Telegram.")
    except Exception as e:
        logger.error(f"Error enviando texto a Telegram: {e}")

    try:
        if screenshot_path and os.path.exists(screenshot_path):
            id_tag = f" (ID Fila BD: #{rec_id})" if rec_id else ""
            caption = f"📸 Captura para revisión: <b>{script_name}</b>{id_tag} (Aprobación Pendiente)"
            enviar_foto_todos(screenshot_path, caption)
            logger.info("Screenshot de Aprobación Pendiente enviado a Telegram.")
    except Exception as e:
        logger.error(f"Error enviando foto a Telegram: {e}")

    # Marcar en BD como Aprobacion_Pendiente
    _marcar_estado(script_name, descripcion, nuevo_estado='Aprobacion_Pendiente', record_id=rec_id)
    return True


def handle_error_and_exit(script_name: str, error_description: str, record_id: int = None):
    """
    Punto de entrada único para errores críticos en el workflow PACS.

    Pasos:
      1. Toma screenshot completo
      2. Consulta datos del registro en BD (incluyendo ID de fila)
      3. Envía mensaje de texto a Telegram (descripción + datos del registro)
      4. Envía el screenshot a Telegram
      5. Marca el registro como 'Error' en BD
      6. sys.exit(1)
    """
    # 1. Screenshot
    screenshot_path = _tomar_screenshot()

    # 2. Datos del registro
    record_data = _consultar_registro(record_id=record_id)
    rec_id = record_data.get("id") if record_data else record_id

    id_log = f" (ID Fila BD: #{rec_id})" if rec_id else ""
    print(f"\n[ERROR_HANDLER] ERROR CRÍTICO en '{script_name}'{id_log}: {error_description}", flush=True)
    logger.error(f"❌ [{script_name}]{id_log} {error_description}")

    # 3. Mensaje de texto
    mensaje = _formatear_mensaje(script_name, error_description, record_data)

    # 4. Enviar a Telegram
    enviar_alerta_todos, enviar_foto_todos = _get_telegram()

    try:
        # Siempre enviar el texto primero (sin límite de chars)
        # Verificamos si enviar_alerta_todos acepta record_id (para evitar error si se llama desde versiones anteriores)
        import inspect
        sig = inspect.signature(enviar_alerta_todos)
        if "record_id" in sig.parameters:
            enviar_alerta_todos(mensaje, record_id=rec_id)
        else:
            enviar_alerta_todos(mensaje)
        logger.info("Mensaje de texto enviado a Telegram.")
    except Exception as e:
        logger.error(f"Error enviando texto a Telegram: {e}")

    try:
        # Enviar la imagen como foto separada con caption corto
        if screenshot_path and os.path.exists(screenshot_path):
            id_tag = f" (ID Fila BD: #{rec_id})" if rec_id else ""
            caption = f"📸 Captura del error en <b>{script_name}</b>{id_tag}"
            enviar_foto_todos(screenshot_path, caption)
            logger.info("Screenshot enviado a Telegram.")
    except Exception as e:
        logger.error(f"Error enviando foto a Telegram: {e}")

    # 5. Marcar como Error en BD
    _marcar_error(script_name, error_description, record_id=rec_id)

    # 6. Salir
    sys.exit(1)

