import sys
import os
if sys.stdout is not None:
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
if sys.stderr is not None:
    try: sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
import time
from pathlib import Path
from dotenv import load_dotenv

# Configurar rutas del proyecto
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "rpa_framework"))

load_dotenv(dotenv_path=ROOT_DIR / ".env")

from utils.stream_manager import stream_manager

def main():
    print("=" * 60)
    print("📡 TEST DE TRANSMISIÓN EN VIVO A TELEGRAM (RTMP)")
    print("=" * 60)
    
    stream_url = os.environ.get("TELEGRAM_STREAM_URL", "rtmps://dc4-1.rtmp.t.me/s/")
    stream_key = os.environ.get("TELEGRAM_STREAM_KEY", "")
    
    print(f"• URL del Servidor: {stream_url}")
    print(f"• Clave (Stream Key): {'*' * len(stream_key) if stream_key else '❌ NO CONFIGURADA EN .env'}")
    
    if not stream_key:
        print("\n⚠️ Por favor, abre tu archivo .env y agrega la línea:")
        print("TELEGRAM_STREAM_KEY=tu_stream_key_aqui\n")
        print("Para obtenerla:")
        print("1. En tu grupo de Telegram, ve al menú superior (3 puntos) y elige 'Iniciar videochat' / 'Transmitir con...'")
        print("2. Copia la 'Clave de transmisión' (Stream Key) y pégala en tu archivo .env")
        return

    duracion = 30
    if len(sys.argv) > 1:
        try:
            duracion = int(sys.argv[1])
        except ValueError:
            pass

    print(f"\n🚀 Iniciando transmisión de prueba por {duracion} segundos...")
    exito, msg = stream_manager.iniciar_transmision(duracion_max_segundos=duracion)
    
    if not exito:
        print(f"❌ Error: {msg}")
        return

    print("✅ Transmisión iniciada.")
    print("👉 Abre tu grupo de Telegram ahora mismo. Deberías ver la transmisión en vivo en la parte superior del grupo.\n")

    try:
        start_t = time.time()
        while stream_manager.esta_activo():
            transcurrido = int(time.time() - start_t)
            restante = max(0, duracion - transcurrido)
            print(f"\r🔴 En vivo... Tiempo: {stream_manager.tiempo_transcurrido_str()} | Restante: {restante}s  (Ctrl+C para detener)", end="", flush=True)
            time.sleep(1)
            if transcurrido >= duracion:
                break
    except KeyboardInterrupt:
        print("\n\n🛑 Deteniendo transmisión...")
    finally:
        stream_manager.detener_transmision()
        print("\n🏁 Prueba completada.")

if __name__ == "__main__":
    main()
