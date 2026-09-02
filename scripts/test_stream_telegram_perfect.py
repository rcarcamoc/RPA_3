import os
import sys

if sys.stdout is not None:
    try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass
if sys.stderr is not None:
    try: sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception: pass

import time
import subprocess
import ctypes
from ctypes import wintypes
import imageio_ffmpeg
import mss
from dotenv import load_dotenv

load_dotenv()

# Vincular hilo al escritorio interactivo real de Windows
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
except Exception as e:
    print(f"Desktop attach warning: {e}", flush=True)

ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
stream_url = os.environ.get("TELEGRAM_STREAM_URL", "rtmps://dc5-1.rtmp.t.me/s/").rstrip("/")
stream_key = os.environ.get("TELEGRAM_STREAM_KEY", "")
target = f"{stream_url}/{stream_key}"

fps = 20
duracion_segundos = 90

with mss.mss() as sct:
    mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
    w, h = mon["width"], mon["height"]

w = w if w % 2 == 0 else w - 1
h = h if h % 2 == 0 else h - 1

print(f"🚀 INICIANDO TRANSMISION REAL A TELEGRAM ({w}x{h} @ {fps} FPS)...", flush=True)

cmd = [
    ffmpeg,
    "-y",
    "-f", "rawvideo",
    "-vcodec", "rawvideo",
    "-s", f"{w}x{h}",
    "-pix_fmt", "bgra",
    "-r", str(fps),
    "-i", "-",
    "-f", "lavfi",
    "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
    "-c:v", "libx264",
    "-preset", "ultrafast",
    "-tune", "zerolatency",
    "-profile:v", "baseline",
    "-pix_fmt", "yuv420p",
    "-g", str(fps * 2),
    "-keyint_min", str(fps * 2),
    "-sc_threshold", "0",
    "-b:v", "2000k",
    "-maxrate", "2500k",
    "-bufsize", "4000k",
    "-c:a", "aac",
    "-b:a", "64k",
    "-ar", "44100",
    "-flvflags", "no_duration_filesize",
    "-shortest",
    "-f", "flv",
    target
]

proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

total_frames = duracion_segundos * fps
frame_interval = 1.0 / fps
frames_enviados = 0

print("🔴 ¡Transmitiendo escritorio en vivo a Telegram! Mira tu app de Telegram ahora mismo...", flush=True)

try:
    with mss.mss() as sct:
        mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
        for i in range(total_frames):
            loop_start = time.perf_counter()
            if proc.poll() is not None:
                print(f"\nFFmpeg termino prematuramente (codigo {proc.returncode})", flush=True)
                break
                
            shot = sct.grab(mon)
            proc.stdin.write(shot.raw)
            frames_enviados += 1
            
            elapsed = time.perf_counter() - loop_start
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
                
            if (i + 1) % fps == 0:
                seg = (i + 1) // fps
                print(f"[LIVE] Transmitiendo pantalla: {seg}/{duracion_segundos}s...", flush=True)
except Exception as e:
    print(f"\nExcepcion en transmision: {e}", flush=True)
finally:
    if proc.stdin:
        try: proc.stdin.close()
        except Exception: pass
    if hDesk:
        try: user32.CloseDesktop(hDesk)
        except Exception: pass

err = proc.stderr.read().decode("utf-8", errors="ignore")
proc.wait()
if proc.returncode == 0:
    print(f"\n✅ Transmision completada con exito ({frames_enviados // fps}s).", flush=True)
else:
    print(f"\nFFmpeg Exit Code: {proc.returncode}")
    print(err[-600:], flush=True)
