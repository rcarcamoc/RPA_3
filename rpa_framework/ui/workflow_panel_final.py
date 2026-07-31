import os
import sys
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QPushButton, QLabel, 
    QStyle, QListWidget, QGroupBox, QTabWidget, QToolBar, QTextEdit, 
    QInputDialog, QMessageBox, QComboBox, QProgressBar, QDialog, QFrame,
    QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QAction, QKeySequence, QUndoStack, QIcon

from .node_palette_final import NodePaletteFinal
from .workflow_canvas_final import WorkflowCanvasFinal
from .panels.properties_panel_final import PropertiesPanelFinal
from .workflow_panel import WorkflowExecutorWorker
from .workflow_commands import AddNodeCommand, DeleteNodeCommand, MoveNodeCommand, ConnectionCommand, ModifyPropertyCommand

from core.models import Workflow, Node, NodeType, ActionNode, DecisionNode, LoopNode, WorkflowNode
from core.validator import WorkflowValidator

# ============================================================================
# STYLESHEET EXCLUSIVO PARA WORKFLOWS (MODERNO Y PREMIUM)
# ============================================================================
WORKFLOW_STYLESHEET = """
    /* Ribbon/Toolbar */
    QToolBar {
        background-color: #ffffff;
        border-bottom: 1px solid #e2e8f0;
        spacing: 12px;
        padding: 6px;
    }
    
    QToolBar QFrame {
        background-color: #cbd5e1;
        width: 1px;
        max-width: 1px;
        margin: 2px 4px;
    }
    
    /* Panel lateral de Workflows */
    #WorkflowList {
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        background-color: #ffffff;
        padding: 5px;
    }
    
    #WorkflowList::item {
        padding: 8px 12px;
        border-radius: 4px;
        color: #334155;
    }
    
    #WorkflowList::item:hover {
        background-color: #f1f5f9;
        color: #0f172a;
    }
    
    #WorkflowList::item:selected {
        background-color: #e2e8f0;
        color: #0f172a;
        font-weight: bold;
    }
    
    /* Log Panel */
    #LogTerminal {
        background-color: #0f172a;
        color: #e2e8f0;
        font-family: 'Consolas', 'Courier New', monospace;
        font-size: 11px;
        border: 1px solid #1e293b;
        border-radius: 6px;
        padding: 5px;
    }
    
    /* Botones de acción del Log */
    QPushButton#log_action_btn {
        background-color: transparent;
        border: none;
        padding: 4px;
        border-radius: 4px;
    }
    QPushButton#log_action_btn:hover {
        background-color: #f1f5f9;
    }
    
    /* Barra de Progreso */
    QProgressBar {
        border: 1px solid #e2e8f0;
        border-radius: 4px;
        text-align: center;
        background-color: #f1f5f9;
        color: #334155;
        font-weight: bold;
    }
    QProgressBar::chunk {
        background-color: #10b981;
        border-radius: 3px;
    }
"""

class LogWindowFinal(QDialog):
    """Ventana de log flotante rediseñada como QDialog para corregir el bug de la señal 'finished'"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Monitor de Ejecución en Tiempo Real")
        self.resize(700, 450)
        self.setWindowFlags(Qt.WindowType.Window)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setObjectName("LogTerminal")
        self.text_edit.setStyleSheet("""
            QTextEdit {
                background-color: #0f172a;
                color: #e2e8f0;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                border: none;
            }
        """)
        layout.addWidget(self.text_edit)
        
    def append_html(self, html):
        self.text_edit.append(html)
        self.text_edit.verticalScrollBar().setValue(
            self.text_edit.verticalScrollBar().maximum()
        )

    def set_html(self, html):
        self.text_edit.setHtml(html)
        
    def clear(self):
        self.text_edit.clear()


class ZoomControlsFinal(QWidget):
    """Pill bar flotante para controles de zoom en la esquina inferior del canvas"""
    
    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.setWindowFlags(Qt.WindowType.SubWindow)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)
        
        # Estilo Pill
        self.setObjectName("ZoomPill")
        self.setStyleSheet("""
            #ZoomPill {
                background-color: rgba(15, 23, 42, 0.85); /* Slate 900 semi-transparente */
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 18px;
            }
            QPushButton {
                background-color: transparent;
                border: none;
                color: #ffffff;
                font-weight: bold;
                font-size: 13px;
                min-width: 26px;
                min-height: 26px;
                border-radius: 13px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.15);
            }
            QLabel {
                color: #e2e8f0;
                font-weight: bold;
                font-size: 10px;
                padding: 0 4px;
            }
        """)
        
        btn_out = QPushButton("−")
        btn_out.setToolTip("Alejar (Ctrl+Wheel)")
        btn_out.clicked.connect(lambda: self.adjust_zoom(1/1.2))
        layout.addWidget(btn_out)
        
        self.lbl_pct = QLabel("100%")
        layout.addWidget(self.lbl_pct)
        
        btn_in = QPushButton("+")
        btn_in.setToolTip("Acercar (Ctrl+Wheel)")
        btn_in.clicked.connect(lambda: self.adjust_zoom(1.2))
        layout.addWidget(btn_in)
        
        btn_fit = QPushButton("⛶")
        btn_fit.setToolTip("Ajustar al Canvas")
        btn_fit.clicked.connect(self.fit_view)
        layout.addWidget(btn_fit)
        
    def adjust_zoom(self, factor):
        self.canvas.scale_view(factor)
        self.update_label()
        
    def fit_view(self):
        rect = self.canvas.scene.itemsBoundingRect()
        if not rect.isEmpty():
            self.canvas.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
            # Aproximar factor de escala actual
            transform = self.canvas.transform()
            self.canvas._zoom = transform.m11()
        else:
            self.canvas._zoom = 1.0
            self.canvas.resetTransform()
        self.update_label()
        
    def update_label(self):
        pct = int(self.canvas._zoom * 100)
        self.lbl_pct.setText(f"{pct}%")


class WorkflowPanelFinal(QWidget):
    """Panel de Workflows rediseñado con Ribbon Bar, Dirty State, Validación y Highlights de Ejecución"""
    
    def __init__(self, config: dict = None):
        super().__init__()
        self.config = config or {}
        self.current_workflow = None
        self.worker = None
        self.undo_stack = QUndoStack(self)
        self._is_dirty = False
        
        self.init_ui()
        self.setStyleSheet(WORKFLOW_STYLESHEET)
        
        # Conexión de señales del canvas
        self.canvas.node_selected.connect(self.on_node_selected)
        self.canvas.connection_created.connect(self.on_connection_created)
        self.canvas.connection_deleted.connect(self.on_connection_deleted)
        self.canvas.node_dropped.connect(self.create_node_from_palette)
        
        self.load_workflow_list()
        
    def set_dirty(self, dirty: bool):
        self._is_dirty = dirty
        self.update_breadcrumb()

    def update_breadcrumb(self):
        if self.current_workflow:
            state = " ● (Sin guardar)" if self._is_dirty else ""
            self.lbl_breadcrumb.setText(f"📂 <b>{self.current_workflow.name}.json</b>{state}")
            self.lbl_breadcrumb.setStyleSheet("color: #0f172a; font-size: 11px;")
        else:
            self.lbl_breadcrumb.setText("Ningún workflow activo")
            self.lbl_breadcrumb.setStyleSheet("color: #64748b; font-size: 11px;")

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # --- 1. RIBBON BAR (TOOLBAR GROUPED) ---
        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)
        
        # Grupo: Archivo
        self.act_new = QAction("Nuevo", self)
        self.act_new.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        self.act_new.triggered.connect(self.create_new_workflow)
        self.toolbar.addAction(self.act_new)
        
        self.act_save = QAction("Guardar", self)
        self.act_save.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        self.act_save.triggered.connect(self.save_workflow)
        self.toolbar.addAction(self.act_save)
        
        self.toolbar.addWidget(QFrame()) # Separador visual
        
        # Grupo: Edición
        self.act_undo = self.undo_stack.createUndoAction(self, "Deshacer")
        self.act_undo.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowBack))
        self.act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self.toolbar.addAction(self.act_undo)
        
        self.act_redo = self.undo_stack.createRedoAction(self, "Rehacer")
        self.act_redo.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowForward))
        self.act_redo.setShortcut(QKeySequence.StandardKey.Redo)
        self.toolbar.addAction(self.act_redo)
        
        self.toolbar.addWidget(QFrame()) # Separador visual
        
        # Grupo: Ejecución / Control
        self.act_validate = QAction("Validar", self)
        self.act_validate.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))
        self.act_validate.triggered.connect(self.validate_workflow)
        self.toolbar.addAction(self.act_validate)
        
        self.act_run = QAction("Ejecutar", self)
        self.act_run.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.act_run.triggered.connect(self.execute_workflow)
        self.toolbar.addAction(self.act_run)
        
        self.act_stop = QAction("Detener", self)
        self.act_stop.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop))
        self.act_stop.triggered.connect(self.stop_workflow)
        self.act_stop.setEnabled(False)
        self.toolbar.addAction(self.act_stop)
        
        # Información de estado / Breadcrumb
        self.toolbar.addSeparator()
        self.lbl_breadcrumb = QLabel("Ningún workflow activo")
        self.lbl_breadcrumb.setContentsMargins(10, 0, 0, 0)
        self.toolbar.addWidget(self.lbl_breadcrumb)
        
        main_layout.addWidget(self.toolbar)
        
        # --- 2. MAIN SPLITTER (Left | Center | Right) ---
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(2)
        
        # 2.1 PANEL IZQUIERDO (Selector de Workflow + Paleta de Nodos directamente)
        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(6, 6, 6, 6)
        left_layout.setSpacing(8)
        
        # Selector de Workflow Activo
        wf_select_group = QGroupBox("Workflow Activo")
        wf_select_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 10px;
                color: #0f172a;
            }
        """)
        wf_select_layout = QVBoxLayout(wf_select_group)
        wf_select_layout.setContentsMargins(8, 8, 8, 8)
        wf_select_layout.setSpacing(6)
        
        self.workflow_selector = QComboBox()
        self.workflow_selector.setStyleSheet("""
            QComboBox {
                padding: 6px;
                border: 1px solid #cbd5e1;
                border-radius: 5px;
                background-color: #ffffff;
                color: #0f172a;
            }
            QComboBox:focus {
                border: 1px solid #10b981;
            }
        """)
        self.workflow_selector.currentIndexChanged.connect(self.on_workflow_combo_changed)
        wf_select_layout.addWidget(self.workflow_selector)
        
        # Botones de Acción para Workflows
        wf_btn_layout = QHBoxLayout()
        wf_btn_layout.setSpacing(4)
        
        btn_refresh_wf = QPushButton("🔄 Recargar")
        btn_refresh_wf.setStyleSheet("padding: 4px 8px; font-size: 8pt;")
        btn_refresh_wf.clicked.connect(self.load_workflow_list)
        wf_btn_layout.addWidget(btn_refresh_wf)
        
        btn_dup_wf = QPushButton("👥 Duplicar")
        btn_dup_wf.setStyleSheet("padding: 4px 8px; font-size: 8pt;")
        btn_dup_wf.clicked.connect(self.duplicate_active_workflow)
        wf_btn_layout.addWidget(btn_dup_wf)
        
        btn_del_wf = QPushButton("🗑️ Eliminar")
        btn_del_wf.setStyleSheet("padding: 4px 8px; font-size: 8pt; background-color: #fef2f2; color: #ef4444;")
        btn_del_wf.clicked.connect(self.delete_active_workflow)
        wf_btn_layout.addWidget(btn_del_wf)
        
        wf_select_layout.addLayout(wf_btn_layout)
        left_layout.addWidget(wf_select_group)
        
        # Separador visual HLine
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        left_layout.addWidget(sep)
        
        # Paleta de Nodos directamente debajo (sin pestañas)
        self.node_palette = NodePaletteFinal()
        left_layout.addWidget(self.node_palette)
        
        self.splitter.addWidget(left_container)
        
        # 2.2 PANEL CENTRAL (Canvas)
        center_container = QWidget()
        center_layout = QVBoxLayout(center_container)
        center_layout.setContentsMargins(0,0,0,0)
        
        self.canvas = WorkflowCanvasFinal(self)
        center_layout.addWidget(self.canvas)
        self.splitter.addWidget(center_container)
        
        # 2.3 PANEL DERECHO (Propiedades + Log Terminal)
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0,0,0,0)
        
        self.right_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Panel Propiedades (Superior)
        self.properties_panel = PropertiesPanelFinal()
        self.properties_panel.node_updated.connect(self.on_node_updated)
        self.properties_panel.node_deleted.connect(self.on_node_deleted_req)
        self.properties_panel.hide()
        self.right_splitter.addWidget(self.properties_panel)
        
        # Log Terminal (Inferior)
        log_group = QWidget()
        log_layout = QVBoxLayout(log_group)
        log_layout.setContentsMargins(5, 5, 5, 5)
        log_layout.setSpacing(4)
        
        # Header de Terminal de Logs con Controles
        log_header = QWidget()
        log_header_layout = QHBoxLayout(log_header)
        log_header_layout.setContentsMargins(0, 2, 0, 2)
        log_header_layout.setSpacing(4)
        
        lbl_log_title = QLabel("Terminal de Ejecución")
        lbl_log_title.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        lbl_log_title.setStyleSheet("color: #475569;")
        log_header_layout.addWidget(lbl_log_title)
        
        log_header_layout.addStretch()
        
        # Selector de Nivel de Filtro
        self.log_filter = QComboBox()
        self.log_filter.addItems(["Todos los logs", "Éxitos", "Advertencias", "Errores"])
        self.log_filter.setFixedWidth(120)
        self.log_filter.setStyleSheet("QComboBox { padding: 2px 4px; font-size: 8pt; }")
        self.log_filter.currentIndexChanged.connect(self.refilter_logs)
        log_header_layout.addWidget(self.log_filter)
        
        # Copiar Log
        btn_copy_log = QPushButton()
        btn_copy_log.setObjectName("log_action_btn")
        btn_copy_log.setToolTip("Copiar logs al portapapeles")
        btn_copy_log.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        btn_copy_log.clicked.connect(self.copy_log_to_clipboard)
        log_header_layout.addWidget(btn_copy_log)
        
        # Limpiar Log
        btn_clear_log = QPushButton()
        btn_clear_log.setObjectName("log_action_btn")
        btn_clear_log.setToolTip("Limpiar consola")
        btn_clear_log.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        btn_clear_log.clicked.connect(self.clear_log)
        log_header_layout.addWidget(btn_clear_log)
        
        # Log Flotante Toggle
        btn_float_log = QPushButton()
        btn_float_log.setObjectName("log_action_btn")
        btn_float_log.setToolTip("Monitor Flotante")
        btn_float_log.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarNormalButton))
        btn_float_log.clicked.connect(self.show_floating_log)
        log_header_layout.addWidget(btn_float_log)
        
        log_layout.addWidget(log_header)
        
        # Barra de progreso integrada
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFont(QFont("Segoe UI", 7))
        log_layout.addWidget(self.progress_bar)
        
        # Widget Text Edit Terminal
        self.log_widget = QTextEdit()
        self.log_widget.setObjectName("LogTerminal")
        self.log_widget.setReadOnly(True)
        log_layout.addWidget(self.log_widget)
        
        self.right_splitter.addWidget(log_group)
        self.right_splitter.setSizes([380, 220])
        
        right_layout.addWidget(self.right_splitter)
        self.splitter.addWidget(right_container)
        
        # Splitter Layout Porcentajes: 15% | 63% | 22%
        self.splitter.setSizes([260, 820, 320])
        self.splitter.setCollapsible(1, False)
        
        main_layout.addWidget(self.splitter)
        
        # Monitor Flotante Lazy
        self.log_window = None
        
        # Controles de Zoom Pill Bar flotantes
        self.zoom_controls = ZoomControlsFinal(self.canvas, self.canvas)
        self.zoom_controls.show()
        
        # Monkey patch del canvas resize event para posicionar ZoomPill
        original_resize = self.canvas.resizeEvent
        def new_resize_event(event):
            original_resize(event)
            zc_width = self.zoom_controls.sizeHint().width()
            zc_height = self.zoom_controls.sizeHint().height()
            x = event.size().width() - zc_width - 15
            y = event.size().height() - zc_height - 15
            self.zoom_controls.move(x, y)
            self.zoom_controls.raise_()
            self.zoom_controls.update_label()
            
        self.canvas.resizeEvent = new_resize_event
        self.raw_logs_cache = [] # Caché para filtros de log

    # --- LOGICA DE COMANDOS Y SEÑALES ---

    def create_node_from_palette(self, node_def, pos):
        """Callback ejecutado por DropEvent del canvas"""
        if not self.current_workflow:
            self.create_new_workflow()
            
        import uuid
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
        if not self.current_workflow: return
        cmd = ConnectionCommand(self.current_workflow, from_id, to_id, self, is_add=True)
        self.undo_stack.push(cmd)
        self.set_dirty(True)

    def on_connection_deleted(self, from_id, to_id):
        if not self.current_workflow: return
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
        # Por comodidad empresarial, añadir nodo START y END por defecto
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
                import re
                self.current_workflow.name = new_name.strip()
                self.current_workflow.id = re.sub(r'[^a-zA-Z0-9]', '_', new_name.lower())
                name = self.current_workflow.name
            else:
                return
                
        if not os.path.exists("workflows"):
            os.makedirs("workflows", exist_ok=True)
            
        filepath = f"workflows/{name}.json"
        
        if os.path.exists(filepath) and self.current_workflow.id == "workflow_nuevo":
            ret = QMessageBox.question(self, "Sobrescribir", f"El archivo '{name}.json' ya existe. ¿Desea sobrescribirlo?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if ret == QMessageBox.StandardButton.No:
                return
                
        try:
            self.current_workflow.to_json(filepath)
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
                
        path = f"workflows/{name}.json"
        if os.path.exists(path):
            try:
                self.current_workflow = Workflow.from_json(path)
                self.canvas.load_workflow(self.current_workflow)
                self.properties_panel.hide()
                self.undo_stack.clear()
                self.set_dirty(False)
                self.prev_combo_index = index
                self.append_log(f"Workflow '{name}' cargado.", "SUCCESS")
                self.validate_workflow(silent=True)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error cargando el workflow:\n{e}")

    def load_workflow_list(self):
        self._loading_workflow_list = True
        self.workflow_selector.clear()
        self.workflow_selector.addItem("--- Seleccionar Workflow ---")
        
        active_index = 0
        try:
            if not os.path.exists("workflows"):
                os.makedirs("workflows")
                
            files = sorted([f for f in os.listdir("workflows") if f.endswith(".json")])
            for i, f in enumerate(files):
                wf_name = f.replace(".json", "")
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
            import shutil
            try:
                shutil.copy(f"workflows/{name}.json", f"workflows/{new_name}.json")
                dup_wf = Workflow.from_json(f"workflows/{new_name}.json")
                dup_wf.name = new_name
                import re
                dup_wf.id = re.sub(r'[^a-zA-Z0-9]', '_', new_name.lower())
                dup_wf.to_json(f"workflows/{new_name}.json")
                
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
                os.remove(f"workflows/{name}.json")
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
        
        # Limpiar warnings previos
        for item in self.canvas.node_items.values():
            item.set_warning("")
            
        errors = [r for r in results if r.get("severity") == "error"]
        warnings_list = [r for r in results if r.get("severity") == "warning"]
        
        # Mostrar detalles en los logs
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
        
        # Aplicar visualmente en el Canvas
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
        if not self.current_workflow: return
        
        # Forzar validación antes de ejecutar
        if not self.validate_workflow(silent=True):
            ret = QMessageBox.question(self, "Confirmar ejecución", 
                                     "El workflow tiene errores. ¿Desea ejecutarlo de todas formas?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if ret == QMessageBox.StandardButton.No:
                return

        self.append_log("🚀 Iniciando ejecución...", "SUCCESS")
        
        # Configurar barra de progreso
        steps_total = len(self.current_workflow.nodes)
        self.progress_bar.setMaximum(steps_total)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.progress_bar.setFormat("Inicializando... %p%")
        
        # Detener worker previo
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
        if self.worker:
            self.worker.stop()
            self.append_log("🛑 Detención solicitada.", "WARNING")

    def on_execution_finished(self, result):
        self.progress_bar.setVisible(False)
        self.act_run.setEnabled(True)
        self.act_stop.setEnabled(False)
        
        # Limpiar highlight de ejecución en todos los nodos
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
            
        # Actualizar barra de progreso con el nombre del nodo activo
        if "📍 Nodo actual:" in raw_message:
            node_label = raw_message.split("📍 Nodo actual:")[-1].strip()
            val = self.progress_bar.value() + 1
            self.progress_bar.setValue(min(val, self.progress_bar.maximum()))
            self.progress_bar.setFormat(f"Ejecutando: {node_label} (%p%)")
            
        # Quitar tags
        clean_msg = raw_message
        for tag in ["[INFO]", "[ERROR]", "[WARNING]", "[SUCCESS]"]:
            if clean_msg.startswith(tag):
                clean_msg = clean_msg[len(tag):].strip()
                
        self.append_log(clean_msg, level)

    def append_log(self, message: str, level: str = "INFO"):
        from datetime import datetime
        
        # Noise Filter
        noise = ["======", "Categorical units", "Dashboard actualizado"]
        if any(n in message for n in noise):
            return
            
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Guardar en caché crudo
        self.raw_logs_cache.append((timestamp, message, level))
        
        # Renderizar según filtro actual
        self.render_log_entry(timestamp, message, level)

    def render_log_entry(self, timestamp, message, level):
        filter_idx = self.log_filter.currentIndex()
        if filter_idx == 1 and level != "SUCCESS": return
        if filter_idx == 2 and level != "WARNING": return
        if filter_idx == 3 and level != "ERROR": return
        
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
        
        # Sincronizar contenido actual
        self.log_window.set_html(self.log_widget.toHtml())
        self.log_window.show()
        self.log_window.raise_()

    # --- CLOSE EVENT OVERRIDE ---
    
    def closeEvent(self, event):
        if self._is_dirty:
            ret = QMessageBox.question(
                self, "Cambios sin guardar",
                "Hay cambios pendientes en el workflow. ¿Desea guardarlos antes de salir?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel
            )
            if ret == QMessageBox.StandardButton.Yes:
                self.save_workflow()
                event.accept()
            elif ret == QMessageBox.StandardButton.No:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
