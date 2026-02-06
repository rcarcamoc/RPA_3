#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script autogenerado: clic_y_ordenar
Generado: 2026-01-02 14:37:33
Total de acciones: 5
"""

import sys
import time
import logging
import random
import os
from pathlib import Path
from datetime import datetime


# --- CONFIGURACIÓN DE DEPURACIÓN ---
SAVE_DEBUG_IMAGE = True  # Cambiar a False para no guardar capturas OCR
# -----------------------------------

# Agregar raíz del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pywinauto import Application, findwindows
from core.executor import ActionExecutor
from core.action import Action, ActionType
from ocr.engine import OCREngine
from ocr.matcher import OCRMatcher
from ocr.actions import OCRActions
from utils.logging_setup import setup_logging

# Configuración de MySQL (opcional)
try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

logger = logging.getLogger(__name__)


class ClicYOrdenarAutomation:
    """Automatización generada: clic_y_ordenar"""
    
    def __init__(self):
        self.app = None
        self.executor = None
        self.ocr_actions = None
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Carpeta de logs específica
        self.log_dir = Path("rpa_framework/log/clic_y_ordenar")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
    def db_update_status(self, status='En Proceso', obs=None):
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
            script_name = "clic_y_ordenar"
            
            if status == 'Error':
                query = "UPDATE registro_acciones SET estado = 'Error', observacion = %s, `update` = NOW() WHERE estado = 'En Proceso'"
                cursor.execute(query, (obs,))
            else:
                query = "UPDATE registro_acciones SET `update` = NOW(), ultimo_nodo = %s, estado = %s WHERE estado = 'En Proceso'"
                cursor.execute(query, (script_name, status))
            
            conn.commit()
            conn.close()
            logger.info(f"[DB] Tracking actualizado: {script_name} ({status})")
        except Exception as e:
            logger.warning(f"[DB Error] {e}")

    def fatal_error(self, message):
        """Actualiza la BD con el error y detiene la ejecución inmediatamente."""
        logger.error(f"❌ ERROR CRÍTICO: {message}")
        self.db_update_status('Error', obs=message)
        print(f"ERROR: {message}")
        sys.exit(1)
    
    def setup(self) -> bool:
        """Conecta a la aplicación objetivo."""
        logger.info("Configurando conexión a la aplicación...")
        
        try:
            # Intentar conectar a ventana activa o Desktop
            try:
                self.app = Application(backend='uia').connect(path="explorer.exe")
            except:
                logger.warning("Usando modo Desktop")
                self.app = Application(backend='uia')
            
            self.executor = ActionExecutor(self.app, {})
            
            # Inicializar OCR para detección robusta
            try:
                logger.info("Inicializando OCR (Tesseract)...")
                engine = OCREngine(
                    engine='tesseract',
                    language='es',
                    confidence_threshold=0.5,
                    use_gpu=True
                )
                matcher = OCRMatcher(threshold=80)
                self.ocr_actions = OCRActions(engine, matcher)
                logger.info("✅ OCR Inicializado")
            except Exception as e:
                logger.warning(f"⚠️ Error inicializando OCR: {e}")

            logger.info("✅ Conexión establecida")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error en setup: {e}")
            return False
    
    def run(self) -> dict:
        """Ejecuta todas las acciones grabadas."""
        # DB Tracking: Start
        self.db_update_status('En Proceso')

        if not self.setup():
            self.fatal_error("Falló el inicio de la aplicación (setup)")
        
        results = {
            "session_id": self.session_id,
            "status": "RUNNING",
            "total_actions": 5,
            "completed": 0,
            "failed": 0,
            "errors": [],
            "start_time": datetime.now().isoformat(),
        }
        
        logger.info(f"🚀 Iniciando ejecución: {results['total_actions']} acciones")
        
        try:
            # Acción 1: OCR Find 'Estado' + 2 Left Clicks (Human-like)
            try:
                # Verificar inicialización de OCR
                if not self.ocr_actions:
                    self.fatal_error("OCR no inicializado. No se puede buscar 'estado'.")

                # Intentar encontrar 'Estado' por OCR en la región de cabecera
                matches = self.ocr_actions.capture_and_find(
                    search_term='estado', 
                    fuzzy=True,
                    take_screenshot=True,
                    region={'left': 186, 'top': 55, 'width': 1734, 'height': 145}
                )
                
                if matches:
                    best = matches[0]
                    base_x = int(best['center']['x'])
                    base_y = int(best['center']['y'])
                    logger.info(f"👁️ OCR encontró 'estado' en ({base_x}, {base_y})")
                    
                    # Guardar imagen de depuración si está habilitado
                    if SAVE_DEBUG_IMAGE:
                        img_name = f"ocr_estado_{self.session_id}.png"
                        img_path = str(self.log_dir / img_name)
                        try:
                            self.ocr_actions.save_screenshot(img_path)
                            logger.info(f"📸 Captura de depuración guardada: {img_path}")
                        except Exception as img_err:
                            logger.warning(f"No se pudo guardar la captura: {img_err}")
                else:
                    self.fatal_error("OCR no encontró el texto 'estado'.")
                
                # Click 1 with slight jitter
                jx1, jy1 = random.randint(-1, 1), random.randint(-1, 1)
                action1 = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': '[Editor] Edit Area'},
                    position={'x': base_x + jx1, 'y': base_y + jy1},
                    timestamp=datetime.fromisoformat("2026-01-02T14:37:03.221837")
                )
                self.executor.execute(action1)
                
                # Human-like delay between clicks (80ms to 180ms)
                time.sleep(random.uniform(0.08, 0.18))

                # Click 2 with different slight jitter
                jx2, jy2 = random.randint(-1, 1), random.randint(-1, 1)
                action2 = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': '[Editor] Edit Area'},
                    position={'x': base_x + jx2, 'y': base_y + jy2},
                    timestamp=datetime.now()
                )
                self.executor.execute(action2)

                results["completed"] += 1
                logger.info(f"[1/2] ✅ 2 clicks (OCR/Humanized)")
            except Exception as e:
                self.fatal_error(f"Error en paso 1 (OCR 2 Clicks): {e}")

            # Delay entre acciones
            time.sleep(random.uniform(1.5, 2.5))

            # Acción 2: 2 Left Clicks (Human-like)
            try:
                base_x, base_y = 1159, 187
                
                # Click 1
                jx1, jy1 = random.randint(-1, 1), random.randint(-1, 1)
                action1 = Action(
                    type=ActionType.CLICK,
                    position={'x': base_x + jx1, 'y': base_y + jy1},
                    timestamp=datetime.fromisoformat("2026-01-02T14:37:11.542074")
                )
                self.executor.execute(action1)
                
                time.sleep(random.uniform(0.08, 0.18))

                # Click 2
                jx2, jy2 = random.randint(-1, 1), random.randint(-1, 1)
                action2 = Action(
                    type=ActionType.CLICK,
                    position={'x': base_x + jx2, 'y': base_y + jy2},
                    timestamp=datetime.now()
                )
                self.executor.execute(action2)

                results["completed"] += 1
                logger.info(f"[2/2] ✅ 2 clicks (humanized)")
            except Exception as e:
                self.fatal_error(f"Error en paso 2 (2 Clicks): {e}")

            results["status"] = "SUCCESS"
            
        except SystemExit:
            raise
        except Exception as e:
            self.fatal_error(f"Error inesperado: {e}")
        
        results["end_time"] = datetime.now().isoformat()
        logger.info(f"📊 RESUMEN: {results['completed']} OK, {results['failed']} FAILED")
        
        # DB Tracking: Final
        self.db_update_status('En Proceso')
        
        return results


def main():
    """Punto de entrada principal."""
    setup_logging()
    
    automation = ClicYOrdenarAutomation()
    results = automation.run()
    
    print("\n" + "="*50)
    print(f"Resultado: {results['status']}")
    print(f"Completadas: {results['completed']}/5")
    print(f"Fallidas: 0")
    print("="*50)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

