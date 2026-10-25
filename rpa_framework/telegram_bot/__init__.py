"""
Paquete modular del Servicio Bot de Telegram (RPA_3).
"""
from .bot_state import (
    RPA_ROOT,
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
    is_any_workflow_running,
    get_last_loop_params,
    get_current_running_name,
)
from .pacs_monitor import (
    get_pacs_daily_status,
    check_pacs_validated_today,
    trigger_pacs_validation_process,
    consultar_estado_pacs,
    run_pacs_validation_scheduler,
)
from .db_operations import (
    rehabilitar_ultimo_registro,
    obtener_ultimos_errores,
    marcar_registro_en_proceso,
    mostrar_menu_revalidar,
    obtener_ultimo_registro_casos_pendientes,
    enviar_reporte_excel_por_periodo,
)
from .workflow_runner import (
    detener_ejecucion_actual,
    monitor_stop_signal,
    run_workflow,
    run_workflow_headless,
    start_workflow_async,
    cerrar_chrome_rpa,
    pedir_confirmacion_interrupcion,
    forzar_ejecucion_workflow,
    run_llm_daily_checker,
)
from .live_stream import (
    capturar_pantalla_en_vivo,
    obtener_datos_diagnostico,
    enviar_resumen_estado_texto,
    enviar_estado_actual,
    iniciar_live_stream_telegram,
    detener_live_stream_telegram,
)
from .router import (
    procesar_callback_query,
    procesar_mensaje_texto,
    telegram_polling_loop,
)
