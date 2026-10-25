"""
Ejecución, detención e interrupción controlada de workflows desde el servicio Bot de Telegram.
"""
import importlib
import json
import os
import subprocess
import sys
import threading
import time
import traceback

import psutil

from core.models import Workflow, LoopNode
from utils.telegram_manager import enviar_mensaje, editar_mensaje
from . import bot_state
from .bot_state import (
    RPA_ROOT,
    STOP_SIGNAL,
    CMD_SIGNAL,
    mostrar_notificacion_tray,
    set_execution_state,
    is_any_workflow_running,
    get_current_running_name,
)
from .db_operations import obtener_ultimo_registro_casos_pendientes
from .pacs_monitor import trigger_pacs_validation_process


def cerrar_chrome_rpa():
    """Cierra de forma segura única y exclusivamente la ventana/proceso de Chrome utilizada por el RPA (puerto 9222 / RPA_Remote_Profile)."""
    try:
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                name = proc.info.get('name') or ''
                if 'chrome' in name.lower():
                    cmdline = ' '.join(proc.info.get('cmdline') or [])
                    if '9222' in cmdline or 'RPA_Remote_Profile' in cmdline:
                        print(f"[INFO] Cerrando Chrome RPA (PID {proc.info.get('pid')})...")
                        proc.terminate()
                        try:
                            proc.wait(timeout=2)
                        except psutil.TimeoutExpired:
                            proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception as e:
        print(f"[WARNING] Error al cerrar Chrome RPA: {e}")


def detener_ejecucion_actual(chat_id=None, source="Telegram"):
    """
    Detiene de manera inmediata y completa cualquier ejecución en curso (workflow activo,
    subworkflows anidados, scripts en proceso, validación PACS, etc.).
    """
    stopped_anything = False
    wf_name = get_current_running_name()

    print(f"🛑 [STOP] Solicitando detención de ejecución actual desde {source}...")

    # 1. Si hay executor activo local, propagar stop a todo el árbol
    if bot_state.active_executor:
        try:
            print(f"   Deteniendo active_executor: {wf_name}")
            bot_state.active_executor.stop()
            stopped_anything = True
        except Exception as e:
            print(f"⚠️ Error al detener active_executor: {e}")

    # 2. Si hay validación PACS en curso, liquidar el subproceso
    if bot_state._pacs_validating_now:
        print("   Deteniendo proceso de validación PACS...")
        stopped_anything = True
        bot_state._pacs_validating_now = False
        if bot_state._pacs_proc and bot_state._pacs_proc.poll() is None:
            try:
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(bot_state._pacs_proc.pid)], capture_output=True, timeout=3)
                bot_state._pacs_proc.kill()
            except Exception:
                pass
            bot_state._pacs_proc = None

    # 3. Señalizar archivo STOP_SIGNAL por si hay otro proceso (ej. GUI) ejecutando un worker
    if source != "Archivo Stop Signal":
        try:
            STOP_SIGNAL.parent.mkdir(parents=True, exist_ok=True)
            with open(STOP_SIGNAL, "w", encoding="utf-8") as f:
                f.write("stop")
        except Exception as e:
            print(f"Error escribiendo STOP_SIGNAL: {e}")

    # 4. Cerrar Chrome RPA si quedó abierto por el bot
    try:
        cerrar_chrome_rpa()
    except Exception:
        pass

    # 5. Si había ejecución local o remota
    is_running_flag = is_any_workflow_running()
    if stopped_anything or is_running_flag:
        set_execution_state(False)
        mostrar_notificacion_tray(f"Ejecución de '{wf_name}' detenida.", "🛑 Bot RPA")
        if chat_id:
            enviar_mensaje(chat_id, f"🛑 <b>Ejecución Detenida</b>\nSe ha cancelado el proceso: <code>{wf_name}</code>.")
        return True
    else:
        if chat_id:
            enviar_mensaje(chat_id, "ℹ️ No hay ningún proceso en ejecución.")
        return False


def run_workflow(wf_path, params=None, on_finish=None):
    try:
        print(f"🚀 Iniciando flujo: {wf_path}")
        wf = Workflow.from_json(wf_path)

        # Inyectar parámetros para loop si es necesario
        if params:
            tipo_loop = params.get("tipo", "count")
            valor = params.get("valor", "5")
            for node in wf.nodes:
                if isinstance(node, LoopNode):
                    node.loop_type = tipo_loop
                    if tipo_loop == "count":
                        node.iterations = str(valor)
                    elif tipo_loop == "timed":
                        node.duration_hours = float(valor)

        # Recargar dinámicamente workflow_executor para asegurar últimas modificaciones en disco
        try:
            import core.workflow_executor
            importlib.reload(core.workflow_executor)
            from core.workflow_executor import WorkflowExecutor
        except Exception as e_reload:
            print(f"⚠️ Aviso al recargar workflow_executor: {e_reload}")
            from core.workflow_executor import WorkflowExecutor

        bot_state.active_executor = WorkflowExecutor(wf)
        is_loop = (
            getattr(bot_state.active_executor, 'is_loop_workflow', lambda: False)()
            or any(getattr(n, 'type', '') == 'loop' for n in getattr(wf, 'nodes', []))
            or "loop" in getattr(wf, 'name', '').lower()
        )
        set_execution_state(True, wf.name, is_loop=is_loop)

        result = bot_state.active_executor.execute()
        print(f"✅ Flujo finalizado con estado: {result.get('status') if isinstance(result, dict) else result}")
        if on_finish:
            try:
                on_finish(result)
            except Exception as e_cb:
                print(f"Error en on_finish callback: {e_cb}")

    except Exception as e:
        print(f"❌ Error ejecutando workflow: {e}")
        traceback.print_exc()
        if on_finish:
            try:
                on_finish({"status": "error", "error": str(e)})
            except Exception as e_cb:
                print(f"Error en on_finish callback: {e_cb}")
    finally:
        bot_state.active_executor = None
        set_execution_state(False)


run_workflow_headless = run_workflow  # Alias para compatibilidad


def start_workflow_async(workflow_file, params=None, on_finish_callback=None):
    if "loop" in workflow_file.lower() and params:
        bot_state._last_loop_params = params

    if is_any_workflow_running():
        print("⚠️ No se puede iniciar flujo: Ya hay una ejecución activa.")
        return False

    wf_path = os.path.join("workflows", workflow_file)
    if not os.path.exists(wf_path):
        alt_path = RPA_ROOT / "workflows" / workflow_file
        if alt_path.exists():
            wf_path = str(alt_path)
        else:
            print(f"⚠️ Workflow no encontrado: {wf_path} ni en {alt_path}")
            return False

    try:
        if STOP_SIGNAL.exists():
            STOP_SIGNAL.unlink()
    except Exception:
        pass

    bot_state.executor_thread = threading.Thread(
        target=run_workflow,
        args=(wf_path, params, on_finish_callback),
        daemon=True
    )
    bot_state.executor_thread.start()
    return True


def monitor_stop_signal():
    """Monitorea señales de parada y comandos externos hacia el servicio interactivo."""
    while True:
        try:
            if STOP_SIGNAL.exists():
                print("🛑 Recibida señal de stop desde archivo stop_signal.txt.")
                try:
                    STOP_SIGNAL.unlink()
                except Exception:
                    pass
                detener_ejecucion_actual(source="Archivo Stop Signal")

            if CMD_SIGNAL.exists():
                try:
                    with open(CMD_SIGNAL, "r", encoding="utf-8") as f:
                        cmd_data = json.load(f)
                    try:
                        CMD_SIGNAL.unlink()
                    except Exception:
                        pass
                    action = cmd_data.get("action")
                    params = cmd_data.get("params")
                    print(f"📥 [IPC] Recibido comando externo: action={action}, params={params}")
                    if action in ["pega", "pacs"]:
                        start_workflow_async("pacs.json")
                    elif action in ["loop"]:
                        start_workflow_async("loop.json", params)
                    elif action in ["inicio"]:
                        start_workflow_async("Sub_work.json")
                except Exception as e_cmd:
                    print(f"⚠️ Error procesando command_signal: {e_cmd}")
                    try:
                        CMD_SIGNAL.unlink()
                    except Exception:
                        pass
        except Exception as e:
            print(f"Error en monitor_stop_signal: {e}")
        time.sleep(1)


def pedir_confirmacion_interrupcion(chat_id, action_key, nuevo_nombre):
    """Envía un mensaje interactivo con botones preguntando si se desea interrumpir el flujo actual."""
    actual = get_current_running_name()
    texto = (
        f"⚠️ <b>HAY UN PROCESO EN EJECUCIÓN</b>\n\n"
        f"• <b>Tarea actual:</b> <code>{actual}</code>\n"
        f"• <b>Nueva solicitud:</b> <b>{nuevo_nombre}</b>\n\n"
        f"¿Deseas <b>interrumpir</b> la tarea actual para iniciar <b>{nuevo_nombre}</b> ahora mismo?"
    )
    markup = {
        "inline_keyboard": [
            [{"text": "🛑 Sí, interrumpir e iniciar", "callback_data": f"force_{action_key}"}],
            [{"text": "❌ No, mantener en curso", "callback_data": "cancel_interrupt"}]
        ]
    }
    enviar_mensaje(chat_id, texto, reply_markup=markup)


def forzar_ejecucion_workflow(chat_id, msg_id, action_key):
    """Detiene el flujo actual de forma segura y luego inicia la nueva acción solicitada."""
    actual = get_current_running_name()
    msg_espera = f"🛑 <b>Interrumpiendo:</b> <code>{actual}</code>...\n⏳ Preparando nueva ejecución..."
    if msg_id:
        editar_mensaje(chat_id, msg_id, msg_espera)
    else:
        enviar_mensaje(chat_id, msg_espera)

    def _worker():
        detener_ejecucion_actual(source="Forzar Interrupción")

        for _ in range(8):
            if not is_any_workflow_running() and not bot_state._pacs_validating_now:
                break
            time.sleep(0.5)

        set_execution_state(False)
        time.sleep(0.5)

        if action_key == "inicio_v2":
            if start_workflow_async("Sub_work_v2.json"):
                enviar_mensaje(chat_id, "✅ Proceso anterior detenido.\n⚡ Workflow <b>'Sub_work V2 (Optimizado)'</b> iniciado correctamente.")
            else:
                enviar_mensaje(chat_id, "❌ No se encontró el workflow 'Sub_work_v2.json'.")

        elif action_key == "pacs_v2":
            if start_workflow_async("pacs_v2.json"):
                enviar_mensaje(chat_id, "✅ Proceso anterior detenido.\n📋 Workflow <b>'Solo PACS V2'</b> iniciado correctamente.")
            else:
                enviar_mensaje(chat_id, "❌ No se encontró el workflow 'pacs_v2.json'.")

        elif action_key.startswith("loop_v2_"):
            params = action_key.replace("loop_v2_", "").split("_")
            tipo = params[0]
            valor = params[1] if len(params) > 1 else None
            if start_workflow_async("loop_v2.json", {"tipo": tipo, "valor": valor}):
                enviar_mensaje(chat_id, f"✅ Proceso anterior detenido.\n🔁 <b>Loop V2 iniciado</b> en modo: <code>{tipo}</code> ({valor or ''})")
            else:
                enviar_mensaje(chat_id, "❌ No se pudo iniciar el Loop V2.")

        elif action_key == "inicio":
            if start_workflow_async("Sub_work.json"):
                enviar_mensaje(chat_id, "✅ Proceso anterior detenido.\n🚀 Workflow <b>'Inicio Completo'</b> iniciado correctamente.")
            else:
                enviar_mensaje(chat_id, "❌ No se encontró el workflow 'Sub_work.json'.")

        elif action_key in ["pega", "pega_integra"]:
            if start_workflow_async("pacs.json"):
                enviar_mensaje(chat_id, "✅ Proceso anterior detenido.\n📋 Workflow <b>'Solo Pega en Integra'</b> iniciado correctamente.")
            else:
                enviar_mensaje(chat_id, "❌ No se encontró el workflow 'pacs.json'.")

        elif action_key == "casos":
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

        elif action_key == "pacs":
            enviar_mensaje(chat_id, "🩺 Iniciando <b>Validación de PACS</b> bajo demanda...")
            if trigger_pacs_validation_process(manual=True, chat_id=chat_id):
                enviar_mensaje(chat_id, "🩺 <b>Validación PACS iniciada en ventana visible (primer plano).</b>\nPuedes monitorear la consola en pantalla o usar /estado_pacs.")
            else:
                enviar_mensaje(chat_id, "❌ No se pudo iniciar la validación de PACS.")

        elif action_key.startswith("loop_"):
            params = action_key.replace("loop_", "").split("_")
            tipo = params[0]
            valor = params[1] if len(params) > 1 else None
            if start_workflow_async("loop.json", {"tipo": tipo, "valor": valor}):
                enviar_mensaje(chat_id, f"✅ Proceso anterior detenido.\n🔁 <b>Loop iniciado</b> en modo: <code>{tipo}</code> ({valor or ''})")
            else:
                enviar_mensaje(chat_id, "❌ No se pudo iniciar el Loop.")
        else:
            enviar_mensaje(chat_id, f"⚠️ Acción no reconocida: {action_key}")

    threading.Thread(target=_worker, daemon=True, name="ForzarEjecucionWorker").start()


def run_llm_daily_checker():
    """Ejecuta la validación y actualización diaria de modelos LLM en segundo plano."""
    print("🤖 Iniciando checker diario de modelos LLM...")
    try:
        from utils.auto_replace_daily import run_daily_update
    except Exception as e:
        print(f"[LLM Checker] Error importando run_daily_update: {e}")
        return

    while True:
        try:
            run_daily_update()
        except Exception as e:
            print(f"[LLM Checker] Error en verificación: {e}")
        time.sleep(3600)
