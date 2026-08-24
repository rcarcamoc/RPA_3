import os
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')
import json
import time
import logging
from pathlib import Path
import psutil

# Intentar importar enviar_alerta_todos desde telegram_manager
try:
    from utils.telegram_manager import enviar_alerta_todos
except ImportError:
    try:
        from telegram_manager import enviar_alerta_todos
    except ImportError:
        enviar_alerta_todos = None

logger = logging.getLogger("BatteryMonitor")

# Ruta de configuración para guardar el estado previo de la batería
CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
STATE_FILE = CONFIG_DIR / "battery_state.json"

def get_battery_status():
    """
    Obtiene el estado actual de la batería mediante psutil.
    Retorna un diccionario con percent, power_plugged, secsleft o None si no hay batería.
    """
    try:
        battery = psutil.sensors_battery()
        if battery is None:
            return None
        return {
            "percent": float(battery.percent),
            "power_plugged": bool(battery.power_plugged) if battery.power_plugged is not None else False,
            "secsleft": int(battery.secsleft) if battery.secsleft is not None else -1
        }
    except Exception as e:
        logger.error(f"Error obteniendo sensores de batería: {e}")
        return None

def load_battery_state():
    """Carga el último estado guardado de la batería."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Error leyendo {STATE_FILE}: {e}")
    return {}

def save_battery_state(state):
    """Guarda el estado actual de la batería."""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error guardando {STATE_FILE}: {e}")

def check_battery_and_notify():
    """
    Verifica el estado de la batería y envía una alerta por Telegram si:
    - El porcentaje actual baje del 50% (< 50)
    - La lectura anterior era superior (>= 50)
    """
    status = get_battery_status()
    if status is None:
        logger.info("No se detectó sensor de batería (PC de escritorio o sin batería).")
        return

    current_percent = status["percent"]
    power_plugged = status["power_plugged"]
    
    state = load_battery_state()
    previous_percent = state.get("last_percent")

    logger.debug(f"[Battery Check] Actual: {current_percent}%, Previo: {previous_percent}%, Plugged: {power_plugged}")

    # Si es la primera ejecución y no hay previo registrado, inicializarlo
    if previous_percent is None:
        previous_percent = current_percent

    # Regla: gatillar alerta cuando baje de 50% y la lectura anterior era >= 50%
    if current_percent < 50.0 and previous_percent >= 50.0:
        plugged_str = "Conectado a la corriente 🟢" if power_plugged else "Desconectado (Batería) 🔴"
        mensaje = (
            "🪫 <b>ALERTA DE BATERÍA BAJA (&lt; 50%)</b>\n\n"
            "⚠️ La batería del equipo ha bajado del 50%.\n\n"
            f"🔋 <b>Nivel Actual:</b> {current_percent:.1f}%\n"
            f"📊 <b>Lectura Anterior:</b> {previous_percent:.1f}%\n"
            f"🔌 <b>Alimentación:</b> {plugged_str}\n\n"
            "💡 <i>Se recomienda conectar el equipo a la corriente eléctrica.</i>"
        )
        print(f"⚠️ Alerta de batería baja enviada a Telegram: {current_percent}% (Previo: {previous_percent}%)")
        if enviar_alerta_todos:
            try:
                enviar_alerta_todos(mensaje)
            except Exception as e:
                logger.error(f"Error enviando alerta de batería por Telegram: {e}")
        else:
            logger.warning("enviar_alerta_todos no está disponible para notificar.")

    # Actualizar estado guardado
    state["last_percent"] = current_percent
    state["power_plugged"] = power_plugged
    state["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save_battery_state(state)

def obtener_estado_bateria_msg():
    """Genera un mensaje con el estado de la batería para comandos de Telegram."""
    status = get_battery_status()
    if status is None:
        return "🖥️ Este equipo no posee batería o funciona como PC de escritorio sin sensor de batería."

    percent = status["percent"]
    plugged = status["power_plugged"]
    secsleft = status["secsleft"]

    plugged_str = "Conectado a corriente 🟢" if plugged else "Usando batería 🔴"
    
    if secsleft > 0:
        hrs = secsleft // 3600
        mins = (secsleft % 3600) // 60
        secs_str = f"{hrs}h {mins}m restantes"
    elif plugged:
        secs_str = "Cargando / Alimentación AC"
    else:
        secs_str = "Calculando..."

    emoji_bat = "🔋" if percent >= 50 else ("🪫" if percent > 20 else "⚠️🪫")

    return (
        f"{emoji_bat} <b>ESTADO DE LA BATERÍA DEL PC</b>\n\n"
        f"• <b>Nivel de carga:</b> {percent:.1f}%\n"
        f"• <b>Estado:</b> {plugged_str}\n"
        f"• <b>Estimación:</b> {secs_str}"
    )

def run_battery_monitor_loop(interval_seconds=600):
    """Bucle continuo para monitoreo de batería (por defecto cada 10 min = 600 s)."""
    print(f"🔋 Iniciando monitor de batería del PC (revisión cada {interval_seconds // 60} minutos)...")
    while True:
        try:
            check_battery_and_notify()
        except Exception as e:
            print(f"[Battery Monitor Error] {e}")
        time.sleep(interval_seconds)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Probando lectura de batería...")
    print(obtener_estado_bateria_msg())
    check_battery_and_notify()
