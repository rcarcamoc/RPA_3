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
            # Si el nodo está deshabilitado, no generar errores bloqueantes
            is_enabled = getattr(node, 'enabled', True)
            severity_if_disabled = "warning" if not is_enabled else "error"

            # Validar Nodos de Acción (pueden ser Script Python, Comando de Sistema o Ejecutable)
            if node.type == NodeType.ACTION:
                has_script = bool(getattr(node, 'script', None) and str(node.script).strip())
                has_command = bool(getattr(node, 'command', None) and str(node.command).strip())
                has_program = bool(getattr(node, 'program_path', None) and str(node.program_path).strip())

                if not (has_script or has_command or has_program):
                    errors.append({
                        "node_id": node.id,
                        "message": "El nodo de acción no tiene script ni comando configurado",
                        "severity": severity_if_disabled
                    })

            # Validar Loops (Bucle repetitivo)
            elif node.type == NodeType.LOOP:
                has_script = bool(getattr(node, 'script', None) and str(node.script).strip())
                has_command = bool(getattr(node, 'command', None) and str(node.command).strip())
                has_wf = bool(getattr(node, 'workflow_path', None) and str(node.workflow_path).strip())

                if not (has_script or has_command or has_wf):
                    errors.append({
                        "node_id": node.id,
                        "message": "No se ha configurado script, workflow ni comando para el bucle",
                        "severity": severity_if_disabled
                    })

                loop_t = getattr(node, 'loop_type', 'count')
                if loop_t == 'count' and not getattr(node, 'iterations', None):
                    errors.append({
                        "node_id": node.id,
                        "message": "Falta definir número de iteraciones",
                        "severity": severity_if_disabled
                    })
                elif loop_t == 'list' and not getattr(node, 'iterable', None):
                    errors.append({
                        "node_id": node.id,
                        "message": "Falta definir la variable iterable para la lista",
                        "severity": severity_if_disabled
                    })
                elif loop_t == 'while' and not getattr(node, 'condition', None):
                    errors.append({
                        "node_id": node.id,
                        "message": "Falta definir la condición del bucle while",
                        "severity": severity_if_disabled
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
