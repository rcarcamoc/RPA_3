"""
Worker QThread para ejecutar workflows en segundo plano sin bloquear la interfaz PyQt6.
Extraído de ui/workflow_panel.py manteniendo 100% de compatibilidad.
"""

from PyQt6.QtCore import QThread, pyqtSignal

try:
    import pythoncom
except ImportError:
    pythoncom = None

from core.models import Workflow
from core.workflow_executor import WorkflowExecutor


class WorkflowExecutorWorker(QThread):
    """Worker thread para ejecutar workflows sin bloquear la UI."""
    
    log_update = pyqtSignal(str)
    node_started = pyqtSignal(str)  # node_id cuando empieza
    node_finished = pyqtSignal(str)  # node_id cuando termina
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, workflow: Workflow, log_dir: str = "workflows/logs"):
        super().__init__()
        self.workflow = workflow
        self.log_dir = log_dir
        self.executor = None
    
    def run(self):
        # Inicializar COM para este hilo (necesario para interactuar con Shell via PowerShell)
        com_initialized = False
        if pythoncom:
            try:
                pythoncom.CoInitialize()
                com_initialized = True
            except Exception:
                pass

        try:
            self.executor = WorkflowExecutor(self.workflow, self.log_dir)
            
            # Parche para capturar logs en tiempo real y detectar nodos
            original_log = self.executor.logger.log
            current_node_id = [None]  # Usamos lista para poder modificar en closure
            
            def patched_log(message, level="INFO"):
                try:
                    original_log(message, level)
                    self.log_update.emit(f"[{level}] {message}")
                    
                    # Detectar inicio de nodo
                    if "📍 Nodo actual:" in message:
                        # Buscar el nodo por label
                        for node in self.workflow.nodes:
                            if f"Nodo actual: {node.label}" in message:
                                if current_node_id[0]:
                                    self.node_finished.emit(current_node_id[0])
                                current_node_id[0] = node.id
                                self.node_started.emit(node.id)
                                break
                except Exception as log_e:
                    # Si falla el log parcheado, al menos intentamos el original
                    try:
                        original_log(f"Error en patched_log: {log_e}", "ERROR")
                    except Exception:
                        pass
            
            self.executor.logger.log = patched_log
            
            result = self.executor.execute()
            
            # Emitir fin del ultimo nodo
            if current_node_id[0]:
                self.node_finished.emit(current_node_id[0])
            
            self.finished.emit(result)
            
        except Exception as e:
            self.error.emit(str(e))
        finally:
            if com_initialized and pythoncom:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass
    
    def stop(self):
        if self.executor:
            self.executor.stop()

    def stop_after_current_case(self):
        """Solicita detener el bucle de manera segura una vez que finalice la iteración/caso actual."""
        if self.executor:
            self.executor.stop_after_current_case()

    def is_loop_running(self) -> bool:
        """Indica si el worker está ejecutando un flujo con bucle (Loop)."""
        if self.executor and hasattr(self.executor, 'is_loop_workflow'):
            if self.executor.is_loop_workflow():
                return True
        if self.workflow and getattr(self.workflow, 'nodes', None):
            for node in self.workflow.nodes:
                if getattr(node, 'type', None) in ('loop', 'LoopNode') or str(getattr(node, 'type', '')).lower() == 'loop':
                    return True
        if self.workflow and "loop" in getattr(self.workflow, 'name', '').lower():
            return True
        return False
