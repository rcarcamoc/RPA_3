import os
import sys
if sys.stdout is not None:
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
if sys.stderr is not None:
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass
import json
import time
import threading
import requests
import socket
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import traceback

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
    except Exception as e:
        pass

    return True

from core.models import Workflow, LoopNode
from core.workflow_executor import WorkflowExecutor
from utils.telegram_manager import enviar_mensaje, configurar_menu_comandos, cargar_usuarios, guardar_usuarios
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
CONFIG_DIR = Path("config")
CONFIG_DIR.mkdir(exist_ok=True)
UPDATE_FILE = CONFIG_DIR / "telegram_last_update.json"
STATE_FILE = CONFIG_DIR / "execution_state.json"
STOP_SIGNAL = CONFIG_DIR / "stop_signal.txt"

# Estado global
active_executor = None
executor_thread = None
tray_manager = None


def get_last_update_id():
    if UPDATE_FILE.exists():
        try:
            with open(UPDATE_FILE, 'r') as f:
                data = json.load(f)
                return data.get("last_update_id", 0)
        except:
            return 0
    return 0

def save_last_update_id(update_id):
    with open(UPDATE_FILE, 'w') as f:
        json.dump({"last_update_id": update_id}, f)

def set_execution_state(is_running, workflow_name=""):
    state = {
        "is_running": is_running,
        "workflow": workflow_name,
        "updated_at": time.time()
    }
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f)
    except Exception as e:
        print(f"Error guardando estado: {e}")

def monitor_stop_signal():
    """Monitorea si la GUI solicita detener la ejecución."""
    global active_executor
    while True:
        if STOP_SIGNAL.exists() and active_executor:
            print("🛑 Recibida señal de stop desde la GUI.")
            active_executor.stop()
            try:
                STOP_SIGNAL.unlink()
            except:
                pass
        time.sleep(1)

def run_workflow_headless(wf_path, params=None, on_finish=None):
    global active_executor
    
    try:
        print(f"▶️ Iniciando flujo: {wf_path}")
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
        
        # Bloquea hasta que termina
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
                    # Si la última actualización fue hace más de 15 minutos, considerar colgado
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
        target=run_workflow_headless, 
        args=(wf_path, params, on_finish_callback), 
        daemon=True
    )
    executor_thread.start()
    return True

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

def consultar_estado_pacs():
    """Consulta el estado actual y las últimas 5 validaciones de PACS desde ris.validacion_pacs."""
    try:
        import mysql.connector
        conn = mysql.connector.connect(host='localhost', user='root', password='', database='ris', connect_timeout=5)
        cursor = conn.cursor(dictionary=True)

        # Verificar si existe la tabla
        cursor.execute("SHOW TABLES LIKE 'validacion_pacs'")
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return "⚠️ La tabla <b>validacion_pacs</b> aún no existe. No se ha ejecutado ninguna validación."

        # Último estado
        cursor.execute("SELECT * FROM ris.validacion_pacs ORDER BY id DESC LIMIT 1")
        ultimo = cursor.fetchone()

        if not ultimo:
            cursor.close()
            conn.close()
            return "ℹ️ No hay registros de validación PACS aún."

        estado = ultimo.get('estado', 'Sin Datos')
        fecha = str(ultimo.get('fecha_validacion', '--'))
        obs = ultimo.get('observacion') or 'Sin observaciones'
        duracion = ultimo.get('duracion_segundos')
        intentos = ultimo.get('intentos', 1)

        iconos = {'Exitoso': '🟢', 'Error': '🔴', 'En Proceso': '🟡'}
        icono = iconos.get(estado, '⚪')

        msg = f"🔍 <b>Estado PACS</b>\n\n"
        msg += f"{icono} Estado: <b>{estado}</b>\n"
        msg += f"📅 Última verificación: {fecha}\n"
        msg += f"🔄 Intentos: {intentos}\n"
        if duracion is not None:
            msg += f"⏱ Duración: {duracion}s\n"
        msg += f"📝 Observación: {obs}\n"

        # Historial (últimas 5)
        cursor.execute("SELECT fecha_validacion, estado, duracion_segundos, intentos, observacion FROM ris.validacion_pacs ORDER BY id DESC LIMIT 5")
        registros = cursor.fetchall()

        if len(registros) > 1:
            msg += "\n<b>📋 Últimas validaciones:</b>\n"
            for r in registros:
                r_estado = r.get('estado', '?')
                r_icono = iconos.get(r_estado, '⚪')
                r_fecha = str(r.get('fecha_validacion', '--'))
                r_dur = f"{r.get('duracion_segundos', 0)}s" if r.get('duracion_segundos') is not None else '--'
                msg += f"  {r_icono} {r_fecha} | {r_dur} | {r.get('intentos', 1)} int.\n"

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
        # Verificar nuevamente en 1 hora
        time.sleep(3600)

def run_pacs_validation_scheduler():
    """Ejecuta en segundo plano la validación diaria de PACS según la hora y días configurados."""
    print("🔍 Iniciando scheduler de validación diaria PACS...")
    config_path = Path(__file__).resolve().parent / "config" / "pacs_validation_config.json"
    script_path = Path(__file__).resolve().parent / "recordings" / "sistema" / "validar_pacs_diario.py"

    def cargar_cfg():
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {"habilitado": True, "hora_validacion": "09:00", "dias_validacion": [0, 1, 2, 3, 4]}

    ultima_ejecucion_fecha = None

    while True:
        try:
            cfg = cargar_cfg()
            if cfg.get("habilitado", True):
                ahora = datetime.now()
                dia_actual = ahora.weekday()  # 0=Lunes, 6=Domingo
                hora_cfg = cfg.get("hora_validacion", "09:00")
                dias_permitidos = cfg.get("dias_validacion", [0, 1, 2, 3, 4])
                
                try:
                    h_target, m_target = [int(x) for x in hora_cfg.split(":")]
                except Exception:
                    h_target, m_target = 9, 0

                fecha_hoy_str = ahora.strftime("%Y-%m-%d")

                # Verificar si es la hora configurada (o minuto coincide) y no se ha ejecutado hoy
                if (ahora.hour == h_target and ahora.minute == m_target and 
                    dia_actual in dias_permitidos and ultima_ejecucion_fecha != fecha_hoy_str):
                    
                    if not is_any_workflow_running():
                        print(f"⏰ Hora alcanzada ({hora_cfg}). Lanzando validación diaria PACS...")
                        ultima_ejecucion_fecha = fecha_hoy_str
                        proc = subprocess.Popen([sys.executable, str(script_path)])
                        proc.wait()
                    else:
                        print("⏳ Hora alcanzada para validación PACS pero hay otro workflow corriendo. Reintentando en 60s...")
        except Exception as e:
            print(f"[PACS Scheduler Error] {e}")

        time.sleep(30)

def telegram_polling_loop():
    print("🤖 Iniciando Servicio de Telegram en background...")
    
    # 🗄️ Verificación e Inicio Automático de MySQL
    try:
        ensure_mysql_running()
    except Exception as e:
        print(f"⚠️ Error al verificar/iniciar MySQL: {e}")

    if not TOKEN:
        print("⚠️ No hay token de Telegram configurado.")
        return

    # Iniciar el verificador diario de modelos LLM en segundo plano
    threading.Thread(target=run_llm_daily_checker, daemon=True, name="LLM_Daily_Checker").start()

    # 🔍 Iniciar Scheduler de Validación PACS en segundo plano
    threading.Thread(target=run_pacs_validation_scheduler, daemon=True, name="PACS_Validation_Scheduler").start()

    # 📊 Iniciar Notificador de Resúmenes en segundo plano
    try:
        from utils.notificador_resumen import main as start_notificador
        threading.Thread(target=start_notificador, daemon=True, name="NotifierResumen").start()
        print("📊 Notificador de Resúmenes iniciado.")
    except Exception as e:
        print(f"⚠️ No se pudo iniciar el servicio de Notificador: {e}")

    # 🔄 Sincronizar tabla ris.medicos con SharePoint en segundo plano
    try:
        import subprocess
        _sync_script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "quick_scripts", "sync_medicos_sharepoint.py"
        )
        if os.path.exists(_sync_script):
            def _run_sync_tg():
                try:
                    proc = subprocess.Popen(
                        [sys.executable, _sync_script],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    proc.wait()
                except Exception as _e:
                    print(f"[sync_medicos] Error: {_e}")
            threading.Thread(target=_run_sync_tg, daemon=True, name="SyncMedicos").start()
            print("Sincronizacion de medicos SharePoint iniciada en segundo plano.")
    except Exception as e:
        print(f"[sync_medicos] No se pudo iniciar: {e}")

    # 🔋 Iniciar Monitor de Batería en segundo plano (cada 10 min)
    try:
        from utils.battery_monitor import run_battery_monitor_loop
        threading.Thread(target=run_battery_monitor_loop, daemon=True, name="BatteryMonitor").start()
        print("🔋 Monitor de Batería iniciado.")
    except Exception as e:
        print(f"⚠️ No se pudo iniciar el servicio de Monitor de Batería: {e}")

    # 🤖 Iniciar Icono de Robot en la Bandeja de Sistema (System Tray)
    global tray_manager
    try:
        from utils.tray_manager import SystemTrayManager
        tray_manager = SystemTrayManager(on_stop_callback=lambda: set_execution_state(False))
        tray_manager.start()
    except Exception as e:
        print(f"⚠️ No se pudo iniciar el icono de la bandeja de sistema: {e}")

    configurar_menu_comandos()
    set_execution_state(False)
    
    # Iniciar monitor de señales de STOP de la GUI
    threading.Thread(target=monitor_stop_signal, daemon=True).start()
    
    # Si hay un archivo stop signal huérfano, borrarlo
    if STOP_SIGNAL.exists():
        try: STOP_SIGNAL.unlink()
        except: pass
    
    ultimo_update_id = get_last_update_id()
    usuarios = cargar_usuarios()
    
    print(f"▶️ Escuchando mensajes (desde update_id: {ultimo_update_id})...")
    
    while True:
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={ultimo_update_id + 1}&timeout=30"
            response = requests.get(url, timeout=40).json()
            
            if response.get("ok"):
                for update in response.get("result", []):
                    ultimo_update_id = update["update_id"]
                    save_last_update_id(ultimo_update_id)
                    
                    # Manejar callbacks (botones en línea)
                    if "callback_query" in update:
                        callback_query = update["callback_query"]
                        callback_data = callback_query.get("data")
                        chat_id = callback_query["message"]["chat"]["id"]
                        
                        if callback_data and callback_data.startswith("gestionado_"):
                            record_id = callback_data.split("_")[1]
                            try:
                                import mysql.connector
                                conn = mysql.connector.connect(host="localhost", user="root", password="", database="ris")
                                cursor = conn.cursor()
                                cursor.execute("UPDATE registro_acciones SET estado_notificacion = 'Gestionado', fecha_actualizacion_notificacion = NOW() WHERE id = %s", (record_id,))
                                conn.commit()
                                conn.close()
                                
                                url_cb = f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery"
                                requests.post(url_cb, json={"callback_query_id": callback_query["id"], "text": "Estado actualizado a gestionado ✅"})
                                
                                url_edit = f"https://api.telegram.org/bot{TOKEN}/editMessageReplyMarkup"
                                new_markup = {"inline_keyboard": [[{"text": "Gestionado ✅", "callback_data": "ya_gestionado"}]]}
                                if "message" in callback_query:
                                    requests.post(url_edit, json={
                                        "chat_id": chat_id, 
                                        "message_id": callback_query["message"]["message_id"], 
                                        "reply_markup": new_markup
                                    })
                            except Exception as e:
                                print(f"Error procesando callback_query gestionado: {e}")
                                
                        elif callback_data == "ya_gestionado":
                            url_cb = f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery"
                            requests.post(url_cb, json={
                                "callback_query_id": callback_query["id"], 
                                "text": "Este incidente ya fue marcado como gestionado ✅", 
                                "show_alert": False
                            })
                            
                        elif callback_data and callback_data.startswith("loop_"):
                            url_cb = f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery"
                            requests.post(url_cb, json={"callback_query_id": callback_query["id"], "text": "Procesando..."})
                            
                            if active_executor:
                                enviar_mensaje(chat_id, "⚠️ Ya hay un workflow en ejecución. Espere a que termine o deténgalo primero (/detener).")
                            else:
                                params = callback_data.replace("loop_", "").split("_")
                                tipo = params[0]
                                valor = params[1] if len(params) > 1 else None
                                
                                if start_workflow_async("loop.json", {"tipo": tipo, "valor": valor}):
                                    enviar_mensaje(chat_id, f"✅ Loop iniciado en modo: {tipo}")
                                else:
                                    enviar_mensaje(chat_id, "❌ No se pudo iniciar el Loop.")
                        continue

                    # Manejar comandos de texto
                    message = update.get("message")
                    if not message: continue
                    
                    chat = message.get("chat")
                    chat_id = chat.get("id")
                    text = message.get("text", "")
                    chat_title = chat.get("title") or chat.get("first_name", "Usuario")
                    
                    # Limpiar el comando por si viene en formato "/comando@NombreBot"
                    comando = text.split('@')[0].strip()
                    
                    if comando == "/start":
                        if chat_id not in usuarios:
                            usuarios.append(chat_id)
                            guardar_usuarios(usuarios)
                            enviar_mensaje(chat_id, f"Te has suscrito a las alertas de Atrys RPA en {chat_title}.")
                        else:
                            enviar_mensaje(chat_id, "Ya estás suscrito. Usa el botón de menú para ver los comandos.")
                            
                    elif comando == "/stop":
                        if chat_id in usuarios:
                            usuarios.remove(chat_id)
                            guardar_usuarios(usuarios)
                            enviar_mensaje(chat_id, "Te has desuscrito de las alertas.")
                            
                    elif comando == "/inicio":
                        if active_executor:
                            enviar_mensaje(chat_id, "⚠️ Ya hay un workflow en ejecución. Espere a que termine o deténgalo primero (/detener).")
                        else:
                            if start_workflow_async("Sub_work.json"):
                                enviar_mensaje(chat_id, "✅ Workflow 'Inicio Completo' iniciado correctamente.")
                            else:
                                enviar_mensaje(chat_id, "❌ Workflow 'Sub_work.json' no encontrado.")
                                
                    elif comando == "/pega":
                        if active_executor or is_any_workflow_running():
                            enviar_mensaje(chat_id, "⚠️ Ya hay un workflow en ejecución. Espere a que termine o deténgalo primero (/detener).")
                        else:
                            if start_workflow_async("pacs.json"):
                                enviar_mensaje(chat_id, "✅ Workflow 'Solo Pega en Integra' iniciado correctamente.")
                            else:
                                enviar_mensaje(chat_id, "❌ Workflow 'pacs.json' no encontrado.")

                    elif comando in ["/cuenta_casos_pendientes", "/casos_pendientes", "/cuenta_casos", "/cuentacasos"]:
                        if active_executor or is_any_workflow_running():
                            enviar_mensaje(chat_id, "⚠️ Ya hay un workflow en ejecución. Espere a que termine o deténgalo primero (/detener).")
                        else:
                            def _on_finish_casos(res):
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
                        if active_executor:
                            enviar_mensaje(chat_id, "🛑 Solicitando detención de la ejecución actual...")
                            active_executor.stop()
                        else:
                            enviar_mensaje(chat_id, "⚠️ No hay ningún proceso en ejecución.")
                            
                    elif comando == "/resumen":
                        enviar_mensaje(chat_id, "📊 Generando resumen del día en curso...")
                        try:
                            from utils.notificador_resumen import enviar_reporte_hourly
                            enviar_reporte_hourly(force=True)
                        except Exception as e:
                            enviar_mensaje(chat_id, f"❌ Error generando resumen: {e}")

                    elif comando == "/deten_notificaciones":
                        if notificaciones_pausadas():
                            enviar_mensaje(chat_id, "⚠️ Las notificaciones ya están suspendidas. Usa /reanudar_notificaciones para activarlas.")
                        else:
                            pausar_notificaciones()
                            if tray_manager:
                                tray_manager.update_icon()
                            enviar_mensaje(chat_id, "🔕 Notificaciones automáticas <b>suspendidas</b>. No se enviarán reportes horarios ni diarios. Usa /reanudar_notificaciones para volver a activarlas.")

                    elif comando == "/reanudar_notificaciones":
                        if not notificaciones_pausadas():
                            enviar_mensaje(chat_id, "ℹ️ Las notificaciones ya están activas.")
                        else:
                            reanudar_notificaciones()
                            if tray_manager:
                                tray_manager.update_icon()
                            enviar_mensaje(chat_id, "🔔 Notificaciones automáticas <b>reanudadas</b>. Los reportes horarios y diarios volverán a enviarse con normalidad.")

                    elif comando == "/ver_log":
                        tail = get_log_tail(15)
                        if len(tail) > 3800:
                            tail = "..." + tail[-3800:]
                        enviar_mensaje(chat_id, f"📋 <b>Últimas 15 líneas del log:</b>\n<code>{tail}</code>")

                    elif comando == "/bateria":
                        try:
                            from utils.battery_monitor import obtener_estado_bateria_msg
                            enviar_mensaje(chat_id, obtener_estado_bateria_msg())
                        except Exception as e:
                            enviar_mensaje(chat_id, f"❌ Error consultando batería: {e}")

                    elif comando == "/estado_pacs":
                        enviar_mensaje(chat_id, consultar_estado_pacs())

                    elif comando == "/loop":
                        markup = {
                            "inline_keyboard": [
                                [{"text": "🔄 5 Iteraciones", "callback_data": "loop_count_5"}],
                                [{"text": "⏳ 1 Hora", "callback_data": "loop_timed_1.0"}],
                                [{"text": "⏳ 2 Horas", "callback_data": "loop_timed_2.0"}],
                                [{"text": "♾️ Infinito", "callback_data": "loop_infinite"}]
                            ]
                        }
                        enviar_mensaje(chat_id, "Selecciona el modo de Loop Continuo:", reply_markup=markup)
            
            time.sleep(1)
        except requests.exceptions.RequestException as re:
            print(f"Error de red en polling: {re}")
            time.sleep(5)
        except KeyboardInterrupt:
            print("\n⏹️ Deteniendo servicio...")
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
