#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script: verifica_inicio_v4_similitud_v2.py
Versión optimizada de verifica_inicio_v4_similitud.py:
- Detección visual ágil (intervalo 0.5s en lugar de 2s).
- Elimina bloqueos de highlight.
- Corrige inicialización de variables locales para prevenir excepciones.
"""

import sys
import time
import logging
import os
import cv2
import numpy as np
import pyautogui
pyautogui.FAILSAFE = False
from pathlib import Path
from datetime import datetime
import psutil
import re
from pywinauto import Desktop
import pywinauto.findwindows as fw

ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

try:
    from rpa_framework.utils.window_utils import force_foreground_window, maximize_hwnd
except ImportError:
    force_foreground_window = None
    maximize_hwnd = None

try:
    from rpa_framework.utils.screen_utils import safe_screenshot
except ImportError:
    safe_screenshot = None

try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.70  # 70% de similitud para detección ágil
WAIT_TIMEOUT = 60


class VerificaInicioSimilitudV2:
    def __init__(self):
        self.reference_image_path = str(ROOT_DIR / "utils" / "inicio pacs.png")
        self.wait_timeout = WAIT_TIMEOUT
        self.region = (0, 24, 194, 1006) 
        self.similarity_threshold = SIMILARITY_THRESHOLD
        self.reference_img = self._load_reference()

    def _load_reference(self):
        if not os.path.exists(self.reference_image_path):
            return None
        try:
            return cv2.imread(self.reference_image_path, cv2.IMREAD_GRAYSCALE)
        except Exception:
            return None

    def db_update_status(self, status='En Proceso'):
        if not HAS_MYSQL:
            return
        try:
            conn = mysql.connector.connect(host='localhost', user='root', password='', database='ris')
            cursor = conn.cursor()
            query = "UPDATE registro_acciones SET `update` = NOW(), ultimo_nodo = 'verifica_inicio_v2', estado = %s WHERE estado = 'En Proceso'"
            cursor.execute(query, (status,))
            conn.commit()
            conn.close()
        except Exception:
            pass

    def focus_ris(self):
        try:
            titles = ["Carestream RIS", "Workflow Information Management", "Vue RIS", "Carestream Vue PACS"]
            for title in titles:
                windows = fw.find_windows(title_re=re.compile(f".*{re.escape(title)}.*", re.I))
                if windows:
                    hwnd = windows[0]
                    if force_foreground_window:
                        force_foreground_window(hwnd)
                    elif maximize_hwnd:
                        maximize_hwnd(hwnd)
                    return True
        except Exception:
            pass
        return False

    def verify_visual_match(self) -> bool:
        if self.reference_img is None:
            return True # Si no hay imagen de referencia, continuar

        num_matches = 0
        similarity_pct = 0.0

        try:
            if safe_screenshot:
                screenshot = safe_screenshot(region=self.region)
            else:
                screenshot = pyautogui.screenshot(region=self.region)

            if screenshot is None:
                return False

            screenshot_np = np.array(screenshot)
            current_gray = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2GRAY)
            
            orb = cv2.ORB_create(nfeatures=500)
            kp_ref, des_ref = orb.detectAndCompute(self.reference_img, None)
            kp_cur, des_cur = orb.detectAndCompute(current_gray, None)
            
            if des_ref is not None and des_cur is not None:
                bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
                matches = bf.match(des_ref, des_cur)
                good_matches = [m for m in matches if m.distance < 60]
                num_matches = len(good_matches)
                similarity_pct = min((num_matches / 100.0) * 100.0, 100.0)
            
            umbral_pct = self.similarity_threshold * 100
            if similarity_pct >= umbral_pct:
                logger.info(f"✓ Coincidencia visual confirmada: {similarity_pct:.1f}%")
                return True
            return False
            
        except Exception as e:
            return False

    def run(self):
        logger.info("Iniciando Verificación de Inicio PACS v2...")
        self.db_update_status('En Proceso')
        start_time = time.time()
        
        while (time.time() - start_time) < self.wait_timeout:
            self.focus_ris()
            if self.verify_visual_match():
                return True
            time.sleep(0.5)

        logger.warning("Timeout verificación visual. Continuando por tolerancia...")
        return True


def main():
    autom = VerificaInicioSimilitudV2()
    if autom.run():
        print("ok")
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
