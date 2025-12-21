"""
Panel de Workflows para la GUI principal del RPA Framework 3.

Este módulo contiene el WorkflowPanel que integra el motor de ejecución
de workflows con la interfaz PyQt6.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QListWidget, QListWidgetItem, QPushButton, QLabel, 
    QTextEdit, QGroupBox, QFormLayout, QLineEdit, QComboBox,
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem,
    QGraphicsPathItem, QGraphicsEllipseItem, QMessageBox, QFileDialog, QApplication,
    QInputDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPointF, QRectF
from PyQt6.QtGui import QFont, QColor, QBrush, QPen, QPainterPath, QPolygonF, QPainter, QPainterPathStroker
from pathlib import Path
from datetime import datetime
import json
import os
import sys

# Añadir path para importar módulos core
sys.path.insert(0, str(Path(__file__).parent))

from core.models import Workflow, Node, NodeType, ActionNode, DecisionNode, LoopNode, Edge
from core.workflow_executor import WorkflowExecutor
from core.logger import WorkflowLogger


class WorkflowExecutorWorker(QThread):
    """Worker thread para ejecutar workflows sin bloquear la UI."""
    
    log_update = pyqtSignal(str)
    node_started = pyqtSignal(str)  # node_id cuando empieza
    node_finished = pyqtSignal(str)  # node_id cuando termina
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, workflow: Workflow, log_dir: str = "workflows/logs"):
        super().__init__()
        self.workflow = workflow
        self.log_dir = log_dir
        self.executor = None
    
    def run(self):
        try:
            self.executor = WorkflowExecutor(self.workflow, self.log_dir)
            
            # Parche para capturar logs en tiempo real y detectar nodos
            original_log = self.executor.logger.log
            current_node_id = [None]  # Usamos lista para poder modificar en closure
            
            def patched_log(message, level="INFO"):
                original_log(message, level)
                self.log_update.emit(f"[{level}] {message}")
                
                # Detectar inicio de nodo
                if "Ejecutando nodo:" in message:
                    # Buscar el nodo por label
                    for node in self.workflow.nodes:
                        if node.label in message:
                            if current_node_id[0]:
                                self.node_finished.emit(current_node_id[0])
                            current_node_id[0] = node.id
                            self.node_started.emit(node.id)
                            break
            
            self.executor.logger.log = patched_log
            
            result = self.executor.execute()
            
            # Emitir fin del ultimo nodo
            if current_node_id[0]:
                self.node_finished.emit(current_node_id[0])
            
            self.finished.emit(result)
            
        except Exception as e:
            self.error.emit(str(e))
    
    def stop(self):
        if self.executor:
            self.executor.stop()



class OutputPortItem(QGraphicsEllipseItem):
    """Puerto de salida visual para crear conexiones."""
    
    def __init__(self, parent=None):
        super().__init__(-6, -6, 12, 12, parent)
        self.setBrush(QBrush(QColor("#ffffff")))
        self.setPen(QPen(QColor("#333333"), 1.5))
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
    
    def hoverEnterEvent(self, event):
        self.setBrush(QBrush(QColor("#ff0000"))) # Red on hover
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        self.setBrush(QBrush(QColor("#ffffff")))
        super().hoverLeaveEvent(event)
    
    def mousePressEvent(self, event):
        # Iniciar arrastre de conexión
        views = self.scene().views()
        if views:
            view = views[0]
            if hasattr(view, 'start_connection_drag'):
                # Start drag from parent Node center-right
                view.start_connection_drag(self.parentItem(), self.mapToScene(self.rect().center()))
                event.accept()
        else:
            super().mousePressEvent(event)


class NodeGraphicsItem(QGraphicsRectItem):
    """Item grafico para representar un nodo en el canvas (con drag-drop)"""
    
    COLORS = {
        NodeType.ACTION: QColor("#007bff"),
        NodeType.DECISION: QColor("#ffc107"),
        NodeType.LOOP: QColor("#28a745"),
        NodeType.START: QColor("#6c757d"),
        NodeType.END: QColor("#dc3545")
    }
    
    def __init__(self, node: Node, parent=None):
        super().__init__(0, 0, 150, 60, parent)
        self.node = node
        
        self.setBrush(QBrush(self.COLORS.get(node.type, QColor("#999999"))))
        self.setPen(QPen(QColor("#333333"), 2))
        
        # Habilitar seleccion y arrastre
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        
        self.text_item = QGraphicsTextItem(self)
        self.text_item.setPlainText(node.label)
        self.text_item.setDefaultTextColor(Qt.GlobalColor.white)
        
        text_rect = self.text_item.boundingRect()
        text_x = (150 - text_rect.width()) / 2
        text_y = (60 - text_rect.height()) / 2
        self.text_item.setPos(text_x, text_y)
        
        self.setPos(node.position.get("x", 0), node.position.get("y", 0))
        
        # Cursor de arrastre
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        
        # Agregar puerto de salida (si no es END)
        if node.type != NodeType.END:
            self.output_port = OutputPortItem(self)
            self.output_port.setPos(150, 30)  # Lado derecho, centro vertical
    
    def get_center(self) -> QPointF:
        return QPointF(self.pos().x() + 75, self.pos().y() + 30)
    
    def highlight(self, active: bool = True):
        if active:
            self.setPen(QPen(QColor("#00ff00"), 3))
        else:
            self.setPen(QPen(QColor("#333333"), 2))
    
    def itemChange(self, change, value):
        """Sincroniza la posicion del nodo cuando se mueve"""
        if change == QGraphicsRectItem.GraphicsItemChange.ItemPositionHasChanged:
            # Actualizar posicion en el modelo
            self.node.position = {"x": value.x(), "y": value.y()}
            # Notificar a los edges conectados para que se actualicen
            if self.scene():
                for item in self.scene().items():
                    if isinstance(item, EdgeGraphicsItem):
                        if item.from_item == self or item.to_item == self:
                            item.update_path()
        return super().itemChange(change, value)
    
    def mousePressEvent(self, event):
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)
    
    def mouseReleaseEvent(self, event):
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        
        # Detectar si se soltó sobre un edge (para insertar nodo)
        if self.scene():
            # Buscar intersecciones con edges
            colliding = self.scene().collidingItems(self)
            for item in colliding:
                if isinstance(item, EdgeGraphicsItem):
                    # Solicitar división del edge
                    views = self.scene().views()
                    if views:
                        view = views[0]
                        if hasattr(view, 'request_split_edge'):
                            view.request_split_edge(self, item)
                            break
        
        super().mouseReleaseEvent(event)
    
    def mouseDoubleClickEvent(self, event):
        """Abre el script asociado al hacer doble click"""
        script_path = None
        
        # Obtener script segun tipo de nodo
        if hasattr(self.node, 'script') and self.node.script:
            script_path = self.node.script
        
        if script_path:
            # Construir ruta absoluta
            from pathlib import Path
            import subprocess
            
            full_path = Path(script_path)
            if not full_path.is_absolute():
                full_path = Path.cwd() / script_path
            
            if full_path.exists():
                # Abrir con el programa predeterminado del sistema
                try:
                    os.startfile(str(full_path))
                except Exception as e:
                    from PyQt6.QtWidgets import QMessageBox
                    QMessageBox.warning(None, "Error", f"No se pudo abrir el archivo:\n{e}")
            else:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(None, "Archivo no encontrado", 
                    f"El script no existe:\n{full_path}\n\nCrealo primero.")
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(None, "Sin script", 
                f"Este nodo ({self.node.type.value}) no tiene script asociado.")
        
        super().mouseDoubleClickEvent(event)


class EdgeGraphicsItem(QGraphicsPathItem):
    """Item grafico para conexiones entre nodos"""
    
    def __init__(self, from_item: NodeGraphicsItem, to_item: NodeGraphicsItem, parent=None):
        super().__init__(parent)
        self.from_item = from_item
        self.to_item = to_item
        
        self.setPen(QPen(QColor("#666666"), 2))
        self.update_path()
    
    def update_path(self):
        start = self.from_item.get_center()
        start.setY(start.y() + 30)
        
        end = self.to_item.get_center()
        end.setY(end.y() - 30)
        
        path = QPainterPath()
        path.moveTo(start)
        path.lineTo(end)
        
        self.setPath(path)
    
    def shape(self):
        """Area de colision mas ancha para facilitar seleccion."""
        path_stroker = QPainterPathStroker()
        path_stroker.setWidth(20) # Ancho de deteccion
        return path_stroker.createStroke(self.path())


class WorkflowCanvas(QGraphicsView):
    """Canvas para visualizar workflows"""
    
    node_selected = pyqtSignal(object)  # Node
    connection_created = pyqtSignal(str, str) # from_id, to_id
    edge_split_requested = pyqtSignal(object, str, str) # node_item, from_id, to_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        self.setStyleSheet("background-color: #f5f5f5; border: 1px solid #ccc;")
        
        self.node_items = {}
        self.edge_items = []
        
        # Estado de conexión visual
        self.is_connecting = False
        self.temp_line = None
        self.source_node = None
    
    def load_workflow(self, workflow: Workflow):
        self.scene.clear()
        self.node_items.clear()
        self.edge_items.clear()
        
        for node in workflow.nodes:
            item = NodeGraphicsItem(node)
            self.scene.addItem(item)
            self.node_items[node.id] = item
        
        for edge in workflow.edges:
            if edge.from_node in self.node_items and edge.to_node in self.node_items:
                from_item = self.node_items[edge.from_node]
                to_item = self.node_items[edge.to_node]
                edge_item = EdgeGraphicsItem(from_item, to_item)
                self.scene.addItem(edge_item)
                self.edge_items.append(edge_item)
        
        self.scene.setSceneRect(self.scene.itemsBoundingRect())
    
    def highlight_node(self, node_id: str, active: bool = True):
        if node_id in self.node_items:
            self.node_items[node_id].highlight(active)
    
    def clear_highlights(self):
        for item in self.node_items.values():
            item.highlight(False)
    
    def start_connection_drag(self, source_node, start_pos):
        """Inicia el arrastre de una nueva conexión."""
        self.is_connecting = True
        self.source_node = source_node
        
        self.temp_line = QGraphicsPathItem()
        self.temp_line.setPen(QPen(QColor("#666666"), 2, Qt.PenStyle.DashLine))
        self.scene.addItem(self.temp_line)
        
        # Iniciar linea
        path = QPainterPath(start_pos)
        path.lineTo(start_pos)
        self.temp_line.setPath(path)
    
    def mouseMoveEvent(self, event):
        if self.is_connecting and self.temp_line:
            # Actualizar linea temporal
            start_pos = self.temp_line.path().elementAt(0)
            end_pos = self.mapToScene(event.pos())
            
            path = QPainterPath(QPointF(start_pos.x, start_pos.y))
            path.lineTo(end_pos)
            self.temp_line.setPath(path)
            
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        if self.is_connecting:
            # Finalizar conexión
            end_pos = self.mapToScene(event.pos())
            items = self.scene.items(end_pos)
            
            target_node = None
            for item in items:
                if isinstance(item, NodeGraphicsItem) and item != self.source_node:
                    target_node = item
                    break
                elif isinstance(item, QGraphicsTextItem) and item.parentItem() != self.source_node:
                    if isinstance(item.parentItem(), NodeGraphicsItem):
                         target_node = item.parentItem()
                         break
            
            if target_node:
                self.connection_created.emit(self.source_node.node.id, target_node.node.id)
            
            # Limpiar estado
            self.is_connecting = False
            self.source_node = None
            if self.temp_line:
                self.scene.removeItem(self.temp_line)
                self.temp_line = None
                
        super().mouseReleaseEvent(event)

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        item = self.itemAt(event.pos())
        if isinstance(item, QGraphicsTextItem):
            item = item.parentItem()
        if isinstance(item, NodeGraphicsItem):
            self.node_selected.emit(item.node)
    
    def contextMenuEvent(self, event):
        """Menu contextual con click derecho"""
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtGui import QAction
        
        item = self.itemAt(event.pos())
        if isinstance(item, QGraphicsTextItem):
            item = item.parentItem()
        
        menu = QMenu(self)
        
        if isinstance(item, NodeGraphicsItem):
            # Menu para nodo
            node = item.node
            
            edit_action = menu.addAction("Editar propiedades")
            edit_action.triggered.connect(lambda: self.node_selected.emit(node))
            
            menu.addSeparator()
            
            highlight_action = menu.addAction("Resaltar")
            highlight_action.triggered.connect(lambda: item.highlight(True))
            
            unhighlight_action = menu.addAction("Quitar resaltado")
            unhighlight_action.triggered.connect(lambda: item.highlight(False))
            
            menu.addSeparator()
            
            delete_action = menu.addAction("Eliminar nodo")
            delete_action.triggered.connect(lambda: self._request_delete(node))
        else:
            # Menu para canvas vacio
            add_action = menu.addAction("Agregar nodo ACTION")
            add_action.triggered.connect(lambda: self._request_add_node("action", event.pos()))
            
            add_decision = menu.addAction("Agregar nodo DECISION")
            add_decision.triggered.connect(lambda: self._request_add_node("decision", event.pos()))
            
            add_loop = menu.addAction("Agregar nodo LOOP")
            add_loop.triggered.connect(lambda: self._request_add_node("loop", event.pos()))
            
            menu.addSeparator()
            
            clear_action = menu.addAction("Limpiar resaltados")
            clear_action.triggered.connect(self.clear_highlights)
        
        menu.exec(event.globalPos())
    
    def _request_delete(self, node: Node):
        """Emite señal para eliminar nodo"""
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "Confirmar",
            f"Eliminar nodo '{node.label}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            # Emitir senal de seleccion para que el panel lo maneje
            self.node_selected.emit(node)
    
    def _request_add_node(self, node_type: str, pos):
        """Solicita agregar un nuevo nodo en la posicion del click"""
        scene_pos = self.mapToScene(pos)
        # Por ahora solo loggeamos, la implementacion real conectara con el panel
        print(f"[Canvas] Agregar nodo {node_type} en ({scene_pos.x()}, {scene_pos.y()})")
        
    def request_split_edge(self, node_item, edge_item):
        """Solicita dividir un edge con un nodo."""
        from_id = edge_item.from_item.node.id
        to_id = edge_item.to_item.node.id
        self.edge_split_requested.emit(node_item.node, from_id, to_id)


class WorkflowPanel(QWidget):
    """Panel principal de Workflows para la GUI."""
    
    def __init__(self, config: dict = None):
        super().__init__()
        self.config = config or {}
        self.current_workflow = None
        self.worker = None
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
        
        btn_new = QPushButton("+ Nuevo")
        btn_new.setStyleSheet("background-color: #17a2b8; color: white; font-weight: bold; padding: 5px 15px;")
        btn_new.clicked.connect(self.create_new_workflow)
        header_layout.addWidget(btn_new)
        
        self.btn_save = QPushButton("Guardar")
        self.btn_save.setStyleSheet("background-color: #6c757d; color: white; font-weight: bold; padding: 5px 15px;")
        self.btn_save.clicked.connect(self.save_workflow)
        self.btn_save.setEnabled(False)
        header_layout.addWidget(self.btn_save)
        
        layout.addLayout(header_layout)
        
        # Splitter principal
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Panel izquierdo (Lista + Propiedades)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # Lista de workflows
        list_group = QGroupBox("Workflows Disponibles")
        list_layout = QVBoxLayout()
        
        self.workflow_list = QListWidget()
        self.workflow_list.itemClicked.connect(self.on_workflow_selected)
        list_layout.addWidget(self.workflow_list)
        
        btn_refresh = QPushButton("Recargar")
        btn_refresh.clicked.connect(self.load_workflow_list)
        list_layout.addWidget(btn_refresh)
        
        list_group.setLayout(list_layout)
        left_layout.addWidget(list_group)
        
        # Controles de ejecucion
        control_group = QGroupBox("Ejecucion")
        control_layout = QVBoxLayout()
        
        btn_layout = QHBoxLayout()
        
        self.btn_execute = QPushButton("Ejecutar")
        self.btn_execute.setStyleSheet("background-color: #28a745; color: white; font-weight: bold;")
        self.btn_execute.clicked.connect(self.execute_workflow)
        self.btn_execute.setEnabled(False)
        btn_layout.addWidget(self.btn_execute)
        
        self.btn_stop = QPushButton("Detener")
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
        
        # Botones de gestion de nodos
        node_btn_layout = QHBoxLayout()
        
        self.btn_add_node = QPushButton("+ Agregar")
        self.btn_add_node.setStyleSheet("background-color: #28a745; color: white;")
        self.btn_add_node.clicked.connect(self.add_node)
        self.btn_add_node.setEnabled(False)
        node_btn_layout.addWidget(self.btn_add_node)
        
        self.btn_delete_node = QPushButton("- Eliminar")
        self.btn_delete_node.setStyleSheet("background-color: #dc3545; color: white;")
        self.btn_delete_node.clicked.connect(self.delete_node)
        self.btn_delete_node.setEnabled(False)
        node_btn_layout.addWidget(self.btn_delete_node)
        
        self.btn_apply = QPushButton("Aplicar")
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
        self.prop_type.addItems(["action", "decision", "loop", "start", "end"])
        self.prop_type.currentTextChanged.connect(self.on_type_changed)
        props_layout.addRow("Tipo:", self.prop_type)
        
        # Script selector con combo y boton de refrescar
        script_layout = QHBoxLayout()
        self.prop_script = QComboBox()
        self.prop_script.setEditable(True)  # Permite escribir si es necesario
        self.prop_script.setPlaceholderText("Seleccionar script...")
        self.prop_script.setMinimumWidth(150)
        script_layout.addWidget(self.prop_script)
        
        btn_refresh_scripts = QPushButton("...")
        btn_refresh_scripts.setMaximumWidth(30)
        btn_refresh_scripts.setToolTip("Actualizar lista de scripts")
        btn_refresh_scripts.clicked.connect(self.load_script_list)
        script_layout.addWidget(btn_refresh_scripts)
        
        props_layout.addRow("Script:", script_layout)
        
        # Cargar lista inicial de scripts
        self.load_script_list()
        
        self.prop_condition = QLineEdit()
        self.prop_condition.setPlaceholderText("variable == 'valor'")
        props_layout.addRow("Condicion:", self.prop_condition)
        
        # Campos para Decision path
        self.prop_true_path = QLineEdit()
        self.prop_true_path.setPlaceholderText("ID nodo si TRUE")
        props_layout.addRow("TRUE ->:", self.prop_true_path)
        
        self.prop_false_path = QLineEdit()
        self.prop_false_path.setPlaceholderText("ID nodo si FALSE")
        props_layout.addRow("FALSE ->:", self.prop_false_path)
        
        self.prop_iterations = QLineEdit()
        self.prop_iterations.setPlaceholderText("3 o nombre_variable")
        props_layout.addRow("Iteraciones:", self.prop_iterations)
        
        # Campo para conectar al siguiente nodo
        self.prop_next_node = QLineEdit()
        self.prop_next_node.setPlaceholderText("ID del siguiente nodo")
        props_layout.addRow("Siguiente:", self.prop_next_node)
        
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
        
        # Proporciones del splitter
        splitter.setSizes([280, 400, 270])
        
        layout.addWidget(splitter)
        self.setLayout(layout)
    
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
        
        # Desconectar señal temporalmente para evitar triggers
        try:
            self.prop_script.currentTextChanged.disconnect(self.on_script_selected)
        except:
            pass
        
        self.prop_script.clear()
        
        # Directorios donde buscar scripts
        script_dirs = ["scripts", "recordings", "quick_scripts"]
        scripts_found = []
        
        for dir_name in script_dirs:
            dir_path = Path(dir_name)
            if dir_path.exists():
                for py_file in sorted(dir_path.glob("*.py")):
                    rel_path = str(py_file).replace("\\", "/")
                    scripts_found.append(rel_path)
        
        # Agregar al combo
        if scripts_found:
            self.prop_script.addItems(scripts_found)
        
        # Agregar opcion para examinar archivos externos
        self.prop_script.addItem("📁 Examinar...")
        
        # Reconectar señal
        self.prop_script.currentTextChanged.connect(self.on_script_selected)
        
        # Restaurar texto anterior si existe
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
            # Usuario canceló, deseleccionar
            self.prop_script.setCurrentIndex(-1)
            return
        
        file_path = Path(file_path)
        scripts_dir = Path("scripts")
        
        # Verificar si ya está en la carpeta de scripts
        try:
            file_path.relative_to(scripts_dir.resolve())
            # Ya está en scripts, usar directamente
            rel_path = str(file_path).replace("\\", "/")
            self.prop_script.setCurrentText(rel_path)
            return
        except ValueError:
            pass
        
        # Preguntar si quiere copiar
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
            # Copiar archivo
            import shutil
            scripts_dir.mkdir(parents=True, exist_ok=True)
            dest_path = scripts_dir / file_path.name
            
            # Si ya existe, preguntar
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
            
            # Recargar lista y seleccionar el copiado
            self.load_script_list()
            self.prop_script.setCurrentText(str(dest_path).replace("\\", "/"))
        else:
            # Usar ruta externa directamente
            self.prop_script.setCurrentText(str(file_path).replace("\\", "/"))
    
    def generate_node_id(self) -> str:
        """Genera un ID único para un nuevo nodo."""
        if not self.current_workflow:
            return "n1"
        
        # Buscar el número más alto existente
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
        
        # Llenar campos de propiedades
        self.prop_id.setText(node.id)
        self.prop_label.setText(node.label)
        self.prop_type.setCurrentText(node.type.value)
        
        # Limpiar campos especificos
        self.prop_script.clear()
        self.prop_condition.clear()
        self.prop_true_path.clear()
        self.prop_false_path.clear()
        self.prop_iterations.clear()
        self.prop_next_node.clear()
        
        # Llenar segun tipo
        if isinstance(node, ActionNode):
            self.prop_script.setCurrentText(node.script)
        elif isinstance(node, DecisionNode):
            self.prop_condition.setText(node.condition)
            self.prop_true_path.setText(node.true_path or "")
            self.prop_false_path.setText(node.false_path or "")
        elif isinstance(node, LoopNode):
            self.prop_script.setCurrentText(node.script)
            self.prop_iterations.setText(node.iterations)
        
        # Buscar conexion siguiente (para nodos no-decision)
        if self.current_workflow and not isinstance(node, DecisionNode):
            next_node_id = self.current_workflow.get_next_node(node.id)
            if next_node_id:
                self.prop_next_node.setText(next_node_id)
        
        # Trigger type change to enable/disable fields
        self.on_type_changed(node.type.value)
        
        self.log(f"Nodo seleccionado: {node.label} ({node.type.value})")
    
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
        if self.worker:
            self.worker.stop()
            self.log("Deteniendo ejecucion...")
    
    
    def on_log_update(self, message: str):
        """Actualiza el log en tiempo real."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        
        # Auto-scroll
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
        
        # Mostrar variables finales
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
    
    def create_new_workflow(self):
        """Crea un nuevo workflow vacio."""
        from PyQt6.QtWidgets import QInputDialog
        
        name, ok = QInputDialog.getText(self, "Nuevo Workflow", "Nombre del workflow:")
        if not ok or not name:
            return
        
        # Generar ID unico
        workflow_id = f"wf_{name.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Crear workflow basico con nodos Start y End
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
        
        # Mostrar en canvas
        self.canvas.load_workflow(self.current_workflow)
        self.btn_execute.setEnabled(True)
        self.btn_save.setEnabled(True)
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
        
        # Actualizar variables desde el campo de texto
        try:
            var_text = self.var_text.toPlainText().strip()
            if var_text:
                self.current_workflow.variables = json.loads(var_text)
        except json.JSONDecodeError as e:
            QMessageBox.warning(self, "Error", f"Variables JSON invalido:\n{e}")
            return
        
        # Guardar archivo
        workflows_dir = Path("workflows")
        workflows_dir.mkdir(parents=True, exist_ok=True)
        
        filename = f"{self.current_workflow.id}.json"
        filepath = workflows_dir / filename
        
        try:
            self.current_workflow.to_json(str(filepath))
            self.log(f"Workflow guardado: {filepath}")
            QMessageBox.information(self, "Guardado", f"Workflow guardado en:\n{filepath}")
            
            # Recargar lista
            self.load_workflow_list()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error guardando workflow:\n{e}")
            self.log(f"Error guardando: {e}")
    
    def on_workflow_selected(self, item: QListWidgetItem):
        """Carga el workflow seleccionado con validacion robusta."""
        if not item:
            return
        
        filepath = item.data(Qt.ItemDataRole.UserRole)
        
        # Validar que tenemos filepath
        if not filepath:
            self.log("Error: No se pudo obtener la ruta del workflow")
            return
        
        # Validar que el archivo existe
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
            self.btn_add_node.setEnabled(True)
            self.status_label.setText(f"Cargado: {self.current_workflow.name}")
            self.status_label.setStyleSheet("color: #28a745; font-weight: bold;")
            
            # Mostrar variables iniciales
            self.var_text.setText(json.dumps(self.current_workflow.variables, indent=2))
            
            # Limpiar propiedades
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
        # Generar ID automatico para el proximo nodo
        if self.current_workflow:
            next_id = self.generate_node_id()
            self.prop_id.setText(next_id)
        else:
            self.prop_id.clear()
        
        self.prop_label.clear()
        self.prop_script.setCurrentIndex(-1)  # Deseleccionar combo
        self.prop_condition.clear()
        self.prop_true_path.clear()
        self.prop_false_path.clear()
        self.prop_iterations.clear()
        self.prop_next_node.clear()
        self.btn_delete_node.setEnabled(False)
        self.btn_apply.setEnabled(False)
    
    def on_type_changed(self, type_text: str):
        """Muestra/oculta campos segun el tipo de nodo."""
        # Habilitar campos segun tipo
        is_action = type_text == "action"
        is_decision = type_text == "decision"
        is_loop = type_text == "loop"
        
        self.prop_script.setEnabled(is_action or is_loop)
        self.prop_condition.setEnabled(is_decision)
        self.prop_true_path.setEnabled(is_decision)
        self.prop_false_path.setEnabled(is_decision)
        self.prop_iterations.setEnabled(is_loop)
        self.prop_next_node.setEnabled(not is_decision)
    
    def add_node(self):
        """Agrega un nuevo nodo al workflow."""
        if not self.current_workflow:
            return
        
        node_id = self.prop_id.text().strip()
        node_label = self.prop_label.text().strip()
        node_type = self.prop_type.currentText()
        
        # Auto-generar ID si está vacío
        if not node_id:
            node_id = self.generate_node_id()
        
        if not node_label:
            node_label = f"Nodo {node_id}"
        
        # Verificar ID unico
        if self.current_workflow.get_node(node_id):
            QMessageBox.warning(self, "Error", f"Ya existe un nodo con ID '{node_id}'")
            return
        
        # Crear nodo segun tipo
        # Calcular posicion automatica
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
        else:
            new_node = Node(id=node_id, type=NodeType(node_type), label=node_label, position=new_pos)
        
        # Agregar nodo
        self.current_workflow.nodes.append(new_node)
        
        # Agregar conexion si se especifico siguiente
        next_node = self.prop_next_node.text().strip()
        if next_node and node_type != "decision":
            self.current_workflow.edges.append(Edge(from_node=node_id, to_node=next_node))
        
        # Actualizar canvas
        self.canvas.load_workflow(self.current_workflow)
        self.clear_node_fields()
        self.log(f"Nodo agregado: {node_label} ({node_type})")
        
        QMessageBox.information(self, "Nodo Agregado", f"Nodo '{node_label}' agregado.\nRecuerda guardar el workflow.")
    
    def delete_node(self):
        """Elimina el nodo seleccionado."""
        if not self.current_workflow or not hasattr(self, 'selected_node') or not self.selected_node:
            return
        
        node_id = self.selected_node.id
        node_label = self.selected_node.label
        
        # Confirmar
        reply = QMessageBox.question(
            self, "Confirmar Eliminacion",
            f"Eliminar nodo '{node_label}'?\n\nTambien se eliminaran las conexiones asociadas.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Eliminar nodo
        self.current_workflow.nodes = [n for n in self.current_workflow.nodes if n.id != node_id]
        
        # Eliminar conexiones
        self.current_workflow.edges = [
            e for e in self.current_workflow.edges 
            if e.from_node != node_id and e.to_node != node_id
        ]
        
        # Actualizar canvas
        self.selected_node = None
        self.canvas.load_workflow(self.current_workflow)
        self.clear_node_fields()
        self.log(f"Nodo eliminado: {node_label}")
    
    def apply_node_changes(self):
        """Aplica cambios al nodo seleccionado."""
        if not self.current_workflow or not hasattr(self, 'selected_node') or not self.selected_node:
            return
        
        node = self.selected_node
        
        # Actualizar propiedades basicas
        node.label = self.prop_label.text().strip() or node.label
        
        # Actualizar segun tipo
        if isinstance(node, ActionNode):
            node.script = self.prop_script.text().strip()
        elif isinstance(node, DecisionNode):
            node.condition = self.prop_condition.text().strip()
            node.true_path = self.prop_true_path.text().strip()
            node.false_path = self.prop_false_path.text().strip()
        elif isinstance(node, LoopNode):
            node.script = self.prop_script.text().strip()
            node.iterations = self.prop_iterations.text().strip() or "1"
        
        # Actualizar conexion siguiente (para no-decision nodes)
        if not isinstance(node, DecisionNode):
            next_node_id = self.prop_next_node.text().strip()
            # Eliminar conexion existente
            self.current_workflow.edges = [
                e for e in self.current_workflow.edges if e.from_node != node.id
            ]
            # Agregar nueva conexion
            if next_node_id:
                self.current_workflow.edges.append(Edge(from_node=node.id, to_node=next_node_id))
        
        # Actualizar canvas
        # Actualizar canvas
        self.canvas.load_workflow(self.current_workflow)
        self.log(f"Nodo actualizado: {node.label}")

    def on_connection_created(self, from_id: str, to_id: str):
        """Maneja la creación visual de conexiones."""
        if not self.current_workflow:
            return
            
        from_node = self.current_workflow.get_node(from_id)
        if not from_node:
            return

        # Prevenir auto-conexión
        if from_id == to_id:
            QMessageBox.warning(self, "Acción inválida", "No puedes conectar un nodo consigo mismo.")
            return

        # Lógica para DecisionNode
        if isinstance(from_node, DecisionNode):
            # Preguntar camino
            items = []
            if not from_node.true_path: items.append("TRUE")
            if not from_node.false_path: items.append("FALSE")
            
            # Si caminos están ocupados, permitir reescribir? Si.
            items = ["TRUE", "FALSE"]
            
            path, ok = QInputDialog.getItem(self, "Conexión de Decisión", 
                f"Conectar '{from_node.label}' -> '{to_id}' como:", items, 0, False)
            
            if not ok or not path:
                return
            
            # Actualizar modelo
            if path == "TRUE":
                from_node.true_path = to_id
            else:
                from_node.false_path = to_id
            
            # Reconstruir edges para asegurar consistencia
            # Eliminar edges antiguos de este nodo que coincidan con el path si es necesario
            # Simplificación: Agregar el nuevo edge. El canvas redibujará todo.
            # Nota: Si ya existía edge visual para ese path, deberíamos limpiarlo.
            # Pero Workflow.edges es lista simple. 
            pass # Se agrega abajo
            
        else:
            # Action/Loop/Start -> Solo 1 salida normal
            # Eliminar conexiones salientes previas
            self.current_workflow.edges = [e for e in self.current_workflow.edges if e.from_node != from_id]
            
            # Si estamos editando el nodo seleccionado, actualizar UI text
            if hasattr(self, 'selected_node') and self.selected_node and self.selected_node.id == from_id:
                self.prop_next_node.setText(to_id)
        
        # Eliminar cualquier edge duplicado exacto
        self.current_workflow.edges = [e for e in self.current_workflow.edges 
                                     if not (e.from_node == from_id and e.to_node == to_id)]
                                     
        # Agregar nueva conexión
        self.current_workflow.edges.append(Edge(from_node=from_id, to_node=to_id))
        
        # Recargar canvas
        self.canvas.load_workflow(self.current_workflow)
        self.log(f"Conexión creada: {from_id} -> {to_id}")

    def on_edge_split_requested(self, node: Node, from_id: str, to_id: str):
        """Maneja la inserción de un nodo en una conexión existente."""
        if not self.current_workflow: return
        
        reply = QMessageBox.question(
            self, "Insertar Nodo",
            f"¿Insertar nodo '{node.label}' entre '{from_id}' y '{to_id}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return

        # 1. Eliminar edge viejo
        self.current_workflow.edges = [e for e in self.current_workflow.edges 
            if not (e.from_node == from_id and e.to_node == to_id)]
            
        # Si era DecisionNode (A), actualizar path
        from_node = self.current_workflow.get_node(from_id)
        if isinstance(from_node, DecisionNode):
            if from_node.true_path == to_id:
                from_node.true_path = node.id
            if from_node.false_path == to_id:
                from_node.false_path = node.id
        
        # 2. Crear edge (A->Nodo)
        self.current_workflow.edges.append(Edge(from_node=from_id, to_node=node.id))
        
        # 3. Crear edge (Nodo->B)
        if not isinstance(node, DecisionNode):
            self.current_workflow.edges.append(Edge(from_node=node.id, to_node=to_id))
            # Actualizar next_node visualmente si seleccionamos el nodo insertado
            if hasattr(self, 'selected_node') and self.selected_node and self.selected_node.id == node.id:
                 self.prop_next_node.setText(to_id)
        else:
             # Si insertamos DecisionNode, conectamos true_path por defecto
             node.true_path = to_id
             self.current_workflow.edges.append(Edge(from_node=node.id, to_node=to_id))
        
        # Recargar
        self.canvas.load_workflow(self.current_workflow)
        self.log(f"Nodo insertado: {from_id} -> {node.id} -> {to_id}")

