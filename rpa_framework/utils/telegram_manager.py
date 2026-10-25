"""
Fachada de compatibilidad para el gestor de Telegram.
Delega en el paquete modular `rpa_framework/utils/telegram/`.
"""
import sys

try:
    from utils.telegram import (
        TOKEN,
        TELEGRAM_BASE_URL,
        USUARIOS_FILE,
        _telegram_session,
        telegram_request,
        cargar_usuarios,
        guardar_usuarios,
        configurar_menu_comandos,
        get_menu_principal_markup,
        get_menu_ejecucion_markup,
        get_menu_v2_markup,
        get_menu_loop_v2_markup,
        get_menu_revalidar_markup,
        get_menu_post_revalidar_markup,
        get_menu_loop_markup,
        get_menu_reportes_markup,
        get_menu_periodo_excel_markup,
        get_menu_sistema_markup,
        get_live_status_markup,
        get_menu_stream_markup,
        get_menu_notificaciones_markup,
        enviar_mensaje,
        editar_mensaje,
        responder_callback,
        enviar_mensaje_todos,
        enviar_alerta_todos,
        notificar_loop_pausado,
        enviar_foto,
        enviar_foto_todos,
        enviar_video,
        enviar_video_todos,
        enviar_documento,
        enviar_documento_todos,
    )
except ImportError:
    from rpa_framework.utils.telegram import (
        TOKEN,
        TELEGRAM_BASE_URL,
        USUARIOS_FILE,
        _telegram_session,
        telegram_request,
        cargar_usuarios,
        guardar_usuarios,
        configurar_menu_comandos,
        get_menu_principal_markup,
        get_menu_ejecucion_markup,
        get_menu_v2_markup,
        get_menu_loop_v2_markup,
        get_menu_revalidar_markup,
        get_menu_post_revalidar_markup,
        get_menu_loop_markup,
        get_menu_reportes_markup,
        get_menu_periodo_excel_markup,
        get_menu_sistema_markup,
        get_live_status_markup,
        get_menu_stream_markup,
        get_menu_notificaciones_markup,
        enviar_mensaje,
        editar_mensaje,
        responder_callback,
        enviar_mensaje_todos,
        enviar_alerta_todos,
        notificar_loop_pausado,
        enviar_foto,
        enviar_foto_todos,
        enviar_video,
        enviar_video_todos,
        enviar_documento,
        enviar_documento_todos,
    )

if __name__ == "__main__":
    if len(sys.argv) > 1:
        texto_alerta = " ".join(sys.argv[1:])
        enviar_alerta_todos(texto_alerta)
    else:
        print("Uso:")
        print("  python telegram_manager.py 'Tu mensaje'      # Para enviar alerta a todos")
