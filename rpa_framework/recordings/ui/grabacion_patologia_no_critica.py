#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script autogenerado: grabacion_patologia_no_critica
Generado: 2026-01-07 17:28:50
Total de acciones: 60
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


class GrabacionPatologiaNoCriticaAutomation:
    """Automatización generada: grabacion_patologia_no_critica"""
    
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
            script_name = "grabacion_patologia_no_critica"
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
            "total_actions": 60,
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
                    selector={'automation_id': '[Editor] Edit Area'},
                    position={'x': 837, 'y': 227},
                    timestamp=datetime.fromisoformat("2026-01-07T17:24:58.366132")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[1/60] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 1, "type": "click", "reason": str(e)})
                logger.error(f"[1/60] ❌ click: {e}")

            # Acción 2: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'name': 'Diagnosticar', 'control_type': 'MenuItem'},
                    position={'x': 1017, 'y': 410},
                    timestamp=datetime.fromisoformat("2026-01-07T17:25:32.790943")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[2/60] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 2, "type": "click", "reason": str(e)})
                logger.error(f"[2/60] ❌ click: {e}")

            # Acción 3: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'name': 'Escritorio 1', 'control_type': 'Pane'},
                    position={'x': 662, 'y': 929},
                    timestamp=datetime.fromisoformat("2026-01-07T17:25:44.037634")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[3/60] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 3, "type": "click", "reason": str(e)})
                logger.error(f"[3/60] ❌ click: {e}")

            # Acción 4: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'Result Grid Wrapper'},
                    position={'x': 1284, 'y': 602},
                    timestamp=datetime.fromisoformat("2026-01-07T17:25:45.321969")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[4/60] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 4, "type": "click", "reason": str(e)})
                logger.error(f"[4/60] ❌ click: {e}")

            # Acción 5: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'name': 'Edit Cell', 'control_type': 'MenuItem'},
                    position={'x': 1339, 'y': 607},
                    timestamp=datetime.fromisoformat("2026-01-07T17:25:46.340420")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[5/60] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 5, "type": "click", "reason": str(e)})
                logger.error(f"[5/60] ❌ click: {e}")

            # Acción 6: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': '1511414'},
                    position={'x': 305, 'y': 395},
                    timestamp=datetime.fromisoformat("2026-01-07T17:25:48.401650")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[6/60] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 6, "type": "click", "reason": str(e)})
                logger.error(f"[6/60] ❌ click: {e}")

            # Acción 7: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': '1511414'},
                    position={'x': 305, 'y': 225},
                    timestamp=datetime.fromisoformat("2026-01-07T17:25:51.991564")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[7/60] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 7, "type": "click", "reason": str(e)})
                logger.error(f"[7/60] ❌ click: {e}")

            # Acción 8: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'name': 'Copy', 'control_type': 'MenuItem'},
                    position={'x': 363, 'y': 307},
                    timestamp=datetime.fromisoformat("2026-01-07T17:25:53.645347")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[8/60] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 8, "type": "click", "reason": str(e)})
                logger.error(f"[8/60] ❌ click: {e}")

            # Acción 9: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'name': 'Escritorio 1', 'control_type': 'Pane'},
                    position={'x': 919, 'y': 954},
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:00.604068")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[9/60] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 9, "type": "click", "reason": str(e)})
                logger.error(f"[9/60] ❌ click: {e}")

            # Acción 10: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': '2689638'},
                    position={'x': 509, 'y': 58},
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:03.399242")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[10/60] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 10, "type": "click", "reason": str(e)})
                logger.error(f"[10/60] ❌ click: {e}")

            # Acción 11: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': '[Editor] Edit Area'},
                    position={'x': 814, 'y': 219},
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:05.873437")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[11/60] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 11, "type": "click", "reason": str(e)})
                logger.error(f"[11/60] ❌ click: {e}")

            # Acción 12: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'name': 'Diagnosticar', 'control_type': 'MenuItem'},
                    position={'x': 893, 'y': 411},
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:07.939113")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[12/60] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 12, "type": "click", "reason": str(e)})
                logger.error(f"[12/60] ❌ click: {e}")

            # Acción 13: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': '2689638'},
                    position={'x': 580, 'y': 60},
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:18.382374")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[13/60] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 13, "type": "click", "reason": str(e)})
                logger.error(f"[13/60] ❌ click: {e}")

            # Acción 14: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': '[Editor] Edit Area'},
                    position={'x': 814, 'y': 222},
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:21.068125")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[14/60] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 14, "type": "click", "reason": str(e)})
                logger.error(f"[14/60] ❌ click: {e}")

            # Acción 15: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'name': 'Diagnosticar', 'control_type': 'MenuItem'},
                    position={'x': 902, 'y': 417},
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:23.527765")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[15/60] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 15, "type": "click", "reason": str(e)})
                logger.error(f"[15/60] ❌ click: {e}")

            # Acción 16: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'Appid: {6D809377-6AF0-444B-8957-A3773F02200E}\\Carestream\\PACS\\cshpacs\\mv_client\\mp.exe'},
                    position={'x': 874, 'y': 1065},
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:26.301904")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[16/60] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 16, "type": "click", "reason": str(e)})
                logger.error(f"[16/60] ❌ click: {e}")

            # Acción 17: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'm_TextControl'},
                    position={'x': 421, 'y': 310},
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:27.779625")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[17/60] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 17, "type": "click", "reason": str(e)})
                logger.error(f"[17/60] ❌ click: {e}")

            # Acción 18: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'm_TextControl'},
                    position={'x': 383, 'y': 318},
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:28.349689")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[18/60] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 18, "type": "click", "reason": str(e)})
                logger.error(f"[18/60] ❌ click: {e}")

            # Acción 19: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'name': 'Pegar', 'control_type': 'MenuItem'},
                    position={'x': 481, 'y': 377},
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:30.548666")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[19/60] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 19, "type": "click", "reason": str(e)})
                logger.error(f"[19/60] ❌ click: {e}")

            # Acción 20: TYPE_TEXT
            try:
                action = Action(
                    type=ActionType.TYPE_TEXT,
                    text='\x1a',
                    selector={'name': 'Pegar', 'control_type': 'MenuItem'},
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:34.479378")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[20/60] ✅ type_text")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 20, "type": "type_text", "reason": str(e)})
                logger.error(f"[20/60] ❌ type_text: {e}")

            # Acción 21: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'm_TextControl'},
                    position={'x': 527, 'y': 563},
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:34.531532")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[21/60] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 21, "type": "click", "reason": str(e)})
                logger.error(f"[21/60] ❌ click: {e}")

            # Acción 22: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'm_TextControl'},
                    position={'x': 390, 'y': 511},
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:35.395806")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[22/60] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 22, "type": "click", "reason": str(e)})
                logger.error(f"[22/60] ❌ click: {e}")

            # Acción 23: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'm_TextControl'},
                    position={'x': 557, 'y': 614},
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:38.620966")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[23/60] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 23, "type": "click", "reason": str(e)})
                logger.error(f"[23/60] ❌ click: {e}")

            # Acción 24: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'm_TextControl'},
                    position={'x': 504, 'y': 395},
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:40.308720")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[24/60] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 24, "type": "click", "reason": str(e)})
                logger.error(f"[24/60] ❌ click: {e}")

            # Acción 25: TYPE_TEXT
            try:
                action = Action(
                    type=ActionType.TYPE_TEXT,
                    text='\x02',
                    selector={'automation_id': 'm_TextControl'},
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:44.597364")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[25/60] ✅ type_text")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 25, "type": "type_text", "reason": str(e)})
                logger.error(f"[25/60] ❌ type_text: {e}")

            # Acción 26: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'm_TextControl'},
                    position={'x': 467, 'y': 454},
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:44.628704")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[26/60] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 26, "type": "click", "reason": str(e)})
                logger.error(f"[26/60] ❌ click: {e}")

            # Acción 27: TYPE_TEXT
            try:
                action = Action(
                    type=ActionType.TYPE_TEXT,
                    text='\x02',
                    selector={'automation_id': 'm_TextControl'},
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:47.921985")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[27/60] ✅ type_text")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 27, "type": "type_text", "reason": str(e)})
                logger.error(f"[27/60] ❌ type_text: {e}")

            # Acción 28: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'm_TextControl'},
                    position={'x': 471, 'y': 258},
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:49.337863")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[28/60] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 28, "type": "click", "reason": str(e)})
                logger.error(f"[28/60] ❌ click: {e}")

            # Acción 29: KEY
            try:
                action = Action(
                    type=ActionType.KEY_PRESS,
                    key_code="BACKSPACE",
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:51.046488")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[29/60] ✅ key")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 29, "type": "key", "reason": str(e)})
                logger.error(f"[29/60] ❌ key: {e}")

            # Acción 30: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'm_TextControl'},
                    position={'x': 343, 'y': 274},
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:52.399646")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[30/60] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 30, "type": "click", "reason": str(e)})
                logger.error(f"[30/60] ❌ click: {e}")

            # Acción 31: TYPE_TEXT
            try:
                action = Action(
                    type=ActionType.TYPE_TEXT,
                    text='\x02',
                    selector={'automation_id': 'm_TextControl'},
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:55.283964")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[31/60] ✅ type_text")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 31, "type": "type_text", "reason": str(e)})
                logger.error(f"[31/60] ❌ type_text: {e}")

            # Acción 32: KEY
            try:
                action = Action(
                    type=ActionType.KEY_PRESS,
                    key_code="UP",
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:55.284579")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[32/60] ✅ key")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 32, "type": "key", "reason": str(e)})
                logger.error(f"[32/60] ❌ key: {e}")

            # Acción 33: KEY
            try:
                action = Action(
                    type=ActionType.KEY_PRESS,
                    key_code="DOWN",
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:56.432991")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[33/60] ✅ key")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 33, "type": "key", "reason": str(e)})
                logger.error(f"[33/60] ❌ key: {e}")

            # Acción 34: KEY
            try:
                action = Action(
                    type=ActionType.KEY_PRESS,
                    key_code="DOWN",
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:56.817043")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[34/60] ✅ key")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 34, "type": "key", "reason": str(e)})
                logger.error(f"[34/60] ❌ key: {e}")

            # Acción 35: KEY
            try:
                action = Action(
                    type=ActionType.KEY_PRESS,
                    key_code="DOWN",
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:57.015489")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[35/60] ✅ key")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 35, "type": "key", "reason": str(e)})
                logger.error(f"[35/60] ❌ key: {e}")

            # Acción 36: KEY
            try:
                action = Action(
                    type=ActionType.KEY_PRESS,
                    key_code="DOWN",
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:57.206491")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[36/60] ✅ key")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 36, "type": "key", "reason": str(e)})
                logger.error(f"[36/60] ❌ key: {e}")

            # Acción 37: KEY
            try:
                action = Action(
                    type=ActionType.KEY_PRESS,
                    key_code="DOWN",
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:57.700537")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[37/60] ✅ key")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 37, "type": "key", "reason": str(e)})
                logger.error(f"[37/60] ❌ key: {e}")

            # Acción 38: KEY
            try:
                action = Action(
                    type=ActionType.KEY_PRESS,
                    key_code="DOWN",
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:57.733914")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[38/60] ✅ key")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 38, "type": "key", "reason": str(e)})
                logger.error(f"[38/60] ❌ key: {e}")

            # Acción 39: KEY
            try:
                action = Action(
                    type=ActionType.KEY_PRESS,
                    key_code="DOWN",
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:57.763630")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[39/60] ✅ key")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 39, "type": "key", "reason": str(e)})
                logger.error(f"[39/60] ❌ key: {e}")

            # Acción 40: KEY
            try:
                action = Action(
                    type=ActionType.KEY_PRESS,
                    key_code="DOWN",
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:57.805273")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[40/60] ✅ key")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 40, "type": "key", "reason": str(e)})
                logger.error(f"[40/60] ❌ key: {e}")

            # Acción 41: KEY
            try:
                action = Action(
                    type=ActionType.KEY_PRESS,
                    key_code="DOWN",
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:57.836095")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[41/60] ✅ key")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 41, "type": "key", "reason": str(e)})
                logger.error(f"[41/60] ❌ key: {e}")

            # Acción 42: KEY
            try:
                action = Action(
                    type=ActionType.KEY_PRESS,
                    key_code="DOWN",
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:57.863384")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[42/60] ✅ key")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 42, "type": "key", "reason": str(e)})
                logger.error(f"[42/60] ❌ key: {e}")

            # Acción 43: KEY
            try:
                action = Action(
                    type=ActionType.KEY_PRESS,
                    key_code="DOWN",
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:57.897320")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[43/60] ✅ key")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 43, "type": "key", "reason": str(e)})
                logger.error(f"[43/60] ❌ key: {e}")

            # Acción 44: KEY
            try:
                action = Action(
                    type=ActionType.KEY_PRESS,
                    key_code="DOWN",
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:57.931098")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[44/60] ✅ key")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 44, "type": "key", "reason": str(e)})
                logger.error(f"[44/60] ❌ key: {e}")

            # Acción 45: KEY
            try:
                action = Action(
                    type=ActionType.KEY_PRESS,
                    key_code="DOWN",
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:57.967605")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[45/60] ✅ key")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 45, "type": "key", "reason": str(e)})
                logger.error(f"[45/60] ❌ key: {e}")

            # Acción 46: KEY
            try:
                action = Action(
                    type=ActionType.KEY_PRESS,
                    key_code="DOWN",
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:58.355905")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[46/60] ✅ key")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 46, "type": "key", "reason": str(e)})
                logger.error(f"[46/60] ❌ key: {e}")

            # Acción 47: KEY
            try:
                action = Action(
                    type=ActionType.KEY_PRESS,
                    key_code="UP",
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:59.010876")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[47/60] ✅ key")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 47, "type": "key", "reason": str(e)})
                logger.error(f"[47/60] ❌ key: {e}")

            # Acción 48: KEY
            try:
                action = Action(
                    type=ActionType.KEY_PRESS,
                    key_code="DOWN",
                    timestamp=datetime.fromisoformat("2026-01-07T17:26:59.494128")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[48/60] ✅ key")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 48, "type": "key", "reason": str(e)})
                logger.error(f"[48/60] ❌ key: {e}")

            # Acción 49: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'm_TextControl'},
                    position={'x': 383, 'y': 467},
                    timestamp=datetime.fromisoformat("2026-01-07T17:27:02.769148")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[49/60] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 49, "type": "click", "reason": str(e)})
                logger.error(f"[49/60] ❌ click: {e}")

            # Acción 50: TYPE_TEXT
            try:
                action = Action(
                    type=ActionType.TYPE_TEXT,
                    text='\x02',
                    selector={'automation_id': 'm_TextControl'},
                    timestamp=datetime.fromisoformat("2026-01-07T17:27:19.384389")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[50/60] ✅ type_text")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 50, "type": "type_text", "reason": str(e)})
                logger.error(f"[50/60] ❌ type_text: {e}")

            # Acción 51: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'm_TextControl'},
                    position={'x': 311, 'y': 256},
                    timestamp=datetime.fromisoformat("2026-01-07T17:27:21.011720")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[51/60] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 51, "type": "click", "reason": str(e)})
                logger.error(f"[51/60] ❌ click: {e}")

            # Acción 52: KEY
            try:
                action = Action(
                    type=ActionType.KEY_PRESS,
                    key_code="DELETE",
                    timestamp=datetime.fromisoformat("2026-01-07T17:27:22.931073")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[52/60] ✅ key")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 52, "type": "key", "reason": str(e)})
                logger.error(f"[52/60] ❌ key: {e}")

            # Acción 53: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'm_TextControl'},
                    position={'x': 514, 'y': 374},
                    timestamp=datetime.fromisoformat("2026-01-07T17:27:30.566057")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[53/60] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 53, "type": "click", "reason": str(e)})
                logger.error(f"[53/60] ❌ click: {e}")

            # Acción 54: KEY
            try:
                action = Action(
                    type=ActionType.KEY_PRESS,
                    key_code="ENTER",
                    timestamp=datetime.fromisoformat("2026-01-07T17:27:32.550642")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[54/60] ✅ key")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 54, "type": "key", "reason": str(e)})
                logger.error(f"[54/60] ❌ key: {e}")

            # Acción 55: KEY
            try:
                action = Action(
                    type=ActionType.KEY_PRESS,
                    key_code="DOWN",
                    timestamp=datetime.fromisoformat("2026-01-07T17:27:33.452530")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[55/60] ✅ key")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 55, "type": "key", "reason": str(e)})
                logger.error(f"[55/60] ❌ key: {e}")

            # Acción 56: KEY
            try:
                action = Action(
                    type=ActionType.KEY_PRESS,
                    key_code="DOWN",
                    timestamp=datetime.fromisoformat("2026-01-07T17:27:33.622818")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[56/60] ✅ key")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 56, "type": "key", "reason": str(e)})
                logger.error(f"[56/60] ❌ key: {e}")

            # Acción 57: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'name': 'scn_confirm', 'control_type': 'SplitButton'},
                    position={'x': 43, 'y': 93},
                    timestamp=datetime.fromisoformat("2026-01-07T17:27:48.074044")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[57/60] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 57, "type": "click", "reason": str(e)})
                logger.error(f"[57/60] ❌ click: {e}")

            # Acción 58: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'name': 'Escritorio 1', 'control_type': 'Pane'},
                    position={'x': 618, 'y': 960},
                    timestamp=datetime.fromisoformat("2026-01-07T17:27:57.415849")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[58/60] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 58, "type": "click", "reason": str(e)})
                logger.error(f"[58/60] ❌ click: {e}")

            # Acción 59: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'name': 'Escritorio 1', 'control_type': 'Pane'},
                    position={'x': 878, 'y': 948},
                    timestamp=datetime.fromisoformat("2026-01-07T17:28:33.127757")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[59/60] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 59, "type": "click", "reason": str(e)})
                logger.error(f"[59/60] ❌ click: {e}")

            # Acción 60: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'position': {'x': 1413, 'y': 409}},
                    position={'x': 1413, 'y': 409},
                    timestamp=datetime.fromisoformat("2026-01-07T17:28:35.220346")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[60/60] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 60, "type": "click", "reason": str(e)})
                logger.error(f"[60/60] ❌ click: {e}")

            
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
    
    automation = GrabacionPatologiaNoCriticaAutomation()
    results = automation.run()
    
    print("\n" + "="*50)
    print(f"Resultado: {results['status']}")
    print(f"Completadas: {results['completed']}/{results['total_actions']}")
    print(f"Fallidas: {results['failed']}")
    print("="*50)
    
    return 0 if results["status"] == "SUCCESS" else 1


if __name__ == "__main__":
    sys.exit(main())
