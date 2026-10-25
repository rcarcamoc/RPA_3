"""
Elementos gráficos del canvas final empresarial (PortItemFinal, NodeGraphicsItemFinal, EdgeGraphicsItemFinal).
Extraído de ui/workflow_canvas_final.py.
"""

import math
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QGraphicsRectItem, QGraphicsTextItem,
    QGraphicsPathItem, QGraphicsEllipseItem, QMessageBox
)
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import (
    QFont, QColor, QBrush, QPen, QPainterPath, QPolygonF,
    QPainterPathStroker, QLinearGradient
)

from core.models import NodeType, Node


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
            self.setPen(QPen(QColor("#10b981"), 3))
        elif self.is_highlighted:
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
            script_path = Path(script_path_str)
            
            # Si no es ruta absoluta, buscar de forma recursiva e inteligente
            if not script_path.is_absolute():
                found_path = None
                
                possible_paths = [
                    Path.cwd() / script_path_str,
                    Path.cwd() / "rpa_framework" / script_path_str,
                    Path.cwd() / "recordings" / script_path_str,
                    Path.cwd() / "rpa_framework" / "recordings" / script_path_str,
                    Path.cwd() / "recordings" / "ui" / script_path_str,
                    Path.cwd() / "rpa_framework" / "recordings" / "ui" / script_path_str,
                    Path.cwd() / "recordings" / "ocr" / script_path_str,
                    Path.cwd() / "rpa_framework" / "recordings" / "ocr" / script_path_str,
                    Path.cwd() / "recordings" / "web" / script_path_str,
                    Path.cwd() / "recordings" / "desktop" / script_path_str,
                    Path.cwd() / "rpa_framework" / "recordings" / "web" / script_path_str,
                    Path.cwd() / "rpa_framework" / "recordings" / "desktop" / script_path_str,
                ]
                for p in possible_paths:
                    if p.exists():
                        found_path = p
                        break
                
                if not found_path:
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
