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
import imageio_ffmpeg
import mss
from dotenv import load_dotenv

load_dotenv()

url = os.environ.get("TELEGRAM_STREAM_URL", "").rstrip("/")
key = os.environ.get("TELEGRAM_STREAM_KEY", "")
target = f"{url}/{key}"

duracion_segundos = 60
fps = 15

print(f"URL destino: {url}", flush=True)

with mss.mss() as sct:
    mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
    w, h = mon["width"], mon["height"]

print(f"Monitor detectado: {w}x{h} @ {fps} FPS", flush=True)

cmd = [
    imageio_ffmpeg.get_ffmpeg_exe(),
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
    "-g", str(fps * 2),
    "-b:v", "1500k",
    "-maxrate", "1500k",
    "-bufsize", "3000k",
    "-pix_fmt", "yuv420p",
    "-c:a", "aac",
    "-b:a", "64k",
    "-f", "flv",
    target
]

print("Conectando con Telegram e iniciando transmision en vivo...", flush=True)
proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

total_frames = duracion_segundos * fps
frames_enviados = 0
frame_interval = 1.0 / fps

try:
    with mss.mss() as sct:
        mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
        
        for i in range(total_frames):
            loop_start = time.perf_counter()
            
            if proc.poll() is not None:
                print(f"\nFFmpeg termino anticipadamente (codigo {proc.returncode})", flush=True)
                break
                
            shot = sct.grab(mon)
            proc.stdin.write(shot.raw)
            frames_enviados += 1
            
            elapsed = time.perf_counter() - loop_start
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
                
            if (i + 1) % fps == 0:
                seg_actual = (i + 1) // fps
                print(f"[LIVE] Transmitiendo a Telegram: {seg_actual}/{duracion_segundos}s...", flush=True)
except Exception as e:
    print(f"\nExcepcion en transmision: {e}", flush=True)
finally:
    if proc.stdin:
        try: proc.stdin.close()
        except Exception: pass

err = proc.stderr.read().decode("utf-8", errors="ignore")
proc.wait()
print(f"Resultado final FFmpeg: Codigo {proc.returncode}", flush=True)
if proc.returncode != 0:
    print(f"Detalle error FFmpeg:\n{err[-600:]}", flush=True)
else:
    print(f"[OK] Transmision de {frames_enviados // fps}s completada con exito en Telegram!", flush=True)
