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
from pathlib import Path
from datetime import datetime

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


class ClicYOrdenarAutomation:
    """Automatización generada: clic_y_ordenar"""
    
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
            script_name = "clic_y_ordenar"
            query = "UPDATE registro_acciones SET `update` = NOW(), ultimo_nodo = %s, estado = %s WHERE estado = 'En Proceso'"
            cursor.execute(query, (script_name, status))
            conn.commit()
            conn.close()
            logger.info(f"[DB] Tracking actualizado: {script_name} ({status})")
        except Exception as e:
            logger.warning(f"[DB Error] {e}")
    
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
         # Acción 1: DOUBLE_CLICK
            try:
                action = Action(
                    type=ActionType.DOUBLE_CLICK,
                    selector={'automation_id': '[Editor] Edit Area'},
                    position={'x': 420, 'y': 357},
                    timestamp=datetime.fromisoformat("2026-01-02T14:37:03.221837")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[1/2] ✅ double_click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 1, "type": "double_click", "reason": str(e)})
                logger.error(f"[1/2] ❌ double_click: {e}")

            # Delay entre acciones
            time.sleep(2.0)


           # Acción 2: CLICK
            try:
                action = Action(
                    type=ActionType.DOUBLE_CLICK,
            
                    position={'x': 1159, 'y': 187},
                    timestamp=datetime.fromisoformat("2026-01-02T14:37:11.542074")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[2/2] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 2, "type": "click", "reason": str(e)})
                logger.error(f"[2/2] ❌ click: {e}")


           

            
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
    
    automation = ClicYOrdenarAutomation()
    results = automation.run()
    
    print("\n" + "="*50)
    print(f"Resultado: {results['status']}")
    print(f"Completadas: {results['completed']}/{results['total_actions']}")
    print(f"Fallidas: {results['failed']}")
    print("="*50)
    
    return 0 if results["status"] == "SUCCESS" else 1


if __name__ == "__main__":
    sys.exit(main())
