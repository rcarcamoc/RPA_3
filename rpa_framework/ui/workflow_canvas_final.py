"""
Canvas final de workflows con grid punteado y highlight de ejecución.
Los items gráficos (PortItemFinal, NodeGraphicsItemFinal, EdgeGraphicsItemFinal)
fueron modularizados hacia ui/canvas/final_items.py manteniendo 100% de compatibilidad.
"""

import math
from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsTextItem,
    QGraphicsPathItem, QMessageBox, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRectF
from PyQt6.QtGui import QColor, QPen, QPainterPath, QPainter

from core.models import NodeType, Node, Edge, ActionNode, DecisionNode, LoopNode, Workflow
from .node_definitions import NodeDefinition, get_all_nodes, NODE_CATALOG
from .canvas.final_items import PortItemFinal, NodeGraphicsItemFinal, EdgeGraphicsItemFinal


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
            add_menu = menu.addMenu("Agregar Nodo")
            for cat, defs in NODE_CATALOG.items():
                cat_menu = add_menu.addMenu(cat)
                for node_def in defs:
                    act_add = cat_menu.addAction(f"{node_def.icon} {node_def.name}")
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
        
        node_def = next((n for n in get_all_nodes() if n.id == node_def_id), None)
        if node_def:
            self.node_dropped.emit(node_def, drop_pos)
            event.acceptProposedAction()
