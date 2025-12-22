"""
Nodo de anotación para workflows RPA Framework 3.

Este módulo define el AnnotationNode para comentarios y documentación.
"""

from typing import Dict, Any
from dataclasses import dataclass, field
from core.models import Node, NodeType


@dataclass
class AnnotationNode(Node):
    """Nodo de anotación/comentario para documentación"""
    text: str = ""
    color: str = "#ffffcc"  # Light yellow
    width: int = 200
    height: int = 100
    type: NodeType = field(default=NodeType.ANNOTATION, init=False)
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "text": self.text,
            "color": self.color,
            "width": self.width,
            "height": self.height
        })
        return data
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'AnnotationNode':
        node = object.__new__(AnnotationNode)
        node.id = data["id"]
        node.label = data["label"]
        node.text = data.get("text", "")
        node.color = data.get("color", "#ffffcc")
        node.width = data.get("width", 200)
        node.height = data.get("height", 100)
        node.position = data.get("position", {"x": 0, "y": 0})
        node.type = NodeType.ANNOTATION
        return node
