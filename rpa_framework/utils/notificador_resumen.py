import time
import os
import datetime
import mysql.connector
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import FancyBboxPatch
from matplotlib.ticker import MaxNLocator
import schedule
import sys
from pathlib import Path

# Importar el telegram_manager local
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    import telegram_manager
except ImportError:
    print("No se pudo importar telegram_manager. Asegúrate de estar ejecutando desde el entorno correcto.")

# Configuraciones
HORA_INICIO_HOURLY = 9
HORA_FIN_HOURLY = 19
HORA_DAILY = "09:00"
DIAS_SEMANA_VALIDOS = [0, 1, 2, 3, 4] # Lunes a Viernes (0=Lunes, 4=Viernes)

# Archivo que indica que las notificaciones automáticas están pausadas
BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__))).parent
PAUSE_FILE = BASE_DIR / "config" / "notifications_paused.txt"
LOG_FILE   = BASE_DIR / "logs" / "rpa.log"


def notificaciones_pausadas() -> bool:
    """Retorna True si las notificaciones automáticas están suspendidas."""
    return PAUSE_FILE.exists()


def pausar_notificaciones():
    """Crea el archivo de pausa para suspender los reportes automáticos."""
    PAUSE_FILE.parent.mkdir(exist_ok=True)
    PAUSE_FILE.write_text(datetime.datetime.now().isoformat())


def reanudar_notificaciones():
    """Elimina el archivo de pausa para reanudar los reportes automáticos."""
    if PAUSE_FILE.exists():
        PAUSE_FILE.unlink()


def get_log_tail(n: int = 15) -> str:
    """Retorna las últimas n líneas del log de ejecución."""
    if not LOG_FILE.exists():
        return "⚠️ Archivo de log no encontrado."
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        tail = lines[-n:] if len(lines) >= n else lines
        return "".join(tail).strip() or "(log vacío)"
    except Exception as e:
        return f"❌ Error leyendo log: {e}"

def get_db_connection():
    try:
        from utils.mysql_auto_starter import ensure_mysql_running
        ensure_mysql_running()
    except Exception:
        pass
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="ris"
    )

def obtener_datos(fecha_inicio, fecha_fin):
    """Obtiene los registros de la base de datos entre dos fechas, excluyendo tareas utilitarias (conteo RIS y validación PACS)."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    query = """
    SELECT inicio, estado, estado_notificacion 
    FROM registro_acciones 
    WHERE inicio >= %s AND inicio <= %s
      AND (
          (ultimo_nodo IS NULL OR ultimo_nodo NOT IN ('Validación PACS', 'valida_pacs', 'seleccion int casos pendientes', 'casos_pendientes', 'Inicia RIS'))
          OR numero_documento IS NOT NULL
      )
      AND (observacion IS NULL OR (observacion NOT LIKE '%validación PACS%' AND observacion NOT LIKE '%validacion PACS%') OR numero_documento IS NOT NULL)
    """
    cursor.execute(query, (fecha_inicio, fecha_fin))
    datos = cursor.fetchall()
    conn.close()
    
    if not datos:
        return pd.DataFrame(columns=['inicio', 'estado', 'estado_notificacion'])
    return pd.DataFrame(datos)

def is_success(e):
    return any(k in str(e).lower() for k in ['terminado', 'finalizado', 'éxito', 'exito'])

def is_error(e):
    return any(k in str(e).lower() for k in ['error', 'fallo', 'falla', 'falló'])

def is_in_progress(e):
    return any(k in str(e).lower() for k in ['proceso'])

def generar_texto_resumen_hourly(df_hora, df_dia, periodo_str):
    """Genera un mensaje de texto formateado en HTML, claro y amigable para usuarios no técnicos."""
    total_hora = len(df_hora) if df_hora is not None else 0
    total_dia = len(df_dia) if df_dia is not None else 0
    
    # Fecha amigable en español
    now = datetime.datetime.now()
    dias_es = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
    dia_nombre = dias_es[now.weekday()]
    fecha_fmt = f"{dia_nombre} {now.strftime('%d/%m')}"
    
    texto = "📊 <b>Resumen Horario RPA</b>\n"
    texto += f"🕒 <b>Ventana:</b> {periodo_str} hrs | <i>{fecha_fmt}</i>\n\n"
    
    # 1. Actividad en la última hora
    texto += "⚡ <b>Actividad en la última hora:</b>\n"
    if total_hora == 0:
        texto += "• ℹ️ <i>Sin nuevos casos en esta ventana (Robot en espera activa)</i>\n"
    else:
        conteo_hora = df_hora['estado'].value_counts()
        exitos_h = sum(cnt for st, cnt in conteo_hora.items() if is_success(st))
        proceso_h = sum(cnt for st, cnt in conteo_hora.items() if is_in_progress(st))
        errores_h = sum(cnt for st, cnt in conteo_hora.items() if is_error(st))
        
        if exitos_h > 0:
            texto += f"• ✅ Procesados con éxito: <b>{exitos_h}</b>\n"
        if proceso_h > 0:
            texto += f"• ⏳ En ejecución: <b>{proceso_h}</b>\n"
        if errores_h > 0:
            texto += f"• ❌ Con incidencias: <b>{errores_h}</b>\n"
            
        # Otros estados no estándar
        for st, cnt in conteo_hora.items():
            if not (is_success(st) or is_in_progress(st) or is_error(st)):
                texto += f"• ℹ️ {st}: <b>{cnt}</b>\n"
                
        texto += f"👉 <i>Total en la hora: {total_hora} casos gestionados</i>\n"
        
    texto += "\n📈 <b>Acumulado de la jornada (Hoy):</b>\n"
    if total_dia == 0:
        texto += "• 🎯 Total procesados hoy: <b>0 casos</b>\n"
        texto += "• 🟢 Alertas pendientes: <b>Ninguna</b> ✨\n"
    else:
        conteo_dia = df_dia['estado'].value_counts()
        exitos_d = sum(cnt for st, cnt in conteo_dia.items() if is_success(st))
        errores_d = sum(cnt for st, cnt in conteo_dia.items() if is_error(st))
        
        texto += f"• 🎯 Total procesados hoy: <b>{total_dia} casos</b>\n"
        
        base_tasa = exitos_d + errores_d
        tasa = (exitos_d / base_tasa * 100) if base_tasa > 0 else 100.0
        tasa_emoji = "🟢" if tasa >= 95.0 else ("🟡" if tasa >= 80.0 else "🔴")
        texto += f"• {tasa_emoji} Tasa de efectividad: <b>{tasa:.1f}%</b>\n"
        
        # Desglose de errores y alertas pendientes
        pendientes = 0
        if errores_d > 0 and 'estado_notificacion' in df_dia.columns:
            df_err = df_dia[df_dia['estado'].astype(str).str.lower().str.contains('error|fall', na=False)]
            pendientes = len(df_err[df_err['estado_notificacion'] == 'Pendiente'])
            gestionados = len(df_err[df_err['estado_notificacion'] == 'Gestionado'])
            if pendientes > 0:
                texto += f"• ⚠️ Errores acumulados: <b>{errores_d}</b> (🔴 <b>{pendientes}</b> pendiente{'s' if pendientes > 1 else ''} de revisión)\n"
            else:
                texto += f"• ⚠️ Errores acumulados: <b>{errores_d}</b> (🟢 Todos gestionados)\n"
        elif errores_d == 0:
            texto += "• ⚠️ Alertas pendientes: <b>Ninguna</b> ✨\n"
            
    # Estado Operativo general
    texto += "\n"
    if total_dia == 0:
        texto += "💡 <b>Estado:</b> 🟢 <i>Sistema listo para operar</i>"
    elif 'pendientes' in locals() and pendientes > 0:
        texto += f"💡 <b>Estado:</b> ⚠️ <i>Atención requerida ({pendientes} alerta{'s' if pendientes > 1 else ''} pendiente{'s' if pendientes > 1 else ''})</i>"
    elif total_hora > 0 and any(is_error(st) for st in df_hora['estado'].unique()):
        texto += "💡 <b>Estado:</b> ⚠️ <i>Incidencia en la última hora</i>"
    elif total_hora == 0:
        texto += "💡 <b>Estado:</b> 🟢 <i>Operación fluida (esperando nuevos casos)</i>"
    else:
        texto += "💡 <b>Estado:</b> 🟢 <i>Operación normal sin incidencias</i>"
        
    return texto

def generar_dashboard_ejecutivo(df_hora, df_dia, periodo_str, filename, is_daily=False):
    """Genera una imagen unificada estilo dashboard ejecutivo con KPIs superiores y gráfico de progresión."""
    fig = plt.figure(figsize=(10, 5.8), facecolor='#f8fafc', dpi=150)
    gs = gridspec.GridSpec(2, 4, height_ratios=[1.1, 2.3], hspace=0.32, wspace=0.25,
                           left=0.06, right=0.94, top=0.92, bottom=0.10)

    total_dia = len(df_dia) if df_dia is not None else 0
    total_hora = len(df_hora) if df_hora is not None else 0
    
    exitos_d = sum(1 for e in df_dia['estado'] if is_success(e)) if total_dia > 0 else 0
    errores_d = sum(1 for e in df_dia['estado'] if is_error(e)) if total_dia > 0 else 0
    
    base_tasa = exitos_d + errores_d
    tasa_exito = (exitos_d / base_tasa * 100) if base_tasa > 0 else 100.0
    
    # 4 Tarjetas KPI superiores
    ventana_label = periodo_str.split(" a ")[0] if " a " in periodo_str else periodo_str
    if is_daily:
        kpis = [
            ('TOTAL DÍA', f'{total_dia}', 'Casos jornada', '#0f172a', '#ffffff', '#e2e8f0'),
            ('PROCESADOS', f'{exitos_d}', 'Exitosos', '#0284c7', '#f0f9ff', '#bae6fd'),
            ('EFECTIVIDAD', f'{tasa_exito:.1f}%', f'{exitos_d} completados', '#15803d' if tasa_exito >= 90 else '#b45309', '#f0fdf4' if tasa_exito >= 90 else '#fffbeb', '#bbf7d0' if tasa_exito >= 90 else '#fde68a'),
            ('INCIDENCIAS', f'{errores_d}', 'Alertas jornada' if errores_d > 0 else 'Sin alertas activas', '#b91c1c' if errores_d > 0 else '#475569', '#fef2f2' if errores_d > 0 else '#ffffff', '#fecaca' if errores_d > 0 else '#e2e8f0')
        ]
    else:
        kpis = [
            ('TOTAL DÍA', f'{total_dia}', 'Casos acumulados', '#0f172a', '#ffffff', '#e2e8f0'),
            ('ÚLTIMA HORA', f'{total_hora}', f'Ventana {ventana_label}', '#0284c7', '#f0f9ff', '#bae6fd'),
            ('EFECTIVIDAD', f'{tasa_exito:.1f}%', f'{exitos_d} exitosos hoy', '#15803d' if tasa_exito >= 90 else '#b45309', '#f0fdf4' if tasa_exito >= 90 else '#fffbeb', '#bbf7d0' if tasa_exito >= 90 else '#fde68a'),
            ('INCIDENCIAS', f'{errores_d}', 'Alertas hoy' if errores_d > 0 else 'Sin alertas activas', '#b91c1c' if errores_d > 0 else '#475569', '#fef2f2' if errores_d > 0 else '#ffffff', '#fecaca' if errores_d > 0 else '#e2e8f0')
        ]
    
    for i, (title, val, subtitle, text_col, bg_col, border_col) in enumerate(kpis):
        ax_kpi = fig.add_subplot(gs[0, i])
        ax_kpi.axis('off')
        
        # Tarjeta redondeada moderna
        p_bbox = FancyBboxPatch((0.02, 0.02), 0.96, 0.96,
                                boxstyle='round,pad=0.03,rounding_size=0.12',
                                ec=border_col, fc=bg_col, linewidth=1.2,
                                transform=ax_kpi.transAxes, zorder=1)
        ax_kpi.add_patch(p_bbox)
        
        ax_kpi.text(0.5, 0.77, title, ha='center', va='center', fontsize=9, fontweight='bold', color='#64748b', transform=ax_kpi.transAxes, zorder=2)
        ax_kpi.text(0.5, 0.44, val, ha='center', va='center', fontsize=19, fontweight='bold', color=text_col, transform=ax_kpi.transAxes, zorder=2)
        ax_kpi.text(0.5, 0.17, subtitle, ha='center', va='center', fontsize=8, color='#64748b', transform=ax_kpi.transAxes, zorder=2)

    # Gráfico inferior
    ax_chart = fig.add_subplot(gs[1, :])
    ax_chart.set_facecolor('#ffffff')
    
    # Fondo del chart card
    p_chart_bg = FancyBboxPatch((-0.03, -0.15), 1.06, 1.25,
                                boxstyle='round,pad=0.02,rounding_size=0.05',
                                ec='#e2e8f0', fc='#ffffff', linewidth=1.2,
                                transform=ax_chart.transAxes, zorder=0)
    ax_chart.add_patch(p_chart_bg)
    
    # Filtrar 'sin registros para trabajar' del gráfico
    df_chart = df_dia[df_dia['estado'] != 'sin registros para trabajar'].copy() if (df_dia is not None and not df_dia.empty) else pd.DataFrame()
    
    if not df_chart.empty:
        df_chart['hora'] = pd.to_datetime(df_chart['inicio']).dt.strftime('%H:00')
        agrupado = df_chart.groupby(['hora', 'estado']).size().unstack(fill_value=0)
        
        def get_col_color(c):
            cl = str(c).lower()
            if 'error' in cl or 'fall' in cl: return '#ef4444' # Rojo coral
            if any(x in cl for x in ['terminado', 'finalizado', 'exito', 'éxito']): return '#10b981' # Verde esmeralda
            if 'proceso' in cl: return '#0ea5e9' # Azul cielo
            if 'pending' in cl: return '#f59e0b' # Ámbar
            return '#94a3b8' # Gris pizarra
            
        colors = [get_col_color(col) for col in agrupado.columns]
        
        # Mapear nombres de columnas a etiquetas amigables para la leyenda
        def format_legend_label(col_name):
            cl = str(col_name).lower()
            if any(x in cl for x in ['terminado', 'finalizado', 'éxito', 'exito']): return 'Exitoso'
            if 'proceso' in cl: return 'En Proceso'
            if 'error' in cl or 'fall' in cl: return 'Error'
            if 'pending' in cl: return 'Pendiente'
            return str(col_name)
            
        agrupado.columns = [format_legend_label(c) for c in agrupado.columns]
        
        agrupado.plot(kind='bar', stacked=True, color=colors, ax=ax_chart, width=0.45, edgecolor='#ffffff', linewidth=1, zorder=3)
        
        chart_title = f'Progresión Cierre Diario RPA ({periodo_str})' if is_daily else f'Progresión de Gestiones por Hora (Ventana {periodo_str})'
        ax_chart.set_title(chart_title, fontsize=11, fontweight='bold', color='#1e293b', pad=12, zorder=4)
        ax_chart.set_xlabel('', fontsize=9)
        ax_chart.set_ylabel('Casos', fontsize=9, color='#64748b', labelpad=8)
        ax_chart.tick_params(axis='x', rotation=0, colors='#334155', labelsize=9)
        ax_chart.tick_params(axis='y', colors='#64748b', labelsize=8)
        ax_chart.yaxis.set_major_locator(MaxNLocator(integer=True))
        ax_chart.grid(axis='y', linestyle='--', alpha=0.35, color='#cbd5e1', zorder=1)
        
        # Eliminar bordes innecesarios
        for spine in ['top', 'right', 'left', 'bottom']:
            ax_chart.spines[spine].set_color('#e2e8f0')
            
        # Leyenda estilizada sin duplicados
        handles, labels = ax_chart.get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        leg = ax_chart.legend(by_label.values(), by_label.keys(), frameon=True, facecolor='#ffffff', edgecolor='#e2e8f0', fontsize=8.5, loc='upper left')
        if leg:
            leg.set_zorder(5)
        
        # Etiquetas numéricas dentro de las barras
        for c in ax_chart.containers:
            ax_chart.bar_label(c, label_type='center', fontsize=8.5, color='#ffffff', fontweight='bold', fmt=lambda x: f'{int(x)}' if x > 0 else '', zorder=6)
    else:
        ax_chart.text(0.5, 0.5, 'ℹ️ Sin actividad registrada en esta jornada', ha='center', va='center', color='#94a3b8', fontsize=12, fontweight='bold', transform=ax_chart.transAxes)
        ax_chart.axis('off')

    plt.savefig(filename, dpi=150, facecolor=fig.get_facecolor(), bbox_inches='tight')
    plt.close(fig)
    return True

def generar_tabla_imagen(df_hora, df_dia, periodo_str, filename):
    """Función de compatibilidad: Redirige a generar_dashboard_ejecutivo."""
    return generar_dashboard_ejecutivo(df_hora, df_dia, periodo_str, filename)

def generar_grafico_barras(df, filename):
    """Función de compatibilidad: Redirige a generar_dashboard_ejecutivo."""
    df_vacio = pd.DataFrame(columns=['inicio', 'estado', 'estado_notificacion'])
    return generar_dashboard_ejecutivo(df_vacio, df, "Hoy", filename, is_daily=True)

def generar_texto_resumen_simple(df, tipo_reporte, periodo_str):
    """Genera un texto de resumen simple y estructurado (usado para el cierre diario)."""
    if df.empty:
        return f"📊 <b>Resumen {tipo_reporte} ({periodo_str})</b>\n\nℹ️ <i>No hubo gestiones registradas en este período.</i>"
    
    total = len(df)
    conteo_estados = df['estado'].value_counts()
    
    exitos = sum(cnt for st, cnt in conteo_estados.items() if is_success(st))
    errores = sum(cnt for st, cnt in conteo_estados.items() if is_error(st))
    base_tasa = exitos + errores
    tasa = (exitos / base_tasa * 100) if base_tasa > 0 else 100.0
    tasa_emoji = "🟢" if tasa >= 95.0 else ("🟡" if tasa >= 80.0 else "🔴")
    
    texto = f"📊 <b>Resumen {tipo_reporte}</b>\n"
    texto += f"📅 <i>{periodo_str}</i>\n\n"
    texto += f"🎯 <b>Total Gestionado:</b> <b>{total} casos</b>\n"
    texto += f"{tasa_emoji} <b>Tasa de Efectividad:</b> <b>{tasa:.1f}%</b>\n\n"
    texto += "📋 <b>Desglose por Estado:</b>\n"
    
    if exitos > 0:
        texto += f"• ✅ Procesados con éxito: <b>{exitos}</b>\n"
    
    proceso = sum(cnt for st, cnt in conteo_estados.items() if is_in_progress(st))
    if proceso > 0:
        texto += f"• ⏳ En Proceso: <b>{proceso}</b>\n"
        
    if errores > 0:
        texto += f"• ❌ Con Incidencias / Error: <b>{errores}</b>\n"
        if 'estado_notificacion' in df.columns:
            df_err = df[df['estado'].astype(str).str.lower().str.contains('error|fall', na=False)]
            pendientes = len(df_err[df_err['estado_notificacion'] == 'Pendiente'])
            gestionados = len(df_err[df_err['estado_notificacion'] == 'Gestionado'])
            if pendientes > 0:
                texto += f"   └ 🔴 <b>{pendientes}</b> pendiente{'s' if pendientes > 1 else ''} de revisión\n"
            if gestionados > 0:
                texto += f"   └ 🟢 <b>{gestionados}</b> gestionado{'s' if gestionados > 1 else ''}\n"
                
    for st, cnt in conteo_estados.items():
        if not (is_success(st) or is_in_progress(st) or is_error(st)):
            texto += f"• ℹ️ {st}: <b>{cnt}</b>\n"
                
    return texto

def enviar_reporte_hourly(force=False):
    """Envía el reporte de la última hora y el acumulado del día con 1 dashboard visual y texto amigable.
    Se salta si las notificaciones están pausadas (a menos que force=True).
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
    
    # Enviar 1 sola imagen unificada (Dashboard Ejecutivo) con el texto descriptivo como caption
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

def main():
    print("Iniciando servicio de notificaciones resumidas de Telegram...")
    print(f"Horario Hourly: Lunes a Viernes entre las {HORA_INICIO_HOURLY}:00 y {HORA_FIN_HOURLY}:00.")
    print(f"Horario Daily: Lunes a Viernes a las {HORA_DAILY}.")
    
    # Programar reporte diario
    schedule.every().day.at(HORA_DAILY).do(enviar_reporte_daily)
    
    # Programar reportes horarios
    # Ejecutamos a la hora en punto (:00).
    schedule.every().hour.at(":00").do(enviar_reporte_hourly)
    
    # loop principal
    while True:
        schedule.run_pending()
        time.sleep(10)

if __name__ == "__main__":
    main()
