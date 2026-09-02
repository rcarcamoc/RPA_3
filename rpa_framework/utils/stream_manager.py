"""
Gestor de transmision en vivo (Live Stream) hacia canales/grupos de Telegram via RTMP/RTMPS y Telethon.
Permite iniciar transmisiones de pantalla bajo demanda o vinculadas a workflows RPA.
"""
import os
import sys
import time
import threading
import subprocess
import asyncio
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

try:
    import imageio_ffmpeg
    FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_EXE = "ffmpeg"

API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
SESSION_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "telegram_user_session"
)
DEFAULT_CHAT_ID = -1003969784801


class TelegramStreamManager:
    """
    Gestor de streaming en vivo de escritorio hacia Telegram (Videochat / Live Stream).
    Soporta obtencion automatica de credenciales RTMP via Telethon (MTProto)
    o uso de variables de entorno estaticas.
    """

    def __init__(self, fps=15, bitrate="1800k"):
        self.fps = fps
        self.bitrate = bitrate
        self._process = None
        self._thread = None
        self._stop_event = threading.Event()
        self._lock = threading.RLock()
        self._start_time = 0
        self._last_status = "Inactivo"
        self._on_stop_callback = None
        self._stop_checker = None
        self._finish_reason = "tiempo"

    def _worker_stream(self, target_rtmp: str, duracion_max_segundos: int | None):
        """Hilo dedicado de captura directa en tiempo real y emisión RTMP de cero latencia."""
        import mss
        import ctypes
        from ctypes import wintypes

        # Vincular este hilo de trabajo al escritorio activo de Windows
        user32 = ctypes.windll.user32
        user32.OpenInputDesktop.restype = wintypes.HANDLE
        user32.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        user32.SetThreadDesktop.restype = wintypes.BOOL
        user32.SetThreadDesktop.argtypes = [wintypes.HANDLE]

        hDesk = None
        try:
            hDesk = user32.OpenInputDesktop(0, False, 0x01FF)
            if hDesk:
                user32.SetThreadDesktop(hDesk)
        except Exception:
            pass

        # Obtener resolución de entrada
        with mss.mss() as sct:
            mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            w, h = mon["width"], mon["height"]
        w = w if w % 2 == 0 else w - 1
        h = h if h % 2 == 0 else h - 1

        # Comando FFmpeg optimizado para transmisión fluida de pantalla en vivo
        cmd = [
            FFMPEG_EXE,
            "-y",
            "-f", "rawvideo",
            "-vcodec", "rawvideo",
            "-s", f"{w}x{h}",
            "-pix_fmt", "bgra",
            "-r", str(self.fps),
            "-i", "-",
            "-f", "lavfi",
            "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-vf", "scale=1280:720",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-tune", "zerolatency",
            "-bf", "0",
            "-pix_fmt", "yuv420p",
            "-g", str(self.fps * 2),
            "-b:v", self.bitrate,
            "-maxrate", self.bitrate,
            "-bufsize", "3600k",
            "-c:a", "aac",
            "-b:a", "128k",
            "-ar", "48000",
            "-ac", "2",
            "-shortest",
            "-f", "flv",
            target_rtmp
        ]

        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

        try:
            self._process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                creationflags=creation_flags
            )
        except Exception as e:
            print(f"[StreamManager] Error iniciando FFmpeg: {e}", flush=True)
            if hDesk:
                try: ctypes.windll.user32.CloseDesktop(hDesk)
                except Exception: pass
            return

        frame_interval = 1.0 / self.fps
        start_ts = time.time()

        try:
            with mss.mss() as sct:
                target_mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                while not self._stop_event.is_set():
                    if duracion_max_segundos and (time.time() - start_ts) >= duracion_max_segundos:
                        self._finish_reason = "tiempo"
                        break

                    if self._stop_checker:
                        try:
                            should_stop, reason = self._stop_checker()
                            if should_stop:
                                self._finish_reason = reason or "workflow"
                                break
                        except Exception as e_chk:
                            print(f"[StreamManager] Error en stop_checker: {e_chk}", flush=True)

                    if self._process.poll() is not None:
                        print(f"[StreamManager] FFmpeg finalizó (código {self._process.returncode})", flush=True)
                        self._finish_reason = "error"
                        break

                    t_start = time.perf_counter()
                    shot = sct.grab(target_mon)

                    try:
                        self._process.stdin.write(shot.raw)
                    except (BrokenPipeError, OSError):
                        break

                    elapsed = time.perf_counter() - t_start
                    sleep_time = frame_interval - elapsed
                    if sleep_time > 0:
                        time.sleep(sleep_time)

        except Exception as e:
            print(f"[StreamManager] Error en bucle de emisión: {e}", flush=True)
            self._finish_reason = "error"
        finally:
            if hDesk:
                try: ctypes.windll.user32.CloseDesktop(hDesk)
                except Exception: pass

            proc = self._process
            if proc:
                try:
                    if proc.stdin:
                        proc.stdin.close()
                    proc.terminate()
                except Exception:
                    pass
            self._process = None
            self._start_time = 0
            print(f"[StreamManager] Transmisión finalizada (motivo: {self._finish_reason}).", flush=True)
            
            # Ejecutar callback si existe
            if self._on_stop_callback:
                try:
                    import inspect
                    sig = inspect.signature(self._on_stop_callback)
                    if len(sig.parameters) > 0:
                        self._on_stop_callback(self._finish_reason)
                    else:
                        self._on_stop_callback()
                except Exception as e_cb:
                    print(f"[StreamManager] Error en on_stop_callback: {e_cb}", flush=True)

    def esta_activo(self) -> bool:
        """Verifica si la transmision se encuentra activa."""
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                return True
            return False

    def tiempo_transcurrido_str(self) -> str:
        """Devuelve el tiempo transcurrido de transmision formateado (MM:SS)."""
        if not self.esta_activo() or self._start_time == 0:
            return "00:00"
        seg = int(time.time() - self._start_time)
        m = seg // 60
        s = seg % 60
        return f"{m:02d}:{s:02d}"

    def _obtener_credenciales_rtmp_telethon(self, chat_id=None) -> tuple[str, str]:
        """Obtiene la URL y clave RTMP usando la sesion autenticada de Telethon."""
        if not API_ID or not API_HASH:
            raise ValueError("No se han configurado TELEGRAM_API_ID o TELEGRAM_API_HASH.")
        
        import random
        from telethon import TelegramClient
        from telethon.tl.functions.phone import (
            CreateGroupCallRequest,
            GetGroupCallStreamRtmpUrlRequest,
        )
        from telethon.tl.functions.channels import GetFullChannelRequest

        target_chat = chat_id or DEFAULT_CHAT_ID

        async def _async_get():
            client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
            await client.connect()
            if not await client.is_user_authorized():
                await client.disconnect()
                raise ValueError("La sesión de Telethon no está autorizada.")
                
            try:
                entity = await client.get_entity(target_chat)
                full = await client(GetFullChannelRequest(entity))
                call = full.full_chat.call
                if not call:
                    print("[StreamManager] Creando Videochat RTMP...", flush=True)
                    await client(CreateGroupCallRequest(
                        peer=entity,
                        rtmp_stream=True,
                        random_id=random.randint(1, 2147483647),
                        title="Stream Atrys RPA"
                    ))
                print("[StreamManager] Obteniendo RTMP Stream URL...", flush=True)
                rtmp_info = await client(GetGroupCallStreamRtmpUrlRequest(
                    peer=entity,
                    revoke=False
                ))
                return rtmp_info.url, rtmp_info.key
            finally:
                await client.disconnect()

        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(_async_get())
        finally:
            loop.close()

    def iniciar_transmision(self, duracion_max_segundos=600, chat_id=None, on_stop=None, stop_checker=None) -> tuple[bool, str]:
        """
        Inicia la transmision en vivo de escritorio en segundo plano.
        
        Args:
            duracion_max_segundos: Limite de tiempo en segundos (por defecto 600s / 10 min). None para ilimitado.
            chat_id: ID del grupo de Telegram donde transmitir.
            on_stop: Callback opcional ejecutado al finalizar la transmision.
            stop_checker: Funcion opcional que retorna (bool, str) para detener anticipadamente la transmision (ej. fin de workflow).
            
        Returns:
            (exito, mensaje)
        """
        with self._lock:
            if self.esta_activo():
                return True, f"La transmision ya se encuentra activa ({self.tiempo_transcurrido_str()})."

            self._on_stop_callback = on_stop
            self._stop_checker = stop_checker
            self._finish_reason = "tiempo"

            # 1. Obtener URL y Key RTMP
            rtmp_url = None
            rtmp_key = None

            # Intentar primero con Telethon (automatizacion completa)
            try:
                print("[StreamManager] Consultando credenciales RTMP via Telethon...", flush=True)
                rtmp_url, rtmp_key = self._obtener_credenciales_rtmp_telethon(chat_id)
                print(f"[StreamManager] Telethon OK: {rtmp_url}", flush=True)
            except Exception as e_telethon:
                print(f"[StreamManager] Telethon no disponible ({e_telethon}), usando fallback .env...", flush=True)
                rtmp_url = os.environ.get("TELEGRAM_STREAM_URL", "")
                rtmp_key = os.environ.get("TELEGRAM_STREAM_KEY", "")

            if not rtmp_url or not rtmp_key:
                return False, "No se pudieron obtener las credenciales RTMP para la transmision."

            target_rtmp = f"{rtmp_url.rstrip('/')}/{rtmp_key}"

            self._stop_event.clear()
            self._start_time = time.time()

            self._thread = threading.Thread(
                target=self._worker_stream,
                args=(target_rtmp, duracion_max_segundos),
                daemon=True,
                name="TelegramLiveStreamWorker"
            )
            self._thread.start()

            # Esperar confirmacion de inicio (hasta 3.0s)
            for _ in range(30):
                time.sleep(0.1)
                if self.esta_activo():
                    break

            if self.esta_activo():
                dur_txt = f"{duracion_max_segundos}s" if duracion_max_segundos else "continuo"
                return True, f"Transmision en vivo iniciada ({dur_txt})."
            else:
                return False, "Error al iniciar el motor de transmision."

    def _cerrar_videochat_telethon(self, chat_id=None):
        """Cierra/descarta el Videochat en Telegram para que finalice la llamada en todos los clientes."""
        if not API_ID or not API_HASH:
            return
        from telethon import TelegramClient
        from telethon.tl.functions.channels import GetFullChannelRequest
        from telethon.tl.functions.phone import DiscardGroupCallRequest

        target_chat = chat_id or DEFAULT_CHAT_ID

        async def _async_discard():
            client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
            await client.connect()
            if not await client.is_user_authorized():
                await client.disconnect()
                return
            try:
                entity = await client.get_entity(target_chat)
                full = await client(GetFullChannelRequest(entity))
                call = full.full_chat.call
                if call:
                    await client(DiscardGroupCallRequest(call=call))
                    print("[StreamManager] Videochat cerrado exitosamente en Telegram.", flush=True)
            finally:
                await client.disconnect()

        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_async_discard())
        except Exception as e:
            print(f"[StreamManager] Info descartando videochat: {e}", flush=True)
        finally:
            loop.close()

    def detener_transmision(self, cerrar_videochat=True, chat_id=None) -> tuple[bool, str]:
        """Detiene la transmision en vivo si esta activa y cierra la llamada en Telegram."""
        with self._lock:
            self._finish_reason = "manual"
            self._stop_event.set()

            proc = self._process
            if proc:
                try:
                    if proc.stdin:
                        try: proc.stdin.close()
                        except Exception: pass
                    proc.kill()
                except Exception as e:
                    print(f"[StreamManager] Error deteniendo FFmpeg: {e}")

            self._process = None
            self._start_time = 0

            if cerrar_videochat:
                threading.Thread(target=self._cerrar_videochat_telethon, args=(chat_id,), daemon=True).start()

            return True, "Transmision en vivo detenida correctamente."

# Instancia singleton global para todo el proyecto
stream_manager = TelegramStreamManager()
