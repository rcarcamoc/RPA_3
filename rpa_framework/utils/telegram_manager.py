import requests
import json
import time
import sys
import subprocess
import os
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
    except Exception as e:
        return None

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
            print(f"[WARN] No se pudo configurar comandos de Telegram (posible bloqueo de red).")
    except Exception as e:
        print(f"Error en configurar_menu_comandos: {e}")

# =========================================================================
# Generadores de Teclados Inline para Menús y Submenús
# =========================================================================

def get_menu_principal_markup():
    """Panel Principal con accesos rápidos directos y categorías operativas."""
    return {
        "inline_keyboard": [
            [{"text": "🔴 Transmitir pantalla (Stream)", "callback_data": "cmd_stream_menu"}],
            [{"text": "🚀 Iniciar ejecuciones", "callback_data": "sec_ejecucion"}],
            [{"text": "📊 Reportes y consultas", "callback_data": "sec_reportes"}],
            [{"text": "🛠️ Herramientas del sistema", "callback_data": "sec_sistema"}],
            [{"text": "🔍 Contar casos directo en RIS", "callback_data": "cmd_casos"}],
            [{"text": "🛑 Detener todo (Emergencia)", "callback_data": "cmd_detener"}]
        ]
    }

def get_menu_ejecucion_markup():
    """Submenú Iniciar ejecuciones."""
    return {
        "inline_keyboard": [
            [{"text": "⚡ Flujo Optimizado V2 (Pipeline Rápido)", "callback_data": "sec_v2"}],
            [{"text": "▶️ Ejecutar 1 vez (Flujo completo V1)", "callback_data": "cmd_inicio"}],
            [{"text": "📋 Ejecutar solo carga (Integra)", "callback_data": "cmd_pega_integra"}],
            [{"text": "🔄 Reintentar un caso con error", "callback_data": "cmd_revalidar"}],
            [{"text": "🔁 Ejecución con repeticiones (V1)", "callback_data": "cmd_loop_menu"}],
            [{"text": "🛑 Detener proceso actual", "callback_data": "cmd_detener"}],
            [{"text": "🏠 Menú Principal", "callback_data": "menu_principal"}]
        ]
    }

def get_menu_v2_markup():
    """Submenú Flujo Optimizado V2."""
    return {
        "inline_keyboard": [
            [{"text": "▶️ Ejecutar 1 vez (Sub_work V2)", "callback_data": "cmd_inicio_v2"}],
            [{"text": "🔁 Bucle Continuo V2 (loop_v2)", "callback_data": "cmd_loop_v2_menu"}],
            [{"text": "📋 Solo PACS V2", "callback_data": "cmd_pacs_v2"}],
            [
                {"text": "⬅️ Volver a Ejecuciones", "callback_data": "sec_ejecucion"},
                {"text": "🏠 Menú Principal", "callback_data": "menu_principal"}
            ]
        ]
    }

def get_menu_loop_v2_markup():
    """Submenú Bucle Continuo V2 con repeticiones."""
    return {
        "inline_keyboard": [
            [{"text": "⚡ 5 veces", "callback_data": "loop_v2_count_5"}, {"text": "⏱️ Durante 1 hora", "callback_data": "loop_v2_timed_1.0"}],
            [{"text": "⏱️ Durante 2 horas", "callback_data": "loop_v2_timed_2.0"}, {"text": "🔄 Continuo (Sin parar)", "callback_data": "loop_v2_infinite"}],
            [
                {"text": "⬅️ Volver a Flujo V2", "callback_data": "sec_v2"},
                {"text": "🏠 Menú Principal", "callback_data": "menu_principal"}
            ]
        ]
    }

def get_menu_revalidar_markup(registros):
    """
    Genera el teclado inline para seleccionar cuál de los registros en error
    debe quedar en estado 'En Proceso'.
    """
    keyboard = []
    for reg in registros:
        r_id = reg.get("id")
        doc = str(reg.get("numero_documento") or "--").strip()
        btn_text = f"🔄 #{r_id} • Doc: {doc}"
        keyboard.append([{"text": btn_text, "callback_data": f"reval_set_{r_id}"}])
    
    keyboard.append([
        {"text": "⬅️ Volver a Ejecuciones", "callback_data": "sec_ejecucion"},
        {"text": "🏠 Menú Principal", "callback_data": "menu_principal"}
    ])
    return {"inline_keyboard": keyboard}

def get_menu_post_revalidar_markup(registro_id):
    """Submenú ofrecido tras marcar un registro como 'En Proceso'."""
    return {
        "inline_keyboard": [
            [
                {"text": "⚡ Ejecutar con V2 (Rápido)", "callback_data": "cmd_inicio_v2"},
                {"text": "▶️ Ejecutar con V1", "callback_data": "cmd_inicio"}
            ],
            [{"text": "📋 Ejecutar solo carga (Integra)", "callback_data": "cmd_pega_integra"}],
            [{"text": "🔄 Ver otros errores", "callback_data": "cmd_revalidar"}],
            [
                {"text": "⬅️ Volver a Ejecuciones", "callback_data": "sec_ejecucion"},
                {"text": "🏠 Menú Principal", "callback_data": "menu_principal"}
            ]
        ]
    }

def get_menu_loop_markup():
    """Submenú Ejecución con repeticiones."""
    return {
        "inline_keyboard": [
            [{"text": "⚡ 5 veces", "callback_data": "loop_count_5"}, {"text": "⏱️ Durante 1 hora", "callback_data": "loop_timed_1.0"}],
            [{"text": "⏱️ Durante 2 horas", "callback_data": "loop_timed_2.0"}, {"text": "🔄 Continuo (Sin parar)", "callback_data": "loop_infinite"}],
            [
                {"text": "⬅️ Volver a Ejecuciones", "callback_data": "sec_ejecucion"},
                {"text": "🏠 Menú Principal", "callback_data": "menu_principal"}
            ]
        ]
    }

def get_menu_reportes_markup():
    """Submenú Reportes y Consultas."""
    return {
        "inline_keyboard": [
            [
                {"text": "📑 Resumen del día", "callback_data": "cmd_resumen"},
                {"text": "📥 Descargar reporte Excel", "callback_data": "cmd_menu_excel"}
            ],
            [
                {"text": "🔍 Contar casos directo en RIS", "callback_data": "cmd_casos"},
                {"text": "🏥 Ver estado de PACS", "callback_data": "cmd_estado_pacs"}
            ],
            [{"text": "🏠 Menú Principal", "callback_data": "menu_principal"}]
        ]
    }

def get_menu_periodo_excel_markup():
    """Submenú de Selección de Periodo para Reporte Excel."""
    return {
        "inline_keyboard": [
            [{"text": "📅 Día de hoy", "callback_data": "rep_excel_hoy"}],
            [{"text": "🗓️ Últimos 7 días", "callback_data": "rep_excel_7d"}],
            [{"text": "📆 Mes actual", "callback_data": "rep_excel_mes"}],
            [
                {"text": "⬅️ Volver a Reportes", "callback_data": "sec_reportes"},
                {"text": "🏠 Menú Principal", "callback_data": "menu_principal"}
            ]
        ]
    }

def get_menu_sistema_markup():
    """Submenú Herramientas del sistema."""
    return {
        "inline_keyboard": [
            [{"text": "📸 Foto de pantalla actual", "callback_data": "cmd_estado_actual"}],
            [{"text": "🩺 Probar conexión PACS ahora", "callback_data": "cmd_validar_pacs"}],
            [{"text": "📜 Ver últimas actividades (Logs)", "callback_data": "cmd_ver_log"}],
            [{"text": "🔋 Nivel de batería y energía", "callback_data": "cmd_bateria"}],
            [{"text": "🔔 Pausar o activar alertas", "callback_data": "sec_notificaciones"}],
            [{"text": "🏠 Menú Principal", "callback_data": "menu_principal"}]
        ]
    }

def get_live_status_markup(stream_activo=False):
    """Teclado inline adjunto a la foto o diagnóstico en vivo."""
    if stream_activo:
        stream_btn = {"text": "🛑 Detener Transmisión", "callback_data": "cmd_detener_stream"}
    else:
        stream_btn = {"text": "🔴 Transmitir pantalla (Stream)", "callback_data": "cmd_iniciar_stream"}
    
    return {
        "inline_keyboard": [
            [stream_btn],
            [
                {"text": "🔄 Actualizar foto", "callback_data": "cmd_estado_actual"},
                {"text": "🏠 Menú Principal", "callback_data": "menu_principal"}
            ]
        ]
    }

def get_menu_stream_markup(stream_activo=False, tiempo_str="00:00"):
    """Submenú de control de Transmisión de Pantalla (Live Stream)."""
    if stream_activo:
        return {
            "inline_keyboard": [
                [{"text": "🛑 Detener Transmisión de Pantalla", "callback_data": "cmd_detener_stream"}],
                [{"text": "📸 Foto de pantalla actual", "callback_data": "cmd_estado_actual"}],
                [
                    {"text": "⬅️ Volver a Herramientas", "callback_data": "sec_sistema"},
                    {"text": "🏠 Menú Principal", "callback_data": "menu_principal"}
                ]
            ]
        }
    else:
        return {
            "inline_keyboard": [
                [{"text": "🔴 Iniciar transmisión (10 min / Fin de flujo)", "callback_data": "cmd_iniciar_stream_600"}],
                [{"text": "🔴 Iniciar transmisión continua", "callback_data": "cmd_iniciar_stream_inf"}],
                [
                    {"text": "⬅️ Volver a Herramientas", "callback_data": "sec_sistema"},
                    {"text": "🏠 Menú Principal", "callback_data": "menu_principal"}
                ]
            ]
        }

def get_menu_notificaciones_markup():
    """Submenú Pausar o activar alertas."""
    return {
        "inline_keyboard": [
            [
                {"text": "🔕 Pausar alertas automáticas", "callback_data": "cmd_deten_notif"},
                {"text": "🔔 Activar alertas automáticas", "callback_data": "cmd_reanudar_notif"}
            ],
            [
                {"text": "⬅️ Volver a Herramientas", "callback_data": "sec_sistema"},
                {"text": "🏠 Menú Principal", "callback_data": "menu_principal"}
            ]
        ]
    }

# =========================================================================
# Envío y Edición de Mensajes y Callbacks
# =========================================================================

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

    markup = {
        "inline_keyboard": [
            [
                {"text": "▶️ Reanudar Loop", "callback_data": "loop_reanudar"},
                {"text": "⏹️ Detener definitivamente", "callback_data": "loop_detener"}
            ]
        ]
    }

    print(f"Enviando alerta de Loop Pausado a {len(usuarios)} usuarios...")
    for chat_id in usuarios:
        enviar_mensaje(chat_id, mensaje, markup)
    return True


def enviar_foto(chat_id, ruta_imagen, caption="", reply_markup=None):
    """Envía una foto a un chat. Si el archivo es muy grande, la comprime antes."""
    import json
    url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
    data = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)

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

if __name__ == "__main__":
    if len(sys.argv) > 1:
        texto_alerta = " ".join(sys.argv[1:])
        enviar_alerta_todos(texto_alerta)
    else:
        print("Uso:")
        print("  python telegram_manager.py 'Tu mensaje'      # Para enviar alerta a todos")