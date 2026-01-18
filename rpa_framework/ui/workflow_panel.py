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
    QInputDialog, QStyle
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPointF, QRectF
from PyQt6.QtGui import QFont, QColor, QBrush, QPen, QPainterPath, QPolygonF, QPainter, QPainterPathStroker, QUndoStack, QKeySequence, QAction, QLinearGradient
from pathlib import Path
from datetime import datetime
import json
import os
import sys

# Importar comandos
from .workflow_commands import AddNodeCommand, DeleteNodeCommand, MoveNodeCommand, ConnectionCommand, ModifyPropertyCommand


# Añadir path para importar módulos core
sys.path.insert(0, str(Path(__file__).parent))

from core.models import Workflow, Node, NodeType, ActionNode, DecisionNode, LoopNode, Edge
from core.workflow_executor import WorkflowExecutor
from .node_palette import NodePalette
from .node_definitions import NodeDefinition
from core.logger import WorkflowLogger
from core.validator import WorkflowValidator


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
    
    # Enhanced color scheme with gradients
    NODE_STYLES = {
        NodeType.ACTION: {
            'color1': QColor("#4facfe"),
            'color2': QColor("#00f2fe"),
            'icon': "▶️",  # Play
            'shadow': QColor(79, 172, 254, 100)
        },
        NodeType.DECISION: {
            'color1': QColor("#f093fb"),
            'color2': QColor("#f5576c"),
            'icon': "◆",  # Diamond
            'shadow': QColor(240, 147, 251, 100)
        },
        NodeType.LOOP: {
            'color1': QColor("#43cea2"),
            'color2': QColor("#185a9d"),
            'icon': "↻",  # Circular arrows
            'shadow': QColor(67, 206, 162, 100)
        },
        NodeType.DATABASE: {
            'color1': QColor("#fa709a"),
            'color2': QColor("#fee140"),
            'icon': "🗄",  # Database
            'shadow': QColor(250, 112, 154, 100)
        },
        NodeType.ANNOTATION: {
            'color1': QColor("#ffffcc"),
            'color2': QColor("#fff9c4"),
            'icon': "📝",  # Note
            'shadow': QColor(255, 249, 196, 120),
            'dashed': True
        },
        NodeType.START: {
            'color1': QColor("#6c757d"),
            'color2': QColor("#95a5a6"),
            'icon': "🏁",  # Flag
            'shadow': QColor(108, 117, 125, 100)
        },
        NodeType.END: {
            'color1': QColor("#dc3545"),
            'color2': QColor("#c82333"),
            'icon': "✔️",  # Checkmark
            'shadow': QColor(220, 53, 69, 100)
        }
    }
    
    def __init__(self, node: Node, parent=None):
        # Variable size based on node type
        from core.annotation_node import AnnotationNode
        if isinstance(node, AnnotationNode):
            width = node.width
            height = node.height
        else:
            width = 180
            height = 80
        
        super().__init__(0, 0, width, height, parent)
        self.node = node
        self.node_width = width
        self.node_height = height
        
        self.is_highlighted = False
        self.has_warning = False
        self.execution_state = None  # 'running', 'success', 'error'
        
        # Get style for this node type
        style = self.NODE_STYLES.get(node.type, self.NODE_STYLES[NodeType.ACTION])
        
        # Create gradient brush
        gradient = QLinearGradient(0, 0, 0, height)
        gradient.setColorAt(0, style['color1'])
        gradient.setColorAt(1, style['color2'])
        self.setBrush(QBrush(gradient))
        
        # Pen style (dashed for annotations)
        pen_style = Qt.PenStyle.DashLine if style.get('dashed') else Qt.PenStyle.SolidLine
        self.setPen(QPen(QColor("#333333"), 2, pen_style))
        
        # Habilitar seleccion y arrastre
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        
        # Icon text
        self.icon_item = QGraphicsTextItem(self)
        self.icon_item.setPlainText(style['icon'])
        icon_font = QFont("Segoe UI Emoji", 16)
        self.icon_item.setFont(icon_font)
        self.icon_item.setDefaultTextColor(Qt.GlobalColor.white)
        self.icon_item.setPos(10, (height - 20) / 2)
        
        # Label text
        self.text_item = QGraphicsTextItem(self)
        self.text_item.setPlainText(node.label)
        label_font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        self.text_item.setFont(label_font)
        self.text_item.setDefaultTextColor(Qt.GlobalColor.white)
        
        text_rect = self.text_item.boundingRect()
        text_x = 40  # After icon
        text_y = (height - text_rect.height()) / 2
        self.text_item.setPos(text_x, text_y)
        
        # For annotations, show text content below label
        if isinstance(node, AnnotationNode) and node.text:
            self.annotation_text = QGraphicsTextItem(self)
            self.annotation_text.setPlainText(node.text[:100])  # Truncate
            anno_font = QFont("Segoe UI", 8)
            self.annotation_text.setFont(anno_font)
            self.annotation_text.setDefaultTextColor(QColor("#666666"))
            self.annotation_text.setPos(10, 35)
        
        self.setPos(node.position.get("x", 0), node.position.get("y", 0))
        
        # Cursor de arrastre
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        
        # Agregar puerto de salida (si no es END ni ANNOTATION)
        if node.type not in [NodeType.END, NodeType.ANNOTATION]:
            self.output_port = OutputPortItem(self)
            self.output_port.setPos(width / 2, height)  # Parte inferior, centro horizontal
        
        # Aplicar opacidad si el nodo está deshabilitado
        if not node.enabled:
            self.setOpacity(0.4)
    
    def get_center(self) -> QPointF:
        return QPointF(self.pos().x() + self.node_width / 2, self.pos().y() + self.node_height / 2)
    
    def highlight(self, active: bool = True):
        self.is_highlighted = active
        self._update_appearance()
        
    def set_warning(self, message: str):
        self.has_warning = bool(message)
        self.setToolTip(f"⚠️ {message}" if message else "")
        self._update_appearance()
        
    def _update_appearance(self):
        if self.is_highlighted:
            self.setPen(QPen(QColor("#00ff00"), 3))
        elif self.has_warning:
            self.setPen(QPen(QColor("#dc3545"), 3))
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
        super().mouseReleaseEvent(event)
        
        # Solo intentar split si hubo arrastre (evita activarse con click simple o doble click)
        start_pos = event.buttonDownScenePos(Qt.MouseButton.LeftButton)
        end_pos = event.scenePos()
        if (start_pos - end_pos).manhattanLength() < 5:
            return
        
        # Detectar si se soltó sobre un edge (para insertar nodo)
        if self.scene():
            # Buscar intersecciones con edges
            colliding = self.scene().collidingItems(self)
            for item in colliding:
                if isinstance(item, EdgeGraphicsItem):
                    # Ignorar propios edges conectadas
                    if item.from_item == self or item.to_item == self:
                        continue
                        
                    # Solicitar división del edge
                    views = self.scene().views()
                    if views:
                        view = views[0]
                        if hasattr(view, 'request_split_edge'):
                            view.request_split_edge(self, item)
                            break
    
    def mouseDoubleClickEvent(self, event):
        """Abre el script asociado al hacer doble click"""
        script_path_str = None
        
        # Obtener script segun tipo de nodo
        if hasattr(self.node, 'script') and self.node.script:
            script_path_str = self.node.script
        
        if script_path_str:
            from pathlib import Path
            import os
            
            script_path = Path(script_path_str)
            
            # Si la ruta no es absoluta, buscar en las carpetas estándar de grabaciones
            if not script_path.is_absolute():
                possible_paths = [
                    Path.cwd() / script_path_str,
                    Path.cwd() / "rpa_framework" / script_path_str,
                    Path.cwd() / "recordings" / script_path_str,
                    Path.cwd() / "rpa_framework" / "recordings" / script_path_str,
                    Path.cwd() / "rpa_framework" / "recordings" / "web" / script_path_str,
                    Path.cwd() / "recordings" / "web" / script_path_str,
                ]
                
                for p in possible_paths:
                    if p.exists():
                        script_path = p
                        break
            
            if script_path.exists():
                # Abrir con el programa predeterminado del sistema
                try:
                    self.node.script = str(script_path) # Actualizar a ruta real si se encontró
                    os.startfile(str(script_path))
                except Exception as e:
                    from PyQt6.QtWidgets import QMessageBox
                    QMessageBox.warning(None, "Error", f"No se pudo abrir el archivo:\n{e}")
            else:
                from PyQt6.QtWidgets import QMessageBox
                formatted_paths = "\n".join([str(p) for p in possible_paths[:3]])
                QMessageBox.warning(None, "Archivo no encontrado", 
                    f"El script '{script_path_str}' no se encuentra en las rutas de búsqueda.\n\n"
                    f"Asegúrate de que el archivo exista en la carpeta 'recordings'.")
        else:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(None, "Sin script", 
                f"Este nodo no tiene un script Python asociado.")
        
        super().mouseDoubleClickEvent(event)


class EdgeGraphicsItem(QGraphicsPathItem):
    """Item grafico para conexiones entre nodos"""
    
    def __init__(self, from_item: NodeGraphicsItem, to_item: NodeGraphicsItem, parent=None):
        super().__init__(parent)
        self.from_item = from_item
        self.to_item = to_item
        
        self.setPen(QPen(QColor("#666666"), 2))
        self.setAcceptHoverEvents(True)  # Enable hover for insert button
        self.update_path()
        
        # Insert button (created on demand)
        self.insert_button = None
    
    def update_path(self):
        # CONEXIONES VERTICALES: de abajo hacia arriba
        # Start point (Output port if available, else center-bottom)
        if hasattr(self.from_item, 'output_port') and self.from_item.output_port:
            start = self.from_item.mapToScene(self.from_item.output_port.pos())
        else:
            start = self.from_item.get_center()
            start.setY(start.y() + self.from_item.node_height / 2)  # Parte inferior del nodo
        
        # End point (Input port logic - usually center-top)
        end = self.to_item.get_center()
        end.setY(end.y() - self.to_item.node_height / 2)  # Parte superior del nodo
        
        path = QPainterPath()
        path.moveTo(start)
        
        # Cubic Bezier for smooth curve (VERTICAL)
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        # Control points para curva vertical
        ctrl1 = QPointF(start.x(), start.y() + dy * 0.5)
        ctrl2 = QPointF(end.x(), end.y() - dy * 0.5)
        
        path.cubicTo(ctrl1, ctrl2, end)
        
        self.setPath(path)
    
    def contextMenuEvent(self, event):
        from PyQt6.QtWidgets import QMenu
        menu = QMenu()
        delete_action = menu.addAction("🗑️ Eliminar Conexión")
        action = menu.exec(event.screenPos())
        
        if action == delete_action:
            # Emit signal via scene/view or handle directly
            views = self.scene().views()
            if views:
                view = views[0]
                if hasattr(view, 'request_delete_edge'):
                    view.request_delete_edge(self)
                else:
                    # Fallback: eliminar directamente
                    self._delete_connection()
    
    def hoverEnterEvent(self, event):
        # Show insert button
        if not self.insert_button:
            # Import here to avoid circular dependency
            from ui.insert_node_button import InsertNodeButton
            self.insert_button = InsertNodeButton(self, self)
        
        # Position button at hover point
        self.insert_button.setPos(event.pos())
        self.insert_button.setVisible(True)
        
        # Highlight edge
        self.setPen(QPen(QColor("#28a745"), 3))
        super().hoverEnterEvent(event)
    
    def hoverMoveEvent(self, event):
        # Move button with cursor
        if self.insert_button:
            self.insert_button.setPos(event.pos())
        super().hoverMoveEvent(event)
    
    def hoverLeaveEvent(self, event):
        # Hide button
        if self.insert_button:
            self.insert_button.setVisible(False)
        
        # Un-highlight edge
        self.setPen(QPen(QColor("#666666"), 2))
        super().hoverLeaveEvent(event)
    
    def on_insert_requested(self, click_pos):
        """Called when user clicks the + button"""
        # Get the view to show node type selector
        views = self.scene().views()
        if views:
            view = views[0]
            if hasattr(view, 'show_insert_node_menu'):
                view.show_insert_node_menu(self, click_pos)
    
    def shape(self):
        """Area de colision mas ancha para facilitar seleccion."""
        path_stroker = QPainterPathStroker()
        path_stroker.setWidth(20) # Ancho de deteccion
        return path_stroker.createStroke(self.path())


class WorkflowCanvas(QGraphicsView):
    """Canvas para visualizar workflows"""
    
    node_selected = pyqtSignal(object)  # Node
    connection_created = pyqtSignal(str, str) # from_id, to_id
    connection_deleted = pyqtSignal(str, str) # from_id, to_id
    edge_split_requested = pyqtSignal(object, str, str) # node_item, from_id, to_id
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # Mejorar UX de zoom
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        
        # Habilitar Drop
        self.setAcceptDrops(True)
        
        # Variables de estado
        self.is_connecting = False
        self.source_node = None
        self.temp_line = None
        
        self.scene.selectionChanged.connect(self.on_selection_changed)
        
        self.setStyleSheet("background-color: #f5f5f5; border: 1px solid #ccc;")
        
        self.node_items = {}
        self.edge_items = []
        
        # Estado Navegación
        self._zoom = 1.0
        self._panning = False
        self._pan_start = None

    def on_selection_changed(self):
        """Notifica cambio de seleccion"""
        items = self.scene.selectedItems()
        if items and isinstance(items[0], NodeGraphicsItem):
            self.node_selected.emit(items[0].node)

    def wheelEvent(self, event):
        """Zoom con Ctrl + Rueda"""
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)
            
    def zoom_in(self):
        self.scale_view(1.2)
        
    def zoom_out(self):
        self.scale_view(1 / 1.2)
        
    def zoom_reset_view(self):
        self._zoom = 1.0
        self.resetTransform()
        
    def scale_view(self, factor):
        new_zoom = self._zoom * factor
        # Limitar zoom (0.2x a 5.0x)
        if new_zoom < 0.2: 
            factor = 0.2 / self._zoom
            new_zoom = 0.2
        elif new_zoom > 5.0:
            factor = 5.0 / self._zoom
            new_zoom = 5.0
            
        self._zoom = new_zoom
        self.scale(factor, factor)
    
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
        if self._panning:
            h_bar = self.horizontalScrollBar()
            v_bar = self.verticalScrollBar()
            delta = event.pos() - self._pan_start
            h_bar.setValue(h_bar.value() - delta.x())
            v_bar.setValue(v_bar.value() - delta.y())
            self._pan_start = event.pos()
            event.accept()
            return
            
        if self.is_connecting and self.temp_line:
            # Actualizar linea temporal
            start_pos = self.temp_line.path().elementAt(0)
            end_pos = self.mapToScene(event.pos())
            
            path = QPainterPath(QPointF(start_pos.x, start_pos.y))
            path.lineTo(end_pos)
            self.temp_line.setPath(path)
            
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton and self._panning:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            event.accept()
            return

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
            
            # Guardar IDs antes de limpiar
            source_id = self.source_node.node.id if self.source_node else None
            target_id = target_node.node.id if target_node else None
            
            # Limpiar estado ANTES de emitir señal (evita crash si la señal limpia la escena)
            if self.temp_line:
                if self.temp_line.scene() == self.scene:
                    self.scene.removeItem(self.temp_line)
                self.temp_line = None
            
            self.is_connecting = False
            self.source_node = None
            
            # Emitir señal
            if source_id and target_id:
                self.connection_created.emit(source_id, target_id)
                
        super().mouseReleaseEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)
            
            # Detectar selección de nodo
            item = self.itemAt(event.pos())
            if isinstance(item, QGraphicsTextItem):
                item = item.parentItem()
            if isinstance(item, NodeGraphicsItem):
                self.node_selected.emit(item.node)
    
    def contextMenuEvent(self, event):
        """Menu contextual con click derecho"""
        from PyQt6.QtWidgets import QMenu
        from PyQt6.QtGui import QAction
        
        # Convertir posición del evento a coordenadas de la escena
        scene_pos = self.mapToScene(event.pos())
        
        # Buscar items en el punto de clic (con un pequeño margen de tolerancia)
        # Creamos un rectangulo pequeño alrededor del clic para facilitar la seleccion de lineas
        click_area = QRectF(scene_pos.x() - 5, scene_pos.y() - 5, 10, 10)
        items = self.scene.items(click_area)
        
        # Prioridad: Nodos > Edges > Fondo
        selected_node = None
        selected_edge = None
        
        for item in items:
            if isinstance(item, QGraphicsTextItem):
                item = item.parentItem()
            
            if isinstance(item, NodeGraphicsItem):
                selected_node = item
                break # Prioridad máxima, si clicamos un nodo es un nodo
            elif isinstance(item, EdgeGraphicsItem) and not selected_edge:
                selected_edge = item
        
        menu = QMenu(self)
        
        if selected_node:
            item = selected_node
            # Menu para nodo
            node = item.node
            
            edit_action = menu.addAction("✏️ Editar propiedades")
            edit_action.triggered.connect(lambda: self.node_selected.emit(node))
            
            menu.addSeparator()
            
            # Toggle enabled/disabled
            if node.enabled:
                toggle_action = menu.addAction("🚫 Deshabilitar Nodo")
                toggle_action.triggered.connect(lambda: self._toggle_node_enabled(item, False))
            else:
                toggle_action = menu.addAction("✅ Habilitar Nodo")
                toggle_action.triggered.connect(lambda: self._toggle_node_enabled(item, True))
            
            menu.addSeparator()
            
            # Menu de nodo
            action = menu.addAction("🗑️ Eliminar Nodo")
            action.triggered.connect(lambda: self._request_delete(item.node)) # Changed to _request_delete
        elif selected_edge:
            action = menu.addAction("🗑️ Eliminar Conexión")
            action.triggered.connect(lambda: self.request_delete_edge(selected_edge))
        else:
            # Menu de canvas
            add_menu = menu.addMenu("Agregar Nodo")
            
            action = add_menu.addAction("▶️ ACTION")
            action.triggered.connect(lambda: self._request_add_node("action", event.pos()))
            
            decision = add_menu.addAction("◆ DECISION")
            decision.triggered.connect(lambda: self._request_add_node("decision", event.pos()))
            
            loop = add_menu.addAction("↻ LOOP")
            loop.triggered.connect(lambda: self._request_add_node("loop", event.pos()))
            
            db = add_menu.addAction("🗄 DATABASE")
            db.triggered.connect(lambda: self._request_add_node("database", event.pos()))
            
            note = add_menu.addAction("📝 ANNOTATION")
            note.triggered.connect(lambda: self._request_add_node("annotation", event.pos()))

        menu.exec(event.globalPos())
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
            
    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
            
    def dropEvent(self, event):
        node_id_type = event.mimeData().text()
        drop_pos = self.mapToScene(event.position().toPoint())
        
        # Create node via parent panel
        # Necesitamos comunicar esto al WorkflowPanel para que use su logica centralizada (undo, etc)
        # O emitimos una señal
        self.create_node_from_drop(node_id_type, drop_pos)
        event.acceptProposedAction()
        
    def create_node_from_drop(self, node_def_id, pos):
        """Crea nodo desde drop de paleta"""
        # Buscar definicion
        from .node_definitions import get_all_nodes
        
        node_def = next((n for n in get_all_nodes() if n.id == node_def_id), None)
        if not node_def:
            return
            
        # Delegar creacion al padre (WorkflowPanel) si es posible para usar AddNodeCommand
        # O emitir señal. WorkflowPanel tiene 'add_node_at_pos(type, pos, props)'?
        # WorkflowPanel tiene `add_node` pero usa props UI.
        
        # Vamos a emitir una señal nueva para solicitar creacion
        # Pero WorkflowCanvas no tiene señal definida para esto aun, vamos a usar una referencia al padre o emitir
        # Hack: self.parentWidget() es el layout container, seguimos subiendo
        
        # Mejor opcion: Agregar nueva señal a WorkflowCanvas
        parent = self.parentWidget()
        while parent and not hasattr(parent, 'create_node_from_palette'):
            parent = parent.parentWidget()
            
        if parent:
            parent.create_node_from_palette(node_def, pos)

    def _request_add_node(self, node_type, pos):
        """Solicita agregar nodo en posicion (desde context menu)"""
        scene_pos = self.mapToScene(pos)
        # Emit signal to parent (WorkflowPanel) to add node
        # Hack: access parent directly for now as per existing pattern
        # El codigo original usaba signals o direct calls?
        # Revisando contextMenuEvent original... llamaba a metodos que no vi completos.
        # Vamos a asumir que WorkflowPanel maneja esto.
        
        # Para mantener compatibilidad con el codigo existente, vamos a usar la referencia al panel padre
        views_parent = self.parentWidget()
        while views_parent and not hasattr(views_parent, 'add_node_interactive'):
             views_parent = views_parent.parentWidget()
        
        if views_parent:
            views_parent.add_node_interactive(node_type, scene_pos)
    
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
    
    def _toggle_node_enabled(self, node_item: NodeGraphicsItem, enabled: bool):
        """Habilita o deshabilita un nodo"""
        node_item.node.enabled = enabled
        # Actualizar apariencia visual
        if enabled:
            node_item.setOpacity(1.0)
        else:
            node_item.setOpacity(0.4)
        # Actualizar tooltip
        if not enabled:
            current_tooltip = node_item.toolTip()
            node_item.setToolTip(f"🚫 DESHABILITADO\n{current_tooltip}" if current_tooltip else "🚫 DESHABILITADO")
        else:
            # Limpiar tooltip de deshabilitado
            current_tooltip = node_item.toolTip()
            if current_tooltip.startswith("🚫 DESHABILITADO"):
                node_item.setToolTip(current_tooltip.replace("🚫 DESHABILITADO\n", ""))
    
    def request_delete_edge(self, edge_item: EdgeGraphicsItem):
        """Solicita eliminar una conexión"""
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "Confirmar",
            "¿Eliminar esta conexión?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            from_id = edge_item.from_item.node.id
            to_id = edge_item.to_item.node.id
            # Emitir señal para que el panel lo maneje
            self.connection_deleted.emit(from_id, to_id)
        
    def request_split_edge(self, node_item, edge_item):
        """Solicita dividir un edge con un nodo."""
        from_id = edge_item.from_item.node.id
        to_id = edge_item.to_item.node.id
        self.edge_split_requested.emit(node_item.node, from_id, to_id)
    
    def show_insert_node_menu(self, edge_item, scene_pos):
        """Muestra menu para insertar nodo en edge"""
        from PyQt6.QtWidgets import QMenu
        
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { font-size: 10pt; }")
        
        # Node type options
        action_option = menu.addAction("▶️ ACTION")
        decision_option = menu.addAction("◆ DECISION")  
        loop_option = menu.addAction("↻ LOOP")
        db_option = menu.addAction("🗄 DATABASE")
        menu.addSeparator()
        annotation_option = menu.addAction("📝 ANNOTATION")
        
        # Show menu at cursor position  
        view_pos = self.mapFromScene(scene_pos)
        global_pos = self.mapToGlobal(view_pos)
        
        selected_action = menu.exec(global_pos)
        
        if selected_action:
            # Determine node type
            node_type_map = {
                action_option: NodeType.ACTION,
                decision_option: NodeType.DECISION,
                loop_option: NodeType.LOOP,
                db_option: NodeType.DATABASE,
                annotation_option: NodeType.ANNOTATION
            }
            
            node_type = node_type_map.get(selected_action)
            if node_type:
                self.insert_node_in_edge(edge_item, scene_pos, node_type)
    
    def request_delete_edge(self, edge_item):
        """Solicita borrar una conexión"""
        from_id = edge_item.from_item.node.id
        to_id = edge_item.to_item.node.id
        self.connection_deleted.emit(from_id, to_id)
    
    def insert_node_in_edge(self, edge_item, scene_pos, node_type):
        """Inserta un nodo en medio de un edge"""
        import uuid
        from core.models import ActionNode, DecisionNode, LoopNode
        from core.database_node import DatabaseNode
        from core.annotation_node import AnnotationNode
        
        # Get workflow from parent panel
        views_parent = self.parentWidget()
        while views_parent and not hasattr(views_parent, 'current_workflow'):
            views_parent = views_parent.parentWidget()
        
        if not views_parent or not views_parent.current_workflow:
            return
        
        workflow = views_parent.current_workflow
        
        # Create new node
        node_id = str(uuid.uuid4())[:8]
        
        if node_type == NodeType.ACTION:
            new_node = ActionNode(id=node_id, label=f"Action {node_id[:4]}", script="")
        elif node_type == NodeType.DECISION:
            new_node = DecisionNode(id=node_id, label=f"Decision {node_id[:4]}", condition="")
        elif node_type == NodeType.LOOP:
            new_node = LoopNode(id=node_id, label=f"Loop {node_id[:4]}", iterations="1")
        elif node_type == NodeType.DATABASE:
            new_node = DatabaseNode(id=node_id, label=f"Database {node_id[:4]}")
        elif node_type == NodeType.ANNOTATION:
            new_node = AnnotationNode(id=node_id, label=f"Note {node_id[:4]}", text="")
        else:
            return
        
        # Set position at click location
        new_node.position = {"x": scene_pos.x(), "y": scene_pos.y()}
        
        # Find and remove old edge
        old_edge = None
        for edge in workflow.edges:
            if edge.from_node == edge_item.from_item.node.id and edge.to_node == edge_item.to_item.node.id:
                old_edge = edge
                break
        
        if old_edge:
            workflow.edges.remove(old_edge)
        
        # Add new node
        workflow.nodes.append(new_node)
        
        # Create two new edges
        from core.models import Edge
        edge1 = Edge(from_node=edge_item.from_item.node.id, to_node=new_node.id)
        edge2 = Edge(from_node=new_node.id, to_node=edge_item.to_item.node.id)
        workflow.edges.append(edge1)
        workflow.edges.append(edge2)
        
        # Refresh view
        if hasattr(views_parent, 'refresh_canvas'):
            views_parent.refresh_canvas()



class WorkflowPanel(QWidget):
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
        self.btn_validate.setEnabled(False) # Habilitar al cargar workflow
        header_layout.addWidget(self.btn_validate)
        
        layout.addLayout(header_layout)
        
        # Splitter principal
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Paleta de Nodos (Nuevo)
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
        
        # Botones de gestion de nodos
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
        
        # Script selector con combo y boton de refrescar
        script_layout = QHBoxLayout()
        self.prop_script = QComboBox()
        self.prop_script.setEditable(True)  # Permite escribir si es necesario
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
        
        
        # Cargar lista inicial de scripts
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
        
        # Use centralized path management with recursive discovery
        from utils.paths import get_all_scripts
        scripts_found = get_all_scripts(include_subdirs=True)
        
        # Convert to relative paths for display
        script_paths = [str(script).replace("\\", "/") for script in scripts_found]
        
        # Agregar al combo
        if script_paths:
            self.prop_script.addItems(script_paths)
        
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
                # Map color to dropdown
                color_map_reverse = {
                    "#ffffcc": "Amarillo",
                    "#cce5ff": "Azul",
                    "#ffccf2": "Rosa",
                    "#ccffcc": "Verde"
                }
                color_name = color_map_reverse.get(node.color, "Amarillo")
                self.prop_annotation_color.setCurrentText(color_name)
        
        # Buscar conexion siguiente (para nodos no-decision y no-annotation)
        if self.current_workflow and not isinstance(node, DecisionNode) and node.type != NodeType.ANNOTATION:
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
            self.btn_validate.setEnabled(True)
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
    
    def create_node_from_palette(self, node_def, pos):
        """Crea un nodo desde la paleta (Drag & Drop)"""
        node_id = self.generate_node_id()
        
        # Determine type map
        type_map = {
            'action': NodeType.ACTION,
            'decision': NodeType.DECISION,
            'loop': NodeType.LOOP,
            'database': NodeType.DATABASE,
            'annotation': NodeType.ANNOTATION
        }
        
        node_type = type_map.get(node_def.node_type_enum, NodeType.ACTION)
        
        # Create node instance based on type
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
            # Check for specific actions like run_script
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

        # Use Undo stack
        self.undo_stack.beginMacro(f"Agregar {node_def.name}")
        self.undo_stack.push(AddNodeCommand(self.current_workflow, new_node, self))
        self.undo_stack.endMacro()
        
        # Select the new node
        self.on_node_selected(new_node)
        self.canvas.scene.clearSelection()
        # Find item and select it? (Canvas reload makes this tricky unless we find item)
        
    def add_node_interactive(self, node_type_str, pos):
        """Called from context menu"""
        # Create a dummy node def
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
        
        # Agregar nodo con Undo
        self.undo_stack.beginMacro(f"Agregar {node_label}")
        self.undo_stack.push(AddNodeCommand(self.current_workflow, new_node, self))
        
        # Agregar conexion si se especifico siguiente
        next_node = self.prop_next_node.text().strip()
        if next_node and node_type != "decision":
            self.undo_stack.push(ConnectionCommand(self.current_workflow, node_id, next_node, self))
        
        self.undo_stack.endMacro()
        
        # Limpieza UI
        self.clear_node_fields()
        self.log(f"Nodo agregado: {node_label} ({node_type})")
        
        QMessageBox.information(self, "Nodo Agregado", f"Nodo '{node_label}' agregado.")
    
    def delete_node(self):
        """Elimina el nodo seleccionado (Undoable)."""
        if not self.current_workflow or not hasattr(self, 'selected_node') or not self.selected_node:
            return
        
        node_label = self.selected_node.label
        
        # Confirmar
        reply = QMessageBox.question(
            self, "Confirmar Eliminacion",
            f"Eliminar nodo '{node_label}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Undo Command
        self.undo_stack.push(DeleteNodeCommand(self.current_workflow, self.selected_node, self))
        
        self.selected_node = None
        self.clear_node_fields()
    
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

    def validate_workflow(self):
        """Ejecuta validación y muestra errores visualmente."""
        if not self.current_workflow:
            return
            
        errors = WorkflowValidator.validate(self.current_workflow)
        
        # Limpiar errores previos
        if hasattr(self, 'scene'):
            for item in self.scene.items():
                if isinstance(item, NodeGraphicsItem):
                    item.set_warning(None)
        
        if not errors:
            self.status_label.setText("Validación OK")
            self.status_label.setStyleSheet("color: #28a745; font-weight: bold;")
            QMessageBox.information(self, "Validación Correcta", "El workflow es válido y está listo para ejecutarse.")
            return

        # Mostrar errores
        msg_list = []
        for err in errors:
            node_id = err["node_id"]
            msg = err["message"]
            msg_list.append(f"- {node_id or 'Global'}: {msg}")
            
            if node_id:
                # Buscar item y marcar
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

        # Prevenir auto-conexión
        if from_id == to_id:
            QMessageBox.warning(self, "Acción inválida", "No puedes conectar un nodo consigo mismo.")
            return

        self.undo_stack.beginMacro(f"Conectar {from_id} -> {to_id}")
        
        # Lógica para DecisionNode
        if isinstance(from_node, DecisionNode):
            # Preguntar camino
            items = ["TRUE", "FALSE"]
            path, ok = QInputDialog.getItem(self, "Conexión de Decisión", 
                f"Conectar '{from_node.label}' -> '{to_id}' como:", items, 0, False)
            
            if not ok or not path:
                self.undo_stack.endMacro()
                return
            
            # Actualizar propiedad
            prop_name = "true_path" if path == "TRUE" else "false_path"
            old_val = getattr(from_node, prop_name)
            
            self.undo_stack.push(ModifyPropertyCommand(
                self.current_workflow, from_id, prop_name, to_id, old_val, self
            ))
            
            # Agregar edge visual
            self.undo_stack.push(ConnectionCommand(self.current_workflow, from_id, to_id, self, is_add=True))
            
        else:
            # Action/Loop -> Solo 1 salida normal. Eliminar previas via Command
            existing = [e for e in self.current_workflow.edges if e.from_node == from_id]
            for e in existing:
                self.undo_stack.push(ConnectionCommand(
                    self.current_workflow, e.from_node, e.to_node, self, is_add=False
                ))
            
            # Agregar nueva
            self.undo_stack.push(ConnectionCommand(self.current_workflow, from_id, to_id, self, is_add=True))
            
            # Si estamos editando el nodo seleccionado, actualizar UI text
            if hasattr(self, 'selected_node') and self.selected_node and self.selected_node.id == from_id:
                self.prop_next_node.setText(to_id)
        
        self.undo_stack.endMacro()
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

        self.undo_stack.beginMacro(f"Insertar nodo en {from_id}->{to_id}")

        # 1. Eliminar edge viejo
        self.undo_stack.push(ConnectionCommand(self.current_workflow, from_id, to_id, self, is_add=False))
            
        # Si era DecisionNode (A), actualizar path
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
        
        # 2. Crear edge (A->Nodo)
        self.undo_stack.push(ConnectionCommand(self.current_workflow, from_id, node.id, self, is_add=True))
        
        # 3. Crear edge (Nodo->B)
        if not isinstance(node, DecisionNode):
            self.undo_stack.push(ConnectionCommand(self.current_workflow, node.id, to_id, self, is_add=True))
            # Actualizar next_node visualmente
            if hasattr(self, 'selected_node') and self.selected_node and self.selected_node.id == node.id:
                 self.prop_next_node.setText(to_id)
        else:
             # Si insertamos DecisionNode, conectamos true_path por defecto
             self.undo_stack.push(ModifyPropertyCommand(
                 self.current_workflow, node.id, "true_path", to_id, getattr(node, "true_path", ""), self
             ))
             self.undo_stack.push(ConnectionCommand(self.current_workflow, node.id, to_id, self, is_add=True))
        
        self.undo_stack.endMacro()
        
        # Recargar lo manejan los comandos, pero si hay cambios propiedades fuera de command...
        # ModifyPropertyCommand ya recarga.
        
        self.log(f"Nodo insertado: {from_id} -> {node.id} -> {to_id}")

