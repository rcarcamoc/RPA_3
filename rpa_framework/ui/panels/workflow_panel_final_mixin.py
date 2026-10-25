"""
Mixin para operaciones de archivo, validación, ejecución y consola de logs de WorkflowPanelFinal.
Extraído de ui/workflow_panel_final.py.
"""

import os
import re
import shutil
import uuid
from pathlib import Path
from datetime import datetime
from PyQt6.QtWidgets import QMessageBox, QInputDialog, QApplication

from core.models import Workflow, Node, NodeType, ActionNode, DecisionNode, LoopNode, WorkflowNode
from core.validator import WorkflowValidator
from ui.workflow_commands import AddNodeCommand, DeleteNodeCommand, ConnectionCommand
from ui.workers.workflow_executor_worker import WorkflowExecutorWorker
from ui.canvas.final_widgets import LogWindowFinal


class WorkflowPanelFinalMixin:
    """Mixin que provee comandos, gestión de archivos, validación, ejecución y logs a WorkflowPanelFinal."""

    # --- LOGICA DE COMANDOS Y SEÑALES ---

    def create_node_from_palette(self, node_def, pos):
        """Callback ejecutado por DropEvent del canvas"""
        if not self.current_workflow:
            self.create_new_workflow()
            
        new_id = f"n_{str(uuid.uuid4())[:6]}"
        ntype = NodeType(node_def.node_type_enum)
        defaults = node_def.default_values.copy()
        
        if ntype == NodeType.DATABASE:
            from core.database_node import DatabaseNode
            node = DatabaseNode(id=new_id, label=node_def.name, position={"x": pos.x(), "y": pos.y()}, **defaults)
        elif ntype == NodeType.ANNOTATION:
            from core.annotation_node import AnnotationNode
            node = AnnotationNode(id=new_id, label=node_def.name, position={"x": pos.x(), "y": pos.y()}, **defaults)
        elif ntype == NodeType.DECISION:
             node = DecisionNode(id=new_id, label=node_def.name, position={"x": pos.x(), "y": pos.y()}, **defaults)
        elif ntype == NodeType.LOOP:
             node = LoopNode(id=new_id, label=node_def.name, position={"x": pos.x(), "y": pos.y()}, **defaults)
        elif ntype == NodeType.DELAY:
             from core.delay_node import DelayNode
             node = DelayNode(id=new_id, label=node_def.name, position={"x": pos.x(), "y": pos.y()}, **defaults)
        elif ntype == NodeType.START:
             node = Node(id=new_id, type=NodeType.START, label="Inicio", position={"x": pos.x(), "y": pos.y()})
        elif ntype == NodeType.END:
             node = Node(id=new_id, type=NodeType.END, label="Fin", position={"x": pos.x(), "y": pos.y()})
        elif ntype == NodeType.WORKFLOW:
             node = WorkflowNode(id=new_id, label=node_def.name, position={"x": pos.x(), "y": pos.y()}, **defaults)
        else:
             node = ActionNode(id=new_id, label=node_def.name, position={"x": pos.x(), "y": pos.y()}, **defaults)
             
        cmd = AddNodeCommand(self.current_workflow, node, self)
        self.undo_stack.push(cmd)
        
        self.canvas.highlight_node(node.id)
        self.on_node_selected(node)
        self.set_dirty(True)

    def on_node_selected(self, node):
        if not node:
            self.properties_panel.hide()
            return
        self.properties_panel.load_node(node)
        self.properties_panel.show()

    def on_node_updated(self, node):
        """Llamado en autoguardado del PropertiesPanel"""
        self.canvas.load_workflow(self.current_workflow)
        self.canvas.highlight_node(node.id)
        self.set_dirty(True)

    def on_node_deleted_req(self, node):
        cmd = DeleteNodeCommand(self.current_workflow, node, self)
        self.undo_stack.push(cmd)
        self.properties_panel.hide()
        self.set_dirty(True)

    def on_connection_created(self, from_id, to_id):
        if not self.current_workflow:
            return
        cmd = ConnectionCommand(self.current_workflow, from_id, to_id, self, is_add=True)
        self.undo_stack.push(cmd)
        self.set_dirty(True)

    def on_connection_deleted(self, from_id, to_id):
        if not self.current_workflow:
            return
        cmd = ConnectionCommand(self.current_workflow, from_id, to_id, self, is_add=False)
        self.undo_stack.push(cmd)
        self.set_dirty(True)

    # --- ARCHIVO Y WORKFLOWS ---

    def create_new_workflow(self):
        if self._is_dirty:
            ret = QMessageBox.question(
                self, "Cambios sin guardar",
                "¿Desea crear un nuevo workflow? Los cambios no guardados se perderán.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if ret == QMessageBox.StandardButton.No:
                return
                
        self.current_workflow = Workflow(id="workflow_nuevo", name="Nuevo Workflow")
        start = Node(id="start_node", type=NodeType.START, label="Inicio", position={"x": 100, "y": 200})
        end = Node(id="end_node", type=NodeType.END, label="Fin", position={"x": 500, "y": 200})
        self.current_workflow.nodes.extend([start, end])
        
        self.canvas.load_workflow(self.current_workflow)
        self.properties_panel.hide()
        self.undo_stack.clear()
        self.set_dirty(False)
        self.append_log("Nuevo workflow inicializado.", "SUCCESS")

    def save_workflow(self):
        if not self.current_workflow:
            return
            
        name = self.current_workflow.name
        if name == "Nuevo Workflow" or self.current_workflow.id == "workflow_nuevo":
            new_name, ok = QInputDialog.getText(self, "Guardar", "Nombre del Workflow:")
            if ok and new_name.strip():
                self.current_workflow.name = new_name.strip()
                self.current_workflow.id = re.sub(r'[^a-zA-Z0-9]', '_', new_name.lower())
                name = self.current_workflow.name
            else:
                return
                
        existing_path = self._find_workflow_file(name)
        if not existing_path:
            from utils.paths import WORKFLOWS_DIR
            WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)
            filepath = WORKFLOWS_DIR / f"{name}.json"
        else:
            filepath = existing_path
        
        if filepath.exists() and self.current_workflow.id == "workflow_nuevo":
            ret = QMessageBox.question(self, "Sobrescribir", f"El archivo '{name}.json' ya existe. ¿Desea sobrescribirlo?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if ret == QMessageBox.StandardButton.No:
                return
                
        try:
            self.current_workflow.to_json(str(filepath))
            self.set_dirty(False)
            self.append_log(f"Workflow guardado en: {filepath}", "SUCCESS")
            self.load_workflow_list()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo guardar el archivo:\n{e}")

    def on_workflow_combo_changed(self, index):
        if getattr(self, '_loading_workflow_list', False) or index <= 0:
            return
            
        name = self.workflow_selector.itemText(index)
        if "Sin Guardar" in name:
            return
            
        if name.startswith("📄 "):
            name = name[2:]
            
        if self._is_dirty:
            ret = QMessageBox.question(
                self, "Cambios sin guardar",
                "Hay cambios sin guardar en el workflow actual. ¿Desea cargar otro?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if ret == QMessageBox.StandardButton.No:
                self.workflow_selector.blockSignals(True)
                self.workflow_selector.setCurrentIndex(self.prev_combo_index)
                self.workflow_selector.blockSignals(False)
                return
                
        target_path = self._find_workflow_file(name)
        if target_path and target_path.exists():
            try:
                self.current_workflow = Workflow.from_json(str(target_path))
                self.canvas.load_workflow(self.current_workflow)
                self.properties_panel.hide()
                self.undo_stack.clear()
                self.set_dirty(False)
                self.prev_combo_index = index
                self.append_log(f"Workflow '{name}' cargado.", "SUCCESS")
                self.validate_workflow(silent=True)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error cargando el workflow:\n{e}")

    def _get_workflow_dirs(self):
        from utils.paths import WORKFLOWS_DIR
        dirs = [WORKFLOWS_DIR]
        for p in [Path("rpa_framework/workflows"), Path("workflows")]:
            if p.exists() and p.resolve() not in [d.resolve() for d in dirs]:
                dirs.append(p)
        return dirs

    def _find_workflow_file(self, name):
        for d in self._get_workflow_dirs():
            candidate = d / f"{name}.json"
            if candidate.exists():
                return candidate
        return None

    def load_workflow_list(self):
        self._loading_workflow_list = True
        self.workflow_selector.clear()
        self.workflow_selector.addItem("--- Seleccionar Workflow ---")
        
        active_index = 0
        try:
            found_files = {}
            for d in self._get_workflow_dirs():
                if d.exists():
                    for f in d.glob("*.json"):
                        if f.stem not in found_files:
                            found_files[f.stem] = f
                            
            for i, wf_name in enumerate(sorted(found_files.keys(), key=lambda s: s.lower())):
                self.workflow_selector.addItem(f"📄 {wf_name}")
                if self.current_workflow and self.current_workflow.name == wf_name:
                    active_index = i + 1
        except Exception as e:
            print(f"Error loading workflow list: {e}")
            
        if self.current_workflow and (self.current_workflow.id == "workflow_nuevo" or self.current_workflow.name == "Nuevo Workflow"):
            self.workflow_selector.addItem("📄 Nuevo Workflow (Sin Guardar)")
            active_index = self.workflow_selector.count() - 1
            
        self.workflow_selector.setCurrentIndex(active_index)
        self.prev_combo_index = active_index
        self._loading_workflow_list = False

    def duplicate_active_workflow(self):
        if not self.current_workflow or self.current_workflow.id == "workflow_nuevo":
            QMessageBox.warning(self, "Aviso", "No hay un workflow guardado activo para duplicar.")
            return
        self.duplicate_workflow(self.current_workflow.name)

    def delete_active_workflow(self):
        if not self.current_workflow:
            return
        if self.current_workflow.id == "workflow_nuevo":
            self.current_workflow = None
            self.canvas.scene.clear()
            self.properties_panel.hide()
            self.set_dirty(False)
            self.load_workflow_list()
            return
        self.delete_workflow_file(self.current_workflow.name)

    def duplicate_workflow(self, name):
        new_name, ok = QInputDialog.getText(self, "Duplicar Workflow", "Nombre para el duplicado:")
        if ok and new_name.strip():
            new_name = new_name.strip()
            try:
                src_path = self._find_workflow_file(name)
                if not src_path:
                    raise FileNotFoundError(f"No se encontró el workflow original '{name}.json'")
                from utils.paths import WORKFLOWS_DIR
                dst_path = WORKFLOWS_DIR / f"{new_name}.json"
                shutil.copy(str(src_path), str(dst_path))
                dup_wf = Workflow.from_json(str(dst_path))
                dup_wf.name = new_name
                dup_wf.id = re.sub(r'[^a-zA-Z0-9]', '_', new_name.lower())
                dup_wf.to_json(str(dst_path))
                
                self.load_workflow_list()
                self.append_log(f"Workflow duplicado como '{new_name}'", "SUCCESS")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo duplicar el workflow:\n{e}")

    def delete_workflow_file(self, name):
        ret = QMessageBox.question(self, "Eliminar Workflow", 
                                 f"¿Estás seguro de que deseas eliminar permanentemente '{name}.json'?",
                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ret == QMessageBox.StandardButton.Yes:
            try:
                found_path = self._find_workflow_file(name)
                if found_path and found_path.exists():
                    os.remove(str(found_path))
                if self.current_workflow and self.current_workflow.name == name:
                    self.current_workflow = None
                    self.canvas.scene.clear()
                    self.properties_panel.hide()
                    self.set_dirty(False)
                self.load_workflow_list()
                self.append_log(f"Workflow '{name}' eliminado.", "WARNING")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo eliminar el archivo:\n{e}")

    # --- VALIDACIÓN ---

    def validate_workflow(self, silent=False):
        """Valida que el workflow no tenga errores lógicos o referencias rotas"""
        if not self.current_workflow:
            return True
            
        results = WorkflowValidator.validate(self.current_workflow)
        self.canvas.clear_highlights()
        
        for item in self.canvas.node_items.values():
            item.set_warning("")
            
        errors = [r for r in results if r.get("severity") == "error"]
        warnings_list = [r for r in results if r.get("severity") == "warning"]
        
        if errors:
            self.append_log(f"⚠️ Validación fallida: {len(errors)} errores detectados.", "ERROR")
            for err in errors:
                nid = err.get("node_id")
                msg = err.get("message")
                self.append_log(f"   • Nodo [{nid or 'Global'}]: {msg}", "ERROR")
        
        if warnings_list:
            if not errors:
                self.append_log(f"⚠️ Validación con {len(warnings_list)} advertencias detectadas.", "WARNING")
            for warn in warnings_list:
                nid = warn.get("node_id")
                msg = warn.get("message")
                self.append_log(f"   • Nodo [{nid or 'Global'}]: {msg}", "WARNING")
        
        for err in errors:
            nid = err.get("node_id")
            msg = err.get("message")
            if nid and nid in self.canvas.node_items:
                self.canvas.node_items[nid].set_warning(msg)
                    
        for warn in warnings_list:
            nid = warn.get("node_id")
            msg = warn.get("message")
            if nid and nid in self.canvas.node_items:
                self.canvas.node_items[nid].set_warning(msg)
                    
        if errors:
            if not silent:
                err_text = "\n".join([f"- {e.get('message')}" for e in errors])
                QMessageBox.warning(self, "Validación", f"El workflow tiene errores críticos:\n{err_text}\n\nRevisa los nodos marcados en rojo.")
            return False
        else:
            if not silent:
                self.append_log("✅ Validación exitosa. Sin errores críticos.", "SUCCESS")
                QMessageBox.information(self, "Validación", "El workflow es válido y está listo para ejecutarse.")
            return True

    # --- EJECUCIÓN ---

    def execute_workflow(self):
        if not self.current_workflow:
            return
        
        if not self.validate_workflow(silent=True):
            ret = QMessageBox.question(self, "Confirmar ejecución", 
                                     "El workflow tiene errores. ¿Desea ejecutarlo de todas formas?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if ret == QMessageBox.StandardButton.No:
                return

        self.append_log("🚀 Iniciando ejecución...", "SUCCESS")
        
        steps_total = len(self.current_workflow.nodes)
        self.progress_bar.setMaximum(steps_total)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.progress_bar.setFormat("Inicializando... %p%")
        
        if hasattr(self, 'worker') and self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(1500)
            
        self.worker = WorkflowExecutorWorker(self.current_workflow)
        self.worker.log_update.connect(self.process_executor_log)
        self.worker.node_started.connect(lambda nid: self.canvas.set_execution_highlight(nid, True))
        self.worker.node_finished.connect(lambda nid: self.canvas.set_execution_highlight(nid, False))
        self.worker.finished.connect(self.on_execution_finished)
        self.worker.error.connect(self.on_execution_finished)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()
        
        self.act_run.setEnabled(False)
        self.act_stop.setEnabled(True)

    def stop_workflow(self):
        if not (hasattr(self, 'worker') and self.worker and self.worker.isRunning()):
            return

        is_loop = False
        if hasattr(self.worker, 'is_loop_running'):
            is_loop = self.worker.is_loop_running()
        elif self.current_workflow:
            is_loop = any(getattr(n, 'type', None) in ('loop', 'LoopNode') or str(getattr(n, 'type', '')).lower() == 'loop' for n in getattr(self.current_workflow, 'nodes', [])) or "loop" in getattr(self.current_workflow, 'name', '').lower()

        if is_loop:
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
                if hasattr(self.worker, 'stop_after_current_case'):
                    self.worker.stop_after_current_case()
                self.act_stop.setEnabled(False)
                self.append_log("⏳ Solicitud registrada: se detendrá el bucle al finalizar el caso actual.", "WARNING")
                return

        self.worker.stop()
        self.act_stop.setEnabled(False)
        self.append_log("🛑 Detención inmediata solicitada.", "WARNING")

    def on_execution_finished(self, result):
        self.progress_bar.setVisible(False)
        self.act_run.setEnabled(True)
        self.act_stop.setEnabled(False)
        
        for item in self.canvas.node_items.values():
            item.set_executing(False)
            
        if isinstance(result, str):
            self.append_log(f"❌ Ejecución interrumpida por error: {result}", "ERROR")
        elif isinstance(result, dict) and result.get("status") == "stopped":
            self.append_log("⏹️ Ejecución detenida.", "WARNING")
        else:
            self.append_log("✅ Ejecución finalizada con éxito.", "SUCCESS")
            
        self.worker = None

    # --- LOGS / TERMINAL ---

    def process_executor_log(self, raw_message):
        """Procesa y limpia logs del worker en tiempo real"""
        level = "INFO"
        if "[ERROR]" in raw_message or "❌" in raw_message:
            level = "ERROR"
        elif "[WARNING]" in raw_message or "⚠️" in raw_message:
            level = "WARNING"
        elif "[SUCCESS]" in raw_message or "✅" in raw_message:
            level = "SUCCESS"
            
        if "📍 Nodo actual:" in raw_message:
            node_label = raw_message.split("📍 Nodo actual:")[-1].strip()
            val = self.progress_bar.value() + 1
            self.progress_bar.setValue(min(val, self.progress_bar.maximum()))
            self.progress_bar.setFormat(f"Ejecutando: {node_label} (%p%)")
            
        clean_msg = raw_message
        for tag in ["[INFO]", "[ERROR]", "[WARNING]", "[SUCCESS]"]:
            if clean_msg.startswith(tag):
                clean_msg = clean_msg[len(tag):].strip()
                
        self.append_log(clean_msg, level)

    def append_log(self, message: str, level: str = "INFO"):
        noise = ["======", "Categorical units", "Dashboard actualizado"]
        if any(n in message for n in noise):
            return
            
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.raw_logs_cache.append((timestamp, message, level))
        self.render_log_entry(timestamp, message, level)

    def render_log_entry(self, timestamp, message, level):
        filter_idx = self.log_filter.currentIndex()
        if filter_idx == 1 and level != "SUCCESS":
            return
        if filter_idx == 2 and level != "WARNING":
            return
        if filter_idx == 3 and level != "ERROR":
            return
        
        colors = {
            "INFO": "#e2e8f0",
            "SUCCESS": "#34d399",
            "WARNING": "#fb923c",
            "ERROR": "#f87171"
        }
        color = colors.get(level, "#e2e8f0")
        formatted = f'<span style="color: {color};">[{timestamp}] {message}</span>'
        
        self.log_widget.append(formatted)
        self.log_widget.verticalScrollBar().setValue(
            self.log_widget.verticalScrollBar().maximum()
        )
        
        if self.log_window and self.log_window.isVisible():
            self.log_window.append_html(formatted)

    def refilter_logs(self):
        """Vuelve a renderizar la consola de logs aplicando el filtro seleccionado"""
        self.log_widget.clear()
        if self.log_window:
            self.log_window.clear()
            
        for timestamp, message, level in self.raw_logs_cache:
            self.render_log_entry(timestamp, message, level)

    def copy_log_to_clipboard(self):
        text = self.log_widget.toPlainText()
        if text.strip():
            QApplication.clipboard().setText(text)
            self.append_log("Logs copiados al portapapeles.", "SUCCESS")

    def clear_log(self):
        self.log_widget.clear()
        self.raw_logs_cache.clear()
        if self.log_window:
            self.log_window.clear()
        self.append_log("Consola limpia.", "INFO")

    def show_floating_log(self):
        if not self.log_window:
            self.log_window = LogWindowFinal(self)
        
        self.log_window.set_html(self.log_widget.toHtml())
        self.log_window.show()
        self.log_window.raise_()
