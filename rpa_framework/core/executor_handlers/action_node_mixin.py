"""
Mixin para ejecución de nodos de acción (ActionNode: comandos del sistema y scripts Python).
"""

import subprocess
import json
import sys
import time
import threading
import queue
from pathlib import Path
from typing import Optional
import mysql.connector

from core.models import ActionNode
from utils.telegram_manager import enviar_alerta_todos
from .process_utils import get_python_exe, _get_silent_process_flags

try:
    import win32com.client
    import pythoncom
except ImportError:
    pass

try:
    from utils.window_utils import maximize_ris_pacs
except ImportError:
    try:
        from rpa_framework.utils.window_utils import maximize_ris_pacs
    except ImportError:
        maximize_ris_pacs = None


class ActionNodeMixin:
    """Mixin para ejecutar ActionNode (comandos o scripts Python con streaming y control de errores)."""

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
                     
                     cmd_str = str(node.command).lower() if node.command else ""
                     label_str = str(node.label).lower() if node.label else ""
                     es_cmd_excluido = any(k in cmd_str for k in ["mp.exe"]) or \
                                       any(k in label_str for k in ["abre pacs", "abrir pacs", "ingresa user pacs"])
                     if not es_cmd_excluido:
                         if any(k in cmd_str for k in ["carestream ris"]) or \
                            any(k in label_str for k in ["inicia ris", "iniciar ris"]):
                              if maximize_ris_pacs:
                                  try:
                                      max_w = maximize_ris_pacs()
                                      if max_w > 0:
                                          self.logger.log(f"   🪟 Ventana(s) de RIS/PACS maximizada(s) ({max_w})")
                                  except Exception as max_err:
                                      self.logger.log(f"   ⚠️ Aviso al auto-maximizar ventana: {max_err}")
                elif returncode == 2 or any(k in str(node.label).lower() for k in ["vpn"]):
                     self.logger.log(f"ℹ️ Comando finalizado (código {returncode}): Tratando como sin registros para trabajar / espera VPN. Deteniendo flujo de forma limpia.")
                     self.no_records_found = True
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
                
                # Leer salida en tiempo real con timeout de seguridad (12 minutos)
                out_queue = queue.Queue()
                def _reader():
                    try:
                        for l in iter(process.stdout.readline, ''):
                            out_queue.put(l)
                    except Exception:
                        pass
                    finally:
                        out_queue.put(None)

                reader_thread = threading.Thread(target=_reader, daemon=True)
                reader_thread.start()

                full_stdout = []
                start_script_time = time.time()
                SCRIPT_MAX_TIMEOUT = 720  # 12 minutos
                is_timeout = False

                while True:
                    if self.should_stop:
                        break

                    if time.time() - start_script_time > SCRIPT_MAX_TIMEOUT:
                        is_timeout = True
                        self.logger.log(f"🚨 TIMEOUT (12 min): Script '{node.label}' excedió el tiempo máximo permitido ({SCRIPT_MAX_TIMEOUT}s). Forzando cierre...")
                        try:
                            if sys.platform == "win32":
                                subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True, timeout=3)
                            process.kill()
                        except Exception:
                            pass
                        break

                    try:
                        line = out_queue.get(timeout=0.5)
                        if line is None:
                            break
                        clean_line = line.strip()
                        if clean_line:
                            self.logger.log(f"   [PY] {clean_line}")
                            full_stdout.append(clean_line)
                    except queue.Empty:
                        if process.poll() is not None and out_queue.empty():
                            break

                try:
                    returncode = process.wait(timeout=5)
                except Exception:
                    returncode = process.poll()
                if is_timeout:
                    returncode = -1
                    full_stdout.append(f"TIMEOUT: Script finalizado forzadamente tras {SCRIPT_MAX_TIMEOUT}s de inactividad.")
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
                
                # Auto-maximizar ventanas de RIS y PACS si el script o nodo abrió RIS/PACS
                # (Deshabilitado para abre_pacs e ingresa_user_pacs)
                script_str = str(node.script).lower() if node.script else ""
                label_str = str(node.label).lower() if node.label else ""
                es_excluido = any(k in script_str for k in ["abre_pacs", "ingresa_user_pacs"]) or \
                              any(k in label_str for k in ["abre pacs", "abrir pacs", "ingresa user pacs"])
                if not es_excluido:
                    if any(k in script_str for k in ["inicio_ris"]) or \
                       any(k in label_str for k in ["inicia ris", "iniciar ris"]):
                        if maximize_ris_pacs:
                            try:
                                max_w = maximize_ris_pacs()
                                if max_w > 0:
                                    self.logger.log(f"   🪟 Ventana(s) de RIS/PACS maximizada(s) post-ejecución ({max_w})")
                            except Exception as max_err:
                                self.logger.log(f"   ⚠️ Aviso al auto-maximizar ventana: {max_err}")
            elif returncode == 2:
                self.logger.log(f"ℹ️ Script finalizado (código 2): Sin registros para trabajar. Deteniendo flujo de forma limpia.")
                self.no_records_found = True
                self.should_stop = True
                return None
            elif any(k in str(node.label).lower() for k in ["vpn"]) or any(k in str(node.script).lower() for k in ["vpn"]):
                self.logger.log(f"ℹ️ Verificación VPN finalizada sin conexión (código {returncode}). Tratando como 'sin registros para trabajar'. Deteniendo flujo de forma limpia.")
                try:
                    conn_chk = mysql.connector.connect(host='localhost', user='root', password='', database='ris', connect_timeout=3)
                    cur_chk = conn_chk.cursor(dictionary=True)
                    cur_chk.execute("SELECT id FROM ris.registro_acciones WHERE estado = 'En Proceso' ORDER BY id DESC LIMIT 1")
                    rec_chk = cur_chk.fetchone()
                    if rec_chk:
                        rec_id = rec_chk['id']
                        cur_chk.execute("UPDATE ris.registro_acciones SET estado = 'sin registros para trabajar', observacion = %s, `update` = NOW() WHERE id = %s",
                                        (f"[{node.label}] VPN no conectada o espera activa agotada", rec_id))
                        conn_chk.commit()
                    cur_chk.close()
                    conn_chk.close()
                except Exception as chk_e:
                    self.logger.log(f"⚠️ Error actualizando registro VPN a sin registros: {chk_e}")
                self.no_records_found = True
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
                            enviar_alerta_todos(f"🚨 <b>ERROR en {node.label}</b> (Fila #{rec_id})\n\n🆔 <b>ID Fila BD:</b> <code>{rec_id}</code>\n\n📋 <b>Problema:</b>\nScript terminó con código de error {returncode}.\n\n<code>{ultimo_log}</code>", record_id=rec_id)
                        cur_chk.close()
                        conn_chk.close()
                    except Exception as chk_e:
                        self.logger.log(f"⚠️ Error en verificación de fallback: {chk_e}")
                except Exception as tel_e:
                    self.logger.log(f"⚠️ Error al procesar alerta de respaldo: {tel_e}")
                
                if getattr(node, 'on_error', 'stop') == 'stop':
                    raise RuntimeError(f"El asistente no pudo completar la tarea en la fase '{node.label}'.")
                else:
                    prefix = f"{self.workflow.name}_{node.label}"
                    self._save_and_send_error_video(f"Script falló con código {returncode}", custom_prefix=prefix)
                    if not self.should_stop:
                        self._restart_screen_recorder()
            
        except Exception as e:
            self.logger.log(f"❌ Error: {str(e)}")
            
            # Igual omitimos alerta si el nivel superior lo va a atrapar
            # enviar_alerta_todos(f"❌ <b>Excepción en Script</b>\nNodo: {node.label}\nError: <code>{str(e)}</code>")
                
            if getattr(node, 'on_error', 'stop') == 'stop':
                raise RuntimeError(f"Falla inesperada en la fase '{node.label}': {str(e)}")
            else:
                prefix = f"{self.workflow.name}_{node.label}"
                self._save_and_send_error_video(f"Excepción en nodo {node.label}: {str(e)}", custom_prefix=prefix)
                if not self.should_stop:
                    self._restart_screen_recorder()
        
        return self.workflow.get_next_node(node.id)
