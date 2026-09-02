"""
Script de autenticacion unica para Telethon.
Genera un archivo .session que se reutiliza automaticamente.

Ejecutar una sola vez:
    python scripts/setup_telethon_session.py
"""
import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from telethon import TelegramClient

API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")

# El archivo de sesion se guarda en la raiz del proyecto
SESSION_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "telegram_user_session"
)

async def main():
    print("=" * 50)
    print("  CONFIGURACION DE SESION TELETHON")
    print("=" * 50)
    print()
    print(f"API ID: {API_ID}")
    print(f"API Hash: {API_HASH[:8]}...")
    print(f"Archivo de sesion: {SESSION_PATH}.session")
    print()
    
    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
    
    await client.start()
    
    me = await client.get_me()
    print()
    print("=" * 50)
    print(f"  SESION CREADA EXITOSAMENTE!")
    print(f"  Usuario: {me.first_name} {me.last_name or ''}")
    print(f"  Telefono: +{me.phone}")
    print(f"  ID: {me.id}")
    print("=" * 50)
    print()
    print(f"El archivo '{SESSION_PATH}.session' se ha guardado.")
    print("No necesitas ejecutar esto de nuevo.")
    
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
