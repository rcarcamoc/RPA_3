"""
Panel de Workflows para la GUI principal del RPA Framework 3.

Este módulo contiene el WorkflowPanel que integra el motor de ejecución
de workflows con la interfaz PyQt6.

Refactorizado de forma modular hacia ui/workers/, ui/canvas/ y ui/panels/workflow_editor_mixin.py
manteniendo 100% de compatibilidad hacia atrás.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QListWidget, QListWidgetItem, QPushButton, QLabel, 
    QTextEdit, QGroupBox, QFormLayout, QLineEdit, QComboBox,
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem,
    QGraphicsPathItem, QGraphicsEllipseItem, QMessageBox, QFileDialog, QApplication,
    QInputDialog, QStyle
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPointF, QRectF
from PyQt6.QtGui import (
    QFont, QColor, QBrush, QPen, QPainterPath, QPolygonF, QPainter,
    QPainterPathStroker, QUndoStack, QKeySequence, QAction, QLinearGradient
)
from pathlib import Path
from datetime import datetime
import json
import os
import sys
import math

try:
    import pythoncom
except ImportError:
    pythoncom = None

from .workflow_commands import AddNodeCommand, DeleteNodeCommand, MoveNodeCommand, ConnectionCommand, ModifyPropertyCommand

# Añadir path para importar módulos core
sys.path.insert(0, str(Path(__file__).parent))

from core.models import Workflow, Node, NodeType, ActionNode, DecisionNode, LoopNode, Edge
from core.workflow_executor import WorkflowExecutor
from .node_palette import NodePalette
from .node_definitions import NodeDefinition
from core.logger import WorkflowLogger
from core.validator import WorkflowValidator

# Re-exportaciones modulares (100% compatibilidad hacia atrás)
from .workers.workflow_executor_worker import WorkflowExecutorWorker
from .canvas.legacy_items import PortItem, NodeGraphicsItem, EdgeGraphicsItem
from .canvas.legacy_canvas import WorkflowCanvas
from .panels.workflow_editor_mixin import WorkflowEditorMixin


class WorkflowPanel(WorkflowEditorMixin, QWidget):
    """Panel principal de Workflows para la GUI."""
    
    def __init__(self, config: dict = None):
        super().__init__()
        self.config = config or {}
        self.current_workflow = None
        self.worker = None
        
        # Undo Stack
        self.undo_stack = QUndoStack(self)
        
        self.init_ui()
        self.load_workflow_list()
    
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Titulo y botones de archivo
        header_layout = QHBoxLayout()
        
        title = QLabel("Workflows")
        title_font = QFont("Arial", 14, QFont.Weight.Bold)
        title.setFont(title_font)
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Botones Undo/Redo
        self.btn_undo = QPushButton()
        self.btn_undo.setToolTip("Deshacer (Ctrl+Z)")
        self.btn_undo.setFixedWidth(30)
        self.btn_undo.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowBack))
        self.btn_undo.clicked.connect(self.undo_stack.undo)
        self.btn_undo.setEnabled(False)
        header_layout.addWidget(self.btn_undo)
        
        self.btn_redo = QPushButton()
        self.btn_redo.setToolTip("Rehacer (Ctrl+Y)")
        self.btn_redo.setFixedWidth(30)
        self.btn_redo.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowForward))
        self.btn_redo.clicked.connect(self.undo_stack.redo)
        self.btn_redo.setEnabled(False)
        header_layout.addWidget(self.btn_redo)
        
        # Conectar señales del stack
        self.undo_stack.canUndoChanged.connect(self.btn_undo.setEnabled)
        self.undo_stack.canRedoChanged.connect(self.btn_redo.setEnabled)
        
        # Actions for Shortcuts
        undo_action = self.undo_stack.createUndoAction(self, "Deshacer")
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        self.addAction(undo_action)
        
        redo_action = self.undo_stack.createRedoAction(self, "Rehacer")
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        self.addAction(redo_action)
        
        header_layout.addSpacing(10)
        
        # Zoom Controls
        self.btn_zoom_out = QPushButton("➖")
        self.btn_zoom_out.setToolTip("Alejar (Ctrl + Rueda)")
        self.btn_zoom_out.setFixedWidth(30)
        header_layout.addWidget(self.btn_zoom_out)
        
        self.btn_zoom_reset = QPushButton("1:1")
        self.btn_zoom_reset.setToolTip("Resetear Zoom")
        self.btn_zoom_reset.setFixedWidth(35)
        header_layout.addWidget(self.btn_zoom_reset)
        
        self.btn_zoom_in = QPushButton("➕")
        self.btn_zoom_in.setToolTip("Acercar (Ctrl + Rueda)")
        self.btn_zoom_in.setFixedWidth(30)
        header_layout.addWidget(self.btn_zoom_in)
        
        btn_new = QPushButton("+ Nuevo")
        btn_new.setStyleSheet("background-color: #17a2b8; color: white; font-weight: bold; padding: 5px 15px;")
        btn_new.clicked.connect(self.create_new_workflow)
        header_layout.addWidget(btn_new)
        
        self.btn_save = QPushButton(" Guardar")
        self.btn_save.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        self.btn_save.setStyleSheet("background-color: #6c757d; color: white; font-weight: bold; padding: 5px 15px;")
        self.btn_save.clicked.connect(self.save_workflow)
        self.btn_save.setEnabled(False)
        header_layout.addWidget(self.btn_save)
        
        self.btn_validate = QPushButton(" Validar")
        self.btn_validate.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))
        self.btn_validate.setStyleSheet("background-color: #ffc107; color: black; font-weight: bold; padding: 5px 15px;")
        self.btn_validate.clicked.connect(self.validate_workflow)
        self.btn_validate.setEnabled(False)
        header_layout.addWidget(self.btn_validate)
        
        layout.addLayout(header_layout)
        
        # Splitter principal
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Paleta de Nodos
        self.node_palette = NodePalette()
        splitter.addWidget(self.node_palette)
        
        # Panel izquierdo (Lista + Propiedades)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # Lista de workflows
        list_group = QGroupBox("Workflows Disponibles")
        list_layout = QVBoxLayout()
        
        self.workflow_list = QListWidget()
        self.workflow_list.itemClicked.connect(self.on_workflow_selected)
        list_layout.addWidget(self.workflow_list)
        
        btn_refresh = QPushButton(" Recargar")
        btn_refresh.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        btn_refresh.clicked.connect(self.load_workflow_list)
        list_layout.addWidget(btn_refresh)
        
        list_group.setLayout(list_layout)
        left_layout.addWidget(list_group)
        
        # Controles de ejecucion
        control_group = QGroupBox("Ejecucion")
        control_layout = QVBoxLayout()
        
        btn_layout = QHBoxLayout()
        
        self.btn_execute = QPushButton(" Ejecutar")
        self.btn_execute.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.btn_execute.setStyleSheet("background-color: #28a745; color: white; font-weight: bold;")
        self.btn_execute.clicked.connect(self.execute_workflow)
        self.btn_execute.setEnabled(False)
        btn_layout.addWidget(self.btn_execute)
        
        self.btn_stop = QPushButton(" Detener")
        self.btn_stop.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.btn_stop.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold;")
        self.btn_stop.clicked.connect(self.stop_workflow)
        self.btn_stop.setEnabled(False)
        btn_layout.addWidget(self.btn_stop)
        
        control_layout.addLayout(btn_layout)
        
        self.status_label = QLabel("Estado: Listo")
        self.status_label.setStyleSheet("color: #666; font-style: italic;")
        control_layout.addWidget(self.status_label)
        
        control_group.setLayout(control_layout)
        left_layout.addWidget(control_group)
        
        # Propiedades del Nodo Seleccionado
        props_group = QGroupBox("Editor de Nodo")
        props_layout = QFormLayout()
        
        node_btn_layout = QHBoxLayout()
        
        self.btn_add_node = QPushButton(" Agregar")
        self.btn_add_node.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        self.btn_add_node.setStyleSheet("background-color: #28a745; color: white;")
        self.btn_add_node.clicked.connect(self.add_node)
        self.btn_add_node.setEnabled(False)
        node_btn_layout.addWidget(self.btn_add_node)
        
        self.btn_delete_node = QPushButton(" Eliminar")
        self.btn_delete_node.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        self.btn_delete_node.setStyleSheet("background-color: #dc3545; color: white;")
        self.btn_delete_node.clicked.connect(self.delete_node)
        self.btn_delete_node.setEnabled(False)
        node_btn_layout.addWidget(self.btn_delete_node)
        
        self.btn_apply = QPushButton(" Aplicar")
        self.btn_apply.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))
        self.btn_apply.setStyleSheet("background-color: #007bff; color: white;")
        self.btn_apply.clicked.connect(self.apply_node_changes)
        self.btn_apply.setEnabled(False)
        node_btn_layout.addWidget(self.btn_apply)
        
        props_layout.addRow(node_btn_layout)
        
        self.prop_id = QLineEdit()
        self.prop_id.setPlaceholderText("node_id_unico")
        props_layout.addRow("ID:", self.prop_id)
        
        self.prop_label = QLineEdit()
        self.prop_label.setPlaceholderText("Nombre del nodo")
        props_layout.addRow("Nombre:", self.prop_label)
        
        self.prop_type = QComboBox()
        self.prop_type.addItems(["action", "decision", "loop", "database", "annotation", "start", "end"])
        self.prop_type.currentTextChanged.connect(self.on_type_changed)
        props_layout.addRow("Tipo:", self.prop_type)
        
        script_layout = QHBoxLayout()
        self.prop_script = QComboBox()
        self.prop_script.setEditable(True)
        self.prop_script.setPlaceholderText("Seleccionar script...")
        self.prop_script.setMinimumWidth(150)
        script_layout.addWidget(self.prop_script)
        
        btn_refresh_scripts = QPushButton()
        btn_refresh_scripts.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        btn_refresh_scripts.setMaximumWidth(30)
        btn_refresh_scripts.setToolTip("Actualizar lista de scripts")
        btn_refresh_scripts.clicked.connect(self.load_script_list)
        script_layout.addWidget(btn_refresh_scripts)
        
        props_layout.addRow("Script:", script_layout)
        
        self.load_script_list()
        
        # DECISION fields
        self.prop_condition = QLineEdit()
        self.prop_condition.setPlaceholderText("variable == 'valor'")
        self.prop_condition_label = QLabel("Condicion:")
        props_layout.addRow(self.prop_condition_label, self.prop_condition)
        
        self.prop_true_path = QLineEdit()
        self.prop_true_path.setPlaceholderText("ID nodo si TRUE")
        self.prop_true_path_label = QLabel("TRUE ->:")
        props_layout.addRow(self.prop_true_path_label, self.prop_true_path)
        
        self.prop_false_path = QLineEdit()
        self.prop_false_path.setPlaceholderText("ID nodo si FALSE")
        self.prop_false_path_label = QLabel("FALSE ->:")
        props_layout.addRow(self.prop_false_path_label, self.prop_false_path)
        
        # LOOP fields
        self.prop_iterations = QLineEdit()
        self.prop_iterations.setPlaceholderText("3 o nombre_variable")
        self.prop_iterations_label = QLabel("Iteraciones:")
        props_layout.addRow(self.prop_iterations_label, self.prop_iterations)
        
        # DATABASE fields
        self.prop_db_host = QLineEdit()
        self.prop_db_host.setPlaceholderText("localhost")
        self.prop_db_host_label = QLabel("DB Host:")
        props_layout.addRow(self.prop_db_host_label, self.prop_db_host)
        
        self.prop_db_port = QLineEdit()
        self.prop_db_port.setPlaceholderText("3306")
        self.prop_db_port_label = QLabel("DB Port:")
        props_layout.addRow(self.prop_db_port_label, self.prop_db_port)
        
        self.prop_db_user = QLineEdit()
        self.prop_db_user.setPlaceholderText("root")
        self.prop_db_user_label = QLabel("DB User:")
        props_layout.addRow(self.prop_db_user_label, self.prop_db_user)
        
        self.prop_db_password = QLineEdit()
        self.prop_db_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.prop_db_password.setPlaceholderText("password")
        self.prop_db_password_label = QLabel("DB Password:")
        props_layout.addRow(self.prop_db_password_label, self.prop_db_password)
        
        self.prop_db_database = QLineEdit()
        self.prop_db_database.setPlaceholderText("my_database")
        self.prop_db_database_label = QLabel("Database:")
        props_layout.addRow(self.prop_db_database_label, self.prop_db_database)
        
        self.prop_db_query = QTextEdit()
        self.prop_db_query.setMaximumHeight(80)
        self.prop_db_query.setPlaceholderText("SELECT * FROM users WHERE id = {user_id}")
        self.prop_db_query_label = QLabel("SQL Query:")
        props_layout.addRow(self.prop_db_query_label, self.prop_db_query)
        
        self.prop_db_operation = QComboBox()
        self.prop_db_operation.addItems(["SELECT", "INSERT", "UPDATE", "DELETE"])
        self.prop_db_operation_label = QLabel("Operation:")
        props_layout.addRow(self.prop_db_operation_label, self.prop_db_operation)
        
        self.prop_db_result_var = QLineEdit()
        self.prop_db_result_var.setPlaceholderText("db_result")
        self.prop_db_result_var_label = QLabel("Result Var:")
        props_layout.addRow(self.prop_db_result_var_label, self.prop_db_result_var)
        
        # ANNOTATION fields
        self.prop_annotation_text = QTextEdit()
        self.prop_annotation_text.setMaximumHeight(100)
        self.prop_annotation_text.setPlaceholderText("Nota de documentación...")
        self.prop_annotation_text_label = QLabel("Texto:")
        props_layout.addRow(self.prop_annotation_text_label, self.prop_annotation_text)
        
        self.prop_annotation_color = QComboBox()
        self.prop_annotation_color.addItems(["Amarillo", "Azul", "Rosa", "Verde"])
        self.prop_annotation_color_label = QLabel("Color:")
        props_layout.addRow(self.prop_annotation_color_label, self.prop_annotation_color)
        
        # Campo para conectar al siguiente nodo
        self.prop_next_node = QLineEdit()
        self.prop_next_node.setPlaceholderText("ID del siguiente nodo")
        self.prop_next_node_label = QLabel("Siguiente:")
        props_layout.addRow(self.prop_next_node_label, self.prop_next_node)
        
        props_group.setLayout(props_layout)
        left_layout.addWidget(props_group)
        
        # Variables
        var_group = QGroupBox("Variables")
        var_layout = QVBoxLayout()
        
        self.var_text = QTextEdit()
        self.var_text.setMaximumHeight(100)
        self.var_text.setStyleSheet("font-family: Consolas; font-size: 10pt;")
        self.var_text.setPlaceholderText('{"key": "value"}')
        var_layout.addWidget(self.var_text)
        
        var_group.setLayout(var_layout)
        left_layout.addWidget(var_group)
        
        left_layout.addStretch()
        splitter.addWidget(left_widget)
        
        # Panel central (Canvas)
        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        
        canvas_label = QLabel("Vista del Workflow")
        canvas_label.setStyleSheet("font-weight: bold;")
        center_layout.addWidget(canvas_label)
        
        self.canvas = WorkflowCanvas()
        self.canvas.setMinimumSize(400, 300)
        self.canvas.node_selected.connect(self.on_node_selected)
        self.canvas.connection_created.connect(self.on_connection_created)
        self.canvas.edge_split_requested.connect(self.on_edge_split_requested)
        
        # Conectar controles de Zoom
        self.btn_zoom_in.clicked.connect(self.canvas.zoom_in)
        self.btn_zoom_out.clicked.connect(self.canvas.zoom_out)
        self.btn_zoom_reset.clicked.connect(self.canvas.zoom_reset_view)
        
        center_layout.addWidget(self.canvas)
        splitter.addWidget(center_widget)
        
        # Panel derecho (Logs)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        log_label = QLabel("Logs de Ejecucion")
        log_label.setStyleSheet("font-weight: bold;")
        right_layout.addWidget(log_label)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet(
            "background-color: #1e1e1e; color: #d4d4d4; "
            "font-family: Consolas; font-size: 10pt;"
        )
        right_layout.addWidget(self.log_text)
        
        btn_clear_log = QPushButton("Limpiar Logs")
        btn_clear_log.clicked.connect(lambda: self.log_text.clear())
        right_layout.addWidget(btn_clear_log)
        
        splitter.addWidget(right_widget)
        splitter.setSizes([280, 400, 270])
        
        layout.addWidget(splitter)
        self.setLayout(layout)
    
    def execute_workflow(self):
        """Ejecuta el workflow actual."""
        if not self.current_workflow:
            return
        
        self.log_text.clear()
        self.canvas.clear_highlights()
        
        self.btn_execute.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.status_label.setText("Ejecutando...")
        self.status_label.setStyleSheet("color: #007bff; font-weight: bold;")
        
        self.worker = WorkflowExecutorWorker(self.current_workflow)
        self.worker.log_update.connect(self.on_log_update)
        self.worker.node_started.connect(self.on_node_started)
        self.worker.node_finished.connect(self.on_node_finished)
        self.worker.finished.connect(self.on_execution_finished)
        self.worker.error.connect(self.on_execution_error)
        self.worker.start()
    
    def stop_workflow(self):
        """Detiene la ejecucion del workflow."""
        if not (self.worker and self.worker.isRunning()):
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
                self.worker.stop_after_current_case()
                self.btn_stop.setEnabled(False)
                self.status_label.setText("Estado: Deteniendo tras caso actual...")
                self.log("⏳ Solicitud registrada: se detendrá el bucle al finalizar el caso actual.")
                return

        self.worker.stop()
        self.btn_stop.setEnabled(False)
        self.status_label.setText("Estado: Deteniendo...")
        self.log("🛑 Solicitando detención inmediata de la ejecución...")
    
    def on_log_update(self, message: str):
        """Actualiza el log en tiempo real."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def on_node_started(self, node_id: str):
        """Resalta el nodo que esta ejecutandose."""
        self.canvas.highlight_node(node_id, True)
    
    def on_node_finished(self, node_id: str):
        """Quita el resaltado del nodo que termino."""
        self.canvas.highlight_node(node_id, False)
    
    def on_execution_finished(self, result: dict):
        """Maneja el fin de la ejecucion."""
        status = result.get('status', 'unknown')
        
        if status == 'success':
            self.status_label.setText("Completado")
            self.status_label.setStyleSheet("color: #28a745; font-weight: bold;")
            self.log("[OK] Workflow completado exitosamente")
        elif status == 'stopped':
            self.status_label.setText("Detenido")
            self.status_label.setStyleSheet("color: #ffc107; font-weight: bold;")
            self.log("[STOP] Workflow detenido por el usuario")
        else:
            self.status_label.setText("Error")
            self.status_label.setStyleSheet("color: #dc3545; font-weight: bold;")
            self.log(f"[ERROR] {result.get('error', 'Unknown error')}")
        
        self.var_text.setText(json.dumps(result.get('context', {}), indent=2))
        self.btn_execute.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.canvas.clear_highlights()
    
    def on_execution_error(self, error: str):
        """Maneja errores de ejecucion."""
        self.status_label.setText("Error")
        self.status_label.setStyleSheet("color: #dc3545; font-weight: bold;")
        self.log(f"[ERROR] {error}")
        self.btn_execute.setEnabled(True)
        self.btn_stop.setEnabled(False)
        QMessageBox.critical(self, "Error de Ejecucion", f"Error:\n{error}")
    
    def log(self, message: str):
        """Agrega mensaje al log."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
