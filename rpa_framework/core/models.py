"""
Modelos para el sistema de workflows RPA Framework 3.

Este módulo define las clases base para representar workflows, nodos y conexiones.
"""

from typing import Dict, List, Any, Optional, Literal
from dataclasses import dataclass, field
from enum import Enum
import json

# Forward declaration - DatabaseNode will be imported after NodeType is defined


class NodeType(Enum):
    """Tipos de nodos soportados"""
    ACTION = "action"
    DECISION = "decision"
    LOOP = "loop"
    DATABASE = "database"
    ANNOTATION = "annotation"
    START = "start"
    END = "end"


@dataclass
class Node:
    """Clase base para nodos de workflow"""
    id: str
    type: NodeType
    label: str
    position: Dict[str, float] = field(default_factory=lambda: {"x": 0, "y": 0})
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte el nodo a diccionario para serialización"""
        return {
            "id": self.id,
            "type": self.type.value,
            "label": self.label,
            "position": self.position
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'Node':
        """Crea un nodo desde un diccionario"""
        node_type = NodeType(data["type"])
        
        # Import here to avoid circular dependency
        if node_type == NodeType.DATABASE:
            from core.database_node import DatabaseNode
            return DatabaseNode.from_dict(data)
        
        if node_type == NodeType.ANNOTATION:
            from core.annotation_node import AnnotationNode
            return AnnotationNode.from_dict(data)
        
        if node_type == NodeType.ACTION:
            return ActionNode.from_dict(data)
        elif node_type == NodeType.DECISION:
            return DecisionNode.from_dict(data)
        elif node_type == NodeType.LOOP:
            return LoopNode.from_dict(data)
        else:
            return Node(
                id=data["id"],
                type=node_type,
                label=data["label"],
                position=data.get("position", {"x": 0, "y": 0})
            )


@dataclass
class ActionNode(Node):
    """Nodo de acción que ejecuta un script"""
    script: str = ""
    type: NodeType = field(default=NodeType.ACTION, init=False)
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["script"] = self.script
        return data
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'ActionNode':
        # Don't pass type since it's not in __init__
        node = object.__new__(ActionNode)
        node.id = data["id"]
        node.label = data["label"]
        node.script = data.get("script", "")
        node.position = data.get("position", {"x": 0, "y": 0})
        node.type = NodeType.ACTION
        return node


@dataclass
class DecisionNode(Node):
    """Nodo de decisión (IF/ELSE)"""
    condition: str = ""
    true_path: str = ""  # ID del nodo si condición es True
    false_path: str = ""  # ID del nodo si condición es False
    type: NodeType = field(default=NodeType.DECISION, init=False)
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "condition": self.condition,
            "truePath": self.true_path,
            "falsePath": self.false_path
        })
        return data
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'DecisionNode':
        node = object.__new__(DecisionNode)
        node.id = data["id"]
        node.label = data["label"]
        node.condition = data.get("condition", "")
        node.true_path = data.get("truePath", "")
        node.false_path = data.get("falsePath", "")
        node.position = data.get("position", {"x": 0, "y": 0})
        node.type = NodeType.DECISION
        return node


@dataclass
class LoopNode(Node):
    """Nodo de bucle (LOOP)"""
    script: str = ""
    iterations: str = "1"  # Puede ser número o nombre de variable
    loop_var: str = "_loop_index"  # Nombre de variable para índice actual
    type: NodeType = field(default=NodeType.LOOP, init=False)
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "script": self.script,
            "iterations": self.iterations,
            "loopVar": self.loop_var
        })
        return data
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'LoopNode':
        node = object.__new__(LoopNode)
        node.id = data["id"]
        node.label = data["label"]
        node.script = data.get("script", "")
        node.iterations = data.get("iterations", "1")
        node.loop_var = data.get("loopVar", "_loop_index")
        node.position = data.get("position", {"x": 0, "y": 0})
        node.type = NodeType.LOOP
        return node


@dataclass
class Edge:
    """Conexión entre nodos"""
    from_node: str
    to_node: str
    
    def to_dict(self) -> Dict[str, str]:
        return {
            "from": self.from_node,
            "to": self.to_node
        }
    
    @staticmethod
    def from_dict(data: Dict[str, str]) -> 'Edge':
        return Edge(
            from_node=data["from"],
            to_node=data["to"]
        )


@dataclass
class Workflow:
    """Workflow completo con nodos y conexiones"""
    id: str
    name: str
    nodes: List[Node] = field(default_factory=list)
    edges: List[Edge] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    
    def get_node(self, node_id: str) -> Optional[Node]:
        """Obtiene un nodo por su ID"""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None
    
    def get_next_node(self, node_id: str) -> Optional[str]:
        """Obtiene el ID del siguiente nodo conectado"""
        for edge in self.edges:
            if edge.from_node == node_id:
                return edge.to_node
        return None
    
    def get_start_node(self) -> Optional[Node]:
        """Obtiene el nodo de inicio"""
        for node in self.nodes:
            if node.type == NodeType.START:
                return node
        # Si no hay nodo START, devuelve el primero
        return self.nodes[0] if self.nodes else None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte el workflow a diccionario para serialización"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
            "variables": self.variables
        }
    
    def to_json(self, filepath: str):
        """Guarda el workflow en un archivo JSON"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'Workflow':
        """Crea un workflow desde un diccionario"""
        return Workflow(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            nodes=[Node.from_dict(n) for n in data.get("nodes", [])],
            edges=[Edge.from_dict(e) for e in data.get("edges", [])],
            variables=data.get("variables", {})
        )
    
    @staticmethod
    def from_json(filepath: str) -> 'Workflow':
        """Carga un workflow desde un archivo JSON"""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return Workflow.from_dict(data)
