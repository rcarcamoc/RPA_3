"""
Panel de Workflows rediseñado con Ribbon Bar, Dirty State, Validación y Highlights de Ejecución.
Refactorizado de forma modular hacia ui/canvas/final_widgets.py y ui/panels/workflow_panel_final_mixin.py
manteniendo 100% de compatibilidad hacia atrás.
"""

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
from .canvas.final_widgets import WORKFLOW_STYLESHEET, LogWindowFinal, ZoomControlsFinal
from .panels.workflow_panel_final_mixin import WorkflowPanelFinalMixin

from core.models import Workflow, Node, NodeType, ActionNode, DecisionNode, LoopNode, WorkflowNode
from core.validator import WorkflowValidator


class WorkflowPanelFinal(WorkflowPanelFinalMixin, QWidget):
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
        center_layout.setContentsMargins(0, 0, 0, 0)
        
        self.canvas = WorkflowCanvasFinal(self)
        center_layout.addWidget(self.canvas)
        self.splitter.addWidget(center_container)
        
        # 2.3 PANEL DERECHO (Propiedades + Log Terminal)
        right_container = QWidget()
        right_layout = QVBoxLayout(right_container)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
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
