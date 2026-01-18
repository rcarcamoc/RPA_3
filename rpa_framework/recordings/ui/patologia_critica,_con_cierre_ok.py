#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script autogenerado: patologia_critica,_con_cierre_ok
Generado: 2026-01-14 15:11:56
Total de acciones: 16
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


class PatologiaCritica,ConCierreOkAutomation:
    """Automatización generada: patologia_critica,_con_cierre_ok"""
    
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
            script_name = "patologia_critica,_con_cierre_ok"
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
            "total_actions": 16,
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
                    selector={'automation_id': 'Appid: {6D809377-6AF0-444B-8957-A3773F02200E}\\Carestream\\RIS\\Carestream RIS.exe'},
                    position={'x': 955, 'y': 1061},
                    timestamp=datetime.fromisoformat("2026-01-14T15:10:36.573090")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[1/16] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 1, "type": "click", "reason": str(e)})
                logger.error(f"[1/16] ❌ click: {e}")

            # Acción 2: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'tabControl1'},
                    position={'x': 692, 'y': 84},
                    timestamp=datetime.fromisoformat("2026-01-14T15:10:39.561316")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[2/16] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 2, "type": "click", "reason": str(e)})
                logger.error(f"[2/16] ❌ click: {e}")

            # Acción 3: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'cbxClResultadocritico1'},
                    position={'x': 233, 'y': 126},
                    timestamp=datetime.fromisoformat("2026-01-14T15:10:42.178933")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[3/16] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 3, "type": "click", "reason": str(e)})
                logger.error(f"[3/16] ❌ click: {e}")

            # Acción 4: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'name': 'Sí', 'control_type': 'ListItem'},
                    position={'x': 201, 'y': 182},
                    timestamp=datetime.fromisoformat("2026-01-14T15:10:43.561504")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[4/16] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 4, "type": "click", "reason": str(e)})
                logger.error(f"[4/16] ❌ click: {e}")

            # Acción 5: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'cbxClCodigodiagnostico1'},
                    position={'x': 201, 'y': 184},
                    timestamp=datetime.fromisoformat("2026-01-14T15:10:44.998266")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[5/16] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 5, "type": "click", "reason": str(e)})
                logger.error(f"[5/16] ❌ click: {e}")

            # Acción 6: TYPE_TEXT
            try:
                action = Action(
                    type=ActionType.TYPE_TEXT,
                    text='f',
                    selector={'automation_id': 'cbxClCodigodiagnostico1'},
                    timestamp=datetime.fromisoformat("2026-01-14T15:10:49.226758")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[6/16] ✅ type_text")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 6, "type": "type_text", "reason": str(e)})
                logger.error(f"[6/16] ❌ type_text: {e}")

            # Acción 7: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'name': 'FRACTURA DE COLUMNA COMO PRIMER HALLAZGO', 'control_type': 'ListItem'},
                    position={'x': 252, 'y': 215},
                    timestamp=datetime.fromisoformat("2026-01-14T15:10:53.821614")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[7/16] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 7, "type": "click", "reason": str(e)})
                logger.error(f"[7/16] ❌ click: {e}")

            # Acción 8: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'Appid: {6D809377-6AF0-444B-8957-A3773F02200E}\\Carestream\\PACS\\cshpacs\\mv_client\\mp.exe'},
                    position={'x': 914, 'y': 1065},
                    timestamp=datetime.fromisoformat("2026-01-14T15:11:00.418500")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[8/16] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 8, "type": "click", "reason": str(e)})
                logger.error(f"[8/16] ❌ click: {e}")

            # Acción 9: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'name': 'scn_confirm', 'control_type': 'SplitButton'},
                    position={'x': 42, 'y': 92},
                    timestamp=datetime.fromisoformat("2026-01-14T15:11:13.056271")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[9/16] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 9, "type": "click", "reason": str(e)})
                logger.error(f"[9/16] ❌ click: {e}")

            # Acción 10: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'Appid: {6D809377-6AF0-444B-8957-A3773F02200E}\\Carestream\\RIS\\Carestream RIS.exe'},
                    position={'x': 961, 'y': 1061},
                    timestamp=datetime.fromisoformat("2026-01-14T15:11:24.182067")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[10/16] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 10, "type": "click", "reason": str(e)})
                logger.error(f"[10/16] ❌ click: {e}")

            # Acción 11: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': '45681940'},
                    position={'x': 529, 'y': 62},
                    timestamp=datetime.fromisoformat("2026-01-14T15:11:30.336727")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[11/16] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 11, "type": "click", "reason": str(e)})
                logger.error(f"[11/16] ❌ click: {e}")

            # Acción 12: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': '45681940'},
                    position={'x': 672, 'y': 60},
                    timestamp=datetime.fromisoformat("2026-01-14T15:11:31.595248")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[12/16] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 12, "type": "click", "reason": str(e)})
                logger.error(f"[12/16] ❌ click: {e}")

            # Acción 13: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': '[Editor] Edit Area'},
                    position={'x': 570, 'y': 162},
                    timestamp=datetime.fromisoformat("2026-01-14T15:11:36.198004")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[13/16] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 13, "type": "click", "reason": str(e)})
                logger.error(f"[13/16] ❌ click: {e}")

            # Acción 14: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': '45681940'},
                    position={'x': 523, 'y': 63},
                    timestamp=datetime.fromisoformat("2026-01-14T15:11:38.382372")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[14/16] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 14, "type": "click", "reason": str(e)})
                logger.error(f"[14/16] ❌ click: {e}")

            # Acción 15: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': '45681940'},
                    position={'x': 688, 'y': 59},
                    timestamp=datetime.fromisoformat("2026-01-14T15:11:39.975784")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[15/16] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 15, "type": "click", "reason": str(e)})
                logger.error(f"[15/16] ❌ click: {e}")

            # Acción 16: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'position': {'x': 1807, 'y': 157}},
                    position={'x': 1807, 'y': 157},
                    timestamp=datetime.fromisoformat("2026-01-14T15:11:45.320354")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[16/16] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 16, "type": "click", "reason": str(e)})
                logger.error(f"[16/16] ❌ click: {e}")

            
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
    
    automation = PatologiaCritica,ConCierreOkAutomation()
    results = automation.run()
    
    print("\n" + "="*50)
    print(f"Resultado: {results['status']}")
    print(f"Completadas: {results['completed']}/{results['total_actions']}")
    print(f"Fallidas: {results['failed']}")
    print("="*50)
    
    return 0 if results["status"] == "SUCCESS" else 1


if __name__ == "__main__":
    sys.exit(main())
