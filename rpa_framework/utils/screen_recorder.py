"""
Módulo de Grabación de Pantalla Completa para RPA Framework 3.

Utiliza 'mss' para captura rápida de fotogramas e 'imageio-ffmpeg' (o OpenCV) para
codificación de video H.264 (yuv420p) de alta compatibilidad con reproductores móviles y Telegram.
Permite iniciar la grabación al comienzo de un workflow y decidir al finalizar si se guarda o se descarta.
"""

import os
import sys
import time
import shutil
import threading
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional

try:
    import cv2
    import numpy as np
    import mss
    HAS_SCREEN_REC_DEPS = True
except ImportError:
    HAS_SCREEN_REC_DEPS = False

try:
    import imageio_ffmpeg
    HAS_FFMPEG = True
except ImportError:
    HAS_FFMPEG = False


def _attach_to_default_desktop():
    """Conecta el hilo actual al escritorio interactivo 'Default' de Windows."""
    if sys.platform == "win32":
        try:
            import ctypes
            user32 = ctypes.windll.user32
            GENERIC_ALL = 0x10000000
            hdesk = user32.OpenDesktopW('Default', 0, False, GENERIC_ALL)
            if hdesk:
                user32.SetThreadDesktop(hdesk)
        except Exception:
            pass


class ScreenRecorder:
    """Grabador de pantalla completa en hilo secundario con codificación H.264 para Telegram."""

    def __init__(self, fps: int = 6, max_width: int = 1280, format: str = "mp4", temp_dir: Optional[str] = None):
        """
        Inicializa el grabador de pantalla.

        Args:
            fps: Fotogramas por segundo (default: 6 para optimizar peso)
            max_width: Ancho máximo de resolución (default: 1280px para video ligero y legible)
            format: Formato del video ('mp4')
            temp_dir: Directorio para archivos temporales
        """
        self.fps = fps
        self.max_width = max_width
        self.format = format.lower()
        self.temp_dir = Path(temp_dir) if temp_dir else Path("tmp")
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        self.temp_file = self.temp_dir / f"rec_temp_{timestamp}.{self.format}"

        self.recording = False
        self.thread: Optional[threading.Thread] = None
        self.ffmpeg_proc = None
        self.video_writer = None
        self._lock = threading.Lock()

    def start(self) -> bool:
        """Inicia la grabación de pantalla en un hilo secundario."""
        if not HAS_SCREEN_REC_DEPS:
            print("[WARN] ScreenRecorder: mss o opencv-python no están instalados. Grabación deshabilitada.")
            return False

        if self.recording:
            return True

        self.recording = True
        self.thread = threading.Thread(target=self._record_loop, daemon=True, name="ScreenRecorder_Thread")
        self.thread.start()
        return True

    def _record_loop(self):
        """Bucle continuo de captura de frames."""
        _attach_to_default_desktop()
        try:
            with mss.mss() as sct:
                # monitor[1] es la pantalla principal
                monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                orig_w = monitor["width"]
                orig_h = monitor["height"]

                # Calcular resolución escalada respetando proporción
                if self.max_width and orig_w > self.max_width:
                    scale = self.max_width / float(orig_w)
                    width = int(orig_w * scale)
                    height = int(orig_h * scale)
                else:
                    width = orig_w
                    height = orig_h

                # Asegurar dimensiones pares requeridas por H.264
                if width % 2 != 0: width -= 1
                if height % 2 != 0: height -= 1

                # Intentar usar FFMPEG nativo (H.264 yuv420p ultra-compatible con Telegram)
                use_ffmpeg = False
                if HAS_FFMPEG:
                    try:
                        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
                        cmd = [
                            ffmpeg_exe,
                            '-y',
                            '-f', 'rawvideo',
                            '-vcodec', 'rawvideo',
                            '-s', f'{width}x{height}',
                            '-pix_fmt', 'bgr24',
                            '-r', str(self.fps),
                            '-i', '-',
                            '-c:v', 'libx264',
                            '-pix_fmt', 'yuv420p',
                            '-preset', 'veryfast',
                            '-crf', '26',
                            str(self.temp_file)
                        ]
                        cflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                        self.ffmpeg_proc = subprocess.Popen(
                            cmd,
                            stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            creationflags=cflags
                        )
                        use_ffmpeg = True
                    except Exception as fe:
                        print(f"[WARN] ScreenRecorder: No se pudo iniciar FFmpeg ({fe}), usando fallback OpenCV...")
                        use_ffmpeg = False

                if not use_ffmpeg:
                    codec = 'mp4v' if self.format == 'mp4' else 'XVID'
                    fourcc = cv2.VideoWriter_fourcc(*codec)
                    with self._lock:
                        self.video_writer = cv2.VideoWriter(
                            str(self.temp_file),
                            fourcc,
                            float(self.fps),
                            (width, height)
                        )

                interval = 1.0 / self.fps

                while self.recording:
                    start_time = time.time()

                    # Capturar pantalla
                    sct_img = sct.grab(monitor)
                    frame = np.array(sct_img)

                    # Convertir BGRA a BGR y redimensionar
                    frame_bgr = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                    if frame_bgr.shape[1] != width or frame_bgr.shape[0] != height:
                        frame_bgr = cv2.resize(frame_bgr, (width, height), interpolation=cv2.INTER_AREA)

                    # Escribir frame
                    if use_ffmpeg and self.ffmpeg_proc and self.ffmpeg_proc.stdin:
                        try:
                            self.ffmpeg_proc.stdin.write(frame_bgr.tobytes())
                        except Exception:
                            break
                    else:
                        with self._lock:
                            if self.video_writer and self.video_writer.isOpened():
                                self.video_writer.write(frame_bgr)

                    # Control de FPS
                    elapsed = time.time() - start_time
                    wait_time = interval - elapsed
                    if wait_time > 0:
                        time.sleep(wait_time)

        except Exception as e:
            print(f"[ERROR] ScreenRecorder error en el bucle de grabación: {e}")
        finally:
            self._close_writer()

    def _close_writer(self):
        """Cierra de forma segura el VideoWriter o el proceso FFmpeg."""
        with self._lock:
            if self.ffmpeg_proc:
                try:
                    if self.ffmpeg_proc.stdin:
                        self.ffmpeg_proc.stdin.close()
                    self.ffmpeg_proc.wait(timeout=5)
                except Exception:
                    try:
                        self.ffmpeg_proc.kill()
                    except Exception:
                        pass
                self.ffmpeg_proc = None

            if self.video_writer:
                try:
                    self.video_writer.release()
                except Exception:
                    pass
                self.video_writer = None

    def stop(self):
        """Detiene el hilo de grabación de forma limpia."""
        if not self.recording:
            return
        self.recording = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=4.0)
        self._close_writer()

    def discard(self):
        """Detiene la grabación y elimina el archivo temporal."""
        self.stop()
        try:
            if self.temp_file.exists():
                os.remove(self.temp_file)
        except Exception as e:
            print(f"[WARN] ScreenRecorder: No se pudo eliminar video temporal {self.temp_file}: {e}")

    def save(self, destination_path: str) -> Optional[str]:
        """
        Detiene la grabación y guarda el video en la ruta especificada.

        Args:
            destination_path: Ruta destino final

        Returns:
            Ruta del archivo guardado o None si falló
        """
        self.stop()
        dest = Path(destination_path)
        dest.parent.mkdir(parents=True, exist_ok=True)

        try:
            if self.temp_file.exists() and self.temp_file.stat().st_size > 0:
                shutil.move(str(self.temp_file), str(dest))
                return str(dest)
            else:
                print(f"[WARN] ScreenRecorder: Archivo temporal {self.temp_file} vacío o no encontrado.")
                return None
        except Exception as e:
            print(f"[ERROR] ScreenRecorder: Error al guardar el video en {dest}: {e}")
            return None
