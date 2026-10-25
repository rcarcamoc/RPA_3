"""
Ejecutor de workflows para el RPA Framework 3.

Este módulo contiene la lógica para ejecutar workflows secuencialmente,
manejar control de flujo (IF/ELSE, LOOP) y gestionar variables compartidas.

Refactorizado de forma modular hacia rpa_framework/core/executor_handlers/
manteniendo 100% de compatibilidad hacia atrás.
"""

import subprocess
import os
import sys
import threading
from datetime import datetime
from typing import Dict, Any, Optional

from core.models import Workflow, Node, NodeType, ActionNode, DecisionNode, LoopNode, WorkflowNode
from core.logger import WorkflowLogger
from utils.telegram_manager import enviar_alerta_todos

from core.executor_handlers import (
    get_python_exe,
    _get_silent_process_flags,
    ProcessEnvMixin,
    VideoRecorderMixin,
    ActionNodeMixin,
    LoopNodeMixin,
    DatabaseNodeMixin,
    SubworkflowNodeMixin,
)

try:
    from utils.screen_utils import get_screen_resolution
except ImportError:
    try:
        from rpa_framework.utils.screen_utils import get_screen_resolution
    except ImportError:
        def get_screen_resolution():
            return "1920x1080"


class WorkflowExecutor(
    ProcessEnvMixin,
    VideoRecorderMixin,
    ActionNodeMixin,
    LoopNodeMixin,
    DatabaseNodeMixin,
    SubworkflowNodeMixin,
):
    """Ejecutor de workflows con soporte para IF/ELSE y LOOP"""

    def __init__(self, workflow: Workflow, log_dir: str = "logs", enable_recording: bool = True, is_sub_workflow: bool = False):
        """
        Inicializa el ejecutor.
        
        Args:
            workflow: Workflow a ejecutar
            log_dir: Directorio para guardar logs
            enable_recording: Si es True, graba la pantalla durante la ejecución
            is_sub_workflow: Indica si es un flujo hijo llamado por otro workflow
        """
        self.workflow = workflow
        self.enable_recording = enable_recording
        self.is_sub_workflow = is_sub_workflow
        self.screen_recorder = None

        # Create a unique log filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Simple sanitization
        safe_name = "".join([c for c in workflow.name if c.isalnum() or c in (' ', '-', '_')]).strip().replace(' ', '_')
        log_filename = f"wf_{safe_name}_{timestamp}.log"

        # Ensure log_dir is not empty/None
        if not log_dir:
            log_dir = "logs"

        log_path = os.path.join(log_dir, log_filename)

        self.logger = WorkflowLogger(log_path)
        self.context: Dict[str, Any] = workflow.variables.copy()
        self.should_stop = False
        self._external_stop = False  # True solo cuando stop() es llamado por el usuario
        self.stop_after_iteration = False  # True para detener loop tras caso actual
        self.is_in_loop = False  # True mientras se ejecuta activamente un LoopNode
        self.no_records_found = False  # True cuando un script o sub-workflow termina con código 2 (sin registros)
        self.active_process = None
        self.nested_executor = None

        # Control de pausa/reanudación
        self.is_paused = False
        self.pause_event = threading.Event()
        self.pause_event.set()

        self.logger.log(f"🚀 Workflow inicializado: {workflow.name}")
        self.logger.log(f"   Variables iniciales: {self.context}")

    def execute(self) -> Dict[str, Any]:
        """
        Ejecuta el workflow completo.
        
        Returns:
            Diccionario con el resultado de la ejecución:
            {
                "status": "success" | "error" | "stopped",
                "context": dict con variables finales,
                "logs": list de logs,
                "error": mensaje de error (si hubo),
                "video_path": ruta del video guardado si hubo error
            }
        """
        recorder = None
        keep_awake_cm = None
        if not self.is_sub_workflow:
            try:
                from utils.keep_alive import keep_system_awake
                keep_awake_cm = keep_system_awake(keep_display=True)
                keep_awake_cm.__enter__()
            except Exception as ka_e:
                self.logger.log(f"⚠️ No se pudo inicializar Keep-Alive: {ka_e}")

            # ── Validación Pre-Flujo: Servicios Críticos (MySQL y Ollama) ──
            try:
                from utils.mysql_auto_starter import ensure_mysql_running
                ensure_mysql_running()
            except Exception as e_mysql:
                self.logger.log(f"⚠️ [Validación Pre-Flujo] Error verificando MySQL: {e_mysql}")

            try:
                from utils.ollama_auto_starter import ensure_ollama_running, verify_model_available
                ollama_ok, ollama_msg = ensure_ollama_running(max_wait_seconds=6)
                if ollama_ok:
                    has_model = verify_model_available("qwen2.5:3b")
                    modelo_str = "qwen2.5:3b" if has_model else "alerta: modelo no descargado"
                    self.logger.log(f"🧠 [Validación Pre-Flujo] Ollama local ACTIVO ({modelo_str}) en GPU GTX 1070: {ollama_msg}")
                else:
                    self.logger.log(f"⚠️ [Validación Pre-Flujo] Ollama no disponible: {ollama_msg}. Flujo operará con fallback a LLM Cloud.")
            except Exception as e_ollama:
                self.logger.log(f"⚠️ [Validación Pre-Flujo] Error validando Ollama: {e_ollama}")

        recorder = None
        if self.enable_recording and not self.is_sub_workflow:
            try:
                from utils.screen_recorder import ScreenRecorder
                recorder = ScreenRecorder(fps=6, max_width=1280, format="mp4")
                if recorder.start():
                    self.screen_recorder = recorder
                    self.logger.log("🎥 Grabación de pantalla optimizada (6 FPS, 720p) iniciada en segundo plano")
                else:
                    recorder = None
            except Exception as rec_e:
                recorder = None
                self.logger.log(f"⚠️ No se pudo iniciar el grabador de pantalla: {rec_e}")

        try:
            self.logger.log("=" * 60)
            self.logger.log(f"▶️ Iniciando ejecución: {self.workflow.name}")
            self.logger.log("=" * 60)

            # Registrar actividad para el notificador horario
            try:
                try:
                    from utils.notificador_resumen import registrar_ejecucion_workflow
                except ImportError:
                    from rpa_framework.utils.notificador_resumen import registrar_ejecucion_workflow
                registrar_ejecucion_workflow(self.workflow.name, status="running")
            except Exception:
                pass

            # Verificar vigencia de validación de modelos LLM (< 6 horas)
            if not self.is_sub_workflow:
                try:
                    try:
                        from utils.llm_auto_manager import check_and_refresh_llm_cache
                    except ImportError:
                        from rpa_framework.utils.llm_auto_manager import check_and_refresh_llm_cache

                    self.logger.log("🤖 Verificando vigencia de validación LLM (< 6h)...")
                    llm_res = check_and_refresh_llm_cache(max_age_hours=6.0, log_callback=self.logger.log)
                    if llm_res.get("status") == "Vigente":
                        self.logger.log(f"✅ Modelos LLM validados recientemente ({llm_res.get('elapsed_minutes', 0):.1f} min atrás < 6h).")
                    else:
                        self.logger.log(f"🔄 Validación/reemplazo de modelos LLM finalizada: {llm_res.get('status')}")
                except Exception as llm_err:
                    self.logger.log(f"⚠️ Error durante verificación de vigencia LLM: {llm_err}")

            # Verificar y desactivar Bloq Mayús si está activo
            try:
                from utils.keyboard_utils import ensure_capslock_off
                ensure_capslock_off(self.logger.log)
            except Exception as cap_e:
                self.logger.log(f"⚠️ No se pudo verificar estado de Bloq Mayús: {cap_e}")

            # Registrar resolución de pantalla
            try:
                screen_res = get_screen_resolution()
                self.context["screen_resolution"] = screen_res
                self.logger.log(f"🖥️ Resolución de pantalla detectada: {screen_res}")
                self._sync_screen_resolution_to_db(screen_res)
            except Exception as scr_e:
                self.logger.log(f"⚠️ No se pudo determinar/sincronizar resolución de pantalla: {scr_e}")

            # Obtener nodo inicial
            current_node = self.workflow.get_start_node()

            if not current_node:
                raise ValueError("No se encontró nodo de inicio")

            # Ejecutar nodos secuencialmente
            while current_node and not self.should_stop:
                self.logger.log(f"\n📍 Nodo actual: {current_node.label} ({current_node.type.value})")

                # Ejecutar nodo y obtener siguiente
                next_node_id = self._execute_node(current_node)

                # Asegurar sincronización de resolución si el nodo inicializó el registro
                if "screen_resolution" in self.context:
                    self._sync_screen_resolution_to_db(self.context["screen_resolution"])

                if not next_node_id:
                    self.logger.log("✅ Fin del workflow (no hay más nodos)")
                    break

                # Obtener siguiente nodo
                current_node = self.workflow.get_node(next_node_id)

                if not current_node:
                    self.logger.log(f"⚠️ Nodo no encontrado: {next_node_id}")
                    break

            # Resultado final
            if self.no_records_found:
                status = "no_records"
            elif self.should_stop:
                status = "stopped"
            else:
                status = "success"

            self.logger.log("=" * 60)
            self.logger.log(f"✅ Ejecución completada: {status}")
            self.logger.log(f"   Variables finales: {self.context}")
            self.logger.log("=" * 60)

            # Si terminó correctamente, fue detenido, o finalizó sin registros, descartar grabación
            if self.screen_recorder:
                self.screen_recorder.discard()
                self.logger.log("🗑️ Grabación de pantalla descartada (workflow exitoso/detenido/sin registros)")
                self.screen_recorder = None

            # Registrar finalización para el notificador horario
            try:
                try:
                    from utils.notificador_resumen import registrar_ejecucion_workflow
                except ImportError:
                    from rpa_framework.utils.notificador_resumen import registrar_ejecucion_workflow
                registrar_ejecucion_workflow(self.workflow.name, status=status)
            except Exception:
                pass

            return {
                "status": status,
                "context": self.context,
                "logs": self.logger.get_logs(),
                "error": None
            }

        except Exception as e:
            # Registrar estado en caso de error o parada para el notificador horario
            try:
                try:
                    from utils.notificador_resumen import registrar_ejecucion_workflow
                except ImportError:
                    from rpa_framework.utils.notificador_resumen import registrar_ejecucion_workflow
                registrar_ejecucion_workflow(self.workflow.name, status="stopped" if self.should_stop else "error")
            except Exception:
                pass

            if self.should_stop:
                self.logger.log("⏹️ Workflow interrumpido por solicitud de parada del usuario.")
                if self.screen_recorder:
                    self.screen_recorder.discard()
                    self.screen_recorder = None
                return {
                    "status": "stopped",
                    "context": self.context,
                    "logs": self.logger.get_logs(),
                    "error": None
                }

            error_msg = f"Error en ejecución: {str(e)}"
            self.logger.log(f"❌ {error_msg}")

            saved_video_path = self._save_and_send_error_video(str(e))

            return {
                "status": "error",
                "context": self.context,
                "logs": self.logger.get_logs(),
                "error": error_msg,
                "video_path": saved_video_path
            }
        finally:
            if keep_awake_cm:
                try:
                    keep_awake_cm.__exit__(None, None, None)
                except Exception:
                    pass

    def pause(self):
        """Pausa la ejecución del workflow."""
        self.is_paused = True
        if hasattr(self, 'pause_event') and self.pause_event:
            self.pause_event.clear()
        self.logger.log("⏸️ Workflow pausado")

    def resume(self):
        """Reanuda la ejecución del workflow si estaba pausado."""
        self.is_paused = False
        if hasattr(self, 'pause_event') and self.pause_event:
            self.pause_event.set()
        self.logger.log("▶️ Workflow reanudado")

    def stop_after_current_case(self):
        """Solicita detener el bucle de manera segura una vez que finalice el caso en curso."""
        self.stop_after_iteration = True
        self.logger.log("⏳ Solicitud recibida: se detendrá el bucle al finalizar el caso actual.")
        if getattr(self, 'nested_executor', None):
            try:
                self.nested_executor.stop_after_iteration = True
            except Exception:
                pass
        if hasattr(self, 'pause_event') and not self.pause_event.is_set():
            self.pause_event.set()

    def is_loop_workflow(self) -> bool:
        """Determina si el workflow actual es o contiene un bucle (LoopNode)."""
        if getattr(self, 'is_in_loop', False):
            return True
        if self.nested_executor and getattr(self.nested_executor, 'is_loop_workflow', lambda: False)():
            return True
        if self.workflow and getattr(self.workflow, 'nodes', None):
            for node in self.workflow.nodes:
                if getattr(node, 'type', None) in ('loop', NodeType.LOOP) or str(getattr(node, 'type', '')).lower() == 'loop':
                    return True
        if self.workflow and "loop" in getattr(self.workflow, 'name', '').lower():
            return True
        return False

    def stop(self):
        """Detiene la ejecución del workflow"""
        self.should_stop = True
        self._external_stop = True  # Marcar como stop externo (usuario/Telegram)
        self.is_paused = False
        if hasattr(self, 'pause_event') and self.pause_event:
            self.pause_event.set()
        self.logger.log("⏹️ Deteniendo workflow...")

        if self.screen_recorder:
            try:
                self.screen_recorder.stop()
                self.screen_recorder = None
            except Exception:
                pass

        # 1. Detener executor anidado si existe
        if self.nested_executor:
            self.logger.log("   Propagando stop a workflow anidado...")
            self.nested_executor.stop()

        # 2. Detener proceso activo si existe
        if self.active_process:
            try:
                pid = self.active_process.pid
                self.logger.log(f"   Terminando árbol de procesos activo (PID: {pid})...")

                # 2.1. En Windows, forzar la terminación del árbol de procesos completo
                if sys.platform == "win32":
                    try:
                        subprocess.run(
                            ["taskkill", "/F", "/T", "/PID", str(pid)],
                            capture_output=True,
                            timeout=3
                        )
                    except Exception as tk_e:
                        self.logger.log(f"   ⚠️ taskkill warning: {tk_e}")

                # 2.2. psutil para garantizar terminación de hijos
                try:
                    import psutil
                    parent_proc = psutil.Process(pid)
                    for child in parent_proc.children(recursive=True):
                        try:
                            child.kill()
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                    try:
                        parent_proc.kill()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                except Exception:
                    pass

                # 2.3. Fallback directo sobre objeto Popen
                try:
                    self.active_process.kill()
                except Exception:
                    pass
                self.logger.log(f"   ✅ Proceso {pid} y subprocesos terminados.")
            except Exception as e:
                self.logger.log(f"⚠️ Error al detener proceso: {e}")
            finally:
                self.active_process = None

    def _execute_node(self, node: Node) -> Optional[str]:
        """
        Ejecuta un nodo individual y devuelve el ID del siguiente nodo.
        """
        # Skip disabled nodes
        if not node.enabled:
            self.logger.log(f"🚫 Nodo deshabilitado: {node.label} (saltando)", "WARNING")
            return self.workflow.get_next_node(node.id)

        # Skip annotation nodes (they're just for documentation)
        if node.type == NodeType.ANNOTATION:
            self.logger.log(f"📝 Anotación: {node.label} (saltando)")
            return self.workflow.get_next_node(node.id)

        if node.type == NodeType.ACTION:
            return self._execute_action(node)
        elif node.type == NodeType.DECISION:
            return self._execute_decision(node)
        elif node.type == NodeType.LOOP:
            return self._execute_loop(node)
        elif node.type == NodeType.DATABASE:
            return self._execute_database(node)
        elif node.type == NodeType.DELAY:
            return self._execute_delay(node)
        elif node.type == NodeType.WORKFLOW:
            return self._execute_workflow(node)
        elif node.type == NodeType.END:
            self.logger.log("⏹️ Nodo Final alcanzado.")
            return None
        else:
            # Nodos START u otros: solo continuar al siguiente
            return self.workflow.get_next_node(node.id)
