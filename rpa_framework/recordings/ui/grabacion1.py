#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script autogenerado: grabacion1
Generado: 2026-02-11 13:50:19
Total de acciones: 17
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


class Grabacion1Automation:
    """Automatización generada: grabacion1"""
    
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
            script_name = "grabacion1"
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
            "total_actions": 17,
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
                    selector={'automation_id': 'txtUsername'},
                    position={'x': 991, 'y': 443},
                    timestamp=datetime.fromisoformat("2026-02-11T13:49:54.451087")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[1/17] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 1, "type": "click", "reason": str(e)})
                logger.error(f"[1/17] ❌ click: {e}")

            # Acción 2: TYPE_TEXT
            try:
                action = Action(
                    type=ActionType.TYPE_TEXT,
                    text='hola',
                    selector={'automation_id': 'txtUsername'},
                    timestamp=datetime.fromisoformat("2026-02-11T13:49:56.991100")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[2/17] ✅ type_text")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 2, "type": "type_text", "reason": str(e)})
                logger.error(f"[2/17] ❌ type_text: {e}")

            # Acción 3: KEY
            try:
                action = Action(
                    type=ActionType.KEY_PRESS,
                    key_code="SPACE",
                    timestamp=datetime.fromisoformat("2026-02-11T13:49:56.992204")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[3/17] ✅ key")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 3, "type": "key", "reason": str(e)})
                logger.error(f"[3/17] ❌ key: {e}")

            # Acción 4: TYPE_TEXT
            try:
                action = Action(
                    type=ActionType.TYPE_TEXT,
                    text='ke',
                    selector=None,
                    timestamp=datetime.fromisoformat("2026-02-11T13:49:57.945050")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[4/17] ✅ type_text")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 4, "type": "type_text", "reason": str(e)})
                logger.error(f"[4/17] ❌ type_text: {e}")

            # Acción 5: KEY
            try:
                action = Action(
                    type=ActionType.KEY_PRESS,
                    key_code="SPACE",
                    timestamp=datetime.fromisoformat("2026-02-11T13:49:57.945432")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[5/17] ✅ key")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 5, "type": "key", "reason": str(e)})
                logger.error(f"[5/17] ❌ key: {e}")

            # Acción 6: TYPE_TEXT
            try:
                action = Action(
                    type=ActionType.TYPE_TEXT,
                    text='ase',
                    selector=None,
                    timestamp=datetime.fromisoformat("2026-02-11T13:49:58.955108")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[6/17] ✅ type_text")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 6, "type": "type_text", "reason": str(e)})
                logger.error(f"[6/17] ❌ type_text: {e}")

            # Acción 7: KEY
            try:
                action = Action(
                    type=ActionType.KEY_PRESS,
                    key_code="TAB",
                    timestamp=datetime.fromisoformat("2026-02-11T13:49:58.955496")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[7/17] ✅ key")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 7, "type": "key", "reason": str(e)})
                logger.error(f"[7/17] ❌ key: {e}")

            # Acción 8: TYPE_TEXT
            try:
                action = Action(
                    type=ActionType.TYPE_TEXT,
                    text='ke',
                    selector=None,
                    timestamp=datetime.fromisoformat("2026-02-11T13:50:00.093654")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[8/17] ✅ type_text")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 8, "type": "type_text", "reason": str(e)})
                logger.error(f"[8/17] ❌ type_text: {e}")

            # Acción 9: KEY
            try:
                action = Action(
                    type=ActionType.KEY_PRESS,
                    key_code="SPACE",
                    timestamp=datetime.fromisoformat("2026-02-11T13:50:00.094699")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[9/17] ✅ key")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 9, "type": "key", "reason": str(e)})
                logger.error(f"[9/17] ❌ key: {e}")

            # Acción 10: TYPE_TEXT
            try:
                action = Action(
                    type=ActionType.TYPE_TEXT,
                    text='tal',
                    selector=None,
                    timestamp=datetime.fromisoformat("2026-02-11T13:50:03.883952")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[10/17] ✅ type_text")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 10, "type": "type_text", "reason": str(e)})
                logger.error(f"[10/17] ❌ type_text: {e}")

            # Acción 11: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'btnLogin'},
                    position={'x': 1018, 'y': 580},
                    timestamp=datetime.fromisoformat("2026-02-11T13:50:03.915945")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[11/17] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 11, "type": "click", "reason": str(e)})
                logger.error(f"[11/17] ❌ click: {e}")

            # Acción 12: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'txtUsername'},
                    position={'x': 1042, 'y': 432},
                    timestamp=datetime.fromisoformat("2026-02-11T13:50:05.690516")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[12/17] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 12, "type": "click", "reason": str(e)})
                logger.error(f"[12/17] ❌ click: {e}")

            # Acción 13: TYPE_TEXT
            try:
                action = Action(
                    type=ActionType.TYPE_TEXT,
                    text='123',
                    selector={'automation_id': 'txtUsername'},
                    timestamp=datetime.fromisoformat("2026-02-11T13:50:10.530029")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[13/17] ✅ type_text")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 13, "type": "type_text", "reason": str(e)})
                logger.error(f"[13/17] ❌ type_text: {e}")

            # Acción 14: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'txtPassword'},
                    position={'x': 1031, 'y': 470},
                    timestamp=datetime.fromisoformat("2026-02-11T13:50:10.563548")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[14/17] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 14, "type": "click", "reason": str(e)})
                logger.error(f"[14/17] ❌ click: {e}")

            # Acción 15: TYPE_TEXT
            try:
                action = Action(
                    type=ActionType.TYPE_TEXT,
                    text='456',
                    selector={'automation_id': 'txtPassword'},
                    timestamp=datetime.fromisoformat("2026-02-11T13:50:13.269723")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[15/17] ✅ type_text")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 15, "type": "type_text", "reason": str(e)})
                logger.error(f"[15/17] ❌ type_text: {e}")

            # Acción 16: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'btnLogin'},
                    position={'x': 1017, 'y': 579},
                    timestamp=datetime.fromisoformat("2026-02-11T13:50:13.307257")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[16/17] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 16, "type": "click", "reason": str(e)})
                logger.error(f"[16/17] ❌ click: {e}")

            # Acción 17: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'position': {'x': 312, 'y': 212}},
                    position={'x': 312, 'y': 212},
                    timestamp=datetime.fromisoformat("2026-02-11T13:50:14.736277")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[17/17] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 17, "type": "click", "reason": str(e)})
                logger.error(f"[17/17] ❌ click: {e}")

            
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
    
    automation = Grabacion1Automation()
    results = automation.run()
    
    print("\n" + "="*50)
    print(f"Resultado: {results['status']}")
    print(f"Completadas: {results['completed']}/{results['total_actions']}")
    print(f"Fallidas: {results['failed']}")
    print("="*50)
    
    return 0 if results["status"] == "SUCCESS" else 1


if __name__ == "__main__":
    sys.exit(main())
