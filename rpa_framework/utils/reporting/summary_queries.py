"""
Consultas a base de datos, estado de ejecución y clasificadores de estado para reportes RPA.
"""
import datetime
import json
import os
import time
from pathlib import Path
import mysql.connector
import pandas as pd

# Configuraciones
HORA_INICIO_HOURLY = 9
HORA_FIN_HOURLY = 19
HORA_DAILY = "09:00"
DIAS_SEMANA_VALIDOS = [0, 1, 2, 3, 4]  # Lunes a Viernes (0=Lunes, 4=Viernes)

# BASE_DIR apunta a rpa_framework/ (dos niveles arriba de utils/reporting/)
BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__))).parent.parent
PAUSE_FILE = BASE_DIR / "config" / "notifications_paused.txt"
LOG_FILE = BASE_DIR / "logs" / "rpa.log"
LAST_WORKFLOW_FILE = BASE_DIR / "config" / "last_workflow_execution.json"
EXECUTION_STATE_FILE = BASE_DIR / "config" / "execution_state.json"


def registrar_ejecucion_workflow(workflow_name: str = "", status: str = "running"):
    """Registra la ejecución reciente de un workflow para el control del notificador horario."""
    try:
        LAST_WORKFLOW_FILE.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "workflow": workflow_name,
            "status": status,
            "timestamp": time.time(),
            "datetime": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        with open(LAST_WORKFLOW_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"⚠️ Error registrando ejecución de workflow: {e}")


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


def se_ejecuto_workflow_ultimos_minutos(minutos: int = 60, tolerancia_minutos: int = 5) -> bool:
    """
    Retorna True si se ejecutó o está ejecutándose algún workflow durante los últimos N minutos (por defecto 60 + 5m tolerancia).
    Consulta múltiples fuentes fiables:
    1. Estado de ejecución actual (execution_state.json).
    2. Archivo de tracking de última ejecución (last_workflow_execution.json).
    3. Registros de acciones en la base de datos MySQL (tabla registro_acciones).
    4. Archivos de logs de workflows (wf_*.log).
    """
    ventana_segundos = (minutos + tolerancia_minutos) * 60
    ahora_ts = time.time()
    ahora_dt = datetime.datetime.now()
    limite_dt = ahora_dt - datetime.timedelta(seconds=ventana_segundos)

    # 1. Verificar si hay un workflow en ejecución activa en este instante
    if EXECUTION_STATE_FILE.exists():
        try:
            with open(EXECUTION_STATE_FILE, "r", encoding="utf-8") as f:
                state_data = json.load(f)
            if state_data.get("is_running", False):
                return True
            updated_at = state_data.get("updated_at", 0)
            if ahora_ts - updated_at <= ventana_segundos:
                return True
        except Exception:
            pass

    # 2. Verificar archivo de tracking de última ejecución
    if LAST_WORKFLOW_FILE.exists():
        try:
            with open(LAST_WORKFLOW_FILE, "r", encoding="utf-8") as f:
                last_data = json.load(f)
            ts = last_data.get("timestamp", 0)
            if ahora_ts - ts <= ventana_segundos:
                return True
        except Exception:
            pass

    # 3. Verificar registros en base de datos MySQL (tabla registro_acciones)
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "SELECT id FROM registro_acciones WHERE inicio >= %s OR `update` >= %s LIMIT 1"
        cursor.execute(query, (limite_dt, limite_dt))
        row = cursor.fetchone()
        conn.close()
        if row:
            return True
    except Exception:
        pass

    # 4. Verificar archivos de logs de workflows (wf_*.log)
    log_dirs = [
        BASE_DIR / "logs",
        BASE_DIR.parent / "logs",
        BASE_DIR / "workflows" / "logs",
    ]
    for d in log_dirs:
        if not d.exists():
            continue
        try:
            for item in d.glob("wf_*.log"):
                try:
                    mtime = item.stat().st_mtime
                    if ahora_ts - mtime <= ventana_segundos:
                        return True
                except Exception:
                    pass
        except Exception:
            pass

    return False


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


def obtener_datos(fecha_inicio, fecha_fin):
    """Obtiene los registros de la base de datos entre dos fechas, excluyendo tareas utilitarias (conteo RIS, validación PACS y VPN)."""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
    SELECT inicio, estado, estado_notificacion 
    FROM registro_acciones 
    WHERE inicio >= %s AND inicio <= %s
      AND (
          (ultimo_nodo IS NULL OR ultimo_nodo NOT IN ('Validación PACS', 'valida_pacs', 'seleccion int casos pendientes', 'casos_pendientes', 'Inicia RIS', 'Verifica VPN', 'verifica_vpn', 'Comprueba VPN', 'comprueba vpn'))
          OR numero_documento IS NOT NULL
      )
      AND (observacion IS NULL OR (observacion NOT LIKE '%validación PACS%' AND observacion NOT LIKE '%validacion PACS%' AND observacion NOT LIKE '%VPN%' AND observacion NOT LIKE '%vpn%') OR numero_documento IS NOT NULL)
      AND (estado != 'sin registros para trabajar' OR numero_documento IS NOT NULL)
    """
    cursor.execute(query, (fecha_inicio, fecha_fin))
    datos = cursor.fetchall()
    conn.close()

    if not datos:
        return pd.DataFrame(columns=['inicio', 'estado', 'estado_notificacion'])
    return pd.DataFrame(datos)


def is_addendum(e):
    return 'addendum' in str(e).lower()


def is_ya_ingresado(e):
    return any(k in str(e).lower() for k in ['ya ingresado', 'ya_ingresado'])


def is_pending_approval(e):
    return any(k in str(e).lower() for k in ['aprobacion_pendiente', 'pendiente de aprobación', 'pending'])


def is_success_standard(e):
    st = str(e).lower()
    return any(k in st for k in ['terminado', 'finalizado', 'éxito', 'exito']) and not (is_pending_approval(e) or is_addendum(e) or is_ya_ingresado(e))


def is_success(e):
    st = str(e).lower()
    return any(k in st for k in ['terminado', 'finalizado', 'éxito', 'exito', 'addendum', 'ya ingresado', 'ya_ingresado']) or is_pending_approval(e)


def is_error(e):
    st = str(e).lower()
    return any(k in st for k in ['error', 'fallo', 'falla', 'falló']) and not is_pending_approval(e) and not is_addendum(e) and not is_ya_ingresado(e) and not any(k in st for k in ['sin registros', 'vpn'])


def is_in_progress(e):
    return any(k in str(e).lower() for k in ['proceso'])
