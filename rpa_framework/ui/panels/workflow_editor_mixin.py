"""
Mixin para edición de nodos, archivos y conexiones de WorkflowPanel.
Extraído de ui/workflow_panel.py.
"""

import json
import shutil
from pathlib import Path
from datetime import datetime
from PyQt6.QtWidgets import QListWidgetItem, QMessageBox, QFileDialog, QInputDialog
from PyQt6.QtCore import Qt

from core.models import Workflow, Node, NodeType, ActionNode, DecisionNode, LoopNode, Edge
from core.validator import WorkflowValidator
from ui.workflow_commands import (
    AddNodeCommand, DeleteNodeCommand, ConnectionCommand, ModifyPropertyCommand
)
from ui.canvas.legacy_items import NodeGraphicsItem


class WorkflowEditorMixin:
    """Mixin que provee gestión de archivos, scripts, nodos y conexiones a WorkflowPanel."""

    def load_workflow_list(self):
        """Carga lista de workflows desde el directorio."""
        self.workflow_list.clear()
        
        workflows_dir = Path("workflows")
        if not workflows_dir.exists():
            workflows_dir.mkdir(parents=True)
        
        json_files = sorted(
            list(workflows_dir.glob("*.json")), 
            reverse=True,
            key=lambda p: p.stat().st_mtime
        )
        
        for p in json_files:
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    name = data.get('name', p.stem)
                    item = QListWidgetItem(f"{name} ({p.name})")
                    item.setData(Qt.ItemDataRole.UserRole, str(p))
                    self.workflow_list.addItem(item)
            except Exception as e:
                self.log(f"Error cargando {p.name}: {e}")
    
    def load_script_list(self):
        """Carga lista de scripts disponibles para el combo."""
        current_text = self.prop_script.currentText()
        
        try:
            self.prop_script.currentTextChanged.disconnect(self.on_script_selected)
        except Exception:
            pass
        
        self.prop_script.clear()
        
        from utils.paths import get_all_scripts
        scripts_found = get_all_scripts(include_subdirs=True)
        
        script_paths = [str(script).replace("\\", "/") for script in scripts_found]
        
        if script_paths:
            self.prop_script.addItems(script_paths)
        
        self.prop_script.addItem("📁 Examinar...")
        self.prop_script.currentTextChanged.connect(self.on_script_selected)
        
        if current_text and current_text != "📁 Examinar...":
            self.prop_script.setCurrentText(current_text)
    
    def on_script_selected(self, text: str):
        """Maneja la selección de script, incluyendo 'Examinar...'"""
        if text == "📁 Examinar...":
            self.browse_for_script()
    
    def browse_for_script(self):
        """Abre el selector de archivos para elegir un script externo."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar Script Python",
            "", "Python Files (*.py);;All Files (*.*)"
        )
        
        if not file_path:
            self.prop_script.setCurrentIndex(-1)
            return
        
        file_path = Path(file_path)
        scripts_dir = Path("scripts")
        
        try:
            file_path.relative_to(scripts_dir.resolve())
            rel_path = str(file_path).replace("\\", "/")
            self.prop_script.setCurrentText(rel_path)
            return
        except ValueError:
            pass
        
        reply = QMessageBox.question(
            self, "Copiar Script",
            f"El archivo está fuera de la carpeta 'scripts/'.\n\n"
            f"¿Deseas copiarlo a la carpeta de scripts?\n\n"
            f"Archivo: {file_path.name}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
        )
        
        if reply == QMessageBox.StandardButton.Cancel:
            self.prop_script.setCurrentIndex(-1)
            return
        
        if reply == QMessageBox.StandardButton.Yes:
            scripts_dir.mkdir(parents=True, exist_ok=True)
            dest_path = scripts_dir / file_path.name
            
            if dest_path.exists():
                overwrite = QMessageBox.question(
                    self, "Archivo existente",
                    f"Ya existe '{file_path.name}' en scripts/.\n¿Sobrescribir?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if overwrite != QMessageBox.StandardButton.Yes:
                    self.prop_script.setCurrentIndex(-1)
                    return
            
            shutil.copy2(file_path, dest_path)
            self.log(f"Script copiado: {dest_path}")
            
            self.load_script_list()
            self.prop_script.setCurrentText(str(dest_path).replace("\\", "/"))
        else:
            self.prop_script.setCurrentText(str(file_path).replace("\\", "/"))
    
    def generate_node_id(self) -> str:
        """Genera un ID único para un nuevo nodo."""
        if not self.current_workflow:
            return "n1"
        
        max_num = 0
        for node in self.current_workflow.nodes:
            if node.id.startswith("n") and node.id[1:].isdigit():
                num = int(node.id[1:])
                if num > max_num:
                    max_num = num
        
        return f"n{max_num + 1}"
    
    def on_node_selected(self, node: Node):
        """Muestra info del nodo seleccionado en el panel de propiedades."""
        self.selected_node = node
        self.btn_save.setEnabled(True)
        self.btn_delete_node.setEnabled(True)
        self.btn_apply.setEnabled(True)
        
        self.prop_id.setText(node.id)
        self.prop_label.setText(node.label)
        self.prop_type.setCurrentText(node.type.value)
        
        self.prop_script.clear()
        self.prop_condition.clear()
        self.prop_true_path.clear()
        self.prop_false_path.clear()
        self.prop_iterations.clear()
        self.prop_next_node.clear()
        
        if isinstance(node, ActionNode):
            self.prop_script.setCurrentText(node.script)
        elif isinstance(node, DecisionNode):
            self.prop_condition.setText(node.condition)
            self.prop_true_path.setText(node.true_path or "")
            self.prop_false_path.setText(node.false_path or "")
        elif isinstance(node, LoopNode):
            self.prop_script.setCurrentText(node.script)
            self.prop_iterations.setText(node.iterations)
        elif node.type == NodeType.DATABASE:
            from core.database_node import DatabaseNode
            if isinstance(node, DatabaseNode):
                self.prop_db_host.setText(node.host)
                self.prop_db_port.setText(str(node.port))
                self.prop_db_user.setText(node.user)
                self.prop_db_password.setText(node.password)
                self.prop_db_database.setText(node.database)
                self.prop_db_query.setPlainText(node.query)
                self.prop_db_operation.setCurrentText(node.operation)
                self.prop_db_result_var.setText(node.result_var)
        elif node.type == NodeType.ANNOTATION:
            from core.annotation_node import AnnotationNode
            if isinstance(node, AnnotationNode):
                self.prop_annotation_text.setPlainText(node.text)
                color_map_reverse = {
                    "#ffffcc": "Amarillo",
                    "#cce5ff": "Azul",
                    "#ffccf2": "Rosa",
                    "#ccffcc": "Verde"
                }
                color_name = color_map_reverse.get(node.color, "Amarillo")
                self.prop_annotation_color.setCurrentText(color_name)
        
        if self.current_workflow and not isinstance(node, DecisionNode) and node.type != NodeType.ANNOTATION:
            next_node_id = self.current_workflow.get_next_node(node.id)
            if next_node_id:
                self.prop_next_node.setText(next_node_id)
        
        self.on_type_changed(node.type.value)
        self.log(f"Nodo seleccionado: {node.label} ({node.type.value})")

    def create_new_workflow(self):
        """Crea un nuevo workflow vacio."""
        name, ok = QInputDialog.getText(self, "Nuevo Workflow", "Nombre del workflow:")
        if not ok or not name:
            return
        
        workflow_id = f"wf_{name.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        self.current_workflow = Workflow(
            id=workflow_id,
            name=name,
            description="Nuevo workflow",
            nodes=[
                Node(id="start", type=NodeType.START, label="Inicio", position={"x": 200, "y": 50}),
                Node(id="end", type=NodeType.END, label="Fin", position={"x": 200, "y": 250})
            ],
            edges=[
                Edge(from_node="start", to_node="end")
            ],
            variables={}
        )
        
        self.canvas.load_workflow(self.current_workflow)
        self.btn_execute.setEnabled(True)
        self.btn_save.setEnabled(True)
        self.btn_validate.setEnabled(True)
        self.var_text.setText("{}")
        self.status_label.setText(f"Nuevo: {name}")
        
        self.log(f"Nuevo workflow creado: {name}")
        self.log("  Agrega nodos haciendo click en el canvas y guardando")
        
        QMessageBox.information(
            self, "Workflow Creado",
            f"Workflow '{name}' creado.\n\n"
            "Para agregar nodos:\n"
            "1. Edita el archivo JSON directamente\n"
            "2. O usa 'Guardar' para guardarlo y editarlo despues"
        )
    
    def save_workflow(self):
        """Guarda el workflow actual."""
        if not self.current_workflow:
            QMessageBox.warning(self, "Aviso", "No hay workflow para guardar")
            return
        
        try:
            var_text = self.var_text.toPlainText().strip()
            if var_text:
                self.current_workflow.variables = json.loads(var_text)
        except json.JSONDecodeError as e:
            QMessageBox.warning(self, "Error", f"Variables JSON invalido:\n{e}")
            return
        
        workflows_dir = Path("workflows")
        workflows_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"{self.current_workflow.id}.json"
        filepath = workflows_dir / filename
        
        try:
            self.current_workflow.to_json(str(filepath))
            self.log(f"Workflow guardado: {filepath}")
            QMessageBox.information(self, "Guardado", f"Workflow guardado en:\n{filepath}")
            self.load_workflow_list()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error guardando workflow:\n{e}")
            self.log(f"Error guardando: {e}")
    
    def on_workflow_selected(self, item: QListWidgetItem):
        """Carga el workflow seleccionado con validacion robusta."""
        if not item:
            return
        
        filepath = item.data(Qt.ItemDataRole.UserRole)
        if not filepath:
            self.log("Error: No se pudo obtener la ruta del workflow")
            return
        
        if not Path(filepath).exists():
            QMessageBox.warning(self, "Archivo no encontrado", 
                f"El archivo no existe:\n{filepath}\n\nRecargando lista...")
            self.load_workflow_list()
            return
        
        try:
            self.current_workflow = Workflow.from_json(filepath)
            self.selected_node = None
            self.canvas.load_workflow(self.current_workflow)
            self.btn_execute.setEnabled(True)
            self.btn_save.setEnabled(True)
            self.btn_validate.setEnabled(True)
            self.btn_add_node.setEnabled(True)
            self.status_label.setText(f"Cargado: {self.current_workflow.name}")
            self.status_label.setStyleSheet("color: #28a745; font-weight: bold;")
            
            self.var_text.setText(json.dumps(self.current_workflow.variables, indent=2))
            self.clear_node_fields()
            
            self.log(f"Workflow cargado: {self.current_workflow.name}")
            self.log(f"  Nodos: {len(self.current_workflow.nodes)}")
            self.log(f"  Conexiones: {len(self.current_workflow.edges)}")
            
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "Error de JSON", f"Archivo JSON invalido:\n{e}")
            self.log(f"Error JSON: {e}")
        except KeyError as e:
            QMessageBox.critical(self, "Error de Estructura", f"Falta campo requerido en JSON:\n{e}")
            self.log(f"Error de estructura: {e}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo cargar el workflow:\n{e}")
            self.log(f"Error: {e}")
            import traceback
            traceback.print_exc()
    
    def clear_node_fields(self):
        """Limpia todos los campos del editor de nodos."""
        if self.current_workflow:
            next_id = self.generate_node_id()
            self.prop_id.setText(next_id)
        else:
            self.prop_id.clear()
        
        self.prop_label.clear()
        self.prop_script.setCurrentIndex(-1)
        self.prop_condition.clear()
        self.prop_true_path.clear()
        self.prop_false_path.clear()
        self.prop_iterations.clear()
        self.prop_next_node.clear()
        self.btn_delete_node.setEnabled(False)
        self.btn_apply.setEnabled(False)
    
    def on_type_changed(self, type_text: str):
        """Muestra/oculta campos segun el tipo de nodo."""
        is_action = type_text == "action"
        is_decision = type_text == "decision"
        is_loop = type_text == "loop"
        
        self.prop_script.setEnabled(is_action or is_loop)
        self.prop_condition.setEnabled(is_decision)
        self.prop_true_path.setEnabled(is_decision)
        self.prop_false_path.setEnabled(is_decision)
        self.prop_iterations.setEnabled(is_loop)
        self.prop_next_node.setEnabled(not is_decision)
    
    def create_node_from_palette(self, node_def, pos):
        """Crea un nodo desde la paleta (Drag & Drop)"""
        node_id = self.generate_node_id()
        
        type_map = {
            'action': NodeType.ACTION,
            'decision': NodeType.DECISION,
            'loop': NodeType.LOOP,
            'database': NodeType.DATABASE,
            'annotation': NodeType.ANNOTATION
        }
        
        node_type = type_map.get(node_def.node_type_enum, NodeType.ACTION)
        
        if node_type == NodeType.DATABASE:
            from core.database_node import DatabaseNode
            new_node = DatabaseNode(
                id=node_id,
                label=node_def.name,
                position={"x": pos.x(), "y": pos.y()},
                **node_def.default_values
            )
        elif node_type == NodeType.ANNOTATION:
            from core.annotation_node import AnnotationNode
            new_node = AnnotationNode(
                id=node_id,
                label=node_def.name,
                position={"x": pos.x(), "y": pos.y()},
                **node_def.default_values
            )
        elif node_type == NodeType.ACTION:
            script = node_def.default_values.get('script', '')
            new_node = ActionNode(
                id=node_id,
                label=node_def.name,
                script=script,
                position={"x": pos.x(), "y": pos.y()}
            )
        elif node_type == NodeType.DECISION:
            condition = node_def.default_values.get('condition', '')
            new_node = DecisionNode(
                id=node_id,
                label=node_def.name,
                condition=condition,
                position={"x": pos.x(), "y": pos.y()}
            )
        elif node_type == NodeType.LOOP:
            new_node = LoopNode(
                id=node_id,
                label=node_def.name,
                iterations=node_def.default_values.get('iterations', '1'),
                position={"x": pos.x(), "y": pos.y()}
            )
        else:
            return

        self.undo_stack.beginMacro(f"Agregar {node_def.name}")
        self.undo_stack.push(AddNodeCommand(self.current_workflow, new_node, self))
        self.undo_stack.endMacro()
        
        self.on_node_selected(new_node)
        self.canvas.scene.clearSelection()
        
    def add_node_interactive(self, node_type_str, pos):
        """Called from context menu"""
        class DummyDef:
            pass
        
        d = DummyDef()
        d.node_type_enum = node_type_str
        d.name = node_type_str.capitalize()
        d.default_values = {}
        
        self.create_node_from_palette(d, pos)

    def add_node(self):
        """Agrega un nodo desde el panel de propiedades (Boton Agregar)."""
        if not self.current_workflow:
            return
        
        node_id = self.prop_id.text().strip() or self.generate_node_id()
        node_label = self.prop_label.text().strip() or f"Node {node_id}"
        node_type = self.prop_type.currentText()
        
        if not node_label:
            node_label = f"Nodo {node_id}"
        
        if self.current_workflow.get_node(node_id):
            QMessageBox.warning(self, "Error", f"Ya existe un nodo con ID '{node_id}'")
            return
        
        max_y = max((n.position.get("y", 0) for n in self.current_workflow.nodes), default=0)
        new_pos = {"x": 200, "y": max_y + 100}
        
        new_node = None
        if node_type == "action":
            new_node = object.__new__(ActionNode)
            new_node.id = node_id
            new_node.label = node_label
            new_node.script = self.prop_script.currentText().strip()
            new_node.type = NodeType.ACTION
            new_node.position = new_pos
        elif node_type == "decision":
            new_node = object.__new__(DecisionNode)
            new_node.id = node_id
            new_node.label = node_label
            new_node.condition = self.prop_condition.text().strip()
            new_node.true_path = self.prop_true_path.text().strip()
            new_node.false_path = self.prop_false_path.text().strip()
            new_node.type = NodeType.DECISION
            new_node.position = new_pos
        elif node_type == "loop":
            new_node = object.__new__(LoopNode)
            new_node.id = node_id
            new_node.label = node_label
            new_node.script = self.prop_script.currentText().strip()
            new_node.iterations = self.prop_iterations.text().strip() or "1"
            new_node.loop_var = "_loop_index"
            new_node.type = NodeType.LOOP
            new_node.position = new_pos
        elif node_type == "database":
            from core.database_node import DatabaseNode
            new_node = DatabaseNode(
                id=node_id,
                label=node_label,
                host=self.prop_db_host.text().strip() or "localhost",
                port=int(self.prop_db_port.text().strip() or "3306"),
                user=self.prop_db_user.text().strip() or "root",
                password=self.prop_db_password.text().strip(),
                database=self.prop_db_database.text().strip(),
                query=self.prop_db_query.toPlainText().strip(),
                operation=self.prop_db_operation.currentText(),
                result_var=self.prop_db_result_var.text().strip() or "db_result",
                position=new_pos
            )
        elif node_type == "annotation":
            from core.annotation_node import AnnotationNode
            color_map = {
                "Amarillo": "#ffffcc",
                "Azul": "#cce5ff",
                "Rosa": "#ffccf2",
                "Verde": "#ccffcc"
            }
            new_node = AnnotationNode(
                id=node_id,
                label=node_label,
                text=self.prop_annotation_text.toPlainText().strip(),
                color=color_map.get(self.prop_annotation_color.currentText(), "#ffffcc"),
                position=new_pos
            )
        else:
            new_node = Node(id=node_id, type=NodeType(node_type), label=node_label, position=new_pos)
        
        self.undo_stack.beginMacro(f"Agregar {node_label}")
        self.undo_stack.push(AddNodeCommand(self.current_workflow, new_node, self))
        
        next_node = self.prop_next_node.text().strip()
        if next_node and node_type != "decision":
            self.undo_stack.push(ConnectionCommand(self.current_workflow, node_id, next_node, self))
        
        self.undo_stack.endMacro()
        
        self.clear_node_fields()
        self.log(f"Nodo agregado: {node_label} ({node_type})")
        
        QMessageBox.information(self, "Nodo Agregado", f"Nodo '{node_label}' agregado.")
    
    def delete_node(self):
        """Elimina el nodo seleccionado (Undoable)."""
        if not self.current_workflow or not hasattr(self, 'selected_node') or not self.selected_node:
            return
        
        node_label = self.selected_node.label
        
        reply = QMessageBox.question(
            self, "Confirmar Eliminacion",
            f"Eliminar nodo '{node_label}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        self.undo_stack.push(DeleteNodeCommand(self.current_workflow, self.selected_node, self))
        
        self.selected_node = None
        self.clear_node_fields()
    
    def apply_node_changes(self):
        """Aplica cambios al nodo seleccionado."""
        if not self.current_workflow or not hasattr(self, 'selected_node') or not self.selected_node:
            return
        
        node = self.selected_node
        node.label = self.prop_label.text().strip() or node.label
        
        if isinstance(node, ActionNode):
            node.script = self.prop_script.currentText().strip() if hasattr(self.prop_script, 'currentText') else self.prop_script.text().strip()
        elif isinstance(node, DecisionNode):
            node.condition = self.prop_condition.text().strip()
            node.true_path = self.prop_true_path.text().strip()
            node.false_path = self.prop_false_path.text().strip()
        elif isinstance(node, LoopNode):
            node.script = self.prop_script.currentText().strip() if hasattr(self.prop_script, 'currentText') else self.prop_script.text().strip()
            node.iterations = self.prop_iterations.text().strip() or "1"
        
        if not isinstance(node, DecisionNode):
            next_node_id = self.prop_next_node.text().strip()
            self.current_workflow.edges = [
                e for e in self.current_workflow.edges if e.from_node != node.id
            ]
            if next_node_id:
                self.current_workflow.edges.append(Edge(from_node=node.id, to_node=next_node_id))
        
        self.canvas.load_workflow(self.current_workflow)
        self.log(f"Nodo actualizado: {node.label}")

    def validate_workflow(self):
        """Ejecuta validación y muestra errores visualmente."""
        if not self.current_workflow:
            return
            
        errors = WorkflowValidator.validate(self.current_workflow)
        
        if hasattr(self, 'scene'):
            for item in self.scene.items():
                if isinstance(item, NodeGraphicsItem):
                    item.set_warning(None)
        
        if not errors:
            self.status_label.setText("Validación OK")
            self.status_label.setStyleSheet("color: #28a745; font-weight: bold;")
            QMessageBox.information(self, "Validación Correcta", "El workflow es válido y está listo para ejecutarse.")
            return

        msg_list = []
        for err in errors:
            node_id = err["node_id"]
            msg = err["message"]
            msg_list.append(f"- {node_id or 'Global'}: {msg}")
            
            if node_id and hasattr(self, 'scene'):
                for item in self.scene.items():
                    if isinstance(item, NodeGraphicsItem) and item.node.id == node_id:
                        item.set_warning(msg)
                        break
        
        count = len(errors)
        self.status_label.setText(f"{count} Errores encontrados")
        self.status_label.setStyleSheet("color: #dc3545; font-weight: bold;")
        
        QMessageBox.warning(self, "Errores de Validación", 
            f"Se encontraron {count} problemas:\n\n" + "\n".join(msg_list))

    def on_connection_created(self, from_id: str, to_id: str):
        """Maneja la creación visual de conexiones (Undoable)."""
        if not self.current_workflow:
            return
            
        from_node = self.current_workflow.get_node(from_id)
        if not from_node:
            return

        if from_id == to_id:
            QMessageBox.warning(self, "Acción inválida", "No puedes conectar un nodo consigo mismo.")
            return

        self.undo_stack.beginMacro(f"Conectar {from_id} -> {to_id}")
        
        if isinstance(from_node, DecisionNode):
            items = ["TRUE", "FALSE"]
            path, ok = QInputDialog.getItem(self, "Conexión de Decisión", 
                f"Conectar '{from_node.label}' -> '{to_id}' como:", items, 0, False)
            
            if not ok or not path:
                self.undo_stack.endMacro()
                return
            
            prop_name = "true_path" if path == "TRUE" else "false_path"
            old_val = getattr(from_node, prop_name)
            
            self.undo_stack.push(ModifyPropertyCommand(
                self.current_workflow, from_id, prop_name, to_id, old_val, self
            ))
            self.undo_stack.push(ConnectionCommand(self.current_workflow, from_id, to_id, self, is_add=True))
            
        else:
            existing = [e for e in self.current_workflow.edges if e.from_node == from_id]
            for e in existing:
                self.undo_stack.push(ConnectionCommand(
                    self.current_workflow, e.from_node, e.to_node, self, is_add=False
                ))
            
            self.undo_stack.push(ConnectionCommand(self.current_workflow, from_id, to_id, self, is_add=True))
            
            if hasattr(self, 'selected_node') and self.selected_node and self.selected_node.id == from_id:
                self.prop_next_node.setText(to_id)
        
        self.undo_stack.endMacro()
        self.log(f"Conexión creada: {from_id} -> {to_id}")

    def on_edge_split_requested(self, node: Node, from_id: str, to_id: str):
        """Maneja la inserción de un nodo en una conexión existente."""
        if not self.current_workflow:
            return
        
        reply = QMessageBox.question(
            self, "Insertar Nodo",
            f"¿Insertar nodo '{node.label}' entre '{from_id}' y '{to_id}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.undo_stack.beginMacro(f"Insertar nodo en {from_id}->{to_id}")
        self.undo_stack.push(ConnectionCommand(self.current_workflow, from_id, to_id, self, is_add=False))
            
        from_node = self.current_workflow.get_node(from_id)
        if isinstance(from_node, DecisionNode):
            if from_node.true_path == to_id:
                self.undo_stack.push(ModifyPropertyCommand(
                    self.current_workflow, from_id, "true_path", node.id, to_id, self
                ))
            if from_node.false_path == to_id:
                self.undo_stack.push(ModifyPropertyCommand(
                    self.current_workflow, from_id, "false_path", node.id, to_id, self
                ))
        
        self.undo_stack.push(ConnectionCommand(self.current_workflow, from_id, node.id, self, is_add=True))
        
        if not isinstance(node, DecisionNode):
            self.undo_stack.push(ConnectionCommand(self.current_workflow, node.id, to_id, self, is_add=True))
            if hasattr(self, 'selected_node') and self.selected_node and self.selected_node.id == node.id:
                 self.prop_next_node.setText(to_id)
        else:
             self.undo_stack.push(ModifyPropertyCommand(
                 self.current_workflow, node.id, "true_path", to_id, getattr(node, "true_path", ""), self
             ))
             self.undo_stack.push(ConnectionCommand(self.current_workflow, node.id, to_id, self, is_add=True))
        
        self.undo_stack.endMacro()
        self.log(f"Nodo insertado: {from_id} -> {node.id} -> {to_id}")
