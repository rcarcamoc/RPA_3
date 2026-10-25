"""
Envío y programación de reportes horarios, diarios y notificaciones de inicio/fin de loop.
"""
import datetime
import os
import sys
import time
import pandas as pd
import schedule

# Asegurar que el directorio utils/ esté disponible para importar telegram_manager
_UTILS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _UTILS_DIR not in sys.path:
    sys.path.append(_UTILS_DIR)

try:
    import telegram_manager
except ImportError:
    from rpa_framework.utils import telegram_manager

from .summary_queries import (
    HORA_INICIO_HOURLY,
    HORA_FIN_HOURLY,
    HORA_DAILY,
    DIAS_SEMANA_VALIDOS,
    notificaciones_pausadas,
    se_ejecuto_workflow_ultimos_minutos,
    obtener_datos,
)
from .summary_charts import (
    generar_texto_resumen_hourly,
    generar_dashboard_ejecutivo,
    generar_texto_resumen_simple,
)


def enviar_reporte_hourly(force=False):
    """Envía el reporte de la última hora y el acumulado del día con 1 dashboard visual y texto amigable.
    Se salta si las notificaciones están pausadas o si no se ejecutó ningún workflow en los últimos 60 minutos (a menos que force=True).
    """
    now = datetime.datetime.now()

    if not force:
        if now.weekday() not in DIAS_SEMANA_VALIDOS:
            return

        if not (HORA_INICIO_HOURLY <= now.hour <= HORA_FIN_HOURLY):
            return

        if notificaciones_pausadas():
            print(f"[{now}] Notificaciones pausadas — reporte horario omitido.")
            return

        if not se_ejecuto_workflow_ultimos_minutos(minutos=60):
            print(f"[{now}] No se ejecutó ningún workflow en los últimos 60 minutos — reporte horario omitido.")
            return

    # 1. Datos de la última hora (e.g. de 09:00:00 a 09:59:59)
    fecha_fin_h = now.replace(minute=59, second=59, microsecond=999999) - datetime.timedelta(hours=1)
    fecha_inicio_h = fecha_fin_h.replace(minute=0, second=0, microsecond=0)

    # 2. Datos acumulados del día (de 00:00:00 a ahora)
    fecha_inicio_d = now.replace(hour=0, minute=0, second=0, microsecond=0)
    fecha_fin_d = now

    periodo_str = f"{fecha_inicio_h.strftime('%H:%M')} a {fecha_fin_h.strftime('%H:%M')}"

    print(f"[{now}] Ejecutando reporte hourly...")
    df_hora = obtener_datos(fecha_inicio_h, fecha_fin_h)
    df_dia = obtener_datos(fecha_inicio_d, fecha_fin_d)

    texto = generar_texto_resumen_hourly(df_hora, df_dia, periodo_str)

    img_dashboard = "hourly_dashboard_temp.png"
    try:
        if generar_dashboard_ejecutivo(df_hora, df_dia, periodo_str, img_dashboard, is_daily=False):
            telegram_manager.enviar_foto_todos(img_dashboard, caption=texto)
        else:
            telegram_manager.enviar_alerta_todos(texto)
    except Exception as e:
        print(f"Error generando dashboard horario: {e}")
        telegram_manager.enviar_alerta_todos(texto)
    finally:
        if os.path.exists(img_dashboard):
            try:
                os.remove(img_dashboard)
            except Exception:
                pass


def enviar_reporte_daily():
    """Envía el reporte del día anterior completo con dashboard ejecutivo unificado y texto.
    Se salta si las notificaciones están pausadas.
    """
    now = datetime.datetime.now()

    if notificaciones_pausadas():
        print(f"[{now}] Notificaciones pausadas — reporte diario omitido.")
        return

    fecha_anterior = now - datetime.timedelta(days=1)
    fecha_inicio = fecha_anterior.replace(hour=0, minute=0, second=0, microsecond=0)
    fecha_fin = fecha_anterior.replace(hour=23, minute=59, second=59, microsecond=999999)

    periodo_str = f"{fecha_inicio.strftime('%d/%m/%Y')}"

    print(f"[{now}] Ejecutando reporte daily...")
    df = obtener_datos(fecha_inicio, fecha_fin)

    texto = generar_texto_resumen_simple(df, "Cierre Diario", periodo_str)

    img_dashboard = "daily_dashboard_temp.png"
    try:
        df_vacio = pd.DataFrame(columns=['inicio', 'estado', 'estado_notificacion'])
        if generar_dashboard_ejecutivo(df_vacio, df, periodo_str, img_dashboard, is_daily=True):
            telegram_manager.enviar_foto_todos(img_dashboard, caption=texto)
        else:
            telegram_manager.enviar_alerta_todos(texto)
    except Exception as e:
        print(f"Error generando dashboard diario: {e}")
        telegram_manager.enviar_alerta_todos(texto)
    finally:
        if os.path.exists(img_dashboard):
            try:
                os.remove(img_dashboard)
            except Exception:
                pass


def notificar_inicio_loop(modo: str = "count", detalles: str = "", workflow_name: str = "loop"):
    """
    Envía notificación por Telegram cuando inicia un ciclo en bucle de ejecución.
    """
    now = datetime.datetime.now()
    hora_str = now.strftime("%H:%M:%S")
    fecha_str = now.strftime("%d/%m/%Y")

    modo_map = {
        "count": "Por Cantidad de Ciclos",
        "timed": "Por Tiempo Programado",
        "infinite": "Continuo Infinito",
        "while": "Condicional (While)",
        "list": "Por Lista de Datos"
    }
    modo_amigable = modo_map.get(str(modo).lower(), modo)

    lineas = [
        "🔄 <b>CICLO EN BUCLE INICIADO</b>",
        "",
        f"🤖 <b>Workflow:</b> <code>{workflow_name}</code>",
        f"⚙️ <b>Modo:</b> {modo_amigable}",
    ]
    if detalles:
        lineas.append(f"📌 <b>Configuración:</b> {detalles}")

    lineas.extend([
        f"🕒 <b>Inicio:</b> <code>{hora_str}</code> (<i>{fecha_str}</i>)",
        "",
        "ℹ️ <i>El robot ejecutará las iteraciones configuradas. Al finalizar el bucle se enviará el resumen de gestión del día.</i>"
    ])

    mensaje = "\n".join(lineas)
    try:
        telegram_manager.enviar_mensaje_todos(mensaje)
    except Exception as e:
        print(f"Error enviando notificación de inicio de loop a Telegram: {e}")


def notificar_fin_loop_con_resumen(motivo: str = "completado", iteraciones: int = 0, duracion_segundos: float = 0, workflow_name: str = "loop"):
    """
    Envía notificación por Telegram cuando termina el bucle de ejecución,
    acompañada de un resumen consolidado y dashboard gráfico de la gestión del día.
    """
    try:
        from utils.watchdog_supervisor import is_watchdog_recovering
        if is_watchdog_recovering():
            print("ℹ️ Fin de loop originado por Watchdog. Omitiendo notificación redundante de parada manual.")
            return
    except Exception:
        pass

    now = datetime.datetime.now()
    hora_fin_str = now.strftime("%H:%M:%S")
    fecha_fin_str = now.strftime("%d/%m/%Y")

    if duracion_segundos >= 3600:
        h = int(duracion_segundos // 3600)
        m = int((duracion_segundos % 3600) // 60)
        s = int(duracion_segundos % 60)
        dur_str = f"{h}h {m}m {s}s"
    elif duracion_segundos >= 60:
        m = int(duracion_segundos // 60)
        s = int(duracion_segundos % 60)
        dur_str = f"{m}m {s}s"
    else:
        dur_str = f"{int(duracion_segundos)}s"

    motivo_lower = str(motivo).lower()
    if any(k in motivo_lower for k in ["detenido", "stop"]):
        header = "🛑 <b>CICLO EN BUCLE DETENIDO</b>"
        resultado_desc = "Detenido por solicitud del usuario / señal externa"
    elif any(k in motivo_lower for k in ["tiempo", "timed"]):
        header = "⏰ <b>CICLO EN BUCLE FINALIZADO (TIEMPO CUMPLIDO)</b>"
        resultado_desc = "Tiempo programado cumplido con éxito"
    elif any(k in motivo_lower for k in ["error", "fall"]):
        header = "❌ <b>CICLO EN BUCLE INTERRUMPIDO POR ERROR</b>"
        resultado_desc = f"Interrupción: {motivo}"
    else:
        header = "🏁 <b>CICLO EN BUCLE FINALIZADO</b>"
        resultado_desc = "Todas las iteraciones completadas con éxito"

    fecha_inicio_d = now.replace(hour=0, minute=0, second=0, microsecond=0)
    fecha_fin_d = now
    df_dia = obtener_datos(fecha_inicio_d, fecha_fin_d)

    msg_fin = (
        f"{header}\n\n"
        f"🤖 <b>Workflow:</b> <code>{workflow_name}</code>\n"
        f"📋 <b>Resultado:</b> {resultado_desc}\n"
        f"🔄 <b>Iteraciones ejecutadas:</b> <b>{iteraciones}</b>\n"
        f"⏱️ <b>Duración del ciclo:</b> <code>{dur_str}</code>\n"
        f"🕒 <b>Hora fin:</b> <code>{hora_fin_str}</code>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
    )

    resumen_gestion = generar_texto_resumen_simple(df_dia, "Gestión del Día", fecha_fin_str)
    texto_completo = msg_fin + resumen_gestion

    img_dashboard = os.path.join(_UTILS_DIR, f"dashboard_fin_loop_{int(time.time())}.png")
    foto_enviada = False

    try:
        df_vacio = pd.DataFrame(columns=['inicio', 'estado', 'estado_notificacion'])
        periodo_chart = f"Cierre Ciclo ({fecha_fin_str})"
        if generar_dashboard_ejecutivo(df_vacio, df_dia, periodo_chart, img_dashboard, is_daily=True):
            if len(texto_completo) <= 1024:
                telegram_manager.enviar_foto_todos(img_dashboard, caption=texto_completo)
                foto_enviada = True
            else:
                caption_breve = f"{header}\n\n📊 <b>Resumen Gestión del Día</b> (<i>{fecha_fin_str}</i>)\n🔄 {iteraciones} iteraciones • ⏱️ {dur_str}"
                telegram_manager.enviar_foto_todos(img_dashboard, caption=caption_breve)
                telegram_manager.enviar_mensaje_todos(texto_completo)
                foto_enviada = True
    except Exception as e_dash:
        print(f"Error generando dashboard gráfico de fin de loop: {e_dash}")
    finally:
        if os.path.exists(img_dashboard):
            try:
                os.remove(img_dashboard)
            except Exception:
                pass

    if not foto_enviada:
        telegram_manager.enviar_mensaje_todos(texto_completo)


def main():
    print("Iniciando servicio de notificaciones resumidas de Telegram...")
    print(f"Horario Hourly: Lunes a Viernes entre las {HORA_INICIO_HOURLY}:00 y {HORA_FIN_HOURLY}:00.")
    print(f"Horario Daily: Lunes a Viernes a las {HORA_DAILY}.")

    schedule.every().day.at(HORA_DAILY).do(enviar_reporte_daily)
    schedule.every().hour.at(":00").do(enviar_reporte_hourly)

    while True:
        schedule.run_pending()
        time.sleep(10)
