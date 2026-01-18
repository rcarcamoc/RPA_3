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


class {self.module_name.title().replace("_", "")}Automation:
    """Automatización generada: {self.module_name}"""
    
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
            script_name = "{self.module_name}"
            query = "UPDATE registro_acciones SET `update` = NOW(), ultimo_nodo = %s, estado = %s WHERE estado = 'En Proceso'"
            cursor.execute(query, (script_name, status))
            conn.commit()
            conn.close()
            logger.info(f"[DB] Tracking actualizado: {{script_name}} ({{status}})")
        except Exception as e:
            logger.warning(f"[DB Error] {{e}}")
    
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
    
    automation = {self.module_name.title().replace("_", "")}Automation()
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
                self.executor.execute(action)'''
        
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
