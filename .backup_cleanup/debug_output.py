# HOOK BLOCK MOCK
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


class PatologiaCriticaConCierreOkAutomation:
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

    def db_get_detected_patology(self):
        """Obtiene la patología detectada de la BD para el registro en proceso."""
        if not HAS_MYSQL:
            return None
        try:
            conn = mysql.connector.connect(
                host='localhost',
                user='root',
                password='',
                database='ris'
            )
            cursor = conn.cursor()
            query = "SELECT patologia_critica_detectada FROM registro_acciones WHERE estado = 'En Proceso' LIMIT 1"
            cursor.execute(query)
            result = cursor.fetchone()
            conn.close()
            if result and result[0]:
                return result[0]
            return None
        except Exception as e:
            logger.warning(f"[DB Get Error] {e}")
            return None


    def stop_with_error(self, message):
        """Gestiona el error, actualiza la BD y detiene la ejecución de forma controlada."""
        logger.error(f"❌ ERROR: {message}")
        
        # Actualización de Estado (SQL)
        if HAS_MYSQL:
            try:
                conn = mysql.connector.connect(
                    host='localhost',
                    user='root',
                    password='',
                    database='ris'
                )
                cursor = conn.cursor()
                # Query solicitado: UPDATE ris.registro_acciones SET estado = 'Error', observacion = ...
                query = "UPDATE ris.registro_acciones SET estado = 'Error', observacion = %s WHERE estado = 'En Proceso'"
                cursor.execute(query, (message[:254],))
                conn.commit()
                conn.close()
                logger.info(f"[DB] Estado de error actualizado: {message}")
            except Exception as db_e:
                logger.warning(f"[DB Error during stop_with_error] {db_e}")

        # Cerrar cualquier recurso abierto (navegador, base de datos).
        # (En este script los recursos se abren y cierran puntualmente)
        
        # Código de Salida (Python)
        import sys
        print(f"ERROR: {message}") # Esto aparecerá en el log de la UI
        sys.exit(1) # Código 1 indica fallo y detiene el workflow

    
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
            _rpa_step_hook(1)
            # Acción 1: Cambiar a la ventana de Carestream RIS
            try:
                time.sleep(1)
                logger.info("Buscando y enfocando la ventana de Carestream RIS...")
                
                # Estrategia de conexión robusta con reintentos
                connected = False
                for attempt in range(1, 4):
                    try:
                        logger.debug(f"Intento {attempt} de conexión a Carestream RIS...")
                        # 1. Buscar por título para obtener un handle estable
                        titulos = findwindows.find_elements(title_re=".*Carestream RIS.*", backend='uia')
                        
                        if titulos:
                            logger.info(f"Ventana encontrada por título: {titulos[0].name}")
                            self.app = Application(backend='uia').connect(handle=titulos[0].handle)
                        else:
                            # 2. Fallback a conectar por process path o title_re directo
                            try:
                                self.app = Application(backend='uia').connect(path="Carestream RIS.exe")
                            except:
                                self.app = Application(backend='uia').connect(title_re=".*Carestream RIS.*")
                        
                        # 3. Validar existencia y dar foco (específico en vez de top_window)
                        main_window = self.app.window(title_re=".*Carestream RIS.*")
                        if main_window.exists(timeout=5):
                            main_window.set_focus()
                            # A veces requiere un segundo intento o esperar un poco
                            time.sleep(0.5)
                            main_window.set_focus()
                            connected = True
                            break
                        else:
                            logger.warning(f"Intento {attempt}: La ventana no parece estar lista")
                            
                    except Exception as connect_e:
                        logger.warning(f"Intento {attempt} fallido: {connect_e}")
                        time.sleep(2) # Esperar antes de reintentar
                
                if not connected:
                    # Fallback final: intentar top_window pero con captura de error
                    try:
                        logger.info("Intentando fallback final con top_window...")
                        window = self.app.top_window()
                        window.set_focus()
                    except Exception as final_e:
                        raise Exception(f"Fallo total al conectar con Carestream RIS: {final_e}")
                
                # Actualizar el executor con el nuevo contexto de aplicación
                self.executor = ActionExecutor(self.app, {})
                
                results["completed"] += 1
                logger.info("[1/16] ✅ Ventana de Carestream RIS enfocada")
            except Exception as e:
                self.stop_with_error(f"No se pudo encontrar o activar la ventana de Carestream RIS: {e}")

            _rpa_step_hook(2)
 # Acción 2: CLICK en resultado critico
            # Mover antes de hacer clic
            time.sleep(1)
            self.executor.execute(Action(
                type=ActionType.MOVE,
                position={'x': 692, 'y': 84},
                timestamp=datetime.now()
            ))
            action = Action(
                type=ActionType.DOUBLE_CLICK,
                selector={'automation_id': 'tabControl1'},
                position={'x': 692, 'y': 84},
                timestamp=datetime.fromisoformat("2026-01-14T15:10:39.561316")
            )
            self.executor.execute(action)
            results["completed"] += 1
            logger.info(f"[2/16] ✅ click")


            _rpa_step_hook(3)
         # Acción 3: CLICK en combobox resultado critico
            # Mover antes de hacer clic
            time.sleep(1)
            self.executor.execute(Action(
                type=ActionType.MOVE,
                position={'x': 295, 'y': 123},
                timestamp=datetime.now()
            ))
            action = Action(
                type=ActionType.CLICK,
                selector={'automation_id': 'cbxClResultadocritico1'},
                position={'x': 295, 'y': 123},
                timestamp=datetime.fromisoformat("2026-01-14T15:10:42.178933")
            )
            self.executor.execute(action)
            results["completed"] += 1
            logger.info(f"[3/16] ✅ click")

            _rpa_step_hook(4)
                        # Acción 4: CLICK en si resultado critico
            # Mover antes de hacer clic
            time.sleep(1)
            self.executor.execute(Action(
                type=ActionType.MOVE,
                
                position={'x': 201, 'y': 182},
                timestamp=datetime.now()
            ))
            action = Action(
                type=ActionType.CLICK,
                selector={'name': 'Sí', 'control_type': 'ListItem'},
                position={'x': 201, 'y': 182},
                timestamp=datetime.fromisoformat("2026-01-14T15:10:43.561504")
            )
            self.executor.execute(action)
            results["completed"] += 1
            logger.info(f"[4/16] ✅ click")


            _rpa_step_hook(5)
   # Acción 5: CLICK (ComboBox)
            # Mover antes de hacer clic para asegurar foco
            time.sleep(1)
            self.executor.execute(Action(
                type=ActionType.MOVE,
                position={'x': 612, 'y': 185},
                timestamp=datetime.now()
            ))
            action = Action(
                type=ActionType.CLICK,
                selector={'automation_id': 'cbxClCodigodiagnostico1'},
                position={'x': 612, 'y': 185},
                timestamp=datetime.fromisoformat("2026-01-14T15:10:44.998266")
            )
            self.executor.execute(action)
            results["completed"] += 1
            logger.info(f"[5/16] ✅ click (ComboBox)")


            _rpa_step_hook(6)
            # Acción 6: TYPE_TEXT
            time.sleep(1)
            
            # Obtener el texto dinámico de la BD
            patologia_detectada = self.db_get_detected_patology()
            text_to_type = 'f' # Default fallback
            if patologia_detectada:
                text_to_type = patologia_detectada[0].lower()
                logger.info(f"Usando primera letra de '{patologia_detectada}': '{text_to_type}'")
            else:
                logger.warning("No se pudo obtener patologia_critica_detectada de la BD, usando fallback 'f'")

            action = Action(
                type=ActionType.TYPE_TEXT,
                text=text_to_type,
                selector={'automation_id': 'cbxClCodigodiagnostico1'},
                timestamp=datetime.fromisoformat("2026-01-14T15:10:49.226758")
            )
            self.executor.execute(action)
            results["completed"] += 1
            logger.info(f"[6/16] ✅ type_text ('{text_to_type}')")






            results["status"] = "SUCCESS"
            
        except Exception as e:
            self.stop_with_error(str(e))

        
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
    
    automation = PatologiaCriticaConCierreOkAutomation()
    results = automation.run()
    
    print("\n" + "="*50)
    print(f"Resultado: {results['status']}")
    print(f"Completadas: {results['completed']}/{results['total_actions']}")
    print(f"Fallidas: {results['failed']}")
    print("="*50)
    
    return 0 if results["status"] == "SUCCESS" else 1


if __name__ == "__main__":
    sys.exit(main())
