#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script autogenerado y optimizado: ingresapassvpn
Generado: 2026-10-22 11:28:53
Total de acciones: 14
"""

import sys
import time
import logging
import threading
import tkinter as tk
import pyautogui
pyautogui.FAILSAFE = False
from pathlib import Path
from datetime import datetime

# Agregar raíz del proyecto al path de ejecución
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pywinauto import Application, findwindows
from core.executor import ActionExecutor
from core.action import Action, ActionType
from utils.logging_setup import setup_logging
from utils.keyboard_utils import ensure_capslock_off

# Configuración de base de datos MySQL (opcional para tracking)
try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

logger = logging.getLogger(__name__)

class VisualFeedbackLocal:
    """Feedback visual de coordenadas (Círculo verde flotante)"""
    def highlight_click(self, x, y, color="#10b981", duration=0.5):
        try:
            t = threading.Thread(target=self._draw_circle, args=(x, y, color, duration), daemon=True)
            t.start()
        except: pass

    def _draw_circle(self, x, y, color, duration):
        try:
            root = tk.Tk()
            root.overrideredirect(True)
            root.attributes("-topmost", True)
            root.attributes("-alpha", 0.7)
            size = 60
            root.geometry(f"{size}x{size}+{int(x)-30}+{int(y)-30}")
            canvas = tk.Canvas(root, width=size, height=size, bg='white', highlightthickness=0)
            canvas.pack()
            try: root.wm_attributes("-transparentcolor", "white")
            except: pass
            canvas.create_oval(4, 4, size-4, size-4, outline=color, width=5)
            canvas.create_oval(28, 28, 32, 32, fill=color, outline=color)
            root.update()
            time.sleep(duration)
            root.destroy()
        except: pass

vf = VisualFeedbackLocal()


class IngresapassvpnAutomation:
    """Automatización de escritorio optimizada para ingresapassvpn"""
    
    def __init__(self):
        self.app = None
        self.executor = None
        self.main_window = None
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
    def db_update_status(self, status='En Proceso'):
        """Actualiza el estado de ejecución en la base de datos de telemetría (opcional)"""
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
            script_name = "ingresapassvpn"
            query = "UPDATE registro_acciones SET `update` = NOW(), ultimo_nodo = %s, estado = %s WHERE estado = 'En Proceso'"
            cursor.execute(query, (script_name, status))
            conn.commit()
            conn.close()
            logger.info(f"[DB] Telemetría actualizada: {script_name} ({status})")
        except Exception as e:
            logger.debug(f"[DB Bypass] {e}")

    def humanized_click(self, x, y, duration=0.5, is_double=False):
        """Desplaza suavemente el cursor, dibuja círculo de feedback y hace click físico"""
        logger.info(f"Movimiento de cursor a ({x}, {y})...")
        pyautogui.moveTo(x, y, duration=0.3, tween=pyautogui.easeInOutQuad)
        time.sleep(0.05)
        
        if vf:
            vf.highlight_click(x, y, color="#10b981", duration=0.6) # Verde esmeralda para coincidir con UX
            time.sleep(0.1)
            
        if is_double:
            pyautogui.doubleClick()
        else:
            pyautogui.mouseDown()
            time.sleep(0.15)
            pyautogui.mouseUp()
        time.sleep(0.1)

    def execute_click_action(self, action):
        """Resuelve dinámicamente un click usando esperas activas de UIA, validación OCR (Self-Healing) o coordenadas"""
        x, y = None, None
        
        # 1. INTENTAR RESOLVER POR UIA (SELECTOR)
        if action.selector:
            try:
                # Espera activa (Dynamic Wait) de 4.0 segundos para estabilidad
                element = self.executor.selector_helper.find_element(
                    action.selector,
                    timeout=4.0,
                    app_context=action.app_context
                )
                
                # Forzar foco en la ventana y el elemento
                try:
                    element.set_focus()
                    time.sleep(0.2)
                except:
                    pass
                
                rect = element.rectangle()
                x, y = rect.mid_point().x, rect.mid_point().y
                logger.info(f"Selector resuelto por UIA a ({x}, {y})")
            except Exception as e:
                logger.debug(f"Búsqueda por selector UIA fallida, intentando alternativos: {e}")
                
        # 2. AUTO-CORRECCIÓN VISUAL POR OCR (SELF-HEALING)
        if (x is None or y is None) and action.element_info and action.element_info.get("name"):
            search_text = action.element_info["name"]
            # Excluir nombres genéricos, vacíos, coordenadas o IDs para evitar falsos positivos
            if search_text and len(search_text) < 40 and not search_text.startswith("n_"):
                try:
                    logger.info(f"Self-Healing: Intentando localizar elemento visualmente con OCR: '{search_text}'...")
                    from ocr.actions import OCRActions
                    # OCR Engine cargará EasyOCR/Tesseract por debajo
                    ocr = OCRActions()
                    matches = ocr.capture_and_find(search_text, fuzzy=True, take_screenshot=True)
                    if matches:
                        match = matches[0]
                        x, y = match["center"]["x"], match["center"]["y"]
                        logger.info(f"✅ Self-Healing con éxito: Texto '{search_text}' localizado en ({x}, {y})")
                except Exception as ocr_e:
                    logger.warning(f"Self-Healing por OCR fallido: {ocr_e}")
                    
        # 3. FALLBACK FINAL POR COORDENADAS ORIGINALES
        if x is None or y is None:
            if action.position and "x" in action.position and "y" in action.position:
                x, y = action.position["x"], action.position["y"]
                logger.info(f"Usando coordenadas fijas de fallback de grabación: ({x}, {y})")
                if self.main_window:
                    try:
                        self.main_window.set_focus()
                        time.sleep(0.15)
                    except: pass
            else:
                raise Exception("No se pudo resolver el elemento por selector UIA, validación OCR ni coordenadas")
                
        self.humanized_click(x, y, duration=0.5, is_double=(action.type == ActionType.DOUBLE_CLICK))
    
    def setup(self) -> bool:
        """Conecta a la aplicación objetivo detectada de forma robusta"""
        logger.info("Inicializando conexión con la ventana de la aplicación...")
        
        try:
            target_title = ".*Desktop.*"
            connected = False
            
            # Reintentos de conexión con tiempos de espera activos
            for attempt in range(1, 4):
                try:
                    logger.debug(f"Intento {attempt} de conexión a '{target_title}'...")
                    titulos = findwindows.find_elements(title_re=target_title, backend='uia')
                    
                    if titulos:
                        logger.info(f"Ventana detectada: {titulos[0].name}")
                        self.app = Application(backend='uia').connect(handle=titulos[0].handle)
                        self.main_window = self.app.window(handle=titulos[0].handle)
                        connected = True
                        break
                    else:
                        # Conectar directo por title regex
                        self.app = Application(backend='uia').connect(title_re=target_title)
                        self.main_window = self.app.window(title_re=target_title)
                        connected = True
                        break
                except Exception as connect_e:
                    logger.debug(f"Intento {attempt} de conexión fallido: {connect_e}")
                    time.sleep(1.0)
            
            if connected and self.main_window:
                try:
                    self.main_window.set_focus()
                    time.sleep(0.3)
                except:
                    pass
            else:
                logger.warning("No se pudo conectar a una ventana específica. Conectando al Desktop raíz.")
                self.app = Application(backend='uia')
                self.main_window = None
                
            self.executor = ActionExecutor(self.app, {})
            logger.info("✅ Conexión establecida de forma exitosa")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error crítico en setup: {e}")
            self.app = Application(backend='uia')
            self.executor = ActionExecutor(self.app, {})
            return True
    
    def run(self) -> dict:
        if not self.setup():
            return {"status": "FAILED", "reason": "Setup failed"}
        
        # Verificar y desactivar Bloq Mayús si está activo
        try:
            ensure_capslock_off(logger.info)
        except Exception as cap_e:
            logger.warning(f"No se pudo verificar el estado de Bloq Mayús: {cap_e}")

        results = {
            "session_id": self.session_id,
            "status": "RUNNING",
            "total_actions": 14,
            "completed": 0,
            "failed": 0,
            "errors": [],
            "start_time": datetime.now().isoformat(),
        }
        
        logger.info(f"🚀 Iniciando ejecución de {results['total_actions']} acciones grabadas")
        self.db_update_status('En Proceso')
        
        try:
            # Acción 1: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'NotifyItemIcon'},
                    position={'x': 1679, 'y': 1058},
                    app_context={'title': 'Desktop', 'class_name': '#32769'},
                    element_info={'name': 'Desconectado', 'automation_id': 'NotifyItemIcon', 'class_name': 'SystemTray.NormalButton', 'control_type': 'Button'},
                    timestamp=datetime.fromisoformat("2026-10-22T11:27:17.749288")
                )
                self.execute_click_action(action)
                results["completed"] += 1
                logger.info(f"[1/14] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 1, "type": "click", "reason": str(e)})
                logger.error(f"[1/14] ❌ click: {e}")

            # Acción 2: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'name': 'Conectar', 'control_type': 'Button'},
                    position={'x': 1749, 'y': 1008},
                    app_context={'title': 'Desktop', 'class_name': '#32769'},
                    element_info={'name': 'Conectar', 'automation_id': '1160', 'class_name': 'Button', 'control_type': 'Button'},
                    timestamp=datetime.fromisoformat("2026-10-22T11:27:21.243473")
                )
                self.execute_click_action(action)
                results["completed"] += 1
                logger.info(f"[2/14] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 2, "type": "click", "reason": str(e)})
                logger.error(f"[2/14] ❌ click: {e}")

            # Acción 3: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'name': 'Password', 'control_type': 'Edit'},
                    position={'x': 1807, 'y': 860},
                    app_context={'title': 'Desktop', 'class_name': '#32769'},
                    element_info={'name': 'Password', 'automation_id': '1166', 'class_name': 'Edit', 'control_type': 'Edit'},
                    timestamp=datetime.fromisoformat("2026-10-22T11:27:24.726237")
                )
                self.execute_click_action(action)
                results["completed"] += 1
                logger.info(f"[3/14] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 3, "type": "click", "reason": str(e)})
                logger.error(f"[3/14] ❌ click: {e}")

            # Acción 4: TYPE_TEXT
            try:
                action = Action(
                    type=ActionType.TYPE_TEXT,
                    text='\x01',
                    selector={'name': 'Password', 'control_type': 'Edit'},
                    app_context={},
                    element_info={},
                    timestamp=datetime.fromisoformat("2026-10-22T11:27:27.133696")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[4/14] ✅ type_text")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 4, "type": "type_text", "reason": str(e)})
                logger.error(f"[4/14] ❌ type_text: {e}")

            # Acción 5: KEY
            try:
                action = Action(
                    type=ActionType.KEY_PRESS,
                    key_code="DELETE",
                    timestamp=datetime.fromisoformat("2026-10-22T11:27:27.134229")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[5/14] ✅ key")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 5, "type": "key", "reason": str(e)})
                logger.error(f"[5/14] ❌ key: {e}")

            # Acción 6: TYPE_TEXT
            try:
                action = Action(
                    type=ActionType.TYPE_TEXT,
                    text='Ricardo.Carcamo',
                    selector=None,
                    app_context={},
                    element_info={},
                    timestamp=datetime.fromisoformat("2026-10-22T11:27:32.705125")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[6/14] ✅ type_text")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 6, "type": "type_text", "reason": str(e)})
                logger.error(f"[6/14] ❌ type_text: {e}")

            # Acción 7: KEY
            try:
                action = Action(
                    type=ActionType.KEY_PRESS,
                    key_code="TAB",
                    timestamp=datetime.fromisoformat("2026-10-22T11:27:32.705428")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[7/14] ✅ key")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 7, "type": "key", "reason": str(e)})
                logger.error(f"[7/14] ❌ key: {e}")

            # Acción 8: TYPE_TEXT
            try:
                action = Action(
                    type=ActionType.TYPE_TEXT,
                    text='Min#',
                    selector=None,
                    app_context={},
                    element_info={},
                    timestamp=datetime.fromisoformat("2026-10-22T11:27:44.220452")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[8/14] ✅ type_text")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 8, "type": "type_text", "reason": str(e)})
                logger.error(f"[8/14] ❌ type_text: {e}")

            # Acción 9: KEY
            try:
                action = Action(
                    type=ActionType.KEY_PRESS,
                    key_code="ENTER",
                    timestamp=datetime.fromisoformat("2026-10-22T11:27:44.220859")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[9/14] ✅ key")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 9, "type": "key", "reason": str(e)})
                logger.error(f"[9/14] ❌ key: {e}")

            # Acción 10: TYPE_TEXT
            try:
                action = Action(
                    type=ActionType.TYPE_TEXT,
                    text='Mim#',
                    selector=None,
                    app_context={},
                    element_info={},
                    timestamp=datetime.fromisoformat("2026-10-22T11:27:56.713655")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[10/14] ✅ type_text")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 10, "type": "type_text", "reason": str(e)})
                logger.error(f"[10/14] ❌ type_text: {e}")

            # Acción 11: KEY
            try:
                action = Action(
                    type=ActionType.KEY_PRESS,
                    key_code="ENTER",
                    timestamp=datetime.fromisoformat("2026-10-22T11:27:56.714079")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[11/14] ✅ key")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 11, "type": "key", "reason": str(e)})
                logger.error(f"[11/14] ❌ key: {e}")

            # Acción 12: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'name': 'Enter Your Microsoft verification code', 'control_type': 'Edit'},
                    position={'x': 1749, 'y': 910},
                    app_context={'title': 'Desktop', 'class_name': '#32769'},
                    element_info={'name': 'Enter Your Microsoft verification code', 'automation_id': '1167', 'class_name': 'Edit', 'control_type': 'Edit'},
                    timestamp=datetime.fromisoformat("2026-10-22T11:28:04.186875")
                )
                self.execute_click_action(action)
                results["completed"] += 1
                logger.info(f"[12/14] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 12, "type": "click", "reason": str(e)})
                logger.error(f"[12/14] ❌ click: {e}")

            # Acción 13: KEY
            try:
                action = Action(
                    type=ActionType.KEY_PRESS,
                    key_code="ENTER",
                    timestamp=datetime.fromisoformat("2026-10-22T11:28:22.450185")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[13/14] ✅ key")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 13, "type": "key", "reason": str(e)})
                logger.error(f"[13/14] ❌ key: {e}")

            # Acción 14: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'automation_id': 'QApplication.DesktopFloatingControlWindow.QPushButton'},
                    position={'x': 1024, 'y': 428},
                    app_context={'title': 'Desktop', 'class_name': '#32769'},
                    element_info={'name': '⏹ Terminar', 'automation_id': 'QApplication.DesktopFloatingControlWindow.QPushButton', 'class_name': 'QPushButton', 'control_type': 'Button'},
                    timestamp=datetime.fromisoformat("2026-10-22T11:28:37.277042")
                )
                self.execute_click_action(action)
                results["completed"] += 1
                logger.info(f"[14/14] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 14, "type": "click", "reason": str(e)})
                logger.error(f"[14/14] ❌ click: {e}")

            results["status"] = "SUCCESS" if results["failed"] == 0 else "PARTIAL"
            
        except Exception as e:
            logger.error(f"❌ Error de ejecución crítico: {e}")
            results["status"] = "FAILED"
            results["errors"].append({"reason": str(e)})
            self.db_update_status('error')
        
        results["end_time"] = datetime.now().isoformat()
        logger.info(f"📊 Resumen de ejecución: {results['completed']} OK, {results['failed']} FAILED")
        
        if results["status"] == "SUCCESS":
            self.db_update_status('Finalizado')
            
        return results


def main():
    setup_logging()
    automation = IngresapassvpnAutomation()
    results = automation.run()
    
    print("\n" + "="*50)
    print(f"Resultado de Validación: {results['status']}")
    print(f"Pasos Completados: {results['completed']}/{results['total_actions']}")
    print(f"Pasos Fallidos: {results['failed']}")
    print("="*50)
    
    return 0 if results["status"] == "SUCCESS" else 1


if __name__ == "__main__":
    sys.exit(main())
