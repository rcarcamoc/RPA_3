#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script RPA: Cierra el "Visor de documentos" y vuelve a Carestream.

Flujo:
  1. Busca la imagen 'visor de documentos2.png' en pantalla usando
     Multi-scale matching y doble confirmación.
  2. Si lo encuentra, posiciona el cursor en el centro y hace clic sostenido.
  3. Envía la combinación Alt+F4.
  4. Selecciona (activa) la ventana de Carestream Radiology Client / Vue PACS.
  
  Si NO encuentra la imagen, simplemente no hace nada.
"""

import sys
import os
import time
import logging
import random
import re
import pyautogui
import cv2
import numpy as np
from pathlib import Path

# ── pywinauto para activar ventana ───────────────────────────────
from pywinauto import Desktop
import pywinauto.findwindows as fw

# Agregar raíz del proyecto al path para importar utils
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# ── Visual Feedback ──────────────────────────────────────────────
try:
    from utils.visual_feedback import VisualFeedback
    vf = VisualFeedback()
except ImportError:
    vf = None

# ── Telegram ─────────────────────────────────────────────────────
try:
    from utils.telegram_manager import enviar_alerta_todos
except ImportError:
    def enviar_alerta_todos(msg): pass

# ── MySQL (opcional) ─────────────────────────────────────────────
try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ── Configuracion ────────────────────────────────────────────────
HOLD_TIME = 0.5
MAX_INTENTOS = 3

TITULOS_CARESTREAM = [
    "Carestream Radiology Client",
    "Carestream Vue PACS",
]

id_registro = os.environ.get('VAR_id_registro')

# ── Carpeta de logs especifica para esta tarea ───────────────────
LOG_DIR = os.path.join(
    str(Path(__file__).parent.parent.parent),
    "log", "verifica_inicio"
)
os.makedirs(LOG_DIR, exist_ok=True)

VISOR_TEMPLATE_PATH = os.path.join(
    str(Path(__file__).parent.parent.parent),
    "utils", "visor de documentos2.png"
)


def db_update(status='En Proceso', obs=None, node='cierra_visor_documentos'):
    """Actualiza estado en la BD."""
    if not id_registro or not HAS_MYSQL:
        return
    try:
        conn = mysql.connector.connect(
            host='localhost', user='root', password='', database='ris'
        )
        cursor = conn.cursor()
        if status == 'Error':
            query = "UPDATE registro_acciones SET estado = 'Error', observacion = %s, `update` = NOW() WHERE id = %s"
            cursor.execute(query, (obs, id_registro))
        else:
            query = "UPDATE registro_acciones SET estado = %s, ultimo_nodo = %s, `update` = NOW() WHERE id = %s"
            cursor.execute(query, (status, node, id_registro))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"[DB Error] {e}")


def buscar_imagen_visor(template_path, confidence_threshold=0.70):
    """
    Busca la imagen en la pantalla usando MULTI-SCALE MATCHING y DOBLE CONFIRMACIÓN.
    (Basado en buscar_bloque_toolbar de 'pega en word.py')
    """
    if not os.path.exists(template_path):
        logger.error(f"❌ Error: No se encuentra {template_path}")
        return None
    
    # Leer la template
    template = cv2.imread(template_path)
    if template is None:
        logger.error(f"❌ Error: No se pudo leer {template_path}")
        return None
    
    original_h, original_w = template.shape[:2]
    
    # Capturar pantalla actual
    try:
        current_screen = pyautogui.screenshot()
        screen_np = np.array(current_screen)
        screen_cv = cv2.cvtColor(screen_np, cv2.COLOR_RGB2BGR)
    except Exception as e:
        logger.error(f"❌ Error capturando pantalla: {e}")
        return None
    
    # Búsqueda EXACTA (1:1) en COLOR (BGR)
    try:
        result = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
    except Exception as e:
        logger.error(f"❌ Error crítico en matchTemplate: {e}")
        return None
        
    template_w = original_w
    template_h = original_h

    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
    x, y = max_loc
    
    center_x = x + original_w / 2
    center_y = y + original_h / 2

    match_found = False
    
    # 1. Confianza Alta (Pase Directo)
    if max_val >= confidence_threshold:
        match_found = True
        logger.info(f"   ✅ Confianza alta ({max_val*100:.2f}%). Pase directo.")
        if vf:
            vf.highlight_region(x, y, template_w, template_h, color="#FFEB3B", duration=1.5)
        
    # 2. Confianza "Aceptable" -> DOBLE CONFIRMACIÓN
    elif max_val >= 0.20:
        logger.warning(f"   ⚠️ Confianza preliminar baja ({max_val*100:.2f}%) en ({x}, {y}). DOBLE CONFIRMACIÓN...")
        
        try:
            h_scr, w_scr = screen_cv.shape[:2]
            y2, x2 = min(y + template_h, h_scr), min(x + template_w, w_scr)
            crop = screen_cv[y:y2, x:x2]

            # Redimensionar crop al tamaño exacto de la template para comparación directa
            crop_resized = cv2.resize(crop, (template_w, template_h), interpolation=cv2.INTER_LINEAR)

            # Comparación directa pixel a pixel: similitud por diferencia normalizada
            diff = cv2.norm(crop_resized.astype(np.float32), template.astype(np.float32), cv2.NORM_L2)
            max_possible = np.sqrt(template_w * template_h * 3) * 255.0
            similitud = 1.0 - (diff / max_possible)

            logger.info(f"   🔍 Doble Confirmación (similitud directa): {similitud*100:.2f}%")

            # Umbral de similitud directa (0.65 = 65% de similitud pixel a pixel)
            UMBRAL_CONFIRM2 = 0.65

            # Guardar imagen del recorte con etiqueta de resultado
            try:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                crop_viz = crop_resized.copy()
                label = f"Sim: {similitud*100:.1f}%"
                color_label = (0, 200, 0) if similitud >= UMBRAL_CONFIRM2 else (0, 0, 255)
                cv2.putText(crop_viz, label, (4, 22),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4)
                cv2.putText(crop_viz, label, (4, 22),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, color_label, 2)
                suffix_crop = "confirm2_ok" if similitud >= UMBRAL_CONFIRM2 else "confirm2_fail"
                crop_path = os.path.join(LOG_DIR, f"cierra_visor_img_{suffix_crop}_{timestamp}.png")
                cv2.imwrite(crop_path, crop_viz)
                logger.info(f"   [LOG IMG] Recorte 2ª confirmación: {crop_path}")
            except Exception as e_img:
                logger.debug(f"   [ERROR IMG] No se pudo guardar recorte: {e_img}")

            if similitud >= UMBRAL_CONFIRM2:
                match_found = True
                logger.info("   ✅ Match confirmado tras segunda pasada (similitud directa).")
                if vf:
                    vf.highlight_region(x, y, template_w, template_h, color="#FFEB3B", duration=1.5)
            else:
                logger.warning(f"   ❌ Falló doble confirmación (similitud={similitud*100:.1f}% < {UMBRAL_CONFIRM2*100:.0f}%).")
                match_found = False

        except Exception as e:
            logger.error(f"   Error durante la doble confirmación: {e}")
            match_found = False

    if match_found:
        return {
            'x': x,
            'y': y,
            'w': template_w,
            'h': template_h,
            'center_x': int(center_x),
            'center_y': int(center_y),
            'text': 'visor de documentos (imagen_v2)'
        }
    else:
        return None


def humanized_click(x, y, hold_time=HOLD_TIME):
    """Mueve el raton, destaca la zona y hace clic sostenido."""
    if vf:
        vf.highlight_click(x, y, color="#FF0000", duration=0.8)
        time.sleep(0.3)

    duration = random.uniform(0.4, 0.8)
    pyautogui.moveTo(x, y, duration=duration, tween=pyautogui.easeInOutQuad)
    logger.info(f"   -> Cursor posicionado en ({x}, {y})")

    time.sleep(0.5)

    if hold_time > 0.0:
        logger.info(f"   -> Clic sostenido ({hold_time}s)...")
        pyautogui.mouseDown()
        time.sleep(hold_time)
        pyautogui.mouseUp()
    else:
        pyautogui.click()

    logger.info(f"   -> Clic completado en ({x}, {y})")


def activar_ventana_carestream():
    """Busca y activa la ventana de Carestream."""
    logger.info("Buscando ventana Carestream...")

    for titulo in TITULOS_CARESTREAM:
        try:
            ventanas = fw.find_windows(
                title_re=re.compile(f".*{re.escape(titulo)}.*", re.I)
            )
            if ventanas:
                hwnd = ventanas[0]
                win = Desktop(backend="win32").window(handle=hwnd)
                titulo_real = win.window_text()
                logger.info(f"   Ventana encontrada: '{titulo_real}' (hwnd={hwnd})")

                win.set_focus()
                time.sleep(0.5)

                if vf:
                    vf.show_message("Carestream activado", duration=2.0)

                logger.info(f"   -> Ventana '{titulo_real}' activada.")
                return True

        except Exception as e:
            logger.warning(f"   Error buscando '{titulo}': {e}")
            continue

    logger.warning("No se encontro ninguna ventana de Carestream abierta.")
    return False


def execute():
    """Punto de entrada principal del script."""
    logger.info("=" * 60)
    logger.info("RPA: Cierra Visor de Documentos v2 (por imagen) -> Vuelve a Carestream")
    logger.info("=" * 60)

    db_update(status='En Proceso')

    try:
        # ── Paso 1: Capturar pantalla y buscar imagen ─────
        logger.info(f"[1/3] Buscando imagen del visor en pantalla completa...")
        
        resultado = None

        for intento in range(1, MAX_INTENTOS + 1):
            logger.info(f"   Intento {intento}/{MAX_INTENTOS}...")

            resultado = buscar_imagen_visor(VISOR_TEMPLATE_PATH)

            if resultado:
                break

            logger.warning(f"   Imagen no encontrada (intento {intento})")
            if intento < MAX_INTENTOS:
                time.sleep(1.0)

        if not resultado:
            logger.info(f"Imagen del visor no encontrada en {MAX_INTENTOS} intentos. Nada que hacer.")
            return {
                'status': 'skipped',
                'reason': 'Imagen no encontrada en pantalla'
            }

        # ── Paso 2: Feedback visual + Clic sostenido ─────────────
        click_x = resultado['center_x']
        click_y = resultado['center_y']
        
        logger.info(f"[2/3] Clic sostenido en ({click_x}, {click_y})...")
        
        humanized_click(click_x, click_y, hold_time=HOLD_TIME)
        time.sleep(1.0)

        # ── Paso 3: Enviar Alt + F4 ──────────────────────────────
        logger.info("[2/3] Enviando Alt + F4...")
        pyautogui.hotkey('alt', 'f4', interval=0.1)
        
        logger.info("   -> Alt + F4 enviado.")
        time.sleep(1.5)

        # ── Paso 4: Activar ventana Carestream ───────────────────
        logger.info("[3/3] Activando ventana Carestream...")
        carestream_ok = activar_ventana_carestream()

        if not carestream_ok:
            logger.warning("No se pudo activar Carestream. Puede que no este abierto.")

        # ── Exito ────────────────────────────────────────────────
        logger.info("=" * 60)
        logger.info("Visor cerrado y Carestream activado exitosamente.")
        logger.info("=" * 60)

        db_update(status='En Proceso')

        return {
            'status': 'success',
            'click_position': {'x': click_x, 'y': click_y},
            'carestream_activated': carestream_ok
        }

    except SystemExit:
        sys.exit(1)
    except Exception as e:
        error_msg = f"Excepcion critica: {str(e)}"
        logger.error(f"ERROR: {error_msg}")
        db_update(status='Error', obs=error_msg)
        enviar_alerta_todos(
            f"<b>Error Critico: cierra_visor_documentos_v2</b>\n{error_msg}"
        )
        sys.exit(1)


# Alias para compatibilidad con el framework
main = execute

if __name__ == '__main__':
    print('Ejecutando cierra_visor_documentos_v2...')
    result = execute()
    print(f'Resultado: {result}')
