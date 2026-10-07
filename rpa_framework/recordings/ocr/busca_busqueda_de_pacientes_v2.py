#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script: busca_busqueda_de_pacientes_v2.py
Versión optimizada de busca_busqueda de pacientes.py:
- Primer intento inmediato sin esperar 5 segundos (Ahorro directo de ~5s).
- Intervalos de reintento dinámicos.
"""

import sys
import time
import os
from pathlib import Path

ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.append(str(ROOT_DIR))

try:
    from pywinauto import Desktop
    import pywinauto.findwindows as fw
    import re
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


def execute_ocr_click_0():
    time.sleep(0.3)

    try:
        titles = ["Carestream RIS", "Workflow Information Management", "Vue RIS", "Carestream Vue PACS"]
        for title in titles:
            windows = fw.find_windows(title_re=re.compile(f".*{re.escape(title)}.*", re.I))
            if windows:
                hwnd = windows[0]
                win = Desktop(backend="win32").window(handle=hwnd)
                win.set_focus()
                break
    except Exception:
        pass

    engine = OCREngine(engine='tesseract', confidence_threshold=0.5)
    matcher = OCRMatcher(threshold=80)
    actions = OCRActions(engine, matcher, delay=0.1)

    delays = [0, 1, 1.5, 2, 2] # Primer intento INMEDIATO sin delay
    search_terms = ['Búsqueda de Pacientes', 'Patient Search']
    region = {'left': 0, 'top': 0, 'width': 182, 'height': 1010}

    for attempt, delay in enumerate(delays):
        if delay > 0:
            time.sleep(delay)

        actions.capture_screenshot(region=region)
        results = actions.engine.extract_text(actions.last_screenshot)

        for item in results:
            text = item.get('text', '').strip()
            if not text:
                continue

            for term in search_terms:
                sim = fuzz.partial_ratio(term.lower(), text.lower())
                if sim >= 80:
                    pos = item.get('position', {})
                    center_x = pos.get('x', 0) + (pos.get('width', 0) // 2)
                    center_y = pos.get('y', 0) + (pos.get('height', 0) // 2)

                    actions.mouse.click(center_x, center_y)
                    print(f"[OK v2] Encontrado: '{text}' ({sim}% coincidencia). Clic en ({center_x}, {center_y})")
                    return True

    print("[WARNING v2] No se encontró texto de búsqueda de pacientes.")
    return False


def main():
    if execute_ocr_click_0():
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
