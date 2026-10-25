"""
Estado global compartido, bloqueo de instancia única y rutas de configuración del servicio Bot de Telegram.
"""
import json
import os
import socket
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Directorio raíz de rpa_framework (un nivel arriba de telegram_bot/)
RPA_ROOT = Path(__file__).resolve().parent.parent

env_parent = RPA_ROOT.parent / ".env"
if env_parent.exists():
    load_dotenv(dotenv_path=env_parent)
else:
    load_dotenv()

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# Rutas de configuración y logs
CONFIG_DIR = RPA_ROOT / "config"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR = RPA_ROOT.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
DEBUG_LOG = LOG_DIR / "service_debug.log"
UPDATE_FILE = CONFIG_DIR / "telegram_last_update.json"
STATE_FILE = CONFIG_DIR / "execution_state.json"
STOP_SIGNAL = CONFIG_DIR / "stop_signal.txt"
CMD_SIGNAL = CONFIG_DIR / "command_signal.json"

_lock_socket = None
_lock_file = CONFIG_DIR / "servicio_bot.lock"

# Estado mutable compartido entre módulos del bot
active_executor = None
executor_thread = None
tray_manager = None
_pacs_proc = None
_pacs_validating_now = False
_last_loop_params = {"tipo": "count", "valor": "10"}


def check_single_instance(port=28374):
    global _lock_socket
    try:
        _lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _lock_socket.bind(("127.0.0.1", port))
        _lock_socket.listen(1)
    except socket.error:
        _lock_socket = None
        return False

    try:
        _lock_file.parent.mkdir(exist_ok=True)
        with open(_lock_file, "w", encoding="utf-8") as f:
            json.dump({"pid": os.getpid(), "started_at": datetime.now().isoformat()}, f)
    except Exception:
        pass

    return True


def get_last_update_id():
    if UPDATE_FILE.exists():
        try:
            with open(UPDATE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("last_update_id", 0)
        except Exception:
            return 0
    return 0


def save_last_update_id(update_id):
    with open(UPDATE_FILE, 'w', encoding='utf-8') as f:
        json.dump({"last_update_id": update_id}, f)


def mostrar_notificacion_tray(mensaje: str, titulo: str = "🤖 Bot RPA - Atrys"):
    """Envía una alerta o burbuja emergente al icono de la bandeja del sistema."""
    global tray_manager
    if tray_manager:
        try:
            tray_manager.notify(mensaje, titulo)
            tray_manager.update_icon()
        except Exception as e:
            print(f"Error mostrando alerta tray: {e}")


def set_execution_state(is_running, workflow_name="", is_loop=False):
    state = {
        "is_running": is_running,
        "workflow": workflow_name,
        "is_loop": is_loop,
        "updated_at": time.time()
    }
    try:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f)
    except Exception as e:
        print(f"Error guardando estado: {e}")

    try:
        from utils.notificador_resumen import registrar_ejecucion_workflow
        registrar_ejecucion_workflow(workflow_name, status="running" if is_running else "finished")
    except Exception:
        pass

    global tray_manager
    if tray_manager:
        try:
            if is_running and workflow_name:
                tray_manager.notify(f"Iniciando workflow: {workflow_name}", "🚀 Bot RPA - Flujo Iniciado")
            elif not is_running:
                tray_manager.notify("La ejecución del flujo ha finalizado.", "✅ Bot RPA - Flujo Completado")
            tray_manager.update_icon()
        except Exception:
            pass


def is_any_workflow_running():
    """Retorna True si hay una ejecución activa local o via execution_state.json."""
    global active_executor
    if active_executor is not None:
        return True
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get("is_running", False):
                    if time.time() - data.get("updated_at", 0) < 900:
                        return True
        except Exception:
            pass
    return False


def get_last_loop_params():
    global _last_loop_params
    return _last_loop_params


def get_current_running_name():
    """Obtiene el nombre descriptivo del workflow o proceso actualmente en ejecución."""
    global active_executor, _pacs_validating_now
    if _pacs_validating_now:
        return "Validación PACS"
    if active_executor and hasattr(active_executor, 'workflow') and active_executor.workflow:
        return active_executor.workflow.name or "Workflow en curso"
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get("is_running"):
                    return data.get("workflow", "Workflow en curso")
        except Exception:
            pass
    return "Workflow en curso"
