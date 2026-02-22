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

def registrar_usuarios():
    """
    Escucha mensajes nuevos para registrar usuarios/grupos que usen /start.
    Implementación 'lite' usando requests (basada en tu documentación).
    """
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
                    
                    # Manejar mensajes
                    message = update.get("message")
                    if not message: continue
                    
                    chat = message.get("chat")
                    chat_id = chat.get("id")
                    text = message.get("text", "")
                    chat_title = chat.get("title") or chat.get("first_name", "Usuario")
                    
                    if text == "/start":
                        if chat_id not in usuarios:
                            usuarios.append(chat_id)
                            guardar_usuarios(usuarios)
                            print(f"[OK] Nuevo suscriptor: {chat_title} (ID: {chat_id})")
                            enviar_mensaje(chat_id, f"Te has suscrito a las alertas de Atrys RPA en {chat_title}.")
                        else:
                            enviar_mensaje(chat_id, "Ya estás suscrito.")
                            
                    elif text == "/stop":
                        if chat_id in usuarios:
                            usuarios.remove(chat_id)
                            guardar_usuarios(usuarios)
                            print(f"[X] Desuscrito: {chat_title} (ID: {chat_id})")
                            enviar_mensaje(chat_id, "Te has desuscrito de las alertas.")
            
            time.sleep(1)
        except KeyboardInterrupt:
            print("\nDeteniendo escucha...")
            break
        except Exception as e:
            print(f"Error en polling: {e}")
            time.sleep(5)

def enviar_mensaje(chat_id, texto):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": texto, "parse_mode": "HTML"}
    try:
        res = requests.post(url, data=payload).json()
        return res.get("ok")
    except:
        return False

def enviar_alerta_todos(mensaje):
    """Envía un mensaje a todos los usuarios registrados."""
    usuarios = cargar_usuarios()
    if not usuarios:
        print("Error: No hay usuarios registrados en usuarios.json. Ejecuta el script con --listen primero.")
        return

    print(f"Enviando alerta a {len(usuarios)} suscriptores...")
    for chat_id in usuarios:
        if enviar_mensaje(chat_id, mensaje):
            print(f"  [OK] Enviado a {chat_id}")
        else:
            print(f"  [Error] No se pudo enviar a {chat_id}")

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
