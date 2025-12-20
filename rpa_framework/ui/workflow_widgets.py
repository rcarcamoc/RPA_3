"""
Widgets personalizados para la interfaz de workflows del RPA Framework 3.

Este módulo contiene los componentes PyQt5 para visualizar y editar workflows.
"""

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from typing import Optional, Dict, List,Any
from core.models import Workflow, Node, NodeType, ActionNode, DecisionNode, LoopNode, Edge


class NodeGraphicsItem(QGraphicsRectItem):
    """Item gráfico para representar un nodo en el canvas"""
    
    # Colores por tipo de nodo
    COLORS = {
        NodeType.ACTION: QColor("#007bff"),  # Azul
        NodeType.DECISION: QColor("#ffc107"),  # Amarillo
        NodeType.LOOP: QColor("#28a745"),  # Verde
        NodeType.START: QColor("#6c757d"),  # Gris
        NodeType.END: QColor("#dc3545")  # Rojo
    }
    
    def __init__(self, node: Node, parent=None):
        super().__init__(0, 0, 150, 60, parent)
        self.node = node
        
        # Configurar apariencia
        self.setBrush(QBrush(self.COLORS.get(node.type, QColor("#999999"))))
        self.setPen(QPen(QColor("#333333"), 2))
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        
        # Añadir texto
        self.text_item = QGraphicsTextItem(self)
        self.text_item.setPlainText(node.label)
        self.text_item.setDefaultTextColor(Qt.white)
        
        # Centrar texto
        text_rect = self.text_item.boundingRect()
        text_x = (150 - text_rect.width()) / 2
        text_y = (60 - text_rect.height()) / 2
        self.text_item.setPos(text_x, text_y)
        
        # Posicionar nodo
        self.setPos(node.position.get("x", 0), node.position.get("y", 0))
    
    def get_center(self) -> QPointF:
        """Devuelve el punto central del nodo"""
        return QPointF(
            self.pos().x() + 75,
            self.pos().y() + 30
        )
    
    def paint(self, painter, option, widget):
        """Override para mostrar selección"""
        if option.state & QStyle.State_Selected:
            self.setPen(QPen(QColor("#000000"), 3, Qt.DashLine))
        else:
            self.setPen(QPen(QColor("#333333"), 2))
        super().paint(painter, option, widget)


class EdgeGraphicsItem(QGraphicsPathItem):
    """Item gráfico para representar una conexión entre nodos"""
    
    def __init__(self, from_item: NodeGraphicsItem, to_item: NodeGraphicsItem, parent=None):
        super().__init__(parent)
        self.from_item = from_item
        self.to_item = to_item
        
        # Configurar apariencia
        self.setPen(QPen(QColor("#666666"), 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        
        # Flecha
        self.arrow_head = QPolygonF()
        
        self.update_path()
    
    def update_path(self):
        """Actualiza el camino de la flecha"""
        start = self.from_item.get_center()
        start.setY(start.y() + 30)  # Desde la parte inferior del nodo
        
        end = self.to_item.get_center()
        end.setY(end.y() - 30)  # Hacia la parte superior del nodo
        
        path = QPainterPath()
        path.moveTo(start)
        
        # Línea curva si están en diferentes Y
        if abs(end.y() - start.y()) > 50:
            control1 = QPointF(start.x(), start.y() + (end.y() - start.y()) / 3)
            control2 = QPointF(end.x(), end.y() - (end.y() - start.y()) / 3)
            path.cubicTo(control1, control2, end)
        else:
            path.lineTo(end)
        
        self.setPath(path)
        
        # Calcular flecha
        angle = path.angleAtPercent(1.0)
        arrow_p1 = end - QPointF(
            10 * qCos(qDegreesToRadians(angle + 150)),
            -10 * qSin(qDegreesToRadians(angle + 150))
        )
        arrow_p2 = end - QPointF(
            10 * qCos(qDegreesToRadians(angle - 150)),
            -10 * qSin(qDegreesToRadians(angle - 150))
        )
        
        self.arrow_head = QPolygonF([end, arrow_p1, arrow_p2])
    
    def paint(self, painter, option, widget):
        """Override para dibujar flecha"""
        super().paint(painter, option, widget)
        painter.setBrush(QBrush(QColor("#666666")))
        painter.drawPolygon(self.arrow_head)


class WorkflowCanvas(QGraphicsView):
    """Canvas para visualizar workflows"""
    
    node_selected = pyqtSignal(Node)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Crear escena
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        # Configuración de la vista
        self.setRenderHint(QPainter.Antialiasing)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        
        # Fondo
        self.setBackgroundBrush(QBrush(QColor("#f5f5f5")))
        
        # Almacenar items
        self.node_items: Dict[str, NodeGraphicsItem] = {}
        self.edge_items: List[EdgeGraphicsItem] = []
    
    def load_workflow(self, workflow: Workflow):
        """Carga y visualiza un workflow"""
        # Limpiar escena
        self.scene.clear()
        self.node_items.clear()
        self.edge_items.clear()
        
        # Crear items para nodos
        for node in workflow.nodes:
            item = NodeGraphicsItem(node)
            self.scene.addItem(item)
            self.node_items[node.id] = item
        
        # Crear items para edges
        for edge in workflow.edges:
            if edge.from_node in self.node_items and edge.to_node in self.node_items:
                from_item = self.node_items[edge.from_node]
                to_item = self.node_items[edge.to_node]
                edge_item = EdgeGraphicsItem(from_item, to_item)
                self.scene.addItem(edge_item)
                self.edge_items.append(edge_item)
        
        # Ajustar vista
        self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
    
    def mousePressEvent(self, event):
        """Maneja clicks en nodos"""
        super().mousePressEvent(event)
        
        item = self.itemAt(event.pos())
        if isinstance(item, QGraphicsTextItem):
            item = item.parentItem()
        
        if isinstance(item, NodeGraphicsItem):
            self.node_selected.emit(item.node)


class NodePropertiesPanel(QWidget):
    """Panel para editar propiedades de nodos"""
    
    properties_changed = pyqtSignal(Node)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_node: Optional[Node] = None
        self.setup_ui()
    
    def setup_ui(self):
        """Configura la interfaz"""
        layout = QVBoxLayout(self)
        
        # Título
        title = QLabel("Propiedades del Nodo")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)
        
        # Formulario
        form = QFormLayout()
        
        # Nombre
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Nombre del nodo")
        form.addRow("Nombre:", self.name_edit)
        
        # Tipo
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Action", "Decision (IF)", "Loop"])
        self.type_combo.currentTextChanged.connect(self._on_type_changed)
        form.addRow("Tipo:", self.type_combo)
        
        # Script (para ACTION y LOOP)
        self.script_edit = QLineEdit()
        self.script_edit.setPlaceholderText("Ruta al script Python")
        self.script_label = QLabel("Script:")
        form.addRow(self.script_label, self.script_edit)
        
        # Condición (para DECISION)
        self.condition_edit = QTextEdit()
        self.condition_edit.setPlaceholderText("Ejemplo: status == 'success'")
        self.condition_edit.setMaximumHeight(60)
        self.condition_label = QLabel("Condición:")
        form.addRow(self.condition_label, self.condition_edit)
        
        # True Path (para DECISION)
        self.true_path_edit = QLineEdit()
        self.true_path_edit.setPlaceholderText("ID del nodo si TRUE")
        self.true_path_label = QLabel("Path TRUE:")
        form.addRow(self.true_path_label, self.true_path_edit)
        
        # False Path (para DECISION)
        self.false_path_edit = QLineEdit()
        self.false_path_edit.setPlaceholderText("ID del nodo si FALSE")
        self.false_path_label = QLabel("Path FALSE:")
        form.addRow(self.false_path_label, self.false_path_edit)
        
        # Iteraciones (para LOOP)
        self.iterations_edit = QLineEdit()
        self.iterations_edit.setPlaceholderText("Número o nombre de variable")
        self.iterations_label = QLabel("Iteraciones:")
        form.addRow(self.iterations_label, self.iterations_edit)
        
        layout.addLayout(form)
        
        # Botón Aplicar
        self.apply_btn = QPushButton("Aplicar Cambios")
        self.apply_btn.clicked.connect(self._apply_changes)
        layout.addWidget(self.apply_btn)
        
        layout.addStretch()
        
        # Ocultar campos no usados inicialmente
        self._hide_all_type_fields()
    
    def load_node(self, node: Node):
        """Carga un nodo para editar"""
        self.current_node = node
        
        # Llenar campos
        self.name_edit.setText(node.label)
        
        # Seleccionar tipo
        if node.type == NodeType.ACTION:
            self.type_combo.setCurrentText("Action")
        elif node.type == NodeType.DECISION:
            self.type_combo.setCurrentText("Decision (IF)")
        elif node.type == NodeType.LOOP:
            self.type_combo.setCurrentText("Loop")
        
        # Llenar campos específicos
        if isinstance(node, ActionNode):
            self.script_edit.setText(node.script)
        elif isinstance(node, DecisionNode):
            self.condition_edit.setPlainText(node.condition)
            self.true_path_edit.setText(node.true_path)
            self.false_path_edit.setText(node.false_path)
        elif isinstance(node, LoopNode):
            self.script_edit.setText(node.script)
            self.iterations_edit.setText(node.iterations)
    
    def _on_type_changed(self, type_text: str):
        """Muestra/oculta campos según el tipo"""
        self._hide_all_type_fields()
        
        if type_text == "Action":
            self.script_label.setVisible(True)
            self.script_edit.setVisible(True)
        elif type_text == "Decision (IF)":
            self.condition_label.setVisible(True)
            self.condition_edit.setVisible(True)
            self.true_path_label.setVisible(True)
            self.true_path_edit.setVisible(True)
            self.false_path_label.setVisible(True)
            self.false_path_edit.setVisible(True)
        elif type_text == "Loop":
            self.script_label.setVisible(True)
            self.script_edit.setVisible(True)
            self.iterations_label.setVisible(True)
            self.iterations_edit.setVisible(True)
    
    def _hide_all_type_fields(self):
        """Oculta todos los campos específicos de tipo"""
        self.script_label.setVisible(False)
        self.script_edit.setVisible(False)
        self.condition_label.setVisible(False)
        self.condition_edit.setVisible(False)
        self.true_path_label.setVisible(False)
        self.true_path_edit.setVisible(False)
        self.false_path_label.setVisible(False)
        self.false_path_edit.setVisible(False)
        self.iterations_label.setVisible(False)
        self.iterations_edit.setVisible(False)
    
    def _apply_changes(self):
        """Aplica cambios al nodo actual"""
        if not self.current_node:
            return
        
        # Actualizar nombre
        self.current_node.label = self.name_edit.text()
        
        # Actualizar campos específicos
        if isinstance(self.current_node, ActionNode):
            self.current_node.script = self.script_edit.text()
        elif isinstance(self.current_node, DecisionNode):
            self.current_node.condition = self.condition_edit.toPlainText()
            self.current_node.true_path = self.true_path_edit.text()
            self.current_node.false_path = self.false_path_edit.text()
        elif isinstance(self.current_node, LoopNode):
            self.current_node.script = self.script_edit.text()
            self.current_node.iterations = self.iterations_edit.text()
        
        self.properties_changed.emit(self.current_node)
