"""RecordingPlayer - Reproduce grabación."""
import json
import logging
from pathlib import Path
from datetime import datetime
from pywinauto import Application, findwindows
from .action import Action
from .executor import ActionExecutor

logger = logging.getLogger(__name__)

class RecordingPlayer:
    """Reproduce grabación con validación."""
    
from typing import Dict, Optional, Union

# ... imports ...

class RecordingPlayer:
    """Reproduce grabación con validación."""
    
    def __init__(self, recording_source: Union[str, Dict], config: dict):
        self.config = config
        self.app = None
        self.executor = None
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if isinstance(recording_source, dict):
            self.data = recording_source
            self.recording_path = None
        else:
            self.recording_path = Path(recording_source)
            with open(recording_source, "r", encoding="utf-8") as f:
                self.data = json.load(f)
    
    def setup(self) -> bool:
        """Conecta a ventana objetivo."""
        app_context = self.config.get("app_context", "VueRIS")
        window_title_pattern = self.config.get("window_title", ".*Vue.*RIS.*")
        
        logger.info(f"Buscando ventana: {window_title_pattern}")
        
        try:
            windows = findwindows.find_windows(title_re=window_title_pattern)
            if windows:
                self.app = Application(backend='uia').connect(handle=windows[0])
                logger.info(f"Conectado a: {windows[0].window_text()}")
            else:
                logger.warning("Ventana principal no encontrada. Fallando a modo Desktop (Global).")
                # Conectar a explorer como fallback para tener un contexto válido
                try:
                    self.app = Application(backend='uia').connect(path="explorer.exe")
                except:
                    logger.warning("No se pudo conectar a explorer.exe, usando modo Desktop puro.")
                    self.app = None
            
            self.executor = ActionExecutor(self.app, self.config)
            return True
            
        except Exception as e:
            logger.error(f"Error en setup: {e}")
            # Intentar continuar aun si falla el setup específico
            try:
                self.app = Application(backend='uia')
                self.executor = ActionExecutor(self.app, self.config)
                return True
            except:
                return False
    
    def run(self) -> dict:
        """Ejecuta todas las acciones."""
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
