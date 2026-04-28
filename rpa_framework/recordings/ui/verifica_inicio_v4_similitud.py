#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script: verifica_inicio_v4_similitud
Descripción: Verifica el inicio del RIS comparando visualmente una región
mediante similitud de imagen directa (OpenCV) con una tolerancia amplia (~40-50%).
Esto permite variaciones de idioma y menús contraídos.
"""

import sys
import time
import logging
import os
import cv2
import numpy as np
import pyautogui
from pathlib import Path
from datetime import datetime
import psutil
import re
from pywinauto import Desktop
import pywinauto.findwindows as fw

# Agregar raíz del proyecto al path
ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

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

# ============================================================================
# CONFIGURACIÓN GLOBAL
# ============================================================================
SIMILARITY_THRESHOLD = 0.90  # 90% de similitud (Ajustar según necesidad)
# ============================================================================

class VerificaInicioSimilitud:
    """Automatización: verifica_inicio (Versión 4 Similitud Visual)"""
    
    def __init__(self):
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.reference_image_path = str(ROOT_DIR / "utils" / "inicio pacs.png")
        self.wait_timeout = 90
        # Región típica del menú lateral (ajustar si es necesario)
        self.region = (0, 24, 194, 1006) 
        self.similarity_threshold = SIMILARITY_THRESHOLD
        self.log_dir = ROOT_DIR / "log" / "verifica_inicio"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Inicializar Feedback Visual
        self.vf = VisualFeedback()
        
        # Cargar imagen de referencia una sola vez
        self.reference_img = self._load_reference()

    def _load_reference(self):
        """Carga la imagen de referencia en escala de grises."""
        if not os.path.exists(self.reference_image_path):
            logger.warning(f"Imagen de referencia no encontrada: {self.reference_image_path}")
            return None
        
        try:
            # Leer imagen y convertir a escala de grises
            img = cv2.imread(self.reference_image_path, cv2.IMREAD_GRAYSCALE)
            if img is not None:
                logger.info(f"Imagen de referencia cargada correctamente. Dimensiones: {img.shape}")
            return img
        except Exception as e:
            logger.error(f"Error cargando imagen de referencia: {e}")
            return None

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
            titles = ["Carestream RIS", "Workflow Information Management", "Vue RIS", "Carestream RIS V11"]
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
        """
        Toma captura de la región y la compara estructuralmente con la referencia.
        Usa cv2.matchTemplate para obtener un porcentaje de similitud global.
        """
        if self.reference_img is None:
            logger.error("No hay imagen de referencia para comparar.")
            return False

        try:
            # Resaltar en pantalla la zona de captura
            if self.vf:
                self.vf.highlight_region(*self.region, duration=0.8)
                time.sleep(0.1)

            # 1. Capturar región actual
            screenshot = pyautogui.screenshot(region=self.region)
            screenshot_np = np.array(screenshot)
            
            # 2. Convertir a escala de grises
            current_gray = cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2GRAY)
            
            # 3. Comparación robusta por Puntos Clave (ORB Feature Matching)
            # ORB es resistente a cambios de idioma, colores y menús contraídos porque busca formas (íconos, bordes).
            orb = cv2.ORB_create(nfeatures=500)
            kp_ref, des_ref = orb.detectAndCompute(self.reference_img, None)
            kp_cur, des_cur = orb.detectAndCompute(current_gray, None)
            
            similarity_pct = 0.0
            
            if des_ref is not None and des_cur is not None:
                bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
                matches = bf.match(des_ref, des_cur)
                
                # Filtrar matches de alta calidad (distancia < 60 es un buen estándar para ORB)
                good_matches = [m for m in matches if m.distance < 60]
                num_matches = len(good_matches)
                
                # Para esta sección de la UI, encontrar > 40-50 puntos clave idénticos confirma que es el programa.
                # Escalamos para que 100 coincidencias representen un "100%" en nuestro log.
                similarity_pct = min((num_matches / 100.0) * 100.0, 100.0)
            
            umbral_pct = self.similarity_threshold * 100

            # 5. Guardar log visual de la captura
            timestamp = datetime.now().strftime("%H%M%S_%f")[:-3]
            log_filename = f"capture_{timestamp}_sim_{similarity_pct:.1f}.png"
            cv2.imwrite(str(self.log_dir / log_filename), current_gray)
            
            if similarity_pct >= umbral_pct:
                logger.info(f"✅ ¡COINCIDENCIA! Similitud: {similarity_pct:.1f}% (Supera el umbral de {umbral_pct}%)")
                return True
            
            logger.info(f"⏳ Similitud insuficiente: {similarity_pct:.1f}% ({num_matches} puntos clave vs {umbral_pct}% req)")
            return False
            
        except Exception as e:
            logger.error(f"Error en verify_visual_match: {e}")
            return False

    def run(self) -> dict:
        logger.info(f"Iniciando Verificación de Inicio V4 (Similitud Visual > {self.similarity_threshold*100}%)")
        self.db_update_status('En Proceso')
        
        start_time = time.time()
        
        while (time.time() - start_time) < self.wait_timeout:
            # 1. Verificar proceso
            if self.check_process_running():
                # 2. Enfocar ventana
                if self.focus_ris():
                    logger.info(f"[{int(time.time() - start_time)}s] RIS detectado y enfocado. Validando imagen...")
                else:
                    logger.warning(f"[{int(time.time() - start_time)}s] RIS detectado pero no se pudo enfocar.")
                
                time.sleep(2) 
                
                # 3. Verificar contenido visual (Comparación de imagen directa)
                if self.verify_visual_match():
                    return {"status": "SUCCESS", "message": "Inicio verificado visualmente"}
            else:
                logger.debug("Esperando a que el proceso del RIS inicie...")
            
            time.sleep(1)
            
        logger.error("Timeout alcanzado sin confirmación visual del inicio.")
        return {"status": "FAILED", "reason": "No se validó el contenido visual tras el tiempo de espera."}

def main():
    setup_logging()
    automation = VerificaInicioSimilitud()
    results = automation.run()
    
    if results["status"] == "SUCCESS":
        print("ok")
        return 0
    else:
        print(f"Error: {results.get('reason', 'Desconocido')}")
        try:
            msg = f"❌ <b>Error de Inicio Visual (Similitud)</b>\nNo se pudo validar la carga visual del RIS.\n<code>{results.get('reason')}</code>"
            enviar_alerta_todos(msg)
        except: pass
        return 1

if __name__ == "__main__":
    sys.exit(main())
