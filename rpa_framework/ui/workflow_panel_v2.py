from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter, 
                             QPushButton, QLabel, QStyle, QListWidget, QGroupBox,
                             QTabWidget, QToolBar, QTextEdit, QInputDialog, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QAction, QKeySequence, QUndoStack, QIcon

from .node_palette import NodePalette
from .workflow_panel import WorkflowCanvas, WorkflowExecutorWorker # Reusing Canvas logic
from .panels.properties_panel import PropertiesPanel
from .workflow_commands import AddNodeCommand, DeleteNodeCommand, MoveNodeCommand, ConnectionCommand, ModifyPropertyCommand
from core.models import Workflow, Node, NodeType, ActionNode, DecisionNode, LoopNode, WorkflowNode
from core.workflow_executor import WorkflowExecutor
import os

class WorkflowPanelV2(QWidget):
    """
    Workflow Editor V2 - Diseño Moderno (3 Paneles)
    Izquierda: Paleta | Centro: Canvas | Derecha: Propiedades
    """
    
    def __init__(self, config: dict = None):
        super().__init__()
        self.config = config or {}
        self.current_workflow = None
        self.undo_stack = QUndoStack(self)
        
        self.init_ui()
        
        # Setup signals
        # Setup signals
        self.canvas.node_selected.connect(self.on_node_selected)
        self.canvas.connection_created.connect(self.on_connection_created)
        self.canvas.connection_deleted.connect(self.on_connection_deleted)
        
        # For drag and drop creation -> Canvas needs to call parent
        # We'll monkey patch or ensure canvas calls 'create_node_from_palette'
        
        self.load_workflow_list() # Dummy implementation or reuse logic

    def on_connection_created(self, from_id, to_id):
        """Handle link creation from Canvas"""
        if not self.current_workflow: return
        
        # Command
        cmd = ConnectionCommand(self.current_workflow, from_id, to_id, self, is_add=True)
        self.undo_stack.push(cmd)
        
        # Note: Canvas usually draws the line temporarily. 
        # The command execution will call load_workflow which redraws everything properly.

    def on_connection_deleted(self, from_id, to_id):
        """Handle link deletion from Canvas"""
        if not self.current_workflow: return
        
        cmd = ConnectionCommand(self.current_workflow, from_id, to_id, self, is_add=False)
        self.undo_stack.push(cmd)


    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0,0,0,0)
        main_layout.setSpacing(0)
        
        # --- TOP TOOLBAR ---
        toolbar = QToolBar()
        toolbar.setStyleSheet("background-color: #f8f9fa; border-bottom: 1px solid #ddd; padding: 5px;")
        toolbar.setMovable(False)
        
        # File Actions
        btn_new = QAction("➕ Nuevo", self)
        btn_new.triggered.connect(self.create_new_workflow)
        toolbar.addAction(btn_new)
        
        btn_save = QAction("💾 Guardar", self)
        btn_save.triggered.connect(self.save_workflow)
        toolbar.addAction(btn_save)
        
        toolbar.addSeparator()
        
        # Undo/Redo
        undo_act = self.undo_stack.createUndoAction(self, "")
        undo_act.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowBack))
        undo_act.setShortcut(QKeySequence.StandardKey.Undo)
        toolbar.addAction(undo_act)
        
        redo_act = self.undo_stack.createRedoAction(self, "")
        redo_act.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowForward))
        redo_act.setShortcut(QKeySequence.StandardKey.Redo)
        toolbar.addAction(redo_act)
        
        toolbar.addSeparator()
        
        # Zoom Actions
        act_zoom_in = QAction("🔍+", self)
        act_zoom_in.triggered.connect(lambda: self.canvas.scale_view(1.2))
        toolbar.addAction(act_zoom_in)
        
        act_zoom_out = QAction("🔍-", self)
        act_zoom_out.triggered.connect(lambda: self.canvas.scale_view(1/1.2))
        toolbar.addAction(act_zoom_out)
        
        toolbar.addSeparator()
        
        # Execution
        self.act_run = QAction("▶ Ejecutar", self)
        self.act_run.triggered.connect(self.execute_workflow)
        toolbar.addAction(self.act_run)
        
        self.act_stop = QAction("⏹ Detener", self)
        self.act_stop.triggered.connect(self.stop_workflow)
        self.act_stop.setEnabled(False)
        toolbar.addAction(self.act_stop)
        
        toolbar.addSeparator()
        
        
        # Log Actions
        act_clear_log = QAction("🗑️ Limpiar Log", self)
        act_clear_log.triggered.connect(self.clear_log)
        toolbar.addAction(act_clear_log)
        
        self.act_float_log = QAction("🖥️ Log Flotante", self)
        self.act_float_log.setCheckable(True)
        self.act_float_log.toggled.connect(self.toggle_float_log)
        toolbar.addAction(self.act_float_log)
        
        main_layout.addWidget(toolbar)
        
        # --- MAIN SPLITTER (Left | Center | Right) ---
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(1)
        
        # 1. LEFT PANEL (Palette & List)
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0,0,0,0)
        
        self.left_tabs = QTabWidget()
        self.node_palette = NodePalette()
        self.left_tabs.addTab(self.node_palette, "Componentes")
        
        self.workflow_list = QListWidget()
        self.workflow_list.itemClicked.connect(self.on_workflow_list_click)
        self.left_tabs.addTab(self.workflow_list, "Mis Workflows")
        
        left_layout.addWidget(self.left_tabs)
        self.splitter.addWidget(left_container)
        
        # 2. CENTER PANEL (Canvas)
        center_container = QWidget()
        center_layout = QVBoxLayout(center_container)
        center_layout.setContentsMargins(0,0,0,0)
        
        self.canvas = WorkflowCanvas(self) # Parent is self, so it finds create_node_from_palette
        center_layout.addWidget(self.canvas)
        self.splitter.addWidget(center_container)
        
        # 3. RIGHT PANEL (Properties + Log)
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0,0,0,0)
        
        # Vertical splitter for properties and log
        self.right_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Properties Panel (top)
        self.properties_panel = PropertiesPanel()
        self.properties_panel.node_updated.connect(self.on_node_updated)
        self.properties_panel.node_deleted.connect(self.on_node_deleted_req)
        self.properties_panel.hide() # Hidden by default
        self.right_splitter.addWidget(self.properties_panel)
        
        # Log Panel (bottom)
        log_group = QGroupBox("📋 Log de Ejecución")
        log_layout = QVBoxLayout()
        log_layout.setContentsMargins(5,5,5,5)
        
        self.log_widget = QTextEdit()
        self.log_widget.setReadOnly(True)
        self.log_widget.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 10px;
                border: 1px solid #3c3c3c;
            }
        """)
        self.log_widget.setMinimumHeight(100)
        log_layout.addWidget(self.log_widget)
        log_group.setLayout(log_layout)
        
        self.right_splitter.addWidget(log_group)
        self.right_splitter.setSizes([400, 200])
        
        right_layout.addWidget(self.right_splitter)
        self.splitter.addWidget(right_container)
        
        # Set Stretch Factors (15% | 65% | 20%)
        self.splitter.setSizes([250, 800, 300])
        self.splitter.setCollapsible(1, False) # Canvas not collapsible
        
        main_layout.addWidget(self.splitter)
        
        self.log_window = None # Instancia lazy
        
        # Floating Zoom Controls
        self.zoom_controls = ZoomControls(self.canvas, self.canvas)
        self.zoom_controls.show()
        
        # Monkey patch resize event of canvas to move zoom controls
        original_resize = self.canvas.resizeEvent
        
        def new_resize_event(event):
            original_resize(event)
            # Position bottom right
            zc_width = self.zoom_controls.sizeHint().width()
            zc_height = self.zoom_controls.sizeHint().height()
            x = event.size().width() - zc_width - 20
            y = event.size().height() - zc_height - 20
            self.zoom_controls.move(x, y)
            self.zoom_controls.raise_()
            
        self.canvas.resizeEvent = new_resize_event

    # --- LOGIC ---

    def toggle_float_log(self, checked):
        if checked:
            if not self.log_window:
                self.log_window = LogWindow(self)
                # Copiar contenido actual
                self.log_window.set_html(self.log_widget.toHtml())
                self.log_window.finished.connect(lambda: self.act_float_log.setChecked(False))
            self.log_window.show()
            self.log_window.raise_()
        else:
            if self.log_window:
                self.log_window.hide()
    
    def on_workflow_list_click(self, item):
        # Load workflow logic
        wf_name = item.text()
        wf_path = f"workflows/{wf_name}.json"
        if os.path.exists(wf_path):
            try:
                self.current_workflow = Workflow.from_json(wf_path)
                self.canvas.load_workflow(self.current_workflow)
                self.append_log(f"Workflow cargado: {wf_name}", "INFO")
                self.properties_panel.hide()
            except Exception as e:
                self.append_log(f"Error cargando workflow: {e}", "ERROR")
                QMessageBox.critical(self, "Error", f"No se pudo cargar el workflow: {e}")

    def create_new_workflow(self):
        self.current_workflow = Workflow(id="new_workflow", name="Nuevo Workflow")
        self.canvas.load_workflow(self.current_workflow)
        self.properties_panel.hide()
        self.undo_stack.clear()
        self.append_log("Nuevo workflow creado.", "INFO")

    def save_workflow(self):
        if not self.current_workflow:
            QMessageBox.warning(self, "Aviso", "No hay un workflow activo para guardar.")
            return

        name = self.current_workflow.name
        # Si es el nombre por defecto o el ID es 'new_workflow', preguntamos nombre
        if name == "Nuevo Workflow" or self.current_workflow.id == "new_workflow":
            new_name, ok = QInputDialog.getText(self, "Guardar Workflow", "Nombre del Workflow:", text=name)
            if ok and new_name.strip():
                self.current_workflow.name = new_name.strip()
                # Generar un ID simple basado en el nombre
                import re
                clean_id = re.sub(r'[^a-zA-Z0-9]', '_', new_name.lower())
                self.current_workflow.id = clean_id
                name = self.current_workflow.name
            else:
                return # Usuario canceló

        if not os.path.exists("workflows"):
            os.makedirs("workflows", exist_ok=True)

        filepath = f"workflows/{name}.json"
        
        # Confirmar sobreescritura si el archivo ya existe y es un 'Nuevo Workflow' que cambió de nombre
        if os.path.exists(filepath):
            ret = QMessageBox.question(self, "Confirmar Guardado", 
                                     f"El archivo '{name}.json' ya existe. ¿Desea sobrescribirlo?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if ret == QMessageBox.StandardButton.No:
                return

        try:
            self.current_workflow.to_json(filepath)
            self.append_log(f"Workflow guardado correctamente en: {filepath}", "SUCCESS")
            self.load_workflow_list()
        except Exception as e:
            self.append_log(f"Error al guardar workflow: {e}", "ERROR")
            QMessageBox.critical(self, "Error", f"Error al guardar el archivo: {e}")
             
    def create_node_from_palette(self, node_def, pos):
        """Called by Canvas drop event"""
        if not self.current_workflow:
            self.create_new_workflow()
            
        # Logic similar to original but using clean command pattern
        # Generate ID
        new_id = f"n{len(self.current_workflow.nodes) + 1}_{int(os.times()[4]*100)}"
        
        # Map definition to Node instance
        # Reuse logic from V1 roughly, can be optimized
        node_type_map = {
            'action': NodeType.ACTION,
            'decision': NodeType.DECISION,
            'loop': NodeType.LOOP,
            'database': NodeType.DATABASE,
            'annotation': NodeType.ANNOTATION,
            'delay': NodeType.DELAY,
            'start': NodeType.START,
            'end': NodeType.END,
            'workflow': NodeType.WORKFLOW
        }

        
        ntype = node_type_map.get(node_def.node_type_enum, NodeType.ACTION)
        
        defaults = node_def.default_values
        
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
             # Action (Python or Command)
             node = ActionNode(id=new_id, label=node_def.name, position={"x": pos.x(), "y": pos.y()}, **defaults)
             # If default has 'command', ActionNode handles it via **defaults linkage? 
             # ActionNode definition has 'command' field now. Yes.
             
        # Execute Command
        cmd = AddNodeCommand(self.current_workflow, node, self)
        self.undo_stack.push(cmd)
        
        # Select it
        self.canvas.highlight_node(node.id)
        self.on_node_selected(node)

    def on_node_selected(self, node):
        if not node:
            self.properties_panel.hide()
            return
            
        self.properties_panel.load_node(node)
        self.properties_panel.show()
        
    def on_node_updated(self, node):
        # Called when Apply clicked in properties
        # Ideally property panel emits diff, here we just refresh canvas for visual updates
        # Since we modified the object in place (in properties_panel), we just need to repaint
        # To make it undoable, properties panel should emit 'old_val', 'new_val'. 
        # For this V2, we assume direct edit for simplicity or implement ModifyCommand in panel.
        # But panel emitted signal 'node_updated' after modifying it.
        # Let's refresh canvas.
        self.canvas.load_workflow(self.current_workflow) # Brute force refresh
        self.canvas.highlight_node(node.id)

    def on_node_deleted_req(self, node):
        cmd = DeleteNodeCommand(self.current_workflow, node, self)
        self.undo_stack.push(cmd)
        self.properties_panel.hide()

    def execute_workflow(self):
        if not self.current_workflow: return
        
        # Si log flotante está activo, traerlo al frente
        if self.log_window and self.log_window.isVisible():
            self.log_window.raise_()
        
        self.append_log("🚀 Iniciando ejecución del workflow...", "INFO")
        self.worker = WorkflowExecutorWorker(self.current_workflow)
        self.worker.log_update.connect(lambda msg: self.append_log(msg, "INFO"))
        self.worker.finished.connect(lambda res: self.append_log("✅ Ejecución finalizada correctamente.", "SUCCESS"))
        self.worker.error.connect(lambda err: self.append_log(f"❌ Error en ejecución: {err}", "ERROR"))
        self.worker.start()
        self.act_run.setEnabled(False)
        self.act_stop.setEnabled(True)
        
    def stop_workflow(self):
        if self.worker:
            self.worker.stop()
            self.append_log("🛑 Ejecución detenida por el usuario.", "WARNING")
        self.act_run.setEnabled(True)
        self.act_stop.setEnabled(False)
    
    def append_log(self, message: str, level: str = "INFO"):
        """Append a message to the log widget with color formatting"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Auto-detect level from message content if provided in brackets
        if message.startswith("[ERROR]"): level = "ERROR"
        elif message.startswith("[WARNING]"): level = "WARNING"
        elif "✅" in message or "[SUCCESS]" in message: level = "SUCCESS"
        elif "❌" in message: level = "ERROR"
        elif "⚠️" in message: level = "WARNING"
        
        # Clean up the message for display
        display_msg = message
        for tag in ["[INFO]", "[ERROR]", "[WARNING]", "[SUCCESS]"]:
            if display_msg.startswith(tag):
                display_msg = display_msg[len(tag):].strip()
        
        color_map = {
            "INFO": "#d4d4d4",
            "SUCCESS": "#4ec9b0",
            "WARNING": "#ce9178",
            "ERROR": "#f48771"
        }
        
        color = color_map.get(level, "#d4d4d4")
        formatted_msg = f'<span style="color: {color};">[{timestamp}] {display_msg}</span>'
        
        self.log_widget.append(formatted_msg)
        # Auto-scroll to bottom
        self.log_widget.verticalScrollBar().setValue(
            self.log_widget.verticalScrollBar().maximum()
        )
        
        # Update floating log if visible
        if self.log_window and self.log_window.isVisible():
            self.log_window.append_html(formatted_msg)
    
    def clear_log(self):
        """Clear the log widget"""
        self.log_widget.clear()
        if self.log_window:
            self.log_window.clear()
        self.append_log("Log limpiado.", "INFO")

    # --- Methods required by existing Commands (AddNodeCommand expects 'panel.canvas.load_workflow') ---
    # The commands were designed for the old panel structure. 
    # Luckily we named our canvas 'self.canvas' so it should work if commands access 'panel.canvas'.
    
    def load_workflow_list(self):
        # Populate list
        self.workflow_list.clear()
        try:
            if not os.path.exists("workflows"): os.makedirs("workflows")
            for f in os.listdir("workflows"):
                if f.endswith(".json"):
                    self.workflow_list.addItem(f.replace(".json", ""))
        except: pass

class LogWindow(QWidget):
    """Ventana flotante para mostrar el log"""
    def __init__(self, parent=None):
        super().__init__() # Es una ventana independiente, no hija directa en UI
        self.setWindowTitle("Monitor de Ejecución - RPA Framework")
        self.resize(600, 400)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                border: none;
            }
        """)
        layout.addWidget(self.text_edit)
        
        # Mantener siempre encima? Opcional
        self.setWindowFlags(Qt.WindowType.Window) 
        
    def append_html(self, html):
        self.text_edit.append(html)
        self.text_edit.verticalScrollBar().setValue(
            self.text_edit.verticalScrollBar().maximum()
        )

    def set_html(self, html):
        self.text_edit.setHtml(html)
        
    def clear(self):
        self.text_edit.clear()

class ZoomControls(QWidget):
    """Controles flotantes de zoom para el canvas"""
    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.setWindowFlags(Qt.WindowType.SubWindow)
        # Background semi-transparent
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Style for buttons
        btn_style = """
            QPushButton {
                background-color: rgba(255, 255, 255, 0.9);
                border: 1px solid #ccc;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
                color: #333;
                min-width: 30px;
                min-height: 30px;
            }
            QPushButton:hover {
                background-color: #e6f7ff;
                border-color: #1890ff;
            }
        """
        
        # Zoom Out
        btn_out = QPushButton("−")
        btn_out.setToolTip("Alejar")
        btn_out.setStyleSheet(btn_style)
        btn_out.clicked.connect(lambda: self.canvas.scale_view(1/1.2))
        layout.addWidget(btn_out)
        
        # Fit View
        btn_fit = QPushButton("⛶") # Unicode for square
        btn_fit.setToolTip("Ajustar a Ventana")
        btn_fit.setStyleSheet(btn_style)
        btn_fit.clicked.connect(self.fit_view)
        layout.addWidget(btn_fit)
        
        # Zoom In
        btn_in = QPushButton("+")
        btn_in.setToolTip("Acercar")
        btn_in.setStyleSheet(btn_style)
        btn_in.clicked.connect(lambda: self.canvas.scale_view(1.2))
        layout.addWidget(btn_in)
        
        # Container style
        self.container = QWidget() # Wrapper if needed, but direct layout on self works for subwindow
        
    def fit_view(self):
        self.canvas.fitInView(self.canvas.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.canvas._zoom = 1.0 # Reset internal zoom tracker roughly

