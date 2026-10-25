"""
Captura de pantalla en vivo (Input Desktop), diagnóstico de estado y control de Live Stream en Telegram.
"""
import html
import json
import os
import threading
import time
from datetime import datetime

import psutil

from utils.stream_manager import stream_manager
from utils.telegram_manager import (
    enviar_mensaje,
    enviar_foto,
    get_live_status_markup,
)
from . import bot_state
from .bot_state import RPA_ROOT, STATE_FILE, is_any_workflow_running
from .pacs_monitor import get_pacs_daily_status


def capturar_pantalla_en_vivo(output_path):
    """
    Captura la pantalla actual completa del escritorio en tiempo real.
    Ejecuta la captura en un hilo dedicado y limpio para que SetThreadDesktop
    pueda vincularse al Input Desktop activo de Windows (WinSta0\\Default)
    sin interferencia de handles de GUI del hilo principal.
    """
    res_holder = {"success": False}

    def _thread_capture():
        hDesk = None
        try:
            import ctypes
            from ctypes import wintypes
            import mss
            from PIL import Image

            user32 = ctypes.windll.user32

            user32.OpenInputDesktop.restype = wintypes.HANDLE
            user32.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            user32.SetThreadDesktop.restype = wintypes.BOOL
            user32.SetThreadDesktop.argtypes = [wintypes.HANDLE]

            try:
                hDesk = user32.OpenInputDesktop(0, False, 0x01FF)
                if hDesk:
                    user32.SetThreadDesktop(hDesk)
            except Exception as e_desk:
                print(f"[Desktop Attach Info] {e_desk}")

            try:
                user32.SendMessageA(0xFFFF, 0x0112, 0xF170, -1)
            except Exception:
                pass

            with mss.mss() as sct:
                shot = sct.grab(sct.monitors[0])
                img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
                img.save(str(output_path), "PNG")
                res_holder["success"] = True
        except Exception as e:
            print(f"[Captura Pantalla Error] {e}")
        finally:
            if hDesk:
                try:
                    ctypes.windll.user32.CloseDesktop(hDesk)
                except Exception:
                    pass

    t = threading.Thread(target=_thread_capture, daemon=True)
    t.start()
    t.join(timeout=8.0)
    return res_holder["success"]


def obtener_datos_diagnostico():
    """Recopila todos los datos estructurados del sistema y BD."""
    en_ejecucion = is_any_workflow_running()
    wf_name = "Ninguno"
    tiempo_str = ""

    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                s_data = json.load(f)
                if s_data.get("is_running"):
                    wf_name = s_data.get("workflow", "Desconocido")
                    t_up = s_data.get("updated_at", 0)
                    if t_up:
                        seg = int(time.time() - t_up)
                        minutos = seg // 60
                        segundos = seg % 60
                        tiempo_str = f" ({minutos}m {segundos}s)"
        except Exception:
            pass

    if en_ejecucion:
        estado_proc_title = f"🔴 <b>EN EJECUCIÓN</b>\n  • Workflow: <code>{wf_name}</code>{tiempo_str}"
    else:
        estado_proc_title = "🟢 <b>INACTIVO / EN ESPERA</b>\n  • Sin tareas en curso"

    detalle_bd_texto = "Sin registros recientes"
    try:
        import mysql.connector
        conn = mysql.connector.connect(host='localhost', user='root', password='', database='ris', connect_timeout=5)
        cursor = conn.cursor(dictionary=True)
        query = """
        SELECT * FROM ris.registro_acciones 
        WHERE (
            (ultimo_nodo IS NULL OR ultimo_nodo NOT IN ('Validación PACS', 'valida_pacs', 'seleccion int casos pendientes', 'casos_pendientes', 'Inicia RIS'))
            OR numero_documento IS NOT NULL
        )
        AND (observacion IS NULL OR (observacion NOT LIKE '%validación PACS%' AND observacion NOT LIKE '%validacion PACS%') OR numero_documento IS NOT NULL)
        ORDER BY id DESC LIMIT 1
        """
        cursor.execute(query)
        reg = cursor.fetchone()
        if reg:
            r_id = reg.get("id")
            r_estado = reg.get("estado", "Desconocido")
            f_dt = reg.get("update") or reg.get("inicio")
            r_fecha = f_dt.strftime("%d/%m/%Y %H:%M:%S") if hasattr(f_dt, "strftime") else (str(f_dt) if f_dt else "--")
            r_doc = reg.get("numero_documento") or "--"
            r_exam = reg.get("examen") or "--"
            r_med = reg.get("doctor_detectado") or reg.get("User") or "--"
            r_nodo = reg.get("ultimo_nodo") or "--"
            r_obs = reg.get("observacion")

            r_pat = reg.get("patologia_critica")
            r_pat_det = reg.get("patologia_critica_detectada")
            if r_pat and str(r_pat).strip().lower() in ['si', 'sí', 'true', '1']:
                if r_pat_det and str(r_pat_det).strip():
                    pat_texto = f"🚨 <b>SÍ</b> (<i>{html.escape(str(r_pat_det).strip())}</i>)"
                else:
                    pat_texto = "🚨 <b>SÍ</b>"
            elif r_pat and str(r_pat).strip().lower() in ['no', 'false', '0']:
                pat_texto = "🟢 No"
            elif r_pat:
                pat_texto = f"ℹ️ {html.escape(str(r_pat).strip())}"
            else:
                pat_texto = "⚪ Sin evaluar"

            r_diag = reg.get("diagnostico")
            if r_diag and str(r_diag).strip():
                diag_clean = " ".join(str(r_diag).replace('\r', ' ').replace('\n', ' ').replace('\x0c', ' ').split())
                if len(diag_clean) > 200:
                    diag_preview = html.escape(diag_clean[:200].rstrip()) + "..."
                else:
                    diag_preview = html.escape(diag_clean)
                diag_texto = f"<i>{diag_preview}</i>"
            else:
                diag_texto = "<i>No registrado</i>"

            r_icono = "✅" if any(k in str(r_estado).lower() for k in ["terminado", "exitoso", "finalizado", "éxito", "exito"]) else ("❌" if any(k in str(r_estado).lower() for k in ["error", "fallo", "falla"]) else "⏳")

            lineas_caso = [
                f"{r_icono} <b>{html.escape(str(r_estado))}</b> (ID #{r_id})",
                f"  • <b>Fecha:</b> <code>{r_fecha}</code>",
                f"  • <b>Documento:</b> <code>{html.escape(str(r_doc))}</code>",
                f"  • <b>Examen:</b> {html.escape(str(r_exam))}",
                f"  • <b>Médico:</b> {html.escape(str(r_med))}",
                f"  • <b>Patología Crítica:</b> {pat_texto}",
                f"  • <b>Diagnóstico:</b> {diag_texto}",
                f"  • <b>Última Fase:</b> <code>{html.escape(str(r_nodo))}</code>"
            ]
            if r_obs and str(r_obs).strip() and str(r_obs).strip().lower() != "sin observaciones":
                obs_clean = " ".join(str(r_obs).replace('\r', ' ').replace('\n', ' ').split())
                obs_preview = html.escape(obs_clean[:140].rstrip()) + "..." if len(obs_clean) > 140 else html.escape(obs_clean)
                lineas_caso.append(f"  • <b>Detalle:</b> <i>{obs_preview}</i>")

            detalle_bd_texto = "\n".join(lineas_caso)
        cursor.close()
        conn.close()
    except Exception as e:
        detalle_bd_texto = f"⚠️ Error consultando BD: {e}"

    pacs_txt = "No disponible"
    try:
        daily_stat = get_pacs_daily_status()
        if bot_state._pacs_validating_now:
            pacs_txt = "⏳ Validación en curso..."
        elif daily_stat.get("ya_exitoso"):
            f_hoy = daily_stat.get('ultimo_timestamp')
            h_str = f_hoy.strftime('%H:%M:%S') if hasattr(f_hoy, 'strftime') else str(f_hoy or '')
            pacs_txt = f"✅ Validado hoy ({h_str})"
        else:
            pacs_txt = "⚠️ Pendiente de hoy"
    except Exception:
        pass

    bat_txt = "No disponible"
    try:
        b = psutil.sensors_battery()
        if b:
            pct = int(b.percent)
            plugged_str = "🔌 Conectado a corriente" if b.power_plugged else "🔋 En batería"
            bat_txt = f"{pct}% ({plugged_str})"
        else:
            bat_txt = "PC de escritorio (Alimentación fija)"
    except Exception:
        try:
            from utils.battery_monitor import obtener_estado_bateria_msg
            lines = [l.strip() for l in obtener_estado_bateria_msg().split('\n') if l.strip()]
            bat_txt = lines[1] if len(lines) > 1 else lines[0]
        except Exception:
            pass

    return {
        "estado_proc_title": estado_proc_title,
        "detalle_bd_texto": detalle_bd_texto,
        "pacs_txt": pacs_txt,
        "bat_txt": bat_txt
    }


def enviar_resumen_estado_texto(chat_id):
    """Genera y envía ficha de estado en vivo en texto formateado (rápido, sin screenshot ni fotos)."""
    diag_data = obtener_datos_diagnostico()
    is_streaming = stream_manager.esta_activo()
    stream_txt = f"🔴 Transmitiendo ({stream_manager.tiempo_transcurrido_str()})" if is_streaming else "⚪ Inactivo"

    txt = (
        "🔴 <b>ESTADO ACTUAL EN VIVO - ATRYS RPA</b>\n\n"
        f"🤖 <b>Estado Proceso:</b>\n{diag_data['estado_proc_title']}\n\n"
        f"📋 <b>Último Caso Procesado:</b>\n{diag_data['detalle_bd_texto']}\n\n"
        f"🏥 <b>PACS:</b> {diag_data['pacs_txt']}\n"
        f"🔋 <b>Batería:</b> {diag_data['bat_txt']}\n"
        f"📡 <b>Live Stream:</b> {stream_txt}\n"
        f"⏰ <b>Hora:</b> <code>{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</code>"
    )
    enviar_mensaje(chat_id, txt)


def enviar_estado_actual(chat_id):
    """Genera captura de pantalla real del escritorio en vivo y envía reporte con la foto adjunta y botón de Live Stream."""
    enviar_mensaje(chat_id, "📸 Generando diagnóstico y captura de pantalla en vivo...")

    screenshots_dir = RPA_ROOT / "logs" / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    shot_path = screenshots_dir / f"live_status_{int(time.time())}.png"

    diag_data = obtener_datos_diagnostico()
    is_streaming = stream_manager.esta_activo()
    stream_txt = f"🔴 Transmitiendo ({stream_manager.tiempo_transcurrido_str()})" if is_streaming else "⚪ Inactivo"
    status_markup = get_live_status_markup(is_streaming)

    caption_txt = (
        "📸 <b>DIAGNÓSTICO EN VIVO - ATRYS RPA</b>\n\n"
        f"🤖 <b>Estado Proceso:</b>\n{diag_data['estado_proc_title']}\n\n"
        f"📋 <b>Último Caso Procesado:</b>\n{diag_data['detalle_bd_texto']}\n\n"
        f"🏥 <b>PACS:</b> {diag_data['pacs_txt']}\n"
        f"🔋 <b>Batería:</b> {diag_data['bat_txt']}\n"
        f"📡 <b>Live Stream:</b> {stream_txt}\n"
        f"⏰ <b>Hora:</b> <code>{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</code>"
    )

    capturado = capturar_pantalla_en_vivo(shot_path)

    if capturado and os.path.exists(shot_path):
        if not enviar_foto(chat_id, str(shot_path), caption=caption_txt, reply_markup=status_markup):
            enviar_foto(chat_id, str(shot_path), caption="📸 Captura de pantalla en vivo")
            enviar_mensaje(chat_id, caption_txt, reply_markup=status_markup)
        try:
            shot_path.unlink()
        except Exception:
            pass
    else:
        enviar_mensaje(chat_id, f"⚠️ No se pudo tomar la captura de pantalla.\n\n{caption_txt}", reply_markup=status_markup)


def iniciar_live_stream_telegram(chat_id, duracion=600, stop_on_workflow=True):
    """Inicia la transmisión en vivo de escritorio vía Telethon y Videochat de Telegram."""
    if stream_manager.esta_activo():
        enviar_mensaje(
            chat_id,
            f"ℹ️ <b>La transmisión ya se encuentra activa</b> ({stream_manager.tiempo_transcurrido_str()}).\n"
            "Toca la barra superior del grupo para unirte al directo.",
            reply_markup={"inline_keyboard": [
                [{"text": "⏹️ Detener Transmisión", "callback_data": "cmd_detener_stream"}],
                [{"text": "📸 Estado Actual", "callback_data": "cmd_estado_actual"}]
            ]}
        )
        return

    enviar_mensaje(chat_id, "🚀 <b>Iniciando Live Stream en Telegram...</b>\n⏳ Conectando Videochat y configurando captura...")

    def _on_stream_finish(reason="tiempo"):
        stream_manager._cerrar_videochat_telethon(chat_id)
        if reason == "workflow":
            enviar_mensaje(
                chat_id,
                "⏹️ <b>Transmisión en vivo finalizada:</b>\nEl workflow en ejecución ha concluido.",
                reply_markup={"inline_keyboard": [
                    [{"text": "🔴 Iniciar Stream Nuevo", "callback_data": "cmd_iniciar_stream"}],
                    [{"text": "📸 Estado Actual", "callback_data": "cmd_estado_actual"}]
                ]}
            )
        elif reason == "tiempo":
            dur_mins = (duracion // 60) if duracion else 10
            enviar_mensaje(
                chat_id,
                f"⏹️ <b>Transmisión en vivo finalizada:</b>\nSe ha completado el tiempo máximo ({dur_mins} minutos).",
                reply_markup={"inline_keyboard": [
                    [{"text": "🔴 Iniciar Stream Nuevo", "callback_data": "cmd_iniciar_stream"}],
                    [{"text": "📸 Estado Actual", "callback_data": "cmd_estado_actual"}]
                ]}
            )

    stop_checker = None
    if stop_on_workflow:
        wf_running_at_least_once = is_any_workflow_running() or bot_state._pacs_validating_now
        wf_stopped_time = None

        def _check_workflow_status():
            nonlocal wf_running_at_least_once, wf_stopped_time
            currently_running = is_any_workflow_running() or bot_state._pacs_validating_now

            if currently_running:
                wf_running_at_least_once = True
                wf_stopped_time = None
                return False, ""

            if wf_running_at_least_once and not currently_running:
                if wf_stopped_time is None:
                    wf_stopped_time = time.time()
                if time.time() - wf_stopped_time >= 3:
                    return True, "workflow"

            return False, ""

        stop_checker = _check_workflow_status

    def _async_start():
        ok, msg = stream_manager.iniciar_transmision(
            duracion_max_segundos=duracion,
            chat_id=chat_id,
            on_stop=_on_stream_finish,
            stop_checker=stop_checker
        )
        if ok:
            if duracion == 600 or (duracion and stop_on_workflow):
                dur_txt = "10 minutos (o hasta que finalice el workflow en ejecución)"
            elif duracion:
                dur_txt = f"{duracion} segundos"
            else:
                dur_txt = "modo continuo"

            enviar_mensaje(
                chat_id,
                f"🔴 <b>TRANSMISIÓN EN VIVO INICIADA</b>\n\n"
                f"⏱️ <b>Duración:</b> {dur_txt}\n"
                f"📺 <b>Cómo ver:</b> Toca la barra superior azul/morada de este grupo (<b>Videochat</b>) para ver el escritorio en tiempo real.",
                reply_markup={"inline_keyboard": [
                    [{"text": "⏹️ Detener Transmisión", "callback_data": "cmd_detener_stream"}],
                    [{"text": "📸 Estado Actual", "callback_data": "cmd_estado_actual"}]
                ]}
            )
        else:
            enviar_mensaje(chat_id, f"❌ <b>Error al iniciar Live Stream:</b>\n{msg}")

    threading.Thread(target=_async_start, daemon=True).start()


def detener_live_stream_telegram(chat_id):
    """Detiene la transmisión en vivo y descarta el Videochat en Telegram."""
    stream_manager.detener_transmision(cerrar_videochat=True, chat_id=chat_id)
    enviar_mensaje(
        chat_id,
        "⏹️ <b>Transmisión en vivo y Videochat detenidos correctamente.</b>",
        reply_markup={"inline_keyboard": [
            [{"text": "🔴 Iniciar Stream Nuevo", "callback_data": "cmd_iniciar_stream"}],
            [{"text": "📸 Estado Actual", "callback_data": "cmd_estado_actual"}]
        ]}
    )
