from dataclasses import dataclass, field
from typing import Dict, Any
from .models import Node, NodeType

@dataclass
class DelayNode(Node):
    """Nodo para pausar la ejecución por un tiempo determinado"""
    delay_seconds: int = 5
    type: NodeType = field(default=NodeType.DELAY, init=False)
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["delay_seconds"] = self.delay_seconds
        return data
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'DelayNode':
        node = object.__new__(DelayNode)
        node.id = data["id"]
        node.label = data["label"]
        node.delay_seconds = int(data.get("delay_seconds", 5))
        node.on_error = data.get("on_error", "stop")
        node.enabled = data.get("enabled", True)
        node.position = data.get("position", {"x": 0, "y": 0})
        node.type = NodeType.DELAY
        return node
