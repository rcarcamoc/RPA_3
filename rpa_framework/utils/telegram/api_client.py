"""
Cliente HTTP y funciones de envío para la API de Telegram.
"""
import io
import json
import os
import sys
import time
import requests
import urllib3
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

# Configuración
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
if not TOKEN:
    print("Warning: TELEGRAM_BOT_TOKEN environment variable not set. Please create a .env file with the token.")

TELEGRAM_BASE_URL = os.environ.get("TELEGRAM_API_URL", "https://api.telegram.org").rstrip("/")
_telegram_session = requests.Session()
_telegram_session.verify = False

_last_fw_warning = 0

# Apunta a rpa_framework/utils/usuarios.json (directorio padre de utils/telegram/)
UTILS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USUARIOS_FILE = os.path.join(UTILS_DIR, "usuarios.json")


def telegram_request(method: str, endpoint: str, **kwargs):
    """
    Ejecuta peticiones seguras a la API de Telegram.
    Soporta bypass SSL (para proxies corporativos e inspección Fortinet),
    URL base personalizada si se usa proxy, y maneja de forma limpia
    los bloqueos de filtro web corporativo (ej. FortiGuard 403).
    """
    global _last_fw_warning
    url = f"{TELEGRAM_BASE_URL}/bot{TOKEN}/{endpoint.lstrip('/')}"
    if "timeout" not in kwargs:
        kwargs["timeout"] = 15

    try:
        resp = _telegram_session.request(method, url, **kwargs)
        if resp.status_code == 403 and "forti" in resp.text.lower():
            now = time.time()
            if now - _last_fw_warning > 60:
                print("⚠️ [Firewall] Tráfico a Telegram bloqueado por política de seguridad corporativa (FortiGuard: Instant Messaging).")
                _last_fw_warning = now
            return None

        try:
            return resp.json()
        except Exception:
            return None
    except requests.exceptions.SSLError as e:
        now = time.time()
        if now - _last_fw_warning > 60:
            print(f"⚠️ [SSL Error] No se pudo verificar el certificado con Telegram/Firewall: {e}")
            _last_fw_warning = now
        return None
    except Exception:
        return None


def cargar_usuarios():
    if os.path.exists(USUARIOS_FILE):
        try:
            with open(USUARIOS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []


def guardar_usuarios(usuarios):
    with open(USUARIOS_FILE, 'w', encoding='utf-8') as f:
        json.dump(usuarios, f, indent=4)


def configurar_menu_comandos():
    """Configura el menú nativo de comandos en Telegram (organizado con accesos esenciales)."""
    commands = [
        {"command": "menu", "description": "🎛️ Panel de control principal"},
        {"command": "ejecucion", "description": "🚀 Iniciar ejecuciones"},
        {"command": "v2", "description": "⚡ Flujo optimizado V2 (Pipeline)"},
        {"command": "stream", "description": "🔴 Estado actual y transmitir pantalla"},
        {"command": "revalidar", "description": "🔄 Reintentar casos con error"},
        {"command": "casos", "description": "🔍 Contar casos directo en RIS"},
        {"command": "detener", "description": "🛑 Detener cualquier proceso"}
    ]
    try:
        res = telegram_request("POST", "setMyCommands", json={"commands": commands}, timeout=10)
        if res and res.get("ok"):
            print("[OK] Menu de comandos de Telegram configurado exitosamente.")
        else:
            print("[WARN] No se pudo configurar comandos de Telegram (posible bloqueo de red).")
    except Exception as e:
        print(f"Error en configurar_menu_comandos: {e}")


def enviar_mensaje(chat_id, texto, reply_markup=None):
    payload = {"chat_id": chat_id, "text": texto, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        res = telegram_request("POST", "sendMessage", json=payload, timeout=15)
        return res.get("ok", False) if res else False
    except Exception as e:
        print(f"Error en enviar_mensaje: {e}")
        return False


def editar_mensaje(chat_id, message_id, texto, reply_markup=None):
    """Edita un mensaje existente en el chat (navegación fluida)."""
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": texto,
        "parse_mode": "HTML"
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    try:
        res = telegram_request("POST", "editMessageText", json=payload, timeout=10)
        return res.get("ok", False) if res else False
    except Exception as e:
        print(f"Error en editar_mensaje: {e}")
        return False


def responder_callback(callback_id, text=None, show_alert=False):
    """Responde al evento callback para ocultar el icono de carga en Telegram."""
    payload = {"callback_query_id": callback_id, "show_alert": show_alert}
    if text:
        payload["text"] = text
    try:
        telegram_request("POST", "answerCallbackQuery", json=payload, timeout=5)
    except Exception:
        pass


def enviar_mensaje_todos(texto, reply_markup=None):
    """Envía un mensaje formateado a todos los usuarios registrados."""
    usuarios = cargar_usuarios()
    if not usuarios:
        print("Error: No hay usuarios registrados en usuarios.json.")
        return False
    exito = True
    for chat_id in usuarios:
        if not enviar_mensaje(chat_id, texto, reply_markup):
            exito = False
    return exito


def enviar_alerta_todos(mensaje, record_id=None):
    """Envía un mensaje a todos los usuarios registrados, opcionalmente con un botón para gestionarlo."""
    usuarios = cargar_usuarios()
    if not usuarios:
        print("Error: No hay usuarios registrados en usuarios.json. Ejecuta el script con --listen primero.")
        return

    # Asegurar que se incluya la resolución de pantalla si no fue añadida previamente
    if "resoluci" not in mensaje.lower():
        try:
            from utils.screen_utils import get_screen_resolution
            res_str = get_screen_resolution()
        except ImportError:
            try:
                from rpa_framework.utils.screen_utils import get_screen_resolution
                res_str = get_screen_resolution()
            except Exception:
                res_str = "1920x1080"
        except Exception:
            res_str = "1920x1080"
        mensaje = f"{mensaje}\n\n🖥️ <b>Resolución:</b> <code>{res_str}</code>"

    reply_markup = None
    if record_id:
        if not any(tag in mensaje for tag in ["ID Fila", "ID BD", "ID de la fila", "ID Registro", f"#{record_id}"]):
            mensaje = f"{mensaje}\n\n🆔 <b>ID Fila BD:</b> <code>{record_id}</code>"

        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": "🔄 Reprocesar Caso", "callback_data": f"reproc_pacs_{record_id}"}
                ],
                [
                    {"text": "✅ Marcar Gestionado", "callback_data": f"gest_normal_{record_id}"}
                ],
                [
                    {"text": "📝 Addendum", "callback_data": f"gest_addendum_{record_id}"},
                    {"text": "🔁 Ya Ingresado", "callback_data": f"gest_ya_ingresado_{record_id}"}
                ]
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


def notificar_loop_pausado(ultimo_error: str = "", workflow_name: str = "Loop", iteracion: int = 0, record_id: int = None):
    """Envía alerta de pausa por 2 errores consecutivos en loop con botones para Reanudar o Detener."""
    usuarios = cargar_usuarios()
    if not usuarios:
        print("Error: No hay usuarios registrados en usuarios.json.")
        return False

    lineas = [
        "⏸️ <b>ALERTA: LOOP PAUSADO POR SEGURIDAD</b>",
        "",
        "⚠️ Se han detectado <b>2 errores consecutivos</b> en la ejecución del ciclo.",
        f"🔄 <b>Workflow:</b> <code>{workflow_name}</code> (Iteración #{iteracion})",
    ]
    if record_id:
        lineas.append(f"🆔 <b>ID Fila BD:</b> <code>{record_id}</code>")
    if ultimo_error:
        lineas.extend([
            "",
            "📋 <b>Último error registrado:</b>",
            f"<code>{ultimo_error[:300]}</code>",
        ])
    lineas.extend([
        "",
        "¿Qué deseas hacer a continuación?"
    ])
    mensaje = "\n".join(lineas)

    inline_k = []
    if record_id:
        inline_k.append([{"text": f"🔄 Reprocesar #{record_id} en PACS", "callback_data": f"reproc_pacs_{record_id}"}])
    inline_k.append([
        {"text": "▶️ Reanudar Loop", "callback_data": "loop_reanudar"},
        {"text": "⏹️ Detener definitivamente", "callback_data": "loop_detener"}
    ])
    markup = {"inline_keyboard": inline_k}

    print(f"Enviando alerta de Loop Pausado a {len(usuarios)} usuarios...")
    for chat_id in usuarios:
        enviar_mensaje(chat_id, mensaje, markup)
    return True


def enviar_foto(chat_id, ruta_imagen, caption="", reply_markup=None):
    """Envía una foto a un chat. Si el archivo es muy grande, la comprime antes."""
    data = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)

    opened_file = None
    files = {}
    try:
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
        res = telegram_request("POST", "sendPhoto", data=data, files=files, timeout=30)
        if res and not res.get("ok"):
            print(f"  [Telegram API Error] sendPhoto: {res.get('description', res)}")
        return res.get("ok", False) if res else False
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

    data = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}

    opened_file = None
    try:
        opened_file = open(ruta_video, "rb")
        files = {"video": (os.path.basename(ruta_video), opened_file, "video/mp4")}
        res = telegram_request("POST", "sendVideo", data=data, files=files, timeout=60)
        if res and res.get("ok"):
            return True

        print(f"  [Telegram API Info] sendVideo falló ({res.get('description') if res else 'Sin respuesta'}), intentando sendDocument...")
        opened_file.seek(0)
        files_doc = {"document": (os.path.basename(ruta_video), opened_file)}
        res_doc = telegram_request("POST", "sendDocument", data=data, files=files_doc, timeout=60)
        return res_doc.get("ok", False) if res_doc else False
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

    if caption and ("error" in caption.lower() or "alerta" in caption.lower()) and "resoluci" not in caption.lower():
        try:
            from utils.screen_utils import get_screen_resolution
            res_str = get_screen_resolution()
        except ImportError:
            try:
                from rpa_framework.utils.screen_utils import get_screen_resolution
                res_str = get_screen_resolution()
            except Exception:
                res_str = "1920x1080"
        except Exception:
            res_str = "1920x1080"
        caption = f"{caption}\n🖥️ <b>Resolución:</b> <code>{res_str}</code>"

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

    data = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}

    opened_file = None
    try:
        opened_file = open(ruta_documento, "rb")
        files = {"document": (os.path.basename(ruta_documento), opened_file)}
        res = telegram_request("POST", "sendDocument", data=data, files=files, timeout=60)
        if res and not res.get("ok"):
            print(f"  [Telegram API Error] sendDocument: {res.get('description', res)}")
        return res.get("ok", False) if res else False
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
