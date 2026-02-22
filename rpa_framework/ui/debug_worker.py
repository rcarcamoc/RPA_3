# -*- coding: utf-8 -*-
"""
debug_worker.py — Motor de ejecución paso a paso para el módulo de depuración RPA.

Estrategia:
  - Parsea el script Python con `ast` para identificar los bloques de acción.
  - Ejecuta el script en un subprocess separado con un protocolo de sincronización
    por pipes (stdin/stdout): el proceso hijo envía "STEP_DONE:<n>" y espera
    "CMD:NEXT", "CMD:BACK" o "CMD:STOP".
  - Emite señales PyQt para que el overlay actualice la UI en tiempo real.
"""

import ast
import os
import sys
import time
import textwrap
import tempfile
from pathlib import Path
from typing import List, Tuple

from PyQt6.QtCore import QThread, pyqtSignal, QMutex, QWaitCondition


# ---------------------------------------------------------------------------
# Helpers de parseo
# ---------------------------------------------------------------------------

def extract_steps_from_script(script_path: str) -> List[Tuple[int, int, str]]:
    """
    Parsea el script y devuelve una lista de pasos como:
        (linea_inicio, linea_fin, descripcion)

    Estrategia de detección de pasos:
      1. Busca comentarios "# Acción N:" para delimitar bloques.
      2. Si no los encuentra, divide el cuerpo del método `run()` en bloques
         separados por líneas en blanco o sentencias `try/except`.
      3. Fallback: cada sentencia de nivel superior dentro de `run()` es un paso.
    """
    try:
        # Intentar utf-8-sig primero (maneja BOM), luego latin-1 como fallback
        try:
            with open(script_path, "r", encoding="utf-8-sig") as f:
                source = f.read()
        except UnicodeDecodeError:
            with open(script_path, "r", encoding="latin-1") as f:
                source = f.read()
        lines = source.splitlines()
    except Exception:
        return []

    steps: List[Tuple[int, int, str]] = []

    # --- Estrategia 1: comentarios "# Acción N:" ---
    import re
    action_pattern = re.compile(r"#\s*Acci[oó]n\s+(\d+)", re.IGNORECASE)
    action_lines = []
    for i, line in enumerate(lines):
        if action_pattern.search(line):
            action_lines.append(i)  # 0-indexed

    if len(action_lines) >= 2:
        for idx, start in enumerate(action_lines):
            end = action_lines[idx + 1] - 1 if idx + 1 < len(action_lines) else len(lines) - 1
            desc = lines[start].strip().lstrip("#").strip()
            steps.append((start + 1, end + 1, desc))  # 1-indexed
        return steps

    # --- Estrategia 2: bloques try/except dentro de run() ---
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "run":
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, ast.Try):
                        start = child.lineno
                        end = child.end_lineno or child.lineno
                        # Extraer descripción del primer comentario o logger.info dentro del bloque
                        desc = f"Bloque línea {start}"
                        for sub in ast.walk(child):
                            if isinstance(sub, ast.Expr) and isinstance(sub.value, ast.Call):
                                if hasattr(sub.value.func, 'attr') and sub.value.func.attr == 'info':
                                    if sub.value.args and isinstance(sub.value.args[0], ast.Constant):
                                        desc = str(sub.value.args[0].value)[:60]
                                        break
                        steps.append((start, end, desc))
        if steps:
            return steps
    except Exception:
        pass

    # --- Estrategia 3: fallback — cada sentencia de run() es un paso ---
    try:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "run":
                for child in ast.iter_child_nodes(node):
                    if hasattr(child, 'lineno'):
                        start = child.lineno
                        end = getattr(child, 'end_lineno', start)
                        steps.append((start, end, f"Sentencia línea {start}"))
        if steps:
            return steps
    except Exception:
        pass

    # --- Último fallback: todo el archivo como un solo paso ---
    return [(1, len(lines), "Script completo")]


# ---------------------------------------------------------------------------
# Script wrapper que se inyecta al proceso hijo
# ---------------------------------------------------------------------------

WRAPPER_TEMPLATE = '''
import sys
import time
import builtins

_STEP_INDEX = [0]
_TOTAL_STEPS = {total_steps}
_STEP_RANGES = {step_ranges}  # list of (start_line, end_line, desc)

def _rpa_step_hook(step_n, desc):
    """Señaliza al padre que el paso N está a punto de ejecutarse y espera su comando."""
    sys.stdout.write(f"STEP_READY:{{step_n}}:{{desc}}\\n")
    sys.stdout.flush()
    while True:
        cmd = sys.stdin.readline().strip()
        if cmd == "CMD:NEXT":
            sys.stdout.write(f"STEP_START:{{step_n}}\\n")
            sys.stdout.flush()
            return True   # continuar
        elif cmd == "CMD:STOP":
            sys.stdout.write("STOPPED\\n")
            sys.stdout.flush()
            sys.exit(0)
        elif cmd == "CMD:SKIP":
            sys.stdout.write(f"STEP_SKIP:{{step_n}}\\n")
            sys.stdout.flush()
            return False  # saltar este paso
        # CMD:BACK es manejado por el padre antes de enviar CMD:NEXT

# Señal de inicio
sys.stdout.write(f"SCRIPT_READY:{{_TOTAL_STEPS}}\\n")
sys.stdout.flush()
'''


# ---------------------------------------------------------------------------
# Worker principal
# ---------------------------------------------------------------------------

class DebugWorker(QThread):
    """
    QThread que ejecuta un script RPA paso a paso.

    Señales:
        script_ready(int)           — script cargado, N pasos detectados
        step_ready(int, str)        — paso N listo para ejecutar (esperando CMD)
        step_started(int, str)      — paso N comenzó a ejecutarse
        step_done(int)              — paso N terminó OK
        step_error(int, str)        — paso N falló con mensaje
        log_line(str)               — línea de log del proceso hijo
        script_finished(bool)       — script terminó (True=OK, False=error)
    """

    script_ready   = pyqtSignal(int)          # total_steps
    step_ready     = pyqtSignal(int, str)     # step_n, desc
    step_started   = pyqtSignal(int, str)     # step_n, desc
    step_done      = pyqtSignal(int)          # step_n
    step_error     = pyqtSignal(int, str)     # step_n, error_msg
    log_line       = pyqtSignal(str)          # raw log line
    script_finished = pyqtSignal(bool)        # success

    def __init__(self, script_path: str):
        super().__init__()
        self.script_path = script_path
        self.steps: List[Tuple[int, int, str]] = []
        self.current_step = 0          # 1-indexed, 0 = no iniciado
        self.total_steps = 0

        self._process = None
        self._stopped = False
        self._paused = False
        self._auto_run = False         # True = ejecutar sin pausa (▶ Ejecutar)
        self._step_mode = False        # True = paso a paso con delay (⏯)
        self._step_delay = 1.0         # segundos entre pasos en modo step

        self._mutex = QMutex()
        self._wait_cond = QWaitCondition()

        # Para retroceso: guardamos los pasos ya ejecutados
        self._executed_steps: List[int] = []

    # ------------------------------------------------------------------
    # Control público (llamado desde el overlay / hilo UI)
    # ------------------------------------------------------------------

    def cmd_next(self):
        """Avanzar al siguiente paso."""
        self._send_cmd("CMD:NEXT")

    def cmd_stop(self):
        """Detener ejecución."""
        self._stopped = True
        self._auto_run = False
        self._step_mode = False
        self._send_cmd("CMD:STOP")

    def cmd_back(self):
        """
        Retroceder un paso: reinicia el proceso desde el inicio
        y avanza automáticamente hasta el paso anterior.
        """
        if self.current_step <= 1:
            return
        target = max(1, self.current_step - 1)
        self._restart_to_step(target)

    def cmd_restart(self):
        """Reiniciar desde el paso 1."""
        self._restart_to_step(1)

    def set_auto_run(self, enabled: bool):
        """Activar/desactivar ejecución continua (▶ Ejecutar)."""
        self._auto_run = enabled
        self._step_mode = False
        if enabled:
            self._send_cmd("CMD:NEXT")

    def set_step_mode(self, enabled: bool, delay: float = 1.0):
        """Activar/desactivar modo paso a paso automático (⏯)."""
        self._step_mode = enabled
        self._auto_run = False
        self._step_delay = delay
        if enabled:
            self._send_cmd("CMD:NEXT")

    def set_paused(self, paused: bool):
        """Pausar/reanudar ejecución continua o paso a paso."""
        self._paused = paused
        if not paused and (self._auto_run or self._step_mode):
            self._send_cmd("CMD:NEXT")

    def set_step_delay(self, delay: float):
        self._step_delay = delay

    # ------------------------------------------------------------------
    # Hilo principal
    # ------------------------------------------------------------------

    def run(self):
        """Punto de entrada del QThread."""
        self._stopped = False
        self.steps = extract_steps_from_script(self.script_path)
        self.total_steps = len(self.steps)

        if self.total_steps == 0:
            self.script_finished.emit(False)
            return

        self.script_ready.emit(self.total_steps)
        self._run_from_step(1)

    def _run_from_step(self, start_step: int):
        """Lanza el proceso hijo y gestiona la comunicación."""
        import subprocess

        self._stopped = False
        self.current_step = 0

        try:
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            env["RPA_DEBUG_MODE"] = "1"
            # Forzar utf-8 en el proceso hijo (crítico en Windows)
            env["PYTHONIOENCODING"] = "utf-8"
            
            # Asegurar que el proceso hijo encuentre los módulos del proyecto
            # Se añade la raíz del proyecto al PYTHONPATH
            project_root = str(Path(self.script_path).parent.parent.parent.resolve())
            env["PYTHONPATH"] = project_root + os.pathsep + env.get("PYTHONPATH", "")

            # Construir el script instrumentado en un archivo temporal
            instrumented = self._build_instrumented_script(start_step)
            # Usar directorio temporal del sistema (no el del script)
            tmp = tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False,
                encoding="utf-8",
                dir=tempfile.gettempdir()
            )
            tmp.write(instrumented)
            tmp.close()
            tmp_path = tmp.name

            self._process = subprocess.Popen(
                [sys.executable, "-X", "utf8", tmp_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                bufsize=1,
            )

            success = self._communicate(start_step)

        except Exception as e:
            self.log_line.emit(f"[ERROR] {e}")
            success = False
        finally:
            self.log_line.emit(f"[DEBUG] Temp script: {tmp_path}")
            # try:
            #     os.unlink(tmp_path)
            # except Exception:
            #     pass
            if self._process:
                try:
                    self._process.kill()
                except Exception:
                    pass
                self._process = None

        if not self._stopped:
            self.script_finished.emit(success)

    def _communicate(self, start_step: int) -> bool:
        """Lee stdout del proceso hijo y gestiona el protocolo."""
        proc = self._process
        step_descs = {i + 1: desc for i, (_, _, desc) in enumerate(self.steps)}
        success = True

        while True:
            if proc.poll() is not None:
                break

            line = proc.stdout.readline()
            if not line:
                break
            line = line.rstrip("\n")

            if line.startswith("SCRIPT_READY:"):
                pass  # ya emitimos script_ready antes

            elif line.startswith("STEP_READY:"):
                # Formato: STEP_READY:<n>:<desc>
                parts = line.split(":", 2)
                n = int(parts[1])
                desc = parts[2] if len(parts) > 2 else step_descs.get(n, f"Paso {n}")
                self.current_step = n
                self.step_ready.emit(n, desc)

                # Decidir si avanzar automáticamente o esperar
                if self._stopped:
                    self._send_cmd("CMD:STOP")
                elif self._auto_run and not self._paused:
                    self._send_cmd("CMD:NEXT")
                elif self._step_mode and not self._paused:
                    time.sleep(self._step_delay)
                    if not self._stopped and not self._paused:
                        self._send_cmd("CMD:NEXT")
                # else: esperar cmd_next() manual

            elif line.startswith("STEP_START:"):
                parts = line.split(":", 1)
                n = int(parts[1])
                desc = step_descs.get(n, f"Paso {n}")
                self.step_started.emit(n, desc)

            elif line.startswith("STEP_DONE:"):
                parts = line.split(":", 1)
                n = int(parts[1])
                self.step_done.emit(n)
                if n not in self._executed_steps:
                    self._executed_steps.append(n)

            elif line.startswith("STEP_ERROR:"):
                parts = line.split(":", 2)
                n = int(parts[1])
                msg = parts[2] if len(parts) > 2 else "Error desconocido"
                self.step_error.emit(n, msg)
                success = False

            elif line == "STOPPED":
                break

            else:
                self.log_line.emit(line)

        return success

    def _send_cmd(self, cmd: str):
        """Envía un comando al proceso hijo por stdin."""
        if self._process and self._process.poll() is None:
            try:
                self._process.stdin.write(cmd + "\n")
                self._process.stdin.flush()
            except Exception:
                pass

    def _restart_to_step(self, target_step: int):
        """Mata el proceso actual y relanza desde target_step."""
        self._stopped = True
        if self._process:
            try:
                self._process.kill()
            except Exception:
                pass
        # Relanzar en el mismo hilo (llamado desde el hilo UI via señal)
        # Usamos un nuevo QThread para no bloquear
        self._stopped = False
        self._executed_steps = []
        self._run_from_step(target_step)

    def _build_instrumented_script(self, start_step: int) -> str:
        """
        Construye el script instrumentado.

        Estrategia:
          1. El bloque del hook (_rpa_step_hook + señal SCRIPT_READY) se PREPENDE
             al inicio del archivo como un bloque de texto plano (sin indentación).
          2. Las llamadas _rpa_step_hook(n) se insertan línea a línea, de atrás
             hacia adelante, respetando la indentación del bloque de acción.
          3. Inmediatamente después de cada llamada al hook se emite STEP_DONE.

        Esto evita InsertionError porque el hook nunca se inserta dentro de
        un bloque indentado (clase, función, try/except).
        """
        import re

        # --- 1. Leer el script original ---
        try:
            with open(self.script_path, "r", encoding="utf-8-sig") as f:
                original = f.read()
        except UnicodeDecodeError:
            with open(self.script_path, "r", encoding="latin-1") as f:
                original = f.read()

        steps = self.steps
        total = len(steps)

        # --- 2. Construir el bloque del hook (siempre a nivel módulo, sin indent) ---
        step_descs_repr = repr({i + 1: desc for i, (_, _, desc) in enumerate(steps)})

        hook_block = (
            "# -*- coding: utf-8 -*-\n"
            "# [RPA DEBUGGER — bloque de instrumentación]\n"
            "import sys as _sys\n"
            "\n"
            f"_RPA_STEP_DESCS = {step_descs_repr}\n"
            "\n"
            "def _rpa_step_hook(step_n):\n"
            "    desc = _RPA_STEP_DESCS.get(step_n, f'Paso {step_n}')\n"
            "    _sys.stdout.write(f'STEP_READY:{step_n}:' + desc + '\\n')\n"
            "    _sys.stdout.flush()\n"
            "    while True:\n"
            "        cmd = _sys.stdin.readline().strip()\n"
            "        if cmd == 'CMD:NEXT':\n"
            f"            _sys.stdout.write(f'STEP_START:{{step_n}}\\n')\n"
            "            _sys.stdout.flush()\n"
            "            return\n"
            "        elif cmd == 'CMD:STOP':\n"
            "            _sys.stdout.write('STOPPED\\n')\n"
            "            _sys.stdout.flush()\n"
            "            _sys.exit(0)\n"
            "\n"
            f"_sys.stdout.write('SCRIPT_READY:{total}\\n')\n"
            "_sys.stdout.flush()\n"
            "# [fin bloque instrumentación]\n"
            "\n"
        )

        # --- 3. Dividir el original en líneas (preservando finales de línea) ---
        lines = original.splitlines(keepends=True)
        # Asegurar que cada línea termina en \n
        lines = [l if l.endswith("\n") else l + "\n" for l in lines]

        # --- 4. Insertar llamadas al hook de atrás hacia adelante ---
        # Esto evita que las inserciones anteriores desplacen los índices posteriores.
        for i, (start_1, end_1, desc) in reversed(list(enumerate(steps))):
            step_n = i + 1
            if step_n < start_step:
                continue  # saltar pasos anteriores al punto de inicio

            # Índice 0-based de la línea donde empieza el bloque
            target_idx = start_1 - 1  # 0-indexed
            if target_idx < 0 or target_idx >= len(lines):
                continue

            # Detectar indentación correcta buscando la primera línea de código
            # Esto evita errores cuando el paso comienza con un comentario mal indentado
            indent_str = ""
            found_indent = False
            
            # Convertir end_1 (1-based, inclusive) a índice 0-based tope para búsqueda
            # Nota: end_1 puede ser el final del archivo
            end_search_idx = min(end_1, len(lines))
            
            for k in range(target_idx, end_search_idx):
                line_k = lines[k]
                stripped_k = line_k.lstrip()
                # Si tiene contenido y NO es un comentario
                if stripped_k and not stripped_k.startswith("#"):
                    indent = len(line_k) - len(stripped_k)
                    indent_str = " " * indent
                    found_indent = True
                    break
            
            if not found_indent:
                # Fallback: usar la indentación de la línea target aunque sea comentario
                target_line = lines[target_idx]
                stripped = target_line.lstrip()
                indent = len(target_line) - len(stripped)
                indent_str = " " * indent

            # Línea de llamada al hook + STEP_DONE inmediatamente después
            hook_call = (
                f"{indent_str}_rpa_step_hook({step_n})\n"
                f"{indent_str}_sys.stdout.write('STEP_DONE:{step_n}\\n'); _sys.stdout.flush()\n"
            )
            lines.insert(target_idx, hook_call)

        # --- 5. Ensamblar: hook_block + líneas instrumentadas ---
        final_source = hook_block + "".join(lines)
        return final_source

