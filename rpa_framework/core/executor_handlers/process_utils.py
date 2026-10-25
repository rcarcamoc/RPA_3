"""
Utilidades de subprocesos, entorno, evaluación de condiciones y nodos básicos (Decision, Delay).
"""

import os
import sys
import time
from pathlib import Path
from typing import Dict, Optional
import mysql.connector
from core.models import DecisionNode


def get_python_exe() -> str:
    """Retorna la ruta al ejecutable python."""
    if os.environ.get("RPA_SHOW_CONSOLE", "0") == "1":
        exe = sys.executable
        if "pythonw.exe" in exe.lower():
            cand = exe.lower().replace("pythonw.exe", "python.exe")
            if os.path.exists(cand):
                return cand
        return exe
    exe = sys.executable
    if "pythonw.exe" in exe.lower():
        return exe
    cand = exe.lower().replace("python.exe", "pythonw.exe")
    if os.path.exists(cand):
        return cand
    return exe


def _get_silent_process_flags():
    """Retorna creationflags y startupinfo. Por política de ejecución en primer plano, nunca oculta consolas en segundo plano."""
    return 0, None


class ProcessEnvMixin:
    """Mixin para gestión de entorno de subprocesos, resolución en BD, condiciones y delays."""

    def _get_subprocess_env(self) -> Dict[str, str]:
        """Prepara el entorno para ejecutar subprocesses de forma robusta"""
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"

        # Agregar project_root y rpa_framework a PYTHONPATH para asegurar importaciones robustas
        # Nota: este archivo vive en rpa_framework/core/executor_handlers/process_utils.py
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        rpa_framework_root = project_root / "rpa_framework"

        existing_pythonpath = env.get("PYTHONPATH", "")
        separator = ";" if os.name == 'nt' else ":"
        if existing_pythonpath:
            env["PYTHONPATH"] = f"{project_root}{separator}{rpa_framework_root}{separator}{existing_pythonpath}"
        else:
            env["PYTHONPATH"] = f"{project_root}{separator}{rpa_framework_root}"

        for key, value in self.context.items():
            env[f"VAR_{key}"] = str(value)

        return env

    def _sync_screen_resolution_to_db(self, resolution: str):
        """Sincroniza la resolución de pantalla con el registro 'En Proceso' en ris.registro_acciones si no está seteada."""
        try:
            conn = mysql.connector.connect(host='localhost', user='root', password='', database='ris', connect_timeout=2)
            cur = conn.cursor()
            cur.execute("""
                UPDATE ris.registro_acciones 
                SET resolucion_pantalla = %s 
                WHERE estado = 'En Proceso' AND (resolucion_pantalla IS NULL OR resolucion_pantalla = '')
            """, (resolution,))
            conn.commit()
            cur.close()
            conn.close()
        except Exception:
            pass

    def _execute_delay(self, node) -> Optional[str]:
        from core.delay_node import DelayNode
        if isinstance(node, DelayNode):
            sec = node.delay_seconds
            self.logger.log(f"⏳ Pausando por {sec} segundos...")
            end_time = time.time() + sec
            while time.time() < end_time and not self.should_stop:
                time.sleep(0.2)
            if self.should_stop:
                self.logger.log("⏹️ Pausa interrumpida por detención de workflow.")
                return None
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
