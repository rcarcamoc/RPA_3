#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script autogenerado: actualiza_estado_v2
Optimizado para V2:
- Sin espera inicial de 5s.
- Ciclo de polling acelerado de ~15s a ~2.5s.
- Refresh ágil y verificación OCR inmediata.
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
pyautogui.FAILSAFE = False
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


def humanized_click(x, y, clicks=1, interval=0.08, hold_time=0.0):
    """
    Realiza un movimiento de mouse humanizado hacia (x, y) y hace click u opcionalmente lo sostiene.
    """
    duration = random.uniform(0.2, 0.4)
    pyautogui.moveTo(x, y, duration=duration, tween=pyautogui.easeInOutQuad)
    time.sleep(random.uniform(0.05, 0.15))
    
    if hold_time > 0.0:
        pyautogui.mouseDown(x, y)
        time.sleep(hold_time)
        pyautogui.mouseUp(x, y)
    else:
        pyautogui.click(clicks=clicks, interval=interval)


class ActualizaEstadoAutomation:
    """Automatización generada: actualiza_estado_v2"""
    
    def __init__(self):
        self.app = None
        self.executor = None
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.target_id = os.environ.get("VAR_TARGET_ID")
        
    def db_update_status(self, status='En Proceso', observacion=None):
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
            script_name = "actualiza_estado_v2"
            
            where_clause = "WHERE id = %s" if self.target_id else "WHERE estado = 'En Proceso'"
            params_prefix = [script_name, status]
            if observacion:
                obs_fmt = f"[{script_name}] {observacion}"[:500]
                query = f"UPDATE registro_acciones SET `update` = NOW(), ultimo_nodo = %s, estado = %s, observacion = %s {where_clause}"
                params = params_prefix + [obs_fmt]
            else:
                query = f"UPDATE registro_acciones SET `update` = NOW(), ultimo_nodo = %s, estado = %s {where_clause}"
                params = params_prefix
                
            if self.target_id:
                params.append(self.target_id)
                
            cursor.execute(query, tuple(params))
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
            if self.target_id:
                query = "SELECT coordenada FROM ris.registro_acciones WHERE id = %s LIMIT 1"
                cursor.execute(query, (self.target_id,))
            else:
                query = "SELECT coordenada FROM ris.registro_acciones WHERE estado = 'En Proceso' ORDER BY id DESC LIMIT 1"
                cursor.execute(query)
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Error consultando coordenada DB: {e}")
            return None

    def check_aprobado_ocr(self, coordinate_str):
        """
        Busca la palabra 'Aprobado' en una franja de 30px de altura en la coordenada Y dada.
        """
        if not coordinate_str or ',' not in coordinate_str:
            logger.warning("Coordenada inválida en DB")
            return False

        try:
            parts = coordinate_str.split(',')
            y_base = int(parts[1])
            
            screen_w, screen_h = pyautogui.size()
            region = (0, max(0, y_base - 17), screen_w, 30)
            
            if vf:
                vf.highlight_region(*region, color="#00FF00", duration=0.5)

            screenshot = pyautogui.screenshot(region=region)
            img_np = np.array(screenshot)
            img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

            try:
                log_dir = Path(r"c:\Desarrollo\RPA_3\rpa_framework\log\estado")
                log_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%H%M%S")
                save_path = log_dir / f"check_aprobado_{timestamp}.png"
                cv2.imwrite(str(save_path), img_bgr)
            except Exception as e_log:
                pass
            
            scale = 3
            img_resized = cv2.resize(img_bgr, (0, 0), fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)
            
            avg_brightness = np.mean(gray)
            if avg_brightness < 100:
                gray = cv2.bitwise_not(gray)
            
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            if pytesseract:
                custom_config = r'--oem 3 --psm 7 -l spa'
                text = pytesseract.image_to_string(binary, config=custom_config)
                detected_text = text.strip().lower()
                
                print(f"[OCR] Texto detectado: \"{detected_text}\"")
                logger.info(f"OCR Texto crudo: '{detected_text}'")
                
                target = "aprobado"
                if target in detected_text:
                    logger.info("✅ Palabra 'Aprobado' detectada directamente.")
                    return True
                
                words = re.findall(r'\w+', detected_text)
                for word in words:
                    if len(word) >= 6:
                        ratio = SequenceMatcher(None, target, word).ratio()
                        if ratio > 0.8:
                            logger.info(f"✨ Coincidencia difusa detectada: '{word}' -> '{target}' (Confianza: {ratio:.2f})")
                            return True
            else:
                logger.error("pytesseract no está instalado.")
                
            return False
        except Exception as e:
            logger.error(f"Error en validación OCR: {e}")
            return False

    def setup(self) -> bool:
        """Conecta a la aplicación objetivo."""
        logger.info("Configurando conexión a la aplicación...")
        
        try:
            patterns = ["Carestream RIS", "Workflow Information Management", "Vue RIS", "Carestream RIS V11"]
            connected = False
            
            all_wins = findwindows.find_elements()
            for pattern in patterns:
                for win in all_wins:
                    if pattern in win.name and "Google Chrome" not in win.name:
                        try:
                            logger.info(f"Conectando a {win.name}")
                            self.app = Application(backend='uia').connect(handle=win.handle)
                            connected = True
                            break
                        except:
                            continue
                if connected:
                    break
            
            if not connected:
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
        self.db_update_status('En Proceso')
        
        try:
            # Enfocar Carestream RIS
            try:
                patterns = ["Carestream RIS", "Workflow Information Management", "Vue RIS", "Carestream RIS V11"]
                all_windows = findwindows.find_elements()
                target_element = None
                
                for pattern in patterns:
                    for win in all_windows:
                        if pattern in win.name and "Google Chrome" not in win.name:
                            target_element = win
                            break
                    if target_element:
                        break
                
                if target_element:
                    window = self.app.window(handle=target_element.handle)
                    window.set_focus()
                    time.sleep(0.5)
                    results["completed"] += 3
                    logger.info(f"[1-3/6] ✅ '{target_element.name}' enfocado correctamente")
            except Exception as e:
                logger.error(f"[1-3/6] ❌ Error enfocando: {e}")

            # Acción 4: Click inicial en Toolbar
            try:
                humanized_click(820, 60, hold_time=0.3)
                results["completed"] += 1
                logger.info("[4/6] ✅ Click inicial toolbar realizado")
            except Exception as e:
                logger.error(f"[4/6] ❌ Error en click inicial: {e}")

            # Loop de Refresh y OCR rápido
            intentos_refresh = 0
            max_wait_time = 180
            start_loop_time = time.time()
            aprobado_confirmado = False

            while not aprobado_confirmado:
                elapsed = time.time() - start_loop_time
                if elapsed > max_wait_time:
                    timeout_msg = f"Se excedió el tiempo máximo de espera ({max_wait_time//60} minutos) sin detectar 'Aprobado'."
                    logger.warning(f"⚠️ {timeout_msg}")
                    try:
                        from rpa_framework.utils.error_handler import notificar_aprobacion_pendiente
                        notificar_aprobacion_pendiente("actualiza_estado_v2.py", timeout_msg)
                    except Exception as e_notif:
                        self.db_update_status('Aprobacion_Pendiente', observacion=timeout_msg)

                    results["status"] = "PENDING_APPROVAL"
                    results["errors"].append({"reason": timeout_msg})
                    results["end_time"] = datetime.now().isoformat()
                    return results

                intentos_refresh += 1
                logger.info(f"🔄 Intento #{intentos_refresh} (Elapsed: {int(elapsed)}s)...")
                
                # Clic rápido en Refresh
                try:
                    humanized_click(1906, 167, hold_time=0.2)
                    time.sleep(1.2) # Tiempo suficiente para recarga de grilla
                except Exception as e:
                    logger.error(f"Error en refresh: {e}")

                # Verificar OCR
                coord = self.fetch_coordinada_db()
                if coord:
                    if self.check_aprobado_ocr(coord):
                        aprobado_confirmado = True
                        results["completed"] += 2
                        logger.info("🎯 Validación EXITOSA: Se encontró 'Aprobado'.")
                        self.db_update_status('Terminado')
                        break
                    else:
                        # Si no está en primer intento, presionar F5 y breve espera
                        if intentos_refresh % 2 == 0:
                            pyautogui.press('f5')
                            time.sleep(1.0)
                        else:
                            time.sleep(1.0)
                else:
                    logger.warning("⚠️ No se encontró coordenada en DB.")
                    time.sleep(1.5)

            if aprobado_confirmado:
                results["status"] = "SUCCESS"
            else:
                msg_no_aprob = "No se detectó 'Aprobado' tras agotar los reintentos."
                logger.warning(f"⚠️ {msg_no_aprob}")
                results["status"] = "PENDING_APPROVAL"
                results["errors"].append({"reason": msg_no_aprob})

        except Exception as e:
            logger.error(f"❌ Error crítico: {e}")
            results["status"] = "FAILED"
            results["errors"].append({"reason": str(e)})
            try:
                from rpa_framework.utils.error_handler import handle_error_and_exit
                handle_error_and_exit("actualiza_estado_v2.py", str(e))
            except ImportError:
                self.db_update_status('error', observacion=str(e))
        
        results["end_time"] = datetime.now().isoformat()
        logger.info(f"📊 RESUMEN: {results['completed']} OK, Status: {results['status']}")
        
        if results["status"] == "SUCCESS":
            self.db_update_status('Terminado')
        
        return results


def main():
    """Punto de entrada principal."""
    setup_logging()
    automation = ActualizaEstadoAutomation()
    results = automation.run()
    
    print("\n" + "="*50)
    print(f"Resultado: {results['status']}")
    print("="*50)
    
    return 0 if results["status"] in ["SUCCESS", "PENDING_APPROVAL"] else 1

if __name__ == "__main__":
    sys.exit(main())
