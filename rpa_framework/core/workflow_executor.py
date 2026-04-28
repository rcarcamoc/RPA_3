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
from core.models import Workflow, Node, NodeType, ActionNode, DecisionNode, LoopNode, WorkflowNode
from core.logger import WorkflowLogger
from utils.telegram_manager import enviar_alerta_todos
import mysql.connector
from mysql.connector import Error as MySQLError
try:
    import win32com.client
    import pythoncom
except ImportError:
    pass


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
        
        # Create a unique log filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Simple sanitization
        safe_name = "".join([c for c in workflow.name if c.isalnum() or c in (' ', '-', '_')]).strip().replace(' ', '_')
        log_filename = f"wf_{safe_name}_{timestamp}.log"
        
        # Ensure log_dir is not empty/None
        if not log_dir: log_dir = "logs"
            
        log_path = os.path.join(log_dir, log_filename)
        
        self.logger = WorkflowLogger(log_path)
        self.context: Dict[str, Any] = workflow.variables.copy()
        self.should_stop = False
        self.active_process = None
        
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
            
#            try:
#                enviar_alerta_todos(f"⏸️ <b>Proceso Pausado</b>\nEl asistente virtual (<b>'{self.workflow.name}'</b>) se ha detenido.\n<b>Motivo:</b> {str(e)}\n\nPor favor, revisa la aplicación para continuar u omitir este caso.")
#            except Exception as tel_e:
#                self.logger.log(f"⚠️ Error enviando alerta de Telegram: {tel_e}")
            
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
        if self.active_process:
            try:
                self.logger.log(f"   Matando proceso activo (PID: {self.active_process.pid})...")
                self.active_process.terminate()
                self.active_process.wait(timeout=3)
                if self.active_process.poll() is None:
                    self.active_process.kill()
            except Exception as e:
                self.logger.log(f"⚠️ Error al detener proceso: {e}")
    
    def _execute_node(self, node: Node) -> Optional[str]:
        """
        Ejecuta un nodo individual y devuelve el ID del siguiente nodo.
        """
        # Skip disabled nodes
        if not node.enabled:
            self.logger.log(f"🚫 Nodo deshabilitado: {node.label} (saltando)", "WARNING")
            return self.workflow.get_next_node(node.id)
        
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
        elif node.type == NodeType.WORKFLOW:
            return self._execute_workflow(node)
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
             # MEJORA: Detectar comando de minimizar todo y ejecutarlo nativamente para evitar conflictos de proceso
             if 'minimizeall()' in node.command.lower():
                 self.logger.log("💻 Ejecutando 'Minimizar Todo' nativamente...")
                 try:
                     # Asegurar que COM esté inicializado en este hilo (aunque el worker lo haga, doble check no duele)
                     if 'pythoncom' in globals():
                        pythoncom.CoInitialize()
                     
                     if 'win32com' in sys.modules or 'win32com' in globals():
                        shell = win32com.client.Dispatch("Shell.Application")
                        shell.MinimizeAll()
                        self.logger.log("✅ Escritorio mostrado (MinimizeAll OK)")
                        return self.workflow.get_next_node(node.id)
                     else:
                        raise ImportError("win32com not available")
                 except Exception as e:
                     self.logger.log(f"⚠️ Error en MinimizeAll nativo: {e}. Intentando vía subprocess...", "WARNING")
                     # Si falla, continuará con la ejecución normal de subprocess
             
             self.logger.log(f"💻 Ejecutando comando: {node.command}")
             try:
                # Preparar entorno
                env = os.environ.copy()
                for key, value in self.context.items():
                    try:
                        env[f"VAR_{key}"] = str(value)
                    except:
                        pass
                
                # MEJORA: Asegurar que los pipes se cierren correctamente con un bloque try-finally robusto
                # Usamos shell=True por compatibilidad con comandos complejos de Windows
                full_output = []
                process = None
                try:
                    process = subprocess.Popen(
                        node.command,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding='utf-8',
                        env=env,
                        bufsize=1,
                        universal_newlines=True,
                        errors='replace'
                    )
                    self.active_process = process
                    
                    # Leer salida en tiempo real
                    while True:
                        line = process.stdout.readline()
                        if not line and process.poll() is not None:
                            break
                        if line:
                            clean_line = line.strip()
                            if clean_line:
                                self.logger.log(f"   [CMD] {clean_line}")
                                full_output.append(clean_line)
                    
                    returncode = process.wait(timeout=10)
                finally:
                    # Garantizar cierre de pipes para evitar fugas de handles (causa de crashes en subsiguientes runs)
                    if process:
                        if process.stdout: process.stdout.close()
                        if process.stderr: process.stderr.close()
                
                if returncode == 0:
                     self.logger.log(f"✅ Comando ejecutado exitosamente")
                     if node.output_variable:
                        output_str = "\n".join(full_output).strip()
                        self.context[node.output_variable] = output_str
                elif returncode == 2:
                     self.logger.log(f"ℹ️ Comando finalizado (código 2): Sin registros. Deteniendo flujo.")
                     self.should_stop = True
                     return None
                else:
                     self.logger.log(f"❌ Error en comando (código {returncode})")
                     try:
                         ultimo_error = "\n".join(full_output[-3:]) if full_output else "Sin salida devuelta."
                         enviar_alerta_todos(f"❌ <b>Error en Comando</b>\nNodo: {node.label}\nComando falló con código {returncode}\nDetalle:\n<code>{ultimo_error}</code>")
                     except Exception as tel_e:
                         self.logger.log(f"⚠️ Error enviando alerta: {tel_e}")

                     if getattr(node, 'on_error', 'stop') == 'stop':
                         raise RuntimeError(f"Comando falló con código {returncode}")
                     
             except Exception as e:
                 self.logger.log(f"❌ Excepción ejecutando comando: {e}")
                 try:
                     enviar_alerta_todos(f"❌ <b>Excepción en Comando</b>\nNodo: {node.label}\nError: <code>{str(e)}</code>")
                 except Exception as tel_e:
                     self.logger.log(f"⚠️ Error enviando alerta: {tel_e}")
                 
                 if getattr(node, 'on_error', 'stop') == 'stop':
                     raise e
             
             return self.workflow.get_next_node(node.id)

        # 2. Ejecución de Script Python
        if not node.script:
            self.logger.log("⚠️ Nodo sin script ni comando, saltando")
            return self.workflow.get_next_node(node.id)
        
        self.logger.log(f"🐍 Ejecutando script: {node.script}")
        
        try:
            # Preparar entorno con variables del contexto
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            for key, value in self.context.items():
                env[f"VAR_{key}"] = str(value)
            
            # Resolver ruta del script
            script_path = Path(node.script)
            
            # Si es absoluta y existe, no hay nada que resolver
            if script_path.is_absolute() and script_path.exists():
                pass
            else:
                # Intentar buscar en ubicaciones relativas
                # Primero, si ya tiene un prefijo de subcarpeta (ej: "ui/Abre_pacs.py")
                possible_roots = [
                    Path.cwd(),
                    Path("recordings"),
                    Path("rpa_framework/recordings"),
                    Path("../recordings"), # Por si acaso se ejecuta desde rpa_framework/
                    Path("recordings/web"),
                    Path("recordings/ui"),
                    Path("recordings/ocr")
                ]
                
                found = False
                for root in possible_roots:
                    test_path = (root / script_path).resolve()
                    if test_path.exists():
                        script_path = test_path
                        found = True
                        break
                
                if not found:
                    # Búsqueda desesperada: si solo es el nombre del archivo, buscarlo recursivamente
                    self.logger.log(f"🔍 Buscando '{script_path}' en recordings recursivamente...")
                    potential_recordings = [Path("recordings"), Path("rpa_framework/recordings")]
                    for rec_dir in potential_recordings:
                        if rec_dir.exists():
                             matches = list(rec_dir.rglob(script_path.name))
                             if matches:
                                 script_path = matches[0].resolve()
                                 found = True
                                 self.logger.log(f"   ✨ Encontrado en: {script_path}")
                                 break
            
            if not script_path.exists():
                 self.logger.log(f"❌ Script no encontrado: {script_path}")
                 return self.workflow.get_next_node(node.id)
            
            # Asegurar ruta absoluta
            script_path = script_path.resolve()
            self.logger.log(f"   Ruta absoluta: {script_path}")

            # Ejecutar script con Popen para streaming
            cmd = [sys.executable, str(script_path)]
            self.logger.log(f"   Comando a ejecutar: {cmd}")
            
            # Use root directory (parent of rpa_framework) as CWD if possible
            current_cwd = Path.cwd()
            if current_cwd.name == "rpa_framework":
                exec_cwd = current_cwd.parent
            else:
                exec_cwd = current_cwd

            self.active_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                env=env,
                cwd=str(exec_cwd),
                bufsize=1,
                universal_newlines=True
            )
            process = self.active_process
            
            # Leer salida en tiempo real
            full_stdout = []
            while True:
                line = process.stdout.readline()
                if not line:
                    if process.poll() is not None:
                        break
                    continue
                
                clean_line = line.strip()
                if clean_line:
                    self.logger.log(f"   [PY] {clean_line}")
                    full_stdout.append(clean_line)
            
            returncode = process.poll()
            
            if returncode == 0:
                self.logger.log(f"✅ Script ejecutado exitosamente")
                
                # Opción 1: Guardar salida completa en variable si se definió explícitamente
                if node.output_variable:
                    output_str = "".join(full_stdout).strip()
                    self.context[node.output_variable] = output_str
                    self.logger.log(f"   Salida guardada en '{node.output_variable}': {output_str[:50]}...")
                
                # Opción 2: Intentar parsear líneas JSON para actualizaciones implícitas de contexto
                # Esto permite que scripts actualicen múltiples variables sin configurar output_variable
                for line in reversed(full_stdout):
                    try:
                        output_data = json.loads(line)
                        if isinstance(output_data, dict):
                            self.context.update(output_data)
                            self.logger.log(f"   Variables actualizadas (JSON): {list(output_data.keys())}")
                            # Si encontramos un JSON válido al final, asumimos que es el resultado estructurado
                            break
                    except json.JSONDecodeError:
                        continue
            elif returncode == 2:
                self.logger.log(f"ℹ️ Script finalizado (código 2): Sin registros para trabajar. Deteniendo flujo.")
                self.should_stop = True
                return None
            else:
                self.logger.log(f"❌ Error en script (código {returncode})")
                
                try:
                    # Capturar la última línea de la salida como posible mensaje de error, si lo hay
                    ultimo_log = "\n".join(full_stdout[-3:]) if full_stdout else "Sin salida devuelta."
                    # El propio script individual suele enviar su alerta detallada.
                    # Mantenemos logs de esto en la consola, pero omitimos un mensaje extra en telegram
                    # enviar_alerta_todos(f"❌ <b>Error en Script</b>\nNodo: {node.label}\nScript falló con código {returncode}\nUltimos logs:\n<code>{ultimo_log}</code>")
                except Exception as tel_e:
                    self.logger.log(f"⚠️ Error al procesar ultimo log: {tel_e}")
                
                if getattr(node, 'on_error', 'stop') == 'stop':
                    raise RuntimeError(f"El asistente no pudo completar la tarea en la fase '{node.label}'.")
            
        except Exception as e:
            self.logger.log(f"❌ Error: {str(e)}")
            
            # Igual omitimos alerta si el nivel superior lo va a atrapar
            # enviar_alerta_todos(f"❌ <b>Excepción en Script</b>\nNodo: {node.label}\nError: <code>{str(e)}</code>")
                
            if getattr(node, 'on_error', 'stop') == 'stop':
                raise RuntimeError(f"Falla inesperada en la fase '{node.label}': {str(e)}")
        
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
        """Ejecuta un nodo de loop (Count, List o While)"""
        
        loop_type = getattr(node, 'loop_type', 'count')
        self.logger.log(f"🔁 Iniciando loop ({loop_type})")
        
        # 1. Definir el iterador según el tipo
        iterator = []
        is_while = False
        
        if loop_type == 'count':
            iterations = self._get_loop_count(node.iterations)
            iterator = range(iterations)
            self.logger.log(f"   Modo: {iterations} iteraciones")
            
        elif loop_type == 'list':
            # Obtener lista desde variable
            var_name = node.iterable
            val = self.context.get(var_name, [])
            if isinstance(val, (list, tuple)):
                iterator = val
                self.logger.log(f"   Modo: Iterar lista '{var_name}' ({len(val)} elementos)")
            elif isinstance(val, dict):
                iterator = list(val.items())
                self.logger.log(f"   Modo: Iterar dict '{var_name}' ({len(val)} elementos)")
            else:
                self.logger.log(f"⚠️ Variable '{var_name}' no es iterable: {type(val)}")
                iterator = []
                
        elif loop_type == 'while':
            is_while = True
            self.logger.log(f"   Modo: While condición '{node.condition}'")
        
        # 2. Ejecutar Loop
        idx = 0
        MAX_ITER = 1000 # Safety break for while
        
        while True:
            if self.should_stop: break
            
            # Control de flujo del iterador
            current_item = None
            
            if is_while:
                if idx >= MAX_ITER:
                    self.logger.log("⚠️ Límite de seguridad alcanzado en While (1000)")
                    break
                if not self._eval_condition(node.condition):
                    break
                current_item = idx # En while, el item suele ser irrelevante o un contador
            else:
                # For loops (count/list)
                if idx >= len(iterator):
                    break
                current_item = iterator[idx]

            
            self.logger.log(f"   🔄 Iteración {idx + 1}")
            
            # Actualizar variables de loop en contexto
            # loop_var es el nombre de la variable para el item
            # _loop_index es inmutable estándar
            self.context["_loop_index"] = idx
            self.context[node.loop_var] = current_item
            
            # Ejecutar contenido del loop
            # 1. Workflow
            if hasattr(node, 'workflow_path') and node.workflow_path:
                try:
                     # Usamos una instancia temporal de WorkflowNode para reutilizar logica
                     # o llamamos directamente a la logica de ejecucion.
                     # Dado que _execute_workflow toma un nodo, creamos uno al vuelo o adaptamos.
                     
                     # Opción mejor: Extraer logica de execute workflow a un metodo auxiliar que tome el path
                     # Pero por simplicidad y reutilización de 'context', llamamos a lógica interna.
                     
                     # Hack: Crear un dummy node para pasarle a _execute_workflow
                     # Pero _execute_workflow devuelve "next node id", lo cual no queremos aqui.
                     # Solo queremos que ejecute y ya.
                     
                     self._run_workflow_internal(node.workflow_path)
                     
                except Exception as e:
                     self.logger.log(f"   ❌ Error en workflow del loop: {e}")
                     
                     # Delay por error si está configurado
                     delay = getattr(node, 'error_delay', 0)
                     if delay > 0:
                         self.logger.log(f"   ⏳ Esperando {delay}s por error...")
                         import time
                         time.sleep(delay)
                         
                     pass 
            
            # 2. Script (si existe y no es workflow, o ambos)
            elif node.script:
                try:
                    self._run_script_internal(node)
                except Exception as e:
                     self.logger.log(f"   ❌ Error en script de loop: {e}")
                     
                     if getattr(node, 'on_error', 'stop') == 'stop':
                         raise e
                     
                     # Si on_error es 'continue', aplicar delay tambien
                     delay = getattr(node, 'error_delay', 0)
                     if delay > 0:
                         self.logger.log(f"   ⏳ Esperando {delay}s por error...")
                         import time
                         time.sleep(delay)
            
            idx += 1
        
        self.logger.log(f"✅ Loop completado ({idx} iteraciones)")
        return self.workflow.get_next_node(node.id)

    def _run_workflow_internal(self, wf_path: str):
        """Ejecuta un workflow hijo reutilizando lógica (sin retorno de nodo)"""
        # Resolver ruta (copiado de _execute_workflow)
        path_obj = Path(wf_path)
        if not path_obj.is_absolute():
            base_dir = Path("rpa_framework/workflows")
            if not base_dir.exists(): base_dir = Path("workflows")
            
            candidate = base_dir / wf_path
            if not candidate.exists() and not candidate.suffix:
                candidate = candidate.with_suffix(".json")
            if candidate.exists(): path_obj = candidate
            else: path_obj = Path(wf_path).resolve()

        if not path_obj.exists():
             raise FileNotFoundError(f"Workflow loop no encontrado: {path_obj}")
             
        # Cargar nested workflow
        nested_wf = Workflow.from_json(str(path_obj))
        nested_wf.variables.update(self.context)
        
        # Executor
        nested_executor = WorkflowExecutor(nested_wf, self.logger.log_dir)
        
        # Patch logs
        original_log = nested_executor.logger.log
        def bridged_log(msg, level="INFO"):
            prefix = f"   [LOOP-WF:{nested_wf.name}]"
            self.logger.log(f"{prefix} {msg}", level)
        nested_executor.logger.log = bridged_log
        
        self.logger.log(f"   ▶️ Loop Running Workflow: {nested_wf.name}")
        result = nested_executor.execute()
        
        if result["status"] == "error":
             raise RuntimeError(f"Fallo en workflow de loop: {result.get('error')}")
        else:
             self.context.update(result["context"])

    def _run_script_internal(self, node):
        """Helper para ejecutar script python del loop"""
        env = os.environ.copy()
        for key, value in self.context.items():
            env[f"VAR_{key}"] = str(value)
        
        # Pasamos variables como JSON string también para estructuras complejas
        # O confiamos en env vars simples. 
        # Para listas/dicts complejos, el script debería leer un JSON temporal o similar si fuera robusto.
        # Por ahora mantenemos compatibilidad simple.
        
        result = subprocess.run(
            [sys.executable, node.script],
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=120,
            env=env
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Script falló: {result.stderr}")
        else:
             # Si el script imprime JSON, actualizamos contexto
             try:
                output_data = json.loads(result.stdout)
                if isinstance(output_data, dict):
                    self.context.update(output_data)
             except: pass
    
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
            
            if getattr(node, 'on_error', 'stop') == 'stop':
                raise e
            
        except Exception as e:
            error_msg = f"Error ejecutando DB: {str(e)}"
            self.logger.log(f"❌ {error_msg}")
            self.context[node.result_var] = {"error": str(e)}
            
            if getattr(node, 'on_error', 'stop') == 'stop':
                raise e
            
        finally:
            if connection and connection.is_connected():
                connection.close()
                self.logger.log(f"🔌 Conexión cerrada")
        
        return self.workflow.get_next_node(node.id)

    def _execute_workflow(self, node) -> Optional[str]:
        """
        Ejecuta un workflow anidado.
        """
        if not isinstance(node, WorkflowNode):
            self.logger.log(f"❌ Nodo no es WorkflowNode: {node.id}")
            return self.workflow.get_next_node(node.id)
            
        wf_path = node.workflow_path
        if not wf_path:
            self.logger.log("⚠️ Nodo Workflow sin ruta definida")
            return self.workflow.get_next_node(node.id)
            
        self.logger.log(f"🔄 Preparando ejecución de workflow anidado: {wf_path}")
        
        # Resolver ruta
        path_obj = Path(wf_path)
        if not path_obj.is_absolute():
            # Intentar en rpa_framework/workflows
            base_dir = Path("rpa_framework/workflows")
            if not base_dir.exists():
                 base_dir = Path("workflows")
            
            candidate = base_dir / wf_path
            # Si tiene extensión .json bien, sino probar agregandola
            if not candidate.exists() and not candidate.suffix:
                candidate = candidate.with_suffix(".json")
            
            if candidate.exists():
                path_obj = candidate
            else:
                # Fallback: intentar desde cwd
                path_obj = Path(wf_path).resolve()

        if not path_obj.exists():
             self.logger.log(f"❌ Archivo de workflow no encontrado: {path_obj}")
             if getattr(node, 'on_error', 'stop') == 'stop':
                 raise FileNotFoundError(f"Workflow no encontrado: {path_obj}")
             return self.workflow.get_next_node(node.id)
             
        try:
            # Cargar nested workflow
            nested_wf = Workflow.from_json(str(path_obj))
            
            # Inicializar variables con el contexto actual
            # (Sobreescribiendo las defaults del nested)
            nested_wf.variables.update(self.context)
            
            # Crear executor
            nested_executor = WorkflowExecutor(nested_wf, self.logger.log_dir)
            
            # --- PATCH LOGGER ---
            # Para que los logs del hijo suban al padre (y a la UI)
            original_child_log = nested_executor.logger.log
            def bridged_log(msg, level="INFO"):
                # Llamar al original para que quede en el archivo del hijo (opcional)
                # original_child_log(msg, level) 
                # O mejor: logguear en el padre con un prefijo
                prefix = f"   [WF:{nested_wf.name}]"
                self.logger.log(f"{prefix} {msg}", level)
            
            nested_executor.logger.log = bridged_log
            # --------------------
            
            self.logger.log(f"▶️ Iniciando sub-workflow: {nested_wf.name}")
            result = nested_executor.execute()
            
            if result["status"] == "error":
                self.logger.log(f"❌ Error en sub-workflow: {result.get('error')}")
                if getattr(node, 'on_error', 'stop') == 'stop':
                     raise RuntimeError(f"Fallo en sub-workflow: {result.get('error')}")
            elif result["status"] == "stopped":
                self.logger.log("⏹️ Sub-workflow detenido (posiblemente sin registros). Deteniendo padre.")
                self.should_stop = True
                return None
            else:
                self.logger.log(f"✅ Sub-workflow finalizado correctamente")
                # Actualizar contexto padre con resultados del hijo
                self.context.update(result["context"])
        
        except Exception as e:
            self.logger.log(f"❌ Error ejecutando nodo workflow: {e}")
            if getattr(node, 'on_error', 'stop') == 'stop':
                raise e
                
        return self.workflow.get_next_node(node.id)
