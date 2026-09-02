import os
import subprocess
import imageio_ffmpeg
from dotenv import load_dotenv

load_dotenv()

ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

app = "s"
playpath = os.environ.get("TELEGRAM_STREAM_KEY", "")
base_url = os.environ.get("TELEGRAM_STREAM_URL", "rtmps://dc1-1.rtmp.t.me:443/s")

print(f"Testing with explicit -rtmp_playpath '{playpath}' to {base_url}...", flush=True)

cmd = [
    ffmpeg,
    "-y",
    "-f", "lavfi",
    "-i", "testsrc=size=640x360:rate=15",
    "-f", "lavfi",
    "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
    "-c:v", "libx264",
    "-preset", "ultrafast",
    "-tune", "zerolatency",
    "-pix_fmt", "yuv420p",
    "-c:a", "aac",
    "-t", "5",
    "-rtmp_playpath", playpath,
    "-f", "flv",
    base_url
]

proc = subprocess.run(cmd, capture_output=True, text=True)
print(f"Return code: {proc.returncode}", flush=True)
if proc.returncode == 0:
    print(">>> EXITO TOTAL CON -rtmp_playpath! <<<", flush=True)
else:
    print("Stderr:\n", proc.stderr[-800:], flush=True)
