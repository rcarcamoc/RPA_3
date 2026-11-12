"""
Mixin para gestión de grabación de pantalla y envío de videos de error a Telegram.
"""

import re
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


def _limpiar_motivo_error(error_desc: str) -> str:
    """Elimina prefijos anidados repetitivos del motor de workflows para dejar la causa concreta."""
    texto = str(error_desc or "").strip()
    patrones_a_eliminar = [
        r"^Iteración\s+\d+\s*\([^)]*\)\s*:\s*",
        r"Fallo en workflow de loop:\s*",
        r"Error en ejecución:\s*",
        r"Fallo en sub-workflow:\s*",
        r"Error en sub-workflow:\s*",
        r"Error ejecutando nodo workflow:\s*",
        r"Falla inesperada en la fase\s+['\"][^'\"]+['\"]\s*:\s*",
        r"El asistente no pudo completar la tarea en la fase\s+['\"][^'\"]+['\"]\s*\.?\s*",
    ]
    for pat in patrones_a_eliminar:
        texto = re.sub(pat, "", texto, flags=re.IGNORECASE).strip()
    return texto or str(error_desc)


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
                    obs_bd = None
                    doc_bd = None
                    examen_bd = None
                    try:
                        _conn = mysql.connector.connect(host='localhost', user='root', password='', database='ris', connect_timeout=2)
                        _cur = _conn.cursor(dictionary=True)
                        _cur.execute("SELECT id, observacion, numero_documento, examen FROM ris.registro_acciones WHERE estado = 'En Proceso' ORDER BY id DESC LIMIT 1")
                        _r = _cur.fetchone()
                        if not _r:
                            _cur.execute("SELECT id, observacion, numero_documento, examen FROM ris.registro_acciones ORDER BY id DESC LIMIT 1")
                            _r = _cur.fetchone()
                        if _r:
                            rec_id = _r.get('id')
                            obs_bd = _r.get('observacion')
                            doc_bd = _r.get('numero_documento')
                            examen_bd = _r.get('examen')
                        _cur.close()
                        _conn.close()
                    except Exception:
                        pass

                    screen_res = self.context.get("screen_resolution") or get_screen_resolution()
                    id_txt = f"\n🆔 <b>ID Fila BD:</b> <code>{rec_id}</code>" if rec_id else ""
                    info_extra = ""
                    if doc_bd or examen_bd:
                        partes = []
                        if doc_bd: partes.append(f"📄 <b>Doc:</b> <code>{doc_bd}</code>")
                        if examen_bd: partes.append(f"🩺 <b>Examen:</b> <code>{examen_bd}</code>")
                        info_extra = "\n" + " | ".join(partes)

                    # Priorizar la observación concreta y descriptiva registrada en BD
                    if obs_bd and len(str(obs_bd).strip()) > 5:
                        motivo_final = str(obs_bd).strip()
                    else:
                        motivo_final = _limpiar_motivo_error(str(error_desc))

                    if len(motivo_final) > 550:
                        motivo_final = motivo_final[:547] + "..."

                    caption = (
                        f"❌ <b>Error en Workflow: {raw_name}</b>{id_txt}{info_extra}\n"
                        f"🖥️ <b>Resolución:</b> <code>{screen_res}</code>\n\n"
                        f"📋 <b>Problema:</b>\n{motivo_final}"
                    )
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
