#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script autogenerado: test1
Generado: 2026-01-11 23:06:05
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
from core.executor import ActionExecutor
from core.action import Action, ActionType
from utils.logging_setup import setup_logging
import re

# Configuración de MySQL (opcional)
try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

logger = logging.getLogger(__name__)


class Test1Automation:
    """Automatización generada: test1"""
    
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
            script_name = "test1"
            query = "UPDATE registro_acciones SET `update` = NOW(), ultimo_nodo = %s, estado = %s WHERE estado = 'En Proceso'"
            cursor.execute(query, (script_name, status))
            conn.commit()
            conn.close()
            logger.info(f"[DB] Tracking actualizado: {script_name} ({status})")
        except Exception as e:
            logger.warning(f"[DB Error] {e}")
    
    def fetch_diagnosis(self):
        """Consulta el diagnóstico desde la base de datos."""
        if not HAS_MYSQL:
            logger.error("MySQL no disponible.")
            return None
        try:
            conn = mysql.connector.connect(
                host='localhost',
                user='root',
                password='',
                database='ris'
            )
            cursor = conn.cursor()
            query = "SELECT diagnostico AS diagnostico_primera_linea FROM ris.registro_acciones WHERE estado = 'En Proceso';"
            cursor.execute(query)
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Error consultando DB: {e}")
            return None

    def type_formatted(self, text):
        """Procesa y escribe el texto asumiendo que el cuadro inicia en NEGRITA."""
        if not text:
            logger.warning("No hay texto para procesar")
            return
            
        # 1. Omitir la primera línea
        lines = text.splitlines()
        if len(lines) > 1:
            text = "\n".join(lines[1:])
            logger.info("Primera línea omitida")
        else:
            logger.warning("El texto tiene una sola línea o está vacío")
            return

        # El cuadro empieza en Negrita (según reporte del usuario)
        current_bold = True 
        
        # 2. Dividir por palabras clave
        parts = re.split(r'(Hallazgos: |Impresión: )', text)
        
        for part in parts:
            if not part:
                continue
                
            is_keyword = part in ["Hallazgos: ", "Impresión: "]
            
            if is_keyword:
                # Si es palabra clave y estamos en normal, encender negrita
                if not current_bold:
                    self.executor.execute(Action(type=ActionType.KEY_COMBINATION, combination="CTRL+B", timestamp=datetime.now()))
                
                # Casos especiales para "Impresión:" (salto de línea antes)
                if "Impresión" in part:
                    self.executor.execute(Action(type=ActionType.KEY_PRESS, key_code="ENTER", timestamp=datetime.now()))
                    
                # Escribir la etiqueta (usando CTRL+V para asegurar acentos OK)
                self.executor.execute(Action(type=ActionType.KEY_COMBINATION, combination="CTRL+V", clipboard_content=part, timestamp=datetime.now()))
                
                # APAGAR negrita inmediatamente después del título para que el contenido sea normal
                self.executor.execute(Action(type=ActionType.KEY_COMBINATION, combination="CTRL+B", timestamp=datetime.now()))
                current_bold = False

                # Salto de línea después de "Impresión:"
                if "Impresión" in part:
                    self.executor.execute(Action(type=ActionType.KEY_PRESS, key_code="ENTER", timestamp=datetime.now()))
            else:
                # Es contenido normal. Si por error estuviera en negrita, apagarla
                if current_bold:
                    self.executor.execute(Action(type=ActionType.KEY_COMBINATION, combination="CTRL+B", timestamp=datetime.now()))
                    current_bold = False
                
                # Pegar contenido
                self.executor.execute(Action(type=ActionType.KEY_COMBINATION, combination="CTRL+V", clipboard_content=part, timestamp=datetime.now()))
    
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
            "total_actions": 3,
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
                    selector={'automation_id': 'm_TextControl'},
                    position={'x': 493, 'y': 537},
                    timestamp=datetime.fromisoformat("2026-01-18T22:53:02.144296")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[1/4] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 1, "type": "click", "reason": str(e)})
                logger.error(f"[1/4] ❌ click: {e}")

            # Acción 2: CTRL+A (Seleccionar todo)
            try:
                action = Action(
                    type=ActionType.KEY_COMBINATION,
                    combination='CTRL+A',
                    timestamp=datetime.fromisoformat("2026-01-18T22:53:08.911226")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[2/4] ✅ ctrl+a")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 2, "type": "key_combination", "reason": str(e)})
                logger.error(f"[2/4] ❌ ctrl+a: {e}")

            # Acción 3: KEY
            try:
                action = Action(
                    type=ActionType.KEY_PRESS,
                    key_code="DELETE",
                    timestamp=datetime.fromisoformat("2026-01-18T22:53:09.062012")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[3/4] ✅ key")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 3, "type": "key", "reason": str(e)})
                logger.error(f"[3/4] ❌ key: {e}")








            # Acción 1: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'm_TextControl'},
                    position={'x': 589, 'y': 325},
                    timestamp=datetime.fromisoformat("2026-01-11T23:05:51.060515")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[1/6] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 1, "type": "click", "reason": str(e)})
                logger.error(f"[1/6] ❌ click: {e}")

            # Acción 2: PROCESAMIENTO DE DIAGNÓSTICO (Reemplaza acciones manuales 2-5)
            try:
                diag = self.fetch_diagnosis()
                if diag:
                    self.type_formatted(diag)
                    results["completed"] += 1
                    logger.info(f"[2/3] ✅ Diagnóstico procesado e ingresado")
                else:
                    logger.warning("No se obtuvo diagnóstico de la DB")
                    results["failed"] += 1
                    results["errors"].append({"action_idx": 2, "type": "db_process", "reason": "No diagnosis data"})
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 2, "type": "db_process", "reason": str(e)})
                logger.error(f"[2/3] ❌ db_process: {e}")

            # Acción 6: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'position': {'x': 433, 'y': 338}},
                    position={'x': 433, 'y': 338},
                    timestamp=datetime.fromisoformat("2026-01-11T23:06:00.058182")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[3/3] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 3, "type": "click", "reason": str(e)})
                logger.error(f"[3/3] ❌ click: {e}")

            
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
    
    automation = Test1Automation()
    results = automation.run()
    
    print("\n" + "="*50)
    print(f"Resultado: {results['status']}")
    print(f"Completadas: {results['completed']}/{results['total_actions']}")
    print(f"Fallidas: {results['failed']}")
    print("="*50)
    
    return 0 if results["status"] == "SUCCESS" else 1


if __name__ == "__main__":
    sys.exit(main())
