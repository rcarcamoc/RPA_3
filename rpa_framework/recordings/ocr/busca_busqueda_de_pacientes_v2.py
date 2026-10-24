#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script: busca_busqueda_de_pacientes_v2.py
Versión optimizada de busca_busqueda de pacientes.py:
- Primer intento inmediato sin esperas innecesarias.
- Intervalos de reintento dinámicos.
- Extracción de texto OCR con ubicación correcta y agrupación de oraciones.
- Clic robusto con pyautogui en coordenadas globales.
- Tracking de estado en base de datos.
"""

import sys
import time
import os
import re
import logging
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.append(str(ROOT_DIR))

try:
    import pyautogui
    pyautogui.FAILSAFE = False
except ImportError:
    pass

try:
    from pywinauto import Desktop
    import pywinauto.findwindows as fw
except ImportError:
    pass

from ocr.engine import OCREngine
from ocr.matcher import OCRMatcher
from ocr.actions import OCRActions
from fuzzywuzzy import fuzz

try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def db_update(status='En Proceso', obs=None, node='busca_busqueda_de_pacientes_v2'):
    if not HAS_MYSQL:
        return
    id_registro = os.environ.get('VAR_id_registro')
    try:
        conn = mysql.connector.connect(host='localhost', user='root', password='', database='ris', connect_timeout=3)
        cursor = conn.cursor()
        if id_registro:
            if status == 'Error':
                cursor.execute("UPDATE registro_acciones SET estado = 'Error', observacion = %s, `update` = NOW() WHERE id = %s", (obs, id_registro))
            else:
                cursor.execute("UPDATE registro_acciones SET estado = %s, ultimo_nodo = %s, `update` = NOW() WHERE id = %s", (status, node, id_registro))
        else:
            if status == 'Error':
                cursor.execute("UPDATE registro_acciones SET estado = 'Error', observacion = %s, `update` = NOW() WHERE estado = 'En Proceso' ORDER BY id DESC LIMIT 1", (obs,))
            else:
                cursor.execute("UPDATE registro_acciones SET estado = %s, ultimo_nodo = %s, `update` = NOW() WHERE estado = 'En Proceso' ORDER BY id DESC LIMIT 1", (status, node))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"Error DB: {e}")


def enfocar_ventana():
    try:
        titles = ["Carestream RIS", "Workflow Information Management", "Vue RIS", "Carestream Vue PACS", "Carestream RIS V11"]
        for title in titles:
            windows = fw.find_windows(title_re=re.compile(f".*{re.escape(title)}.*", re.I))
            if windows:
                hwnd = windows[0]
                win = Desktop(backend="win32").window(handle=hwnd)
                win.set_focus()
                logger.info(f"✓ Ventana enfocada: '{title}'")
                return True
    except Exception as e:
        logger.debug(f"Aviso al enfocar ventana: {e}")
    return False


def execute_ocr_click():
    time.sleep(0.2)
    enfocar_ventana()
    db_update(status='En Proceso', node='busca_busqueda_de_pacientes_v2')

    engine = OCREngine(engine='tesseract', confidence_threshold=0.5)
    matcher = OCRMatcher(threshold=80)
    actions = OCRActions(engine, matcher, delay=0.1)

    delays = [0, 1, 1.5, 2, 2]  # Primer intento inmediato
    search_terms = ['Búsqueda de Pacientes', 'Patient Search']
    region = {'left': 0, 'top': 0, 'width': 182, 'height': 1010}

    for attempt, delay in enumerate(delays):
        if delay > 0:
            logger.info(f"Intento {attempt + 1}: Esperando {delay}s...")
            time.sleep(delay)

        # Captura de la región del panel lateral
        actions.capture_screenshot(region=region)
        ocr_results = engine.extract_text_with_location(actions.last_screenshot)
        if not ocr_results:
            continue

        # Ajustar coordenadas al monitor global
        for res in ocr_results:
            res['center']['x'] += region['left']
            res['center']['y'] += region['top']

        # Ordenar de arriba hacia abajo y de izquierda a derecha (tolerancia 15px en Y)
        ocr_results.sort(key=lambda x: (int(x['center']['y'] / 15), x['center']['x']))

        highest_score = 0
        best_res = None

        for term in search_terms:
            term_lower = term.lower()
            for window_size in [1, 2, 3]:
                if len(ocr_results) < window_size:
                    continue
                for i in range(len(ocr_results) - window_size + 1):
                    window = ocr_results[i:i+window_size]
                    if window_size > 1:
                        y_diff = abs(window[0]['center']['y'] - window[-1]['center']['y'])
                        if y_diff > 25:
                            continue
                    texto_combinado = " ".join([w.get('text', '') for w in window]).strip()
                    score = fuzz.ratio(term_lower, texto_combinado.lower())
                    if score > highest_score:
                        highest_score = score
                        best_res = window[0].copy()
                        best_res['text'] = texto_combinado
                        best_res['match_term'] = term

        if highest_score >= 65 and best_res:
            click_x = int(best_res['center']['x'])
            click_y = int(best_res['center']['y'])
            logger.info(f"✓ [OK v2] Encontrado: '{best_res['text']}' (Similitud: {highest_score}% con '{best_res['match_term']}'). Clic en ({click_x}, {click_y})")

            try:
                from rpa_framework.utils.visual_feedback import VisualFeedback
                vf = VisualFeedback()
                vf.highlight_click(click_x, click_y)
            except Exception:
                pass

            pyautogui.moveTo(click_x, click_y, duration=0.2)
            time.sleep(0.3)
            pyautogui.mouseDown(click_x, click_y, button='left')
            time.sleep(0.15)
            pyautogui.mouseUp(click_x, click_y, button='left')
            time.sleep(0.3)
            return True

    logger.warning("[WARNING v2] No se encontró texto de búsqueda de pacientes tras todos los intentos.")
    return False


def main():
    if execute_ocr_click():
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
