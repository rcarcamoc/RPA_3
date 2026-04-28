#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script autogenerado: actualiza_estado
Generado: 2026-02-25 13:19:38
Modificado: OCR + Loop de validación "Aprobado"
"""

import sys
import time
import logging
from pathlib import Path
from datetime import datetime
import os
import random
import re
import numpy as np
import cv2
import pyautogui
from PIL import Image
from difflib import SequenceMatcher

# Agregar raíz del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pywinauto import Application, findwindows
from core.executor import ActionExecutor
from core.action import Action, ActionType
from utils.logging_setup import setup_logging

try:
    from utils.visual_feedback import VisualFeedback
    vf = VisualFeedback()
except ImportError:
    vf = None

# Imports condicionales para OCR
try:
    import pytesseract
except ImportError:
    pytesseract = None

# Configuración de MySQL (opcional)
try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

logger = logging.getLogger(__name__)


def humanized_click(x, y, clicks=1, interval=0.1, hold_time=0.0):
    """
    Realiza un movimiento de mouse humanizado hacia (x, y) y hace click u opcionalmente lo sostiene.
    """
    duration = random.uniform(0.5, 1.0)
    pyautogui.moveTo(x, y, duration=duration, tween=pyautogui.easeInOutQuad)
    time.sleep(random.uniform(0.1, 0.3))
    
    if hold_time > 0.0:
        pyautogui.mouseDown(x, y)
        time.sleep(hold_time)
        pyautogui.mouseUp(x, y)
    else:
        pyautogui.click(clicks=clicks, interval=interval)


class ActualizaEstadoAutomation:
    """Automatización generada: actualiza_estado"""
    
    def __init__(self):
        self.app = None
        self.executor = None
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
    def db_update_status(self, status='En Proceso'):
        """Actualiza el estado en la BD"""
        if not HAS_MYSQL:
            return
        try:
            conn = mysql.connector.connect(
                host='localhost',
                user='root',
                password='',
                database='ris'
            )
            cursor = conn.cursor()
            script_name = "actualiza_estado"
            query = "UPDATE registro_acciones SET `update` = NOW(), ultimo_nodo = %s, estado = %s WHERE estado = 'En Proceso'"
            cursor.execute(query, (script_name, status))
            conn.commit()
            conn.close()
            logger.info(f"[DB] Tracking actualizado: {script_name} ({status})")
        except Exception as e:
            logger.warning(f"[DB Error] {e}")

    def fetch_coordinada_db(self):
        """Consulta la coordenada desde la BBDD."""
        if not HAS_MYSQL:
            return None
        try:
            conn = mysql.connector.connect(
                host='localhost',
                user='root',
                password='',
                database='ris'
            )
            cursor = conn.cursor()
            query = "SELECT coordenada FROM ris.registro_acciones WHERE estado = 'En Proceso' LIMIT 1"
            cursor.execute(query)
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Error consultando coordenada DB: {e}")
            return None

    def check_aprobado_ocr(self, coordinate_str):
        """
        Busca la palabra 'Aprobado' en una franja de 20px de altura en la coordenada Y dada,
        cubriendo todo el ancho de la pantalla (o región lógica).
        Incluye feedback visual, guardado de logs y visualización de textos.
        """
        if not coordinate_str or ',' not in coordinate_str:
            logger.warning("Coordenada inválida en DB")
            return False

        try:
            # Parsear coordenada (ej: "433,338")
            parts = coordinate_str.split(',')
            y_base = int(parts[1])
            
            # Definir región: Todo el ancho, 30px de alto centrado en Y
            screen_w, screen_h = pyautogui.size()
            region = (0, y_base - 17, screen_w, 30)
            
            # 1. Feedback Visual: Destacar zona en pantalla
            if vf:
                vf.highlight_region(*region, color="#00FF00", duration=1.0)
                time.sleep(0.2)

            logger.info(f"📸 Capturando región OCR para validación: {region}")
            screenshot = pyautogui.screenshot(region=region)
            img_np = np.array(screenshot)
            img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

            # 2. Guardar captura en log/estado
            try:
                log_dir = Path(r"c:\Desarrollo\RPA_3\rpa_framework\log\estado")
                log_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%H%M%S")
                save_path = log_dir / f"check_aprobado_{timestamp}.png"
                cv2.imwrite(str(save_path), img_bgr)
            except Exception as e_log:
                logger.warning(f"No se pudo guardar log de imagen: {e_log}")
            
            # Preprocesamiento Avanzado:
            # 1. Escalar (3x) para que Tesseract lea mejor fuentes pequeñas
            scale = 3
            img_resized = cv2.resize(img_bgr, (0, 0), fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            
            # 2. Convertir a escala de grises
            gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)
            
            # 3. Detectar si el fondo es oscuro e invertir si es necesario (Tesseract prefiere texto negro sobre blanco)
            # Calculamos el promedio de brillo
            avg_brightness = np.mean(gray)
            if avg_brightness < 100: # Fondo oscuro detectado (como en la captura del usuario)
                logger.info(f"🌑 Fondo oscuro detectado ({avg_brightness:.1f}), invirtiendo para OCR...")
                gray = cv2.bitwise_not(gray)
            
            # 4. Umbralizado Otsu
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            # Guardar la imagen preprocesada para depuración (opcional pero muy útil)
            try:
                preproc_path = log_dir / f"preproc_{timestamp}.png"
                cv2.imwrite(str(preproc_path), binary)
            except:
                pass
            
            if pytesseract:
                logger.info("🔍 Ejecutando OCR mediante Tesseract (spa)...")
                # --psm 6: Asume un bloque de texto uniforme
                # --psm 7: Trata la imagen como una única línea de texto (ideal aquí)
                custom_config = r'--oem 3 --psm 7 -l spa'
                text = pytesseract.image_to_string(binary, config=custom_config)
                detected_text = text.strip().lower()
                
                # MOSTRAR TEXTO DETECTADO EN CONSOLA
                print(f"[OCR] Texto detectado: \"{detected_text}\"")
                logger.info(f"OCR Texto crudo: '{detected_text}'")
                
                # Búsqueda Robusta:
                target = "aprobado"
                
                # A. Búsqueda directa
                if target in detected_text:
                    logger.info("✅ Palabra 'Aprobado' detectada directamente.")
                    return True
                
                # B. Búsqueda difusa (Fuzzy Match) - Tolerancia a un error de letra
                # Dividimos por palabras para comparar
                words = re.findall(r'\w+', detected_text)
                for word in words:
                    if len(word) >= 6: # Filtro para evitar coincidencias cortas
                        ratio = SequenceMatcher(None, target, word).ratio()
                        if ratio > 0.8: # Umbral alto para evitar falsos positivos
                            logger.info(f"✨ Coincidencia difusa detectada: '{word}' -> '{target}' (Confianza: {ratio:.2f})")
                            return True
            else:
                logger.error("pytesseract no está instalado.")
                
            return False
        except Exception as e:
            logger.error(f"Error en validación OCR: {e}")
            return False

    def setup(self) -> bool:
        """Conecta a la aplicación objetivo de forma robusta."""
        logger.info("Configurando conexión a la aplicación...")
        
        try:
            # Lista de posibles patrones en orden de preferencia
            patterns = [".*Carestream RIS.*", ".*RIS.*Client.*", ".*RIS.*"]
            connected = False
            
            for pattern in patterns:
                try:
                    logger.info(f"Intentando conectar con patrón: {pattern}")
                    self.app = Application(backend='uia').connect(title_re=pattern, timeout=2)
                    connected = True
                    break
                except:
                    continue
            
            if not connected:
                logger.warning("No se encontró ventana por título, conectando a Desktop")
                self.app = Application(backend='uia')
            
            self.executor = ActionExecutor(self.app, {})
            logger.info("✅ Conexión establecida")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error en setup: {e}")
            return False
    
    def run(self) -> dict:
        """Ejecuta todas las acciones grabadas."""
        if not self.setup():
            return {"status": "FAILED", "reason": "Setup failed"}
        
        results = {
            "session_id": self.session_id,
            "status": "RUNNING",
            "total_actions": 6,
            "completed": 0,
            "failed": 0,
            "errors": [],
            "start_time": datetime.now().isoformat(),
        }
        
        logger.info(f"🚀 Iniciando ejecución: {results['total_actions']} acciones")
        
        # DB Tracking: Start
        self.db_update_status('En Proceso')
        
        try:
            # Acciones 1-3: Asegurar que el RIS está en primer plano
            try:
                all_windows = findwindows.find_elements()
                target_element = None
                for win in all_windows:
                    if "Carestream" in win.name and "RIS" in win.name:
                        target_element = win
                        break
                
                if not target_element:
                    for win in all_windows:
                        if "RIS" in win.name:
                            target_element = win
                            break
                
                if target_element:
                    logger.info(f"Enfocando ventana encontrada: {target_element.name}")
                    self.app = Application(backend='uia').connect(handle=target_element.handle)
                    self.executor.app = self.app
                    window = self.app.window(handle=target_element.handle)
                    window.set_focus()
                    time.sleep(1.5)
                    results["completed"] += 3
                    logger.info(f"[1-3/6] ✅ '{target_element.name}' enfocado correctamente")
            except Exception as e:
                logger.error(f"[1-3/6] ❌ Error enfocando: {e}")

            # Acción 4: CLICK INICIAL (Toolbar/Menú)
            try:
                humanized_click(700, 60, hold_time=1.0)
                results["completed"] += 1
                logger.info(f"[4/6] ✅ click sostenido inicial")
            except Exception as e:
                logger.error(f"[4/6] ❌ click: {e}")

            # Acción 5: LOOP DE REFRESH Y VALIDACIÓN OCR
            intentos_refresh = 0
            max_wait_time = 180 # 3 minutos en segundos
            start_loop_time = time.time()
            aprobado_confirmado = False

            while not aprobado_confirmado:
                # Verificar tiempo transcurrido
                elapsed = time.time() - start_loop_time
                if elapsed > max_wait_time:
                    timeout_msg = f"Se excedió el tiempo máximo de espera ({max_wait_time//60} minutos) sin detectar 'Aprobado'."
                    logger.error(f"❌ {timeout_msg}")
                    try:
                        try:
            from utils.error_handler import handle_error_and_exit
        except ImportError:
            from rpa_framework.utils.error_handler import handle_error_and_exit
                        handle_error_and_exit("actualiza_estado.py", timeout_msg)
                    except ImportError:
                        self.db_update_status('Terminado - Pending')
                        results["status"] = "TIMEOUT"
                        results["errors"].append({"reason": timeout_msg})
                        results["end_time"] = datetime.now().isoformat()
                        return results

                intentos_refresh += 1
                logger.info(f"🔄 Intento de validación #{intentos_refresh} (Tiempo transcurrido: {int(elapsed)}s)...")
                
                # Hacer clic en Refresh
                try:
                    humanized_click(1906, 167, hold_time=1.0)
                    logger.info(f"[5/6] ✅ Refresh clicado (Intento {intentos_refresh})")
                    time.sleep(10) # Esperar a que la lista cargue
                except Exception as e:
                    logger.error(f"Error en refresh: {e}")
                
                # Accion extra: Presionar F5
                try:
                    pyautogui.press('f5')
                    logger.info(f"⌨️ F5 presionado (Intento {intentos_refresh})")
                    time.sleep(2)
                except Exception as e:
                    logger.error(f"Error al presionar F5: {e}")
                
                # Consultar coordenada y verificar OCR
                coord = self.fetch_coordinada_db()
                if coord:
                    if self.check_aprobado_ocr(coord):
                        aprobado_confirmado = True
                        results["completed"] += 2 # Sumar 2 para alcanzar las 6 acciones totales (Refresh + Validación)
                        logger.info("🎯 Validación EXITOSA: Se encontró 'Aprobado'.")
                        # Actualizar estado en BD de forma inmediata al encontrar el texto
                        self.db_update_status('Terminado')
                    else:
                        logger.warning("⏳ 'Aprobado' no encontrado aún. Reintentando...")
                        time.sleep(2)
                else:
                    logger.warning("⚠️ No se encontró coordenada en DB. ¿Se ejecutó el paso previo de búsqueda?")
                    time.sleep(2)


            if aprobado_confirmado:
                results["status"] = "SUCCESS"
            else:
                results["status"] = "PARTIAL"
                results["errors"].append({"reason": "No se detectó 'Aprobado' tras agotar los reintentos."})

        except Exception as e:
            logger.error(f"❌ Error crítico: {e}")
            results["status"] = "FAILED"
            results["errors"].append({"reason": str(e)})
            self.db_update_status('error')
        
        results["end_time"] = datetime.now().isoformat()
        logger.info(f"📊 RESUMEN: {results['completed']} OK, Status: {results['status']}")
        
        if results["status"] == "SUCCESS":
            self.db_update_status('Terminado')
        
        return results


def main():
    """Punto de entrada principal."""
    setup_logging()
    
    logger.info("⏳ Iniciando pausa de 5 segundos antes de comenzar...")
    time.sleep(5)
    
    automation = ActualizaEstadoAutomation()
    results = automation.run()
    
    print("\n" + "="*50)
    print(f"Resultado: {results['status']}")
    print("="*50)
    
    return 0 if results["status"] == "SUCCESS" else 1

if __name__ == "__main__":
    sys.exit(main())
