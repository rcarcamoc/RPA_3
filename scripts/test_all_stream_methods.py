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

ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
key = os.environ.get("TELEGRAM_STREAM_KEY", "")

candidates = [
    ("DC1 RTMPS", f"rtmps://dc1-1.rtmp.t.me/s/{key}"),
    ("DC4 RTMPS", f"rtmps://dc4-1.rtmp.t.me/s/{key}"),
    ("DC5 RTMPS", f"rtmps://dc5-1.rtmp.t.me/s/{key}"),
    ("DC1 Port 443", f"rtmps://dc1-1.rtmp.t.me:443/s/{key}"),
    ("DC4 Port 443", f"rtmps://dc4-1.rtmp.t.me:443/s/{key}"),
    ("DC2 RTMPS", f"rtmps://dc2-1.rtmp.t.me/s/{key}"),
]

successful_target = None

print("=== VERIFICANDO CONEXION A TELEGRAM ===", flush=True)

for name, target in candidates:
    print(f"Probando {name} -> {target[:30]}... ", end="", flush=True)
    cmd = [
        ffmpeg,
        "-y",
        "-f", "lavfi",
        "-i", "testsrc=size=640x360:rate=15",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-tune", "zerolatency",
        "-pix_fmt", "yuv420p",
        "-t", "2",
        "-f", "flv",
        target
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode == 0:
        print(f"¡CONECTADO CON EXITO A {name}!")
        successful_target = target
        break
    else:
        err_lines = [l for l in proc.stderr.splitlines() if "error" in l.lower() or "rtmp" in l.lower()]
        last_err = err_lines[-1] if err_lines else f"RC {proc.returncode}"
        print(f"Fallo ({last_err})")

if not successful_target:
    print("\nNo se pudo conectar a ninguno de los endpoints. Verifique que la ventana de streaming en Telegram siga activa.", flush=True)
    sys.exit(1)

print(f"\n🚀 ¡INICIANDO TRANSMISION EN VIVO DEL ESCRITORIO HACIA TELEGRAM! (Target: {successful_target})", flush=True)

fps = 15
duracion_segundos = 90

with mss.mss() as sct:
    mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
    w, h = mon["width"], mon["height"]

cmd_stream = [
    ffmpeg,
    "-y",
    "-f", "rawvideo",
    "-vcodec", "rawvideo",
    "-s", f"{w}x{h}",
    "-pix_fmt", "bgra",
    "-r", str(fps),
    "-i", "-",
    "-c:v", "libx264",
    "-preset", "ultrafast",
    "-tune", "zerolatency",
    "-g", str(fps * 2),
    "-b:v", "2000k",
    "-maxrate", "2000k",
    "-bufsize", "4000k",
    "-pix_fmt", "yuv420p",
    "-f", "flv",
    successful_target
]

proc_stream = subprocess.Popen(cmd_stream, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

total_frames = duracion_segundos * fps
frame_interval = 1.0 / fps
frames_enviados = 0

try:
    with mss.mss() as sct:
        mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
        for i in range(total_frames):
            loop_start = time.perf_counter()
            if proc_stream.poll() is not None:
                print(f"FFmpeg termino prematuramente (codigo {proc_stream.returncode})", flush=True)
                break
            shot = sct.grab(mon)
            proc_stream.stdin.write(shot.raw)
            frames_enviados += 1
            
            elapsed = time.perf_counter() - loop_start
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)
                
            if (i + 1) % fps == 0:
                seg = (i + 1) // fps
                print(f"🔴 Transmitiendo pantalla a Telegram... {seg}/{duracion_segundos}s", flush=True)
except Exception as e:
    print(f"Excepcion en transmision: {e}", flush=True)
finally:
    if proc_stream.stdin:
        try: proc_stream.stdin.close()
        except Exception: pass

err_final = proc_stream.stderr.read().decode("utf-8", errors="ignore")
proc_stream.wait()
if proc_stream.returncode == 0:
    print(f"\n✅ ¡Transmision en vivo completada exitosamente ({frames_enviados // fps} segundos)!", flush=True)
else:
    print(f"\nFFmpeg Exit Code: {proc_stream.returncode}")
    print(err_final[-600:], flush=True)
