"""
Paquete modular de reportes y resúmenes automáticos por Telegram.
"""
from .summary_queries import (
    HORA_INICIO_HOURLY,
    HORA_FIN_HOURLY,
    HORA_DAILY,
    DIAS_SEMANA_VALIDOS,
    BASE_DIR,
    PAUSE_FILE,
    LOG_FILE,
    LAST_WORKFLOW_FILE,
    EXECUTION_STATE_FILE,
    registrar_ejecucion_workflow,
    se_ejecuto_workflow_ultimos_minutos,
    notificaciones_pausadas,
    pausar_notificaciones,
    reanudar_notificaciones,
    get_log_tail,
    get_db_connection,
    obtener_datos,
    is_addendum,
    is_ya_ingresado,
    is_pending_approval,
    is_success_standard,
    is_success,
    is_error,
    is_in_progress,
)
from .summary_charts import (
    generar_texto_resumen_hourly,
    generar_dashboard_ejecutivo,
    generar_tabla_imagen,
    generar_grafico_barras,
    generar_texto_resumen_simple,
)
from .summary_sender import (
    enviar_reporte_hourly,
    enviar_reporte_daily,
    notificar_inicio_loop,
    notificar_fin_loop_con_resumen,
    main,
)
