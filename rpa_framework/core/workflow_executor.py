"""
Ejecutor de workflows para el RPA Framework 3.

Este módulo contiene la lógica para ejecutar workflows secuencialmente,
manejar control de flujo (IF/ELSE, LOOP) y gestionar variables compartidas.
"""

import subprocess
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional
from core.models import Workflow, Node, NodeType, ActionNode, DecisionNode, LoopNode
from core.logger import WorkflowLogger
import mysql.connector
from mysql.connector import Error as MySQLError


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
        self.logger = WorkflowLogger(log_dir)
        self.context: Dict[str, Any] = workflow.variables.copy()
        self.should_stop = False
        
        self.logger.log(f"🚀 Workflow inicializado: {workflow.name}")
        self.logger.log(f"   Variables iniciales: {self.context}")
    
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
        try:
            self.logger.log("=" * 60)
            self.logger.log(f"▶️ Iniciando ejecución: {self.workflow.name}")
            self.logger.log("=" * 60)
            
            # Obtener nodo inicial
            current_node = self.workflow.get_start_node()
            
            if not current_node:
                raise ValueError("No se encontró nodo de inicio")
            
            # Ejecutar nodos secuencialmente
            while current_node and not self.should_stop:
                self.logger.log(f"\n📍 Nodo actual: {current_node.label} ({current_node.type.value})")
                
                # Ejecutar nodo y obtener siguiente
                next_node_id = self._execute_node(current_node)
                
                if not next_node_id:
                    self.logger.log("✅ Fin del workflow (no hay más nodos)")
                    break
                
                # Obtener siguiente nodo
                current_node = self.workflow.get_node(next_node_id)
                
                if not current_node:
                    self.logger.log(f"⚠️ Nodo no encontrado: {next_node_id}")
                    break
            
            # Resultado final
            status = "stopped" if self.should_stop else "success"
            
            self.logger.log("=" * 60)
            self.logger.log(f"✅ Ejecución completada: {status}")
            self.logger.log(f"   Variables finales: {self.context}")
            self.logger.log("=" * 60)
            
            return {
                "status": status,
                "context": self.context,
                "logs": self.logger.get_logs(),
                "error": None
            }
            
        except Exception as e:
            error_msg = f"Error en ejecución: {str(e)}"
            self.logger.log(f"❌ {error_msg}")
            
            return {
                "status": "error",
                "context": self.context,
                "logs": self.logger.get_logs(),
                "error": error_msg
            }
    
    def stop(self):
        """Detiene la ejecución del workflow"""
        self.should_stop = True
        self.logger.log("⏹️ Deteniendo workflow...")
    
    def _execute_node(self, node: Node) -> Optional[str]:
        """
        Ejecuta un nodo individual y devuelve el ID del siguiente nodo.
        """
        # Skip annotation nodes (they're just for documentation)
        if node.type == NodeType.ANNOTATION:
            self.logger.log(f"📝 Anotación: {node.label} (saltando)")
            return self.workflow.get_next_node(node.id)
        
        if node.type == NodeType.ACTION:
            return self._execute_action(node)
        elif node.type == NodeType.DECISION:
            return self._execute_decision(node)
        elif node.type == NodeType.LOOP:
            return self._execute_loop(node)
        elif node.type == NodeType.DATABASE:
            return self._execute_database(node)
        elif node.type == NodeType.DELAY:
            return self._execute_delay(node)
        elif node.type == NodeType.END:
             self.logger.log("⏹️ Nodo Final alcanzado.")
             return None
        else:
            # Nodos START u otros: solo continuar al siguiente
            return self.workflow.get_next_node(node.id)
            
    def _execute_delay(self, node) -> Optional[str]:
        import time
        from core.delay_node import DelayNode
        if isinstance(node, DelayNode):
            sec = node.delay_seconds
            self.logger.log(f"⏳ Pausando por {sec} segundos...")
            time.sleep(sec)
        return self.workflow.get_next_node(node.id)
    
    def _execute_action(self, node: ActionNode) -> Optional[str]:
        """Ejecuta un nodo de acción (script Python o comando)"""
        
        # 1. Ejecución de Comando de Sistema
        if node.command:
             self.logger.log(f"💻 Ejecutando comando: {node.command}")
             try:
                # Preparar entorno
                env = os.environ.copy()
                for key, value in self.context.items():
                    env[f"VAR_{key}"] = str(value)
                
                # Ejecutar comando en Shell
                result = subprocess.run(
                    node.command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    env=env
                )
                
                if result.returncode == 0:
                     self.logger.log(f"✅ Comando ejecutado exitosamente")
                     if result.stdout: self.logger.log(f"   Salida: {result.stdout.strip()[:200]}")
                else:
                     self.logger.log(f"❌ Error en comando (código {result.returncode})")
                     if result.stderr: self.logger.log(f"   Error: {result.stderr.strip()[:200]}")
                     
             except Exception as e:
                 self.logger.log(f"❌ Error ejecutando comando: {e}")
             
             return self.workflow.get_next_node(node.id)

        # 2. Ejecución de Script Python
        if not node.script:
            self.logger.log("⚠️ Nodo sin script ni comando, saltando")
            return self.workflow.get_next_node(node.id)
        
        self.logger.log(f"🐍 Ejecutando script: {node.script}")
        
        try:
            # Preparar entorno con variables del contexto
            env = os.environ.copy()
            for key, value in self.context.items():
                env[f"VAR_{key}"] = str(value)
            
            # Resolver ruta del script
            script_path = Path(node.script)
            if not script_path.is_absolute():
                # Intentar buscar en rpa_framework/recordings o cwd
                possible_paths = [
                    Path("rpa_framework/recordings") / script_path,
                    Path("recordings") / script_path,
                    Path.cwd() / script_path
                ]
                
                for p in possible_paths:
                    if p.exists():
                        script_path = p
                        break
            
            if not script_path.exists():
                 self.logger.log(f"❌ Script no encontrado: {script_path}")
                 return self.workflow.get_next_node(node.id)
            
            # Asegurar ruta absoluta
            script_path = script_path.resolve()
            self.logger.log(f"   Ruta absoluta: {script_path}")

            # Ejecutar script
            cmd = [sys.executable, str(script_path)]
            self.logger.log(f"   Comando a ejecutar: {cmd}")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                env=env,
                cwd=str(script_path.parent) # Ejecutar en el directorio del script
            )
            
            if result.returncode == 0:
                self.logger.log(f"✅ Script ejecutado exitosamente")
                
                # Intentar parsear salida como JSON para actualizar contexto
                try:
                    output_data = json.loads(result.stdout)
                    if isinstance(output_data, dict):
                        self.context.update(output_data)
                        self.logger.log(f"   Variables actualizadas: {list(output_data.keys())}")
                except json.JSONDecodeError:
                    # Si no es JSON, solo loguear la salida
                    if result.stdout:
                        self.logger.log(f"   Salida: {result.stdout[:200]}")
            else:
                self.logger.log(f"❌ Error en script (código {result.returncode})")
                if result.stderr:
                    self.logger.log(f"   Error: {result.stderr[:200]}")
            
        except subprocess.TimeoutExpired:
            self.logger.log("❌ Timeout ejecutando script")
        except Exception as e:
            self.logger.log(f"❌ Error: {str(e)}")
        
        return self.workflow.get_next_node(node.id)
    
    def _execute_decision(self, node: DecisionNode) -> Optional[str]:
        """Ejecuta un nodo de decisión (IF/ELSE)"""
        if not node.condition:
            self.logger.log("⚠️ Decisión sin condición, tomando rama TRUE")
            return node.true_path or self.workflow.get_next_node(node.id)
        
        self.logger.log(f"🔀 Evaluando condición: {node.condition}")
        
        result = self._eval_condition(node.condition)
        
        if result:
            self.logger.log("   ✅ Condición TRUE")
            return node.true_path or self.workflow.get_next_node(node.id)
        else:
            self.logger.log("   ❌ Condición FALSE")
            return node.false_path or self.workflow.get_next_node(node.id)
    
    def _execute_loop(self, node: LoopNode) -> Optional[str]:
        """Ejecuta un nodo de loop"""
        iterations = self._get_loop_count(node.iterations)
        
        self.logger.log(f"🔁 Iniciando loop: {iterations} iteraciones")
        
        for i in range(iterations):
            if self.should_stop:
                break
            
            self.logger.log(f"   Iteración {i + 1}/{iterations}")
            
            # Actualizar variable de loop
            self.context[node.loop_var] = i
            
            # Ejecutar script del loop si existe
            if node.script:
                try:
                    env = os.environ.copy()
                    for key, value in self.context.items():
                        env[f"VAR_{key}"] = str(value)
                    
                    result = subprocess.run(
                        ['python', node.script],
                        capture_output=True,
                        text=True,
                        timeout=30,
                        env=env
                    )
                    
                    if result.returncode != 0:
                        self.logger.log(f"   ⚠️ Error en iteración {i + 1}")
                        
                except Exception as e:
                    self.logger.log(f"   ❌ Error: {str(e)}")
        
        self.logger.log(f"✅ Loop completado")
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
            # Crear un diccionario seguro con solo las variables del contexto
            safe_dict = self.context.copy()
            
            # Agregar operadores seguros
            safe_dict.update({
                '__builtins__': {
                    'True': True,
                    'False': False,
                    'None': None,
                    'len': len,
                    'str': str,
                    'int': int,
                    'float': float
                }
            })
            
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
                self.logger.log(f"⚠️ Iteraciones inválidas: {iterations}, usando 1")
                return 1
    
    def _execute_database(self, node) -> Optional[str]:
        """
        Ejecuta un nodo de base de datos.
        
        Args:
            node: DatabaseNode a ejecutar
            
        Returns:
            ID del siguiente nodo
        """
        from core.database_node import DatabaseNode
        
        if not isinstance(node, DatabaseNode):
            self.logger.log(f"❌ Nodo no es DatabaseNode: {node.id}")
            return self.workflow.get_next_node(node.id)
        
        self.logger.log(f"🗄️ Ejecutando nodo DB: {node.label}")
        self.logger.log(f"   Operación: {node.operation}")
        self.logger.log(f"   Host: {node.host}:{node.port}")
        self.logger.log(f"   Database: {node.database}")
        
        connection = None
        try:
            # Conectar a MySQL
            connection = mysql.connector.connect(
                host=node.host,
                port=node.port,
                user=node.user,
                password=node.password,
                database=node.database
            )
            
            if connection.is_connected():
                self.logger.log(f"✅ Conectado a MySQL")
                
                cursor = connection.cursor(dictionary=True)
                
                # Reemplazar variables en la query
                query = node.query
                for var_name, var_value in self.context.items():
                    placeholder = f"{{{var_name}}}"
                    if placeholder in query:
                        # Escapar valores para prevenir SQL injection
                        if isinstance(var_value, str):
                            var_value = var_value.replace("'", "''")
                            query = query.replace(placeholder, f"'{var_value}'")
                        else:
                            query = query.replace(placeholder, str(var_value))
                
                self.logger.log(f"   Query: {query[:100]}...")
                
                # Ejecutar query
                cursor.execute(query)
                
                if node.operation.upper() == "SELECT":
                    # Para SELECT, obtener resultados
                    results = cursor.fetchall()
                    
                    # Inyectar resultados en contexto
                    if results:
                        if len(results) == 1:
                            # Un solo resultado: dict
                            self.context[node.result_var] = results[0]
                            self.logger.log(f"✅ Resultado guardado en '{node.result_var}': {results[0]}")
                        else:
                            # Múltiples resultados: lista de dicts
                            self.context[node.result_var] = results
                            self.logger.log(f"✅ {len(results)} resultados guardados en '{node.result_var}'")
                    else:
                        self.context[node.result_var] = None
                        self.logger.log(f"⚠️ No se encontraron resultados")
                else:
                    # Para INSERT/UPDATE/DELETE, hacer commit
                    connection.commit()
                    affected_rows = cursor.rowcount
                    self.logger.log(f"✅ {node.operation} ejecutado. Filas afectadas: {affected_rows}")
                    self.context[node.result_var] = {"affected_rows": affected_rows}
                
                cursor.close()
                
        except MySQLError as e:
            error_msg = f"Error MySQL: {str(e)}"
            self.logger.log(f"❌ {error_msg}")
            self.context[node.result_var] = {"error": str(e)}
            
        except Exception as e:
            error_msg = f"Error ejecutando DB: {str(e)}"
            self.logger.log(f"❌ {error_msg}")
            self.context[node.result_var] = {"error": str(e)}
            
        finally:
            if connection and connection.is_connected():
                connection.close()
                self.logger.log(f"🔌 Conexión cerrada")
        
        return self.workflow.get_next_node(node.id)
