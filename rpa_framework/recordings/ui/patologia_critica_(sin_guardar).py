#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script autogenerado: patologia_critica_(sin_guardar)
Generado: 2026-01-14 14:30:09
Total de acciones: 13
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


class PatologiaCritica(SinGuardar)Automation:
    """Automatización generada: patologia_critica_(sin_guardar)"""
    
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
            script_name = "patologia_critica_(sin_guardar)"
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
            "total_actions": 13,
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
                    position={'x': 911, 'y': 1067},
                    timestamp=datetime.fromisoformat("2026-01-14T14:28:56.190468")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[1/13] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 1, "type": "click", "reason": str(e)})
                logger.error(f"[1/13] ❌ click: {e}")

            # Acción 2: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'tabControl1'},
                    position={'x': 682, 'y': 83},
                    timestamp=datetime.fromisoformat("2026-01-14T14:28:58.885803")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[2/13] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 2, "type": "click", "reason": str(e)})
                logger.error(f"[2/13] ❌ click: {e}")

            # Acción 3: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'cbxClResultadocritico1'},
                    position={'x': 234, 'y': 132},
                    timestamp=datetime.fromisoformat("2026-01-14T14:29:01.553069")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[3/13] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 3, "type": "click", "reason": str(e)})
                logger.error(f"[3/13] ❌ click: {e}")

            # Acción 4: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'name': 'Sí', 'control_type': 'ListItem'},
                    position={'x': 228, 'y': 185},
                    timestamp=datetime.fromisoformat("2026-01-14T14:29:03.191062")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[4/13] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 4, "type": "click", "reason": str(e)})
                logger.error(f"[4/13] ❌ click: {e}")

            # Acción 5: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'cbxClResultadocritico1'},
                    position={'x': 273, 'y': 117},
                    timestamp=datetime.fromisoformat("2026-01-14T14:29:04.557670")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[5/13] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 5, "type": "click", "reason": str(e)})
                logger.error(f"[5/13] ❌ click: {e}")

            # Acción 6: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'cbxClResultadocritico1'},
                    position={'x': 265, 'y': 143},
                    timestamp=datetime.fromisoformat("2026-01-14T14:29:05.329456")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[6/13] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 6, "type": "click", "reason": str(e)})
                logger.error(f"[6/13] ❌ click: {e}")

            # Acción 7: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'cbxClResultadocritico1'},
                    position={'x': 277, 'y': 123},
                    timestamp=datetime.fromisoformat("2026-01-14T14:29:05.956045")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[7/13] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 7, "type": "click", "reason": str(e)})
                logger.error(f"[7/13] ❌ click: {e}")

            # Acción 8: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'name': 'Sí', 'control_type': 'ListItem'},
                    position={'x': 244, 'y': 184},
                    timestamp=datetime.fromisoformat("2026-01-14T14:29:06.994844")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[8/13] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 8, "type": "click", "reason": str(e)})
                logger.error(f"[8/13] ❌ click: {e}")

            # Acción 9: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'cbxClCodigodiagnostico1'},
                    position={'x': 307, 'y': 180},
                    timestamp=datetime.fromisoformat("2026-01-14T14:29:08.928628")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[9/13] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 9, "type": "click", "reason": str(e)})
                logger.error(f"[9/13] ❌ click: {e}")

            # Acción 10: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'name': 'AVE AGUDO', 'control_type': 'ListItem'},
                    position={'x': 206, 'y': 376},
                    timestamp=datetime.fromisoformat("2026-01-14T14:29:11.190112")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[10/13] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 10, "type": "click", "reason": str(e)})
                logger.error(f"[10/13] ❌ click: {e}")

            # Acción 11: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'name': 'Escritorio 1', 'control_type': 'Pane'},
                    position={'x': 306, 'y': 244},
                    timestamp=datetime.fromisoformat("2026-01-14T14:29:13.471342")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[11/13] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 11, "type": "click", "reason": str(e)})
                logger.error(f"[11/13] ❌ click: {e}")

            # Acción 12: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'Appid: {6D809377-6AF0-444B-8957-A3773F02200E}\\Carestream\\PACS\\cshpacs\\mv_client\\mp.exe'},
                    position={'x': 968, 'y': 1066},
                    timestamp=datetime.fromisoformat("2026-01-14T14:29:27.614970")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[12/13] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 12, "type": "click", "reason": str(e)})
                logger.error(f"[12/13] ❌ click: {e}")

            # Acción 13: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'position': {'x': 465, 'y': 704}},
                    position={'x': 465, 'y': 704},
                    timestamp=datetime.fromisoformat("2026-01-14T14:29:39.353563")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[13/13] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 13, "type": "click", "reason": str(e)})
                logger.error(f"[13/13] ❌ click: {e}")

            
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
    
    automation = PatologiaCritica(SinGuardar)Automation()
    results = automation.run()
    
    print("\n" + "="*50)
    print(f"Resultado: {results['status']}")
    print(f"Completadas: {results['completed']}/{results['total_actions']}")
    print(f"Fallidas: {results['failed']}")
    print("="*50)
    
    return 0 if results["status"] == "SUCCESS" else 1


if __name__ == "__main__":
    sys.exit(main())
