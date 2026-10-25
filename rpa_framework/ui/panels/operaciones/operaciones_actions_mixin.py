"""
Mixin de acciones operativas, telemetría, bucles y control de parada para ModernOperacionesPanel.
Extraído de main_gui_final.py.
"""

import os
import json
import time
from pathlib import Path
from datetime import datetime
from PyQt6.QtWidgets import QApplication, QMessageBox

from core.models import Workflow, LoopNode
from ui.workflow_panel import WorkflowExecutorWorker

# Directorio raíz de rpa_framework (este archivo vive en rpa_framework/ui/panels/operaciones/)
RPA_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class OperacionesActionsMixin:
    """Mixin con la lógica de negocio, telemetría, control de bucles y BD de ModernOperacionesPanel."""

    def actualizar_visibilidad_loop(self):
        """Muestra u oculta campos según el modo de loop seleccionado."""
        modo = self.combo_loop_type.currentText()
        self.container_count.setVisible("Por Cantidad" in modo)
        self.container_timed.setVisible("Por Tiempo" in modo)
        
    def ejecutar_inicio_completo(self):
        wf_path = os.path.join("workflows", "Sub_work.json")
        self.run_workflow(wf_path)

    def ejecutar_pega_integra(self):
        wf_path = os.path.join("workflows", "pacs.json")
        self.run_workflow(wf_path)

    def add_log(self, msg, level="info"):
        """Agrega un mensaje con timestamp y formato estilizado al terminal."""
        now_str = datetime.now().strftime("%H:%M:%S")
        
        if "error" in msg.lower() or "falló" in msg.lower() or "❌" in msg or level == "error":
            color = "#f87171"
        elif "éxito" in msg.lower() or "completado" in msg.lower() or "finalizado" in msg.lower() or "✅" in msg or level == "success":
            color = "#34d399"
        elif "iniciando" in msg.lower() or "🚀" in msg or "ejecutando" in msg.lower() or level == "start":
            color = "#38bdf8"
        elif "advertencia" in msg.lower() or "aviso" in msg.lower() or "⚠️" in msg or level == "warn":
            color = "#fbbf24"
        elif "detectada ejecución externa" in msg.lower() or "servicio" in msg.lower() or "🔄" in msg:
            color = "#c084fc"
        else:
            color = "#e2e8f0"
            
        html_msg = f'<div style="margin-bottom: 2px;"><span style="color: #64748b; font-size: 8pt;">[{now_str}]</span> <span style="color: {color}; font-size: 9pt;">{msg}</span></div>'
        self.log_viewer.append(html_msg)
        sb = self.log_viewer.verticalScrollBar()
        sb.setValue(sb.maximum())

    def limpiar_logs(self):
        """Limpia el terminal de logs."""
        self.log_viewer.clear()

    def copiar_logs(self):
        """Copia el contenido del terminal al portapapeles."""
        text = self.log_viewer.toPlainText()
        if text.strip():
            QApplication.clipboard().setText(text)
            self.add_log("📋 Logs copiados al portapapeles con éxito.")

    def update_elapsed_time(self):
        """Actualiza el label del tiempo transcurrido desde el inicio."""
        if self.start_time:
            elapsed = datetime.now() - self.start_time
            seconds = int(elapsed.total_seconds())
            hours, remainder = divmod(seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            self.lbl_time.setText(f"{hours:02d}:{minutes:02d}:{seconds:02d}")

    def check_background_state(self):
        """Chequea si el servicio de Telegram está ejecutando un flujo mediante el archivo state.json."""
        config_dir = RPA_ROOT / "config"
        state_file = config_dir / "execution_state.json"
        stop_signal_file = config_dir / "stop_signal.txt"

        if stop_signal_file.exists() and self.worker and self.worker.isRunning():
            self.add_log("🛑 Señal de parada externa detectada (Telegram/Tray). Deteniendo worker local...", level="warn")
            self.worker.stop()
            try:
                stop_signal_file.unlink()
            except Exception:
                pass

        bg_running = False
        wf_name = ""
        
        if state_file.exists():
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                    bg_running = state.get("is_running", False)
                    wf_name = state.get("workflow", "")
            except Exception:
                pass
                
        if bg_running != self.is_bg_running:
            self.is_bg_running = bg_running
            self._update_buttons_state()
            
            if bg_running:
                if wf_name == "Validación PACS":
                    self.lbl_status_icon.setText("🔍")
                    self.lbl_status_val.setText("Validación PACS en curso...")
                    self.status_banner.setStyleSheet("background-color: #fffbeb; border: 1px solid #f59e0b; border-radius: 8px; padding: 4px;")
                    self.lbl_active_wf.setText("Validación PACS")
                else:
                    self.lbl_status_icon.setText("🟣")
                    self.lbl_status_val.setText(f"Servicio Remoto: {wf_name}")
                    self.status_banner.setStyleSheet("background-color: #f5f3ff; border: 1px solid #8b5cf6; border-radius: 8px; padding: 4px;")
                    self.lbl_active_wf.setText(wf_name)
                    
                self.lbl_active_mode.setText("Servicio Telegram")
                self.lbl_active_channel.setText("Bot Telegram")
                self.badge_system.setText("● Ocupado (Background)")
                self.badge_system.setStyleSheet("background-color: #fef3c7; color: #d97706; border: 1px solid #fcd34d; border-radius: 12px; padding: 4px 12px; font-size: 9pt; font-weight: 700;")
                
                self.progress_bar.setRange(0, 0)
                self.start_time = datetime.now()
                self.duration_timer.start(1000)
                self.add_log(f"🔄 Detectada ejecución externa: {wf_name}")
            else:
                if not (self.worker and self.worker.isRunning()):
                    self._set_ui_idle_state()

    def _set_ui_idle_state(self):
        """Restaura todos los indicadores visuales al estado de reposo."""
        self.lbl_status_icon.setText("⚪")
        self.lbl_status_val.setText("Sistema en Reposo (Listo para operar)")
        self.status_banner.setStyleSheet("background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 4px;")
        self.lbl_active_wf.setText("Ninguno")
        self.lbl_active_mode.setText("Individual")
        self.lbl_active_channel.setText("Panel Local")
        self.badge_system.setText("● Sistema Listo")
        self.badge_system.setStyleSheet("background-color: #ecfdf5; color: #059669; border: 1px solid #a7f3d0; border-radius: 12px; padding: 4px 12px; font-size: 9pt; font-weight: 700;")
        
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.duration_timer.stop()
        self.lbl_time.setText("00:00:00")

    def _update_buttons_state(self):
        is_busy = bool(self.is_bg_running or (self.worker and self.worker.isRunning()))
        self.btn_inicio.setEnabled(not is_busy)
        self.btn_pega.setEnabled(not is_busy)
        self.btn_loop.setEnabled(not is_busy)
        self.btn_rehabilitar.setEnabled(not is_busy)
        
        self.btn_stop.setText("🛑  Detener Flujo")
        self.btn_stop.setEnabled(is_busy)

    def ejecutar_loop_reiteraciones(self, tg_params=None):
        """Ejecuta el workflow loop.json con las opciones avanzadas configuradas en el panel."""
        wf_path = os.path.join("workflows", "loop.json")
        
        if tg_params:
            tipo_loop = tg_params["tipo"]
            if tipo_loop == "count":
                reiteraciones = tg_params["valor"]
                duracion = 1.0
            elif tipo_loop == "timed":
                reiteraciones = "5"
                duracion = float(tg_params["valor"])
            else:
                reiteraciones = "5"
                duracion = 1.0
            delay_error = 0
            modo_ui = "Telegram"
            print(f"🔄 Modo loop desde Telegram: {tipo_loop}")
        else:
            modo_texto = self.combo_loop_type.currentText()
            if "Por Cantidad" in modo_texto:
                tipo_loop = "count"
                reiteraciones = str(self.spin_iterations.value())
                duracion = 1.0
                modo_ui = f"Cantidad ({reiteraciones} ciclos)"
            elif "Por Tiempo" in modo_texto:
                tipo_loop = "timed"
                reiteraciones = "5"
                duracion = self.spin_duration.value()
                modo_ui = f"Tiempo ({duracion}h)"
            else:
                tipo_loop = "infinite"
                reiteraciones = "9999"
                duracion = 72.0
                modo_ui = "Infinito"
                
            delay_error = self.spin_error_delay.value()
        
        if hasattr(self, 'worker') and self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Atención", "Ya hay un workflow en ejecución. Por favor espere a que termine.")
            return
            
        if not os.path.exists(wf_path):
            QMessageBox.critical(self, "Error", f"No se encontró el workflow:\n{wf_path}")
            return
            
        try:
            workflow = Workflow.from_json(wf_path)
            
            found = False
            for node in workflow.nodes:
                if isinstance(node, LoopNode):
                    node.loop_type = tipo_loop
                    node.iterations = reiteraciones
                    node.duration_hours = duracion
                    node.error_delay = delay_error
                    print(f"🔄 UI: Configurando Loop '{node.label}' -> Tipo: {tipo_loop}, Iteraciones: {reiteraciones}, Duración: {duracion}h, Delay Error: {delay_error}s")
                    found = True
            
            if not found:
                print("⚠️ No se encontró ningún nodo de tipo Loop en loop.json")

            cfg_dir = RPA_ROOT / "config"
            stop_file = cfg_dir / "stop_signal.txt"
            stop_after_file = cfg_dir / "stop_after_case.txt"
            try:
                if stop_file.exists():
                    stop_file.unlink()
                if stop_after_file.exists():
                    stop_after_file.unlink()
            except Exception:
                pass

            self.add_log(f"🚀 Iniciando loop continuo en modo: {modo_ui}", level="start")
            
            self.worker = WorkflowExecutorWorker(workflow)
            self.worker.log_update.connect(self.handle_log_update)
            self.worker.finished.connect(self.on_workflow_finished)
            self.worker.error.connect(self.on_workflow_finished)
            
            self.start_time = datetime.now()
            self.duration_timer.start(1000)
            self.progress_bar.setRange(0, 0)
            
            self.lbl_status_icon.setText("🟢")
            self.lbl_status_val.setText(f"Loop en Ejecución ({modo_ui})")
            self.status_banner.setStyleSheet("background-color: #ecfdf5; border: 1px solid #10b981; border-radius: 8px; padding: 4px;")
            self.lbl_active_wf.setText("loop.json")
            self.lbl_active_mode.setText(f"Loop: {modo_ui}")
            self.lbl_active_channel.setText("Panel Local")
            self.badge_system.setText("● Ejecutando")
            self.badge_system.setStyleSheet("background-color: #dbeafe; color: #1d4ed8; border: 1px solid #93c5fd; border-radius: 12px; padding: 4px 12px; font-size: 9pt; font-weight: 700;")
            
            self._current_is_loop = True
            self.worker.start()
            self._set_local_execution_state(True, "loop.json", is_loop=True)
            self._update_buttons_state()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error iniciando loop: {e}")
            import traceback
            traceback.print_exc()

    def run_workflow(self, wf_path):
        if hasattr(self, 'worker') and self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Atención", "Ya hay un workflow en ejecución. Por favor espere a que termine.")
            return
            
        if not os.path.exists(wf_path):
            QMessageBox.critical(self, "Error", f"No se encontró el workflow:\n{wf_path}")
            return
            
        try:
            workflow = Workflow.from_json(wf_path)
            wf_name = os.path.basename(wf_path)

            cfg_dir = RPA_ROOT / "config"
            stop_file = cfg_dir / "stop_signal.txt"
            stop_after_file = cfg_dir / "stop_after_case.txt"
            try:
                if stop_file.exists():
                    stop_file.unlink()
                if stop_after_file.exists():
                    stop_after_file.unlink()
            except Exception:
                pass

            self.add_log(f"🚀 Iniciando workflow: {wf_name}", level="start")
            
            self.worker = WorkflowExecutorWorker(workflow)
            self.worker.log_update.connect(self.handle_log_update)
            self.worker.finished.connect(self.on_workflow_finished)
            self.worker.error.connect(self.on_workflow_finished)
            
            self.start_time = datetime.now()
            self.duration_timer.start(1000)
            self.progress_bar.setRange(0, 0)
            
            self.lbl_status_icon.setText("🟢")
            self.lbl_status_val.setText(f"Ejecutando: {wf_name}")
            self.status_banner.setStyleSheet("background-color: #ecfdf5; border: 1px solid #10b981; border-radius: 8px; padding: 4px;")
            self.lbl_active_wf.setText(wf_name)
            self.lbl_active_mode.setText("Individual")
            self.lbl_active_channel.setText("Panel Local")
            self.badge_system.setText("● Ejecutando")
            self.badge_system.setStyleSheet("background-color: #dbeafe; color: #1d4ed8; border: 1px solid #93c5fd; border-radius: 12px; padding: 4px 12px; font-size: 9pt; font-weight: 700;")
            
            has_loop = any(getattr(n, 'type', None) in ('loop', 'LoopNode') or str(getattr(n, 'type', '')).lower() == 'loop' for n in getattr(workflow, 'nodes', [])) or "loop" in wf_name.lower()
            self._current_is_loop = has_loop
            self.worker.start()
            self._set_local_execution_state(True, wf_name, is_loop=has_loop)
            self._update_buttons_state()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error iniciando workflow: {e}")
            import traceback
            traceback.print_exc()

    def handle_log_update(self, msg):
        print(f"[WORKFLOW]: {msg}")
        self.add_log(msg)

    def _set_local_execution_state(self, is_running, wf_name="", is_loop=False):
        try:
            cfg_dir = RPA_ROOT / "config"
            cfg_dir.mkdir(parents=True, exist_ok=True)
            with open(cfg_dir / "execution_state.json", "w", encoding="utf-8") as f:
                json.dump({
                    "is_running": is_running,
                    "workflow": wf_name,
                    "is_loop": is_loop,
                    "updated_at": time.time()
                }, f)
        except Exception:
            pass

    def on_workflow_finished(self, result):
        prev_wf = self.lbl_active_wf.text()
        self.duration_timer.stop()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        
        self.lbl_status_icon.setText("⏸️")
        self.lbl_status_val.setText("Inactivo")
        self.status_banner.setStyleSheet("background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 4px;")
        self.lbl_active_wf.setText("Ninguno")
        self.lbl_active_mode.setText("-")
        self.lbl_active_channel.setText("-")
        self.badge_system.setText("● Listo")
        self.badge_system.setStyleSheet("background-color: #f1f5f9; color: #475569; border: 1px solid #cbd5e1; border-radius: 12px; padding: 4px 12px; font-size: 9pt; font-weight: 700;")
        
        if isinstance(result, str):
            self.add_log(f"❌ Error en la ejecución:\n{result}", level="error")
            QMessageBox.critical(self, "Error de Ejecución", f"La ejecución falló con el error:\n{result}")
        elif isinstance(result, dict) and result.get("status") == "stopped":
            self.add_log("🛑 Ejecución detenida por el usuario.", level="warn")
            QMessageBox.warning(self, "Detenido", "Ejecución detenida por el usuario.")
        else:
            self.add_log("✅ La ejecución ha finalizado con éxito.", level="success")
            QMessageBox.information(self, "Completado", "La ejecución ha finalizado con éxito.")

        if "loop" in prev_wf.lower():
            self.add_log("📊 Ciclo en bucle finalizado. Notificación y resumen de gestión del día enviados a Telegram.", level="info")
            
        self._current_is_loop = False
        cfg_dir = RPA_ROOT / "config"
        try:
            stop_after_file = cfg_dir / "stop_after_case.txt"
            if stop_after_file.exists():
                stop_after_file.unlink()
        except Exception:
            pass
        self.worker = None
        self._set_local_execution_state(False)
        self._update_buttons_state()

    def is_loop_running(self) -> bool:
        """Verifica si actualmente se encuentra en ejecución un flujo en loop (local o en segundo plano)."""
        if getattr(self, '_current_is_loop', False):
            return True

        if self.worker and self.worker.isRunning():
            if hasattr(self.worker, 'is_loop_running') and self.worker.is_loop_running():
                return True
            wf = getattr(self.worker, 'workflow', None)
            if wf:
                if "loop" in getattr(wf, 'name', '').lower():
                    return True
                for n in getattr(wf, 'nodes', []):
                    if getattr(n, 'type', None) in ('loop', 'LoopNode') or str(getattr(n, 'type', '')).lower() == 'loop':
                        return True
            if hasattr(self.worker, 'executor') and self.worker.executor:
                if getattr(self.worker.executor, 'is_in_loop', False):
                    return True
                if hasattr(self.worker.executor, 'is_loop_workflow') and self.worker.executor.is_loop_workflow():
                    return True

        config_dir = RPA_ROOT / "config"
        state_file = config_dir / "execution_state.json"
        if state_file.exists():
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                if state.get("is_running", False):
                    if state.get("is_loop", False):
                        return True
                    wf_name = state.get("workflow", "").lower()
                    if "loop" in wf_name:
                        return True
                    wf_candidate = RPA_ROOT / "workflows" / state.get("workflow", "")
                    if not wf_candidate.exists():
                        wf_candidate = wf_candidate.with_suffix(".json")
                    if wf_candidate.exists():
                        try:
                            with open(wf_candidate, 'r', encoding='utf-8') as wf_f:
                                wf_data = json.load(wf_f)
                            for node_data in wf_data.get("nodes", []):
                                if node_data.get("type") == "loop":
                                    return True
                        except Exception:
                            pass
            except Exception:
                pass

        return False

    def detener_a_siguiente_ejecucion(self):
        """Solicita detener el bucle de manera segura al finalizar el caso actual."""
        config_dir = RPA_ROOT / "config"
        config_dir.mkdir(parents=True, exist_ok=True)

        if self.worker and self.worker.isRunning():
            if hasattr(self.worker, 'stop_after_current_case'):
                self.worker.stop_after_current_case()
            elif hasattr(self.worker, 'executor') and self.worker.executor:
                self.worker.executor.stop_after_current_case()

        try:
            stop_after_file = config_dir / "stop_after_case.txt"
            with open(stop_after_file, "w", encoding="utf-8") as f:
                f.write("stop_after_case")
        except Exception as e:
            print(f"Error escribiendo stop_after_case.txt: {e}")

        self.add_log("⏳ Solicitud registrada: el bucle se detendrá al finalizar el caso actual.", level="warn")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setText("⏳ Deteniendo tras caso actual...")
        self.lbl_status_icon.setText("🟡")
        self.lbl_status_val.setText("Deteniendo tras caso...")

    def detener_inmediatamente(self):
        """Detiene la ejecución actual del worker local o del servicio en background de forma inmediata."""
        config_dir = RPA_ROOT / "config"
        config_dir.mkdir(parents=True, exist_ok=True)

        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.add_log("⏹️ Solicitando detención inmediata de worker local...", level="warn")
            self.btn_stop.setEnabled(False)

        try:
            stop_after_file = config_dir / "stop_after_case.txt"
            if stop_after_file.exists():
                stop_after_file.unlink()
        except Exception:
            pass

        try:
            with open(config_dir / "stop_signal.txt", "w", encoding="utf-8") as f:
                f.write("stop")
            self.add_log("🛑 Señal de parada enviada (stop_signal.txt).", level="warn")
            self.btn_stop.setEnabled(False)
        except Exception as e:
            print(f"Error escribiendo stop_signal.txt: {e}")

    def detiene_todo(self):
        """Detiene la ejecución actual. Si hay un loop corriendo, pregunta si se desea
        detenerlo a la siguiente ejecución o en este mismo instante."""
        is_busy = bool(self.is_bg_running or (self.worker and self.worker.isRunning()))
        if not is_busy:
            config_dir = RPA_ROOT / "config"
            state_file = config_dir / "execution_state.json"
            if state_file.exists():
                try:
                    with open(state_file, 'r', encoding='utf-8') as f:
                        is_busy = json.load(f).get("is_running", False)
                except Exception:
                    pass

        if not is_busy:
            return

        if self.is_loop_running():
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("Detener Flujo en Loop")
            msg_box.setText("<h3>¿Cómo desea detener el flujo en bucle?</h3>")
            msg_box.setInformativeText(
                "Se detectó que hay un workflow ejecutándose en bucle (Loop).\n\n"
                "• <b>A la siguiente ejecución:</b> Permite terminar el caso actual y detiene el flujo antes del siguiente ciclo.\n"
                "• <b>En este mismo instante:</b> Fuerza la detención inmediata interrumpiendo el proceso actual."
            )
            msg_box.setIcon(QMessageBox.Icon.Question)

            btn_siguiente = msg_box.addButton("⏳ A la siguiente ejecución", QMessageBox.ButtonRole.ActionRole)
            btn_inmediato = msg_box.addButton("🛑 En este mismo instante", QMessageBox.ButtonRole.DestructiveRole)
            btn_cancelar = msg_box.addButton("Cancelar", QMessageBox.ButtonRole.RejectRole)

            msg_box.setDefaultButton(btn_siguiente)
            msg_box.exec()

            clicked = msg_box.clickedButton()
            if clicked == btn_cancelar:
                return
            elif clicked == btn_siguiente:
                self.detener_a_siguiente_ejecucion()
                return

        self.detener_inmediatamente()

    def rehabilitar_ultimo_registro(self):
        reply = QMessageBox.question(
            self, 
            "Confirmar Acción Crítica", 
            "¿Está seguro de que desea rehabilitar el último registro?\nEsto modificará el estado a 'En Proceso' en la base de datos MySQL.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            import mysql.connector
            
            db_cfg = self.config.get("database", {
                'host': 'localhost',
                'user': 'root',
                'password': '',
                'database': 'ris'
            })
            
            conn = mysql.connector.connect(**db_cfg, connect_timeout=5)
            cursor = conn.cursor()
            
            query = """
            UPDATE ris.registro_acciones 
            SET estado = 'En Proceso' 
            WHERE id = (SELECT max_id FROM (SELECT MAX(id) as max_id FROM ris.registro_acciones) as t)
            """
            cursor.execute(query)
            filas_afectadas = cursor.rowcount
            conn.commit()
            
            cursor.close()
            conn.close()
            
            if filas_afectadas > 0:
                self.add_log("🔄 Último registro rehabilitado en la base de datos ('En Proceso').", level="success")
                QMessageBox.information(self, "Éxito", "Se ha rehabilitado el último registro correctamente ('En Proceso').")
            else:
                self.add_log("⚠️ No se encontró ningún registro para rehabilitar.", level="warn")
                QMessageBox.warning(self, "Aviso", "No se encontró ningún registro para actualizar o ya estaba en proceso.")
                
        except Exception as e:
            self.add_log(f"❌ Error al conectar a la BD: {e}", level="error")
            QMessageBox.critical(self, "Error de Base de Datos", f"No se pudo conectar a la base de datos o ejecutar la consulta:\n{e}")
            import traceback
            traceback.print_exc()
