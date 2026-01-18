"""Generador de módulos."""
import json
import shutil
from pathlib import Path

class ModuleGenerator:
    """Genera módulo independiente."""
    
    def __init__(self, recording_json: str, module_name: str, config: dict):
        self.recording_path = Path(recording_json)
        self.module_name = module_name
        self.config = config
    
    def generate(self) -> Path:
        """Genera módulo independiente sin dependencias externas."""
        # Use centralized path management
        from utils.paths import UI_RECORDINGS_DIR
        
        module_dir = UI_RECORDINGS_DIR / self.module_name
        module_dir.mkdir(parents=True, exist_ok=True)
        
        # Leer JSON original
        with open(self.recording_path, "r", encoding="utf-8") as f:
            recording_content = f.read()

        # Crear run.py con JSON incrustado
        run_py = f'''#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Module runner (Standalone)."""

import sys
import json
from pathlib import Path

# Agregar raíz del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.player import RecordingPlayer
from utils.config_loader import load_config
from utils.logging_setup import setup_logging

try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

def db_update_status(status='En Proceso'):
    """Actualiza el estado en la BD"""
    if not HAS_MYSQL: return
    try:
        conn = mysql.connector.connect(host='localhost', user='root', password='', database='ris')
        cursor = conn.cursor()
        script_name = "{self.module_name}"
        query = "UPDATE registro_acciones SET `update` = NOW(), ultimo_nodo = %s, estado = %s WHERE estado = 'En Proceso'"
        cursor.execute(query, (script_name, status))
        conn.commit()
        conn.close()
        print(f"[DB] Tracking actualizado: {{script_name}} ({{status}})")
    except Exception as e:
        print(f"[DB Error] {{e}}")

# DATOS DE LA GRABACIÓN (INCRUSTADOS)
RECORDING_JSON = r"""
{recording_content}
"""

if __name__ == "__main__":
    setup_logging()
    
    # DB Tracking: Start
    db_update_status('En Proceso')
    
    # Cargar configuración (puede ser externa o default)
    try:
        config = load_config("../../config/ris_config.yaml")
    except:
        config = {{}}
        
    print("🚀 Ejecutando módulo independiente: {self.module_name}")
    
    try:
        # Parsear datos incrustados
        recording_data = json.loads(RECORDING_JSON)
        
        # Instanciar player con diccionario de datos
        player = RecordingPlayer(recording_data, config)
        
        results = player.run()
        print(results)
        
        # DB Tracking: Success
        db_update_status('En Proceso')
    except Exception as e:
        print(f"Error: {{e}}")
        # DB Tracking: Error
        db_update_status('error')
'''
        
        with open(module_dir / "run.py", "w", encoding="utf-8") as f:
            f.write(run_py)
        
        return module_dir
