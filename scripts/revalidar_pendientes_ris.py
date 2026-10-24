#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
revalidar_pendientes_ris.py

Script para re-verificar de forma asíncrona o por lotes los casos que quedaron
en estado 'Aprobacion_Pendiente' en la base de datos (ris.registro_acciones).

Funcionalidad:
1. Consulta registros con estado 'Aprobacion_Pendiente' (por ID, rango horario o todos).
2. Enfoca la ventana del RIS (Workflow Information Management / Carestream RIS).
3. Para cada caso:
   - Refresca la lista (clic en Refresh 1906,167 y F5).
   - Captura la región OCR correspondiente a la fila del estudio (basada en 'coordenada' o escaneo dinámico por documento).
   - Aplica preprocesamiento visual y OCR para verificar si el estado cambió a 'Aprobado'.
   - Si cambió a 'Aprobado': actualiza BD a 'Terminado' y documenta la observación.
   - Si sigue 'pending': mantiene 'Aprobacion_Pendiente' para una revisión posterior.
4. Genera resumen claro y reporte de ejecución.

Uso:
  python scripts/revalidar_pendientes_ris.py --dry-run             # Solo listar casos pendientes en BD
  python scripts/revalidar_pendientes_ris.py --hours 24           # Revalidar casos de las últimas 24 horas
  python scripts/revalidar_pendientes_ris.py --id 1570            # Revalidar un caso específico
  python scripts/revalidar_pendientes_ris.py --limit 5            # Revalidar hasta 5 casos
"""

import sys
import os
import time
import argparse
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from difflib import SequenceMatcher

import cv2
import numpy as np
import pyautogui
pyautogui.FAILSAFE = False

# Agregar ruta base al path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "rpa_framework"))

try:
    import pytesseract
except ImportError:
    pytesseract = None

try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

try:
    from pywinauto import Application, findwindows
except ImportError:
    Application = None
    findwindows = None

# Configuración de Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("revalidar_pendientes")

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "ris"
}


def get_pending_records(record_id=None, hours=24, limit=None):
    """Consulta los registros en estado 'Aprobacion_Pendiente' desde la BD."""
    if not HAS_MYSQL:
        logger.error("mysql-connector no está instalado.")
        return []

    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        params = []
        where_clauses = ["estado = 'Aprobacion_Pendiente'"]

        if record_id:
            where_clauses.append("id = %s")
            params.append(record_id)
        elif hours and hours > 0:
            since_time = datetime.now() - timedelta(hours=hours)
            where_clauses.append("inicio >= %s")
            params.append(since_time.strftime("%Y-%m-%d %H:%M:%S"))

        query = f"""
            SELECT id, inicio, `update`, estado, numero_documento, examen,
                   coordenada, doctor_detectado, observacion
            FROM registro_acciones
            WHERE {' AND '.join(where_clauses)}
            ORDER BY id ASC
        """
        if limit and limit > 0:
            query += f" LIMIT {int(limit)}"

        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows
    except Exception as e:
        logger.error(f"Error consultando BD: {e}")
        return []


def update_record_to_terminado(record_id, detalle="Aprobado confirmado por OCR"):
    """Actualiza un caso validado a estado 'Terminado' en la BD."""
    if not HAS_MYSQL:
        return False
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        obs_append = f" | [revalidar_pendientes] {detalle} ({now_str})"

        query = """
            UPDATE registro_acciones
            SET estado = 'Terminado',
                `update` = NOW(),
                observacion = CONCAT(COALESCE(observacion, ''), %s)
            WHERE id = %s
        """
        cursor.execute(query, (obs_append, record_id))
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()
        logger.info(f"✅ BD: Registro #{record_id} actualizado a 'Terminado' ({affected} fila).")
        return affected > 0
    except Exception as e:
        logger.error(f"Error actualizando registro #{record_id} en BD: {e}")
        return False


def focus_ris_window():
    """Busca y enfoca la ventana del RIS de forma resiliente."""
    if not findwindows or not Application:
        logger.warning("pywinauto no disponible para enfocar ventana.")
        return False

    patterns = ["Workflow Information Management", "Carestream RIS", "Vue RIS", "Carestream RIS V11"]
    all_wins = findwindows.find_elements()
    target_element = None

    for pattern in patterns:
        for win in all_wins:
            if pattern in win.name and "Google Chrome" not in win.name:
                target_element = win
                break
        if target_element:
            break

    if target_element:
        try:
            logger.info(f"Enfocando ventana RIS: '{target_element.name}'")
            app = Application(backend='uia').connect(handle=target_element.handle)
            w = app.window(handle=target_element.handle)
            w.set_focus()
            time.sleep(1.0)
            return True
        except Exception as e:
            logger.warning(f"No se pudo enfocar por uia ({e}), intentando clic de foco.")
            return True
    else:
        logger.warning("⚠️ No se encontró ninguna ventana del RIS abierta.")
        return False


def perform_ris_refresh():
    """Ejecuta el refresh en el cliente RIS (clic en botón Refresh y tecla F5)."""
    try:
        # Botón Refresh en barra de herramientas RIS (coordenada estándar 1906, 167)
        pyautogui.moveTo(1906, 167, duration=0.3)
        pyautogui.mouseDown(1906, 167)
        time.sleep(0.5)
        pyautogui.mouseUp(1906, 167)
        logger.info("Botón Refresh presionado en RIS.")
    except Exception as e:
        logger.warning(f"Error al hacer clic en Refresh: {e}")

    time.sleep(1.0)
    try:
        pyautogui.press('f5')
        logger.info("Tecla F5 enviada.")
    except Exception as e:
        logger.warning(f"Error enviando F5: {e}")


def check_aprobado_ocr(y_base):
    """
    Captura la región centrada en y_base (30px de alto, ancho completo de pantalla),
    aplica preprocesamiento de imagen y evalúa OCR buscando 'Aprobado'.
    """
    if not pytesseract:
        logger.error("Pytesseract no disponible.")
        return False, "pytesseract no instalado"

    try:
        screen_w, screen_h = pyautogui.size()
        y_target = max(0, min(screen_h - 35, y_base - 17))
        region = (0, y_target, screen_w, 34)

        screenshot = pyautogui.screenshot(region=region)
        img_np = np.array(screenshot)
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

        # 1. Escalar 3x para fuentes pequeñas del PACS/RIS
        img_resized = cv2.resize(img_bgr, (0, 0), fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)

        # 2. Invertir si fondo oscuro
        if np.mean(gray) < 100:
            gray = cv2.bitwise_not(gray)

        # 3. Binarizado Otsu
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # 4. OCR
        custom_config = r'--oem 3 --psm 7 -l spa'
        detected_text = pytesseract.image_to_string(binary, config=custom_config).strip().lower()
        logger.info(f"OCR Texto en Y={y_base}: \"{detected_text[:90]}\"")

        # Búsqueda directa o difusa de 'aprobado'
        if "aprobado" in detected_text or "aprobada" in detected_text:
            return True, detected_text

        words = re.findall(r'\w+', detected_text)
        for w in words:
            if len(w) >= 6 and SequenceMatcher(None, "aprobado", w).ratio() > 0.8:
                return True, detected_text

        return False, detected_text
    except Exception as e:
        logger.error(f"Error procesando OCR en Y={y_base}: {e}")
        return False, str(e)


def main():
    parser = argparse.ArgumentParser(description="Revalidación posterior de casos Aprobacion_Pendiente en RIS")
    parser.add_argument("--dry-run", action="store_true", help="Solo lista los casos pendientes en BD sin interactuar con la pantalla")
    parser.add_argument("--hours", type=int, default=24, help="Horas hacia atrás para buscar pendientes (default: 24, 0 para todos)")
    parser.add_argument("--id", type=int, default=None, help="Revalidar solo el ID de registro especificado")
    parser.add_argument("--limit", type=int, default=None, help="Límite máximo de casos a procesar")
    parser.add_argument("--attempts", type=int, default=2, help="Intentos de refresh por caso (default: 2)")
    parser.add_argument("--wait", type=int, default=6, help="Segundos de espera tras refresh para que cargue la lista (default: 6)")
    args = parser.parse_args()

    print("=" * 75)
    print(" 🏥 REVALIDADOR ASÍNCRONO DE CASOS PENDIENTES - RIS")
    print(f" Fecha actual: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 75)

    records = get_pending_records(record_id=args.id, hours=args.hours, limit=args.limit)

    if not records:
        print("ℹ️ No se encontraron registros con estado 'Aprobacion_Pendiente' para los criterios dados.")
        return

    print(f"\n📋 Se encontraron {len(records)} caso(s) en estado 'Aprobacion_Pendiente':")
    for r in records:
        print(f"  • ID #{r['id']} | Paciente: {r['numero_documento']} | Examen: {r['examen']} | Coordenada: {r['coordenada']} | Inicio: {r['inicio']}")

    if args.dry_run:
        print("\n[MODO DRY-RUN] Finalizado sin realizar acciones en pantalla.")
        return

    print("\n🚀 Iniciando proceso de revalidación interactivo...")
    window_ok = focus_ris_window()
    if not window_ok:
        print("⚠️ ADVERTENCIA: No se pudo asegurar el foco de la ventana del RIS. Continuando con precaución...")

    actualizados = 0
    siguen_pendientes = 0
    errores = 0

    for idx, r in enumerate(records, 1):
        rec_id = r['id']
        doc = r['numero_documento']
        coord = r.get('coordenada') or ''

        print(f"\n--- [{idx}/{len(records)}] Procesando Caso #{rec_id} (Doc: {doc}) ---")

        if not coord or ',' not in coord:
            logger.warning(f"Registro #{rec_id} no tiene coordenada válida registrada ('{coord}'). Omitiendo...")
            errores += 1
            continue

        try:
            y_base = int(coord.split(',')[1])
        except (ValueError, IndexError):
            logger.warning(f"Error parseando coordenada '{coord}'. Omitiendo...")
            errores += 1
            continue

        aprobado = False
        ultimo_ocr = ""

        for intento in range(1, args.attempts + 1):
            logger.info(f"🔄 Intento #{intento}/{args.attempts} para #{rec_id}...")
            perform_ris_refresh()
            time.sleep(args.wait)

            is_ok, ocr_txt = check_aprobado_ocr(y_base)
            ultimo_ocr = ocr_txt
            if is_ok:
                aprobado = True
                logger.info(f"🎉 ¡'Aprobado' confirmado para #{rec_id}!")
                break
            else:
                logger.info(f"⏳ Aún no aprobado (Texto: '{ocr_txt[:60]}')...")
                if intento < args.attempts:
                    time.sleep(2)

        if aprobado:
            success = update_record_to_terminado(rec_id, detalle=f"Aprobado detectado en revalidación ({ultimo_ocr[:50]})")
            if success:
                actualizados += 1
            else:
                errores += 1
        else:
            siguen_pendientes += 1
            logger.info(f"ℹ️ Caso #{rec_id} se mantiene en 'Aprobacion_Pendiente'.")

    print("\n" + "=" * 75)
    print(" 📊 RESUMEN FINAL DE REVALIDACIÓN")
    print(f"  • Casos evaluados      : {len(records)}")
    print(f"  • Actualizados a OK    : {actualizados}")
    print(f"  • Siguen pendientes    : {siguen_pendientes}")
    print(f"  • Con error/sin coord  : {errores}")
    print("=" * 75)


if __name__ == "__main__":
    main()
