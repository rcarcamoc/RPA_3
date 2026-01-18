#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script autogenerado: ingresa_user_pacs
Generado: 2026-01-02 06:52:35
Total de acciones: 6
"""

import sys
import time
import logging
from pathlib import Path
from datetime import datetime

# Agregar raíz del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pywinauto import Application, findwindows
import pyautogui
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


class IngresaUserPacsAutomation:
    """Automatización generada: ingresa_user_pacs"""
    
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
            script_name = "ingresa_user_pacs"
            query = "UPDATE registro_acciones SET `update` = NOW(), ultimo_nodo = %s, estado = %s WHERE estado = 'En Proceso'"
            cursor.execute(query, (script_name, status))
            conn.commit()
            conn.close()
            logger.info(f"[DB] Tracking actualizado: {script_name} ({status})")
        except Exception as e:
            logger.warning(f"[DB Error] {e}")

    def get_credentials(self):
        """Obtiene las credenciales de la BD"""
        if not HAS_MYSQL:
            return None, None
        try:
            conn = mysql.connector.connect(
                host='localhost',
                user='root',
                password='',
                database='ris'
            )
            cursor = conn.cursor()
            query = "SELECT user, pass FROM ris.registro_acciones WHERE estado = 'En Proceso' LIMIT 1"
            cursor.execute(query)
            result = cursor.fetchone()
            conn.close()
            if result:
                return result[0], result[1]
            return None, None
        except Exception as e:
            logger.warning(f"[DB Error] No se pudieron obtener credenciales: {e}")
            return None, None
    
    def setup(self) -> bool:
        """Conecta a la aplicación objetivo (Carestream Vue PACS)."""
        logger.info("Configurando conexión a la aplicación...")
        
        titulo_pacs = "Carestream Vue PACS"
        proceso_pacs = "mp.exe"
        
        try:
            # Intentar conectar a la ventana del PACS
            try:
                logger.info(f"Intentando conectar a ventana: '{titulo_pacs}'")
                self.app = Application(backend='uia').connect(title=titulo_pacs, timeout=10)
                logger.info("Conectado por titulo de ventana")
            except Exception as e:
                logger.warning(f"No se pudo conectar por título: {e}. Intentando por proceso...")
                self.app = Application(backend='uia').connect(path=proceso_pacs, timeout=10)
                logger.info("Conectado por nombre de proceso")
            
            # Traer la ventana al frente
            main_window = self.app.window(title=titulo_pacs)
            main_window.set_focus()
            
            self.executor = ActionExecutor(self.app, {})
            logger.info("Conexion establecida y ventana enfocada")
            return True
            
        except Exception as e:
            logger.error(f"Error en setup (PACS no encontrado): {e}")
            logger.info("Asegúrese de que el PACS esté abierto antes de ejecutar este script.")
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
        
        logger.info(f"Iniciando ejecucion: {results['total_actions']} acciones")
        
        # DB Tracking: Start
        self.db_update_status('En Proceso')
        
        # Obtener credenciales de la base de datos
        db_user, db_pass = self.get_credentials()
        if not db_user or not db_pass:
            logger.warning("No se encontraron credenciales en 'ris.registro_acciones' con estado 'En Proceso'. Usando valores por defecto.")
            db_user = 'nombre_medico'
            db_pass = 'pass:medico'
        else:
            # Mostrar longitud de las credenciales para depuración
            logger.info(f"Credenciales obtenidas: Usuario (len={len(db_user)}), Pass (len={len(db_pass)})")
            # Log de depuración para ver qué se va a escribir exactamente
            logger.info(f"DEBUG: db_user='{db_user}', db_pass='{'*' * len(db_pass)}'")
        
        try:
            # Acción 1: CLICK Username
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'txtUsername'},
                    position={'x': 981, 'y': 430},
                    timestamp=datetime.fromisoformat("2026-01-02T06:52:04.414338")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info("[1/6] click (txtUsername)")
                time.sleep(1) # Esperar a que el foco se asiente
                
                # Acción 2: TYPE_TEXT (Estrategia Directa)
                logger.info(f"Escribiendo usuario: {db_user}")
                pyautogui.write(db_user, interval=0.1)
                results["completed"] += 1
                logger.info("[2/6] usuario escrito con pyautogui")
                time.sleep(1)
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 1, "type": "input_user", "reason": str(e)})
                logger.error(f"[1-2] Error ingresando usuario: {e}")

            # Acción 3: CLICK Password
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'txtPassword'},
                    position={'x': 985, 'y': 473},
                    timestamp=datetime.fromisoformat("2026-01-02T06:52:13.702181")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info("[3/6] click (txtPassword)")
                time.sleep(1)
                
                # Acción 4: TYPE_TEXT (Estrategia Directa)
                logger.info("Escribiendo password...")
                pyautogui.write(db_pass, interval=0.1)
                results["completed"] += 1
                logger.info("[4/6] password escrito con pyautogui")
                time.sleep(1)
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 3, "type": "input_pass", "reason": str(e)})
                logger.error(f"[3-4] Error ingresando password: {e}")

            # Acción 5: CLICK Login
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'btnLogin'},
                    position={'x': 1005, 'y': 572},
                    timestamp=datetime.fromisoformat("2026-01-02T06:52:21.553766")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info("[5/6] click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 5, "type": "click", "reason": str(e)})
                logger.error(f"[5/6] click: {e}")

            # Acción 6: CLICK Final
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'position': {'x': 415, 'y': 315}},
                    position={'x': 415, 'y': 315},
                    timestamp=datetime.fromisoformat("2026-01-02T06:52:26.366618")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info("[6/6] click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 6, "type": "click", "reason": str(e)})
                logger.error(f"[6/6] click: {e}")

            
            results["status"] = "SUCCESS" if results["failed"] == 0 else "PARTIAL"
            
        except Exception as e:
            logger.error(f"Error critico: {e}")
            results["status"] = "FAILED"
            results["errors"].append({"reason": str(e)})
            self.db_update_status('error')
        
        results["end_time"] = datetime.now().isoformat()
        
        logger.info(f"RESUMEN: {results['completed']} OK, {results['failed']} FAILED")
        logger.info(f"Status: {results['status']}")
        
        # DB Tracking: Final
        if results["status"] == "SUCCESS":
            self.db_update_status('En Proceso')
        
        return results


def main():
    """Punto de entrada principal."""
    setup_logging()
    
    automation = IngresaUserPacsAutomation()
    results = automation.run()
    
    print("\n" + "="*50)
    print(f"Resultado: {results['status']}")
    print(f"Completadas: {results['completed']}/{results['total_actions']}")
    print(f"Fallidas: {results['failed']}")
    print("="*50)
    
    return 0 if results["status"] == "SUCCESS" else 1


if __name__ == "__main__":
    sys.exit(main())
