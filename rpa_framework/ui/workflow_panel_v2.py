from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QSplitter, 
                             QPushButton, QLabel, QStyle, QListWidget, QGroupBox,
                             QTabWidget, QToolBar)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QAction, QKeySequence, QUndoStack, QIcon

from .node_palette import NodePalette
from .workflow_panel import WorkflowCanvas, WorkflowExecutorWorker # Reusing Canvas logic
from .panels.properties_panel import PropertiesPanel
from .workflow_commands import AddNodeCommand, DeleteNodeCommand, MoveNodeCommand, ConnectionCommand, ModifyPropertyCommand
from core.models import Workflow, Node, NodeType, ActionNode, DecisionNode, LoopNode
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
        
        # 3. RIGHT PANEL (Properties)
        self.properties_panel = PropertiesPanel()
        self.properties_panel.node_updated.connect(self.on_node_updated)
        self.properties_panel.node_deleted.connect(self.on_node_deleted_req)
        self.properties_panel.hide() # Hidden by default
        
        self.splitter.addWidget(self.properties_panel)
        
        # Set Stretch Factors (15% | 65% | 20%)
        self.splitter.setSizes([250, 800, 300])
        self.splitter.setCollapsible(1, False) # Canvas not collapsible
        
        main_layout.addWidget(self.splitter)
        
        # self.status_bar = QLabel(" Listo")
        # self.status_bar.setStyleSheet("background: #eee; border-top: 1px solid #ccc; padding: 2px;")
        # main_layout.addWidget(self.status_bar)

    # --- LOGIC ---
    
    def on_workflow_list_click(self, item):
        # Load workflow logic (Simplified reuse)
        wf_name = item.text()
        wf_path = f"workflows/{wf_name}.json" # Assumption
        # Load...
        pass

    def create_new_workflow(self):
        self.current_workflow = Workflow(id="new_workflow", name="Nuevo Workflow")
        self.canvas.load_workflow(self.current_workflow)
        self.properties_panel.hide()
        # self.status_bar.setText(" Nuevo workflow creado.")

    def save_workflow(self):
        # TODO: Implement basic JSON save
        if self.current_workflow:
             print(" Guardado local (simulado).")
             
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
            'end': NodeType.END
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
        print(" 🚀 Ejecutando...")
        self.worker = WorkflowExecutorWorker(self.current_workflow)
        self.worker.log_update.connect(lambda msg: print(f"LOG: {msg}")) # Redirect to log widget if exists
        self.worker.finished.connect(lambda res: print(" ✅ Ejecución finalizada."))
        self.worker.start()
        
    def stop_workflow(self):
        if self.worker:
            self.worker.stop()
            print(" 🛑 Detenido.")

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
