import os
import sys
import json
import time
import threading
import requests
from pathlib import Path
from dotenv import load_dotenv
import traceback

# Forzar el directorio raíz de rpa_framework
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.models import Workflow, LoopNode
from core.workflow_executor import WorkflowExecutor
from utils.telegram_manager import enviar_mensaje, configurar_menu_comandos, cargar_usuarios, guardar_usuarios
from utils.notificador_resumen import (
    notificaciones_pausadas, pausar_notificaciones, reanudar_notificaciones, get_log_tail
)

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

def run_workflow_headless(wf_path, params=None):
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
        print(f"✅ Flujo finalizado con estado: {result['status']}")
        
    except Exception as e:
        print(f"❌ Error ejecutando workflow: {e}")
        traceback.print_exc()
    finally:
        active_executor = None
        set_execution_state(False)

def start_workflow_async(workflow_file, params=None):
    global active_executor, executor_thread
    
    if active_executor is not None:
        return False
        
    wf_path = os.path.join("workflows", workflow_file)
    if not os.path.exists(wf_path):
        print(f"⚠️ Workflow no encontrado: {wf_path}")
        return False
        
    executor_thread = threading.Thread(target=run_workflow_headless, args=(wf_path, params), daemon=True)
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

def telegram_polling_loop():
    print("🤖 Iniciando Servicio de Telegram en background...")
    if not TOKEN:
        print("⚠️ No hay token de Telegram configurado.")
        return

    # Iniciar el verificador diario de modelos LLM en segundo plano
    threading.Thread(target=run_llm_daily_checker, daemon=True, name="LLM_Daily_Checker").start()

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
                        if active_executor:
                            enviar_mensaje(chat_id, "⚠️ Ya hay un workflow en ejecución. Espere a que termine o deténgalo primero (/detener).")
                        else:
                            if start_workflow_async("pacs.json"):
                                enviar_mensaje(chat_id, "✅ Workflow 'Solo Pega en Integra' iniciado correctamente.")
                            else:
                                enviar_mensaje(chat_id, "❌ Workflow 'pacs.json' no encontrado.")
                                
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
                            enviar_mensaje(chat_id, "🔕 Notificaciones automáticas <b>suspendidas</b>. No se enviarán reportes horarios ni diarios. Usa /reanudar_notificaciones para volver a activarlas.")

                    elif comando == "/reanudar_notificaciones":
                        if not notificaciones_pausadas():
                            enviar_mensaje(chat_id, "ℹ️ Las notificaciones ya están activas.")
                        else:
                            reanudar_notificaciones()
                            enviar_mensaje(chat_id, "🔔 Notificaciones automáticas <b>reanudadas</b>. Los reportes horarios y diarios volverán a enviarse con normalidad.")

                    elif comando == "/ver_log":
                        tail = get_log_tail(15)
                        if len(tail) > 3800:
                            tail = "..." + tail[-3800:]
                        enviar_mensaje(chat_id, f"📋 <b>Últimas 15 líneas del log:</b>\n<code>{tail}</code>")

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
            set_execution_state(False)
            break
        except Exception as e:
            print(f"Error inesperado en polling: {e}")
            traceback.print_exc()
            time.sleep(5)

if __name__ == "__main__":
    telegram_polling_loop()
