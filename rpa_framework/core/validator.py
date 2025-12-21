from typing import List, Dict, Any
from .models import Workflow, NodeType, ActionNode, DecisionNode, LoopNode

class WorkflowValidator:
    """Validador de reglas de integridad para workflows."""
    
    @staticmethod
    def validate(workflow: Workflow) -> List[Dict[str, Any]]:
        """
        Valida el workflow y retorna una lista de errores.
        Formato de error: {"node_id": "id", "message": "Error description", "severity": "error"|"warning"}
        """
        errors = []
        
        # 1. Verificar nodo de inicio
        start_node = workflow.get_start_node()
        if not start_node:
            errors.append({
                "node_id": None, 
                "message": "El workflow no tiene nodo de Inicio (Start)",
                "severity": "error"
            })
            
        # Mapa de nodos accesibles (para detectar bucles inalcanzables)
        # TODO: Implementar recorrido de grafo
            
        # 2. Validar cada nodo individualmente
        for node in workflow.nodes:
            # Validar Scripts
            if node.type in [NodeType.ACTION, NodeType.LOOP]:
                if not hasattr(node, 'script') or not node.script:
                    errors.append({
                        "node_id": node.id,
                        "message": "No se ha seleccionado ningún script",
                        "severity": "error"
                    })
            
            # Validar Decisiones
            if node.type == NodeType.DECISION:
                if not node.condition:
                    errors.append({
                        "node_id": node.id,
                        "message": "La condición está vacía",
                        "severity": "error"
                    })
                
                # Al menos un camino debe estar definido
                if not node.true_path and not node.false_path:
                    errors.append({
                        "node_id": node.id,
                        "message": "Debe tener al menos una conexión de salida (True o False)",
                        "severity": "warning"
                    })
            
            # Validar Loops
            if node.type == NodeType.LOOP:
                if not node.iterations:
                    errors.append({
                        "node_id": node.id,
                        "message": "Falta definir número de iteraciones o variable",
                        "severity": "error"
                    })
            
            # 3. Validar Conectividad
            # Entradas (excepto Start)
            if node.type != NodeType.START:
                has_incoming = any(e.to_node == node.id for e in workflow.edges)
                if not has_incoming:
                    errors.append({
                        "node_id": node.id,
                        "message": "Nodo inalcanzable (sin conexiones de entrada)",
                        "severity": "warning"
                    })
            
            # Salidas (excepto End)
            if node.type != NodeType.END:
                # Para DecisionNode, verificamos true_path/false_path arriba, pero también edges visuales
                # El modelo garantiza sync, asi que checkeamos edges visuales como proxy de conectividad
                has_outgoing = any(e.from_node == node.id for e in workflow.edges)
                
                if not has_outgoing:
                    if node.type == NodeType.DECISION:
                        # Ya cubierto por true/false path check, pero confirmamos
                         pass
                    else:
                        errors.append({
                            "node_id": node.id,
                            "message": "Nodo sin salida (el flujo se detendrá aquí)",
                            "severity": "warning"
                        })
                        
        return errors
