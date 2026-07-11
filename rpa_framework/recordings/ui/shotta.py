#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script autogenerado: shotta
Generado: 2026-07-07 18:47:19
Total de acciones: 3
"""

import sys
import time
import logging
import threading
import tkinter as tk
import pyautogui
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

class VisualFeedbackLocal:
    """Feedback visual integrado para ser independiente del framework."""
    def highlight_click(self, x, y, color="#FF0000", duration=0.5):
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


class ShottaAutomation:
    """Automatización generada: shotta"""
    
    def __init__(self):
        self.app = None
        self.executor = None
        self.main_window = None
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
            script_name = "shotta"
            query = "UPDATE registro_acciones SET `update` = NOW(), ultimo_nodo = %s, estado = %s WHERE estado = 'En Proceso'"
            cursor.execute(query, (script_name, status))
            conn.commit()
            conn.close()
            logger.info(f"[DB] Tracking actualizado: {script_name} ({status})")
        except Exception as e:
            logger.warning(f"[DB Error] {e}")

    def humanized_click(self, x, y, duration=0.5, is_double=False, element=None):
        """Mueve, resalta con círculo rojo y hace clic sostenido."""
        logger.info(f"Posicionando mouse en ({x}, {y}) para clic {'doble' if is_double else 'sostenido'}...")
        pyautogui.moveTo(x, y, duration=0.4, tween=pyautogui.easeInOutQuad)
        time.sleep(0.1)
        
        if vf:
            vf.highlight_click(x, y, color="#FF0000", duration=0.8) # Círculo ROJO
            time.sleep(0.2)
            
        if element:
            try:
                logger.info("Ejecutando clic nativo sobre el control usando pywinauto...")
                if is_double:
                    element.double_click_input()
                elif duration > 0:
                    element.press_mouse_input()
                    time.sleep(duration)
                    element.release_mouse_input()
                else:
                    element.click_input()
                time.sleep(0.2)
                return
            except Exception as e:
                logger.warning(f"Fallo al hacer clic nativo en el elemento ({e}), usando fallback de coordenadas...")

        # Fallback a pywinauto.mouse (más robusto que pyautogui en Windows)
        try:
            from pywinauto import mouse
            if is_double:
                mouse.double_click(coords=(x, y))
            else:
                mouse.press(coords=(x, y))
                time.sleep(duration)
                mouse.release(coords=(x, y))
            logger.info("Clic ejecutado usando pywinauto.mouse")
        except Exception as e:
            logger.warning(f"Fallo en clic de pywinauto.mouse ({e}), usando fallback de pyautogui...")
            if is_double:
                pyautogui.doubleClick(x, y)
            else:
                pyautogui.mouseDown(x, y)
                time.sleep(duration)
                pyautogui.mouseUp(x, y)
        time.sleep(0.2)

    def execute_click_action(self, action):
        """Ejecuta un clic resolviendo primero las coordenadas si es un selector."""
        x, y = None, None
        element = None
        
        if action.selector:
            try:
                # Si no tiene app_context, intentamos usar el título de la ventana principal para guiar el selector
                app_ctx = action.app_context
                if not app_ctx and self.main_window:
                    try:
                        # Extraer el título real de la ventana enfocada
                        win_title = self.main_window.texts()[0]
                        app_ctx = {"title": win_title}
                    except:
                        app_ctx = {"title_re": ".*(Carestream RIS|Workflow Information Management|Carestream RIS V11).*"}
                
                element = self.executor.selector_helper.find_element(
                    action.selector,
                    timeout=self.executor.config.get("element_timeout", 2.0),
                    app_context=app_ctx
                )
                
                # Asegurar foco antes del clic
                try:
                    logger.debug("Forzando foco en el elemento...")
                    element.set_focus()
                    time.sleep(0.3)
                except Exception as e_focus:
                    logger.debug(f"No se pudo dar foco previo: {e_focus}")
                
                rect = element.rectangle()
                x, y = rect.mid_point().x, rect.mid_point().y
            except Exception as e:
                logger.warning(f"No se pudo resolver el selector, usando position de fallback: {e}")
                
        if x is None or y is None:
            if action.position and "x" in action.position and "y" in action.position:
                x, y = action.position["x"], action.position["y"]
                # Si usamos coordenadas, intentamos dar foco a la ventana principal al menos
                if self.main_window:
                    try:
                        self.main_window.set_focus()
                        time.sleep(0.2)
                    except: pass
            else:
                raise Exception("No hay selector válido ni coordinates para el clic")
                
        self.humanized_click(x, y, duration=0.5, is_double=(action.type == ActionType.DOUBLE_CLICK), element=element)
    
    def setup(self) -> bool:
        """Conecta a la aplicación objetivo de forma robusta."""
        logger.info("Configurando conexión a la aplicación...")
        
        try:
            # Estrategia de conexión robusta con reintentos para Carestream RIS
            target_title = ".*(Carestream RIS|Workflow Information Management|Carestream RIS V11).*"
            connected = False
            
            for attempt in range(1, 4):
                try:
                    logger.debug(f"Intento {attempt} de conexión a {target_title}...")
                    # 1. Buscar por título para obtener un handle estable
                    titulos = findwindows.find_elements(title_re=target_title, backend='uia')
                    
                    if titulos:
                        logger.info(f"Ventana encontrada por título: {titulos[0].name}")
                        self.app = Application(backend='uia').connect(handle=titulos[0].handle)
                    else:
                        # 2. Fallback a conectar por process path o title_re directo
                        try:
                            self.app = Application(backend='uia').connect(path="Carestream RIS.exe")
                        except:
                            self.app = Application(backend='uia').connect(title_re=target_title)
                    
                    # 3. Validar existencia y dar foco
                    self.main_window = self.app.window(title_re=target_title)
                    if self.main_window.exists(timeout=5):
                        self.main_window.set_focus()
                        time.sleep(0.5)
                        self.main_window.set_focus() # Segundo foco para asegurar
                        connected = True
                        break
                    else:
                        logger.warning(f"Intento {attempt}: La ventana no parece estar lista")
                except Exception as connect_e:
                    logger.warning(f"Intento {attempt} fallido: {connect_e}")
                    time.sleep(1)
            
            if not connected:
                # Fallback final a Desktop
                logger.warning("No se pudo conectar a la ventana específica, usando Desktop como root")
                self.app = Application(backend='uia')
                self.main_window = None
            
            self.executor = ActionExecutor(self.app, {})
            logger.info("✅ Conexión establecida")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error en setup: {e}")
            return False
    
    def run(self) -> dict:
        """Ejecuta todas las acciones grabadas."""
        results = {
            "session_id": self.session_id,
            "status": "SKIPPED",
            "total_actions": 3,
            "completed": 0,
            "failed": 0,
            "errors": [],
            "start_time": datetime.now().isoformat(),
        }
        
        logger.info("Buscando 'shotta.png' o 'shotta zoom.png' en pantalla...")
        
        root_dir = Path(__file__).parent.parent.parent
        image_paths = [
            str(root_dir / "utils" / "shotta.png"),
            str(root_dir / "utils" / "shotta zoom.png")
        ]
        
        found = False
        for img_path in image_paths:
            if not Path(img_path).exists():
                logger.warning(f"Imagen de referencia no encontrada: {img_path}")
                continue
            try:
                # 80% de similitud para tolerar pequeñas variaciones
                location = pyautogui.locateOnScreen(img_path, confidence=0.8)
                if location is not None:
                    logger.info(f"Coincidencia encontrada con {img_path} en {location}")
                    found = True
                    break
            except Exception as e:
                logger.debug(f"Error o no encontrada la imagen {img_path}: {e}")
                
        if not found:
            logger.info("No se detectó similitud con las imágenes requeridas. No se realiza ninguna acción.")
            results["end_time"] = datetime.now().isoformat()
            return results

        # Si se encuentra, procede con el resto (setup y acciones)
        if not self.setup():
            results["status"] = "FAILED"
            results["errors"].append({"reason": "Setup failed"})
            results["end_time"] = datetime.now().isoformat()
            return results
            
        results["status"] = "RUNNING"
        
        logger.info(f"🚀 Iniciando ejecución: {results['total_actions']} acciones")
        
        # DB Tracking: Start
        self.db_update_status('En Proceso')
        
        try:
            # Acción 1: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'name': 'Aceptar', 'control_type': 'Button'},
                    position={'x': 969, 'y': 576},
                    timestamp=datetime.fromisoformat("2026-07-07T18:47:06.680093")
                )
                self.execute_click_action(action)
                results["completed"] += 1
                logger.info(f"[1/3] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 1, "type": "click", "reason": str(e)})
                logger.error(f"[1/3] ❌ click: {e}")

            # Acción 2: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'name': 'Escritorio 1', 'control_type': 'Pane'},
                    position={'x': 926, 'y': 962},
                    timestamp=datetime.fromisoformat("2026-07-07T18:47:11.140635")
                )
                self.execute_click_action(action)
                results["completed"] += 1
                logger.info(f"[2/3] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 2, "type": "click", "reason": str(e)})
                logger.error(f"[2/3] ❌ click: {e}")

            # Acción 3: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'position': {'x': 503, 'y': 413}},
                    position={'x': 503, 'y': 413},
                    timestamp=datetime.fromisoformat("2026-07-07T18:47:14.995354")
                )
                self.execute_click_action(action)
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
    
    automation = ShottaAutomation()
    results = automation.run()
    
    print("\n" + "="*50)
    print(f"Resultado: {results['status']}")
    print(f"Completadas: {results['completed']}/{results['total_actions']}")
    print(f"Fallidas: {results['failed']}")
    print("="*50)
    
    return 0 if results["status"] in ["SUCCESS", "SKIPPED"] else 1


if __name__ == "__main__":
    sys.exit(main())
