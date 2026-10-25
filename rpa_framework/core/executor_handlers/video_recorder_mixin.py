"""
Mixin para gestión de grabación de pantalla y envío de videos de error a Telegram.
"""

from datetime import datetime
from typing import Optional
import mysql.connector

try:
    from utils.screen_utils import get_screen_resolution
except ImportError:
    try:
        from rpa_framework.utils.screen_utils import get_screen_resolution
    except ImportError:
        def get_screen_resolution():
            return "1920x1080"


class VideoRecorderMixin:
    """Mixin para guardar/enviar videos de error y reiniciar el grabador de pantalla."""

    def _save_and_send_error_video(self, error_desc: str, custom_prefix: Optional[str] = None) -> Optional[str]:
        """Detiene la grabación activa, guarda el video de error y lo envía a Telegram."""
        recorder = self.screen_recorder
        if not recorder:
            return None

        saved_video_path = None
        try:
            try:
                from utils.paths import get_error_recording_path
            except ImportError:
                from rpa_framework.utils.paths import get_error_recording_path

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            raw_name = custom_prefix if custom_prefix else self.workflow.name
            safe_name = "".join([c for c in raw_name if c.isalnum() or c in (' ', '-', '_')]).strip().replace(' ', '_')
            video_filename = f"error_{safe_name}_{timestamp}.mp4"
            dest_path = get_error_recording_path(video_filename)

            saved_video_path = recorder.save(str(dest_path))
            self.screen_recorder = None
            if saved_video_path:
                self.logger.log(f"💾 Grabación de pantalla de error guardada en: {saved_video_path}")
                try:
                    try:
                        from utils.telegram_manager import enviar_video_todos
                    except ImportError:
                        from rpa_framework.utils.telegram_manager import enviar_video_todos

                    rec_id = None
                    try:
                        _conn = mysql.connector.connect(host='localhost', user='root', password='', database='ris', connect_timeout=2)
                        _cur = _conn.cursor(dictionary=True)
                        _cur.execute("SELECT id FROM ris.registro_acciones WHERE estado = 'En Proceso' ORDER BY id DESC LIMIT 1")
                        _r = _cur.fetchone()
                        if not _r:
                            _cur.execute("SELECT id FROM ris.registro_acciones ORDER BY id DESC LIMIT 1")
                            _r = _cur.fetchone()
                        if _r:
                            rec_id = _r.get('id')
                        _cur.close()
                        _conn.close()
                    except Exception:
                        pass

                    screen_res = self.context.get("screen_resolution") or get_screen_resolution()
                    id_txt = f"\n🆔 <b>ID Fila BD:</b> <code>{rec_id}</code>" if rec_id else ""
                    caption = f"❌ <b>Error en Workflow: {raw_name}</b>{id_txt}\n🖥️ <b>Resolución:</b> <code>{screen_res}</code>\n<b>Motivo:</b> {str(error_desc)[:250]}"
                    enviar_video_todos(saved_video_path, caption=caption)
                    self.logger.log("📱 Grabación de video del error enviada a Telegram")
                except Exception as tel_e:
                    self.logger.log(f"⚠️ Error al enviar video por Telegram: {tel_e}")
        except Exception as rec_err:
            self.logger.log(f"⚠️ Error guardando grabación de pantalla: {rec_err}")

        return saved_video_path

    def _restart_screen_recorder(self) -> None:
        """Reinicia el grabador de pantalla si está habilitado y no es sub-workflow."""
        if not self.enable_recording or self.is_sub_workflow:
            return

        if self.screen_recorder:
            try:
                self.screen_recorder.discard()
            except Exception:
                pass
            self.screen_recorder = None

        try:
            try:
                from utils.screen_recorder import ScreenRecorder
            except ImportError:
                from rpa_framework.utils.screen_recorder import ScreenRecorder

            recorder = ScreenRecorder(fps=6, max_width=1280, format="mp4")
            if recorder.start():
                self.screen_recorder = recorder
                self.logger.log("🎥 Grabación de pantalla reiniciada en segundo plano")
            else:
                self.screen_recorder = None
        except Exception as rec_e:
            self.screen_recorder = None
            self.logger.log(f"⚠️ No se pudo reiniciar el grabador de pantalla: {rec_e}")
