"""
Servicio interactivo del Bot de Telegram para Atrys RPA.
Punto de entrada principal y fachada de compatibilidad que delega en `rpa_framework/telegram_bot/`.
"""
import os
import sys

if sys.stdout is not None:
    try:
        sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
    except Exception:
        pass
if sys.stderr is not None:
    try:
        sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)
    except Exception:
        pass

from datetime import datetime
from pathlib import Path
import traceback

# Forzar el directorio raíz de rpa_framework
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram_bot import (
    TOKEN,
    CONFIG_DIR,
    LOG_DIR,
    DEBUG_LOG,
    UPDATE_FILE,
    STATE_FILE,
    STOP_SIGNAL,
    CMD_SIGNAL,
    _lock_socket,
    _lock_file,
    active_executor,
    executor_thread,
    tray_manager,
    _pacs_proc,
    _pacs_validating_now,
    _last_loop_params,
    check_single_instance,
    get_last_update_id,
    save_last_update_id,
    mostrar_notificacion_tray,
    set_execution_state,
    detener_ejecucion_actual,
    monitor_stop_signal,
    run_workflow,
    run_workflow_headless,
    is_any_workflow_running,
    get_last_loop_params,
    start_workflow_async,
    cerrar_chrome_rpa,
    get_current_running_name,
    pedir_confirmacion_interrupcion,
    forzar_ejecucion_workflow,
    rehabilitar_ultimo_registro,
    obtener_ultimos_errores,
    marcar_registro_en_proceso,
    mostrar_menu_revalidar,
    get_pacs_daily_status,
    check_pacs_validated_today,
    trigger_pacs_validation_process,
    consultar_estado_pacs,
    obtener_ultimo_registro_casos_pendientes,
    enviar_reporte_excel_por_periodo,
    capturar_pantalla_en_vivo,
    obtener_datos_diagnostico,
    enviar_resumen_estado_texto,
    enviar_estado_actual,
    iniciar_live_stream_telegram,
    detener_live_stream_telegram,
    run_llm_daily_checker,
    run_pacs_validation_scheduler,
    procesar_callback_query,
    procesar_mensaje_texto,
    telegram_polling_loop,
)
import telegram_bot.bot_state as _bot_state


def __getattr__(name):
    """Mantiene sincronizadas las lecturas de variables de estado mutables desde `bot_state`."""
    if hasattr(_bot_state, name):
        return getattr(_bot_state, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


if __name__ == "__main__":
    log_dir = Path(__file__).resolve().parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    debug_log = log_dir / "service_debug.log"
    with open(debug_log, "a", encoding="utf-8") as f:
        f.write(f"\n--- Iniciando servicio bot a las {datetime.now()} ---\n")
    try:
        if not check_single_instance():
            with open(debug_log, "a", encoding="utf-8") as f:
                f.write("Instancia unica bloqueada (puerto 28374 ya en uso). Saliendo.\n")
            sys.exit(0)
        telegram_polling_loop()
    except Exception as e:
        with open(debug_log, "a", encoding="utf-8") as f:
            f.write(f"Excepcion fatal: {e}\n{traceback.format_exc()}\n")
        raise
