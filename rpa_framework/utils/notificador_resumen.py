import time
import os
import datetime
import mysql.connector
import pandas as pd
import matplotlib.pyplot as plt
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
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="ris"
    )

def obtener_datos(fecha_inicio, fecha_fin):
    """Obtiene los registros de la base de datos entre dos fechas."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    query = """
    SELECT inicio, estado, estado_notificacion 
    FROM registro_acciones 
    WHERE inicio >= %s AND inicio <= %s
    """
    cursor.execute(query, (fecha_inicio, fecha_fin))
    datos = cursor.fetchall()
    conn.close()
    
    if not datos:
        return pd.DataFrame(columns=['inicio', 'estado', 'estado_notificacion'])
    return pd.DataFrame(datos)

def generar_texto_resumen_hourly(df_hora, df_dia, periodo_str):
    """Genera el texto formateado HTML con dos columnas alineadas: Hora y Día."""
    total_hora = len(df_hora)
    total_dia = len(df_dia)
    
    estados_unicos = sorted(list(set(df_dia['estado'].unique()) | set(df_hora['estado'].unique())), key=lambda x: str(x))
    
    texto = f"📊 <b>Resumen Horario</b>\n"
    texto += f"📅 <i>{periodo_str}</i>\n\n"
    
    # Usamos un solo bloque <code> para que todo el cuadro use fuente monoespaciada
    table = "Estado          | Hr | Día\n"
    table += "--------------------------\n"
    
    conteo_hora = df_hora['estado'].value_counts()
    conteo_dia = df_dia['estado'].value_counts()
    
    for estado in estados_unicos:
        if not estado: continue
        est_str = str(estado)
        cant_h = conteo_hora.get(estado, 0)
        cant_d = conteo_dia.get(estado, 0)
        
        # Formatear nombre: Truncar si es muy largo para no romper la columna
        if len(est_str) > 15:
            nombre_f = est_str[:12] + "..."
        else:
            nombre_f = est_str.ljust(15)
            
        cant_h_f = str(cant_h).rjust(2)
        cant_d_f = str(cant_d).rjust(3)
        
        table += f"{nombre_f} | {cant_h_f} | {cant_d_f}\n"
        
        # Desglose de errores (sub-filas alineadas)
        if "error" in est_str.lower() and (cant_h > 0 or cant_d > 0):
            df_err_h = df_hora[df_hora['estado'] == estado]
            df_err_d = df_dia[df_dia['estado'] == estado]
            
            ph = len(df_err_h[df_err_h['estado_notificacion'] == 'Pendiente'])
            gh = len(df_err_h[df_err_h['estado_notificacion'] == 'Gestionado'])
            pd = len(df_err_d[df_err_d['estado_notificacion'] == 'Pendiente'])
            gd = len(df_err_d[df_err_d['estado_notificacion'] == 'Gestionado'])
            
            table += f" > Pnd/Gst Hr: {ph}/{gh}\n"
            table += f" > Pnd/Gst Dí: {pd}/{gd}\n"

    table += "--------------------------\n"
    table += f"TOTALES         | {str(total_hora).rjust(2)} | {str(total_dia).rjust(3)}"
    
    texto += f"<code>{table}</code>"
    return texto

def generar_tabla_imagen(df_hora, df_dia, periodo_str, filename):
    """Genera una imagen con una tabla estilizada de los resultados."""
    if df_dia.empty:
        return False
        
    # Preparar datos
    estados_unicos = sorted(list(set(df_dia['estado'].unique()) | set(df_hora['estado'].unique())), key=lambda x: str(x))
    conteo_hora = df_hora['estado'].value_counts()
    conteo_dia = df_dia['estado'].value_counts()
    
    table_data = []
    for est in estados_unicos:
        if not est: continue
        h = conteo_hora.get(est, 0)
        d = conteo_dia.get(est, 0)
        table_data.append([str(est), h, d])
    
    # Agregar totales
    table_data.append(["TOTALES", len(df_hora), len(df_dia)])
    
    # Crear figura
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.axis('off')
    
    # Estilo de la tabla
    col_labels = ["Estado", "Última Hora", "Acumulado Día"]
    table = ax.table(cellText=table_data, colLabels=col_labels, loc='center', cellLoc='center')
    
    # Personalizar apariencia
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.2, 1.8)
    
    # Colores
    for (row, col), cell in table.get_celld().items():
        if row == 0: # Header
            cell.set_text_props(weight='bold', color='white')
            cell.set_facecolor('#2c3e50')
        elif row == len(table_data): # Totales
            cell.set_text_props(weight='bold')
            cell.set_facecolor('#ecf0f1')
        
        # Bordes suaves
        cell.set_edgecolor('#bdc3c7')

    plt.title(f"Resumen RPA - {periodo_str}", fontsize=14, pad=20, weight='bold', color='#2c3e50')
    plt.tight_layout()
    plt.savefig(filename, dpi=150, bbox_inches='tight')
    plt.close()
    return True

def generar_texto_resumen_simple(df, tipo_reporte, periodo_str):
    # ... (mismo que antes)
    """Genera un texto de resumen simple (usado para el cierre diario)."""
    if df.empty:
        return f"📊 <b>Resumen {tipo_reporte} ({periodo_str})</b>\n\nNo hubo gestiones."
    
    total = len(df)
    conteo_estados = df['estado'].value_counts()
    
    texto = f"📊 <b>Resumen {tipo_reporte}</b>\n"
    texto += f"📅 <i>{periodo_str}</i>\n\n"
    texto += f"<b>Total Gestionado:</b> {total}\n"
    texto += "<b>Desglose por Estado:</b>\n"
    
    for estado, cantidad in conteo_estados.items():
        if not estado: continue
        estado_str = str(estado)
        emoji = "✅" if any(x in estado_str.lower() for x in ["terminado", "finalizado"]) else ("⚠️" if "error" in estado_str.lower() else "ℹ️")
        texto += f"{emoji} {estado_str}: {cantidad}\n"
        
        if "error" in estado_str.lower():
            df_errores = df[df['estado'] == estado]
            pendientes = len(df_errores[df_errores['estado_notificacion'] == 'Pendiente'])
            gestionados = len(df_errores[df_errores['estado_notificacion'] == 'Gestionado'])
            texto += f"   └ 🔴 Pendientes: {pendientes}\n"
            texto += f"   └ 🟢 Gestionados: {gestionados}\n"
                
    return texto

def generar_grafico_barras(df, filename):
    """Genera un gráfico de barras apiladas agrupado por hora."""
    if df.empty:
        return False
        
    # Excluir 'sin registros para trabajar' solo de los gráficos
    df_grafico = df[df['estado'] != 'sin registros para trabajar'].copy()
    
    if df_grafico.empty:
        return False
        
    # Extraer la hora
    df_grafico['hora'] = pd.to_datetime(df_grafico['inicio']).dt.strftime('%H:00')
    
    # Agrupar por hora y estado
    agrupado = df_grafico.groupby(['hora', 'estado']).size().unstack(fill_value=0)
    
    # Configurar estilo y colores
    plt.figure(figsize=(10, 6))
    plt.style.use('ggplot')
    
    # Paleta de colores atractiva
    colores_estados = {
        'error': '#e74c3c',           # Rojo
        'Finalizado': '#2ecc71',      # Verde
        'Terminado': '#27ae60',       # Verde oscuro
        'Terminado - Pending': '#f1c40f', # Amarillo
        'no_match': '#95a5a6',        # Gris
    }
    
    # Obtener colores para los estados presentes en los datos
    colores_plot = [colores_estados.get(str(col).strip(), '#3498db') for col in agrupado.columns]
    
    ax = agrupado.plot(kind='bar', stacked=True, color=colores_plot, ax=plt.gca())
    
    plt.title('Gestiones por Hora y Estado', fontsize=14, pad=15)
    plt.xlabel('Hora de Inicio', fontsize=12)
    plt.ylabel('Cantidad', fontsize=12)
    plt.xticks(rotation=0)
    plt.legend(title='Estado', bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    
    # Añadir valores dentro de las barras (opcional, solo si caben)
    for c in ax.containers:
        # Solo mostrar el valor si la altura de la barra es > 0
        ax.bar_label(c, label_type='center', fontsize=9, fmt=lambda x: f'{int(x)}' if x > 0 else '')
        
    plt.savefig(filename, dpi=120, bbox_inches='tight')
    plt.close()
    return True

def enviar_reporte_hourly(force=False):
    """Envía el reporte de la última hora y el acumulado del día.
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
    
    # 1. Imagen 1: Gráfico de barras (Progresión)
    img_chart = "hourly_chart_temp.png"
    if generar_grafico_barras(df_dia, img_chart):
        telegram_manager.enviar_foto_todos(img_chart, caption="📈 Progresión del día por hora")
        if os.path.exists(img_chart): os.remove(img_chart)
        
    # 2. Imagen 2: Tabla visual (Resumen ejecutivo)
    img_table = "hourly_table_temp.png"
    if generar_tabla_imagen(df_hora, df_dia, periodo_str, img_table):
        # Enviamos la tabla con el texto de resumen como caption para que se pueda copiar
        telegram_manager.enviar_foto_todos(img_table, caption=texto)
        if os.path.exists(img_table): os.remove(img_table)
    else:
        telegram_manager.enviar_alerta_todos(texto)

def enviar_reporte_daily():
    """Envía el reporte del día anterior completo con imagen y texto.
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
    
    # 1. Gráfico de barras
    img_chart = "daily_chart_temp.png"
    if generar_grafico_barras(df, img_chart):
        telegram_manager.enviar_foto_todos(img_chart, caption=f"📈 Progresión del día {periodo_str}")
        if os.path.exists(img_chart): os.remove(img_chart)
    
    # 2. Tabla visual
    img_table = "daily_table_temp.png"
    # Para el diario, pasamos un DF vacío para la 'hora' para que se enfoque en el acumulado
    df_vacio = pd.DataFrame(columns=['estado'])
    if generar_tabla_imagen(df_vacio, df, periodo_str, img_table):
        telegram_manager.enviar_foto_todos(img_table, caption=texto)
        if os.path.exists(img_table): os.remove(img_table)
    else:
        telegram_manager.enviar_alerta_todos(texto)

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
