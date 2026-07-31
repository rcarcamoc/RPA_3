import math
import os
import sys
from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem,
    QGraphicsPathItem, QGraphicsEllipseItem, QMessageBox, QMenu, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRectF
from PyQt6.QtGui import (
    QFont, QColor, QBrush, QPen, QPainterPath, QPolygonF, QPainter, 
    QPainterPathStroker, QLinearGradient
)

from core.models import NodeType, Node, Edge, ActionNode, DecisionNode, LoopNode, Workflow
from .node_definitions import NodeDefinition, get_all_nodes

class PortItemFinal(QGraphicsEllipseItem):
    """Puerto de conexión en el nodo para el canvas final"""
    
    def __init__(self, port_type, parent=None):
        super().__init__(-5, -5, 10, 10, parent)
        self.port_type = port_type  # 'top', 'bottom', 'left', 'right'
        self.setBrush(QBrush(QColor("#ffffff")))
        self.setPen(QPen(QColor("#cbd5e1"), 1.5))
        self.setAcceptHoverEvents(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
    
    def hoverEnterEvent(self, event):
        self.setBrush(QBrush(QColor("#10b981"))) # Verde esmeralda al pasar mouse
        self.setPen(QPen(QColor("#ffffff"), 1))
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        self.setBrush(QBrush(QColor("#ffffff")))
        self.setPen(QPen(QColor("#cbd5e1"), 1.5))
        super().hoverLeaveEvent(event)
    
    def mousePressEvent(self, event):
        views = self.scene().views()
        if views:
            view = views[0]
            if hasattr(view, 'start_connection_drag'):
                view.start_connection_drag(self.parentItem(), self.mapToScene(self.rect().center()))
                event.accept()
        else:
            super().mousePressEvent(event)


class NodeGraphicsItemFinal(QGraphicsRectItem):
    """Representación gráfica de un nodo con soporte de gradientes, desactivación y glow de ejecución"""
    
    NODE_STYLES = {
        NodeType.ACTION: {
            'color1': QColor("#60a5fa"), # Azul suave
            'color2': QColor("#3b82f6"),
            'icon': "▶️",
        },
        NodeType.DECISION: {
            'color1': QColor("#f472b6"), # Rosa suave
            'color2': QColor("#ec4899"),
            'icon': "◆",
        },
        NodeType.LOOP: {
            'color1': QColor("#c084fc"), # Púrpura suave
            'color2': QColor("#8b5cf6"),
            'icon': "↻",
        },
        NodeType.DATABASE: {
            'color1': QColor("#fbbf24"), # Amarillo
            'color2': QColor("#f59e0b"),
            'icon': "🗄",
        },
        NodeType.ANNOTATION: {
            'color1': QColor("#fef08a"), # Nota amarilla clara
            'color2': QColor("#fef08a"),
            'icon': "📝",
            'dashed': True
        },
        NodeType.DELAY: {
            'color1': QColor("#fdba74"), # Naranja
            'color2': QColor("#f97316"),
            'icon': "⏳",
        },
        NodeType.START: {
            'color1': QColor("#34d399"), # Verde inicio
            'color2': QColor("#10b981"),
            'icon': "🏁",
        },
        NodeType.END: {
            'color1': QColor("#f87171"), # Rojo fin
            'color2': QColor("#ef4444"),
            'icon': "✔️",
        },
        NodeType.WORKFLOW: {
            'color1': QColor("#c084fc"),
            'color2': QColor("#a855f7"),
            'icon': "🔗",
        }
    }
    
    def __init__(self, node: Node, parent=None):
        from core.annotation_node import AnnotationNode
        if isinstance(node, AnnotationNode):
            width = getattr(node, 'width', 180)
            height = getattr(node, 'height', 80)
        else:
            width = 180
            height = 80
            
        super().__init__(0, 0, width, height, parent)
        self.node = node
        self.node_width = width
        self.node_height = height
        
        self.is_highlighted = False
        self.is_executing = False
        self.has_warning = False
        
        # Obtener colores
        style = self.NODE_STYLES.get(node.type, self.NODE_STYLES[NodeType.ACTION])
        
        # Crear Gradiente
        gradient = QLinearGradient(0, 0, 0, height)
        gradient.setColorAt(0, style['color1'])
        gradient.setColorAt(1, style['color2'])
        self.setBrush(QBrush(gradient))
        
        # Borde (Línea punteada para notas)
        pen_style = Qt.PenStyle.DashLine if style.get('dashed') else Qt.PenStyle.SolidLine
        self.setPen(QPen(QColor("#475569"), 1.5, pen_style))
        
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsRectItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        
        # Emoji Icon
        self.icon_item = QGraphicsTextItem(self)
        self.icon_item.setPlainText(style['icon'])
        self.icon_item.setFont(QFont("Segoe UI Emoji", 15))
        self.icon_item.setDefaultTextColor(Qt.GlobalColor.white if node.type != NodeType.ANNOTATION else QColor("#0f172a"))
        self.icon_item.setPos(10, (height - 24) / 2)
        
        # Texto Etiqueta
        self.text_item = QGraphicsTextItem(self)
        self.text_item.setPlainText(node.label)
        self.text_item.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        self.text_item.setDefaultTextColor(Qt.GlobalColor.white if node.type != NodeType.ANNOTATION else QColor("#0f172a"))
        
        text_rect = self.text_item.boundingRect()
        self.text_item.setPos(38, (height - text_rect.height()) / 2)
        
        # Texto adicional para notas
        if isinstance(node, AnnotationNode) and hasattr(node, 'text') and node.text:
            self.annotation_text = QGraphicsTextItem(self)
            self.annotation_text.setPlainText(node.text[:80])
            self.annotation_text.setFont(QFont("Segoe UI", 8))
            self.annotation_text.setDefaultTextColor(QColor("#475569"))
            self.annotation_text.setPos(10, 35)
            
        self.setPos(node.position.get("x", 0), node.position.get("y", 0))
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        
        # Puertos (No en notas)
        self.ports = {}
        if node.type != NodeType.ANNOTATION:
            self.ports['top'] = PortItemFinal('top', self)
            self.ports['top'].setPos(width / 2, 0)
            
            self.ports['bottom'] = PortItemFinal('bottom', self)
            self.ports['bottom'].setPos(width / 2, height)
            
            self.ports['left'] = PortItemFinal('left', self)
            self.ports['left'].setPos(0, height / 2)
            
            self.ports['right'] = PortItemFinal('right', self)
            self.ports['right'].setPos(width, height / 2)
            
        self.status_icon = QGraphicsTextItem(self)
        self.status_icon.setDefaultTextColor(QColor("#ef4444"))
        self.status_icon.setFont(QFont("Segoe UI Emoji", 18))
        self.status_icon.setPos(width - 25, -12)
        self.status_icon.hide()
        
        if not node.enabled:
            self._update_enabled_visuals(False)
            
    def get_center(self) -> QPointF:
        return QPointF(self.pos().x() + self.node_width / 2, self.pos().y() + self.node_height / 2)
        
    def highlight(self, active: bool = True):
        self.is_highlighted = active
        self._update_appearance()
        
    def set_executing(self, executing: bool = True):
        self.is_executing = executing
        self._update_appearance()
        
    def set_warning(self, message: str):
        self.has_warning = bool(message)
        self.setToolTip(f"⚠️ {message}" if message else "")
        self._update_appearance()
        
    def _update_appearance(self):
        # Prioridad de color de bordes
        if self.is_executing:
            # Borde verde esmeralda brillante de ejecución
            self.setPen(QPen(QColor("#10b981"), 3))
        elif self.is_highlighted:
            # Borde azul seleccionado
            self.setPen(QPen(QColor("#3b82f6"), 2.5))
        elif self.has_warning:
            self.setPen(QPen(QColor("#ef4444"), 2.5))
        else:
            style = self.NODE_STYLES.get(self.node.type, self.NODE_STYLES[NodeType.ACTION])
            pen_style = Qt.PenStyle.DashLine if style.get('dashed') else Qt.PenStyle.SolidLine
            self.setPen(QPen(QColor("#475569"), 1.5, pen_style))
            
    def itemChange(self, change, value):
        if change == QGraphicsRectItem.GraphicsItemChange.ItemPositionChange and self.scene():
            # Snapping a grid de 10px para alineación perfecta empresarial
            x = round(value.x() / 10.0) * 10.0
            y = round(value.y() / 10.0) * 10.0
            return QPointF(x, y)
            
        if change == QGraphicsRectItem.GraphicsItemChange.ItemPositionHasChanged:
            self.node.position = {"x": value.x(), "y": value.y()}
            if self.scene():
                for item in self.scene().items():
                    if isinstance(item, EdgeGraphicsItemFinal):
                        if item.from_item == self or item.to_item == self:
                            item.update_path()
        return super().itemChange(change, value)
        
    def mousePressEvent(self, event):
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        super().mousePressEvent(event)
        
    def mouseReleaseEvent(self, event):
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)
        
    def _update_enabled_visuals(self, enabled: bool):
        if enabled:
            self.setOpacity(1.0)
            self.status_icon.hide()
        else:
            self.setOpacity(0.55)
            self.status_icon.setPlainText("🚫")
            self.status_icon.show()
            self.status_icon.setZValue(10)

    def mouseDoubleClickEvent(self, event):
        event.accept()
        script_path_str = getattr(self.node, 'script', None)
        if script_path_str:
            from pathlib import Path
            script_path = Path(script_path_str)
            
            # Si no es ruta absoluta, buscar de forma recursiva e inteligente
            if not script_path.is_absolute():
                found_path = None
                
                # Intentar primero rutas lógicas conocidas
                possible_paths = [
                    Path.cwd() / script_path_str,
                    Path.cwd() / "rpa_framework" / script_path_str,
                    Path.cwd() / "recordings" / script_path_str,
                    Path.cwd() / "rpa_framework" / "recordings" / script_path_str,
                    Path.cwd() / "recordings" / "web" / script_path_str,
                    Path.cwd() / "recordings" / "desktop" / script_path_str,
                    Path.cwd() / "rpa_framework" / "recordings" / "web" / script_path_str,
                    Path.cwd() / "rpa_framework" / "recordings" / "desktop" / script_path_str,
                ]
                for p in possible_paths:
                    if p.exists():
                        found_path = p
                        break
                
                # Si sigue sin encontrarse, hacer búsqueda recursiva por nombre de archivo
                if not found_path:
                    # Extraer solo el nombre de archivo final
                    file_name = script_path.name
                    search_roots = [
                        Path.cwd() / "recordings",
                        Path.cwd() / "rpa_framework" / "recordings",
                        Path.cwd()
                    ]
                    for root in search_roots:
                        if root.exists():
                            for p in root.glob(f"**/{file_name}"):
                                if p.exists():
                                    found_path = p
                                    break
                        if found_path:
                            break
                            
                if found_path:
                    script_path = found_path
            
            if script_path.exists():
                try:
                    os.startfile(str(script_path))
                except Exception as e:
                    QMessageBox.warning(None, "Error", f"No se pudo abrir el script:\n{e}")
            else:
                QMessageBox.warning(None, "Archivo no encontrado", 
                                    f"No se pudo encontrar el script '{script_path_str}' en ninguna de las rutas de grabaciones.")
        else:
            QMessageBox.information(None, "Sin script", "Este nodo no tiene ningún script Python asignado.")
        super().mouseDoubleClickEvent(event)


class EdgeGraphicsItemFinal(QGraphicsPathItem):
    """Línea de conexión estilizada con flechas e inserción en el canvas final"""
    
    def __init__(self, from_item: NodeGraphicsItemFinal, to_item: NodeGraphicsItemFinal, parent=None):
        super().__init__(parent)
        self.from_item = from_item
        self.to_item = to_item
        
        self.setPen(QPen(QColor("#64748b"), 1.8))
        self.setAcceptHoverEvents(True)
        self.arrow_head = QPolygonF()
        self.update_path()
        self.insert_button = None
        
    def update_path(self):
        c1 = self.from_item.get_center()
        c2 = self.to_item.get_center()
        
        dx = c2.x() - c1.x()
        dy = c2.y() - c1.y()
        
        start_port = 'bottom'
        end_port = 'top'
        
        if abs(dx) > abs(dy):
            if dx > 0:
                start_port = 'right'
                end_port = 'left'
            else:
                start_port = 'left'
                end_port = 'right'
        else:
            if dy > 0:
                start_port = 'bottom'
                end_port = 'top'
            else:
                start_port = 'top'
                end_port = 'bottom'
                
        if start_port in self.from_item.ports:
            start = self.from_item.mapToScene(self.from_item.ports[start_port].pos())
        else:
            start = c1
            
        if end_port in self.to_item.ports:
            end = self.to_item.mapToScene(self.to_item.ports[end_port].pos())
        else:
            end = c2
            
        path = QPainterPath()
        path.moveTo(start)
        
        dist = (end - start).manhattanLength()
        ctrl_dist = min(dist * 0.4, 80)
        
        if start_port == 'right':     ctrl1 = start + QPointF(ctrl_dist, 0)
        elif start_port == 'left':   ctrl1 = start - QPointF(ctrl_dist, 0)
        elif start_port == 'bottom': ctrl1 = start + QPointF(0, ctrl_dist)
        else:                        ctrl1 = start - QPointF(0, ctrl_dist)
        
        if end_port == 'right':       ctrl2 = end + QPointF(ctrl_dist, 0)
        elif end_port == 'left':     ctrl2 = end - QPointF(ctrl_dist, 0)
        elif end_port == 'bottom':   ctrl2 = end + QPointF(0, ctrl_dist)
        else:                        ctrl2 = end - QPointF(0, ctrl_dist)
        
        path.cubicTo(ctrl1, ctrl2, end)
        self.setPath(path)
        
        direction = end - ctrl2 if end != ctrl2 else end - start
        angle = math.atan2(direction.y(), direction.x())
        
        arrow_size = 9
        arrow_p1 = end + QPointF(math.cos(angle - math.pi + 0.5) * arrow_size,
                                 math.sin(angle - math.pi + 0.5) * arrow_size)
        arrow_p2 = end + QPointF(math.cos(angle - math.pi - 0.5) * arrow_size,
                                 math.sin(angle - math.pi - 0.5) * arrow_size)
        self.arrow_head = QPolygonF([end, arrow_p1, arrow_p2])
        
    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        if not self.arrow_head.isEmpty():
            painter.setBrush(QBrush(self.pen().color()))
            painter.drawPolygon(self.arrow_head)
            
    def hoverEnterEvent(self, event):
        if not self.insert_button:
            from ui.insert_node_button import InsertNodeButton
            self.insert_button = InsertNodeButton(self, self)
        self.insert_button.setPos(event.pos())
        self.insert_button.setVisible(True)
        self.setPen(QPen(QColor("#10b981"), 2.5)) # Resaltar conexión
        super().hoverEnterEvent(event)
        
    def hoverMoveEvent(self, event):
        if self.insert_button:
            self.insert_button.setPos(event.pos())
        super().hoverMoveEvent(event)
        
    def hoverLeaveEvent(self, event):
        if self.insert_button:
            self.insert_button.setVisible(False)
        self.setPen(QPen(QColor("#64748b"), 1.8))
        super().hoverLeaveEvent(event)
        
    def on_insert_requested(self, click_pos):
        views = self.scene().views()
        if views and hasattr(views[0], 'show_insert_node_menu'):
            views[0].show_insert_node_menu(self, click_pos)
            
    def shape(self):
        path_stroker = QPainterPathStroker()
        path_stroker.setWidth(15)
        return path_stroker.createStroke(self.path())


class WorkflowCanvasFinal(QGraphicsView):
    """Canvas final con grid de fondo punteado suave y highlight dinámico de ejecución"""
    
    node_selected = pyqtSignal(object)
    connection_created = pyqtSignal(str, str)
    connection_deleted = pyqtSignal(str, str)
    edge_split_requested = pyqtSignal(object, str, str)
    node_dropped = pyqtSignal(object, object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        
        self.setAcceptDrops(True)
        self.is_connecting = False
        self.source_node = None
        self.temp_line = None
        
        self.scene.selectionChanged.connect(self.on_selection_changed)
        self.setStyleSheet("background-color: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px;")
        
        self.node_items = {}
        self.edge_items = []
        self._zoom = 1.0
        self._panning = False
        self._pan_start = None
        
    def drawBackground(self, painter: QPainter, rect: QRectF):
        """Dibuja un grid empresarial punteado de color suave"""
        super().drawBackground(painter, rect)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        
        grid_size = 20
        left = int(math.floor(rect.left()))
        top = int(math.floor(rect.top()))
        right = int(math.ceil(rect.right()))
        bottom = int(math.ceil(rect.bottom()))
        
        # Alinear a la cuadrícula
        first_x = left - (left % grid_size)
        first_y = top - (top % grid_size)
        
        # Color del grid neutro
        pen = QPen(QColor("#cbd5e1"), 1.0, Qt.PenStyle.DotLine)
        painter.setPen(pen)
        
        # Dibujar líneas verticales y horizontales
        for x in range(first_x, right, grid_size):
            painter.drawLine(x, top, x, bottom)
        for y in range(first_y, bottom, grid_size):
            painter.drawLine(left, y, right, y)
            
        painter.restore()

    def on_selection_changed(self):
        items = self.scene.selectedItems()
        if items and isinstance(items[0], NodeGraphicsItemFinal):
            self.node_selected.emit(items[0].node)
            
    def wheelEvent(self, event):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.angleDelta().y() > 0:
                self.scale_view(1.2)
            else:
                self.scale_view(1 / 1.2)
            event.accept()
        else:
            super().wheelEvent(event)
            
    def scale_view(self, factor):
        new_zoom = self._zoom * factor
        if 0.15 <= new_zoom <= 4.0:
            self._zoom = new_zoom
            self.scale(factor, factor)
            
    def load_workflow(self, workflow: Workflow):
        """Carga y regenera la visualización del workflow"""
        self.scene.clear()
        self.node_items.clear()
        self.edge_items.clear()
        
        # Dibujar nodos
        for node in workflow.nodes:
            item = NodeGraphicsItemFinal(node)
            self.scene.addItem(item)
            self.node_items[node.id] = item
            
        # Dibujar conexiones
        for edge in workflow.edges:
            if edge.from_node in self.node_items and edge.to_node in self.node_items:
                from_item = self.node_items[edge.from_node]
                to_item = self.node_items[edge.to_node]
                edge_item = EdgeGraphicsItemFinal(from_item, to_item)
                self.scene.addItem(edge_item)
                self.edge_items.append(edge_item)
                
        self.scene.setSceneRect(self.scene.itemsBoundingRect().adjusted(-100, -100, 100, 100))
        
    def highlight_node(self, node_id: str, active: bool = True):
        self.clear_highlights()
        if node_id in self.node_items:
            self.node_items[node_id].highlight(active)
            
    def set_execution_highlight(self, node_id: str, active: bool = True):
        """Establece qué nodo se encuentra en ejecución"""
        for item in self.node_items.values():
            item.set_executing(False)
        if active and node_id in self.node_items:
            self.node_items[node_id].set_executing(True)
            self.ensureVisible(self.node_items[node_id])
            
    def clear_highlights(self):
        for item in self.node_items.values():
            item.highlight(False)
            
    def start_connection_drag(self, source_node, start_pos):
        self.is_connecting = True
        self.source_node = source_node
        self.temp_line = QGraphicsPathItem()
        self.temp_line.setPen(QPen(QColor("#10b981"), 1.8, Qt.PenStyle.DashLine))
        self.scene.addItem(self.temp_line)
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
            end_pos = self.mapToScene(event.pos())
            items = self.scene.items(end_pos)
            
            target_node = None
            for item in items:
                if isinstance(item, NodeGraphicsItemFinal) and item != self.source_node:
                    target_node = item
                    break
                elif isinstance(item, QGraphicsTextItem) and item.parentItem() != self.source_node:
                    if isinstance(item.parentItem(), NodeGraphicsItemFinal):
                        target_node = item.parentItem()
                        break
                        
            source_id = self.source_node.node.id if self.source_node else None
            target_id = target_node.node.id if target_node else None
            
            if self.temp_line:
                self.scene.removeItem(self.temp_line)
                self.temp_line = None
                
            self.is_connecting = False
            self.source_node = None
            
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
            item = self.itemAt(event.pos())
            if isinstance(item, QGraphicsTextItem):
                item = item.parentItem()
            if isinstance(item, NodeGraphicsItemFinal):
                self.node_selected.emit(item.node)
                
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            for item in self.scene.selectedItems():
                if isinstance(item, NodeGraphicsItemFinal):
                    self._request_delete(item.node)
                elif isinstance(item, EdgeGraphicsItemFinal):
                    self.connection_deleted.emit(item.from_item.node.id, item.to_item.node.id)
        else:
            super().keyPressEvent(event)
            
    def _request_delete(self, node: Node):
        reply = QMessageBox.question(
            self, "Confirmar",
            f"¿Desea eliminar el nodo '{node.label}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            # Emitir la señal al panel principal para que lo elimine vía Undo Stack
            views_parent = self.parentWidget()
            while views_parent and not hasattr(views_parent, 'on_node_deleted_req'):
                views_parent = views_parent.parentWidget()
            if views_parent:
                views_parent.on_node_deleted_req(node)
                
    def show_insert_node_menu(self, edge_item, scene_pos):
        """Muestra menú contextual sobre una conexión para insertar nodos"""
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { font-size: 9pt; }")
        
        act_action = menu.addAction("▶️ Insertar Acción")
        act_decision = menu.addAction("◆ Insertar Decisión")
        act_loop = menu.addAction("↻ Insertar Loop")
        act_db = menu.addAction("🗄 Insertar Base de Datos")
        menu.addSeparator()
        act_note = menu.addAction("📝 Insertar Nota")
        
        view_pos = self.mapFromScene(scene_pos)
        global_pos = self.mapToGlobal(view_pos)
        selected = menu.exec(global_pos)
        
        if selected:
            node_type_map = {
                act_action: NodeType.ACTION,
                act_decision: NodeType.DECISION,
                act_loop: NodeType.LOOP,
                act_db: NodeType.DATABASE,
                act_note: NodeType.ANNOTATION
            }
            node_type = node_type_map.get(selected)
            if node_type:
                self.insert_node_in_edge(edge_item, scene_pos, node_type)
                
    def insert_node_in_edge(self, edge_item, scene_pos, node_type):
        """Lógica corregida de inserción de nodo en conexión"""
        import uuid
        from core.models import ActionNode, DecisionNode, LoopNode
        from core.database_node import DatabaseNode
        from core.annotation_node import AnnotationNode
        
        views_parent = self.parentWidget()
        while views_parent and not hasattr(views_parent, 'current_workflow'):
            views_parent = views_parent.parentWidget()
            
        if not views_parent or not views_parent.current_workflow:
            return
            
        workflow = views_parent.current_workflow
        node_id = f"n_{str(uuid.uuid4())[:6]}"
        
        if node_type == NodeType.ACTION:
            new_node = ActionNode(id=node_id, label=f"Acción {node_id[-4:]}")
        elif node_type == NodeType.DECISION:
            new_node = DecisionNode(id=node_id, label=f"Decisión {node_id[-4:]}")
        elif node_type == NodeType.LOOP:
            new_node = LoopNode(id=node_id, label=f"Loop {node_id[-4:]}")
        elif node_type == NodeType.DATABASE:
            new_node = DatabaseNode(id=node_id, label=f"DB {node_id[-4:]}")
        elif node_type == NodeType.ANNOTATION:
            new_node = AnnotationNode(id=node_id, label=f"Nota {node_id[-4:]}")
        else:
            return
            
        new_node.position = {"x": scene_pos.x() - 90, "y": scene_pos.y() - 40}
        
        # Eliminar el enlace viejo e insertar el nuevo nodo con los dos enlaces nuevos
        # Nota: Idealmente esto iría en un macro-comando de undo, pero para no romper
        # compatibilidad con el engine original que carece de macro-comandos, lo mutamos directamente:
        old_edge = None
        for edge in workflow.edges:
            if edge.from_node == edge_item.from_item.node.id and edge.to_node == edge_item.to_item.node.id:
                old_edge = edge
                break
                
        if old_edge:
            workflow.edges.remove(old_edge)
            
        workflow.nodes.append(new_node)
        workflow.edges.append(Edge(from_node=edge_item.from_item.node.id, to_node=new_node.id))
        workflow.edges.append(Edge(from_node=new_node.id, to_node=edge_item.to_item.node.id))
        
        self.load_workflow(workflow)
        self.node_selected.emit(new_node)
        
    def contextMenuEvent(self, event):
        scene_pos = self.mapToScene(event.pos())
        click_area = QRectF(scene_pos.x() - 5, scene_pos.y() - 5, 10, 10)
        items = self.scene.items(click_area)
        
        selected_node = None
        selected_edge = None
        for item in items:
            if isinstance(item, QGraphicsTextItem):
                item = item.parentItem()
            if isinstance(item, NodeGraphicsItemFinal):
                selected_node = item
                break
            elif isinstance(item, EdgeGraphicsItemFinal) and not selected_edge:
                selected_edge = item
                
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { font-size: 9pt; }")
        
        if selected_node:
            node = selected_node.node
            act_edit = menu.addAction("✏️ Editar Propiedades")
            act_edit.triggered.connect(lambda: self.node_selected.emit(node))
            
            menu.addSeparator()
            if node.enabled:
                act_toggle = menu.addAction("🚫 Deshabilitar Nodo")
                act_toggle.triggered.connect(lambda: self._toggle_node_enabled(selected_node, False))
            else:
                act_toggle = menu.addAction("✅ Habilitar Nodo")
                act_toggle.triggered.connect(lambda: self._toggle_node_enabled(selected_node, True))
                
            menu.addSeparator()
            act_del = menu.addAction("🗑️ Eliminar Nodo")
            act_del.triggered.connect(lambda: self._request_delete(node))
            
        elif selected_edge:
            act_del_edge = menu.addAction("🗑️ Eliminar Conexión")
            act_del_edge.triggered.connect(lambda: self.connection_deleted.emit(selected_edge.from_item.node.id, selected_edge.to_item.node.id))
        else:
            # Click en fondo: Menú rápido de adición
            add_menu = menu.addMenu("Agregar Nodo")
            
            # Buscamos en el catálogo o creamos genéricos
            for cat, defs in NODE_CATALOG.items():
                cat_menu = add_menu.addMenu(cat)
                for node_def in defs:
                    act_add = cat_menu.addAction(f"{node_def.icon} {node_def.name}")
                    # Usar lambda capturando valores
                    act_add.triggered.connect(self._make_add_handler(node_def, scene_pos))
                    
        menu.exec(event.globalPos())
        
    def _make_add_handler(self, node_def, pos):
        return lambda: self.node_dropped.emit(node_def, pos)
        
    def _toggle_node_enabled(self, node_item: NodeGraphicsItemFinal, enabled: bool):
        node_item.node.enabled = enabled
        node_item._update_enabled_visuals(enabled)
        
    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
            
    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()
            
    def dropEvent(self, event):
        node_def_id = event.mimeData().text()
        drop_pos = self.mapToScene(event.position().toPoint())
        
        # Buscar definición
        node_def = next((n for n in get_all_nodes() if n.id == node_def_id), None)
        if node_def:
            self.node_dropped.emit(node_def, drop_pos)
            event.acceptProposedAction()
