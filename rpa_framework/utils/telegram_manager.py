import requests
import json
import time
import sys
import subprocess
import os
from dotenv import load_dotenv

load_dotenv()

# Configuración
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
if not TOKEN:
    print("Warning: TELEGRAM_BOT_TOKEN environment variable not set. Please create a .env file with the token.")

USUARIOS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "usuarios.json")

def cargar_usuarios():
    if os.path.exists(USUARIOS_FILE):
        try:
            with open(USUARIOS_FILE, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def guardar_usuarios(usuarios):
    with open(USUARIOS_FILE, 'w') as f:
        json.dump(usuarios, f, indent=4)

def configurar_menu_comandos():
    """Configura el menú nativo de comandos en Telegram."""
    url = f"https://api.telegram.org/bot{TOKEN}/setMyCommands"
    commands = [
        {"command": "start", "description": "👋 Bienvenida y panel principal"},
        {"command": "inicio", "description": "▶️ Iniciar flujo completo"},
        {"command": "pega", "description": "📑 Iniciar solo pega en Integra"},
        {"command": "loop", "description": "🔄 Configurar y ejecutar flujo continuo"},
        {"command": "rehabilitar", "description": "🛟 Rehabilitar último registro"},
        {"command": "detener", "description": "🛑 Detener ejecución actual"},
        {"command": "resumen", "description": "📊 Resumen del día en curso"},
        {"command": "deten_notificaciones", "description": "🔕 Suspender notificaciones horarias y diarias"},
        {"command": "reanudar_notificaciones", "description": "🔔 Reanudar notificaciones horarias y diarias"},
        {"command": "ver_log", "description": "📋 Ver las últimas 15 líneas del log de ejecución"}
    ]
    try:
        res = requests.post(url, json={"commands": commands}).json()
        if res.get("ok"):
            print("[OK] Menu de comandos de Telegram configurado exitosamente.")
        else:
            print(f"[WARN] Error configurando comandos: {res}")
    except Exception as e:
        print(f"Error en configurar_menu_comandos: {e}")

def registrar_usuarios(command_callback=None, panel_ref=None):
    """
    Escucha mensajes nuevos para registrar usuarios/grupos que usen /start y atiende comandos.
    Implementación 'lite' usando requests (basada en tu documentación).
    """
    configurar_menu_comandos()
    print("--- Escuchando nuevos suscriptores (Presiona Ctrl+C para detener) ---")
    print("Instrucciones: Envía /start al bot desde el grupo o chat privado.")
    
    ultimo_update_id = 0
    usuarios = cargar_usuarios()
    
    # Si el archivo está vacío, intentar añadir el grupo por defecto si lo detectamos
    
    while True:
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={ultimo_update_id + 1}&timeout=30"
            response = requests.get(url).json()
            
            if response.get("ok"):
                for update in response.get("result", []):
                    ultimo_update_id = update["update_id"]
                    
                    # Manejar callbacks (botones)
                    if "callback_query" in update:
                        callback_query = update["callback_query"]
                        callback_data = callback_query.get("data")
                        
                        if callback_data and callback_data.startswith("gestionado_"):
                            record_id = callback_data.split("_")[1]
                            try:
                                import mysql.connector
                                conn = mysql.connector.connect(host="localhost", user="root", password="", database="ris")
                                cursor = conn.cursor()
                                cursor.execute("UPDATE registro_acciones SET estado_notificacion = 'Gestionado', fecha_actualizacion_notificacion = NOW() WHERE id = %s", (record_id,))
                                conn.commit()
                                conn.close()
                                
                                # Notificar al usuario que hizo clic
                                url_cb = f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery"
                                requests.post(url_cb, json={"callback_query_id": callback_query["id"], "text": "Estado actualizado a gestionado ✅"})
                                
                                # Actualizar el botón en el mensaje
                                url_edit = f"https://api.telegram.org/bot{TOKEN}/editMessageReplyMarkup"
                                new_markup = {"inline_keyboard": [[{"text": "Gestionado ✅", "callback_data": "ya_gestionado"}]]}
                                if "message" in callback_query:
                                    requests.post(url_edit, json={
                                        "chat_id": callback_query["message"]["chat"]["id"], 
                                        "message_id": callback_query["message"]["message_id"], 
                                        "reply_markup": new_markup
                                    })
                                print(f"[OK] Registro {record_id} marcado como gestionado.")
                            except Exception as e:
                                print(f"Error procesando callback_query: {e}")
                        elif callback_data == "ya_gestionado":
                            # Responder al callback para quitar el estado de 'cargando' y mostrar mensaje
                            url_cb = f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery"
                            requests.post(url_cb, json={
                                "callback_query_id": callback_query["id"], 
                                "text": "Este incidente ya fue marcado como gestionado ✅", 
                                "show_alert": False
                            })
                        elif callback_data.startswith("loop_"):
                            url_cb = f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery"
                            requests.post(url_cb, json={"callback_query_id": callback_query["id"], "text": "Iniciando loop..."})
                            chat_id = callback_query["message"]["chat"]["id"]
                            if panel_ref and panel_ref.worker and panel_ref.worker.isRunning():
                                enviar_mensaje(chat_id, "⚠️ Ya hay un workflow en ejecución. Espere a que termine o deténgalo primero.")
                            else:
                                # callback_data es algo como "loop_count_5", "loop_timed_1.0", "loop_infinite"
                                params = callback_data.replace("loop_", "").split("_")
                                cmd_str = f"loop:{params[0]}:{params[1]}" if len(params) > 1 else f"loop:{params[0]}"
                                if command_callback:
                                    command_callback(cmd_str)
                                enviar_mensaje(chat_id, f"✅ Loop iniciado en modo: {params[0]}")
                        continue

                    # Manejar mensajes de texto
                    message = update.get("message")
                    if not message: continue
                    
                    chat = message.get("chat")
                    chat_id = chat.get("id")
                    text = message.get("text", "")
                    chat_title = chat.get("title") or chat.get("first_name", "Usuario")
                    
                    # Limpiar el comando por si viene en formato "/comando@NombreBot" (grupos)
                    comando = text.split('@')[0].strip()
                    
                    if comando == "/start":
                        if chat_id not in usuarios:
                            usuarios.append(chat_id)
                            guardar_usuarios(usuarios)
                            print(f"[OK] Nuevo suscriptor: {chat_title} (ID: {chat_id})")
                            enviar_mensaje(chat_id, f"Te has suscrito a las alertas de Atrys RPA en {chat_title}.")
                        else:
                            enviar_mensaje(chat_id, "Ya estás suscrito.")
                            
                    elif comando == "/stop":
                        if chat_id in usuarios:
                            usuarios.remove(chat_id)
                            guardar_usuarios(usuarios)
                            print(f"[X] Desuscrito: {chat_title} (ID: {chat_id})")
                            enviar_mensaje(chat_id, "Te has desuscrito de las alertas.")
                            
                    elif comando == "/inicio":
                        if panel_ref and panel_ref.worker and panel_ref.worker.isRunning():
                            enviar_mensaje(chat_id, "⚠️ Ya hay un workflow en ejecución. Espere a que termine o deténgalo primero (/detener).")
                        else:
                            if command_callback: command_callback("inicio")
                            enviar_mensaje(chat_id, "✅ Workflow 'Inicio Completo' iniciado correctamente.")
                            
                    elif comando == "/pega":
                        if panel_ref and panel_ref.worker and panel_ref.worker.isRunning():
                            enviar_mensaje(chat_id, "⚠️ Ya hay un workflow en ejecución. Espere a que termine o deténgalo primero (/detener).")
                        else:
                            if command_callback: command_callback("pega")
                            enviar_mensaje(chat_id, "✅ Workflow 'Solo Pega en Integra' iniciado correctamente.")
                            
                    elif comando == "/rehabilitar":
                        if command_callback: command_callback("rehabilitar")
                        enviar_mensaje(chat_id, "🔄 Solicitud de rehabilitación enviada al panel.")
                        
                    elif comando == "/detener":
                        if panel_ref and panel_ref.worker and panel_ref.worker.isRunning():
                            if command_callback: command_callback("detener")
                            enviar_mensaje(chat_id, "🛑 Solicitando detención de la ejecución actual...")
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
                        try:
                            from utils.notificador_resumen import notificaciones_pausadas, pausar_notificaciones
                            if notificaciones_pausadas():
                                enviar_mensaje(chat_id, "⚠️ Las notificaciones ya están suspendidas. Usa /reanudar_notificaciones para activarlas.")
                            else:
                                pausar_notificaciones()
                                enviar_mensaje(chat_id, "🔕 Notificaciones automáticas <b>suspendidas</b>. No se enviarán reportes horarios ni diarios. Usa /reanudar_notificaciones para volver a activarlas.")
                        except Exception as e:
                            enviar_mensaje(chat_id, f"❌ Error suspendiendo notificaciones: {e}")

                    elif comando == "/reanudar_notificaciones":
                        try:
                            from utils.notificador_resumen import notificaciones_pausadas, reanudar_notificaciones
                            if not notificaciones_pausadas():
                                enviar_mensaje(chat_id, "ℹ️ Las notificaciones ya están activas.")
                            else:
                                reanudar_notificaciones()
                                enviar_mensaje(chat_id, "🔔 Notificaciones automáticas <b>reanudadas</b>. Los reportes horarios y diarios volverán a enviarse con normalidad.")
                        except Exception as e:
                            enviar_mensaje(chat_id, f"❌ Error reanudando notificaciones: {e}")

                    elif comando == "/ver_log":
                        try:
                            from utils.notificador_resumen import get_log_tail
                            tail = get_log_tail(15)
                            if len(tail) > 3800:
                                tail = "..." + tail[-3800:]
                            enviar_mensaje(chat_id, f"📋 <b>Últimas 15 líneas del log:</b>\n<code>{tail}</code>")
                        except Exception as e:
                            enviar_mensaje(chat_id, f"❌ Error leyendo log: {e}")

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
        except KeyboardInterrupt:
            print("\nDeteniendo escucha...")
            break
        except Exception as e:
            print(f"Error en polling: {e}")
            time.sleep(5)

def enviar_mensaje(chat_id, texto, reply_markup=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": texto, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        res = requests.post(url, json=payload).json()
        return res.get("ok")
    except Exception as e:
        print(f"Error en enviar_mensaje: {e}")
        return False

def enviar_alerta_todos(mensaje, record_id=None):
    """Envía un mensaje a todos los usuarios registrados, opcionalmente con un botón para gestionarlo."""
    usuarios = cargar_usuarios()
    if not usuarios:
        print("Error: No hay usuarios registrados en usuarios.json. Ejecuta el script con --listen primero.")
        return

    reply_markup = None
    if record_id:
        reply_markup = {
            "inline_keyboard": [
                [{"text": "⚠️ Pendiente ⚠️", "callback_data": f"gestionado_{record_id}"}]
            ]
        }
        # Registrar en la BD que se envió la notificación
        try:
            import mysql.connector
            conn = mysql.connector.connect(host="localhost", user="root", password="", database="ris")
            cursor = conn.cursor()
            cursor.execute("UPDATE registro_acciones SET estado_notificacion = 'Pendiente', fecha_hora_envio = NOW() WHERE id = %s", (record_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Error actualizando DB al enviar alerta: {e}")

    print(f"Enviando alerta a {len(usuarios)} suscriptores...")
    for chat_id in usuarios:
        if enviar_mensaje(chat_id, mensaje, reply_markup):
            print(f"  [OK] Enviado a {chat_id}")
        else:
            print(f"  [Error] No se pudo enviar a {chat_id}")

def enviar_foto(chat_id, ruta_imagen, caption=""):
    """Envía una foto a un chat. Si el archivo es muy grande, la comprime antes."""
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    data = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}

    opened_file = None
    files = {}
    try:
        # Comprimir si el archivo pesa más de 4 MB
        import io
        from PIL import Image as PILImage
        tam = os.path.getsize(ruta_imagen)
        if tam > 4 * 1024 * 1024:
            img = PILImage.open(ruta_imagen)
            img.thumbnail((1920, 1080), PILImage.LANCZOS)
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=70)
            buffer.seek(0)
            files = {"photo": ("screenshot.jpg", buffer, "image/jpeg")}
        else:
            opened_file = open(ruta_imagen, "rb")
            files = {"photo": opened_file}
    except Exception:
        try:
            opened_file = open(ruta_imagen, "rb")
            files = {"photo": opened_file}
        except Exception as e:
            print(f"Error abriendo imagen para enviar: {e}")
            return False

    try:
        res = requests.post(url, data=data, files=files).json()
        if not res.get("ok"):
            print(f"  [Telegram API Error] sendPhoto: {res.get('description', res)}")
        return res.get("ok")
    except Exception as e:
        print(f"Error enviando foto a {chat_id}: {e}")
        return False
    finally:
        if opened_file:
            opened_file.close()

def enviar_foto_todos(ruta_imagen, caption=""):
    """Envía una foto con mensaje a todos los usuarios registrados."""
    usuarios = cargar_usuarios()
    if not usuarios:
        print("Error: No hay usuarios registrados en usuarios.json.")
        return

    print(f"Enviando foto a {len(usuarios)} suscriptores...")
    for chat_id in usuarios:
        if enviar_foto(chat_id, ruta_imagen, caption):
            print(f"  [OK] Foto enviada a {chat_id}")
        else:
            print(f"  [Error] No se pudo enviar foto a {chat_id}")


def enviar_video(chat_id, ruta_video, caption=""):
    """Envía un video (mp4/avi) a un chat de Telegram. Intenta sendVideo primero, y si falla usa sendDocument."""
    if not os.path.exists(ruta_video):
        print(f"Error: El archivo de video no existe: {ruta_video}")
        return False
        
    url = f"https://api.telegram.org/bot{TOKEN}/sendVideo"
    data = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}

    opened_file = None
    try:
        opened_file = open(ruta_video, "rb")
        files = {"video": (os.path.basename(ruta_video), opened_file, "video/mp4")}
        res = requests.post(url, data=data, files=files, timeout=60).json()
        if res.get("ok"):
            return True
            
        # Si falla sendVideo, intentar sendDocument
        print(f"  [Telegram API Info] sendVideo falló ({res.get('description')}), intentando sendDocument...")
        opened_file.seek(0)
        url_doc = f"https://api.telegram.org/bot{TOKEN}/sendDocument"
        files_doc = {"document": (os.path.basename(ruta_video), opened_file)}
        res_doc = requests.post(url_doc, data=data, files=files_doc, timeout=60).json()
        if not res_doc.get("ok"):
            print(f"  [Telegram API Error] sendDocument: {res_doc.get('description', res_doc)}")
        return res_doc.get("ok")
    except Exception as e:
        print(f"Error enviando video a {chat_id}: {e}")
        return False
    finally:
        if opened_file:
            opened_file.close()


def enviar_video_todos(ruta_video, caption=""):
    """Envía un video con mensaje a todos los usuarios registrados."""
    usuarios = cargar_usuarios()
    if not usuarios:
        print("Error: No hay usuarios registrados en usuarios.json.")
        return False

    print(f"Enviando video a {len(usuarios)} suscriptores...")
    exito = True
    for chat_id in usuarios:
        if enviar_video(chat_id, ruta_video, caption):
            print(f"  [OK] Video enviado a {chat_id}")
        else:
            print(f"  [Error] No se pudo enviar video a {chat_id}")
            exito = False
    return exito


if __name__ == "__main__":
    if "--listen" in sys.argv:
        registrar_usuarios()
    elif len(sys.argv) > 1:
        # Si se pasa texto, se envía como alerta a todos
        texto_alerta = " ".join(sys.argv[1:])
        enviar_alerta_todos(texto_alerta)
    else:
        print("Uso:")
        print("  python telegram_manager.py --listen          # Para registrar nuevos usuarios (/start)")
        print("  python telegram_manager.py 'Tu mensaje'      # Para enviar alerta a todos")
