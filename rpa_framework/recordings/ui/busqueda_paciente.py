#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script autogenerado: busqueda_paciente
Generado: 2026-01-02 07:37:17
Total de acciones: 5
"""

import sys
import time
import logging
from pathlib import Path
from datetime import datetime
import pyautogui
pyautogui.FAILSAFE = False

# Agregar raíz del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pywinauto import Application, findwindows
from core.executor import ActionExecutor
from core.action import Action, ActionType
from utils.logging_setup import setup_logging

# Configuración de MySQL (opcional)
try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

logger = logging.getLogger(__name__)


class BusquedaPacienteAutomation:
    """Automatización generada: busqueda_paciente"""
    
    def __init__(self):
        self.app = None
        self.executor = None
        self.executor = None
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Init Visual Feedback
        try:
            from rpa_framework.utils.visual_feedback import VisualFeedback
            self.vf = VisualFeedback()
        except:
            self.vf = None
        
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
            script_name = "busqueda_paciente"
            
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
        """Actualiza la BD con el error, envía Telegram y detiene la ejecución."""
        logger.error(f"❌ ERROR CRÍTICO: {message}")
        try:
            try:
                from utils.error_handler import handle_error_and_exit
            except ImportError:
                from rpa_framework.utils.error_handler import handle_error_and_exit
            handle_error_and_exit("busqueda_paciente.py", message)
        except ImportError:
            self.db_update_status('Error', obs=message)
            print(f"ERROR: {message}")
            sys.exit(1)

    
    def get_patient_id(self):
        """Obtiene el id_primario desde la BD."""
        if not HAS_MYSQL:
            logger.warning("No se puede obtener patient_id: MySQL no disponible")
            return None
        try:
            conn = mysql.connector.connect(
                host='localhost',
                user='root',
                password='',
                database='ris'
            )
            cursor = conn.cursor()
            query = "SELECT replace(numero_documento,'-','') as id_primario FROM registro_acciones WHERE estado ='En Proceso' LIMIT 1"
            cursor.execute(query)
            row = cursor.fetchone()
            conn.close()
            if row:
                return str(row[0])
            return None
        except Exception as e:
            logger.error(f"[DB Error] Fallo al obtener patient_id: {e}")
            return None
    
    def setup(self) -> bool:
        """Conecta a la aplicación objetivo."""
        logger.info("Configurando conexión a la aplicación...")
        
        try:
            # Intentar encontrar una ventana que contenga "Carestream"
            try:
                # Buscamos ventanas con Carestream en el título
                titulos = findwindows.find_elements(title_re=".*Carestream.*")
                if titulos:
                    logger.info(f"Ventana Carestream encontrada: {titulos[0].name}")
                    self.app = Application(backend='uia').connect(handle=titulos[0].handle)
                else:
                    logger.warning("No se encontró ventana Carestream, conectando a explorer.exe")
                    self.app = Application(backend='uia').connect(path="explorer.exe")
            except Exception as e:
                logger.warning(f"Fallo al conectar específicamente: {e}. Usando modo Desktop")
                self.app = Application(backend='uia')
            
            self.executor = ActionExecutor(self.app, {})
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
            # Acción 2: 6 Tabulaciones para posicionarse en Patient ID
            try:                                                
                logger.info("Enviando 5 tabulaciones para posicionarse en el campo Patient ID...")
                for _ in range(5):
                    pyautogui.press('tab')
                    time.sleep(0.15)
                time.sleep(0.3)
                
                results["completed"] += 1
                logger.info("[2/5] ✅ 6 tabulaciones enviadas")
            except Exception as e:
                self.fatal_error(f"No se pudo enviar las tabulaciones: {e}")

            # Acción 3: TYPE_TEXT (Ingresar ID de paciente en el campo enfocado)
            try:
                patient_id = self.get_patient_id()
                if not patient_id:
                    self.fatal_error("No se encontró patient_id en la base de datos")
                
                logger.info(f"Ingresando ID de paciente: {patient_id}")
                
                # Escribir usando pyautogui en el campo enfocado
                pyautogui.write(patient_id, interval=0.1)
                time.sleep(0.5)

                results["completed"] += 1
                logger.info(f"[3/5] ✅ type_text ({patient_id}) con pyautogui")
            except Exception as e:
                self.fatal_error(f"Fallo al escribir ID de paciente: {e}")

            # Acción 4: CLICK btnSearch (Robusto)
            try:
                base_x, base_y = 1702, 291
                logger.info(f"Ejecutando clic robusto en btnSearch ({base_x}, {base_y})")
                
                if self.vf: self.vf.highlight_click(base_x, base_y)
                
                pyautogui.moveTo(base_x, base_y, duration=0.2)
                time.sleep(0.5)
                
                pyautogui.mouseDown(base_x, base_y, button='left')
                time.sleep(0.15)
                pyautogui.mouseUp(base_x, base_y, button='left')
                
                results["completed"] += 1
                logger.info(f"[4/5] ✅ click Search")
            except Exception as e:
                self.fatal_error(f"No se pudo hacer clic en botón Buscar: {e}")

            # Acción 5: DOUBLE_CLICK Robusto
            try:
                base_x, base_y = 1010, 368
                logger.info(f"Realizando doble clic robusto en ({base_x}, {base_y})")
                
                if self.vf: self.vf.highlight_click(base_x, base_y)
                
                pyautogui.moveTo(base_x, base_y, duration=0.2)
                time.sleep(0.5)
                
                # Clic 1
                pyautogui.mouseDown(base_x, base_y, button='left')
                time.sleep(0.1)
                pyautogui.mouseUp(base_x, base_y, button='left')
                
                time.sleep(0.1)
                
                # Clic 2
                pyautogui.mouseDown(base_x, base_y, button='left')
                time.sleep(0.1)
                pyautogui.mouseUp(base_x, base_y, button='left')
                
                results["completed"] += 1
                logger.info(f"[5/5] ✅ double_click (robusto)")
            except Exception as e:
                self.fatal_error(f"No se pudo hacer doble clic en el paciente: {e}")

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
    
    automation = BusquedaPacienteAutomation()
    results = automation.run()
    
    print("\n" + "="*50)
    print(f"Resultado: {results['status']}")
    print(f"Completadas: {results['completed']}/5")
    print(f"Fallidas: 0")
    print("="*50)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
