"""
Elementos gráficos del canvas clásico de workflows (PortItem, NodeGraphicsItem, EdgeGraphicsItem).
Extraído de ui/workflow_panel.py.
"""

import math
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QGraphicsRectItem, QGraphicsTextItem, QGraphicsPathItem,
    QGraphicsEllipseItem, QMessageBox, QMenu
)
from PyQt6.QtCore import Qt, QPointF
from PyQt6.QtGui import (
    QFont, QColor, QBrush, QPen, QPainterPath, QPolygonF,
    QPainterPathStroker, QLinearGradient
)

from core.models import Node, NodeType


class PortItem(QGraphicsEllipseItem):
    """Puerto de conexión (visual) en el nodo."""
    
    def __init__(self, port_type, parent=None):
        super().__init__(-5, -5, 10, 10, parent)
        self.port_type = port_type  # 'top', 'bottom', 'left', 'right'
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
                # Start drag from this port
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
        },
        NodeType.WORKFLOW: {
            'color1': QColor("#8e44ad"),
            'color2': QColor("#9b59b6"),
            'icon': "🔗",  # Link
            'shadow': QColor(142, 68, 173, 100)
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
        
        # Agregar puertos de conexión (4 lados)
        self.ports = {}
        if node.type not in [NodeType.ANNOTATION]:
            # Top
            self.ports['top'] = PortItem('top', self)
            self.ports['top'].setPos(width / 2, 0)
            
            # Bottom
            self.ports['bottom'] = PortItem('bottom', self)
            self.ports['bottom'].setPos(width / 2, height)
            
            # Left
            self.ports['left'] = PortItem('left', self)
            self.ports['left'].setPos(0, height / 2)
            
            # Right
            self.ports['right'] = PortItem('right', self)
            self.ports['right'].setPos(width, height / 2)
        
        # Icono de estado (Deshabilitado)
        self.status_icon = QGraphicsTextItem(self)
        self.status_icon.setDefaultTextColor(QColor("#ff0000"))
        self.status_icon.setFont(QFont("Segoe UI Emoji", 20))
        self.status_icon.setPos(width - 30, -10)
        self.status_icon.hide() # Oculto por defecto
        
        # Aplicar estado inicial
        if not node.enabled:
            self._update_enabled_visuals(False)
    
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
    
    def _update_enabled_visuals(self, enabled: bool):
        """Actualiza la apariencia visual según estado habilitado"""
        if enabled:
            self.setOpacity(1.0)
            if hasattr(self, 'status_icon'):
                self.status_icon.hide()
            
            # Limpiar tooltip
            current = self.toolTip()
            if "🚫 DESHABILITADO" in current:
                 self.setToolTip(current.replace("🚫 DESHABILITADO\n", "").replace("🚫 DESHABILITADO", ""))
        else:
            self.setOpacity(0.5)
            if hasattr(self, 'status_icon'):
                self.status_icon.setPlainText("🚫")
                self.status_icon.show()
                # Asegurar que esté encima
                self.status_icon.setZValue(10)
            
            # Set tooltip
            current = self.toolTip()
            if "🚫 DESHABILITADO" not in current:
                self.setToolTip(f"🚫 DESHABILITADO\n{current}")

    def mouseDoubleClickEvent(self, event):
        """Abre el script asociado al hacer doble click"""
        script_path_str = None
        
        # Obtener script segun tipo de nodo
        if hasattr(self.node, 'script') and self.node.script:
            script_path_str = self.node.script
        
        if script_path_str:
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
                    QMessageBox.warning(None, "Error", f"No se pudo abrir el archivo:\n{e}")
            else:
                QMessageBox.warning(None, "Archivo no encontrado", 
                    f"El script '{script_path_str}' no se encuentra en las rutas de búsqueda.\n\n"
                    f"Asegúrate de que el archivo exista en la carpeta 'recordings'.")
        else:
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
        self.arrow_head = QPolygonF()
        self.update_path()
        
        # Insert button (created on demand)
        self.insert_button = None
    
    def update_path(self):
        # SMART ROUTING: Determinar los mejores puertos basados en posición relativa
        
        # Obtener centros
        c1 = self.from_item.get_center()
        c2 = self.to_item.get_center()
        
        dx = c2.x() - c1.x()
        dy = c2.y() - c1.y()
        
        start_port = 'bottom'
        end_port = 'top'
        
        # Lógica simple de dirección
        if abs(dx) > abs(dy): # Más horizontal que vertical
            if dx > 0: # Target a la derecha
                start_port = 'right'
                end_port = 'left'
            else: # Target a la izquierda
                start_port = 'left'
                end_port = 'right'
        else: # Más vertical
            if dy > 0: # Target abajo
                start_port = 'bottom'
                end_port = 'top'
            else: # Target arriba
                start_port = 'top'
                end_port = 'bottom'
        
        # Obtener posiciones de los puertos
        if hasattr(self.from_item, 'ports') and start_port in self.from_item.ports:
            start = self.from_item.mapToScene(self.from_item.ports[start_port].pos())
        else:
            # Fallback
            start = c1
            start.setY(start.y() + self.from_item.node_height / 2)

        if hasattr(self.to_item, 'ports') and end_port in self.to_item.ports:
            end = self.to_item.mapToScene(self.to_item.ports[end_port].pos())
        else:
            # Fallback
            end = c2
            end.setY(end.y() - self.to_item.node_height / 2)
            
        
        path = QPainterPath()
        path.moveTo(start)
        
        # Curvas Bezier adaptativas
        dist = (end - start).manhattanLength()
        ctrl_dist = min(dist * 0.5, 100) # Control point distance
        
        if start_port == 'right':
            ctrl1 = start + QPointF(ctrl_dist, 0)
        elif start_port == 'left':
            ctrl1 = start - QPointF(ctrl_dist, 0)
        elif start_port == 'bottom':
            ctrl1 = start + QPointF(0, ctrl_dist)
        else: # top
            ctrl1 = start - QPointF(0, ctrl_dist)
            
        if end_port == 'right':
            ctrl2 = end + QPointF(ctrl_dist, 0)
        elif end_port == 'left':
            ctrl2 = end - QPointF(ctrl_dist, 0)
        elif end_port == 'bottom':
            ctrl2 = end + QPointF(0, ctrl_dist)
        else: # top
            ctrl2 = end - QPointF(0, ctrl_dist)
            
        
        path.cubicTo(ctrl1, ctrl2, end)
        
        self.setPath(path)
        
        # Calcular Arrow Head (Triangulo)
        if end == ctrl2:
            direction = end - start
        else:
            direction = end - ctrl2
            
        angle = math.atan2(direction.y(), direction.x())
        
        arrow_size = 10
        arrow_p1 = end + QPointF(math.cos(angle - math.pi + 0.5) * arrow_size,
                                 math.sin(angle - math.pi + 0.5) * arrow_size)
        arrow_p2 = end + QPointF(math.cos(angle - math.pi - 0.5) * arrow_size,
                                 math.sin(angle - math.pi - 0.5) * arrow_size)
                                 
        self.arrow_head = QPolygonF([end, arrow_p1, arrow_p2])

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        # Dibujar flecha
        if not self.arrow_head.isEmpty():
            painter.setBrush(QBrush(self.pen().color()))
            painter.drawPolygon(self.arrow_head)
    
    def contextMenuEvent(self, event):
        menu = QMenu()
        delete_action = menu.addAction("🗑️ Eliminar Conexión")
        action = menu.exec(event.screenPos())
        
        if action == delete_action:
            views = self.scene().views()
            if views:
                view = views[0]
                if hasattr(view, 'request_delete_edge'):
                    view.request_delete_edge(self)
                else:
                    self._delete_connection()
    
    def hoverEnterEvent(self, event):
        if not self.insert_button:
            from ui.insert_node_button import InsertNodeButton
            self.insert_button = InsertNodeButton(self, self)
        
        self.insert_button.setPos(event.pos())
        self.insert_button.setVisible(True)
        
        self.setPen(QPen(QColor("#28a745"), 3))
        super().hoverEnterEvent(event)
    
    def hoverMoveEvent(self, event):
        if self.insert_button:
            self.insert_button.setPos(event.pos())
        super().hoverMoveEvent(event)
    
    def hoverLeaveEvent(self, event):
        if self.insert_button:
            self.insert_button.setVisible(False)
        
        self.setPen(QPen(QColor("#666666"), 2))
        super().hoverLeaveEvent(event)
    
    def on_insert_requested(self, click_pos):
        """Called when user clicks the + button"""
        views = self.scene().views()
        if views:
            view = views[0]
            if hasattr(view, 'show_insert_node_menu'):
                view.show_insert_node_menu(self, click_pos)
    
    def shape(self):
        """Area de colision mas ancha para facilitar seleccion."""
        path_stroker = QPainterPathStroker()
        path_stroker.setWidth(20)
        return path_stroker.createStroke(self.path())
