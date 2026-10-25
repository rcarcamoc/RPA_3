"""
Mixin para ejecución de nodos de bucle (LoopNode) con aislamiento total, auto-pausa y sub-ejecución.
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

from core.models import Workflow, LoopNode
from .process_utils import get_python_exe, _get_silent_process_flags


class LoopNodeMixin:
    """Mixin para ejecutar LoopNode y sus sub-workflows o scripts internos."""

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
        self.is_in_loop = True
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

        # ── Notificación de Inicio a Telegram (Solo para Root Loop) ──
        is_root_loop = (not getattr(self, 'is_sub_workflow', False)) or (str(getattr(self.workflow, 'name', '')).lower() == "loop")
        start_loop_ts = time.time()
        motivo_fin = "completado"

        if is_root_loop:
            detalles_str = ""
            if loop_type == 'count':
                detalles_str = f"{iterations} iteraciones configuradas"
            elif loop_type == 'timed':
                detalles_str = f"{hours:g} horas programadas"
            elif loop_type == 'infinite':
                detalles_str = "Continuo infinito (hasta detención manual)"
            elif loop_type == 'while':
                detalles_str = f"Condición: {node.condition}"
            elif loop_type == 'list':
                detalles_str = f"Lista: {node.iterable} ({len(iterator)} elementos)"

            try:
                try:
                    from utils.notificador_resumen import notificar_inicio_loop
                except ImportError:
                    from rpa_framework.utils.notificador_resumen import notificar_inicio_loop
                notificar_inicio_loop(modo=loop_type, detalles=detalles_str, workflow_name=self.workflow.name)
            except Exception as e_start_notif:
                self.logger.log(f"⚠️ Error enviando notificación de inicio de loop a Telegram: {e_start_notif}")

        # ── 2. Ejecutar Loop ────────────────────────────────────────────
        idx = 0
        consecutive_errors = 0
        MAX_ITER = 100_000  # Safety break para while (~83 días a 1 iter/min)

        # Ruta a config/stop_after_case.txt en rpa_framework/config/
        rpa_framework_dir = Path(__file__).resolve().parent.parent.parent

        while True:
            # Si el loop está pausado, esperar hasta reanudación o parada externa
            while not self.pause_event.is_set() and not self.should_stop:
                time.sleep(0.5)

            # Solo se respeta el stop EXTERNO (botón Stop del usuario).
            # Se verifica ANTES de la iteración, nunca durante.
            # Verificar si se solicitó detener el bucle tras el caso previo
            stop_after_file = rpa_framework_dir / "config" / "stop_after_case.txt"
            if getattr(self, 'stop_after_iteration', False) or stop_after_file.exists():
                motivo_fin = "detenido_tras_caso"
                self.logger.log("⏹️ Loop detenido antes de iniciar nueva iteración (solicitud de reprocesamiento/parada suave).")
                self.should_stop = True
                self._external_stop = True
                try:
                    if stop_after_file.exists():
                        stop_after_file.unlink()
                except Exception:
                    pass
                break

            if self.should_stop:
                motivo_fin = "detenido"
                self.logger.log("⏹️ Loop detenido por señal externa del usuario.")
                break

            # ── Control de flujo según modo ──
            current_item = None

            if is_timed:
                remaining = deadline - time.time()
                if remaining <= 0:
                    motivo_fin = "tiempo_cumplido"
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
                    motivo_fin = "limite_seguridad"
                    self.logger.log(f"⚠️ Límite de seguridad alcanzado ({MAX_ITER:,} iteraciones)")
                    break
                try:
                    condition_result = self._eval_condition(node.condition)
                except Exception as cond_err:
                    self.logger.log(f"⚠️ Error evaluando condición: {cond_err} — asumiendo True")
                    condition_result = True
                if not condition_result:
                    motivo_fin = "condicion_finalizada"
                    break
                current_item = idx

            else:
                # count / list
                if idx >= len(iterator):
                    motivo_fin = "completado"
                    break
                current_item = iterator[idx]

            self.logger.log(f"   🔄 Iteración {idx + 1}")

            # Asegurar que la grabación esté activa para esta iteración
            if self.enable_recording and not self.is_sub_workflow and not self.screen_recorder:
                self._restart_screen_recorder()

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

                # Iteración exitosa: reiniciar contador de errores consecutivos
                consecutive_errors = 0

                # Iteración exitosa: descartar video de esta iteración y reiniciar limpio para la siguiente
                if self.enable_recording and not self.is_sub_workflow and not self.should_stop:
                    if self.screen_recorder:
                        self.screen_recorder.discard()
                        self.screen_recorder = None
                    self._restart_screen_recorder()

            except Exception as e:
                if self.should_stop:
                    self.logger.log("⏹️ Iteración de loop interrumpida por detención externa.")
                    if self.screen_recorder:
                        self.screen_recorder.discard()
                        self.screen_recorder = None
                    break
                self.logger.log(f"   ❌ Error en iteración {idx + 1} (ignorado, loop continúa): {e}")

                # Verificar si el fallo provino de actualiza_estado o si quedó en Aprobacion_Pendiente
                es_aprobacion_pendiente = False
                _ultimo = None
                err_str = str(e).lower()
                if any(k in err_str for k in ["actualiza_estado", "aprobacion_pendiente", "addendum", "ya_ingresado", "ya ingresado"]):
                    es_aprobacion_pendiente = True
                else:
                    try:
                        _conn = mysql.connector.connect(host='localhost', user='root', password='', database='ris', connect_timeout=2)
                        _cur = _conn.cursor(dictionary=True)
                        _cur.execute("SELECT id, estado, observacion FROM ris.registro_acciones ORDER BY id DESC LIMIT 1")
                        _ultimo = _cur.fetchone()
                        _cur.close()
                        _conn.close()
                        if _ultimo:
                            est_ult = str(_ultimo.get("estado") or "").lower()
                            obs_ult = str(_ultimo.get("observacion") or "").lower()
                            if any(k in est_ult for k in ["aprobacion_pendiente", "addendum", "ya_ingresado", "ya ingresado", "terminado"]) or "actualiza_estado" in obs_ult:
                                es_aprobacion_pendiente = True
                    except Exception:
                        pass

                if es_aprobacion_pendiente:
                    self.logger.log("   ℹ️ Evento de Aprobación Pendiente / Reclasificado (Addendum/Ya Ingresado): NO suma al contador de errores de auto-pausa.")
                else:
                    consecutive_errors += 1
                    self.logger.log(f"   ⚠️ Errores consecutivos en loop: {consecutive_errors}/2")
                    if consecutive_errors >= 2:
                        self.logger.log("   🚨 2 errores consecutivos detectados. Pausando loop y alertando a Telegram...")
                        self.pause()
                        try:
                            from utils.telegram_manager import notificar_loop_pausado
                            rec_id_loop = _ultimo.get("id") if (_ultimo and isinstance(_ultimo, dict)) else None
                            notificar_loop_pausado(ultimo_error=str(e), workflow_name=self.workflow.name, iteracion=idx + 1, record_id=rec_id_loop)
                        except Exception as e_notif:
                            self.logger.log(f"   ⚠️ Error enviando alerta de pausa a Telegram: {e_notif}")

                        # Esperar respuesta del usuario desde Telegram (Reanudar o Detener)
                        while not self.pause_event.is_set() and not self.should_stop:
                            time.sleep(0.5)

                        if self.should_stop:
                            motivo_fin = "detenido"
                            self.logger.log("⏹️ Loop cancelado por el usuario durante la pausa.")
                            if self.screen_recorder:
                                self.screen_recorder.discard()
                                self.screen_recorder = None
                            break

                        # Al reanudar:
                        consecutive_errors = 0
                        self.logger.log("   ▶️ Loop reanudado por el usuario. Continuando...")

                # Guardar y enviar video del error de esta iteración
                wf_sub_name = Path(node.workflow_path).stem if node.workflow_path else (Path(node.script).stem if node.script else "iter")
                prefix = f"{self.workflow.name}_{wf_sub_name}_iter{idx+1}"
                self._save_and_send_error_video(f"Iteración {idx + 1} ({wf_sub_name}): {str(e)}", custom_prefix=prefix)

                # Reiniciar grabador limpio para la siguiente iteración
                if not self.should_stop:
                    self._restart_screen_recorder()

                delay = getattr(node, 'error_delay', 0)
                if delay > 0:
                    self.logger.log(f"   ⏳ Esperando {delay}s antes de reintentar...")
                    end_d = time.time() + delay
                    while time.time() < end_d and not self.should_stop:
                        time.sleep(0.2)
                    if self.should_stop:
                        motivo_fin = "detenido"
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

            # Verificar detención suave tras finalizar el caso actual
            stop_after_file = rpa_framework_dir / "config" / "stop_after_case.txt"
            if getattr(self, 'stop_after_iteration', False) or stop_after_file.exists():
                motivo_fin = "detenido_tras_caso"
                self.logger.log("⏹️ Loop detenido tras completar el caso actual sin interrumpirlo (solicitud de reprocesamiento/parada suave).")
                self.should_stop = True
                self._external_stop = True
                try:
                    if stop_after_file.exists():
                        stop_after_file.unlink()
                except Exception:
                    pass
                break

            if self.should_stop:
                motivo_fin = "detenido"
                break

            idx += 1

        self.is_in_loop = False
        self.logger.log(f"✅ Loop finalizado ({idx} iteraciones ejecutadas)")
        if is_root_loop:
            duracion_total = time.time() - start_loop_ts
            self.logger.log("📢 Enviando notificación de fin de ciclo y resumen diario a Telegram...")
            try:
                try:
                    from utils.notificador_resumen import notificar_fin_loop_con_resumen
                except ImportError:
                    from rpa_framework.utils.notificador_resumen import notificar_fin_loop_con_resumen
                notificar_fin_loop_con_resumen(
                    motivo=motivo_fin,
                    iteraciones=idx,
                    duracion_segundos=duracion_total,
                    workflow_name=self.workflow.name
                )
            except Exception as e_fin_notif:
                self.logger.log(f"⚠️ Error enviando notificación de fin de loop a Telegram: {e_fin_notif}")
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
        
        # Executor (usando la misma clase WorkflowExecutor del padre)
        self.nested_executor = self.__class__(nested_wf, self.logger.log_dir, is_sub_workflow=True)
        
        # Patch logs
        original_log = self.nested_executor.logger.log
        def bridged_log(msg, level="INFO"):
            prefix = f"   [LOOP-WF:{nested_wf.name}]"
            self.logger.log(f"{prefix} {msg}", level)
        self.nested_executor.logger.log = bridged_log
        
        self.logger.log(f"   ▶️ Loop Running Workflow: {nested_wf.name}")
        child_executor = self.nested_executor
        try:
            result = child_executor.execute()
        finally:
            self.nested_executor = None
        
        status = result.get("status") if isinstance(result, dict) else "unknown"
        is_ext = self._external_stop or getattr(child_executor, '_external_stop', False)
        if status == "no_records":
            self.logger.log("   ℹ️ Iteración sin registros de pacientes. Continuando ciclo de loop...")
            self.context.update(result.get("context", {}))
            return
        elif status == "stopped" or self.should_stop:
            if is_ext:
                self.logger.log("   Workflow anidado detenido por usuario.")
                self.should_stop = True
                self._external_stop = True
            else:
                self.logger.log("   Workflow anidado detenido internamente.")
                self.should_stop = True
        elif status == "error":
            if self.should_stop or is_ext:
                self.logger.log("   Workflow anidado detenido por usuario.")
                self.should_stop = True
                self._external_stop = is_ext
            else:
                raise RuntimeError(f"Fallo en workflow de loop: {result.get('error')}")
        else:
            self.context.update(result.get("context", {}))

    def _run_script_internal(self, node):
        """Helper para ejecutar script python del loop"""
        env = self._get_subprocess_env()
        
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
            # Leer salida con timeout de seguridad (12 minutos)
            out_queue = queue.Queue()
            def _reader_loop():
                try:
                    for l in iter(process.stdout.readline, ''):
                        out_queue.put(l)
                except Exception:
                    pass
                finally:
                    out_queue.put(None)

            reader_thread = threading.Thread(target=_reader_loop, daemon=True)
            reader_thread.start()

            start_script_time = time.time()
            SCRIPT_MAX_TIMEOUT = 720  # 12 minutos
            is_timeout = False

            while True:
                if self.should_stop:
                    break

                if time.time() - start_script_time > SCRIPT_MAX_TIMEOUT:
                    is_timeout = True
                    self.logger.log(f"🚨 TIMEOUT (12 min): Script de loop '{node.script}' excedió el tiempo máximo permitido ({SCRIPT_MAX_TIMEOUT}s). Forzando cierre...")
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
                        self.logger.log(f"   [LOOP-PY] {clean_line}")
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
                full_stdout.append(f"TIMEOUT: Script de loop finalizado forzadamente tras {SCRIPT_MAX_TIMEOUT}s de inactividad.")
        finally:
            if process:
                try:
                    if process.stdout: process.stdout.close()
                    if process.stderr: process.stderr.close()
                except Exception:
                    pass
            self.active_process = None
        
        if returncode == 2:
            self.logger.log("   ℹ️ Script de loop finalizado (código 2): Sin registros para trabajar. Continuando al siguiente ciclo.")
            return
        elif returncode != 0:
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
                 except Exception:
                     pass
