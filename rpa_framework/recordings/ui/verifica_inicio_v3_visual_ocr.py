#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script: verifica_inicio_v3_visual_ocr
Descripción: Verifica el inicio del RIS comparando visualmente una región específica
usando OCR (Tesseract) contra una imagen de referencia.
"""

import sys
import time
import logging
import os
import numpy as np
import pyautogui
from pathlib import Path
from datetime import datetime
import psutil
import re
from pywinauto import Desktop
import pywinauto.findwindows as fw
from fuzzywuzzy import fuzz

# Agregar raíz del proyecto al path
ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from ocr.engine import OCREngine
from ocr.matcher import OCRMatcher
from utils.logging_setup import setup_logging
from utils.telegram_manager import enviar_alerta_todos
from utils.visual_feedback import VisualFeedback

# Configuración de MySQL
try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

logger = logging.getLogger(__name__)

class VerificaInicioVisualOCR:
    """Automatización: verifica_inicio (Versión 3 Visual OCR)"""
    
    def __init__(self):
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.reference_image = str(ROOT_DIR / "utils" / "inicio pacs.png")
        self.max_retries = 3
        self.wait_timeout = 90
        self.region = (0, 24, 194, 1006) # left, top, width, height (desde 0,24 hasta 194,1030)
        
        # Inicializar OCR y Feedback Visual
        self.engine = OCREngine(engine='tesseract', confidence_threshold=0.4)
        self.matcher = OCRMatcher(threshold=80)
        self.vf = VisualFeedback()
        
        # Pre-extraer texto de referencia
        self.reference_text = self._get_reference_text()

    def _get_reference_text(self) -> str:
        """Extrae el texto de la imagen de referencia una sola vez."""
        if not os.path.exists(self.reference_image):
            logger.warning(f"Imagen de referencia no encontrada: {self.reference_image}")
            return ""
        
        try:
            results = self.engine.extract_text_with_location(self.reference_image)
            text = " ".join([r['text'] for r in results]).strip()
            logger.info(f"Texto de referencia extraído ({len(text)} caracteres)")
            return text
        except Exception as e:
            logger.error(f"Error extrayendo texto de referencia: {e}")
            return ""

    def db_update_status(self, status='En Proceso'):
        """Actualiza el estado en la BD"""
        if not HAS_MYSQL:
            return
        try:
            conn = mysql.connector.connect(host='localhost', user='root', password='', database='ris')
            cursor = conn.cursor()
            query = "UPDATE registro_acciones SET `update` = NOW(), ultimo_nodo = %s, estado = %s WHERE estado = 'En Proceso'"
            cursor.execute(query, ("verifica_inicio", status))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"[DB Error] {e}")

    def focus_ris(self):
        """Busca y enfoca la ventana del RIS."""
        try:
            titles = ["Carestream RIS", "Workflow Information Management", "Vue RIS"]
            for title in titles:
                windows = fw.find_windows(title_re=re.compile(f".*{re.escape(title)}.*", re.I))
                if windows:
                    hwnd = windows[0]
                    win = Desktop(backend="win32").window(handle=hwnd)
                    win.set_focus()
                    return True
        except: pass
        return False

    def check_process_running(self):
        """Verifica si el proceso está en ejecución."""
        for p in psutil.process_iter(['name']):
            try:
                name = p.info['name'].lower()
                if 'carestream ris.exe' in name or 'vue ris.exe' in name:
                    return True
            except: pass
        return False

    def verify_visual_match(self) -> bool:
        """Toma captura de la región y la compara con la referencia vía OCR."""
        try:
            # Resaltar en pantalla la zona de captura
            if self.vf:
                self.vf.highlight_region(*self.region, duration=0.8)
                time.sleep(0.1)

            # Capturar región
            screenshot = pyautogui.screenshot(region=self.region)
            screenshot_np = np.array(screenshot)
            
            # Extraer texto actual
            results = self.engine.extract_text_with_location(screenshot_np)
            current_text = " ".join([r['text'] for r in results]).strip()
            
            if not current_text and not self.reference_text:
                return False
                
            # Comparación Fuzzy
            similarity = fuzz.token_set_ratio(self.reference_text, current_text)
            logger.debug(f"Similitud OCR: {similarity}% | Detectado: '{current_text[:50]}...'")
            
            return similarity >= 80
        except Exception as e:
            logger.error(f"Error en verify_visual_match: {e}")
            return False

    def run(self) -> dict:
        logger.info("Iniciando Verificación de Inicio V3 (Visual OCR)")
        self.db_update_status('En Proceso')
        
        start_time = time.time()
        
        while (time.time() - start_time) < self.wait_timeout:
            # 1. Verificar proceso y ventana básica
            if self.check_process_running():
                self.focus_ris()
                
                # 2. Verificar contenido visual (Sidebar)
                if self.verify_visual_match():
                    logger.info("¡Inicio verificado correctamente mediante comparación visual OCR!")
                    return {"status": "SUCCESS", "message": "Inicio verificado visualmente"}
                else:
                    logger.info("Proceso detectado pero el contenido visual aún no coincide. Reintentando...")
            else:
                logger.debug("Esperando a que el proceso del RIS inicie...")
            
            time.sleep(1) # Reintento cada 1 segundo como se solicitó
            
        logger.error("Timeout alcanzado sin confirmación visual del inicio.")
        return {"status": "FAILED", "reason": "No se validó el contenido visual del menú tras el tiempo de espera."}

def main():
    setup_logging()
    automation = VerificaInicioVisualOCR()
    results = automation.run()
    
    if results["status"] == "SUCCESS":
        print("ok")
        return 0
    else:
        print(f"Error: {results.get('reason', 'Desconocido')}")
        try:
            msg = f"❌ <b>Error de Inicio Visual</b>\nNo se pudo validar la carga del menú principal del RIS.\n<code>{results.get('reason')}</code>"
            enviar_alerta_todos(msg)
        except: pass
        return 1

if __name__ == "__main__":
    sys.exit(main())
