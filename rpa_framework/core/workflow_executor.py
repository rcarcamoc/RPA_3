"""
Ejecutor de workflows para el RPA Framework 3.

Este módulo contiene la lógica para ejecutar workflows secuencialmente,
manejar control de flujo (IF/ELSE, LOOP) y gestionar variables compartidas.
"""

import subprocess
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from core.models import Workflow, Node, NodeType, ActionNode, DecisionNode, LoopNode, WorkflowNode
from core.logger import WorkflowLogger
from utils.telegram_manager import enviar_alerta_todos
import mysql.connector
from mysql.connector import Error as MySQLError
try:
    import win32com.client
    import pythoncom
except ImportError:
    pass

try:
    from utils.screen_utils import get_screen_resolution
except ImportError:
    try:
        from rpa_framework.utils.screen_utils import get_screen_resolution
    except ImportError:
        def get_screen_resolution():
            return "1920x1080"

def get_python_exe() -> str:
    """Retorna la ruta al ejecutable python (preferiendo pythonw.exe para evitar que aparezcan consolas negras)."""
    exe = sys.executable
    if "pythonw.exe" in exe.lower():
        return exe
    cand = exe.lower().replace("python.exe", "pythonw.exe")
    if os.path.exists(cand):
        return cand
    return exe

def _get_silent_process_flags():
    """Retorna creationflags y startupinfo configurados para ocultar totalmente consolas de Windows."""
    creationflags = 0
    startupinfo = None
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 0  # SW_HIDE
    return creationflags, startupinfo


class WorkflowExecutor:
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
        if not log_dir: log_dir = "logs"
            
        log_path = os.path.join(log_dir, log_filename)
        
        self.logger = WorkflowLogger(log_path)
        self.context: Dict[str, Any] = workflow.variables.copy()
        self.should_stop = False
        self._external_stop = False  # True solo cuando stop() es llamado por el usuario
        self.active_process = None
        self.nested_executor = None
        
        self.logger.log(f"🚀 Workflow inicializado: {workflow.name}")
        self.logger.log(f"   Variables iniciales: {self.context}")
        
    def _get_subprocess_env(self) -> Dict[str, str]:
        """Prepara el entorno para ejecutar subprocesses de forma robusta"""
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        
        # Agregar project_root y rpa_framework a PYTHONPATH para asegurar importaciones robustas
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent.resolve()
        rpa_framework_root = project_root / "rpa_framework"
        
        existing_pythonpath = env.get("PYTHONPATH", "")
        separator = ";" if os.name == 'nt' else ":"
        if existing_pythonpath:
            env["PYTHONPATH"] = f"{project_root}{separator}{rpa_framework_root}{separator}{existing_pythonpath}"
        else:
            env["PYTHONPATH"] = f"{project_root}{separator}{rpa_framework_root}"
            
        for key, value in self.context.items():
            env[f"VAR_{key}"] = str(value)
            
        return env

    def _sync_screen_resolution_to_db(self, resolution: str):
        """Sincroniza la resolución de pantalla con el registro 'En Proceso' en ris.registro_acciones si no está seteada."""
        try:
            conn = mysql.connector.connect(host='localhost', user='root', password='', database='ris', connect_timeout=2)
            cur = conn.cursor()
            cur.execute("""
                UPDATE ris.registro_acciones 
                SET resolucion_pantalla = %s 
                WHERE estado = 'En Proceso' AND (resolucion_pantalla IS NULL OR resolucion_pantalla = '')
            """, (resolution,))
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            pass
    
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
            status = "stopped" if self.should_stop else "success"
            
            self.logger.log("=" * 60)
            self.logger.log(f"✅ Ejecución completada: {status}")
            self.logger.log(f"   Variables finales: {self.context}")
            self.logger.log("=" * 60)
            
            # Si terminó correctamente o fue detenido, descartar grabación
            if recorder:
                recorder.discard()
                self.logger.log("🗑️ Grabación de pantalla descartada (workflow exitoso/detenido)")
                self.screen_recorder = None

            return {
                "status": status,
                "context": self.context,
                "logs": self.logger.get_logs(),
                "error": None
            }
            
        except Exception as e:
            if self.should_stop:
                self.logger.log("⏹️ Workflow interrumpido por solicitud de parada del usuario.")
                if recorder:
                    recorder.discard()
                    self.screen_recorder = None
                return {
                    "status": "stopped",
                    "context": self.context,
                    "logs": self.logger.get_logs(),
                    "error": None
                }

            error_msg = f"Error en ejecución: {str(e)}"
            self.logger.log(f"❌ {error_msg}")
            
            saved_video_path = None
            if recorder:
                try:
                    from utils.paths import get_error_recording_path
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    safe_name = "".join([c for c in self.workflow.name if c.isalnum() or c in (' ', '-', '_')]).strip().replace(' ', '_')
                    video_filename = f"error_{safe_name}_{timestamp}.mp4"
                    dest_path = get_error_recording_path(video_filename)
                    
                    saved_video_path = recorder.save(str(dest_path))
                    self.screen_recorder = None
                    if saved_video_path:
                        self.logger.log(f"💾 Grabación de pantalla de error guardada en: {saved_video_path}")
                        
                        try:
                            from utils.telegram_manager import enviar_video_todos
                            screen_res = self.context.get("screen_resolution") or get_screen_resolution()
                            caption = f"❌ <b>Error en Workflow: {self.workflow.name}</b>\n🖥️ <b>Resolución:</b> <code>{screen_res}</code>\n<b>Motivo:</b> {str(e)[:250]}"
                            enviar_video_todos(saved_video_path, caption=caption)
                            self.logger.log("📱 Grabación de video del error enviada a Telegram")
                        except Exception as tel_e:
                            self.logger.log(f"⚠️ Error al enviar video por Telegram: {tel_e}")
                except Exception as rec_err:
                    self.logger.log(f"⚠️ Error guardando grabación de pantalla: {rec_err}")

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
    
    def stop(self):
        """Detiene la ejecución del workflow"""
        self.should_stop = True
        self._external_stop = True  # Marcar como stop externo (usuario/Telegram)
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
            
    def _execute_delay(self, node) -> Optional[str]:
        import time
        from core.delay_node import DelayNode
        if isinstance(node, DelayNode):
            sec = node.delay_seconds
            self.logger.log(f"⏳ Pausando por {sec} segundos...")
            end_time = time.time() + sec
            while time.time() < end_time and not self.should_stop:
                time.sleep(0.2)
            if self.should_stop:
                self.logger.log("⏹️ Pausa interrumpida por detención de workflow.")
                return None
        return self.workflow.get_next_node(node.id)
    
    def _execute_action(self, node: ActionNode) -> Optional[str]:
        """Ejecuta un nodo de acción (script Python o comando)"""
        
        # 1. Ejecución de Comando de Sistema
        if node.command:
             # MEJORA: Detectar comando de minimizar todo y ejecutarlo nativamente para evitar conflictos de proceso
             if 'minimizeall()' in node.command.lower():
                 self.logger.log("💻 Ejecutando 'Minimizar Todo' nativamente...")
                 try:
                     # Asegurar que COM esté inicializado en este hilo (aunque el worker lo haga, doble check no duele)
                     if 'pythoncom' in globals():
                        pythoncom.CoInitialize()
                     
                     if 'win32com' in sys.modules or 'win32com' in globals():
                        shell = win32com.client.Dispatch("Shell.Application")
                        shell.MinimizeAll()
                        self.logger.log("✅ Escritorio mostrado (MinimizeAll OK)")
                        return self.workflow.get_next_node(node.id)
                     else:
                        raise ImportError("win32com not available")
                 except Exception as e:
                     self.logger.log(f"⚠️ Error en MinimizeAll nativo: {e}. Intentando vía subprocess...", "WARNING")
                     # Si falla, continuará con la ejecución normal de subprocess
             
             self.logger.log(f"💻 Ejecutando comando: {node.command}")
             try:
                # Preparar entorno
                env = self._get_subprocess_env()
                
                # MEJORA: Asegurar que los pipes se cierren correctamente con un bloque try-finally robusto
                # Usamos shell=True por compatibilidad con comandos complejos de Windows
                full_output = []
                process = None
                creationflags, startupinfo = _get_silent_process_flags()
                try:
                    process = subprocess.Popen(
                        node.command,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding='utf-8',
                        env=env,
                        bufsize=1,
                        universal_newlines=True,
                        errors='replace',
                        creationflags=creationflags,
                        startupinfo=startupinfo
                    )
                    self.active_process = process
                    
                    # Leer salida en tiempo real
                    while True:
                        line = process.stdout.readline()
                        if not line and process.poll() is not None:
                            break
                        if line:
                            clean_line = line.strip()
                            if clean_line:
                                self.logger.log(f"   [CMD] {clean_line}")
                                full_output.append(clean_line)
                    
                    returncode = process.wait(timeout=10)
                finally:
                    # Garantizar cierre de pipes para evitar fugas de handles (causa de crashes en subsiguientes runs)
                    if process:
                        if process.stdout: process.stdout.close()
                        if process.stderr: process.stderr.close()
                    self.active_process = None
                
                if self.should_stop:
                    self.logger.log("⏹️ Comando interrumpido por detención de workflow.")
                    return None

                if returncode == 0:
                     self.logger.log(f"✅ Comando ejecutado exitosamente")
                     if node.output_variable:
                        output_str = "\n".join(full_output).strip()
                        self.context[node.output_variable] = output_str
                elif returncode == 2:
                     self.logger.log(f"ℹ️ Comando finalizado (código 2): Sin registros. Deteniendo flujo.")
                     self.should_stop = True
                     return None
                else:
                     self.logger.log(f"❌ Error en comando (código {returncode})")
                     try:
                         ultimo_error = "\n".join(full_output[-3:]) if full_output else "Sin salida devuelta."
                         enviar_alerta_todos(f"❌ <b>Error en Comando</b>\nNodo: {node.label}\nComando falló con código {returncode}\nDetalle:\n<code>{ultimo_error}</code>")
                     except Exception as tel_e:
                         self.logger.log(f"⚠️ Error enviando alerta: {tel_e}")

                     if getattr(node, 'on_error', 'stop') == 'stop':
                         raise RuntimeError(f"Comando falló con código {returncode}")
                     
             except Exception as e:
                 self.logger.log(f"❌ Excepción ejecutando comando: {e}")
                 try:
                     enviar_alerta_todos(f"❌ <b>Excepción en Comando</b>\nNodo: {node.label}\nError: <code>{str(e)}</code>")
                 except Exception as tel_e:
                     self.logger.log(f"⚠️ Error enviando alerta: {tel_e}")
                 
                 if getattr(node, 'on_error', 'stop') == 'stop':
                     raise e
             
             return self.workflow.get_next_node(node.id)

        # 2. Ejecución de Script Python
        if not node.script:
            self.logger.log("⚠️ Nodo sin script ni comando, saltando")
            return self.workflow.get_next_node(node.id)
        
        self.logger.log(f"🐍 Ejecutando script: {node.script}")
        
        try:
            env = self._get_subprocess_env()
            
            # Resolver ruta del script
            script_path = Path(node.script)
            
            # Si es absoluta y existe, no hay nada que resolver
            if script_path.is_absolute() and script_path.exists():
                pass
            else:
                # Intentar buscar en ubicaciones relativas
                # Primero, si ya tiene un prefijo de subcarpeta (ej: "ui/Abre_pacs.py")
                possible_roots = [
                    Path.cwd(),
                    Path("recordings"),
                    Path("rpa_framework/recordings"),
                    Path("../recordings"), # Por si acaso se ejecuta desde rpa_framework/
                    Path("recordings/web"),
                    Path("recordings/ui"),
                    Path("recordings/ocr")
                ]
                
                found = False
                for root in possible_roots:
                    test_path = (root / script_path).resolve()
                    if test_path.exists():
                        script_path = test_path
                        found = True
                        break
                
                if not found:
                    # Búsqueda desesperada: si solo es el nombre del archivo, buscarlo recursivamente
                    self.logger.log(f"🔍 Buscando '{script_path}' en recordings recursivamente...")
                    potential_recordings = [Path("recordings"), Path("rpa_framework/recordings")]
                    for rec_dir in potential_recordings:
                        if rec_dir.exists():
                             matches = list(rec_dir.rglob(script_path.name))
                             if matches:
                                 script_path = matches[0].resolve()
                                 found = True
                                 self.logger.log(f"   ✨ Encontrado en: {script_path}")
                                 break
            
            if not script_path.exists():
                 self.logger.log(f"❌ Script no encontrado: {script_path}")
                 return self.workflow.get_next_node(node.id)
            
            # Asegurar ruta absoluta
            script_path = script_path.resolve()
            self.logger.log(f"   Ruta absoluta: {script_path}")

            # Ejecutar script con Popen para streaming
            cmd = [get_python_exe(), str(script_path)]
            self.logger.log(f"   Comando a ejecutar: {cmd}")
            
            # Use root directory (parent of rpa_framework) as CWD if possible
            current_cwd = Path.cwd()
            if current_cwd.name == "rpa_framework":
                exec_cwd = current_cwd.parent
            else:
                exec_cwd = current_cwd

            creationflags, startupinfo = _get_silent_process_flags()
            process = None
            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    env=env,
                    cwd=str(exec_cwd),
                    bufsize=1,
                    universal_newlines=True,
                    creationflags=creationflags,
                    startupinfo=startupinfo
                )
                self.active_process = process
                
                # Leer salida en tiempo real
                full_stdout = []
                while True:
                    line = process.stdout.readline()
                    if not line:
                        if process.poll() is not None:
                            break
                        continue
                    
                    clean_line = line.strip()
                    if clean_line:
                        self.logger.log(f"   [PY] {clean_line}")
                        full_stdout.append(clean_line)
                
                returncode = process.poll()
            finally:
                if process:
                    try:
                        if process.stdout: process.stdout.close()
                        if process.stderr: process.stderr.close()
                    except Exception:
                        pass
                self.active_process = None
            
            if self.should_stop:
                self.logger.log("⏹️ Script interrumpido por detención de workflow.")
                return None
            
            if returncode == 0:
                self.logger.log(f"✅ Script ejecutado exitosamente")
                
                # Opción 1: Guardar salida completa en variable si se definió explícitamente
                if node.output_variable:
                    output_str = "".join(full_stdout).strip()
                    self.context[node.output_variable] = output_str
                    self.logger.log(f"   Salida guardada en '{node.output_variable}': {output_str[:50]}...")
                
                # Opción 2: Intentar parsear líneas JSON para actualizaciones implícitas de contexto
                # Esto permite que scripts actualicen múltiples variables sin configurar output_variable
                for line in reversed(full_stdout):
                    try:
                        output_data = json.loads(line)
                        if isinstance(output_data, dict):
                            self.context.update(output_data)
                            self.logger.log(f"   Variables actualizadas (JSON): {list(output_data.keys())}")
                            # Si encontramos un JSON válido al final, asumimos que es el resultado estructurado
                            break
                    except json.JSONDecodeError:
                        continue
            elif returncode == 2:
                self.logger.log(f"ℹ️ Script finalizado (código 2): Sin registros para trabajar. Deteniendo flujo.")
                self.should_stop = True
                return None
            else:
                self.logger.log(f"❌ Error en script (código {returncode})")
                
                try:
                    ultimo_log = "\n".join(full_stdout[-3:]) if full_stdout else "Sin salida devuelta."
                    # Respaldo: si el script crashó antes de su error_handler, asegurar notificación
                    try:
                        conn_chk = mysql.connector.connect(host='localhost', user='root', password='', database='ris', connect_timeout=3)
                        cur_chk = conn_chk.cursor(dictionary=True)
                        cur_chk.execute("SELECT id, estado, estado_notificacion FROM ris.registro_acciones WHERE estado = 'En Proceso' ORDER BY id DESC LIMIT 1")
                        rec_chk = cur_chk.fetchone()
                        if rec_chk and rec_chk.get('estado_notificacion') is None:
                            rec_id = rec_chk['id']
                            cur_chk.execute("UPDATE ris.registro_acciones SET estado = 'Error', observacion = %s WHERE id = %s", (f"[{node.label}] Error código {returncode}: {ultimo_log[:300]}", rec_id))
                            conn_chk.commit()
                            enviar_alerta_todos(f"🚨 <b>ERROR en {node.label}</b>\n\n📋 <b>Problema:</b>\nScript terminó con código de error {returncode}.\n\n<code>{ultimo_log}</code>", record_id=rec_id)
                        cur_chk.close()
                        conn_chk.close()
                    except Exception as chk_e:
                        self.logger.log(f"⚠️ Error en verificación de fallback: {chk_e}")
                except Exception as tel_e:
                    self.logger.log(f"⚠️ Error al procesar alerta de respaldo: {tel_e}")
                
                if getattr(node, 'on_error', 'stop') == 'stop':
                    raise RuntimeError(f"El asistente no pudo completar la tarea en la fase '{node.label}'.")
            
        except Exception as e:
            self.logger.log(f"❌ Error: {str(e)}")
            
            # Igual omitimos alerta si el nivel superior lo va a atrapar
            # enviar_alerta_todos(f"❌ <b>Excepción en Script</b>\nNodo: {node.label}\nError: <code>{str(e)}</code>")
                
            if getattr(node, 'on_error', 'stop') == 'stop':
                raise RuntimeError(f"Falla inesperada en la fase '{node.label}': {str(e)}")
        
        return self.workflow.get_next_node(node.id)
    
    def _execute_decision(self, node: DecisionNode) -> Optional[str]:
        """Ejecuta un nodo de decisión (IF/ELSE)"""
        if not node.condition:
            self.logger.log("⚠️ Decisión sin condición, tomando rama TRUE")
            return node.true_path or self.workflow.get_next_node(node.id)
        
        self.logger.log(f"🔀 Evaluando condición: {node.condition}")
        
        result = self._eval_condition(node.condition)
        
        if result:
            self.logger.log("   ✅ Condición TRUE")
            return node.true_path or self.workflow.get_next_node(node.id)
        else:
            self.logger.log("   ❌ Condición FALSE")
            return node.false_path or self.workflow.get_next_node(node.id)
    
    def _execute_loop(self, node: LoopNode) -> Optional[str]:
        """Ejecuta un nodo de loop con AISLAMIENTO TOTAL.

        Modos disponibles:
          - count    : N iteraciones fijas
          - list     : Iterar sobre una lista/variable del contexto
          - while    : Mientras condición sea verdadera
          - timed    : Ejecutar durante N horas y luego detenerse
          - infinite : Ejecutar indefinidamente hasta Stop manual

        El loop NUNCA se detiene por errores internos, excepciones ni
        señales should_stop generadas dentro de una iteración.
        Solo se respeta el Stop externo del usuario.
        """
        import time

        loop_type = getattr(node, 'loop_type', 'count')
        self.logger.log(f"🔁 Iniciando loop ({loop_type}) — Aislamiento total activado")

        # ── 1. Configurar modo ──────────────────────────────────────────
        iterator   = []
        is_while   = False
        is_timed   = False
        is_infinite = False
        deadline   = None

        if loop_type == 'count':
            iterations = self._get_loop_count(node.iterations)
            iterator = range(iterations)
            self.logger.log(f"   Modo: {iterations} iteraciones fijas")

        elif loop_type == 'list':
            var_name = node.iterable
            val = self.context.get(var_name, [])
            if isinstance(val, (list, tuple)):
                iterator = val
                self.logger.log(f"   Modo: Iterar lista '{var_name}' ({len(val)} elementos)")
            elif isinstance(val, dict):
                iterator = list(val.items())
                self.logger.log(f"   Modo: Iterar dict '{var_name}' ({len(val)} elementos)")
            else:
                self.logger.log(f"⚠️ Variable '{var_name}' no es iterable: {type(val)}")
                iterator = []

        elif loop_type == 'while':
            is_while = True
            self.logger.log(f"   Modo: While — condición '{node.condition}'")

        elif loop_type == 'timed':
            is_timed = True
            hours = float(getattr(node, 'duration_hours', 1.0))
            deadline = time.time() + (hours * 3600)
            h_str = f"{hours:g} hora{'s' if hours != 1 else ''}"
            self.logger.log(f"   Modo: Programado — durará {h_str}")

        elif loop_type == 'infinite':
            is_infinite = True
            self.logger.log("   Modo: Infinito — solo se detiene con Stop manual")

        # ── 2. Ejecutar Loop ────────────────────────────────────────────
        idx = 0
        MAX_ITER = 100_000  # Safety break para while (~83 días a 1 iter/min)

        while True:
            # Solo se respeta el stop EXTERNO (botón Stop del usuario).
            # Se verifica ANTES de la iteración, nunca durante.
            if self.should_stop:
                self.logger.log("⏹️ Loop detenido por señal externa del usuario.")
                break

            # ── Control de flujo según modo ──
            current_item = None

            if is_timed:
                remaining = deadline - time.time()
                if remaining <= 0:
                    hours = float(getattr(node, 'duration_hours', 1.0))
                    self.logger.log(f"⏰ Tiempo completado ({hours:g}h). Loop finalizado.")
                    break
                mins_left = int(remaining / 60)
                secs_left = int(remaining % 60)
                self.logger.log(f"   ⏱️ Tiempo restante: {mins_left}m {secs_left}s")
                current_item = idx

            elif is_infinite:
                current_item = idx

            elif is_while:
                if idx >= MAX_ITER:
                    self.logger.log(f"⚠️ Límite de seguridad alcanzado ({MAX_ITER:,} iteraciones)")
                    break
                try:
                    condition_result = self._eval_condition(node.condition)
                except Exception as cond_err:
                    self.logger.log(f"⚠️ Error evaluando condición: {cond_err} — asumiendo True")
                    condition_result = True
                if not condition_result:
                    break
                current_item = idx

            else:
                # count / list
                if idx >= len(iterator):
                    break
                current_item = iterator[idx]

            self.logger.log(f"   🔄 Iteración {idx + 1}")

            # Actualizar variables de contexto del loop
            self.context["_loop_index"] = idx
            self.context[node.loop_var] = current_item

            # ── AISLAMIENTO: snapshot antes de ejecutar ──
            snapshot_should_stop = self.should_stop

            try:
                if hasattr(node, 'workflow_path') and node.workflow_path:
                    self._run_workflow_internal(node.workflow_path)
                elif node.script:
                    self._run_script_internal(node)

            except Exception as e:
                if self.should_stop:
                    self.logger.log("⏹️ Iteración de loop interrumpida por detención externa.")
                    break
                self.logger.log(f"   ❌ Error en iteración {idx + 1} (ignorado, loop continúa): {e}")
                delay = getattr(node, 'error_delay', 0)
                if delay > 0:
                    self.logger.log(f"   ⏳ Esperando {delay}s antes de reintentar...")
                    end_d = time.time() + delay
                    while time.time() < end_d and not self.should_stop:
                        time.sleep(0.2)
                    if self.should_stop:
                        break

            finally:
                # Si algo interno puso should_stop=True, lo revertimos
                # PERO si fue un stop externo (usuario/Telegram), lo respetamos
                if self.should_stop and not snapshot_should_stop:
                    if self._external_stop:
                        self.logger.log("⏹️ Stop externo detectado dentro del loop. Respetando detención del usuario.")
                    else:
                        self.logger.log("🔄 Loop aislado: señal de parada interna descartada, reiniciando...")
                        self.should_stop = False

            if self.should_stop:
                break

            idx += 1

        self.logger.log(f"✅ Loop finalizado ({idx} iteraciones ejecutadas)")
        return self.workflow.get_next_node(node.id)

    def _run_workflow_internal(self, wf_path: str):
        """Ejecuta un workflow hijo reutilizando lógica (sin retorno de nodo)"""
        # Resolver ruta (copiado de _execute_workflow)
        path_obj = Path(wf_path)
        if not path_obj.is_absolute():
            base_dir = Path("rpa_framework/workflows")
            if not base_dir.exists(): base_dir = Path("workflows")
            
            candidate = base_dir / wf_path
            if not candidate.exists() and not candidate.suffix:
                candidate = candidate.with_suffix(".json")
            if candidate.exists(): path_obj = candidate
            else: path_obj = Path(wf_path).resolve()

        if not path_obj.exists():
             raise FileNotFoundError(f"Workflow loop no encontrado: {path_obj}")
             
        # Cargar nested workflow
        nested_wf = Workflow.from_json(str(path_obj))
        nested_wf.variables.update(self.context)
        
        # Executor
        self.nested_executor = WorkflowExecutor(nested_wf, self.logger.log_dir, is_sub_workflow=True)
        
        # Patch logs
        original_log = self.nested_executor.logger.log
        def bridged_log(msg, level="INFO"):
            prefix = f"   [LOOP-WF:{nested_wf.name}]"
            self.logger.log(f"{prefix} {msg}", level)
        self.nested_executor.logger.log = bridged_log
        
        self.logger.log(f"   ▶️ Loop Running Workflow: {nested_wf.name}")
        try:
            result = self.nested_executor.execute()
        finally:
            self.nested_executor = None
        
        status = result.get("status") if isinstance(result, dict) else "unknown"
        if status == "stopped" or self.should_stop:
            self.logger.log("   Workflow anidado detenido por usuario.")
            self.should_stop = True
            self._external_stop = True
        elif status == "error":
            if self.should_stop:
                self.logger.log("   Workflow anidado detenido por usuario.")
            else:
                raise RuntimeError(f"Fallo en workflow de loop: {result.get('error')}")
        else:
            self.context.update(result.get("context", {}))

    def _run_script_internal(self, node):
        """Helper para ejecutar script python del loop"""
        env = self._get_subprocess_env()
        
        # Pasamos variables como JSON string también para estructuras complejas
        # O confiamos en env vars simples. 
        # Para listas/dicts complejos, el script debería leer un JSON temporal o similar si fuera robusto.
        # Por ahora mantenemos compatibilidad simple.
        
        current_cwd = Path.cwd()
        if current_cwd.name == "rpa_framework":
            exec_cwd = current_cwd.parent
        else:
            exec_cwd = current_cwd

        creationflags, startupinfo = _get_silent_process_flags()
        process = None
        full_stdout = []
        try:
            process = subprocess.Popen(
                [get_python_exe(), node.script],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                env=env,
                cwd=str(exec_cwd),
                bufsize=1,
                universal_newlines=True,
                creationflags=creationflags,
                startupinfo=startupinfo
            )
            self.active_process = process
            while True:
                line = process.stdout.readline()
                if not line:
                    if process.poll() is not None:
                        break
                    continue
                clean_line = line.strip()
                if clean_line:
                    self.logger.log(f"   [LOOP-PY] {clean_line}")
                    full_stdout.append(clean_line)
                    
            returncode = process.poll()
        finally:
            if process:
                try:
                    if process.stdout: process.stdout.close()
                    if process.stderr: process.stderr.close()
                except Exception:
                    pass
            self.active_process = None
        
        if returncode != 0:
            if self.should_stop:
                self.logger.log("   Script detenido por usuario.")
                return
            raise RuntimeError(f"Script falló con código {returncode}. Últimos logs: {full_stdout[-3:] if full_stdout else 'N/A'}")
        else:
             # Si el script imprime JSON, actualizamos contexto
             for line in reversed(full_stdout):
                 try:
                    output_data = json.loads(line)
                    if isinstance(output_data, dict):
                        self.context.update(output_data)
                        break
                 except: pass
    
    def _eval_condition(self, condition: str) -> bool:
        """
        Evalúa una condición de forma segura.
        
        Args:
            condition: Expresión a evaluar (ej: "x > 5", "status == 'ok'")
            
        Returns:
            Resultado booleano de la evaluación
        """
        try:
            # Crear un diccionario seguro con solo las variables del contexto
            safe_dict = self.context.copy()
            
            # Agregar operadores seguros
            safe_dict.update({
                '__builtins__': {
                    'True': True,
                    'False': False,
                    'None': None,
                    'len': len,
                    'str': str,
                    'int': int,
                    'float': float
                }
            })
            
            result = eval(condition, safe_dict, {})
            return bool(result)
        
        except Exception as e:
            self.logger.warning(f"Error evaluando condición: {e}")
            return False
    
    def _get_loop_count(self, iterations: str) -> int:
        """
        Obtiene el número de iteraciones para un loop.
        
        Args:
            iterations: Puede ser un número o nombre de variable
            
        Returns:
            Número de iteraciones
        """
        try:
            # Intentar convertir directamente a int
            return int(iterations)
        except ValueError:
            # Es un nombre de variable
            value = self.context.get(iterations, 1)
            try:
                return int(value)
            except (ValueError, TypeError):
                self.logger.log(f"⚠️ Iteraciones inválidas: {iterations}, usando 1")
                return 1
    
    def _execute_database(self, node) -> Optional[str]:
        """
        Ejecuta un nodo de base de datos.
        
        Args:
            node: DatabaseNode a ejecutar
            
        Returns:
            ID del siguiente nodo
        """
        from core.database_node import DatabaseNode
        
        if not isinstance(node, DatabaseNode):
            self.logger.log(f"❌ Nodo no es DatabaseNode: {node.id}")
            return self.workflow.get_next_node(node.id)
        
        self.logger.log(f"🗄️ Ejecutando nodo DB: {node.label}")
        self.logger.log(f"   Operación: {node.operation}")
        self.logger.log(f"   Host: {node.host}:{node.port}")
        self.logger.log(f"   Database: {node.database}")
        
        connection = None
        try:
            # Conectar a MySQL
            connection = mysql.connector.connect(
                host=node.host,
                port=node.port,
                user=node.user,
                password=node.password,
                database=node.database
            )
            
            if connection.is_connected():
                self.logger.log(f"✅ Conectado a MySQL")
                
                cursor = connection.cursor(dictionary=True)
                
                # Reemplazar variables en la query
                query = node.query
                for var_name, var_value in self.context.items():
                    placeholder = f"{{{var_name}}}"
                    if placeholder in query:
                        # Escapar valores para prevenir SQL injection
                        if isinstance(var_value, str):
                            var_value = var_value.replace("'", "''")
                            query = query.replace(placeholder, f"'{var_value}'")
                        else:
                            query = query.replace(placeholder, str(var_value))
                
                self.logger.log(f"   Query: {query[:100]}...")
                
                # Ejecutar query
                cursor.execute(query)
                
                if node.operation.upper() == "SELECT":
                    # Para SELECT, obtener resultados
                    results = cursor.fetchall()
                    
                    # Inyectar resultados en contexto
                    if results:
                        if len(results) == 1:
                            # Un solo resultado: dict
                            self.context[node.result_var] = results[0]
                            self.logger.log(f"✅ Resultado guardado en '{node.result_var}': {results[0]}")
                        else:
                            # Múltiples resultados: lista de dicts
                            self.context[node.result_var] = results
                            self.logger.log(f"✅ {len(results)} resultados guardados en '{node.result_var}'")
                    else:
                        self.context[node.result_var] = None
                        self.logger.log(f"⚠️ No se encontraron resultados")
                else:
                    # Para INSERT/UPDATE/DELETE, hacer commit
                    connection.commit()
                    affected_rows = cursor.rowcount
                    self.logger.log(f"✅ {node.operation} ejecutado. Filas afectadas: {affected_rows}")
                    self.context[node.result_var] = {"affected_rows": affected_rows}
                
                cursor.close()
                
        except MySQLError as e:
            error_msg = f"Error MySQL: {str(e)}"
            self.logger.log(f"❌ {error_msg}")
            self.context[node.result_var] = {"error": str(e)}
            
            if getattr(node, 'on_error', 'stop') == 'stop':
                raise e
            
        except Exception as e:
            error_msg = f"Error ejecutando DB: {str(e)}"
            self.logger.log(f"❌ {error_msg}")
            self.context[node.result_var] = {"error": str(e)}
            
            if getattr(node, 'on_error', 'stop') == 'stop':
                raise e
            
        finally:
            if connection and connection.is_connected():
                connection.close()
                self.logger.log(f"🔌 Conexión cerrada")
        
        return self.workflow.get_next_node(node.id)

    def _execute_workflow(self, node) -> Optional[str]:
        """
        Ejecuta un workflow anidado.
        """
        if not isinstance(node, WorkflowNode):
            self.logger.log(f"❌ Nodo no es WorkflowNode: {node.id}")
            return self.workflow.get_next_node(node.id)
            
        wf_path = node.workflow_path
        if not wf_path:
            self.logger.log("⚠️ Nodo Workflow sin ruta definida")
            return self.workflow.get_next_node(node.id)
            
        self.logger.log(f"🔄 Preparando ejecución de workflow anidado: {wf_path}")
        
        # Resolver ruta
        path_obj = Path(wf_path)
        if not path_obj.is_absolute():
            # Intentar en rpa_framework/workflows
            base_dir = Path("rpa_framework/workflows")
            if not base_dir.exists():
                 base_dir = Path("workflows")
            
            candidate = base_dir / wf_path
            # Si tiene extensión .json bien, sino probar agregandola
            if not candidate.exists() and not candidate.suffix:
                candidate = candidate.with_suffix(".json")
            
            if candidate.exists():
                path_obj = candidate
            else:
                # Fallback: intentar desde cwd
                path_obj = Path(wf_path).resolve()

        if not path_obj.exists():
             self.logger.log(f"❌ Archivo de workflow no encontrado: {path_obj}")
             if getattr(node, 'on_error', 'stop') == 'stop':
                 raise FileNotFoundError(f"Workflow no encontrado: {path_obj}")
             return self.workflow.get_next_node(node.id)
             
        try:
            # Cargar nested workflow
            nested_wf = Workflow.from_json(str(path_obj))
            
            # Inicializar variables con el contexto actual
            # (Sobreescribiendo las defaults del nested)
            nested_wf.variables.update(self.context)
            
            # Crear executor
            nested_executor = WorkflowExecutor(nested_wf, self.logger.log_dir, is_sub_workflow=True)
            self.nested_executor = nested_executor
            
            # --- PATCH LOGGER ---
            # Para que los logs del hijo suban al padre (y a la UI)
            original_child_log = nested_executor.logger.log
            def bridged_log(msg, level="INFO"):
                prefix = f"   [WF:{nested_wf.name}]"
                self.logger.log(f"{prefix} {msg}", level)
            
            nested_executor.logger.log = bridged_log
            # --------------------
            
            self.logger.log(f"▶️ Iniciando sub-workflow: {nested_wf.name}")
            try:
                result = nested_executor.execute()
            finally:
                self.nested_executor = None
            
            status = result.get("status") if isinstance(result, dict) else "unknown"
            if status == "stopped" or self.should_stop:
                self.logger.log("⏹️ Sub-workflow detenido por el usuario. Deteniendo padre.")
                self.should_stop = True
                self._external_stop = True
                return None
            elif status == "error":
                if self.should_stop:
                    self.logger.log("⏹️ Sub-workflow cancelado por detención.")
                    return None
                self.logger.log(f"❌ Error en sub-workflow: {result.get('error')}")
                if getattr(node, 'on_error', 'stop') == 'stop':
                     raise RuntimeError(f"Fallo en sub-workflow: {result.get('error')}")
            else:
                self.logger.log(f"✅ Sub-workflow finalizado correctamente")
                # Actualizar contexto padre con resultados del hijo
                self.context.update(result.get("context", {}))
        
        except Exception as e:
            self.logger.log(f"❌ Error ejecutando nodo workflow: {e}")
            if getattr(node, 'on_error', 'stop') == 'stop':
                raise e
                
        return self.workflow.get_next_node(node.id)
