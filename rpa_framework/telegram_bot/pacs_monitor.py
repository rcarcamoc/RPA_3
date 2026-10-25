"""
Monitoreo, consulta y ejecución de validaciones de PACS para el Bot de Telegram.
"""
import html
import json
import os
import subprocess
import sys
import threading
from datetime import datetime

from utils.telegram_manager import enviar_mensaje
from . import bot_state
from .bot_state import RPA_ROOT, mostrar_notificacion_tray


def get_pacs_daily_status():
    """
    Consulta la base de datos para ver el estado de las validaciones de PACS hoy:
    - ya_exitoso: bool (si hubo al menos una ejecución Exitosa hoy)
    - total_intentos: int (cantidad total de registros de validación creados hoy)
    - ultimo_estado: str ('Exitoso', 'Error', 'En Proceso', etc.)
    - ultimo_timestamp: datetime del último intento
    """
    try:
        import mysql.connector
        conn = mysql.connector.connect(host='localhost', user='root', password='', database='ris', connect_timeout=5)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SHOW TABLES LIKE 'validacion_pacs'")
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return {"ya_exitoso": False, "total_intentos": 0, "ultimo_estado": None, "ultimo_timestamp": None}

        cursor.execute("""
            SELECT id, estado, fecha_validacion 
            FROM ris.validacion_pacs 
            WHERE DATE(fecha_validacion) = CURDATE() 
            ORDER BY id DESC
        """)
        filas = cursor.fetchall()
        cursor.close()
        conn.close()

        if not filas:
            return {"ya_exitoso": False, "total_intentos": 0, "ultimo_estado": None, "ultimo_timestamp": None}

        ya_exitoso = any(r.get("estado") == "Exitoso" for r in filas)
        total_intentos = len(filas)
        ultimo_estado = filas[0].get("estado")
        ultimo_timestamp = filas[0].get("fecha_validacion")

        return {
            "ya_exitoso": ya_exitoso,
            "total_intentos": total_intentos,
            "ultimo_estado": ultimo_estado,
            "ultimo_timestamp": ultimo_timestamp
        }
    except Exception as e:
        print(f"[PACS Check DB Error] {e}")
        return {"ya_exitoso": False, "total_intentos": 0, "ultimo_estado": None, "ultimo_timestamp": None}


def check_pacs_validated_today():
    """Consulta la base de datos para ver si ya se realizó una validación exitosa de PACS hoy."""
    return get_pacs_daily_status()["ya_exitoso"]


def trigger_pacs_validation_process(manual=False, chat_id=None):
    """Ejecuta el script validar_pacs_diario.py en primer plano (consola visible) con Keep-Alive y manejo de estado."""
    if bot_state._pacs_validating_now:
        print("⚠️ Ya hay una validación de PACS en ejecución.")
        return False

    script_path = RPA_ROOT / "recordings" / "sistema" / "validar_pacs_diario.py"
    if not script_path.exists():
        print(f"❌ Script de validación PACS no encontrado: {script_path}")
        return False

    def _worker():
        bot_state._pacs_validating_now = True
        try:
            from utils.keep_alive import keep_system_awake
            with keep_system_awake(keep_display=True):
                tag = "MANUAL" if manual else "AUTO"
                print(f"🩺 [{tag}] Lanzando proceso de validación PACS (modo visible)...")
                mostrar_notificacion_tray(f"Iniciando Validación PACS ({tag})...", "🩺 Validación PACS")

                py_exe = sys.executable
                if "pythonw.exe" in py_exe.lower():
                    py_cand = py_exe.lower().replace("pythonw.exe", "python.exe")
                    if os.path.exists(py_cand):
                        py_exe = py_cand

                cmd = [py_exe, str(script_path)]
                if manual:
                    cmd.append("--manual")

                cfg_visible = False
                try:
                    cfg_p = RPA_ROOT / "config" / "pacs_validation_config.json"
                    if cfg_p.exists():
                        with open(cfg_p, 'r', encoding='utf-8') as f:
                            cfg_visible = json.load(f).get("consola_visible", False)
                except Exception:
                    pass

                if cfg_visible and sys.platform == "win32":
                    creation_flags = subprocess.CREATE_NEW_CONSOLE
                elif sys.platform == "win32":
                    creation_flags = subprocess.CREATE_NO_WINDOW
                else:
                    creation_flags = 0

                base_cwd = str(RPA_ROOT)

                proc = subprocess.Popen(
                    cmd,
                    creationflags=creation_flags,
                    cwd=base_cwd
                )

                bot_state._pacs_proc = proc
                proc.wait()
                print(f"✅ Proceso de validación PACS finalizado (exit code: {proc.returncode}).")
                mostrar_notificacion_tray("Validación PACS finalizada.", "🩺 Validación PACS")
                if chat_id:
                    if proc.returncode == 0:
                        res_txt = "✅ <b>Validación PACS Finalizada</b> (Exitosa)\n\nUsa /estado_pacs para ver los detalles."
                    else:
                        err_detalle = ""
                        try:
                            import mysql.connector
                            c_err = mysql.connector.connect(host='localhost', user='root', password='', database='ris', connect_timeout=3)
                            cur_err = c_err.cursor(dictionary=True)
                            cur_err.execute("SELECT observacion, intentos FROM ris.validacion_pacs ORDER BY id DESC LIMIT 1")
                            r_err = cur_err.fetchone()
                            if r_err and r_err.get("observacion"):
                                err_detalle = f"\n\n<b>Detalle del error:</b>\n<code>{html.escape(r_err['observacion'])}</code>"
                            cur_err.close()
                            c_err.close()
                        except Exception:
                            err_detalle = f"\n\n(Código de salida del proceso: {proc.returncode})"
                        res_txt = f"❌ <b>Validación PACS Finalizada con Error</b>{err_detalle}\n\nUsa /estado_pacs para más información."
                    enviar_mensaje(chat_id, res_txt)
        except Exception as e:
            print(f"[PACS Process Error] {e}")
            if chat_id:
                enviar_mensaje(chat_id, f"❌ Error ejecutando validación PACS: {e}")
        finally:
            bot_state._pacs_proc = None
            bot_state._pacs_validating_now = False
            try:
                from recordings.ui.cierra_pacs import cerrar_pacs
                cerrar_pacs()
            except Exception:
                pass

    threading.Thread(target=_worker, daemon=True, name="PACS_Validation_Worker").start()
    return True


def consultar_estado_pacs():
    """Consulta el estado actual, configuración y las últimas validaciones de PACS desde ris.validacion_pacs."""
    try:
        config_path = RPA_ROOT / "config" / "pacs_validation_config.json"
        cfg = {}
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
            except Exception:
                pass

        hora_cfg = cfg.get("hora_validacion", "09:00")
        habilitado = cfg.get("habilitado", True)
        dias_val = cfg.get("dias_validacion", [0, 1, 2, 3, 4, 5, 6])
        nombres_dias = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
        dias_str = ", ".join([nombres_dias[d] for d in dias_val if 0 <= d < 7])

        import mysql.connector
        conn = mysql.connector.connect(host='localhost', user='root', password='', database='ris', connect_timeout=5)
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SHOW TABLES LIKE 'validacion_pacs'")
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return "⚠️ La tabla <b>validacion_pacs</b> aún no existe. No se ha ejecutado ninguna validación."

        cursor.execute("SELECT * FROM ris.validacion_pacs ORDER BY id DESC LIMIT 1")
        ultimo = cursor.fetchone()

        daily_stat = get_pacs_daily_status()
        val_hoy = daily_stat.get("ya_exitoso", False)
        if bot_state._pacs_validating_now:
            estado_hoy_str = "⏳ <b>En ejecución en este momento...</b>"
        elif val_hoy:
            f_hoy = daily_stat.get('ultimo_timestamp')
            hora_val_str = f_hoy.strftime('%H:%M:%S') if hasattr(f_hoy, 'strftime') else str(f_hoy or '')
            estado_hoy_str = f"✅ <b>Completada con éxito hoy a las {hora_val_str}</b>"
        else:
            if not habilitado:
                estado_hoy_str = "⏸️ <b>Desactivado (ejecución solo manual en primer plano)</b>"
            else:
                ahora = datetime.now()
                try:
                    ht, mt = [int(x) for x in hora_cfg.split(":")]
                except Exception:
                    ht, mt = 9, 0
                if (ahora.hour > ht) or (ahora.hour == ht and ahora.minute >= mt):
                    estado_hoy_str = "⚠️ <b>Pendiente de validación</b>"
                else:
                    estado_hoy_str = f"🕒 <b>Programada para hoy a las {hora_cfg}</b>"

        msg = "🏥 <b>MONITOR DE VALIDACIÓN PACS</b>\n\n"
        msg += f"• <b>Estado de Hoy:</b> {estado_hoy_str}\n"
        msg += f"• <b>Programación:</b> Diaria a las <code>{hora_cfg}</code> ({dias_str})\n"
        msg += f"• <b>Servicio automático:</b> {'Activo ✅' if habilitado else 'Desactivado ❌ (ejecución en primer plano)'}\n\n"

        if ultimo:
            estado = ultimo.get('estado', 'Sin Datos')
            fecha = str(ultimo.get('fecha_validacion', '--'))
            obs = ultimo.get('observacion') or 'Sin observaciones'
            duracion = ultimo.get('duracion_segundos')
            intentos = ultimo.get('intentos', 1)
            doc_val = ultimo.get('doctor_validacion')
            user_val = ultimo.get('user_validacion')
            iconos = {'Exitoso': '✅', 'Error': '❌', 'En Proceso': '⏳'}
            icono = iconos.get(estado, '⚠️')

            msg += "📌 <b>Última Verificación Registrada:</b>\n"
            msg += f"  {icono} Estado: <b>{estado}</b> (ID #{ultimo.get('id')})\n"
            if doc_val:
                msg += f"  👨‍⚕️ Médico probado: <b>{doc_val}</b> (<code>{user_val}</code>)\n"
            msg += f"  📅 Fecha: {fecha}\n"
            msg += f"  🔄 Intentos: {intentos}\n"
            if duracion is not None:
                msg += f"  ⏱️ Duración: {duracion}s\n"
            msg += f"  📝 Observación: {obs}\n"

        cursor.execute("SELECT id, fecha_validacion, estado, duracion_segundos, intentos, observacion, doctor_validacion, user_validacion FROM ris.validacion_pacs ORDER BY id DESC LIMIT 5")
        registros = cursor.fetchall()

        if len(registros) > 1:
            msg += "\n<b>📜 Historial Reciente:</b>\n"
            for r in registros[1:]:
                r_estado = r.get('estado', '?')
                iconos = {'Exitoso': '✅', 'Error': '❌', 'En Proceso': '⏳'}
                r_icono = iconos.get(r_estado, '⚠️')
                r_fecha = str(r.get('fecha_validacion', '--'))
                r_dur = f"{r.get('duracion_segundos', 0)}s" if r.get('duracion_segundos') is not None else '--'
                r_doc = r.get('doctor_validacion') or ''
                r_doc_txt = f" | {r_doc[:16]}" if r_doc else ""
                msg += f"  {r_icono} {r_fecha} | {r_dur} | {r.get('intentos', 1)} int.{r_doc_txt}\n"

        msg += "\n💡 <i>Puedes ejecutar la validación desde el Menú de Sistema o con /validar_pacs</i>"

        cursor.close()
        conn.close()
        return msg
    except Exception as e:
        return f"❌ Error consultando estado PACS: {e}"


def run_pacs_validation_scheduler():
    """Desactivado: Ningún workflow debe ejecutarse en segundo plano."""
    print("ℹ️ Scheduler de validación PACS en segundo plano desactivado por política de ejecución en primer plano.")
    return
