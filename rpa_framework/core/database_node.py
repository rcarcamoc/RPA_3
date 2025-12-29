"""
Nodo de base de datos para workflows RPA Framework 3.

Este módulo define el DatabaseNode para operaciones SQL.
"""

from typing import Dict, Any
from dataclasses import dataclass, field
from core.models import Node, NodeType


@dataclass
class DatabaseNode(Node):
    """Nodo de base de datos para operaciones SQL"""
    host: str = "localhost"
    port: int = 3306
    user: str = ""
    password: str = ""
    database: str = ""
    query: str = ""
    operation: str = "SELECT"  # SELECT, INSERT, UPDATE, DELETE
    result_var: str = "db_result"  # Variable donde guardar resultados de SELECT
    type: NodeType = field(default=NodeType.DATABASE, init=False)
    
    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "database": self.database,
            "query": self.query,
            "operation": self.operation,
            "resultVar": self.result_var
        })
        return data
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'DatabaseNode':
        node = object.__new__(DatabaseNode)
        node.id = data["id"]
        node.label = data["label"]
        node.host = data.get("host", "localhost")
        node.port = data.get("port", 3306)
        node.user = data.get("user", "")
        node.password = data.get("password", "")
        node.database = data.get("database", "")
        node.query = data.get("query", "")
        node.operation = data.get("operation", "SELECT")
        node.result_var = data.get("resultVar", "db_result")
        node.on_error = data.get("on_error", "stop")
        node.position = data.get("position", {"x": 0, "y": 0})
        node.type = NodeType.DATABASE
        return node
