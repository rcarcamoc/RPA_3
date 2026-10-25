"""
Generadores de Teclados Inline para Menús y Submenús de Telegram.
"""


def get_menu_principal_markup():
    """Panel Principal con accesos rápidos directos y categorías operativas."""
    return {
        "inline_keyboard": [
            [{"text": "🔴 Transmitir pantalla (Stream)", "callback_data": "cmd_stream_menu"}],
            [{"text": "🚀 Iniciar ejecuciones", "callback_data": "sec_ejecucion"}],
            [{"text": "📊 Reportes y consultas", "callback_data": "sec_reportes"}],
            [{"text": "🛠️ Herramientas del sistema", "callback_data": "sec_sistema"}],
            [{"text": "🔍 Contar casos directo en RIS", "callback_data": "cmd_casos"}],
            [{"text": "🛑 Detener todo (Emergencia)", "callback_data": "cmd_detener"}]
        ]
    }


def get_menu_ejecucion_markup():
    """Submenú Iniciar ejecuciones."""
    return {
        "inline_keyboard": [
            [{"text": "⚡ Flujo Optimizado V2 (Pipeline Rápido)", "callback_data": "sec_v2"}],
            [{"text": "▶️ Ejecutar 1 vez (Flujo completo V1)", "callback_data": "cmd_inicio"}],
            [{"text": "📋 Ejecutar solo carga (Integra)", "callback_data": "cmd_pega_integra"}],
            [{"text": "🔄 Reintentar un caso con error", "callback_data": "cmd_revalidar"}],
            [{"text": "🔁 Ejecución con repeticiones (V1)", "callback_data": "cmd_loop_menu"}],
            [{"text": "🛑 Detener proceso actual", "callback_data": "cmd_detener"}],
            [{"text": "🏠 Menú Principal", "callback_data": "menu_principal"}]
        ]
    }


def get_menu_v2_markup():
    """Submenú Flujo Optimizado V2."""
    return {
        "inline_keyboard": [
            [{"text": "▶️ Ejecutar 1 vez (Sub_work V2)", "callback_data": "cmd_inicio_v2"}],
            [{"text": "🔁 Bucle Continuo V2 (loop_v2)", "callback_data": "cmd_loop_v2_menu"}],
            [{"text": "📋 Solo PACS V2", "callback_data": "cmd_pacs_v2"}],
            [
                {"text": "⬅️ Volver a Ejecuciones", "callback_data": "sec_ejecucion"},
                {"text": "🏠 Menú Principal", "callback_data": "menu_principal"}
            ]
        ]
    }


def get_menu_loop_v2_markup():
    """Submenú Bucle Continuo V2 con repeticiones."""
    return {
        "inline_keyboard": [
            [{"text": "⚡ 5 veces", "callback_data": "loop_v2_count_5"}, {"text": "⏱️ Durante 1 hora", "callback_data": "loop_v2_timed_1.0"}],
            [{"text": "⏱️ Durante 2 horas", "callback_data": "loop_v2_timed_2.0"}, {"text": "🔄 Continuo (Sin parar)", "callback_data": "loop_v2_infinite"}],
            [
                {"text": "⬅️ Volver a Flujo V2", "callback_data": "sec_v2"},
                {"text": "🏠 Menú Principal", "callback_data": "menu_principal"}
            ]
        ]
    }


def get_menu_revalidar_markup(registros):
    """
    Genera el teclado inline para seleccionar cuál de los registros en error
    debe quedar en estado 'En Proceso' y reprocesarse en PACS.
    """
    keyboard = []
    for reg in registros:
        r_id = reg.get("id")
        doc = str(reg.get("numero_documento") or "--").strip()
        btn_text = f"🔄 Reprocesar #{r_id} (Doc: {doc})"
        keyboard.append([{"text": btn_text, "callback_data": f"reproc_pacs_{r_id}"}])

    keyboard.append([
        {"text": "⬅️ Volver a Ejecuciones", "callback_data": "sec_ejecucion"},
        {"text": "🏠 Menú Principal", "callback_data": "menu_principal"}
    ])
    return {"inline_keyboard": keyboard}


def get_menu_post_revalidar_markup(registro_id):
    """Submenú ofrecido tras marcar un registro como 'En Proceso'."""
    return {
        "inline_keyboard": [
            [{"text": "🔄 Reprocesar en PACS (Solo Carga)", "callback_data": f"reproc_pacs_{registro_id}"}],
            [
                {"text": "⚡ Ejecutar con V2 (Rápido)", "callback_data": "cmd_inicio_v2"},
                {"text": "▶️ Ejecutar con V1", "callback_data": "cmd_inicio"}
            ],
            [{"text": "📋 Ejecutar solo carga (Integra)", "callback_data": "cmd_pega_integra"}],
            [{"text": "🔄 Ver otros errores", "callback_data": "cmd_revalidar"}],
            [
                {"text": "⬅️ Volver a Ejecuciones", "callback_data": "sec_ejecucion"},
                {"text": "🏠 Menú Principal", "callback_data": "menu_principal"}
            ]
        ]
    }


def get_menu_loop_markup():
    """Submenú Ejecución con repeticiones."""
    return {
        "inline_keyboard": [
            [{"text": "⚡ 5 veces", "callback_data": "loop_count_5"}, {"text": "⏱️ Durante 1 hora", "callback_data": "loop_timed_1.0"}],
            [{"text": "⏱️ Durante 2 horas", "callback_data": "loop_timed_2.0"}, {"text": "🔄 Continuo (Sin parar)", "callback_data": "loop_infinite"}],
            [
                {"text": "⬅️ Volver a Ejecuciones", "callback_data": "sec_ejecucion"},
                {"text": "🏠 Menú Principal", "callback_data": "menu_principal"}
            ]
        ]
    }


def get_menu_reportes_markup():
    """Submenú Reportes y Consultas."""
    return {
        "inline_keyboard": [
            [
                {"text": "📑 Resumen del día", "callback_data": "cmd_resumen"},
                {"text": "📥 Descargar reporte Excel", "callback_data": "cmd_menu_excel"}
            ],
            [
                {"text": "🔍 Contar casos directo en RIS", "callback_data": "cmd_casos"},
                {"text": "🏥 Ver estado de PACS", "callback_data": "cmd_estado_pacs"}
            ],
            [{"text": "🏠 Menú Principal", "callback_data": "menu_principal"}]
        ]
    }


def get_menu_periodo_excel_markup():
    """Submenú de Selección de Periodo para Reporte Excel."""
    return {
        "inline_keyboard": [
            [{"text": "📅 Día de hoy", "callback_data": "rep_excel_hoy"}],
            [{"text": "🗓️ Últimos 7 días", "callback_data": "rep_excel_7d"}],
            [{"text": "📆 Mes actual", "callback_data": "rep_excel_mes"}],
            [
                {"text": "⬅️ Volver a Reportes", "callback_data": "sec_reportes"},
                {"text": "🏠 Menú Principal", "callback_data": "menu_principal"}
            ]
        ]
    }


def get_menu_sistema_markup():
    """Submenú Herramientas del sistema."""
    return {
        "inline_keyboard": [
            [{"text": "📸 Foto de pantalla actual", "callback_data": "cmd_estado_actual"}],
            [{"text": "🩺 Probar conexión PACS ahora", "callback_data": "cmd_validar_pacs"}],
            [{"text": "📜 Ver últimas actividades (Logs)", "callback_data": "cmd_ver_log"}],
            [{"text": "🔋 Nivel de batería y energía", "callback_data": "cmd_bateria"}],
            [{"text": "🔔 Pausar o activar alertas", "callback_data": "sec_notificaciones"}],
            [{"text": "🏠 Menú Principal", "callback_data": "menu_principal"}]
        ]
    }


def get_live_status_markup(stream_activo=False):
    """Teclado inline adjunto a la foto o diagnóstico en vivo."""
    if stream_activo:
        stream_btn = {"text": "🛑 Detener Transmisión", "callback_data": "cmd_detener_stream"}
    else:
        stream_btn = {"text": "🔴 Transmitir pantalla (Stream)", "callback_data": "cmd_iniciar_stream"}

    return {
        "inline_keyboard": [
            [stream_btn],
            [
                {"text": "🔄 Actualizar foto", "callback_data": "cmd_estado_actual"},
                {"text": "🏠 Menú Principal", "callback_data": "menu_principal"}
            ]
        ]
    }


def get_menu_stream_markup(stream_activo=False, tiempo_str="00:00"):
    """Submenú de control de Transmisión de Pantalla (Live Stream)."""
    if stream_activo:
        return {
            "inline_keyboard": [
                [{"text": "🛑 Detener Transmisión de Pantalla", "callback_data": "cmd_detener_stream"}],
                [{"text": "📸 Foto de pantalla actual", "callback_data": "cmd_estado_actual"}],
                [
                    {"text": "⬅️ Volver a Herramientas", "callback_data": "sec_sistema"},
                    {"text": "🏠 Menú Principal", "callback_data": "menu_principal"}
                ]
            ]
        }
    else:
        return {
            "inline_keyboard": [
                [{"text": "🔴 Iniciar transmisión (10 min / Fin de flujo)", "callback_data": "cmd_iniciar_stream_600"}],
                [{"text": "🔴 Iniciar transmisión continua", "callback_data": "cmd_iniciar_stream_inf"}],
                [
                    {"text": "⬅️ Volver a Herramientas", "callback_data": "sec_sistema"},
                    {"text": "🏠 Menú Principal", "callback_data": "menu_principal"}
                ]
            ]
        }


def get_menu_notificaciones_markup():
    """Submenú Pausar o activar alertas."""
    return {
        "inline_keyboard": [
            [
                {"text": "🔕 Pausar alertas automáticas", "callback_data": "cmd_deten_notif"},
                {"text": "🔔 Activar alertas automáticas", "callback_data": "cmd_reanudar_notif"}
            ],
            [
                {"text": "⬅️ Volver a Herramientas", "callback_data": "sec_sistema"},
                {"text": "🏠 Menú Principal", "callback_data": "menu_principal"}
            ]
        ]
    }
