"""
Vista de canvas clásico (WorkflowCanvas) para el panel de workflows original.
Extraído de ui/workflow_panel.py.
"""

from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsTextItem,
    QGraphicsPathItem, QMessageBox, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal, QPointF, QRectF
from PyQt6.QtGui import QColor, QPen, QPainterPath, QPainter

from core.models import Workflow, Node, NodeType, ActionNode, DecisionNode, LoopNode, Edge
from .legacy_items import NodeGraphicsItem, EdgeGraphicsItem


class WorkflowCanvas(QGraphicsView):
    """Canvas para visualizar workflows"""
    
    node_selected = pyqtSignal(object)  # Node
    connection_created = pyqtSignal(str, str) # from_id, to_id
    connection_deleted = pyqtSignal(str, str) # from_id, to_id
    edge_split_requested = pyqtSignal(object, str, str) # node_item, from_id, to_id
    node_dropped = pyqtSignal(object, object) # node_def, pos
    
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
    
    def keyPressEvent(self, event):
        """Manejar teclas de acceso rápido (Delete, etc)"""
        if event.key() == Qt.Key.Key_Delete:
            # Eliminar items seleccionados
            for item in self.scene.selectedItems():
                if isinstance(item, NodeGraphicsItem):
                    self._request_delete(item.node)
                elif isinstance(item, EdgeGraphicsItem):
                    self.request_delete_edge(item)
        else:
            super().keyPressEvent(event)
    
    def contextMenuEvent(self, event):
        """Menu contextual con click derecho"""
        scene_pos = self.mapToScene(event.pos())
        click_area = QRectF(scene_pos.x() - 5, scene_pos.y() - 5, 10, 10)
        items = self.scene.items(click_area)
        
        selected_node = None
        selected_edge = None
        
        for item in items:
            if isinstance(item, QGraphicsTextItem):
                item = item.parentItem()
            
            if isinstance(item, NodeGraphicsItem):
                selected_node = item
                break
            elif isinstance(item, EdgeGraphicsItem) and not selected_edge:
                selected_edge = item
        
        menu = QMenu(self)
        
        if selected_node:
            item = selected_node
            node = item.node
            
            edit_action = menu.addAction("✏️ Editar propiedades")
            edit_action.triggered.connect(lambda: self.node_selected.emit(node))
            
            menu.addSeparator()
            
            if node.enabled:
                toggle_action = menu.addAction("🚫 Deshabilitar Nodo")
                toggle_action.triggered.connect(lambda: self._toggle_node_enabled(item, False))
            else:
                toggle_action = menu.addAction("✅ Habilitar Nodo")
                toggle_action.triggered.connect(lambda: self._toggle_node_enabled(item, True))
            
            menu.addSeparator()
            
            action = menu.addAction("🗑️ Eliminar Nodo")
            action.triggered.connect(lambda: self._request_delete(item.node))
        elif selected_edge:
            action = menu.addAction("🗑️ Eliminar Conexión")
            action.triggered.connect(lambda: self.request_delete_edge(selected_edge))
        else:
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
        self.create_node_from_drop(node_id_type, drop_pos)
        event.acceptProposedAction()
        
    def create_node_from_drop(self, node_def_id, pos):
        """Crea nodo desde drop de paleta"""
        from ui.node_definitions import get_all_nodes
        
        node_def = next((n for n in get_all_nodes() if n.id == node_def_id), None)
        if not node_def:
            return
            
        if self.receivers(self.node_dropped) > 0:
            self.node_dropped.emit(node_def, pos)
            return

        parent = self.parentWidget()
        while parent and not hasattr(parent, 'create_node_from_palette'):
            parent = parent.parentWidget()
            
        if parent:
            parent.create_node_from_palette(node_def, pos)

    def _request_delete(self, node: Node):
        """Emite señal para eliminar nodo"""
        reply = QMessageBox.question(
            self, "Confirmar",
            f"Eliminar nodo '{node.label}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.node_selected.emit(node)
    
    def _request_add_node(self, node_type: str, pos):
        """Solicita agregar un nuevo nodo en la posicion del click"""
        scene_pos = self.mapToScene(pos)
        views_parent = self.parentWidget()
        while views_parent and not hasattr(views_parent, 'add_node_interactive'):
            views_parent = views_parent.parentWidget()
        if views_parent:
            views_parent.add_node_interactive(node_type, scene_pos)
        else:
            print(f"[Canvas] Agregar nodo {node_type} en ({scene_pos.x()}, {scene_pos.y()})")
    
    def _toggle_node_enabled(self, node_item: NodeGraphicsItem, enabled: bool):
        """Habilita o deshabilita un nodo"""
        node_item.node.enabled = enabled
        node_item._update_enabled_visuals(enabled)
        
    def request_split_edge(self, node_item, edge_item):
        """Solicita dividir un edge con un nodo."""
        from_id = edge_item.from_item.node.id
        to_id = edge_item.to_item.node.id
        self.edge_split_requested.emit(node_item.node, from_id, to_id)
    
    def show_insert_node_menu(self, edge_item, scene_pos):
        """Muestra menu para insertar nodo en edge"""
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { font-size: 10pt; }")
        
        action_option = menu.addAction("▶️ ACTION")
        decision_option = menu.addAction("◆ DECISION")  
        loop_option = menu.addAction("↻ LOOP")
        db_option = menu.addAction("🗄 DATABASE")
        menu.addSeparator()
        annotation_option = menu.addAction("📝 ANNOTATION")
        
        view_pos = self.mapFromScene(scene_pos)
        global_pos = self.mapToGlobal(view_pos)
        
        selected_action = menu.exec(global_pos)
        
        if selected_action:
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
        from core.database_node import DatabaseNode
        from core.annotation_node import AnnotationNode
        
        views_parent = self.parentWidget()
        while views_parent and not hasattr(views_parent, 'current_workflow'):
            views_parent = views_parent.parentWidget()
        
        if not views_parent or not views_parent.current_workflow:
            return
        
        workflow = views_parent.current_workflow
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
        
        new_node.position = {"x": scene_pos.x(), "y": scene_pos.y()}
        
        old_edge = None
        for edge in workflow.edges:
            if edge.from_node == edge_item.from_item.node.id and edge.to_node == edge_item.to_item.node.id:
                old_edge = edge
                break
        
        if old_edge:
            workflow.edges.remove(old_edge)
        
        workflow.nodes.append(new_node)
        
        edge1 = Edge(from_node=edge_item.from_item.node.id, to_node=new_node.id)
        edge2 = Edge(from_node=new_node.id, to_node=edge_item.to_item.node.id)
        workflow.edges.append(edge1)
        workflow.edges.append(edge2)
        
        if hasattr(views_parent, 'refresh_canvas'):
            views_parent.refresh_canvas()
