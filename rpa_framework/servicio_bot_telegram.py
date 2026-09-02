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
import json
import html
import time
import threading
import requests
import socket
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import traceback
import psutil
import subprocess

# Forzar el directorio raíz de rpa_framework
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.mysql_auto_starter import ensure_mysql_running

_lock_socket = None
_lock_file = Path(__file__).resolve().parent / "config" / "servicio_bot.lock"

def check_single_instance(port=28374):
    global _lock_socket
    try:
        _lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _lock_socket.bind(("127.0.0.1", port))
        _lock_socket.listen(1)
    except socket.error:
        _lock_socket = None
        return False

    try:
        _lock_file.parent.mkdir(exist_ok=True)
        with open(_lock_file, "w", encoding="utf-8") as f:
            json.dump({"pid": os.getpid(), "started_at": datetime.now().isoformat()}, f)
    except Exception:
        pass

    return True

from core.models import Workflow, LoopNode
from core.workflow_executor import WorkflowExecutor
from utils.stream_manager import stream_manager
from utils.telegram_manager import (
    enviar_mensaje, editar_mensaje, responder_callback, configurar_menu_comandos,
    cargar_usuarios, guardar_usuarios, enviar_foto, enviar_documento,
    get_menu_principal_markup, get_menu_ejecucion_markup, get_menu_loop_markup,
    get_menu_reportes_markup, get_menu_periodo_excel_markup, get_menu_sistema_markup,
    get_menu_notificaciones_markup, get_live_status_markup, get_menu_stream_markup
)
from utils.excel_generator import generar_excel_reporte
from utils.notificador_resumen import (
    notificaciones_pausadas, pausar_notificaciones, reanudar_notificaciones, get_log_tail
)

env_parent = Path(__file__).resolve().parent.parent / ".env"
if env_parent.exists():
    load_dotenv(dotenv_path=env_parent)
else:
    load_dotenv()
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# Config paths
CONFIG_DIR = Path(__file__).resolve().parent / "config"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
DEBUG_LOG = LOG_DIR / "service_debug.log"
UPDATE_FILE = CONFIG_DIR / "telegram_last_update.json"
STATE_FILE = CONFIG_DIR / "execution_state.json"
STOP_SIGNAL = CONFIG_DIR / "stop_signal.txt"

# Estado global
active_executor = None
executor_thread = None
tray_manager = None
_pacs_proc = None

def get_last_update_id():
    if UPDATE_FILE.exists():
        try:
            with open(UPDATE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("last_update_id", 0)
        except Exception:
            return 0
    return 0

def save_last_update_id(update_id):
    with open(UPDATE_FILE, 'w', encoding='utf-8') as f:
        json.dump({"last_update_id": update_id}, f)

def mostrar_notificacion_tray(mensaje: str, titulo: str = "🤖 Bot RPA - Atrys"):
    """Envía una alerta o burbuja emergente al icono de la bandeja del sistema."""
    global tray_manager
    if tray_manager:
        try:
            tray_manager.notify(mensaje, titulo)
            tray_manager.update_icon()
        except Exception as e:
            print(f"Error mostrando alerta tray: {e}")

def set_execution_state(is_running, workflow_name=""):
    state = {
        "is_running": is_running,
        "workflow": workflow_name,
        "updated_at": time.time()
    }
    try:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f)
    except Exception as e:
        print(f"Error guardando estado: {e}")

    global tray_manager
    if tray_manager:
        try:
            if is_running and workflow_name:
                tray_manager.notify(f"Iniciando workflow: {workflow_name}", "🚀 Bot RPA - Flujo Iniciado")
            elif not is_running:
                tray_manager.notify("La ejecución del flujo ha finalizado.", "✅ Bot RPA - Flujo Completado")
            tray_manager.update_icon()
        except Exception:
            pass

def detener_ejecucion_actual(chat_id=None, source="Telegram"):
    """
    Detiene de manera inmediata y completa cualquier ejecución en curso (workflow activo,
    subworkflows anidados, scripts en proceso, validación PACS, etc.).
    """
    global active_executor, _pacs_validating_now, _pacs_proc
    stopped_anything = False
    wf_name = get_current_running_name()
    
    print(f"🛑 [STOP] Solicitando detención de ejecución actual desde {source}...")
    
    # 1. Si hay executor activo local, propagar stop a todo el árbol
    if active_executor:
        try:
            print(f"   Deteniendo active_executor: {wf_name}")
            active_executor.stop()
            stopped_anything = True
        except Exception as e:
            print(f"⚠️ Error al detener active_executor: {e}")

    # 2. Si hay validación PACS en curso, liquidar el subproceso
    if _pacs_validating_now:
        print("   Deteniendo proceso de validación PACS...")
        stopped_anything = True
        _pacs_validating_now = False
        if _pacs_proc and _pacs_proc.poll() is None:
            try:
                if sys.platform == "win32":
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(_pacs_proc.pid)], capture_output=True, timeout=3)
                _pacs_proc.kill()
            except Exception:
                pass
            _pacs_proc = None

    # 3. Señalizar archivo STOP_SIGNAL por si hay otro proceso (ej. GUI) ejecutando un worker
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

def monitor_stop_signal():
    """Monitorea si la GUI solicita detener la ejecución mediante stop_signal.txt."""
    while True:
        try:
            if STOP_SIGNAL.exists():
                print("🛑 Recibida señal de stop desde archivo stop_signal.txt.")
                try:
                    STOP_SIGNAL.unlink()
                except Exception:
                    pass
                detener_ejecucion_actual(source="Archivo Stop Signal")
        except Exception as e:
            print(f"Error en monitor_stop_signal: {e}")
        time.sleep(1)

def run_workflow(wf_path, params=None, on_finish=None):
    global active_executor
    
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
        
        active_executor = WorkflowExecutor(wf)
        set_execution_state(True, wf.name)
        
        result = active_executor.execute()
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
        active_executor = None
        set_execution_state(False)

run_workflow_headless = run_workflow  # Alias para compatibilidad

def is_any_workflow_running():
    """Retorna True si hay una ejecución activa local o via execution_state.json."""
    global active_executor
    if active_executor is not None:
        return True
    state_file = Path(__file__).resolve().parent / "config" / "execution_state.json"
    if state_file.exists():
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get("is_running", False):
                    if time.time() - data.get("updated_at", 0) < 900:
                        return True
        except Exception:
            pass
    return False

def start_workflow_async(workflow_file, params=None, on_finish_callback=None):
    global active_executor, executor_thread
    
    if is_any_workflow_running():
        print("⚠️ No se puede iniciar flujo: Ya hay una ejecución activa.")
        return False
        
    wf_path = os.path.join("workflows", workflow_file)
    if not os.path.exists(wf_path):
        print(f"⚠️ Workflow no encontrado: {wf_path}")
        return False
        
    executor_thread = threading.Thread(
        target=run_workflow, 
        args=(wf_path, params, on_finish_callback), 
        daemon=True
    )
    executor_thread.start()
    return True

def cerrar_chrome_rpa():
    """Cierra de forma segura única y exclusivamente la ventana/proceso de Chrome utilizada por el RPA (puerto 9222 / RPA_Remote_Profile)."""
    try:
        import psutil
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

def get_current_running_name():
    """Obtiene el nombre descriptivo del workflow o proceso actualmente en ejecución."""
    global active_executor, _pacs_validating_now
    if _pacs_validating_now:
        return "Validación PACS"
    if active_executor and hasattr(active_executor, 'workflow') and active_executor.workflow:
        return active_executor.workflow.name or "Workflow en curso"
    state_file = Path(__file__).resolve().parent / "config" / "execution_state.json"
    if state_file.exists():
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get("is_running"):
                    return data.get("workflow", "Workflow en curso")
        except Exception:
            pass
    return "Workflow en curso"

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
    global active_executor
    
    actual = get_current_running_name()
    msg_espera = f"🛑 <b>Interrumpiendo:</b> <code>{actual}</code>...\n⏳ Preparando nueva ejecución..."
    if msg_id:
        editar_mensaje(chat_id, msg_id, msg_espera)
    else:
        enviar_mensaje(chat_id, msg_espera)
        
    def _worker():
        detener_ejecucion_actual(source="Forzar Interrupción")
        
        # Esperar hasta 4 segundos a que se libere el proceso
        for _ in range(8):
            if not is_any_workflow_running() and not _pacs_validating_now:
                break
            time.sleep(0.5)
        
        set_execution_state(False)
        time.sleep(0.5)
        
        # Ejecutar la acción correspondiente
        if action_key == "inicio":
            if start_workflow_async("Sub_work.json"):
                enviar_mensaje(chat_id, "✅ Proceso anterior detenido.\n🚀 Workflow <b>'Inicio Completo'</b> iniciado correctamente.")
            else:
                enviar_mensaje(chat_id, "❌ No se encontró el workflow 'Sub_work.json'.")
                
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
                enviar_mensaje(chat_id, "⏳ Validación lanzada. Usa /estado_pacs para consultar el progreso.")
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

def rehabilitar_ultimo_registro():
    try:
        import mysql.connector
        config = {
            'host': 'localhost',
            'user': 'root',
            'password': '',
            'database': 'ris'
        }
        conn = mysql.connector.connect(**config, connect_timeout=5)
        cursor = conn.cursor()
        query = """
        UPDATE ris.registro_acciones 
        SET estado = 'En Proceso' 
        WHERE id = (SELECT max_id FROM (SELECT MAX(id) as max_id FROM ris.registro_acciones) as t)
        """
        cursor.execute(query)
        filas_afectadas = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()
        return filas_afectadas > 0
    except Exception as e:
        print(f"Error rehabilitando registro: {e}")
        return False

def check_pacs_validated_today():
    """Consulta la base de datos para ver si ya se realizó una validación exitosa de PACS hoy."""
    try:
        import mysql.connector
        conn = mysql.connector.connect(host='localhost', user='root', password='', database='ris', connect_timeout=5)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SHOW TABLES LIKE 'validacion_pacs'")
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return False
        cursor.execute("SELECT id, fecha_validacion FROM ris.validacion_pacs WHERE DATE(fecha_validacion) = CURDATE() AND estado = 'Exitoso' LIMIT 1")
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return row if row else False
    except Exception as e:
        print(f"[PACS Check DB Error] {e}")
        return False

_pacs_validating_now = False

def trigger_pacs_validation_process(manual=False, chat_id=None):
    """Ejecuta el script validar_pacs_diario.py con Keep-Alive y manejo de estado."""
    global _pacs_validating_now
    if _pacs_validating_now:
        print("⚠️ Ya hay una validación de PACS en ejecución.")
        return False
    
    script_path = Path(__file__).resolve().parent / "recordings" / "sistema" / "validar_pacs_diario.py"
    if not script_path.exists():
        print(f"❌ Script de validación PACS no encontrado: {script_path}")
        return False

    def _worker():
        global _pacs_validating_now, _pacs_proc
        _pacs_validating_now = True
        try:
            from utils.keep_alive import keep_system_awake
            with keep_system_awake(keep_display=True):
                tag = "MANUAL" if manual else "AUTO"
                print(f"🩺 [{tag}] Lanzando proceso de validación PACS...")
                mostrar_notificacion_tray(f"Iniciando Validación PACS ({tag})...", "🩺 Validación PACS")
                
                py_exe = sys.executable
                if "python.exe" in py_exe.lower():
                    pyw_cand = py_exe.lower().replace("python.exe", "pythonw.exe")
                    if os.path.exists(pyw_cand):
                        py_exe = pyw_cand

                cmd = [py_exe, str(script_path)]
                if manual:
                    cmd.append("--manual")
                
                creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                startupinfo = None
                if sys.platform == "win32":
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = 0

                proc = subprocess.Popen(
                    cmd, 
                    creationflags=creation_flags,
                    startupinfo=startupinfo,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding='utf-8',
                    errors='replace'
                )
                _pacs_proc = proc
                if proc.stdout:
                    for line in proc.stdout:
                        if line.strip():
                            print(f"   [PACS] {line.strip()}")
                proc.wait()
                print(f"✅ Proceso de validación PACS finalizado (exit code: {proc.returncode}).")
                mostrar_notificacion_tray("Validación PACS finalizada.", "🩺 Validación PACS")
                if chat_id:
                    res_txt = "✅ <b>Validación PACS Finalizada</b> (Exitosa)" if proc.returncode == 0 else "❌ <b>Validación PACS Finalizada con Error</b>"
                    enviar_mensaje(chat_id, res_txt + "\n\nUsa /estado_pacs para ver los detalles.")
        except Exception as e:
            print(f"[PACS Process Error] {e}")
            if chat_id:
                enviar_mensaje(chat_id, f"❌ Error ejecutando validación PACS: {e}")
        finally:
            _pacs_proc = None
            _pacs_validating_now = False
            try:
                from recordings.ui.cierra_pacs import cerrar_pacs
                cerrar_pacs()
            except Exception:
                pass

    threading.Thread(target=_worker, daemon=True, name="PACS_Validation_Worker").start()
    return True

def consultar_estado_pacs():
    """Consulta el estado actual, configuración y las últimas validaciones de PACS desde ris.validacion_pacs."""
    try:
        config_path = Path(__file__).resolve().parent / "config" / "pacs_validation_config.json"
        cfg = {}
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
            except Exception:
                pass

        hora_cfg = cfg.get("hora_validacion", "09:00")
        habilitado = cfg.get("habilitado", True)
        dias_val = cfg.get("dias_validacion", [0, 1, 2, 3, 4, 5, 6])
        nombres_dias = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
        dias_str = ", ".join([nombres_dias[d] for d in dias_val if 0 <= d < 7])

        import mysql.connector
        conn = mysql.connector.connect(host='localhost', user='root', password='', database='ris', connect_timeout=5)
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SHOW TABLES LIKE 'validacion_pacs'")
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return "⚠️ La tabla <b>validacion_pacs</b> aún no existe. No se ha ejecutado ninguna validación."

        cursor.execute("SELECT * FROM ris.validacion_pacs ORDER BY id DESC LIMIT 1")
        ultimo = cursor.fetchone()

        val_hoy = check_pacs_validated_today()
        if _pacs_validating_now:
            estado_hoy_str = "⏳ <b>En ejecución en este momento...</b>"
        elif val_hoy:
            f_hoy = val_hoy.get('fecha_validacion')
            hora_val_str = f_hoy.strftime('%H:%M:%S') if hasattr(f_hoy, 'strftime') else str(f_hoy)
            estado_hoy_str = f"✅ <b>Completada con éxito hoy a las {hora_val_str}</b>"
        else:
            ahora = datetime.now()
            try:
                ht, mt = [int(x) for x in hora_cfg.split(":")]
            except Exception:
                ht, mt = 9, 0
            if (ahora.hour > ht) or (ahora.hour == ht and ahora.minute >= mt):
                estado_hoy_str = "⚠️ <b>Pendiente / Próxima a ejecutarse (Catch-Up activo)</b>"
            else:
                estado_hoy_str = f"🕒 <b>Programada para hoy a las {hora_cfg}</b>"

        msg = f"🏥 <b>MONITOR DE VALIDACIÓN PACS</b>\n\n"
        msg += f"• <b>Estado de Hoy:</b> {estado_hoy_str}\n"
        msg += f"• <b>Programación:</b> Diaria a las <code>{hora_cfg}</code> ({dias_str})\n"
        msg += f"• <b>Servicio automático:</b> {'Activo ✅' if habilitado else 'Desactivado ❌'}\n\n"

        if ultimo:
            estado = ultimo.get('estado', 'Sin Datos')
            fecha = str(ultimo.get('fecha_validacion', '--'))
            obs = ultimo.get('observacion') or 'Sin observaciones'
            duracion = ultimo.get('duracion_segundos')
            intentos = ultimo.get('intentos', 1)
            iconos = {'Exitoso': '✅', 'Error': '❌', 'En Proceso': '⏳'}
            icono = iconos.get(estado, '⚠️')

            msg += f"📌 <b>Última Verificación Registrada:</b>\n"
            msg += f"  {icono} Estado: <b>{estado}</b> (ID #{ultimo.get('id')})\n"
            msg += f"  📅 Fecha: {fecha}\n"
            msg += f"  🔄 Intentos: {intentos}\n"
            if duracion is not None:
                msg += f"  ⏱️ Duración: {duracion}s\n"
            msg += f"  📝 Observación: {obs}\n"

        cursor.execute("SELECT id, fecha_validacion, estado, duracion_segundos, intentos, observacion FROM ris.validacion_pacs ORDER BY id DESC LIMIT 5")
        registros = cursor.fetchall()

        if len(registros) > 1:
            msg += "\n<b>📜 Historial Reciente:</b>\n"
            for r in registros[1:]:
                r_estado = r.get('estado', '?')
                iconos = {'Exitoso': '✅', 'Error': '❌', 'En Proceso': '⏳'}
                r_icono = iconos.get(r_estado, '⚠️')
                r_fecha = str(r.get('fecha_validacion', '--'))
                r_dur = f"{r.get('duracion_segundos', 0)}s" if r.get('duracion_segundos') is not None else '--'
                msg += f"  {r_icono} {r_fecha} | {r_dur} | {r.get('intentos', 1)} int.\n"

        msg += "\n💡 <i>Puedes forzar la validación ahora mismo enviando /validar_pacs</i>"

        cursor.close()
        conn.close()
        return msg
    except Exception as e:
        return f"❌ Error consultando estado PACS: {e}"

def obtener_ultimo_registro_casos_pendientes():
    """Consulta el último registro de la tabla casos_pendientes y devuelve el mensaje formateado."""
    try:
        import mysql.connector
        conn = mysql.connector.connect(host='localhost', user='root', password='', database='ris', connect_timeout=5)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM casos_pendientes ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row:
            return "ℹ️ No se encontraron registros en la tabla <b>casos_pendientes</b>."

        fecha_hora = row.get("fecha_hora")
        fecha_str = fecha_hora.strftime("%d/%m/%Y %H:%M:%S") if hasattr(fecha_hora, "strftime") else str(fecha_hora)
        total = row.get("total_pendientes", 0)
        cliente = row.get("cliente", "integramedica")
        obs = row.get("observacion")

        msg = f"📊 <b>Conteo de Casos Pendientes</b>\n\n"
        msg += f"🏢 Cliente: <b>{cliente}</b>\n"
        msg += f"📅 Fecha y Hora: <b>{fecha_str}</b>\n"
        msg += f"🔢 Total de registros pendientes: <b>{total}</b>\n"
        if obs:
            msg += f"📝 Observación: <i>{obs}</i>\n"
        return msg
    except Exception as e:
        return f"❌ Error consultando casos pendientes: {e}"

def enviar_reporte_excel_por_periodo(chat_id, periodo):
    """Genera y envía el reporte Excel formateado a Telegram en segundo plano."""
    enviar_mensaje(chat_id, "⏳ <i>Generando archivo Excel del periodo seleccionado...</i>")

    def _worker():
        try:
            res = generar_excel_reporte(periodo)
            if not res.get("success"):
                err = res.get("error_msg", "Error desconocido")
                enviar_mensaje(chat_id, f"❌ Error generando el archivo Excel: {err}")
                return

            file_path = res["file_path"]
            nombre_periodo = res["nombre_periodo"]
            total = res["total_casos"]
            exitos = res["exitosos"]
            errores = res["errores"]
            proceso = res["en_proceso"]
            patologias = res["patologias_criticas"]
            tasa = res["tasa_exito"]

            caption = (
                f"📊 <b>REPORTE EXCEL - ATRYS RPA</b>\n\n"
                f"📅 <b>Periodo:</b> {nombre_periodo}\n"
                f"🔢 <b>Total casos:</b> <b>{total}</b>\n"
                f"✅ <b>Exitosos:</b> {exitos} ({tasa})\n"
                f"❌ <b>Con Incidencias:</b> {errores}\n"
                f"⏳ <b>En Proceso:</b> {proceso}\n"
                f"🚨 <b>Patologías Críticas:</b> {patologias}\n\n"
                f"📁 <i>Archivo adjunto listo para consultar.</i>"
            )

            if not enviar_documento(chat_id, file_path, caption):
                enviar_mensaje(chat_id, f"⚠️ No se pudo enviar el archivo adjunto.\n\n{caption}")
        except Exception as e:
            enviar_mensaje(chat_id, f"❌ Error en la exportación Excel: {e}")

    threading.Thread(target=_worker, daemon=True, name="ExcelReportWorker").start()

# =========================================================================
# Captura de Pantalla Real en Vivo (Con enlace a Input Desktop)
# =========================================================================

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
            
            # 1. Configurar firmas 64-bit seguras
            user32.OpenInputDesktop.restype = wintypes.HANDLE
            user32.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            user32.SetThreadDesktop.restype = wintypes.BOOL
            user32.SetThreadDesktop.argtypes = [wintypes.HANDLE]
            
            # 2. Vincular este hilo limpio al escritorio activo de Windows
            try:
                hDesk = user32.OpenInputDesktop(0, False, 0x01FF)
                if hDesk:
                    user32.SetThreadDesktop(hDesk)
            except Exception as e_desk:
                print(f"[Desktop Attach Info] {e_desk}")

            # 3. Despertar monitor si está en reposo
            try:
                user32.SendMessageA(0xFFFF, 0x0112, 0xF170, -1)
            except Exception:
                pass

            # 4. Capturar pantalla completa con mss
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
    
    state_file = Path(__file__).resolve().parent / "config" / "execution_state.json"
    if state_file.exists():
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
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

            # Patología Crítica
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

            # Diagnóstico
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

    # Estado PACS
    pacs_txt = "No disponible"
    try:
        val_hoy = check_pacs_validated_today()
        if _pacs_validating_now:
            pacs_txt = "⏳ Validación en curso..."
        elif val_hoy:
            f_hoy = val_hoy.get('fecha_validacion')
            h_str = f_hoy.strftime('%H:%M:%S') if hasattr(f_hoy, 'strftime') else str(f_hoy)
            pacs_txt = f"✅ Validado hoy ({h_str})"
        else:
            pacs_txt = "⚠️ Pendiente de hoy"
    except Exception:
        pass

    # Estado Batería
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

def enviar_estado_actual(chat_id):
    """Genera captura de pantalla real del escritorio en vivo y envía reporte con la foto adjunta y botón de Live Stream."""
    enviar_mensaje(chat_id, "📸 Generando diagnóstico y captura de pantalla en vivo...")
    
    screenshots_dir = Path(__file__).resolve().parent / "logs" / "screenshots"
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
        wf_running_at_least_once = is_any_workflow_running() or _pacs_validating_now
        wf_stopped_time = None

        def _check_workflow_status():
            nonlocal wf_running_at_least_once, wf_stopped_time
            currently_running = is_any_workflow_running() or _pacs_validating_now

            if currently_running:
                wf_running_at_least_once = True
                wf_stopped_time = None
                return False, ""

            # Si estuvo corriendo (al inicio o durante el stream) y ahora ya terminó
            if wf_running_at_least_once and not currently_running:
                if wf_stopped_time is None:
                    wf_stopped_time = time.time()
                # Dejar 3 segundos de gracia tras finalizar el flujo
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
    ok, msg = stream_manager.detener_transmision(cerrar_videochat=True, chat_id=chat_id)
    enviar_mensaje(
        chat_id,
        "⏹️ <b>Transmisión en vivo y Videochat detenidos correctamente.</b>",
        reply_markup={"inline_keyboard": [
            [{"text": "🔴 Iniciar Stream Nuevo", "callback_data": "cmd_iniciar_stream"}],
            [{"text": "📸 Estado Actual", "callback_data": "cmd_estado_actual"}]
        ]}
    )

# =========================================================================
# Background Workers & Schedulers
# =========================================================================

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

def run_pacs_validation_scheduler():
    """Ejecuta en segundo plano la validación diaria de PACS según configuración y soporte catch-up."""
    print("🏥 Iniciando scheduler inteligente de validación diaria PACS...")
    config_path = Path(__file__).resolve().parent / "config" / "pacs_validation_config.json"
    
    def cargar_cfg():
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {"habilitado": True, "hora_validacion": "09:00", "dias_validacion": [0, 1, 2, 3, 4, 5, 6]}

    time.sleep(15)

    while True:
        try:
            cfg = cargar_cfg()
            if cfg.get("habilitado", True) and not _pacs_validating_now:
                ahora = datetime.now()
                dia_actual = ahora.weekday()
                hora_cfg = cfg.get("hora_validacion", "09:00")
                dias_permitidos = cfg.get("dias_validacion", [0, 1, 2, 3, 4, 5, 6])
                
                try:
                    h_target, m_target = [int(x) for x in hora_cfg.split(":")]
                except Exception:
                    h_target, m_target = 9, 0

                es_dia_permitido = dia_actual in dias_permitidos
                hora_alcanzada = (ahora.hour > h_target) or (ahora.hour == h_target and ahora.minute >= m_target)

                if es_dia_permitido and hora_alcanzada:
                    ya_validado = check_pacs_validated_today()
                    if not ya_validado:
                        if not is_any_workflow_running():
                            print(f"🩺 [{'Catch-Up' if ahora.hour > h_target or ahora.minute > m_target + 5 else 'Horario'}] Ejecutando validación diaria PACS...")
                            trigger_pacs_validation_process(manual=False)
                            time.sleep(60)
                        else:
                            print("⏳ Validación PACS pendiente, pero hay otro workflow corriendo. Esperando...")
        except Exception as e:
            print(f"[PACS Scheduler Error] {e}")

        time.sleep(30)

# =========================================================================
# Bucle Principal de Polling y Manejo de Comandos/Callbacks
# =========================================================================

def telegram_polling_loop():
    print("🤖 Iniciando Servicio de Telegram en background...")
    
    try:
        ensure_mysql_running()
    except Exception as e:
        print(f"⚠️ Error al verificar/iniciar MySQL: {e}")

    if not TOKEN:
        print("⚠️ No hay token de Telegram configurado.")
        return

    # Iniciar servicios en segundo plano
    threading.Thread(target=run_llm_daily_checker, daemon=True, name="LLM_Daily_Checker").start()
    threading.Thread(target=run_pacs_validation_scheduler, daemon=True, name="PACS_Validation_Scheduler").start()

    try:
        from utils.notificador_resumen import main as start_notificador
        threading.Thread(target=start_notificador, daemon=True, name="NotifierResumen").start()
        print("📊 Notificador de Resúmenes iniciado.")
    except Exception as e:
        print(f"⚠️ No se pudo iniciar el servicio de Notificador: {e}")

    try:
        import subprocess
        _sync_script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "quick_scripts", "sync_medicos_sharepoint.py"
        )
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

    global tray_manager
    try:
        from utils.tray_manager import SystemTrayManager
        tray_manager = SystemTrayManager(
            on_stop_callback=lambda: set_execution_state(False),
            on_stop_workflow_callback=lambda: detener_ejecucion_actual(source="Bandeja de Sistema")
        )
        tray_manager.start()
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
    
    if STOP_SIGNAL.exists():
        try: STOP_SIGNAL.unlink()
        except Exception: pass
    
    ultimo_update_id = get_last_update_id()
    usuarios = cargar_usuarios()
    
    print(f"📡 Escuchando mensajes (desde update_id: {ultimo_update_id})...")
    
    while True:
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={ultimo_update_id + 1}&timeout=30"
            response = requests.get(url, timeout=40).json()
            
            if response.get("ok"):
                for update in response.get("result", []):
                    ultimo_update_id = update["update_id"]
                    save_last_update_id(ultimo_update_id)
                    
                    if "callback_query" in update:
                        callback_query = update["callback_query"]
                        callback_data = callback_query.get("data")
                        chat_id = callback_query["message"]["chat"]["id"]
                        msg_id = callback_query["message"]["message_id"]
                        cb_id = callback_query["id"]
                        
                        if callback_data == "menu_principal":
                            responder_callback(cb_id)
                            editar_mensaje(chat_id, msg_id, "🎛️ <b>Panel de Control Atrys RPA</b>\n\nSelecciona una categoría para ver las opciones disponibles:", reply_markup=get_menu_principal_markup())
                            
                        elif callback_data == "sec_ejecucion":
                            responder_callback(cb_id)
                            editar_mensaje(chat_id, msg_id, "🚀 <b>Módulo de Ejecución y Workflows</b>\n\nSelecciona el flujo que deseas iniciar:", reply_markup=get_menu_ejecucion_markup())
                            
                        elif callback_data == "sec_reportes":
                            responder_callback(cb_id)
                            editar_mensaje(chat_id, msg_id, "📊 <b>Reportes y Consultas</b>\n\nSelecciona el reporte a generar:", reply_markup=get_menu_reportes_markup())
                            
                        elif callback_data == "sec_sistema":
                            responder_callback(cb_id)
                            editar_mensaje(chat_id, msg_id, "🛠️ <b>Diagnóstico y Mantenimiento</b>\n\nHerramientas y estado del sistema host:", reply_markup=get_menu_sistema_markup())
                            
                        elif callback_data == "sec_notificaciones":
                            responder_callback(cb_id)
                            editar_mensaje(chat_id, msg_id, "🔔 <b>Control de Notificaciones y Alertas</b>\n\nAdministra los reportes automáticos:", reply_markup=get_menu_notificaciones_markup())
                            
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
                            
                        elif callback_data == "cmd_inicio":
                            responder_callback(cb_id)
                            if active_executor or is_any_workflow_running() or _pacs_validating_now:
                                pedir_confirmacion_interrupcion(chat_id, "inicio", "Inicio Completo")
                            else:
                                if start_workflow_async("Sub_work.json"):
                                    enviar_mensaje(chat_id, "✅ Workflow 'Inicio Completo' iniciado correctamente.")
                                else:
                                    enviar_mensaje(chat_id, "❌ Workflow 'Sub_work.json' no encontrado.")
                                    
                        elif callback_data == "cmd_loop_menu":
                            responder_callback(cb_id)
                            editar_mensaje(chat_id, msg_id, "🔁 <b>Configuración de Loop Continuo</b>\n\nSelecciona el modo de repetición:", reply_markup=get_menu_loop_markup())
                            
                        elif callback_data == "cmd_detener":
                            responder_callback(cb_id)
                            detener_ejecucion_actual(chat_id=chat_id, source="Telegram Botón")
                                
                        elif callback_data == "cmd_casos":
                            responder_callback(cb_id)
                            if active_executor or is_any_workflow_running() or _pacs_validating_now:
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
                            editar_mensaje(chat_id, msg_id, "📥 <b>Exportación de Reportes a Excel</b>\n\nSelecciona el periodo que deseas exportar a formato Excel (.xlsx):", reply_markup=get_menu_periodo_excel_markup())

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
                            
                        elif callback_data == "cmd_rehabilitar":
                            responder_callback(cb_id)
                            enviar_mensaje(chat_id, "🔄 Rehabilitando el último registro...")
                            if rehabilitar_ultimo_registro():
                                enviar_mensaje(chat_id, "✅ Último registro rehabilitado ('En Proceso').")
                            else:
                                enviar_mensaje(chat_id, "⚠️ No se encontró registro para actualizar o hubo un error.")
                                
                        elif callback_data == "cmd_deten_notif":
                            responder_callback(cb_id)
                            if notificaciones_pausadas():
                                enviar_mensaje(chat_id, "⚠️ Las notificaciones ya están suspendidas.")
                            else:
                                pausar_notificaciones()
                                mostrar_notificacion_tray("Notificaciones automáticas suspendidas.", "🔕 Notificaciones")
                                if tray_manager:
                                    tray_manager.update_icon()
                                enviar_mensaje(chat_id, "🔕 Notificaciones automáticas <b>suspendidas</b>.")
                                
                        elif callback_data == "cmd_reanudar_notif":
                            responder_callback(cb_id)
                            if not notificaciones_pausadas():
                                enviar_mensaje(chat_id, "ℹ️ Las notificaciones ya están activas.")
                            else:
                                reanudar_notificaciones()
                                mostrar_notificacion_tray("Notificaciones automáticas reanudadas.", "🔔 Notificaciones")
                                if tray_manager:
                                    tray_manager.update_icon()
                                enviar_mensaje(chat_id, "🔔 Notificaciones automáticas <b>reanudadas</b>.")

                        elif callback_data == "cmd_stream_menu":
                            responder_callback(cb_id)
                            st_activo = stream_manager.esta_activo()
                            st_txt = f"🔴 <b>Transmitiendo</b> ({stream_manager.tiempo_transcurrido_str()})" if st_activo else "⚪ <b>Inactivo</b>"
                            editar_mensaje(
                                chat_id,
                                msg_id,
                                f"🔴 <b>Control de Transmisión en Vivo (Live Stream)</b>\n\n"
                                f"Estado actual: {st_txt}\n\n"
                                "Selecciona una acción:",
                                reply_markup=get_menu_stream_markup(st_activo, stream_manager.tiempo_transcurrido_str())
                            )

                        elif callback_data in ["cmd_iniciar_stream", "cmd_iniciar_stream_600", "cmd_iniciar_stream_120", "cmd_iniciar_stream_300"]:
                            responder_callback(cb_id, text="Iniciando Live Stream (10 min)...")
                            iniciar_live_stream_telegram(chat_id, duracion=600, stop_on_workflow=True)

                        elif callback_data == "cmd_iniciar_stream_inf":
                            responder_callback(cb_id, text="Iniciando Live Stream continuo...")
                            iniciar_live_stream_telegram(chat_id, duracion=None, stop_on_workflow=False)

                        elif callback_data == "cmd_detener_stream":
                            responder_callback(cb_id, text="Deteniendo Live Stream...")
                            detener_live_stream_telegram(chat_id)
                                
                        elif callback_data and callback_data.startswith("gestionado_"):
                            record_id = callback_data.split("_")[1]
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
                                
                        elif callback_data == "ya_gestionado":
                            responder_callback(cb_id, text="Este incidente ya fue marcado como gestionado ✅", show_alert=False)
                            
                        elif callback_data and callback_data.startswith("loop_"):
                            responder_callback(cb_id, text="Procesando...")
                            params = callback_data.replace("loop_", "").split("_")
                            tipo = params[0]
                            valor = params[1] if len(params) > 1 else None
                            
                            if active_executor or is_any_workflow_running() or _pacs_validating_now:
                                pedir_confirmacion_interrupcion(chat_id, callback_data, f"Loop ({tipo} {valor or ''})")
                            else:
                                if start_workflow_async("loop.json", {"tipo": tipo, "valor": valor}):
                                    enviar_mensaje(chat_id, f"✅ Loop iniciado en modo: {tipo}")
                                else:
                                    enviar_mensaje(chat_id, "❌ No se pudo iniciar el Loop.")
                        continue

                    # -------------------------------------------------------------
                    # Manejo de Comandos de Texto (Comandos Nativos y Directos)
                    # -------------------------------------------------------------
                    message = update.get("message")
                    if not message: continue
                    
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
                        enviar_mensaje(chat_id, "🎛️ <b>Panel de Control Atrys RPA</b>\n\nSelecciona una categoría para ver las opciones disponibles:", reply_markup=get_menu_principal_markup())
                            
                    elif comando in ["/estado", "/status", "/captura"]:
                        enviar_estado_actual(chat_id)
                        
                    elif comando in ["/stream", "/live", "/transmision", "/videochat"]:
                        iniciar_live_stream_telegram(chat_id, duracion=600, stop_on_workflow=True)

                    elif comando in ["/stream_stop", "/stop_stream", "/detener_stream", "/stream_detener"]:
                        detener_live_stream_telegram(chat_id)
                        
                    elif comando == "/ejecucion":
                        enviar_mensaje(chat_id, "🚀 <b>Módulo de Ejecución y Workflows</b>\n\nSelecciona el flujo que deseas iniciar:", reply_markup=get_menu_ejecucion_markup())
                        
                    elif comando == "/reportes":
                        enviar_mensaje(chat_id, "📊 <b>Reportes y Consultas</b>\n\nSelecciona el reporte a generar:", reply_markup=get_menu_reportes_markup())
                        
                    elif comando == "/sistema":
                        enviar_mensaje(chat_id, "🛠️ <b>Diagnóstico y Mantenimiento</b>\n\nHerramientas y estado del sistema host:", reply_markup=get_menu_sistema_markup())
                        
                    elif comando == "/notificaciones":
                        enviar_mensaje(chat_id, "🔔 <b>Control de Notificaciones y Alertas</b>\n\nAdministra los reportes automáticos:", reply_markup=get_menu_notificaciones_markup())

                    elif comando == "/stop":
                        if chat_id in usuarios:
                            usuarios.remove(chat_id)
                            guardar_usuarios(usuarios)
                            print(f"[X] Desuscrito: {chat_title} (ID: {chat_id})")
                            enviar_mensaje(chat_id, "Te has desuscrito de las alertas.")
                            
                    elif comando in ["/ver_casos", "/casos_bd", "/ultimos_casos", "/consultar_casos"]:
                        enviar_mensaje(chat_id, obtener_ultimo_registro_casos_pendientes())
                        
                    elif comando == "/inicio":
                        if active_executor or is_any_workflow_running() or _pacs_validating_now:
                            pedir_confirmacion_interrupcion(chat_id, "inicio", "Inicio Completo")
                        else:
                            if start_workflow_async("Sub_work.json"):
                                enviar_mensaje(chat_id, "✅ Workflow 'Inicio Completo' iniciado correctamente.")
                            else:
                                enviar_mensaje(chat_id, "❌ Workflow 'Sub_work.json' no encontrado.")

                    elif comando in ["/cuenta_casos_pendientes", "/casos_pendientes", "/cuenta_casos", "/cuentacasos"]:
                        if active_executor or is_any_workflow_running() or _pacs_validating_now:
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
                                
                    elif comando == "/rehabilitar":
                        enviar_mensaje(chat_id, "🔄 Rehabilitando el último registro...")
                        if rehabilitar_ultimo_registro():
                            enviar_mensaje(chat_id, "✅ Último registro rehabilitado ('En Proceso').")
                        else:
                            enviar_mensaje(chat_id, "⚠️ No se encontró registro para actualizar o hubo un error.")
                            
                    elif comando == "/detener":
                        detener_ejecucion_actual(chat_id=chat_id, source="Telegram Comando")
                            
                    elif comando == "/resumen":
                        enviar_mensaje(chat_id, "📑 Generando resumen del día en curso...")
                        try:
                            from utils.notificador_resumen import enviar_reporte_hourly
                            enviar_reporte_hourly(force=True)
                        except Exception as e:
                            enviar_mensaje(chat_id, f"❌ Error generando resumen: {e}")

                    elif comando in ["/excel", "/reporte_excel", "/exportar_excel"]:
                        enviar_mensaje(chat_id, "📥 <b>Exportación de Reportes a Excel</b>\n\nSelecciona el periodo que deseas exportar a formato Excel (.xlsx):", reply_markup=get_menu_periodo_excel_markup())

                    elif comando == "/deten_notificaciones":
                        if notificaciones_pausadas():
                            enviar_mensaje(chat_id, "⚠️ Las notificaciones ya están suspendidas. Usa /reanudar_notificaciones para activarlas.")
                        else:
                            pausar_notificaciones()
                            mostrar_notificacion_tray("Notificaciones automáticas suspendidas.", "🔕 Notificaciones")
                            if tray_manager:
                                tray_manager.update_icon()
                            enviar_mensaje(chat_id, "🔕 Notificaciones automáticas <b>suspendidas</b>. No se enviarán reportes horarios ni diarios. Usa /reanudar_notificaciones para volver a activarlas.")

                    elif comando == "/reanudar_notificaciones":
                        if not notificaciones_pausadas():
                            enviar_mensaje(chat_id, "ℹ️ Las notificaciones ya están activas.")
                        else:
                            reanudar_notificaciones()
                            mostrar_notificacion_tray("Notificaciones automáticas reanudadas.", "🔔 Notificaciones")
                            if tray_manager:
                                tray_manager.update_icon()
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
                        if is_any_workflow_running() or _pacs_validating_now:
                            pedir_confirmacion_interrupcion(chat_id, "pacs", "Validación de PACS")
                        else:
                            enviar_mensaje(chat_id, "🩺 Iniciando <b>Validación de PACS</b> bajo demanda...")
                            if trigger_pacs_validation_process(manual=True, chat_id=chat_id):
                                enviar_mensaje(chat_id, "⏳ Validación lanzada en segundo plano con soporte Keep-Alive. Usa /estado_pacs para consultar el progreso.")
                            else:
                                enviar_mensaje(chat_id, "❌ No se pudo iniciar la validación de PACS.")

                    elif comando == "/loop":
                        enviar_mensaje(chat_id, "🔁 <b>Configuración de Loop Continuo</b>\n\nSelecciona el modo de repetición:", reply_markup=get_menu_loop_markup())
            
            time.sleep(1)
        except requests.exceptions.RequestException as re:
            print(f"Error de red en polling: {re}")
            time.sleep(5)
        except KeyboardInterrupt:
            print("\n🛑 Deteniendo servicio...")
            if active_executor:
                active_executor.stop()
            if tray_manager:
                tray_manager.stop()
            set_execution_state(False)
            break
        except Exception as e:
            print(f"Error inesperado en polling: {e}")
            traceback.print_exc()
            time.sleep(5)

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
