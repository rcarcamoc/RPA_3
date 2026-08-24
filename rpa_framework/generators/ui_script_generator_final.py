#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
generators/ui_script_generator_final.py

Genera scripts Python ejecutables robustos con detección dinámica del título de ventana,
esperas activas, auto-corrección visual mediante OCR (Self-Healing) y control de excepciones.
"""

import logging
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict

logger = logging.getLogger(__name__)


class UIScriptGeneratorFinal:
    """Genera scripts Python ejecutables dinámicos y robustos a partir de acciones grabadas."""
    
    def __init__(self, actions: List[Dict], module_name: str):
        self.actions = actions
        self.module_name = module_name.replace(" ", "_").lower()
        
    def generate(self) -> Path:
        from utils.paths import UI_RECORDINGS_DIR
        
        # Crear directorio de salida
        output_dir = UI_RECORDINGS_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generar el código Python
        script_code = self._generate_script_code()
        
        # Guardar archivo
        output_path = output_dir / f"{self.module_name}.py"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(script_code)
        
        logger.info(f"✅ Script robusto generado: {output_path}")
        return output_path
    
    def _generate_script_code(self) -> str:
        # Generar código de las acciones
        actions_code = self._generate_actions_code()
        
        # Preparar nombre de clase válido
        class_name = self.module_name.title().replace("_", "")
        if class_name and class_name[0].isdigit():
            class_name = f"Script{class_name}"
            
        # Detectar dinámicamente el título de la ventana activa más frecuente en las acciones
        titles = [a.get("app_context", {}).get("title") for a in self.actions if a.get("app_context", {}).get("title")]
        if titles:
            most_common_title = max(set(titles), key=titles.count)
            # Limpiar caracteres especiales de regex
            escaped_title = re.escape(most_common_title)
            # Acortar o flexibilizar para permitir nombres parciales
            parts = re.split(r'\s*[-|–—]\s*', most_common_title)
            if len(parts) > 1:
                app_name = parts[-1].strip()
                escaped_title = re.escape(app_name)
            
            target_title_re = f".*{escaped_title}.*"
            logger.info(f"Detección de app: Ventana objetivo configurada como '{target_title_re}' (original: '{most_common_title}')")
        else:
            target_title_re = ".*"
            logger.info("Detección de app: No se encontraron títulos de ventanas. Usando fallback genérico '.*'")

        script = f'''#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script autogenerado y optimizado: {self.module_name}
Generado: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Total de acciones: {len(self.actions)}
"""

import sys
import time
import logging
import threading
import tkinter as tk
import pyautogui
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
            root.geometry(f"{{size}}x{{size}}+{{int(x)-30}}+{{int(y)-30}}")
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


class {class_name}Automation:
    """Automatización de escritorio optimizada para {self.module_name}"""
    
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
            script_name = "{self.module_name}"
            query = "UPDATE registro_acciones SET `update` = NOW(), ultimo_nodo = %s, estado = %s WHERE estado = 'En Proceso'"
            cursor.execute(query, (script_name, status))
            conn.commit()
            conn.close()
            logger.info(f"[DB] Telemetría actualizada: {{script_name}} ({{status}})")
        except Exception as e:
            logger.debug(f"[DB Bypass] {{e}}")

    def humanized_click(self, x, y, duration=0.5, is_double=False):
        """Desplaza suavemente el cursor, dibuja círculo de feedback y hace click físico"""
        logger.info(f"Movimiento de cursor a ({{x}}, {{y}})...")
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
                logger.info(f"Selector resuelto por UIA a ({{x}}, {{y}})")
            except Exception as e:
                logger.debug(f"Búsqueda por selector UIA fallida, intentando alternativos: {{e}}")
                
        # 2. AUTO-CORRECCIÓN VISUAL POR OCR (SELF-HEALING)
        if (x is None or y is None) and action.element_info and action.element_info.get("name"):
            search_text = action.element_info["name"]
            # Excluir nombres genéricos, vacíos, coordenadas o IDs para evitar falsos positivos
            if search_text and len(search_text) < 40 and not search_text.startswith("n_"):
                try:
                    logger.info(f"Self-Healing: Intentando localizar elemento visualmente con OCR: '{{search_text}}'...")
                    from ocr.actions import OCRActions
                    # OCR Engine cargará EasyOCR/Tesseract por debajo
                    ocr = OCRActions()
                    matches = ocr.capture_and_find(search_text, fuzzy=True, take_screenshot=True)
                    if matches:
                        match = matches[0]
                        x, y = match["center"]["x"], match["center"]["y"]
                        logger.info(f"✅ Self-Healing con éxito: Texto '{{search_text}}' localizado en ({{x}}, {{y}})")
                except Exception as ocr_e:
                    logger.warning(f"Self-Healing por OCR fallido: {{ocr_e}}")
                    
        # 3. FALLBACK FINAL POR COORDENADAS ORIGINALES
        if x is None or y is None:
            if action.position and "x" in action.position and "y" in action.position:
                x, y = action.position["x"], action.position["y"]
                logger.info(f"Usando coordenadas fijas de fallback de grabación: ({{x}}, {{y}})")
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
            target_title = "{target_title_re}"
            connected = False
            
            # Reintentos de conexión con tiempos de espera activos
            for attempt in range(1, 4):
                try:
                    logger.debug(f"Intento {{attempt}} de conexión a '{{target_title}}'...")
                    titulos = findwindows.find_elements(title_re=target_title, backend='uia')
                    
                    if titulos:
                        logger.info(f"Ventana detectada: {{titulos[0].name}}")
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
                    logger.debug(f"Intento {{attempt}} de conexión fallido: {{connect_e}}")
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
                
            self.executor = ActionExecutor(self.app, {{}})
            logger.info("✅ Conexión establecida de forma exitosa")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error crítico en setup: {{e}}")
            self.app = Application(backend='uia')
            self.executor = ActionExecutor(self.app, {{}})
            return True
    
    def run(self) -> dict:
        if not self.setup():
            return {{"status": "FAILED", "reason": "Setup failed"}}
        
        # Verificar y desactivar Bloq Mayús si está activo
        try:
            ensure_capslock_off(logger.info)
        except Exception as cap_e:
            logger.warning(f"No se pudo verificar el estado de Bloq Mayús: {{cap_e}}")

        results = {{
            "session_id": self.session_id,
            "status": "RUNNING",
            "total_actions": {len(self.actions)},
            "completed": 0,
            "failed": 0,
            "errors": [],
            "start_time": datetime.now().isoformat(),
        }}
        
        logger.info(f"🚀 Iniciando ejecución de {{results['total_actions']}} acciones grabadas")
        self.db_update_status('En Proceso')
        
        try:
{actions_code}
            results["status"] = "SUCCESS" if results["failed"] == 0 else "PARTIAL"
            
        except Exception as e:
            logger.error(f"❌ Error de ejecución crítico: {{e}}")
            results["status"] = "FAILED"
            results["errors"].append({{"reason": str(e)}})
            self.db_update_status('error')
        
        results["end_time"] = datetime.now().isoformat()
        logger.info(f"📊 Resumen de ejecución: {{results['completed']}} OK, {{results['failed']}} FAILED")
        
        if results["status"] == "SUCCESS":
            self.db_update_status('Finalizado')
            
        return results


def main():
    setup_logging()
    automation = {class_name}Automation()
    results = automation.run()
    
    print("\\n" + "="*50)
    print(f"Resultado de Validación: {{results['status']}}")
    print(f"Pasos Completados: {{results['completed']}}/{{results['total_actions']}}")
    print(f"Pasos Fallidos: {{results['failed']}}")
    print("="*50)
    
    return 0 if results["status"] == "SUCCESS" else 1


if __name__ == "__main__":
    sys.exit(main())
'''
        return script

    def _generate_actions_code(self) -> str:
        lines = []
        for idx, action_data in enumerate(self.actions, 1):
            action_type = action_data.get("type", "unknown")
            lines.append(f"            # Acción {idx}: {action_type.upper()}")
            lines.append(f"            try:")
            
            if action_type == "click":
                lines.append(self._generate_click_action(action_data, idx))
            elif action_type == "type_text":
                lines.append(self._generate_type_action(action_data, idx))
            elif action_type == "key":
                lines.append(self._generate_key_action(action_data, idx))
            elif action_type == "key_combination":
                lines.append(self._generate_key_combination_action(action_data, idx))
            else:
                lines.append(f'                logger.warning(f"Acción desconocida: {action_type}")')
            
            lines.append(f'                results["completed"] += 1')
            lines.append(f'                logger.info(f"[{idx}/{len(self.actions)}] ✅ {action_type}")')
            lines.append(f'            except Exception as e:')
            lines.append(f'                results["failed"] += 1')
            lines.append(f'                results["errors"].append({{"action_idx": {idx}, "type": "{action_type}", "reason": str(e)}})')
            lines.append(f'                logger.error(f"[{idx}/{len(self.actions)}] ❌ {action_type}: {{e}}")')
            lines.append(f'')
        return "\n".join(lines)

    def _generate_click_action(self, action_data: Dict, idx: int) -> str:
        selector = action_data.get("selector", {})
        position = action_data.get("position", {})
        app_context = action_data.get("app_context", {})
        element_info = action_data.get("element_info", {})
        
        code = f'''                action = Action(
                    type=ActionType.CLICK,
                    selector={repr(selector)},
                    position={repr(position)},
                    app_context={repr(app_context)},
                    element_info={repr(element_info)},
                    timestamp=datetime.fromisoformat("{action_data.get('timestamp', datetime.now().isoformat())}")
                )
                self.execute_click_action(action)'''
        return code

    def _generate_type_action(self, action_data: Dict, idx: int) -> str:
        text = action_data.get("text", "")
        selector = action_data.get("selector", {})
        app_context = action_data.get("app_context", {})
        element_info = action_data.get("element_info", {})
        
        code = f'''                action = Action(
                    type=ActionType.TYPE_TEXT,
                    text={repr(text)},
                    selector={repr(selector)},
                    app_context={repr(app_context)},
                    element_info={repr(element_info)},
                    timestamp=datetime.fromisoformat("{action_data.get('timestamp', datetime.now().isoformat())}")
                )
                self.executor.execute(action)'''
        return code

    def _generate_key_action(self, action_data: Dict, idx: int) -> str:
        key_code = action_data.get("key_code", "")
        code = f'''                action = Action(
                    type=ActionType.KEY_PRESS,
                    key_code="{key_code}",
                    timestamp=datetime.fromisoformat("{action_data.get('timestamp', datetime.now().isoformat())}")
                )
                self.executor.execute(action)'''
        return code

    def _generate_key_combination_action(self, action_data: Dict, idx: int) -> str:
        combination = action_data.get("combination", "")
        clipboard_content = action_data.get("clipboard_content")
        code = f'''                action = Action(
                    type=ActionType.KEY_COMBINATION,
                    combination="{combination}",
                    clipboard_content={repr(clipboard_content)},
                    timestamp=datetime.fromisoformat("{action_data.get('timestamp', datetime.now().isoformat())}")
                )
                self.executor.execute(action)'''
        return code
