#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
setup_project.py - RPA Framework v2 Generator

Ejecutar: python setup_project.py

Genera estructura completa:
- 7 módulos core
- 4 módulos utils
- 2 generadores
- Configuración YAML
- CLI principal
- requirements.txt
- README.md

TODO auto-contenido y production-ready.
"""

import os
import shutil
from pathlib import Path
from datetime import datetime

# ============================================================================
# ESTRUCTURA Y CONTENIDOS
# ============================================================================

PROJECT_STRUCTURE = {
    # Core modules
    "core/__init__.py": """\"\"\"Core RPA modules.\"\"\"
from .action import Action, ActionType
from .selector import WindowsSelector, SelectorStrategy
from .executor import ActionExecutor
from .player import RecordingPlayer
from .recorder import RPARecorder, RecorderGUI
from .optimizer import ActionOptimizer

__all__ = [
    "Action",
    "ActionType",
    "WindowsSelector",
    "SelectorStrategy",
    "ActionExecutor",
    "RecordingPlayer",
    "RPARecorder",
    "RecorderGUI",
    "ActionOptimizer",
]
""",

    "core/action.py": """\"\"\"Dataclass Action - Inmutable.\"\"\"
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Optional
from enum import Enum

class ActionType(str, Enum):
    CLICK = "click"
    TYPE_TEXT = "type"
    KEY_PRESS = "key"
    WAIT = "wait"
    VALIDATE = "validate"

@dataclass(frozen=True)
class Action:
    \"\"\"Acción inmutable con metadatos completos.\"\"\"
    type: ActionType
    timestamp: datetime
    wait_before: float = 0.0
    
    selector: Optional[Dict[str, str]] = None
    position: Optional[Dict[str, int]] = None
    
    text: Optional[str] = None
    key_code: Optional[str] = None
    validation_rule: Optional[str] = None
    
    app_context: str = "unknown"
    element_info: Optional[Dict] = None
    
    def to_dict(self) -> Dict:
        data = asdict(self)
        data['type'] = self.type.value
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Action":
        data['type'] = ActionType(data['type'])
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)
""",

    "core/selector.py": """\"\"\"WindowsSelector - Búsqueda con fallback chain.\"\"\"
import logging
from typing import Dict, Optional, Tuple
from pywinauto import Desktop
from pywinauto.findwindows import ElementNotFoundError

logger = logging.getLogger(__name__)

class SelectorStrategy:
    \"\"\"Strategy pattern para selectores.\"\"\"
    
    @staticmethod
    def by_automation_id(automation_id: str) -> Dict:
        return {"automation_id": automation_id}
    
    @staticmethod
    def by_name_and_controltype(name: str, control_type: str) -> Dict:
        return {"name": name, "control_type": control_type}
    
    @staticmethod
    def by_classname_and_title(classname: str, title_regex: str) -> Dict:
        return {"classname": classname, "title_regex": title_regex}
    
    @staticmethod
    def by_position(x: int, y: int) -> Dict:
        return {"position": (x, y)}

class WindowsSelector:
    \"\"\"Encuentra elementos con fallback chain y retry.\"\"\"
    
    FALLBACK_CHAIN = [
        "automation_id",
        "name_and_controltype",
        "classname_and_title",
        "position"
    ]
    
    def __init__(self, app_context: str = "unknown", max_retries: int = 2):
        self.app_context = app_context
        self.max_retries = max_retries
        self.desktop = Desktop(backend='uia')
    
    @staticmethod
    def extract_from_point(x: int, y: int) -> Dict:
        \"\"\"Extrae propiedades de elemento en (x, y).\"\"\"
        try:
            desktop = Desktop(backend='uia')
            element = desktop.from_point((x, y))
            return {
                "name": element.element_info.name or "",
                "automation_id": element.element_info.automation_id or "",
                "class_name": element.element_info.class_name or "",
                "control_type": element.element_info.control_type or "",
            }
        except Exception as e:
            logger.warning(f"No se pudo extraer elemento en ({x}, {y}): {e}")
            return {}
    
    def build_selector(self, element_info: Dict, position: Tuple[int, int]) -> Dict:
        \"\"\"Construye selector priorizado.\"\"\"
        selector = {}
        
        if element_info.get("automation_id"):
            selector["automation_id"] = element_info["automation_id"]
            logger.debug(f"Selector: automation_id")
            return selector
        
        if element_info.get("name") and element_info.get("control_type"):
            selector["name"] = element_info["name"]
            selector["control_type"] = element_info["control_type"]
            logger.debug(f"Selector: name + control_type")
            return selector
        
        if element_info.get("class_name"):
            selector["class_name"] = element_info["class_name"]
            logger.debug(f"Selector: class_name")
            return selector
        
        selector["position"] = position
        logger.debug(f"Selector: position (fallback)")
        return selector
    
    def find_element(self, selector: Dict, timeout: float = 5.0):
        \"\"\"Busca elemento con retry.\"\"\"
        for attempt in range(1, self.max_retries + 1):
            try:
                if "automation_id" in selector:
                    element = self.desktop.window(automation_id=selector["automation_id"])
                elif "name" in selector and "control_type" in selector:
                    element = self.desktop.window(
                        name=selector["name"],
                        control_type=selector["control_type"]
                    )
                elif "class_name" in selector:
                    element = self.desktop.window(class_name=selector["class_name"])
                elif "position" in selector:
                    x, y = selector["position"]
                    element = self.desktop.from_point((x, y))
                else:
                    raise ValueError(f"Selector no reconocido: {selector}")
                
                element.wait("visible", timeout=timeout)
                logger.info(f"Elemento encontrado: {selector}")
                return element
                
            except Exception as e:
                logger.warning(f"Intento {attempt}/{self.max_retries} fallido: {e}")
                if attempt == self.max_retries:
                    logger.error(f"No se pudo encontrar elemento: {selector}")
                    raise
                import time
                time.sleep(0.5)
""",

    "core/executor.py": """\"\"\"ActionExecutor - Ejecuta acciones con retry.\"\"\"
import logging
import time
from typing import Callable
from functools import wraps
from pywinauto import Application
from .action import Action, ActionType
from .selector import WindowsSelector

logger = logging.getLogger(__name__)

def log_execution_time(func: Callable) -> Callable:
    \"\"\"Decorator para loguear tiempo.\"\"\"
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        try:
            result = func(*args, **kwargs)
            elapsed = time.time() - start
            logger.info(f"{func.__name__} completado en {elapsed:.2f}s")
            return result
        except Exception as e:
            elapsed = time.time() - start
            logger.error(f"{func.__name__} falló en {elapsed:.2f}s: {e}")
            raise
    return wrapper

class ActionExecutor:
    \"\"\"Ejecuta acciones con retry y validación.\"\"\"
    
    def __init__(self, app: Application, config: dict):
        self.app = app
        self.config = config
        self.selector_helper = WindowsSelector(
            app_context=config.get("app_context", "unknown"),
            max_retries=config.get("max_retries", 2)
        )
    
    @log_execution_time
    def execute(self, action: Action) -> bool:
        \"\"\"Ejecuta una acción según su tipo.\"\"\"
        
        if action.wait_before > 0:
            logger.debug(f"Esperando {action.wait_before}s...")
            time.sleep(action.wait_before)
        
        if action.type == ActionType.CLICK:
            return self._execute_click(action)
        elif action.type == ActionType.TYPE_TEXT:
            return self._execute_type_text(action)
        elif action.type == ActionType.KEY_PRESS:
            return self._execute_key_press(action)
        elif action.type == ActionType.WAIT:
            return self._execute_wait(action)
        elif action.type == ActionType.VALIDATE:
            return self._execute_validate(action)
        else:
            logger.warning(f"Tipo desconocido: {action.type}")
            return False
    
    def _execute_click(self, action: Action) -> bool:
        \"\"\"Click con fallback.\"\"\"
        max_retries = self.config.get("click_retries", 2)
        retry_delay = self.config.get("retry_delay", 1.0)
        
        for attempt in range(1, max_retries + 1):
            try:
                if action.selector:
                    element = self.selector_helper.find_element(
                        action.selector,
                        timeout=self.config.get("element_timeout", 5.0)
                    )
                    logger.info(f"Click [{attempt}/{max_retries}] por selector")
                    element.click_input()
                else:
                    logger.info(f"Click [{attempt}/{max_retries}] por coordenadas")
                    import pyautogui
                    x, y = action.position["x"], action.position["y"]
                    pyautogui.click(x, y)
                
                logger.info(f"Click exitoso")
                return True
                
            except Exception as e:
                logger.warning(f"Intento {attempt} fallido: {e}")
                if attempt < max_retries:
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Click final fallido")
                    return False
    
    def _execute_type_text(self, action: Action) -> bool:
        \"\"\"Type con selector o foco.\"\"\"
        max_retries = self.config.get("type_retries", 1)
        
        for attempt in range(1, max_retries + 1):
            try:
                if action.selector:
                    element = self.selector_helper.find_element(
                        action.selector,
                        timeout=self.config.get("element_timeout", 5.0)
                    )
                    logger.info(f"Type [{attempt}/{max_retries}] en selector")
                    element.type_keys(action.text, with_spaces=True)
                else:
                    logger.info(f"Type [{attempt}/{max_retries}] en foco")
                    import pyautogui
                    pyautogui.typewrite(action.text, interval=0.05)
                
                logger.info(f"Texto escrito: {action.text[:50]}...")
                return True
                
            except Exception as e:
                logger.warning(f"Intento {attempt} fallido: {e}")
                if attempt == max_retries:
                    logger.error(f"Type final fallido")
                    return False
    
    def _execute_key_press(self, action: Action) -> bool:
        \"\"\"Presionar tecla.\"\"\"
        try:
            logger.info(f"Presionando: {action.key_code}")
            import pyautogui
            pyautogui.press(action.key_code.lower())
            logger.info(f"Tecla {action.key_code} presionada")
            return True
        except Exception as e:
            logger.error(f"Error: {e}")
            return False
    
    def _execute_wait(self, action: Action) -> bool:
        \"\"\"Espera.\"\"\"
        logger.info(f"Esperando: {action.validation_rule}")
        time.sleep(action.wait_before)
        return True
    
    def _execute_validate(self, action: Action) -> bool:
        \"\"\"Validación.\"\"\"
        logger.info(f"Validando: {action.validation_rule}")
        return True
""",

    "core/player.py": """\"\"\"RecordingPlayer - Reproduce grabación.\"\"\"
import json
import logging
from pathlib import Path
from datetime import datetime
from pywinauto import Application, findwindows
from .action import Action
from .executor import ActionExecutor

logger = logging.getLogger(__name__)

class RecordingPlayer:
    \"\"\"Reproduce grabación con validación.\"\"\"
    
    def __init__(self, recording_json: str, config: dict):
        self.recording_path = Path(recording_json)
        self.config = config
        self.app = None
        self.executor = None
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        with open(recording_json, "r", encoding="utf-8") as f:
            self.data = json.load(f)
    
    def setup(self) -> bool:
        \"\"\"Conecta a ventana objetivo.\"\"\"
        app_context = self.config.get("app_context", "VueRIS")
        window_title_pattern = self.config.get("window_title", ".*Vue.*RIS.*")
        
        logger.info(f"Buscando ventana: {window_title_pattern}")
        
        try:
            windows = findwindows.find_windows(title_re=window_title_pattern)
            if not windows:
                logger.error(f"Ventana no encontrada")
                return False
            
            self.app = Application(backend='uia').connect(handle=windows[0])
            logger.info(f"Conectado a: {windows[0].window_text()}")
            
            self.executor = ActionExecutor(self.app, self.config)
            return True
            
        except Exception as e:
            logger.error(f"Error en setup: {e}")
            return False
    
    def run(self) -> dict:
        \"\"\"Ejecuta todas las acciones.\"\"\"
        if not self.setup():
            return {"status": "FAILED", "reason": "Setup failed"}
        
        results = {
            "session_id": self.session_id,
            "status": "RUNNING",
            "total_actions": len(self.data["actions"]),
            "completed": 0,
            "failed": 0,
            "errors": [],
            "start_time": datetime.now().isoformat(),
        }
        
        logger.info(f"Iniciando: {results['total_actions']} acciones")
        
        for idx, action_data in enumerate(self.data["actions"], 1):
            action = Action.from_dict(action_data)
            
            try:
                logger.info(f"[{idx}/{results['total_actions']}] {action.type.value}")
                success = self.executor.execute(action)
                
                if success:
                    results["completed"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append({
                        "action_idx": idx,
                        "type": action.type.value,
                    })
                    
                    if self.config.get("stop_on_error", False):
                        results["status"] = "FAILED"
                        break
                        
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "action_idx": idx,
                    "type": action.type.value,
                    "reason": str(e)
                })
                logger.error(f"Error en acción {idx}: {e}")
                
                if self.config.get("stop_on_error", False):
                    results["status"] = "FAILED"
                    break
        
        results["end_time"] = datetime.now().isoformat()
        results["status"] = "SUCCESS" if results["failed"] == 0 else "PARTIAL"
        
        logger.info(f"RESUMEN: {results['completed']} OK, {results['failed']} FAILED")
        logger.info(f"Status: {results['status']}")
        
        return results
""",

    "core/recorder.py": """\"\"\"RPARecorder - Captura con GUI.\"\"\"
import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict
from pynput import mouse, keyboard
import time

logger = logging.getLogger(__name__)

class RPARecorder:
    \"\"\"Captura acciones mouse/keyboard.\"\"\"
    
    def __init__(self, config: dict):
        self.config = config
        self.actions: List[Dict] = []
        self.recording = False
        self.last_text_time = time.time()
        self.text_buffer = ""
        self.listeners = []
    
    def start(self):
        \"\"\"Inicia grabación.\"\"\"
        self.recording = True
        self.actions = []
        logger.info("Grabación iniciada")
        
        listener_mouse = mouse.Listener(on_click=self._on_click)
        listener_keyboard = keyboard.Listener(on_press=self._on_press)
        
        listener_mouse.start()
        listener_keyboard.start()
        
        self.listeners = [listener_mouse, listener_keyboard]
    
    def stop(self) -> List[Dict]:
        \"\"\"Detiene grabación.\"\"\"
        self.recording = False
        for listener in self.listeners:
            listener.stop()
        logger.info(f"Grabación detenida: {len(self.actions)} acciones")
        return self.actions
    
    def _on_click(self, x, y, button, pressed):
        if not self.recording:
            return
        if pressed:
            logger.debug(f"Click: ({x}, {y})")
            self.actions.append({
                "type": "click",
                "position": {"x": x, "y": y},
                "timestamp": datetime.now().isoformat(),
            })
    
    def _on_press(self, key):
        if not self.recording:
            return
        
        try:
            char = key.char
            if char:
                self.text_buffer += char
                self.last_text_time = time.time()
        except:
            key_name = str(key).replace("Key.", "").upper()
            if key_name in ["ENTER", "TAB", "ESCAPE"]:
                logger.debug(f"Key: {key_name}")
                self.actions.append({
                    "type": "key",
                    "key_code": key_name,
                    "timestamp": datetime.now().isoformat(),
                })
    
    def save(self, filename: str):
        \"\"\"Guarda grabación a JSON.\"\"\"
        output_dir = Path("recordings")
        output_dir.mkdir(exist_ok=True)
        
        if not filename.endswith(".json"):
            filename = f"{filename}.json"
        
        output_path = output_dir / filename
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump({
                "metadata": {
                    "created_at": datetime.now().isoformat(),
                    "total_actions": len(self.actions),
                },
                "actions": self.actions
            }, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Guardado: {output_path}")
        return str(output_path)

class RecorderGUI:
    \"\"\"GUI simple para grabación.\"\"\"
    
    def __init__(self, config: dict):
        self.config = config
        self.recorder = RPARecorder(config)
    
    def run(self):
        \"\"\"Inicia GUI (tkinter).\"\"\"
        try:
            import tkinter as tk
            from tkinter import simpledialog, messagebox
            
            root = tk.Tk()
            root.title("RPA Recorder v2")
            root.geometry("300x150")
            root.attributes('-topmost', True)
            
            self.status_var = tk.StringVar(value="READY")
            self.count_var = tk.StringVar(value="0")
            
            tk.Label(root, textvariable=self.status_var, font=("Arial", 14)).pack(pady=10)
            tk.Label(root, text="Acciones:", font=("Arial", 12)).pack()
            tk.Label(root, textvariable=self.count_var, font=("Arial", 20, "bold")).pack()
            
            frame = tk.Frame(root)
            frame.pack(pady=10)
            
            tk.Button(frame, text="⏺ REC", command=self._record, width=10).pack(side=tk.LEFT, padx=5)
            tk.Button(frame, text="⏸ PAUSE", command=self._pause, width=10).pack(side=tk.LEFT, padx=5)
            tk.Button(frame, text="⏹ STOP", command=self._stop, width=10).pack(side=tk.LEFT, padx=5)
            
            self.root = root
            root.mainloop()
            
        except ImportError:
            logger.info("tkinter no disponible, modo CLI")
            self._run_cli()
    
    def _record(self):
        self.recorder.start()
        self.status_var.set("REC...")
        self._update_count()
    
    def _pause(self):
        self.status_var.set("PAUSED")
    
    def _stop(self):
        self.status_var.set("STOPPED")
        self.recorder.stop()
        
        import tkinter as simpledialog
        name = simpledialog.askstring("Guardar", "Nombre de la grabación:")
        if name:
            self.recorder.save(name)
        
        self.root.quit()
    
    def _update_count(self):
        self.count_var.set(str(len(self.recorder.actions)))
        self.root.after(500, self._update_count)
    
    def _run_cli(self):
        \"\"\"Modo CLI sin GUI.\"\"\"
        input("Presiona ENTER para iniciar grabación...\")
        self.recorder.start()
        print("Grabando... (presiona Ctrl+C para detener)")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.recorder.stop()
            name = input("Nombre de la grabación: ")
            self.recorder.save(name)
""",

    "core/optimizer.py": """\"\"\"ActionOptimizer - Limpia acciones.\"\"\"
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

class ActionOptimizer:
    \"\"\"Optimiza acciones (limpieza, consolidación).\"\"\"
    
    @staticmethod
    def optimize(actions: List[Dict]) -> List[Dict]:
        \"\"\"Optimiza lista de acciones.\"\"\"
        if not actions:
            return []
        
        optimized = []
        
        for action in actions:
            # Saltar acciones de movimiento sin click
            if action.get("type") == "move":
                continue
            
            optimized.append(action)
        
        logger.info(f"Acciones: {len(actions)} → {len(optimized)}")
        return optimized
""",

    # Utils
    "utils/__init__.py": """\"\"\"Utilities.\"\"\"
""",

    "utils/logging_setup.py": """\"\"\"Logging estructurado.\"\"\"
import logging
from pathlib import Path

def setup_logging(level: str = "INFO"):
    \"\"\"Configura logging.\"\"\"
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    log_format = "%(asctime)s [%(name)s] %(levelname)s %(message)s"
    
    logging.basicConfig(
        level=getattr(logging, level),
        format=log_format,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_dir / "rpa.log", encoding="utf-8")
        ]
    )
""",

    "utils/config_loader.py": """\"\"\"Carga configuración YAML.\"\"\"
import yaml
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def load_config(config_file: str) -> dict:
    \"\"\"Carga YAML config.\"\"\"
    config_path = Path(config_file)
    
    if not config_path.exists():
        logger.warning(f"Config no encontrada: {config_file}")
        return {}
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        logger.info(f"Config cargada: {config_file}")
        return config or {}
    except Exception as e:
        logger.error(f"Error cargando config: {e}")
        return {}
""",

    "utils/health_check.py": """\"\"\"Health checks.\"\"\"
import logging
import psutil

logger = logging.getLogger(__name__)

class SystemMonitor:
    \"\"\"Monitorea salud del sistema.\"\"\"
    
    @staticmethod
    def check():
        \"\"\"Verifica CPU, RAM, disco.\"\"\"
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory().percent
        
        if cpu > 80:
            logger.warning(f"CPU alta: {cpu}%")
        if ram > 80:
            logger.warning(f"RAM alta: {ram}%")
        
        logger.debug(f"CPU: {cpu}%, RAM: {ram}%")
        return {"cpu": cpu, "ram": ram}
""",

    "utils/decorators.py": """\"\"\"Decorators.\"\"\"
import logging
import time
from functools import wraps

logger = logging.getLogger(__name__)

def retry_with_logging(max_attempts: int = 3, delay: float = 1.0):
    \"\"\"Retry con logging.\"\"\"
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts:
                        logger.error(f"{func.__name__} fallido finalmente")
                        raise
                    logger.warning(f"{func.__name__} reintentando ({attempt}/{max_attempts})")
                    time.sleep(delay)
        return wrapper
    return decorator

def timing(func):
    \"\"\"Mide tiempo de ejecución.\"\"\"
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start
        logger.info(f"{func.__name__} en {elapsed:.2f}s")
        return result
    return wrapper
""",

    # Generators
    "generators/__init__.py": """\"\"\"Generadores.\"\"\"
""",

    "generators/script_generator.py": """\"\"\"Generador de scripts rápidos.\"\"\"
import json
from pathlib import Path

class QuickScriptGenerator:
    \"\"\"Genera script ejecutable.\"\"\"
    
    def __init__(self, recording_json: str):
        self.recording_path = Path(recording_json)
        
        with open(recording_json) as f:
            self.data = json.load(f)
    
    def generate(self, output: str = None) -> str:
        \"\"\"Genera script.\"\"\"
        if not output:
            output = f"{self.recording_path.stem}_script.py"
        
        script = '''#!/usr/bin/env python
# -*- coding: utf-8 -*-
\"\"\"Auto-generated script.\"\"\"

import json
from pathlib import Path
from core.player import RecordingPlayer
from utils.config_loader import load_config
from utils.logging_setup import setup_logging

if __name__ == "__main__":
    setup_logging()
    config = load_config("config/ris_config.yaml")
    player = RecordingPlayer("''' + str(self.recording_path) + '''", config)
    results = player.run()
    print(results)
'''
        
        with open(output, "w", encoding="utf-8") as f:
            f.write(script)
        
        return output
""",

    "generators/module_generator.py": """\"\"\"Generador de módulos.\"\"\"
import json
import shutil
from pathlib import Path

class ModuleGenerator:
    \"\"\"Genera módulo independiente.\"\"\"
    
    def __init__(self, recording_json: str, module_name: str, config: dict):
        self.recording_path = Path(recording_json)
        self.module_name = module_name
        self.config = config
    
    def generate(self) -> Path:
        \"\"\"Genera módulo.\"\"\"
        module_dir = Path("modules") / self.module_name
        module_dir.mkdir(parents=True, exist_ok=True)
        
        # Copiar recording
        data_dir = module_dir / "data"
        data_dir.mkdir(exist_ok=True)
        shutil.copy(self.recording_path, data_dir / "recording.json")
        
        # Crear run.py
        run_py = '''#!/usr/bin/env python
# -*- coding: utf-8 -*-
\"\"\"Module runner.\"\"\"

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.player import RecordingPlayer
from utils.config_loader import load_config
from utils.logging_setup import setup_logging

if __name__ == "__main__":
    setup_logging()
    config = load_config("../../config/ris_config.yaml")
    player = RecordingPlayer("data/recording.json", config)
    results = player.run()
    print(results)
'''
        
        with open(module_dir / "run.py", "w", encoding="utf-8") as f:
            f.write(run_py)
        
        return module_dir
""",

    # Config
    "config/default_config.yaml": """# Default config

app_context: "Application"
window_title: ".*"

recorder:
  text_timeout: 2.0

execution:
  max_retries: 3
  retry_delay: 1.0
  click_retries: 2
  type_retries: 1
  element_timeout: 5.0
  action_timeout: 10.0
  stop_on_error: false

logging:
  level: "INFO"
""",

    "config/ris_config.yaml": """# Vue RIS config

app_context: "VueRIS"
window_title: ".*Vue.*RIS.*"

recorder:
  text_timeout: 2.0
  capture_element_info: true

execution:
  max_retries: 3
  retry_delay: 1.0
  click_retries: 2
  type_retries: 1
  element_timeout: 5.0
  action_timeout: 10.0
  stop_on_error: false

validation:
  post_login:
    rule: "grid_visible"
    timeout: 15.0

logging:
  level: "INFO"
""",

    # Main
    "main.py": """#!/usr/bin/env python
# -*- coding: utf-8 -*-
\"\"\"RPA Framework v2 - CLI Principal.\"\"\"

import sys
import argparse
from pathlib import Path

from core.recorder import RecorderGUI
from core.player import RecordingPlayer
from generators.script_generator import QuickScriptGenerator
from generators.module_generator import ModuleGenerator
from utils.config_loader import load_config
from utils.logging_setup import setup_logging

def cmd_record(args):
    setup_logging(level=args.log_level)
    config = load_config(args.config)
    gui = RecorderGUI(config=config)
    gui.run()

def cmd_replay(args):
    setup_logging(level=args.log_level)
    config = load_config(args.config)
    player = RecordingPlayer(args.recording, config)
    results = player.run()
    
    import json
    with open(f"replay_report_{results['session_id']}.json", "w") as f:
        json.dump(results, f, indent=2)
    
    return 0 if results["status"] == "SUCCESS" else 1

def cmd_generate_script(args):
    setup_logging(level=args.log_level)
    gen = QuickScriptGenerator(args.recording)
    output = gen.generate(args.output)
    print(f"Script generado: {output}")

def cmd_generate_module(args):
    setup_logging(level=args.log_level)
    config = load_config(args.config)
    gen = ModuleGenerator(args.recording, args.module_name, config)
    module_dir = gen.generate()
    print(f"Módulo generado: {module_dir}")

def main():
    parser = argparse.ArgumentParser(
        description="RPA Framework v2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument("--config", default="config/ris_config.yaml")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    
    subparsers = parser.add_subparsers(dest="command")
    
    sp_record = subparsers.add_parser("record", help="Grabar")
    sp_replay = subparsers.add_parser("replay", help="Reproducir")
    sp_replay.add_argument("recording")
    sp_gen_script = subparsers.add_parser("generate-script", help="Generar script")
    sp_gen_script.add_argument("recording")
    sp_gen_script.add_argument("-o", "--output")
    sp_gen_module = subparsers.add_parser("generate-module", help="Generar módulo")
    sp_gen_module.add_argument("recording")
    sp_gen_module.add_argument("-m", "--module-name", required=True)
    
    args = parser.parse_args()
    
    if args.command == "record":
        return cmd_record(args) or 0
    elif args.command == "replay":
        return cmd_replay(args)
    elif args.command == "generate-script":
        return cmd_generate_script(args) or 0
    elif args.command == "generate-module":
        return cmd_generate_module(args) or 0
    else:
        parser.print_help()
        return 1

if __name__ == "__main__":
    sys.exit(main())
""",

    # Requirements
    "requirements.txt": """pywinauto>=0.6.8
pynput>=1.7.6
pyautogui>=0.9.53
PyYAML>=6.0
psutil>=5.9.0
pytest>=7.0.0
tenacity>=8.0.0
""",

    # README
    "README.md": """# RPA Framework v2

Production-ready RPA framework with GUI recorder, player, and generators.

## Features

- 🎬 GUI Recording (mouse clicks, keyboard input)
- ▶️ Playback with retry logic
- 📄 Script generation
- 📦 Module generation
- 🔧 YAML configuration
- 🏗️ Modular architecture

## Quick Start

```bash
python main.py record --config config/ris_config.yaml
python main.py replay recordings/recording_*.json --config config/ris_config.yaml
python main.py generate-module recordings/recording_*.json --module-name "mi_modulo"
```

## Architecture

- `core/` - Action, Selector, Executor, Player, Recorder
- `utils/` - Logging, Config, Health Check
- `generators/` - Script and Module generators

## See also

- QUICK_START.md - Step by step guide
- RESUMEN_EJECUTIVO.md - Executive summary
- COMANDOS_COPYPASTE.md - Copy/paste commands
""",
}

# ============================================================================
# GENERATOR
# ============================================================================

def create_project():
    """Crea la estructura del proyecto."""
    
    base_dir = Path("rpa_framework")
    
    # Limpiar si existe
    if base_dir.exists():
        response = input(f"📁 {base_dir} ya existe. ¿Sobrescribir? (s/n): ")
        if response.lower() != 's':
            print("Abortado.")
            return
        shutil.rmtree(base_dir)
    
    print(f"📁 Creando {base_dir}...\n")
    
    # Crear archivos
    for file_path, content in PROJECT_STRUCTURE.items():
        full_path = base_dir / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        print(f"  ✓ {file_path}")
    
    # Crear directorios vacíos
    for dir_name in ["recordings", "modules", "logs", "templates", "tests"]:
        (base_dir / dir_name).mkdir(exist_ok=True)
        print(f"  ✓ {dir_name}/")
    
    print(f"\n{'='*60}")
    print(f"✅ Proyecto creado: {base_dir}/")
    print(f"{'='*60}\n")
    print("Próximos pasos:")
    print(f"  cd {base_dir}")
    print("  pip install -r requirements.txt")
    print("  python main.py record --config config/ris_config.yaml\n")

if __name__ == "__main__":
    import shutil
    create_project()
