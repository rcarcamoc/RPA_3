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
            script_name = "busqueda_paciente"
            query = "UPDATE registro_acciones SET `update` = NOW(), ultimo_nodo = %s, estado = %s WHERE estado = 'En Proceso'"
            cursor.execute(query, (script_name, status))
            conn.commit()
            conn.close()
            logger.info(f"[DB] Tracking actualizado: {script_name} ({status})")
        except Exception as e:
            logger.warning(f"[DB Error] {e}")
    
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
        if not self.setup():
            return {"status": "FAILED", "reason": "Setup failed"}
        
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
        
        # DB Tracking: Start
        self.db_update_status('En Proceso')
        
        try:
           

            # Acción 2: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'mtbPatientId1'},
                    position={'x': 368, 'y': 194},
                    timestamp=datetime.fromisoformat("2026-01-02T07:36:53.452761")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[2/5] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 2, "type": "click", "reason": str(e)})
                logger.error(f"[2/5] ❌ click: {e}")

            # Acción 3: TYPE_TEXT (Estrategia Directa con pyautogui + Fallback)
            try:
                patient_id = self.get_patient_id() or "12345678"
                logger.info(f"Ingresando ID de paciente: {patient_id}")
                
                try:
                    # Buscamos y aseguramos foco con pywinauto
                    element = self.executor.selector_helper.find_element(
                        {'automation_id': 'mtbPatientId1'},
                        timeout=5.0
                    )
                    element.set_focus()
                    element.click_input()
                    logger.info("Foco establecido por selector")
                except Exception as e:
                    logger.warning(f"No se pudo encontrar mtbPatientId1 por selector, usando fallback a coordenadas (368, 194): {e}")
                    pyautogui.click(368, 194)
                
                time.sleep(1) 
                
                # Escribir usando pyautogui
                pyautogui.write(patient_id, interval=0.1)
                time.sleep(1)

                results["completed"] += 1
                logger.info(f"[3/5] ✅ type_text ({patient_id}) con pyautogui")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 3, "type": "type_text", "reason": str(e)})
                logger.error(f"[3/5] ❌ type_text: {e}")

            # Acción 4: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'btnSearch'},
                    position={'x': 1702, 'y': 291},
                    timestamp=datetime.fromisoformat("2026-01-02T07:37:04.786888")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[4/5] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 4, "type": "click", "reason": str(e)})
                logger.error(f"[4/5] ❌ click: {e}")

            # Acción 5: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'position': {'x': 1821, 'y': 920}},
                    position={'x': 1821, 'y': 920},
                    timestamp=datetime.fromisoformat("2026-01-02T07:37:08.279462")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[5/5] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 5, "type": "click", "reason": str(e)})
                logger.error(f"[5/5] ❌ click: {e}")

            
            results["status"] = "SUCCESS" if results["failed"] == 0 else "PARTIAL"
            
        except Exception as e:
            logger.error(f"❌ Error crítico: {e}")
            results["status"] = "FAILED"
            results["errors"].append({"reason": str(e)})
            self.db_update_status('error')
        
        results["end_time"] = datetime.now().isoformat()
        
        logger.info(f"📊 RESUMEN: {results['completed']} OK, {results['failed']} FAILED")
        logger.info(f"Status: {results['status']}")
        
        # DB Tracking: Final
        if results["status"] == "SUCCESS":
            self.db_update_status('En Proceso')
        
        return results


def main():
    """Punto de entrada principal."""
    setup_logging()
    
    automation = BusquedaPacienteAutomation()
    results = automation.run()
    
    print("\n" + "="*50)
    print(f"Resultado: {results['status']}")
    print(f"Completadas: {results['completed']}/{results['total_actions']}")
    print(f"Fallidas: {results['failed']}")
    print("="*50)
    
    return 0 if results["status"] == "SUCCESS" else 1


if __name__ == "__main__":
    sys.exit(main())
