#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
generators/ui_script_generator.py

Genera scripts Python ejecutables autosuficientes a partir de acciones grabadas.
Sin dependencia de JSON intermedio.
"""

import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict

logger = logging.getLogger(__name__)


class UIScriptGenerator:
    """Genera scripts Python autosuficientes para reproducir acciones UI."""
    
    def __init__(self, actions: List[Dict], module_name: str):
        """
        Args:
            actions: Lista de acciones grabadas
            module_name: Nombre del módulo/script a generar
        """
        self.actions = actions
        self.module_name = module_name.replace(" ", "_").lower()
        
    def generate(self) -> Path:
        """Genera el script Python ejecutable."""
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
        
        logger.info(f"✅ Script generado: {output_path}")
        return output_path
    
    def _generate_script_code(self) -> str:
        """Genera el código completo del script."""
        
        # Generar código de las acciones
        actions_code = self._generate_actions_code()
        
        # Preparar nombre de clase válido
        class_name = self.module_name.title().replace("_", "")
        if class_name and class_name[0].isdigit():
            class_name = f"Script{class_name}"
            
        # Template del script
        script = f'''#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script autogenerado: {self.module_name}
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
    """Automatización generada: {self.module_name}"""
    
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
            script_name = "{self.module_name}"
            query = "UPDATE registro_acciones SET `update` = NOW(), ultimo_nodo = %s, estado = %s WHERE estado = 'En Proceso'"
            cursor.execute(query, (script_name, status))
            conn.commit()
            conn.close()
            logger.info(f"[DB] Tracking actualizado: {{script_name}} ({{status}})")
        except Exception as e:
            logger.warning(f"[DB Error] {{e}}")

    def humanized_click(self, x, y, duration=0.6, is_double=False):
        """Mueve, resalta con círculo rojo y hace clic sostenido."""
        logger.info(f"Posicionando mouse en ({{x}}, {{y}}) para clic {{'doble' if is_double else 'sostenido'}}...")
        pyautogui.moveTo(x, y, duration=0.4, tween=pyautogui.easeInOutQuad)
        time.sleep(0.1)
        
        if vf:
            vf.highlight_click(x, y, color="#FF0000", duration=0.8) # Círculo ROJO
            time.sleep(0.2)
            
        if is_double:
            pyautogui.doubleClick()
        else:
            pyautogui.mouseDown()
            time.sleep(duration)
            pyautogui.mouseUp()
        time.sleep(0.2)

    def execute_click_action(self, action):
        """Ejecuta un clic resolviendo primero las coordenadas si es un selector."""
        x, y = None, None
        
        if action.selector:
            try:
                element = self.executor.selector_helper.find_element(
                    action.selector,
                    timeout=self.executor.config.get("element_timeout", 2.0),
                    app_context=action.app_context
                )
                
                # Asegurar foco antes del clic
                try:
                    logger.debug("Forzando foco en el elemento...")
                    element.set_focus()
                    time.sleep(0.3)
                except Exception as e_focus:
                    logger.debug(f"No se pudo dar foco previo: {{e_focus}}")
                
                rect = element.rectangle()
                x, y = rect.mid_point().x, rect.mid_point().y
            except Exception as e:
                logger.warning(f"No se pudo resolver el selector, usando position de fallback: {{e}}")
                
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
                
        self.humanized_click(x, y, duration=0.6, is_double=(action.type == ActionType.DOUBLE_CLICK))
    
    def setup(self) -> bool:
        """Conecta a la aplicación objetivo de forma robusta."""
        logger.info("Configurando conexión a la aplicación...")
        
        try:
            # Estrategia de conexión robusta con reintentos para Carestream RIS
            target_title = ".*(Carestream RIS|Workflow Information Management|Carestream RIS V11).*"
            connected = False
            
            for attempt in range(1, 4):
                try:
                    logger.debug(f"Intento {{attempt}} de conexión a {{target_title}}...")
                    # 1. Buscar por título para obtener un handle estable
                    titulos = findwindows.find_elements(title_re=target_title, backend='uia')
                    
                    if titulos:
                        logger.info(f"Ventana encontrada por título: {{titulos[0].name}}")
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
                        logger.warning(f"Intento {{attempt}}: La ventana no parece estar lista")
                except Exception as connect_e:
                    logger.warning(f"Intento {{attempt}} fallido: {{connect_e}}")
                    time.sleep(1)
            
            if not connected:
                # Fallback final a Desktop
                logger.warning("No se pudo conectar a la ventana específica, usando Desktop como root")
                self.app = Application(backend='uia')
                self.main_window = None
            
            self.executor = ActionExecutor(self.app, {{}})
            logger.info("✅ Conexión establecida")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error en setup: {{e}}")
            return False
    
    def run(self) -> dict:
        """Ejecuta todas las acciones grabadas."""
        if not self.setup():
            return {{"status": "FAILED", "reason": "Setup failed"}}
        
        results = {{
            "session_id": self.session_id,
            "status": "RUNNING",
            "total_actions": {len(self.actions)},
            "completed": 0,
            "failed": 0,
            "errors": [],
            "start_time": datetime.now().isoformat(),
        }}
        
        logger.info(f"🚀 Iniciando ejecución: {{results['total_actions']}} acciones")
        
        # DB Tracking: Start
        self.db_update_status('En Proceso')
        
        try:
{actions_code}
            
            results["status"] = "SUCCESS" if results["failed"] == 0 else "PARTIAL"
            
        except Exception as e:
            logger.error(f"❌ Error crítico: {{e}}")
            results["status"] = "FAILED"
            results["errors"].append({{"reason": str(e)}})
            self.db_update_status('error')
        
        results["end_time"] = datetime.now().isoformat()
        
        logger.info(f"📊 RESUMEN: {{results['completed']}} OK, {{results['failed']}} FAILED")
        logger.info(f"Status: {{results['status']}}")
        
        # DB Tracking: Final
        if results["status"] == "SUCCESS":
            self.db_update_status('En Proceso')
        
        return results


def main():
    """Punto de entrada principal."""
    setup_logging()
    
    automation = {class_name}Automation()
    results = automation.run()
    
    print("\\n" + "="*50)
    print(f"Resultado: {{results['status']}}")
    print(f"Completadas: {{results['completed']}}/{{results['total_actions']}}")
    print(f"Fallidas: {{results['failed']}}")
    print("="*50)
    
    return 0 if results["status"] == "SUCCESS" else 1


if __name__ == "__main__":
    sys.exit(main())
'''
        
        return script
    
    def _generate_actions_code(self) -> str:
        """Genera el código para ejecutar cada acción."""
        lines = []
        
        for idx, action_data in enumerate(self.actions, 1):
            action_type = action_data.get("type", "unknown")
            
            # Comentario descriptivo
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
            
            # Manejo de errores
            lines.append(f'                results["completed"] += 1')
            lines.append(f'                logger.info(f"[{idx}/{len(self.actions)}] ✅ {action_type}")')
            lines.append(f'            except Exception as e:')
            lines.append(f'                results["failed"] += 1')
            lines.append(f'                results["errors"].append({{"action_idx": {idx}, "type": "{action_type}", "reason": str(e)}})')
            lines.append(f'                logger.error(f"[{idx}/{len(self.actions)}] ❌ {action_type}: {{e}}")')
            lines.append(f'')
        
        return "\n".join(lines)
    
    def _generate_click_action(self, action_data: Dict, idx: int) -> str:
        """Genera código para acción de click."""
        selector = action_data.get("selector", {})
        position = action_data.get("position", {})
        
        # Crear objeto Action
        code = f'''                action = Action(
                    type=ActionType.CLICK,
                    selector={repr(selector)},
                    position={repr(position)},
                    timestamp=datetime.fromisoformat("{action_data.get('timestamp', datetime.now().isoformat())}")
                )
                self.execute_click_action(action)'''
        
        return code
    
    def _generate_type_action(self, action_data: Dict, idx: int) -> str:
        """Genera código para acción de typing."""
        text = action_data.get("text", "")
        selector = action_data.get("selector", {})
        
        code = f'''                action = Action(
                    type=ActionType.TYPE_TEXT,
                    text={repr(text)},
                    selector={repr(selector)},
                    timestamp=datetime.fromisoformat("{action_data.get('timestamp', datetime.now().isoformat())}")
                )
                self.executor.execute(action)'''
        
        return code
    
    def _generate_key_action(self, action_data: Dict, idx: int) -> str:
        """Genera código para acción de tecla especial."""
        key_code = action_data.get("key_code", "")
        
        code = f'''                action = Action(
                    type=ActionType.KEY_PRESS,
                    key_code="{key_code}",
                    timestamp=datetime.fromisoformat("{action_data.get('timestamp', datetime.now().isoformat())}")
                )
                self.executor.execute(action)'''
        
        return code
    
    def _generate_key_combination_action(self, action_data: Dict, idx: int) -> str:
        """Genera código para combinación de teclas."""
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
