# -*- coding: utf-8 -*-
"""
auto_config_store.py
====================
Persistencia de configuración de autoverificación diaria e historial de los últimos 5 días
para modelos LLM. Extraído de utils/llm_auto_manager.py.
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Directorios de configuración y logs (este archivo vive en rpa_framework/utils/llm/)
UTILS_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = UTILS_DIR.parent.parent
CONFIG_DIR = ROOT_DIR / "rpa_framework" / "config"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = UTILS_DIR / "llm_config.py"
ENV_FILE = ROOT_DIR / ".env"
AUTO_CONFIG_FILE = CONFIG_DIR / "llm_auto_config.json"
LOG_HISTORIAL_FILE = CONFIG_DIR / "llm_verification_log.json"
TIMESTAMP_FILE = UTILS_DIR / "last_llm_update.txt"

# Cargar variables de entorno
load_dotenv(ENV_FILE, override=True)


def get_default_config() -> dict:
    return {
        "enabled": True,
        "frequency": "diario_24h",  # 'diario_24h' o 'hora_fija'
        "scheduled_hour": 3,         # 03:00 AM
        "auto_apply": True,
        "last_run_timestamp": "",
        "last_status": "Sin ejecuciones aún"
    }


def load_auto_config() -> dict:
    """Carga la configuración de verificación automática desde JSON."""
    cfg = get_default_config()
    if AUTO_CONFIG_FILE.exists():
        try:
            with open(AUTO_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                cfg.update(data)
        except Exception as e:
            print(f"[llm_auto_manager] Error leyendo auto_config: {e}")
    return cfg


def save_auto_config(cfg: dict) -> bool:
    """Guarda la configuración de autoverificación en JSON."""
    try:
        with open(AUTO_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[llm_auto_manager] Error guardando auto_config: {e}")
        return False


def load_verification_log() -> list:
    """
    Carga el historial de verificaciones de los últimos 5 días.
    Filtra y elimina automáticamente los registros de más de 5 días de antigüedad.
    """
    if not LOG_HISTORIAL_FILE.exists():
        return []

    try:
        with open(LOG_HISTORIAL_FILE, "r", encoding="utf-8") as f:
            logs = json.load(f)
    except Exception as e:
        print(f"[llm_auto_manager] Error leyendo log de historial: {e}")
        return []

    # Filtrar solo los últimos 5 días
    hace_5_dias = datetime.now() - timedelta(days=5)
    logs_validos = []
    
    for entry in logs:
        ts_str = entry.get("timestamp", "")
        try:
            # Intentar parsear ISO format o YYYY-MM-DD HH:MM:SS
            if "T" in ts_str:
                dt = datetime.fromisoformat(ts_str)
            else:
                dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            
            if dt >= hace_5_dias:
                logs_validos.append(entry)
        except Exception:
            # Si no se puede parsear fecha, conservar si es reciente
            logs_validos.append(entry)

    # Si se purgaron antiguos, actualizar el archivo JSON
    if len(logs_validos) != len(logs):
        save_verification_logs(logs_validos)

    # Ordenar más recientes primero
    logs_validos.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return logs_validos


def save_verification_logs(logs: list) -> bool:
    """Escribe la lista completa de logs en el archivo JSON."""
    try:
        with open(LOG_HISTORIAL_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[llm_auto_manager] Error guardando historial: {e}")
        return False


def add_verification_log(status: str, models_checked: int, models_online: int,
                         models_replaced: int, details: str, log_messages: list = None) -> dict:
    """
    Agrega una entrada al historial de los últimos 5 días y depura automáticamente
    las entradas antiguas.
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = {
        "timestamp": now_str,
        "status": status,  # "✅ Éxito", "🔄 Reemplazo Realizado", "⚠️ Sin Cambios", "❌ Fallo"
        "models_checked": models_checked,
        "models_online": models_online,
        "models_replaced": models_replaced,
        "details": details,
        "log_messages": log_messages or []
    }

    logs = load_verification_log()
    logs.insert(0, entry)  # Insertar al inicio

    # Purgar manteniendo solo registros dentro de los últimos 5 días
    hace_5_dias = datetime.now() - timedelta(days=5)
    logs_filtrados = []
    for l in logs:
        ts_str = l.get("timestamp", "")
        try:
            dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            if dt >= hace_5_dias:
                logs_filtrados.append(l)
        except Exception:
            logs_filtrados.append(l)

    save_verification_logs(logs_filtrados)

    # Actualizar también timestamp de última ejecución en config
    cfg = load_auto_config()
    cfg["last_run_timestamp"] = now_str
    cfg["last_status"] = f"{status} ({models_online}/{models_checked} online)"
    save_auto_config(cfg)

    # Guardar en TIMESTAMP_FILE para retrocompatibilidad
    try:
        with open(TIMESTAMP_FILE, "w", encoding="utf-8") as f:
            f.write(datetime.now().isoformat())
    except Exception:
        pass

    return entry


def should_run_auto_verification(force=False) -> tuple[bool, str]:
    """
    Evalúa si corresponde ejecutar la verificación periódica según la configuración activa.
    Retorna (should_run: bool, reason: str).
    """
    if force:
        return True, "Ejecución manual forzada"

    cfg = load_auto_config()
    if not cfg.get("enabled", True):
        return False, "Autoverificación desactivada en configuración"

    last_ts_str = cfg.get("last_run_timestamp", "")
    if not last_ts_str:
        return True, "Primera ejecución de autoverificación"

    try:
        if "T" in last_ts_str:
            last_run = datetime.fromisoformat(last_ts_str)
        else:
            last_run = datetime.strptime(last_ts_str, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return True, "No se pudo interpretar última fecha de ejecución"

    now = datetime.now()
    freq = cfg.get("frequency", "diario_24h")

    if freq == "diario_24h":
        elapsed = now - last_run
        if elapsed >= timedelta(hours=24):
            return True, f"Han transcurrido {elapsed.total_seconds()/3600:.1f}h (>= 24h)"
        return False, f"Verificación reciente ({elapsed.total_seconds()/3600:.1f}h transcurridas)"

    elif freq in ["cada_6h", "6h", "cada_6_horas"]:
        elapsed = now - last_run
        if elapsed >= timedelta(hours=6):
            return True, f"Han transcurrido {elapsed.total_seconds()/3600:.1f}h (>= 6h)"
        return False, f"Verificación reciente ({elapsed.total_seconds()/3600:.1f}h transcurridas)"

    elif freq == "hora_fija":
        target_hour = cfg.get("scheduled_hour", 3)
        # Si hoy aún no ha corrido y ya pasó o estamos en la hora objetivo
        if last_run.date() < now.date() and now.hour >= target_hour:
            return True, f"Hora programada alcanzada ({now.hour}:00 >= {target_hour}:00)"
        return False, f"Programado para las {target_hour}:00 (Última: {last_run.strftime('%Y-%m-%d %H:%M')})"

    return False, "Frecuencia no definida"


def get_llm_status_summary() -> str:
    """
    Retorna un texto resumido de 1-2 líneas sobre el estado actual de los modelos LLM
    apto para tooltips en la bandeja de sistema y menús contextuales.
    """
    try:
        sys.path.insert(0, str(ROOT_DIR))
        import rpa_framework.utils.llm_config as llm_cfg
        models = list(llm_cfg.BASE_LLM_MODELS)
        total = len(models)
    except Exception:
        models = []
        total = 0

    logs = load_verification_log()
    if not logs:
        return f"🤖 LLM: {total} modelos configurados (Sin verif. reciente)"

    last_log = logs[0]
    ts = last_log.get("timestamp", "Desconocido")
    online = last_log.get("models_online", total)
    checked = last_log.get("models_checked", total)
    replaced = last_log.get("models_replaced", 0)

    # Formatear fecha corta HH:MM
    try:
        dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        time_str = dt.strftime("%d/%m %H:%M")
    except Exception:
        time_str = ts

    if replaced > 0:
        return f"🤖 LLM: {online}/{checked} activos ({replaced} reemplazado{'s' if replaced>1 else ''} {time_str})"
    elif online == checked and checked > 0:
        return f"🤖 LLM: {online}/{checked} Online ✅ ({time_str})"
    else:
        return f"🤖 LLM: {online}/{checked} activos ({time_str})"
