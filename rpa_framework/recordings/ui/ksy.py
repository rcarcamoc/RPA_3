#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script autogenerado: ksy
Generado: 2026-02-22 16:41:15
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


class KsyAutomation:
    """Automatización generada: ksy"""
    
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
            script_name = "ksy"
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
            # Acción 1: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'name': 'Conectar', 'control_type': 'Button'},
                    position={'x': 1747, 'y': 1003},
                    duration=0.5,
                    wait_before=1.0,
                    timestamp=datetime.fromisoformat("2026-02-22T16:41:00.726203")
                )
                if self.executor.execute(action):
                    results["completed"] += 1
                    logger.info(f"[1/5] ✅ click")
                else:
                    raise Exception("Ejecutor devolvió False")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 1, "type": "click", "reason": str(e)})
                logger.error(f"[1/5] ❌ click: {e}")

            # Acción 2: CLICK (Campo de texto)
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': '1167'},
                    position={'x': 1746, 'y': 911},
                    duration=0.8,
                    wait_before=1.5,
                    timestamp=datetime.fromisoformat("2026-02-22T16:41:03.823948")
                )
                if self.executor.execute(action):
                    results["completed"] += 1
                    logger.info(f"[2/5] ✅ click campo")
                else:
                    raise Exception("Ejecutor devolvió False")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 2, "type": "click", "reason": str(e)})
                logger.error(f"[2/5] ❌ click: {e}")

            # Acción 3: TYPE_TEXT (Sin selector para usar el foco del clic)
            try:
                action = Action(
                    type=ActionType.TYPE_TEXT,
                    text='Mim21556167#',
                    wait_before=1.0,
                    timestamp=datetime.fromisoformat("2026-02-22T16:41:07.526134")
                )
                if self.executor.execute(action):
                    results["completed"] += 1
                    logger.info(f"[3/5] ✅ type_text")
                else:
                    raise Exception("Ejecutor devolvió False")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 3, "type": "type_text", "reason": str(e)})
                logger.error(f"[3/5] ❌ type_text: {e}")

            # Acción 4: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'name': 'Conectar', 'control_type': 'Button'},
                    position={'x': 1755, 'y': 958},
                    duration=0.5,
                    wait_before=1.0,
                    timestamp=datetime.fromisoformat("2026-02-22T16:41:08.346230")
                )
                if self.executor.execute(action):
                    results["completed"] += 1
                    logger.info(f"[4/5] ✅ click")
                else:
                    raise Exception("Ejecutor devolvió False")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 4, "type": "click", "reason": str(e)})
                logger.error(f"[4/5] ❌ click: {e}")

            
            # Acción 5: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'position': {'x': 307, 'y': 214}},
                    position={'x': 307, 'y': 214},
                    duration=0.5,
                    wait_before=1.5,
                    timestamp=datetime.fromisoformat("2026-02-22T16:41:11.235807")
                )
                if self.executor.execute(action):
                    results["completed"] += 1
                    logger.info(f"[5/5] ✅ click")
                else:
                    raise Exception("Ejecutor devolvió False")
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
    
    automation = KsyAutomation()
    results = automation.run()
    
    print("\n" + "="*50)
    print(f"Resultado: {results['status']}")
    print(f"Completadas: {results['completed']}/{results['total_actions']}")
    print(f"Fallidas: {results['failed']}")
    print("="*50)
    
    return 0 if results["status"] == "SUCCESS" else 1


if __name__ == "__main__":
    sys.exit(main())
