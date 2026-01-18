"""Generador de scripts rápidos."""
import json
from pathlib import Path

class QuickScriptGenerator:
    """Genera script ejecutable."""
    
    def __init__(self, recording_json: str):
        self.recording_path = Path(recording_json)
        
        with open(recording_json) as f:
            self.data = json.load(f)
    
    def generate(self, output: str = None) -> str:
        """Genera script."""
        # Use centralized path management
        from utils.paths import get_ui_recording_path
        
        if not output:
            output = f"{self.recording_path.stem}_script.py"
        
        # Get full path using centralized management
        output_path = get_ui_recording_path(output)
        
        script = f'''#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Auto-generated script."""

import json
import sys
from pathlib import Path
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
        script_name = Path(sys.argv[0]).stem
        query = "UPDATE registro_acciones SET `update` = NOW(), ultimo_nodo = %s, estado = %s WHERE estado = 'En Proceso'"
        cursor.execute(query, (script_name, status))
        conn.commit()
        conn.close()
        print(f"[DB] Tracking actualizado: {{script_name}} ({{status}})")
    except Exception as e:
        print(f"[DB Error] {{e}}")

if __name__ == "__main__":
    setup_logging()
    
    # DB Tracking: Start
    db_update_status('En Proceso')
    
    try:
        config = load_config("config/ris_config.yaml")
        player = RecordingPlayer("{self.recording_path.as_posix()}", config)
        results = player.run()
        print(results)
        
        # DB Tracking: Success
        db_update_status('En Proceso')
    except Exception as e:
        print(f"Error: {{e}}")
        # DB Tracking: Error
        db_update_status('error')
'''
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(script)
        
        return str(output_path)
