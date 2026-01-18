
from PyQt6.QtCore import QThread, pyqtSignal
from core.player import RecordingPlayer
import json
import os
from pathlib import Path

class ReplayWorker(QThread):
    """Worker para reproducción sin bloquear UI."""
    progress = pyqtSignal(int)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, recording_path: str, config: dict):
        super().__init__()
        self.recording_path = recording_path
        self.config = config
    
    def run(self):
        print(f"[DEBUG] ReplayWorker: Iniciando thread... (TID: {int(QThread.currentThreadId())})")
        
        # Inicializar COM para este hilo (necesario para pywinauto en QThread)
        try:
            import pythoncom
            pythoncom.CoInitialize()
            print("[DEBUG] ReplayWorker: CoInitialize OK")
        except:
            pass

        try:
            from core.web_player import WebReplayer
            ext = Path(self.recording_path).suffix.lower()
            
            if ext == ".py":
                print(f"[DEBUG] ReplayWorker: Ejecutando SCRIPT PYTHON ({self.recording_path})")
                import subprocess
                import sys
                
                env = os.environ.copy()
                env["PYTHONUNBUFFERED"] = "1"
                
                process = subprocess.Popen(
                    [sys.executable, self.recording_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding='utf-8',
                    env=env,
                    bufsize=1,
                    universal_newlines=True
                )
                
                stdout_lines = []
                while True:
                    line = process.stdout.readline()
                    if not line and process.poll() is not None:
                        break
                    if line:
                        print(f"   [REPLAY] {line.strip()}")
                        stdout_lines.append(line)
                
                returncode = process.poll()
                status = "SUCCESS" if returncode == 0 else "FAILED"
                results = {
                    "status": status,
                    "completed": 1 if returncode == 0 else 0,
                    "failed": 0 if returncode == 0 else 1,
                    "stdout": "".join(stdout_lines),
                    "stderr": ""
                }
            else:
                print(f"[DEBUG] ReplayWorker: Cargando JSON {self.recording_path}")
                with open(self.recording_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # Detectar si es web (JSON)
                is_web = "steps" in data and "session" in data
                
                if is_web:
                    print("[DEBUG] ReplayWorker: Usando WebReplayer.")
                    player = WebReplayer(data, self.config)
                else:
                    print("[DEBUG] ReplayWorker: Usando RecordingPlayer.")
                    player = RecordingPlayer(data, self.config)
                
                results = player.run()
            
            self.finished.emit(results)
            
        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n{traceback.format_exc()}"
            print(f"[DEBUG] ReplayWorker: EXCEPCIÓN: {error_msg}")
            self.error.emit(str(e))
            
        finally:
            try:
                import pythoncom
                pythoncom.CoUninitialize()
            except:
                pass

class OCRInitWorker(QThread):
    """Worker para inicializar OCR en segundo plano."""
    finished = pyqtSignal(object, object, object, object) 
    error = pyqtSignal(str)
    
    def __init__(self, engine_name, lang):
        super().__init__()
        self.engine_name = engine_name
        self.lang = lang
        
    def run(self):
        try:
            from ocr.engine import OCREngine
            from ocr.matcher import OCRMatcher
            from ocr.actions import OCRActions
            from ocr.code_generator import OCRCodeGenerator
            
            engine = OCREngine(engine=self.engine_name, language=self.lang)
            matcher = OCRMatcher(threshold=80)
            actions = OCRActions(engine, matcher)
            generator = OCRCodeGenerator(engine=self.engine_name, language=self.lang)
            
            self.finished.emit(engine, matcher, actions, generator)
        except Exception as e:
            import traceback
            self.error.emit(f"{str(e)}\n{traceback.format_exc()}")
