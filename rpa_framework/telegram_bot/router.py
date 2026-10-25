"""
Enrutador de callbacks inline, comandos de texto y bucle principal de polling para el servicio Bot de Telegram.
"""
import html
import os
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime

import requests

from utils.mysql_auto_starter import ensure_mysql_running
from utils.notificador_resumen import (
    notificaciones_pausadas,
    pausar_notificaciones,
    reanudar_notificaciones,
    get_log_tail,
)
from utils.stream_manager import stream_manager
from utils.telegram_manager import (
    enviar_mensaje,
    editar_mensaje,
    responder_callback,
    configurar_menu_comandos,
    cargar_usuarios,
    guardar_usuarios,
    telegram_request,
    get_menu_principal_markup,
    get_menu_ejecucion_markup,
    get_menu_loop_markup,
    get_menu_v2_markup,
    get_menu_loop_v2_markup,
    get_menu_reportes_markup,
    get_menu_periodo_excel_markup,
    get_menu_sistema_markup,
    get_menu_notificaciones_markup,
    get_menu_stream_markup,
    get_menu_post_revalidar_markup,
)

from . import bot_state
from .bot_state import (
    RPA_ROOT,
    TOKEN,
    CONFIG_DIR,
    DEBUG_LOG,
    STOP_SIGNAL,
    get_last_update_id,
    save_last_update_id,
    mostrar_notificacion_tray,
    set_execution_state,
    is_any_workflow_running,
    get_last_loop_params,
    get_current_running_name,
)
from .db_operations import (
    marcar_registro_en_proceso,
    mostrar_menu_revalidar,
    obtener_ultimo_registro_casos_pendientes,
    enviar_reporte_excel_por_periodo,
)
from .live_stream import (
    enviar_resumen_estado_texto,
    enviar_estado_actual,
    iniciar_live_stream_telegram,
    detener_live_stream_telegram,
)
from .pacs_monitor import (
    trigger_pacs_validation_process,
    consultar_estado_pacs,
)
from .workflow_runner import (
    detener_ejecucion_actual,
    monitor_stop_signal,
    start_workflow_async,
    cerrar_chrome_rpa,
    pedir_confirmacion_interrupcion,
    forzar_ejecucion_workflow,
    run_llm_daily_checker,
)


def procesar_callback_query(callback_query):
    """Despacha cualquier callback_query recibido desde los botones inline de Telegram."""
    callback_data = callback_query.get("data")
    chat_id = callback_query["message"]["chat"]["id"]
    msg_id = callback_query["message"]["message_id"]
    cb_id = callback_query["id"]

    if callback_data == "menu_principal":
        responder_callback(cb_id)
        editar_mensaje(chat_id, msg_id, "🎛️ <b>Panel de Control Atrys RPA</b>\n\nSelecciona una opción para continuar:", reply_markup=get_menu_principal_markup())

    elif callback_data == "sec_ejecucion":
        responder_callback(cb_id)
        editar_mensaje(chat_id, msg_id, "🚀 <b>Iniciar ejecuciones</b>\n\nSelecciona el flujo que deseas iniciar:", reply_markup=get_menu_ejecucion_markup())

    elif callback_data == "sec_reportes":
        responder_callback(cb_id)
        editar_mensaje(chat_id, msg_id, "📊 <b>Reportes y consultas</b>\n\nSelecciona el reporte que deseas generar o consultar:", reply_markup=get_menu_reportes_markup())

    elif callback_data == "sec_sistema":
        responder_callback(cb_id)
        editar_mensaje(chat_id, msg_id, "🛠️ <b>Herramientas del sistema</b>\n\nDiagnóstico, pruebas de conexión y mantenimiento:", reply_markup=get_menu_sistema_markup())

    elif callback_data == "sec_notificaciones":
        responder_callback(cb_id)
        editar_mensaje(chat_id, msg_id, "🔔 <b>Pausar o activar alertas</b>\n\nAdministra las notificaciones automáticas:", reply_markup=get_menu_notificaciones_markup())

    elif callback_data == "cmd_estado_actual":
        responder_callback(cb_id, text="Generando captura en vivo...")
        enviar_estado_actual(chat_id)

    elif callback_data == "cmd_ver_casos_bd":
        responder_callback(cb_id)
        enviar_mensaje(chat_id, obtener_ultimo_registro_casos_pendientes())

    elif callback_data and callback_data.startswith("force_"):
        responder_callback(cb_id, text="Interrumpiendo proceso...")
        action_k = callback_data.replace("force_", "", 1)
        forzar_ejecucion_workflow(chat_id, msg_id, action_k)

    elif callback_data == "cancel_interrupt":
        responder_callback(cb_id, text="Interrupción cancelada")
        actual = get_current_running_name()
        editar_mensaje(chat_id, msg_id, f"ℹ️ <b>Solicitud cancelada.</b>\nEl proceso <code>{actual}</code> continúa en ejecución.")

    elif callback_data == "sec_v2":
        responder_callback(cb_id)
        editar_mensaje(
            chat_id, msg_id,
            "⚡ <b>Flujo Optimizado V2 (Pipeline Rápido)</b>\n\n"
            "• <b>Precarga paralela:</b> RIS extrae el siguiente examen en background mientras PACS procesa.\n"
            "• <b>Tiempo estimado:</b> ~1.5 - 2 minutos por caso (vs 8 minutos en V1).\n\n"
            "Selecciona la modalidad:",
            reply_markup=get_menu_v2_markup()
        )

    elif callback_data == "cmd_inicio_v2":
        responder_callback(cb_id)
        if bot_state.active_executor or is_any_workflow_running() or bot_state._pacs_validating_now:
            pedir_confirmacion_interrupcion(chat_id, "inicio_v2", "Sub_work V2 (Optimizado)")
        else:
            if start_workflow_async("Sub_work_v2.json"):
                enviar_mensaje(chat_id, "⚡ Workflow <b>'Sub_work V2 (Optimizado)'</b> iniciado correctamente.")
            else:
                enviar_mensaje(chat_id, "❌ Workflow 'Sub_work_v2.json' no encontrado.")

    elif callback_data == "cmd_pacs_v2":
        responder_callback(cb_id)
        if bot_state.active_executor or is_any_workflow_running() or bot_state._pacs_validating_now:
            pedir_confirmacion_interrupcion(chat_id, "pacs_v2", "Solo PACS V2")
        else:
            if start_workflow_async("pacs_v2.json"):
                enviar_mensaje(chat_id, "✅ Workflow <b>'Solo PACS V2'</b> iniciado correctamente.")
            else:
                enviar_mensaje(chat_id, "❌ Workflow 'pacs_v2.json' no encontrado.")

    elif callback_data == "cmd_loop_v2_menu":
        responder_callback(cb_id)
        editar_mensaje(
            chat_id, msg_id,
            "🔁 <b>Bucle Continuo V2 (Pipeline Rápido)</b>\n\n"
            "Selecciona cuántas repeticiones o por cuánto tiempo deseas procesar exámenes con precarga en paralelo:",
            reply_markup=get_menu_loop_v2_markup()
        )

    elif callback_data == "cmd_inicio":
        responder_callback(cb_id)
        if bot_state.active_executor or is_any_workflow_running() or bot_state._pacs_validating_now:
            pedir_confirmacion_interrupcion(chat_id, "inicio", "Inicio Completo")
        else:
            if start_workflow_async("Sub_work.json"):
                enviar_mensaje(chat_id, "✅ Workflow 'Inicio Completo' iniciado correctamente.")
            else:
                enviar_mensaje(chat_id, "❌ Workflow 'Sub_work.json' no encontrado.")

    elif callback_data in ["cmd_pega", "cmd_pega_integra"]:
        responder_callback(cb_id)
        if bot_state.active_executor or is_any_workflow_running() or bot_state._pacs_validating_now:
            pedir_confirmacion_interrupcion(chat_id, "pega", "Solo Pega en Integra")
        else:
            if start_workflow_async("pacs.json"):
                enviar_mensaje(chat_id, "✅ Workflow <b>'Solo Carga en Integra'</b> iniciado correctamente.")
            else:
                enviar_mensaje(chat_id, "❌ Workflow 'pacs.json' no encontrado.")

    elif callback_data == "cmd_loop_menu":
        responder_callback(cb_id)
        editar_mensaje(chat_id, msg_id, "🔁 <b>Ejecución con repeticiones</b>\n\nSelecciona cuántas veces o por cuánto tiempo deseas repetir:", reply_markup=get_menu_loop_markup())

    elif callback_data == "cmd_detener":
        responder_callback(cb_id)
        is_loop = False
        if bot_state.active_executor and getattr(bot_state.active_executor, 'is_loop_workflow', lambda: False)():
            is_loop = True
        elif "loop" in get_current_running_name().lower():
            is_loop = True

        if is_loop and (bot_state.active_executor or is_any_workflow_running()):
            msg_text = "🔁 <b>Flujo en Bucle (Loop) Detectado</b>\n\n¿Deseas detenerlo a la siguiente ejecución (terminando el caso actual) o en este mismo instante?"
            enviar_mensaje(
                chat_id,
                msg_text,
                reply_markup={"inline_keyboard": [
                    [{"text": "⏳ A la siguiente ejecución", "callback_data": "cmd_detener_next"}],
                    [{"text": "🛑 En este mismo instante", "callback_data": "cmd_detener_now"}]
                ]}
            )
        else:
            detener_ejecucion_actual(chat_id=chat_id, source="Telegram Botón")

    elif callback_data == "cmd_detener_next":
        responder_callback(cb_id, text="Detención programada tras caso actual...")
        if bot_state.active_executor:
            try:
                bot_state.active_executor.stop_after_current_case()
            except Exception:
                bot_state.active_executor.stop_after_iteration = True
        stop_after_file = CONFIG_DIR / "stop_after_case.txt"
        try:
            stop_after_file.parent.mkdir(parents=True, exist_ok=True)
            with open(stop_after_file, "w", encoding="utf-8") as f:
                f.write("stop_after_case")
        except Exception:
            pass
        editar_mensaje(chat_id, msg_id, "⏳ <b>Detención programada:</b> El bucle finalizará de forma limpia cuando concluya el caso en curso.")

    elif callback_data == "cmd_detener_now":
        responder_callback(cb_id, text="Deteniendo proceso de inmediato...")
        detener_ejecucion_actual(chat_id=chat_id, source="Telegram Inmediato")
        editar_mensaje(chat_id, msg_id, "🛑 <b>Proceso detenido inmediatamente por el usuario.</b>")

    elif callback_data == "loop_reanudar":
        responder_callback(cb_id, text="Reanudando loop...")
        if bot_state.active_executor and getattr(bot_state.active_executor, "is_paused", False):
            bot_state.active_executor.resume()
            editar_mensaje(chat_id, msg_id, "▶️ <b>Loop reanudado por el usuario.</b> Continuando con el ciclo...")
        else:
            editar_mensaje(chat_id, msg_id, "ℹ️ El loop ya no se encuentra en estado de pausa o no está activo.")

    elif callback_data == "loop_detener":
        responder_callback(cb_id, text="Deteniendo proceso...")
        detener_ejecucion_actual(chat_id=chat_id, source="Telegram (Detener desde pausa)")
        editar_mensaje(chat_id, msg_id, "⏹️ <b>Loop detenido definitivamente por el usuario.</b>")

    elif callback_data == "cmd_casos":
        responder_callback(cb_id)
        if bot_state.active_executor or is_any_workflow_running() or bot_state._pacs_validating_now:
            pedir_confirmacion_interrupcion(chat_id, "casos", "Conteo de Casos Pendientes en RIS")
        else:
            def _on_finish_cb_casos(res):
                cerrar_chrome_rpa()
                status = res.get("status") if isinstance(res, dict) else "completado"
                msg_datos = obtener_ultimo_registro_casos_pendientes()
                if status == "success":
                    enviar_mensaje(chat_id, f"✅ <b>Conteo de casos finalizado con éxito</b>\n\n{msg_datos}")
                else:
                    err = res.get("error", "") if isinstance(res, dict) else ""
                    err_txt = f"\n⚠️ Detalle: {err}" if err else ""
                    enviar_mensaje(chat_id, f"⚠️ <b>Flujo finalizado (Estado: {status})</b>{err_txt}\n\n{msg_datos}")

            enviar_mensaje(chat_id, "⏳ Iniciando conteo de casos pendientes en RIS...")
            if not start_workflow_async("ris_casos pendientes.json", on_finish_callback=_on_finish_cb_casos):
                enviar_mensaje(chat_id, "❌ No se pudo iniciar el workflow 'ris_casos pendientes.json'.")

    elif callback_data == "cmd_resumen":
        responder_callback(cb_id)
        enviar_mensaje(chat_id, "📑 Generando resumen del día en curso...")
        try:
            from utils.notificador_resumen import enviar_reporte_hourly
            enviar_reporte_hourly(force=True)
        except Exception as e:
            enviar_mensaje(chat_id, f"❌ Error generando resumen: {e}")

    elif callback_data == "cmd_menu_excel":
        responder_callback(cb_id)
        editar_mensaje(chat_id, msg_id, "📥 <b>Descargar reporte Excel</b>\n\nSelecciona el periodo que deseas exportar a formato Excel (.xlsx):", reply_markup=get_menu_periodo_excel_markup())

    elif callback_data == "rep_excel_hoy":
        responder_callback(cb_id, text="Generando Excel de Hoy...")
        enviar_reporte_excel_por_periodo(chat_id, "hoy")

    elif callback_data == "rep_excel_7d":
        responder_callback(cb_id, text="Generando Excel 7 Días...")
        enviar_reporte_excel_por_periodo(chat_id, "7d")

    elif callback_data == "rep_excel_mes":
        responder_callback(cb_id, text="Generando Excel Mes Actual...")
        enviar_reporte_excel_por_periodo(chat_id, "mes")

    elif callback_data == "cmd_estado_pacs":
        responder_callback(cb_id)
        enviar_mensaje(chat_id, consultar_estado_pacs())

    elif callback_data == "cmd_validar_pacs":
        responder_callback(cb_id)
        if bot_state.active_executor or is_any_workflow_running() or bot_state._pacs_validating_now:
            pedir_confirmacion_interrupcion(chat_id, "pacs", "Validación de PACS")
        else:
            enviar_mensaje(chat_id, "🩺 Iniciando <b>Validación de PACS</b> bajo demanda con médico aleatorio...")
            if trigger_pacs_validation_process(manual=True, chat_id=chat_id):
                enviar_mensaje(chat_id, "🩺 <b>Validación PACS iniciada en ventana visible (primer plano).</b>\nPuedes monitorear la consola en pantalla o usar /estado_pacs.")
            else:
                enviar_mensaje(chat_id, "❌ No se pudo iniciar la validación de PACS.")

    elif callback_data == "cmd_bateria":
        responder_callback(cb_id)
        try:
            from utils.battery_monitor import obtener_estado_bateria_msg
            enviar_mensaje(chat_id, obtener_estado_bateria_msg())
        except Exception as e:
            enviar_mensaje(chat_id, f"❌ Error consultando batería: {e}")

    elif callback_data == "cmd_ver_log":
        responder_callback(cb_id)
        tail = get_log_tail(15)
        if len(tail) > 3800:
            tail = "..." + tail[-3800:]
        enviar_mensaje(chat_id, f"📜 <b>Últimas 15 líneas del log:</b>\n<code>{tail}</code>")

    elif callback_data in ["cmd_rehabilitar", "cmd_revalidar", "cmd_revalidar_registro", "cmd_menu_revalidar"]:
        responder_callback(cb_id)
        mostrar_menu_revalidar(chat_id, msg_id)

    elif callback_data and (callback_data.startswith("reval_set_") or callback_data.startswith("reproc_pacs_")):
        responder_callback(cb_id, text="Actualizando estado en base de datos...")
        try:
            reg_id = int(callback_data.split("_")[-1])
            ok, datos = marcar_registro_en_proceso(reg_id)
            if ok and datos:
                txt_exito = (
                    f"✅ <b>Registro #{datos['id']} marcado 'En Proceso'</b>\n\n"
                    f"El registro quedó preparado para ejecutarse en la próxima interacción.\n\n"
                    f"🗓️ <b>Fecha/Hora Inicio:</b> <code>{html.escape(datos['inicio'])}</code>\n"
                    f"👨‍⚕️ <b>Doctor:</b> {html.escape(datos['doctor'])}\n"
                    f"📄 <b>N° Documento:</b> <code>{html.escape(datos['numero_documento'])}</code>\n"
                    f"🧪 <b>Examen:</b> {html.escape(datos['examen'])}\n\n"
                    f"¿Deseas iniciar la ejecución ahora?"
                )
                editar_mensaje(chat_id, msg_id, txt_exito, reply_markup=get_menu_post_revalidar_markup(reg_id))
            else:
                editar_mensaje(chat_id, msg_id, f"❌ No se pudo actualizar el registro #{reg_id}.", reply_markup=get_menu_ejecucion_markup())
        except Exception as e:
            editar_mensaje(chat_id, msg_id, f"❌ Error al revalidar registro: {e}", reply_markup=get_menu_ejecucion_markup())

    elif callback_data == "cmd_deten_notif":
        responder_callback(cb_id)
        if notificaciones_pausadas():
            enviar_mensaje(chat_id, "⚠️ Las notificaciones ya están suspendidas.")
        else:
            pausar_notificaciones()
            mostrar_notificacion_tray("Notificaciones automáticas suspendidas.", "🔕 Notificaciones")
            if bot_state.tray_manager:
                bot_state.tray_manager.update_icon()
            enviar_mensaje(chat_id, "🔕 Notificaciones automáticas <b>suspendidas</b>.")

    elif callback_data == "cmd_reanudar_notif":
        responder_callback(cb_id)
        if not notificaciones_pausadas():
            enviar_mensaje(chat_id, "ℹ️ Las notificaciones ya están activas.")
        else:
            reanudar_notificaciones()
            mostrar_notificacion_tray("Notificaciones automáticas reanudadas.", "🔔 Notificaciones")
            if bot_state.tray_manager:
                bot_state.tray_manager.update_icon()
            enviar_mensaje(chat_id, "🔔 Notificaciones automáticas <b>reanudadas</b>.")

    elif callback_data == "cmd_stream_menu":
        responder_callback(cb_id)
        st_activo = stream_manager.esta_activo()
        st_txt = f"🔴 <b>Transmitiendo</b> ({stream_manager.tiempo_transcurrido_str()})" if st_activo else "⚪ <b>Inactivo</b>"
        editar_mensaje(
            chat_id,
            msg_id,
            f"🔴 <b>Transmisión de pantalla en vivo</b>\n\n"
            f"Estado actual: {st_txt}\n\n"
            "Selecciona una opción:",
            reply_markup=get_menu_stream_markup(st_activo, stream_manager.tiempo_transcurrido_str())
        )

    elif callback_data in ["cmd_iniciar_stream", "cmd_iniciar_stream_600", "cmd_iniciar_stream_120", "cmd_iniciar_stream_300"]:
        responder_callback(cb_id, text="Enviando estado e iniciando transmisión...")
        enviar_resumen_estado_texto(chat_id)
        iniciar_live_stream_telegram(chat_id, duracion=600, stop_on_workflow=True)

    elif callback_data == "cmd_iniciar_stream_inf":
        responder_callback(cb_id, text="Enviando estado e iniciando transmisión continua...")
        enviar_resumen_estado_texto(chat_id)
        iniciar_live_stream_telegram(chat_id, duracion=None, stop_on_workflow=False)

    elif callback_data == "cmd_detener_stream":
        responder_callback(cb_id, text="Deteniendo transmisión...")
        detener_live_stream_telegram(chat_id)

    elif callback_data and (callback_data.startswith("gestionado_") or callback_data.startswith("gest_normal_")):
        record_id = callback_data.split("_")[-1]
        try:
            import mysql.connector
            conn = mysql.connector.connect(host="localhost", user="root", password="", database="ris")
            cursor = conn.cursor()
            cursor.execute("UPDATE registro_acciones SET estado_notificacion = 'Gestionado', fecha_actualizacion_notificacion = NOW() WHERE id = %s", (record_id,))
            conn.commit()
            conn.close()

            responder_callback(cb_id, text="Estado actualizado a gestionado ✅")
            new_markup = {"inline_keyboard": [[{"text": "Gestionado ✅", "callback_data": "ya_gestionado"}]]}
            editar_mensaje(chat_id, msg_id, callback_query["message"].get("text", "") or "Incidente gestionado", reply_markup=new_markup)
        except Exception as e:
            print(f"Error procesando callback_query gestionado: {e}")

    elif callback_data and callback_data.startswith("gest_addendum_"):
        record_id = callback_data.split("_")[-1]
        try:
            import mysql.connector
            conn = mysql.connector.connect(host="localhost", user="root", password="", database="ris")
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE registro_acciones 
                SET estado = 'Terminado - Addendum', 
                    estado_notificacion = 'Gestionado', 
                    fecha_actualizacion_notificacion = NOW(),
                    observacion = CONCAT(COALESCE(observacion, ''), ' | [Telegram: Reclasificado como Addendum]') 
                WHERE id = %s
            """, (record_id,))
            conn.commit()
            conn.close()

            responder_callback(cb_id, text="Caso reclasificado como Exitoso (Addendum) 📝")
            new_markup = {"inline_keyboard": [[{"text": "📝 Reclasificado: Addendum ✅", "callback_data": "ya_gestionado"}]]}
            editar_mensaje(chat_id, msg_id, callback_query["message"].get("text", "") or "Incidente reclasificado", reply_markup=new_markup)
        except Exception as e:
            print(f"Error procesando callback_query addendum: {e}")

    elif callback_data and callback_data.startswith("gest_ya_ingresado_"):
        record_id = callback_data.split("_")[-1]
        try:
            import mysql.connector
            conn = mysql.connector.connect(host="localhost", user="root", password="", database="ris")
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE registro_acciones 
                SET estado = 'Terminado - Ya Ingresado', 
                    estado_notificacion = 'Gestionado', 
                    fecha_actualizacion_notificacion = NOW(),
                    observacion = CONCAT(COALESCE(observacion, ''), ' | [Telegram: Reclasificado como Ya Ingresado]') 
                WHERE id = %s
            """, (record_id,))
            conn.commit()
            conn.close()

            responder_callback(cb_id, text="Caso reclasificado como Exitoso (Ya Ingresado) 🔁")
            new_markup = {"inline_keyboard": [[{"text": "🔁 Reclasificado: Ya Ingresado ✅", "callback_data": "ya_gestionado"}]]}
            editar_mensaje(chat_id, msg_id, callback_query["message"].get("text", "") or "Incidente reclasificado", reply_markup=new_markup)
        except Exception as e:
            print(f"Error procesando callback_query ya ingresado: {e}")

    elif callback_data == "ya_gestionado":
        responder_callback(cb_id, text="Este incidente ya fue gestionado / clasificado ✅", show_alert=False)

    elif callback_data and callback_data.startswith("loop_v2_"):
        responder_callback(cb_id, text="Procesando...")
        params = callback_data.replace("loop_v2_", "").split("_")
        tipo = params[0]
        valor = params[1] if len(params) > 1 else None

        if bot_state.active_executor or is_any_workflow_running() or bot_state._pacs_validating_now:
            pedir_confirmacion_interrupcion(chat_id, callback_data, f"Loop V2 ({tipo} {valor or ''})")
        else:
            if start_workflow_async("loop_v2.json", {"tipo": tipo, "valor": valor}):
                enviar_mensaje(chat_id, f"⚡ <b>Loop V2 iniciado</b> en modo: <code>{tipo}</code> ({valor or ''})")
            else:
                enviar_mensaje(chat_id, "❌ No se pudo iniciar el Loop V2.")

    elif callback_data and callback_data.startswith("loop_"):
        responder_callback(cb_id, text="Procesando...")
        params = callback_data.replace("loop_", "").split("_")
        tipo = params[0]
        valor = params[1] if len(params) > 1 else None

        if bot_state.active_executor or is_any_workflow_running() or bot_state._pacs_validating_now:
            pedir_confirmacion_interrupcion(chat_id, callback_data, f"Loop ({tipo} {valor or ''})")
        else:
            if start_workflow_async("loop.json", {"tipo": tipo, "valor": valor}):
                enviar_mensaje(chat_id, f"✅ Loop iniciado en modo: {tipo}")
            else:
                enviar_mensaje(chat_id, "❌ No se pudo iniciar el Loop.")


def procesar_mensaje_texto(message, usuarios):
    """Despacha comandos nativos y de texto recibidos en el chat."""
    chat = message.get("chat")
    chat_id = chat.get("id")
    text = message.get("text", "")
    chat_title = chat.get("title") or chat.get("first_name", "Usuario")

    comando = text.split('@')[0].strip()

    if comando in ["/start", "/menu", "/panel"]:
        if chat_id not in usuarios:
            usuarios.append(chat_id)
            guardar_usuarios(usuarios)
            enviar_mensaje(chat_id, f"Te has suscrito a las alertas de Atrys RPA en {chat_title}.")
        enviar_mensaje(chat_id, "🎛️ <b>Panel de Control Atrys RPA</b>\n\nSelecciona una opción para continuar:", reply_markup=get_menu_principal_markup())

    elif comando in ["/estado", "/status", "/captura"]:
        enviar_estado_actual(chat_id)

    elif comando in ["/stream", "/live", "/transmision", "/videochat"]:
        enviar_resumen_estado_texto(chat_id)
        iniciar_live_stream_telegram(chat_id, duracion=600, stop_on_workflow=True)

    elif comando in ["/stream_stop", "/stop_stream", "/detener_stream", "/stream_detener"]:
        detener_live_stream_telegram(chat_id)

    elif comando == "/ejecucion":
        enviar_mensaje(chat_id, "🚀 <b>Iniciar ejecuciones</b>\n\nSelecciona el flujo que deseas iniciar:", reply_markup=get_menu_ejecucion_markup())

    elif comando in ["/v2", "/subwork_v2", "/ejecucion_v2"]:
        enviar_mensaje(
            chat_id,
            "⚡ <b>Flujo Optimizado V2 (Pipeline Rápido)</b>\n\n"
            "• <b>Precarga paralela:</b> RIS extrae el siguiente examen en background mientras PACS procesa.\n"
            "• <b>Tiempo estimado:</b> ~1.5 - 2 minutos por caso (vs 8 minutos en V1).\n\n"
            "Selecciona la opción que deseas ejecutar:",
            reply_markup=get_menu_v2_markup()
        )

    elif comando == "/reportes":
        enviar_mensaje(chat_id, "📊 <b>Reportes y consultas</b>\n\nSelecciona el reporte que deseas generar o consultar:", reply_markup=get_menu_reportes_markup())

    elif comando == "/sistema":
        enviar_mensaje(chat_id, "🛠️ <b>Herramientas del sistema</b>\n\nDiagnóstico, pruebas de conexión y mantenimiento:", reply_markup=get_menu_sistema_markup())

    elif comando == "/notificaciones":
        enviar_mensaje(chat_id, "🔔 <b>Pausar o activar alertas</b>\n\nAdministra las notificaciones automáticas:", reply_markup=get_menu_notificaciones_markup())

    elif comando == "/stop":
        if chat_id in usuarios:
            usuarios.remove(chat_id)
            guardar_usuarios(usuarios)
            print(f"[X] Desuscrito: {chat_title} (ID: {chat_id})")
            enviar_mensaje(chat_id, "Te has desuscrito de las alertas.")

    elif comando in ["/ver_casos", "/casos_bd", "/ultimos_casos", "/consultar_casos"]:
        enviar_mensaje(chat_id, obtener_ultimo_registro_casos_pendientes())

    elif comando in ["/inicio_v2", "/run_v2"]:
        if bot_state.active_executor or is_any_workflow_running() or bot_state._pacs_validating_now:
            pedir_confirmacion_interrupcion(chat_id, "inicio_v2", "Sub_work V2 (Optimizado)")
        else:
            if start_workflow_async("Sub_work_v2.json"):
                enviar_mensaje(chat_id, "⚡ Workflow <b>'Sub_work V2 (Optimizado)'</b> iniciado correctamente.")
            else:
                enviar_mensaje(chat_id, "❌ Workflow 'Sub_work_v2.json' no encontrado.")

    elif comando == "/inicio":
        if bot_state.active_executor or is_any_workflow_running() or bot_state._pacs_validating_now:
            pedir_confirmacion_interrupcion(chat_id, "inicio", "Inicio Completo")
        else:
            if start_workflow_async("Sub_work.json"):
                enviar_mensaje(chat_id, "✅ Workflow 'Inicio Completo' iniciado correctamente.")
            else:
                enviar_mensaje(chat_id, "❌ Workflow 'Sub_work.json' no encontrado.")

    elif comando in ["/pega", "/solo_pega", "/pega_integra", "/solo_pega_integra"]:
        if bot_state.active_executor or is_any_workflow_running() or bot_state._pacs_validating_now:
            pedir_confirmacion_interrupcion(chat_id, "pega", "Solo Pega en Integra")
        else:
            if start_workflow_async("pacs.json"):
                enviar_mensaje(chat_id, "✅ Workflow <b>'Solo Carga en Integra'</b> iniciado correctamente.")
            else:
                enviar_mensaje(chat_id, "❌ Workflow 'pacs.json' no encontrado.")

    elif comando in ["/casos", "/contar_casos", "/cuenta_casos_pendientes", "/casos_pendientes", "/cuenta_casos", "/cuentacasos"]:
        if bot_state.active_executor or is_any_workflow_running() or bot_state._pacs_validating_now:
            pedir_confirmacion_interrupcion(chat_id, "casos", "Conteo de Casos Pendientes en RIS")
        else:
            def _on_finish_casos(res):
                cerrar_chrome_rpa()
                status = res.get("status") if isinstance(res, dict) else "completado"
                msg_datos = obtener_ultimo_registro_casos_pendientes()
                if status == "success":
                    enviar_mensaje(chat_id, f"✅ <b>Conteo de casos finalizado con éxito</b>\n\n{msg_datos}")
                else:
                    err = res.get("error", "") if isinstance(res, dict) else ""
                    err_txt = f"\n⚠️ Detalle: {err}" if err else ""
                    enviar_mensaje(chat_id, f"⚠️ <b>Flujo finalizado (Estado: {status})</b>{err_txt}\n\n{msg_datos}")

            enviar_mensaje(chat_id, "⏳ Iniciando conteo de casos pendientes en RIS...")
            if not start_workflow_async("ris_casos pendientes.json", on_finish_callback=_on_finish_casos):
                enviar_mensaje(chat_id, "❌ No se pudo iniciar el workflow 'ris_casos pendientes.json'. Verifique si ya hay otro proceso activo.")

    elif comando in ["/rehabilitar", "/revalidar", "/revalidar_registro", "/revalidar_ultimo_registro"]:
        mostrar_menu_revalidar(chat_id)

    elif comando == "/detener":
        is_loop = False
        if bot_state.active_executor and getattr(bot_state.active_executor, 'is_loop_workflow', lambda: False)():
            is_loop = True
        elif "loop" in get_current_running_name().lower():
            is_loop = True

        if is_loop and (bot_state.active_executor or is_any_workflow_running()):
            msg_text = "🔁 <b>Flujo en Bucle (Loop) Detectado</b>\n\n¿Deseas detenerlo a la siguiente ejecución (terminando el caso actual) o en este mismo instante?"
            enviar_mensaje(
                chat_id,
                msg_text,
                reply_markup={"inline_keyboard": [
                    [{"text": "⏳ A la siguiente ejecución", "callback_data": "cmd_detener_next"}],
                    [{"text": "🛑 En este mismo instante", "callback_data": "cmd_detener_now"}]
                ]}
            )
        else:
            detener_ejecucion_actual(chat_id=chat_id, source="Telegram Comando")

    elif comando in ["/reanudar", "/reanudar_loop", "/continuar"]:
        if bot_state.active_executor and getattr(bot_state.active_executor, "is_paused", False):
            bot_state.active_executor.resume()
            enviar_mensaje(chat_id, "▶️ <b>Loop reanudado.</b> Continuando con el ciclo de trabajo...")
        else:
            enviar_mensaje(chat_id, "ℹ️ No hay ningún loop en estado de pausa actualmente.")

    elif comando == "/resumen":
        enviar_mensaje(chat_id, "📑 Generando resumen del día en curso...")
        try:
            from utils.notificador_resumen import enviar_reporte_hourly
            enviar_reporte_hourly(force=True)
        except Exception as e:
            enviar_mensaje(chat_id, f"❌ Error generando resumen: {e}")

    elif comando in ["/excel", "/reporte_excel", "/exportar_excel"]:
        enviar_mensaje(chat_id, "📥 <b>Descargar reporte Excel</b>\n\nSelecciona el periodo que deseas exportar a formato Excel (.xlsx):", reply_markup=get_menu_periodo_excel_markup())

    elif comando == "/deten_notificaciones":
        if notificaciones_pausadas():
            enviar_mensaje(chat_id, "⚠️ Las notificaciones ya están suspendidas. Usa /reanudar_notificaciones para activarlas.")
        else:
            pausar_notificaciones()
            mostrar_notificacion_tray("Notificaciones automáticas suspendidas.", "🔕 Notificaciones")
            if bot_state.tray_manager:
                bot_state.tray_manager.update_icon()
            enviar_mensaje(chat_id, "🔕 Notificaciones automáticas <b>suspendidas</b>. No se enviarán reportes horarios ni diarios. Usa /reanudar_notificaciones para volver a activarlas.")

    elif comando == "/reanudar_notificaciones":
        if not notificaciones_pausadas():
            enviar_mensaje(chat_id, "ℹ️ Las notificaciones ya están activas.")
        else:
            reanudar_notificaciones()
            mostrar_notificacion_tray("Notificaciones automáticas reanudadas.", "🔔 Notificaciones")
            if bot_state.tray_manager:
                bot_state.tray_manager.update_icon()
            enviar_mensaje(chat_id, "🔔 Notificaciones automáticas <b>reanudadas</b>. Los reportes horarios y diarios volverán a enviarse con normalidad.")

    elif comando == "/ver_log":
        tail = get_log_tail(15)
        if len(tail) > 3800:
            tail = "..." + tail[-3800:]
        enviar_mensaje(chat_id, f"📜 <b>Últimas 15 líneas del log:</b>\n<code>{tail}</code>")

    elif comando == "/bateria":
        try:
            from utils.battery_monitor import obtener_estado_bateria_msg
            enviar_mensaje(chat_id, obtener_estado_bateria_msg())
        except Exception as e:
            enviar_mensaje(chat_id, f"❌ Error consultando batería: {e}")

    elif comando == "/estado_pacs":
        enviar_mensaje(chat_id, consultar_estado_pacs())

    elif comando in ["/validar_pacs", "/valida_pacs", "/forzar_pacs"]:
        if is_any_workflow_running() or bot_state._pacs_validating_now:
            pedir_confirmacion_interrupcion(chat_id, "pacs", "Validación de PACS")
        else:
            enviar_mensaje(chat_id, "🩺 Iniciando <b>Validación de PACS</b> bajo demanda...")
            if trigger_pacs_validation_process(manual=True, chat_id=chat_id):
                enviar_mensaje(chat_id, "🩺 <b>Validación PACS iniciada en ventana visible (primer plano).</b>\nPuedes monitorear la consola en pantalla o usar /estado_pacs.")
            else:
                enviar_mensaje(chat_id, "❌ No se pudo iniciar la validación de PACS.")

    elif comando == "/loop":
        enviar_mensaje(chat_id, "🔁 <b>Ejecución con repeticiones</b>\n\nSelecciona cuántas veces o por cuánto tiempo deseas repetir:", reply_markup=get_menu_loop_markup())


def telegram_polling_loop():
    print("🤖 Iniciando Servicio de Telegram en background...")

    try:
        ensure_mysql_running()
    except Exception as e:
        print(f"⚠️ Error al verificar/iniciar MySQL: {e}")

    if not TOKEN:
        print("⚠️ No hay token de Telegram configurado.")
        return

    threading.Thread(target=run_llm_daily_checker, daemon=True, name="LLM_Daily_Checker").start()

    try:
        from utils.notificador_resumen import main as start_notificador
        threading.Thread(target=start_notificador, daemon=True, name="NotifierResumen").start()
        print("📊 Notificador de Resúmenes iniciado.")
    except Exception as e:
        print(f"⚠️ No se pudo iniciar el servicio de Notificador: {e}")

    try:
        _sync_script = os.path.join(str(RPA_ROOT), "quick_scripts", "sync_medicos_sharepoint.py")
        if os.path.exists(_sync_script):
            def _run_sync_tg():
                try:
                    creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                    proc = subprocess.Popen(
                        [sys.executable, _sync_script],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=creation_flags,
                    )
                    proc.wait()
                except Exception as _e:
                    print(f"[sync_medicos] Error: {_e}")
            threading.Thread(target=_run_sync_tg, daemon=True, name="SyncMedicos").start()
            print("Sincronizacion de medicos SharePoint iniciada en segundo plano.")
    except Exception as e:
        print(f"[sync_medicos] No se pudo iniciar: {e}")

    try:
        from utils.battery_monitor import run_battery_monitor_loop
        threading.Thread(target=run_battery_monitor_loop, daemon=True, name="BatteryMonitor").start()
        print("🔋 Monitor de Batería iniciado.")
    except Exception as e:
        print(f"⚠️ No se pudo iniciar el servicio de Monitor de Batería: {e}")

    try:
        from utils.tray_manager import SystemTrayManager
        bot_state.tray_manager = SystemTrayManager(
            on_stop_callback=lambda: set_execution_state(False),
            on_stop_workflow_callback=lambda: detener_ejecucion_actual(source="Bandeja de Sistema")
        )
        bot_state.tray_manager.start()
        mostrar_notificacion_tray("Servicio Bot RPA iniciado y escuchando comandos.", "🤖 Bot RPA - Atrys")
        with open(DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(f"Icono de bandeja del sistema iniciado exitosamente a las {datetime.now()}\n")
    except Exception as e:
        with open(DEBUG_LOG, "a", encoding="utf-8") as f:
            f.write(f"Error iniciando icono bandeja: {e}\n{traceback.format_exc()}\n")
        print(f"⚠️ No se pudo iniciar el icono de la bandeja de sistema: {e}")

    configurar_menu_comandos()
    set_execution_state(False)

    threading.Thread(target=monitor_stop_signal, daemon=True).start()

    try:
        from utils.watchdog_supervisor import start_watchdog_supervisor, WATCHDOG_ENABLED
        if WATCHDOG_ENABLED:
            start_watchdog_supervisor(
                start_wf_func=start_workflow_async,
                stop_wf_func=detener_ejecucion_actual,
                is_running_func=is_any_workflow_running,
                get_loop_params_func=get_last_loop_params
            )
            print("🛡️ Supervisor Watchdog iniciado (Umbral: 12 min con auto-recuperación).")
        else:
            print("🛡️ Supervisor Watchdog desactivado.")
    except Exception as e:
        print(f"⚠️ No se pudo iniciar el Supervisor Watchdog: {e}")

    if STOP_SIGNAL.exists():
        try:
            STOP_SIGNAL.unlink()
        except Exception:
            pass

    ultimo_update_id = get_last_update_id()
    usuarios = cargar_usuarios()

    print(f"📡 Escuchando mensajes (desde update_id: {ultimo_update_id})...")

    while True:
        try:
            response = telegram_request("GET", f"getUpdates?offset={ultimo_update_id + 1}&timeout=30", timeout=40)
            if not response:
                time.sleep(5)
                continue

            if response.get("ok"):
                for update in response.get("result", []):
                    ultimo_update_id = update["update_id"]
                    save_last_update_id(ultimo_update_id)

                    if "callback_query" in update:
                        procesar_callback_query(update["callback_query"])
                        continue

                    message = update.get("message")
                    if message:
                        procesar_mensaje_texto(message, usuarios)

            time.sleep(1)
        except requests.exceptions.RequestException as re:
            print(f"Error de red en polling: {re}")
            time.sleep(5)
        except KeyboardInterrupt:
            print("\n🛑 Deteniendo servicio...")
            if bot_state.active_executor:
                bot_state.active_executor.stop()
            if bot_state.tray_manager:
                bot_state.tray_manager.stop()
            set_execution_state(False)
            break
        except Exception as e:
            print(f"Error inesperado en polling: {e}")
            traceback.print_exc()
            time.sleep(5)
