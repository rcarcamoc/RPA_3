#!/usr/bin/env python
# -*- coding: utf-8 -*-

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

# Feedback visual integrado
class VisualFeedbackLocal:
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

logger = logging.getLogger(__name__)

class CriticaAutomation:
    """Automatización simplificada: critica"""
    
    def __init__(self):
        self.app = None
        self.executor = None
        self.main_window = None

    def humanized_click(self, x, y, duration=0.6, is_double=False):
        """Mueve, resalta con círculo rojo y hace clic sostenido."""
        logger.info(f"Posicionando mouse en ({x}, {y}) para clic {'doble' if is_double else 'sostenido'}...")
        pyautogui.moveTo(x, y, duration=0.4, tween=pyautogui.easeInOutQuad)
        time.sleep(0.1)
        
        if vf:
            vf.highlight_click(x, y, color="#FF0000", duration=0.8)
            time.sleep(0.2)
            
        if is_double:
            pyautogui.doubleClick()
        else:
            pyautogui.mouseDown()
            time.sleep(duration)
            pyautogui.mouseUp()
        time.sleep(0.2)
        
    def setup(self) -> bool:
        """Conecta a la aplicación de forma robusta."""
        try:
            # Título constante identificado por el usuario (soporta Carestream y Philips)
            target_title = ".*(Carestream RIS|Workflow Information Management).*"
            try:
                logger.info(f"Conectando a {target_title}...")
                self.app = Application(backend='uia').connect(title_re=target_title, timeout=5)
                self.main_window = self.app.window(title_re=target_title)
            except:
                try:
                    # Intento con el nombre de proceso original
                    logger.info("Intentando conectar por 'Carestream RIS.exe'...")
                    self.app = Application(backend='uia').connect(path="Carestream RIS.exe")
                    self.main_window = self.app.top_window()
                except:
                    try:
                        # Intento con el nuevo nombre de proceso (Vue RIS.exe)
                        logger.info("Intentando conectar por 'Vue RIS.exe'...")
                        self.app = Application(backend='uia').connect(path="Vue RIS.exe")
                        self.main_window = self.app.top_window()
                    except:
                        logger.warning("No se pudo conectar, usando Desktop como root")
                        self.app = Application(backend='uia')
            
            self.executor = ActionExecutor(self.app, {})
            return True
        except Exception as e:
            logger.error(f"Error en setup: {e}")
            return False

    def _robust_execute(self, action: Action):
        """Asegura el foco del elemento antes de ejecutar la acción."""
        if action.selector and action.type in [ActionType.CLICK, ActionType.DOUBLE_CLICK]:
            try:
                element = self.executor.selector_helper.find_element(
                    action.selector, 
                    timeout=3
                )
                logger.debug(f"Forzando foco en elemento: {action.selector}")
                element.set_focus()
                time.sleep(0.3)
            except Exception as e:
                logger.debug(f"No se pudo dar foco previo: {e}")
        
        return self.executor.execute(action)

    def run(self):
        """Ejecuta los movimientos automatizados de forma robusta."""
        if not self.setup():
            return
            
        results = {"completed": 0}

        # Acción 2: DOUBLE_CLICK en resultado critico (tabControl1)
        # Mover y esperar un instante para asegurar que el control está listo bajo el mouse
        self.executor.execute(Action(
            type=ActionType.MOVE,
            position={'x': 744, 'y': 84},
            timestamp=datetime.now()
        ))
        time.sleep(0.1)
        
        # Doble clic robusto. Si falla por selector, el nuevo fallback hará clic-pausa-clic.
        self._robust_execute(Action(
            type=ActionType.DOUBLE_CLICK,
            selector={'automation_id': 'tabControl1'},
            position={'x': 744, 'y': 84},
            timestamp=datetime.now()
        ))
        time.sleep(1)

        # Acción 3: CLICK en combobox resultado critico (Alternativa 1 - Nativo)
        time.sleep(1)
        try:
            # Buscar elemento de forma precisa
            element = self.main_window.child_window(auto_id='cbxClResultadocritico1', control_type="ComboBox")
            rect = element.rectangle()
            cx, cy = rect.mid_point().x, rect.mid_point().y
            
            # Clic humanizado (incluye movimiento, círculo rojo y sostenido)
            self.humanized_click(cx, cy)
            
            results["completed"] += 1
            logger.info("[3/16] ✅ clic humanizado (Alt 1) exitoso")
        except Exception as e_click:
            logger.error(f"Error en clic nativo (Acción 3): {e_click}")
            raise e_click

        # Acción 4: CLICK en si resultado critico (Robusto)
        # Aumentamos a 2 segundos para dar tiempo a que el combo despliegue la lista
        time.sleep(2)
        try:
            logger.info("Buscando elemento 'Sí'...")
            element_si = self.main_window.child_window(name='Sí', control_type='ListItem')
            
            if element_si.exists(timeout=3):
                rect = element_si.rectangle()
                self.humanized_click(rect.mid_point().x, rect.mid_point().y)
            else:
                raise Exception("Elemento 'Sí' no encontrado")
            
            # Pausa tras el clic para que se vea la selección
            time.sleep(0.5)
            results["completed"] += 1
            logger.info("[4/16] ✅ clic humanizado en 'Sí' exitoso")
        except Exception as e_si:
            logger.info("Esperando un poco más para el fallback de 'Sí'...")
            time.sleep(1)
            logger.error(f"Error en clic 'Sí': {e_si}")
            # Fallback a coordenadas
            logger.warning("Fallo en selector de 'Sí', intentando fallback por coordenadas...")
            try:
                self.humanized_click(201, 182)
                results["completed"] += 1
                logger.info("[4/16] ✅ clic humanizado (fallback) exitoso")
            except Exception as e_coord:
                logger.error(f"Fallo total en Acción 4: {e_coord}")
                raise e_coord

        # Acción 5: CLICK (ComboBox diagnóstico) - Robusto
        time.sleep(1)
        try:
            auto_id_diag = 'cbxClCodigodiagnostico1'
            logger.info(f"Buscando ComboBox de diagnóstico ({auto_id_diag})...")
            element_diag = self.main_window.child_window(auto_id=auto_id_diag, control_type="ComboBox")
            rect = element_diag.rectangle()
            self.humanized_click(rect.mid_point().x, rect.mid_point().y)
            
            results["completed"] += 1
            logger.info("[5/16] ✅ clic humanizado en ComboBox diagnóstico exitoso")
        except Exception as e_diag:
            logger.error(f"Error en clic Acción 5: {e_diag}")
            # Fallback a coordenadas
            logger.warning("Fallo en selector de Acción 5, intentando fallback por coordenadas...")
            try:
                self.humanized_click(612, 185)
                results["completed"] += 1
                logger.info("[5/16] ✅ clic humanizado (fallback) en Acción 5 exitoso")
            except Exception as e_coord5:
                logger.error(f"Fallo total en Acción 5: {e_coord5}")
                raise e_coord5






if __name__ == "__main__":
    setup_logging()
    CriticaAutomation().run()
