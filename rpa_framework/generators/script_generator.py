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
        if not output:
            output = f"{self.recording_path.stem}_script.py"
        
        script = '''#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Auto-generated script."""

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
