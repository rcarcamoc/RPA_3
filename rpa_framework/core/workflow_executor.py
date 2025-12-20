"""
Ejecutor de workflows para el RPA Framework 3.

Este módulo contiene la lógica para ejecutar workflows secuencialmente,
manejar control de flujo (IF/ELSE, LOOP) y gestionar variables compartidas.
"""

import subprocess
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
from core.models import Workflow, Node, NodeType, ActionNode, DecisionNode, LoopNode
from core.logger import WorkflowLogger


class WorkflowExecutor:
    """Ejecutor de workflows con soporte para IF/ELSE y LOOP"""
    
    def __init__(self, workflow: Workflow, log_dir: str = "logs"):
        """
        Inicializa el ejecutor.
        
        Args:
            workflow: Workflow a ejecutar
            log_dir: Directorio para guardar logs
        """
        self.workflow = workflow
        self.context: Dict[str, Any] = workflow.variables.copy()
        self.is_running = False
        self.should_stop = False
        
        # Crear logger
        log_filename = f"{workflow.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        log_path = os.path.join(log_dir, log_filename)
        self.logger = WorkflowLogger(log_path)
    
    def execute(self) -> Dict[str, Any]:
        """
        Ejecuta el workflow completo.
        
        Returns:
            Diccionario con el resultado de la ejecución:
            {
                "status": "success" | "error" | "stopped",
                "context": dict con variables finales,
                "logs": list de logs,
                "error": mensaje de error (si hubo)
            }
        """
        self.is_running = True
        self.should_stop = False
        self.logger.info(f"Iniciando workflow: {self.workflow.name}")
        
        try:
            # Obtener nodo de inicio
            start_node = self.workflow.get_start_node()
            if not start_node:
                raise ValueError("No se encontró nodo de inicio")
            
            # Ejecutar desde el primer nodo después del START
            current_node_id = self.workflow.get_next_node(start_node.id)
            if not current_node_id:
                current_node_id = start_node.id
            
            visited = set()
            max_iterations = 1000  # Prevenir loops infinitos
            iteration_count = 0
            
            # Ejecutar nodos secuencialmente
            while current_node_id and not self.should_stop:
                iteration_count += 1
                if iteration_count > max_iterations:
                    raise RuntimeError("Se excedió el límite de iteraciones (posible loop infinito)")
                
                node = self.workflow.get_node(current_node_id)
                if not node:
                    self.logger.error(f"Nodo no encontrado: {current_node_id}")
                    break
                
                # Nodo END termina la ejecución
                if node.type == NodeType.END:
                    self.logger.info("Workflow completado (nodo END)")
                    break
                
                # Evitar ciclos infinitos excepto en LOOP
                if node.type != NodeType.LOOP and current_node_id in visited:
                    self.logger.warning(f"Ciclo detectado en nodo {current_node_id}")
                    break
                
                visited.add(current_node_id)
                
                # Ejecutar nodo según su tipo
                self.logger.info(f"Ejecutando nodo: {node.label} ({node.type.value})")
                current_node_id = self._execute_node(node)
            
            # Resultado final
            if self.should_stop:
                self.logger.info("Workflow detenido manualmente")
                status = "stopped"
            else:
                self.logger.info("Workflow completado exitosamente")
                status = "success"
            
            return {
                "status": status,
                "context": self.context,
                "logs": self.logger.get_logs()
            }
        
        except Exception as e:
            self.logger.error(f"Error ejecutando workflow: {str(e)}")
            return {
                "status": "error",
                "context": self.context,
                "logs": self.logger.get_logs(),
                "error": str(e)
            }
        
        finally:
            self.is_running = False
    
    def stop(self):
        """Detiene la ejecución del workflow"""
        self.should_stop = True
        self.logger.warning("Solicitud de detención recibida")
    
    def _execute_node(self, node: Node) -> Optional[str]:
        """
        Ejecuta un nodo individual y devuelve el ID del siguiente nodo.
        
        Args:
            node: Nodo a ejecutar
            
        Returns:
            ID del siguiente nodo a ejecutar, o None si no hay siguiente
        """
        if node.type == NodeType.ACTION:
            return self._execute_action(node)
        elif node.type == NodeType.DECISION:
            return self._execute_decision(node)
        elif node.type == NodeType.LOOP:
            return self._execute_loop(node)
        else:
            # Nodos START u otros: solo continuar al siguiente
            return self.workflow.get_next_node(node.id)
    
    def _execute_action(self, node: ActionNode) -> Optional[str]:
        """Ejecuta un nodo de acción (script Python)"""
        if not node.script:
            self.logger.warning(f"Nodo {node.label} no tiene script asignado")
            return self.workflow.get_next_node(node.id)
        
        try:
            # Preparar entorno con variables del contexto
            env = os.environ.copy()
            for key, value in self.context.items():
                env[key] = str(value)
            
            # Ejecutar script
            self.logger.info(f"Ejecutando script: {node.script}")
            result = subprocess.run(
                ['python', node.script],
                capture_output=True,
                text=True,
                timeout=60,
                env=env
            )
            
            # Verificar resultado
            if result.returncode == 0:
                self.logger.info(f"[OK] Script completado: {node.label}")
                
                # Intentar parsear output JSON para actualizar contexto
                # Buscar líneas JSON válidas (puede haber prints antes)
                if result.stdout.strip():
                    json_found = False
                    for line in reversed(result.stdout.strip().split('\n')):
                        line = line.strip()
                        if line.startswith('{') and line.endswith('}'):
                            try:
                                output_data = json.loads(line)
                                if isinstance(output_data, dict):
                                    self.context.update(output_data)
                                    self.logger.info(f"Variables actualizadas: {list(output_data.keys())}")
                                    json_found = True
                                    break
                            except json.JSONDecodeError:
                                continue
                    
                    if not json_found:
                        self.logger.warning(f"No se encontro JSON valido en output")
            else:
                self.logger.error(f"[ERR] Script falló: {node.label}")
                self.logger.error(f"Error: {result.stderr}")
            
            return self.workflow.get_next_node(node.id)
        
        except subprocess.TimeoutExpired:
            self.logger.error(f"Timeout ejecutando script: {node.script}")
            return self.workflow.get_next_node(node.id)
        except Exception as e:
            self.logger.error(f"Error ejecutando script {node.script}: {str(e)}")
            return self.workflow.get_next_node(node.id)
    
    def _execute_decision(self, node: DecisionNode) -> Optional[str]:
        """Ejecuta un nodo de decisión (IF/ELSE)"""
        if not node.condition:
            self.logger.warning(f"Nodo {node.label} no tiene condición definida")
            return node.true_path if node.true_path else self.workflow.get_next_node(node.id)
        
        try:
            # Evaluar condición de forma segura
            result = self._eval_condition(node.condition)
            self.logger.info(f"Condición '{node.condition}' = {result}")
            
            # Decidir siguiente nodo según resultado
            if result:
                next_id = node.true_path
                self.logger.info(f"Rama TRUE: {next_id}")
            else:
                next_id = node.false_path
                self.logger.info(f"Rama FALSE: {next_id}")
            
            return next_id if next_id else self.workflow.get_next_node(node.id)
        
        except Exception as e:
            self.logger.error(f"Error evaluando condición '{node.condition}': {str(e)}")
            # En caso de error, tomar rama FALSE
            return node.false_path if node.false_path else self.workflow.get_next_node(node.id)
    
    def _execute_loop(self, node: LoopNode) -> Optional[str]:
        """Ejecuta un nodo de loop"""
        try:
            # Determinar número de iteraciones
            iterations = self._get_loop_count(node.iterations)
            self.logger.info(f"Ejecutando loop {node.label}: {iterations} iteraciones")
            
            # Ejecutar script N veces
            for i in range(iterations):
                if self.should_stop:
                    break
                
                self.logger.info(f"Loop iteración {i+1}/{iterations}")
                self.context[node.loop_var] = i
                
                # Ejecutar el script del loop
                if node.script:
                    # Crear ActionNode temporal usando object.__new__ para evitar problemas con __init__
                    temp_action = object.__new__(ActionNode)
                    temp_action.id = f"{node.id}_iter_{i}"
                    temp_action.label = f"{node.label} (iter {i+1})"
                    temp_action.script = node.script
                    temp_action.type = NodeType.ACTION
                    temp_action.position = {"x": 0, "y": 0}
                    self._execute_action(temp_action)
            
            #Limpiar variable de loop
            self.context.pop(node.loop_var, None)
            
            return self.workflow.get_next_node(node.id)
        
        except Exception as e:
            self.logger.error(f"Error ejecutando loop {node.label}: {str(e)}")
            return self.workflow.get_next_node(node.id)
    
    def _eval_condition(self, condition: str) -> bool:
        """
        Evalúa una condición de forma segura.
        
        Args:
            condition: Expresión a evaluar (ej: "x > 5", "status == 'ok'")
            
        Returns:
            Resultado booleano de la evaluación
        """
        try:
            # Crear entorno seguro con solo operadores básicos
            safe_dict = {
                "__builtins__": {},
                "True": True,
                "False": False,
                "None": None
            }
            safe_dict.update(self.context)
            
            result = eval(condition, safe_dict, {})
            return bool(result)
        
        except Exception as e:
            self.logger.warning(f"Error evaluando condición: {e}")
            return False
    
    def _get_loop_count(self, iterations: str) -> int:
        """
        Obtiene el número de iteraciones para un loop.
        
        Args:
            iterations: Puede ser un número o nombre de variable
            
        Returns:
            Número de iteraciones
        """
        try:
            # Intentar convertir directamente a int
            return int(iterations)
        except ValueError:
            # Es un nombre de variable
            value = self.context.get(iterations, 1)
            try:
                return int(value)
            except (ValueError, TypeError):
                self.logger.warning(f"No se pudo obtener iteraciones de '{iterations}', usando 1")
                return 1
