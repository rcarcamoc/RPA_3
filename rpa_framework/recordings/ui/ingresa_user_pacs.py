#!/usr/bin/env python
# -*- coding: utf-8 -*-


import sys
import time
import logging
import random
from pathlib import Path
from datetime import datetime

# Agregar raíz del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pywinauto import Application, findwindows
import pyautogui
from core.executor import ActionExecutor
from core.action import Action, ActionType
from utils.logging_setup import setup_logging
from utils.telegram_manager import enviar_alerta_todos
try:
    from rpa_framework.utils.window_utils import maximize_pacs_windows
except ImportError:
    try:
        from utils.window_utils import maximize_pacs_windows
    except ImportError:
        maximize_pacs_windows = None

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
        """Obtiene las credenciales de la BD. Si no hay registro en proceso, toma un médico al azar de la tabla medicos."""
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
            # 1. Intentar obtener credenciales del registro 'En Proceso' actual
            query = "SELECT user, pass FROM ris.registro_acciones WHERE estado = 'En Proceso' AND user IS NOT NULL AND TRIM(user) != '' LIMIT 1"
            cursor.execute(query)
            result = cursor.fetchone()
            if result and result[0] and result[1]:
                conn.close()
                return result[0].strip(), result[1].strip()
            
            # 2. Si no hay registro en proceso o no tiene credenciales, obtener al azar de la tabla medicos
            logger.info("No hay credenciales en proceso. Obteniendo médico al azar de la tabla 'medicos'...")
            cursor.execute("""
                SELECT usuario_integra, clave_integra, nombre_completo 
                FROM ris.medicos 
                WHERE (estado = 'Activo' OR estado IS NULL) 
                  AND usuario_integra IS NOT NULL AND TRIM(usuario_integra) != '' 
                  AND clave_integra IS NOT NULL AND TRIM(clave_integra) != '' 
                ORDER BY RAND() 
                LIMIT 1
            """)
            result = cursor.fetchone()
            conn.close()
            if result and result[0] and result[1]:
                logger.info(f"🎲 Médico seleccionado al azar: {result[2]} (Usuario: {result[0]})")
                return result[0].strip(), result[1].strip()
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
            error_msg = "No se pudieron obtener credenciales válidas (ni en registro_acciones ni en la tabla 'medicos' de la BD)."
            logger.error(error_msg)
            results["status"] = "FAILED"
            results["reason"] = "Missing credentials"
            results["errors"].append({"reason": error_msg})
            # Actualizar estado a error si es posible
            # self.db_update_status('error')
            return results
        
        # Mostrar longitud de las credenciales para depuración
        logger.info(f"Credenciales obtenidas: Usuario (len={len(db_user)}), Pass (len={len(db_pass)})")
        # Log de depuración para ver qué se va a escribir exactamente
        logger.info(f"DEBUG: db_user='{db_user}', db_pass='{'*' * len(db_pass)}'")
        
        try:
            # Acción 1: CLICK Username
            try:
                # Mover cursor a la ubicación antes del clic
                pyautogui.moveTo(980, 435, duration=0.5)
                action = Action(
                    type=ActionType.DOUBLE_CLICK,
                    selector={'automation_id': 'txtUsername'},
                    position={'x': 980, 'y': 435},
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
                # Acción 3: KEY_PRESS TAB
                action = Action(
                    type=ActionType.KEY_PRESS,
                    key_code="TAB",
                    timestamp=datetime.fromisoformat("2026-02-11T13:49:58.955496")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info("[3/6] TAB para pasar a password")
                time.sleep(0.5)
                
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

            # Acción 5: CLICK Login Robusto
            try:
                base_x, base_y = 980, 572
                logger.info(f"Ejecutando clic robusto en ({base_x}, {base_y})")
                
                # Asegurar foco moviendo el mouse primero (humanizado)
                pyautogui.moveTo(base_x, base_y, duration=0.5)
                
                # Simular clic humano: Presionar, esperar 150ms, soltar
                pyautogui.mouseDown(base_x, base_y, button='left')
                time.sleep(0.15) 
                pyautogui.mouseUp(base_x, base_y, button='left')
                
                results["completed"] += 1
                logger.info("[5/6] clic robusto completado")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 5, "type": "click", "reason": str(e)})
                logger.error(f"[5/6] clic: {e}")

            # Maximización deshabilitada para este nodo
            # time.sleep(2)
            # if maximize_pacs_windows:
            #     try:
            #         logger.info("Maximizando ventana de Carestream Vue PACS / RIS tras login...")
            #         max_count = maximize_pacs_windows()
            #         logger.info(f"Ventanas maximizadas tras login: {max_count}")
            #     except Exception as max_e:
            #         logger.warning(f"Aviso maximizando tras login: {max_e}")

            results["status"] = "SUCCESS" if results["failed"] == 0 else "PARTIAL"
            
        except Exception as e:
            logger.error(f"Error critico: {e}")
            results["status"] = "FAILED"
            results["errors"].append({"reason": str(e)})
            # self.db_update_status('error')
        
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
    
    if results["status"] != "SUCCESS":
        errores = "\\n".join([f"- Acción {e.get('action_idx', '?')}: {e.get('reason', 'Error general')}" for e in results.get('errors', [])])
        try:
            try:
                from utils.error_handler import handle_error_and_exit
            except ImportError:
                from rpa_framework.utils.error_handler import handle_error_and_exit
            handle_error_and_exit("ingresa_user_pacs.py", f"Fallaron acciones durante el login:\\n{errores}")
        except Exception as e:
            logger.error(f"Error invocado manejador de errores: {e}")
            return 1

    # Delay de 10 segundos antes de terminar
    logger.info("Esperando 10 segundos antes de terminar...")
    time.sleep(10)
    return 0


if __name__ == "__main__":
    sys.exit(main())
