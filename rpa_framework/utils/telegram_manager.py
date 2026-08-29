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
            with open(USUARIOS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def guardar_usuarios(usuarios):
    with open(USUARIOS_FILE, 'w', encoding='utf-8') as f:
        json.dump(usuarios, f, indent=4)

def configurar_menu_comandos():
    """Configura el menú nativo de comandos en Telegram (organizado por categorías)."""
    url = f"https://api.telegram.org/bot{TOKEN}/setMyCommands"
    commands = [
        {"command": "menu", "description": "🎛️ Panel de control general"},
        {"command": "estado", "description": "📸 Estado actual y captura en vivo"},
        {"command": "ejecucion", "description": "🚀 Workflows y automatización"},
        {"command": "reportes", "description": "📊 Casos pendientes y métricas"},
        {"command": "excel", "description": "📥 Exportar reporte a Excel (.xlsx)"},
        {"command": "sistema", "description": "🛠️ Diagnóstico y mantenimiento"},
        {"command": "notificaciones", "description": "🔔 Gestión de alertas"},
        {"command": "detener", "description": "⏹️ Parada de emergencia"}
    ]
    try:
        res = requests.post(url, json={"commands": commands}, timeout=10).json()
        if res.get("ok"):
            print("[OK] Menu de comandos de Telegram configurado exitosamente.")
        else:
            print(f"[WARN] Error configurando comandos: {res}")
    except Exception as e:
        print(f"Error en configurar_menu_comandos: {e}")

# =========================================================================
# Generadores de Teclados Inline para Menús y Submenús
# =========================================================================

def get_menu_principal_markup():
    """Menú Maestro con accesos a las secciones y estado actual."""
    return {
        "inline_keyboard": [
            [{"text": "📸 Estado Actual (En vivo)", "callback_data": "cmd_estado_actual"}],
            [
                {"text": "🚀 Ejecución", "callback_data": "sec_ejecucion"},
                {"text": "📊 Reportes", "callback_data": "sec_reportes"}
            ],
            [
                {"text": "🛠️ Sistema", "callback_data": "sec_sistema"},
                {"text": "🔔 Notificaciones", "callback_data": "sec_notificaciones"}
            ],
            [{"text": "⏹️ Detener Todo", "callback_data": "cmd_detener"}]
        ]
    }

def get_menu_ejecucion_markup():
    """Submenú Ejecución (sin 'Solo Pega')."""
    return {
        "inline_keyboard": [
            [{"text": "▶️ Iniciar Completo", "callback_data": "cmd_inicio"}],
            [{"text": "🔁 Configurar Loop", "callback_data": "cmd_loop_menu"}],
            [{"text": "⏹️ Detener Ejecución", "callback_data": "cmd_detener"}],
            [{"text": "🏠 Menú Principal", "callback_data": "menu_principal"}]
        ]
    }

def get_menu_loop_markup():
    """Submenú de selección de Loop."""
    return {
        "inline_keyboard": [
            [{"text": "⚡ 5 Iteraciones", "callback_data": "loop_count_5"}, {"text": "⏱️ 1 Hora", "callback_data": "loop_timed_1.0"}],
            [{"text": "⏱️ 2 Horas", "callback_data": "loop_timed_2.0"}, {"text": "🔄 Infinito", "callback_data": "loop_infinite"}],
            [{"text": "⬅️ Volver a Ejecución", "callback_data": "sec_ejecucion"}]
        ]
    }

def get_menu_reportes_markup():
    """Submenú Reportes y Consultas."""
    return {
        "inline_keyboard": [
            [
                {"text": "📊 Ver Casos (BD)", "callback_data": "cmd_ver_casos_bd"},
                {"text": "📈 Contar en RIS (RPA)", "callback_data": "cmd_casos"}
            ],
            [
                {"text": "📑 Resumen del Día", "callback_data": "cmd_resumen"},
                {"text": "📥 Exportar Excel", "callback_data": "cmd_menu_excel"}
            ],
            [{"text": "🏥 Estado PACS", "callback_data": "cmd_estado_pacs"}],
            [{"text": "🏠 Menú Principal", "callback_data": "menu_principal"}]
        ]
    }

def get_menu_periodo_excel_markup():
    """Submenú de Selección de Periodo para Reporte Excel."""
    return {
        "inline_keyboard": [
            [{"text": "📅 Día en curso", "callback_data": "rep_excel_hoy"}],
            [{"text": "🗓️ Últimos 7 días", "callback_data": "rep_excel_7d"}],
            [{"text": "📆 Mes actual", "callback_data": "rep_excel_mes"}],
            [{"text": "⬅️ Volver a Reportes", "callback_data": "sec_reportes"}]
        ]
    }

def get_menu_sistema_markup():
    """Submenú Diagnóstico y Mantenimiento."""
    return {
        "inline_keyboard": [
            [{"text": "📸 Estado Actual + Captura", "callback_data": "cmd_estado_actual"}],
            [{"text": "🔋 Estado Batería", "callback_data": "cmd_bateria"}],
            [{"text": "📜 Ver Últimos Logs", "callback_data": "cmd_ver_log"}],
            [{"text": "🔄 Rehabilitar Registro", "callback_data": "cmd_rehabilitar"}],
            [{"text": "🏠 Menú Principal", "callback_data": "menu_principal"}]
        ]
    }

def get_menu_notificaciones_markup():
    """Submenú Notificaciones y Alertas."""
    return {
        "inline_keyboard": [
            [
                {"text": "🔕 Pausar Alertas", "callback_data": "cmd_deten_notif"},
                {"text": "🔔 Reanudar Alertas", "callback_data": "cmd_reanudar_notif"}
            ],
            [{"text": "🏠 Menú Principal", "callback_data": "menu_principal"}]
        ]
    }

# =========================================================================
# Envío y Edición de Mensajes y Callbacks
# =========================================================================

def enviar_mensaje(chat_id, texto, reply_markup=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": texto, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        res = requests.post(url, json=payload, timeout=15).json()
        return res.get("ok", False)
    except Exception as e:
        print(f"Error en enviar_mensaje: {e}")
        return False

def editar_mensaje(chat_id, message_id, texto, reply_markup=None):
    """Edita un mensaje existente en el chat (navegación fluida)."""
    url = f"https://api.telegram.org/bot{TOKEN}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": texto,
        "parse_mode": "HTML"
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    try:
        res = requests.post(url, json=payload, timeout=10).json()
        return res.get("ok", False)
    except Exception as e:
        print(f"Error en editar_mensaje: {e}")
        return False

def responder_callback(callback_id, text=None, show_alert=False):
    """Responde al evento callback para ocultar el icono de carga en Telegram."""
    url = f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery"
    payload = {"callback_query_id": callback_id, "show_alert": show_alert}
    if text:
        payload["text"] = text
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception:
        pass

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
        res = requests.post(url, data=data, files=files, timeout=30).json()
        if not res.get("ok"):
            print(f"  [Telegram API Error] sendPhoto: {res.get('description', res)}")
        return res.get("ok", False)
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
    """Envía un video a un chat de Telegram."""
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
            
        print(f"  [Telegram API Info] sendVideo falló ({res.get('description')}), intentando sendDocument...")
        opened_file.seek(0)
        url_doc = f"https://api.telegram.org/bot{TOKEN}/sendDocument"
        files_doc = {"document": (os.path.basename(ruta_video), opened_file)}
        res_doc = requests.post(url_doc, data=data, files=files_doc, timeout=60).json()
        return res_doc.get("ok", False)
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

def enviar_documento(chat_id, ruta_documento, caption=""):
    """Envía un archivo/documento (ej. Excel .xlsx) a un chat de Telegram."""
    if not os.path.exists(ruta_documento):
        print(f"Error: El archivo no existe: {ruta_documento}")
        return False

    url = f"https://api.telegram.org/bot{TOKEN}/sendDocument"
    data = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}

    opened_file = None
    try:
        opened_file = open(ruta_documento, "rb")
        files = {"document": (os.path.basename(ruta_documento), opened_file)}
        res = requests.post(url, data=data, files=files, timeout=60).json()
        if not res.get("ok"):
            print(f"  [Telegram API Error] sendDocument: {res.get('description', res)}")
        return res.get("ok", False)
    except Exception as e:
        print(f"Error enviando documento a {chat_id}: {e}")
        return False
    finally:
        if opened_file:
            opened_file.close()

def enviar_documento_todos(ruta_documento, caption=""):
    """Envía un documento con mensaje a todos los usuarios registrados."""
    usuarios = cargar_usuarios()
    if not usuarios:
        print("Error: No hay usuarios registrados en usuarios.json.")
        return False

    print(f"Enviando documento a {len(usuarios)} suscriptores...")
    exito = True
    for chat_id in usuarios:
        if enviar_documento(chat_id, ruta_documento, caption):
            print(f"  [OK] Documento enviado a {chat_id}")
        else:
            print(f"  [Error] No se pudo enviar documento a {chat_id}")
            exito = False
    return exito

if __name__ == "__main__":
    if len(sys.argv) > 1:
        texto_alerta = " ".join(sys.argv[1:])
        enviar_alerta_todos(texto_alerta)
    else:
        print("Uso:")
        print("  python telegram_manager.py 'Tu mensaje'      # Para enviar alerta a todos")