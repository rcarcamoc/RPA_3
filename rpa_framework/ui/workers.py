
from PyQt6.QtCore import QThread, pyqtSignal
from core.player import RecordingPlayer

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
            print("[DEBUG] ReplayWorker: Intentando CoInitialize...")
            pythoncom.CoInitialize()
            print("[DEBUG] ReplayWorker: CoInitialize OK")
        except ImportError:
            print("[DEBUG] ReplayWorker: pythoncom no encontrado, saltando CoInitialize")
        except Exception as e:
            print(f"[DEBUG] ReplayWorker: Error en CoInitialize: {e}")

        try:
            print(f"[DEBUG] ReplayWorker: Inicializando RecordingPlayer con {self.recording_path}")
            player = RecordingPlayer(self.recording_path, self.config)
            
            print("[DEBUG] ReplayWorker: Ejecutando player.run()...")
            results = player.run()
            
            print(f"[DEBUG] ReplayWorker: Ejecución finalizada. Status: {results.get('status')}")
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
                print("[DEBUG] ReplayWorker: CoUninitialize OK")
            except:
                pass

class OCRInitWorker(QThread):
    """Worker para inicializar OCR en segundo plano."""
    finished = pyqtSignal(object, object, object, object) # engine, matcher, actions, generator
    error = pyqtSignal(str)
    
    def __init__(self, engine_name, lang):
        super().__init__()
        self.engine_name = engine_name
        self.lang = lang
        
    def run(self):
        try:
            # Importar aquí para evitar circularidad o carga temprana
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
