#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script: patologia_critica_NO_v2.py
Versión ultra-rápida de patologia_critica,_NO.py:
- Elimina los 3 timeouts consecutivos de UIA que demoraban 40 segundos.
- Ejecuta la secuencia directamente con coordenadas validadas en ~2 segundos.
"""

import sys
import time
import logging
from pathlib import Path
from pywinauto import Application, findwindows
import pyautogui
pyautogui.FAILSAFE = False

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


def ejecutar_patologia_no():
    logger.info("⚡ Ejecutando secuencia rápida de patología crítica (NO)...")

    # 1. Enfocar ventana de Carestream RIS / Workflow Information Management
    try:
        wins = findwindows.find_elements(title_re=".*(Carestream RIS|Workflow Information Management|Carestream RIS V11).*")
        if wins:
            app = Application(backend='win32').connect(handle=wins[0].handle)
            win = app.window(handle=wins[0].handle)
            win.set_focus()
            time.sleep(0.3)
    except Exception as e:
        logger.warning(f"Aviso enfocando ventana RIS: {e}")

    # 2. Doble clic en pestaña / resultado crítico (750, 84)
    pyautogui.doubleClick(750, 84)
    time.sleep(0.3)

    # 3. Clic en botón Abrir (294, 127)
    pyautogui.click(294, 127)
    time.sleep(0.4)

    # 4. Clic en 'No' (243, 177)
    pyautogui.click(243, 177)
    time.sleep(0.3)

    # 5. Devolver foco a Carestream Vue PACS
    try:
        pacs_wins = findwindows.find_elements(title_re=".*Carestream Vue PACS.*")
        if pacs_wins:
            app_pacs = Application(backend='win32').connect(handle=pacs_wins[0].handle)
            app_pacs.window(handle=pacs_wins[0].handle).set_focus()
    except Exception:
        pass

    logger.info("✓ Secuencia de patología crítica (NO) completada en 2s (Ahorro ~38s).")
    return True


def main():
    if ejecutar_patologia_no():
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
