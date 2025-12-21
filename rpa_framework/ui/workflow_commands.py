from PyQt6.QtGui import QUndoCommand
from rpa_framework.core.models import Node, Edge

class AddNodeCommand(QUndoCommand):
    def __init__(self, workflow, node, panel):
        super().__init__()
        self.workflow = workflow
        self.node = node
        self.panel = panel
        self.setText(f"Agregar nodo {node.label}")

    def redo(self):
        # En redo, simplemente agregamos el nodo
        # Verificamos si ya existe para no duplicar (aunque debería ser nuevo)
        exists = any(n.id == self.node.id for n in self.workflow.nodes)
        if not exists:
            self.workflow.nodes.append(self.node)
        
        self.panel.canvas.load_workflow(self.workflow)

    def undo(self):
        self.workflow.nodes = [n for n in self.workflow.nodes if n.id != self.node.id]
        self.panel.canvas.load_workflow(self.workflow)


class DeleteNodeCommand(QUndoCommand):
    def __init__(self, workflow, node, panel):
        super().__init__()
        self.workflow = workflow
        self.node = node
        self.panel = panel
        self.edges_snapshot = [] # Edges conectados para restaurar
        self.setText(f"Eliminar nodo {node.label}")
        
        # Guardar snapshot de edges conectados en init (antes de que se eliminen)
        self.edges_snapshot = [e for e in self.workflow.edges 
                               if e.from_node == self.node.id or e.to_node == self.node.id]

    def redo(self):
        # Eliminar nodo
        self.workflow.nodes = [n for n in self.workflow.nodes if n.id != self.node.id]
        # Eliminar edges conectados
        self.workflow.edges = [e for e in self.workflow.edges 
                               if e.from_node != self.node.id and e.to_node != self.node.id]
        
        self.panel.canvas.load_workflow(self.workflow)

    def undo(self):
        # Restaurar nodo
        self.workflow.nodes.append(self.node)
        # Restaurar edges
        self.workflow.edges.extend(self.edges_snapshot)
        
        self.panel.canvas.load_workflow(self.workflow)
        
        
class MoveNodeCommand(QUndoCommand):
    def __init__(self, workflow, node_id, old_pos, new_pos, panel):
        super().__init__()
        self.workflow = workflow
        self.node_id = node_id
        self.old_pos = old_pos
        self.new_pos = new_pos
        self.panel = panel
        self.setText(f"Mover nodo {node_id}")

    def redo(self):
        node = self.workflow.get_node(self.node_id)
        if node:
            node.position = self.new_pos
            self.panel.canvas.load_workflow(self.workflow)

    def undo(self):
        node = self.workflow.get_node(self.node_id)
        if node:
            node.position = self.old_pos
            self.panel.canvas.load_workflow(self.workflow)


class ConnectionCommand(QUndoCommand):
    """Comando para Crear o Eliminar conexión"""
    def __init__(self, workflow, from_id, to_id, panel, is_add=True):
        super().__init__()
        self.workflow = workflow
        self.from_id = from_id
        self.to_id = to_id
        self.panel = panel
        self.is_add = is_add
        
        action = "Conectar" if is_add else "Desconectar"
        self.setText(f"{action} {from_id} -> {to_id}")

    def redo(self):
        if self.is_add:
            self._add()
        else:
            self._remove()
        self.panel.canvas.load_workflow(self.workflow)

    def undo(self):
        if self.is_add:
            self._remove()
        else:
            self._add()
        self.panel.canvas.load_workflow(self.workflow)
        
    def _add(self):
        # Prevenir duplicados
        exists = any(e.from_node == self.from_id and e.to_node == self.to_id 
                     for e in self.workflow.edges)
        if not exists:
            self.workflow.edges.append(Edge(self.from_id, self.to_id))
            
    def _remove(self):
        self.workflow.edges = [e for e in self.workflow.edges 
                               if not (e.from_node == self.from_id and e.to_node == self.to_id)]


class ModifyPropertyCommand(QUndoCommand):
    def __init__(self, workflow, node_id, property_name, new_value, old_value, panel):
        super().__init__()
        self.workflow = workflow
        self.node_id = node_id
        self.prop = property_name
        self.new_val = new_value
        self.old_val = old_value
        self.panel = panel
        self.setText(f"Modificar {property_name} en {node_id}")

    def redo(self):
        node = self.workflow.get_node(self.node_id)
        if node:
            setattr(node, self.prop, self.new_val)
            self.panel.canvas.load_workflow(self.workflow) # Visual update

    def undo(self):
        node = self.workflow.get_node(self.node_id)
        if node:
            setattr(node, self.prop, self.old_val)
            self.panel.canvas.load_workflow(self.workflow)
