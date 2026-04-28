"""
Script RPA: Cierra TODOS los programas Carestream + Abre Vue PACS limpio
- Carestream Vue PACS (mp.exe)
- Carestream RIS V11 Client  
- RIS Client
"""

from pywinauto import Application, Desktop
from pywinauto import timings
import pywinauto.findwindows as fw
import os
import re
import time
import psutil
import logging
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Configurar path para importar utilidades
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

# Importar utilidades
try:
    from rpa_framework.utils.visual_feedback import VisualFeedback
    vf_instance = VisualFeedback()
except:
    vf_instance = None

try:
    from rpa_framework.utils.telegram_manager import enviar_alerta_todos
except ImportError:
    enviar_alerta_todos = None

try:
    from utils.error_handler import handle_error_and_exit
except ImportError:
    try:
        from rpa_framework.utils.error_handler import handle_error_and_exit
    except ImportError:
        handle_error_and_exit = None

def get_vf():
    return vf_instance

vf = get_vf()

# =====================================================
# CONFIGURACIÓN - TODOS los programas Carestream
# =====================================================
RUTA_EXE = r"C:\Program Files\Carestream\PACS\cshpacs\mv_client\mp.exe"

# Lista de TODOS los títulos a cerrar
TITULOS_CARESTREAM = [
    "Carestream Vue PACS",
    "Carestream RIS",
    "Carestream RIS V11 Client",
    "RIS Client",
    "Carestream Radiology Client",
    "Carestream Vue RIS",
    "PACS - Carestream",
    "Workflow Information Management",
    "Philips Workflow Information Management"
]

# Procesos conocidos que deben cerrarse
PROCESOS_CARESTREAM = [
    "mp.exe", 
    "csps_win.exe", 
    "RISClient.exe", 
    "CarestreamRIS.exe",
    "Vue RIS.exe",
    "vv_client.exe"
]

def debug_listar_ventanas():
    """Lista TODAS las ventanas Carestream."""
    todas_ventanas = []
    for titulo in TITULOS_CARESTREAM:
        ventanas = fw.find_windows(title_re=re.compile(re.escape(titulo), re.I))
        todas_ventanas.extend(ventanas)
    
    logger.info(f"{len(todas_ventanas)} ventanas Carestream:")
    for hwnd in todas_ventanas:
        try:
            win = Desktop(backend="win32").window(handle=hwnd)
            logger.info(f"   '{win.window_text()}' | hwnd: {hwnd}")
        except:
            pass


def cerrar_todos_carestream():
    """Cierra TODOS los programas Carestream (ventanas y procesos)."""
    logger.info("Iniciando limpieza agresiva de programas Carestream...")
    
    # 1. CERRAR POR VENTANAS (Intento grácil, luego forzoso)
    for titulo in TITULOS_CARESTREAM:
        try:
            # Usamos regex para encontrar cualquier ventana que contenga el título
            ventanas = fw.find_windows(title_re=re.compile(f".*{re.escape(titulo)}.*", re.I))
            if ventanas:
                logger.info(f"   Cerrando {len(ventanas)} ventanas de '{titulo}'")
                for hwnd in ventanas:
                    try:
                        # Conectamos por handle para ser específicos
                        app_tmp = Application(backend="win32").connect(handle=hwnd, timeout=1)
                        # Usar kill() en lugar de close() para forzar el cierre del proceso asociado
                        app_tmp.kill()
                        time.sleep(0.5)
                    except:
                        pass
        except:
            pass

    # 2. MATAR PROCESOS POR POWERSHELL (Nombres de Administrador de Tareas)
    logger.info("   Buscando procesos por Descripción / Nombre en Administrador de Tareas...")
    ps_cmd = 'Get-Process | Where-Object { $_.Description -match "Carestream Radiology Client|Carestream Vue PACS|Carestream RIS" -or $_.MainWindowTitle -match "Carestream" } | Where-Object { $_.Name -notmatch "svchost|carestream_host" } | Stop-Process -Force'
    try:
        import subprocess
        subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True)
    except Exception as e:
        logger.warning(f"Error al ejecutar powershell stop-process: {e}")

    # 3. MATAR PROCESOS (Fuerza bruta para múltiples instancias)
    logger.info("   Limpiando procesos remanentes por ejecutable...")
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            name_lower = proc.info['name'].lower()
            # Matamos si está en la lista o si el nombre contiene carestream (siendo cuidadosos)
            if any(p.lower() == name_lower for p in PROCESOS_CARESTREAM) or \
               ("carestream" in name_lower and name_lower != "carestream_host.exe"): # Evitar matar servicios si existen
                logger.info(f"      Matando {name_lower} (PID: {proc.pid})")
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # 3. VERIFICACIÓN FINAL Y ESPERA
    timeout = 5
    while timeout > 0:
        pacs_vivos = [p for p in psutil.process_iter(['name']) 
                     if p.info['name'].lower() in [n.lower() for n in PROCESOS_CARESTREAM]]
        if not pacs_vivos:
            break
        logger.info(f"      Esperando a que {len(pacs_vivos)} procesos terminen...")
        time.sleep(1)
        timeout -= 1
    
    logger.info("Limpieza completada.")

def abrir_vue_pacs():
    """Abre solo Vue PACS."""
    logger.info("Abriendo Vue PACS...")
    
    app = Application(backend="win32").start(f'"{RUTA_EXE}"')
    pid = app.process
    logger.info(f"   PID: {pid}")

    # Esperar CPU (Reducido para reintento rápido si se cuelga)
    try:
        app.wait_cpu_usage_lower(threshold=15, timeout=10)
        logger.info("   CPU estabilizada")
    except:
        logger.warning("   CPU no estabilizada en 10s, intentando continuar...")

    # DEBUG
    if vf:
        vf.wait(3, "Debug Listar Ventanas...")
    else:
        time.sleep(3)
    debug_listar_ventanas()

    # Tomar ventana PRINCIPAL (soluciona las 2 ventanas)
    logger.info("top_window()...")
    main_window = app.top_window()
    
    titulo_real = main_window.window_text()
    logger.info(f"   '{titulo_real}' hwnd: {main_window.handle}")

    # Esperas seguras - REINTENTO SI DEMORA
    try:
        main_window.wait("exists visible", timeout=10)
        logger.info("   Visible")
    except Exception as e:
        logger.error(f"   PACS demoró demasiado en abrir (> 10s). Forzando reintento...")
        raise Exception("Timeout apertura PACS")

    try:
        main_window.wait("enabled", timeout=20)
        logger.info("   Habilitada")
    except:
        logger.info("   No enabled (normal)")

    if vf:
        vf.wait(5, "Finalizando apertura Vue PACS...")
    else:
        time.sleep(5)
    logger.info(f"LISTA: '{titulo_real}'")
    print(f"\nVue PACS listo!\nhwnd: {main_window.handle}")
    
    return app, main_window

def main():
    logger.info("=" * 70)
    logger.info("RPA CARESTREAM: CIERRE TOTAL + VUE PACS")
    logger.info("=" * 70)
    
    MAX_INTENTOS = 3
    intentos = 0
    ultimo_error = ""

    while intentos < MAX_INTENTOS:
        intentos += 1
        logger.info(f"Intento de apertura #{intentos} / {MAX_INTENTOS}")
        try:
            cerrar_todos_carestream()
            if vf:
                vf.wait(3, f"Pausa estabilidad (Intento {intentos})...")
            else:
                time.sleep(3)  # Pausa para estabilidad
            
            return abrir_vue_pacs()
            
        except Exception as e:
            ultimo_error = str(e)
            logger.error(f"\nERROR en intento {intentos}: {e}")
            
            if intentos < MAX_INTENTOS:
                logger.info("Esperando 10 segundos antes del próximo reintento...")
                time.sleep(10)
            else:
                logger.error("Se agotaron los reintentos.")

    # Si llegamos aquí, fallaron todos los intentos
    msg = f"No se pudo abrir el PACS después de {MAX_INTENTOS} intentos. Último error: {ultimo_error}"
    if handle_error_and_exit:
        handle_error_and_exit("Abre_pacs.py", msg)
    else:
        raise Exception(msg)

if __name__ == "__main__":
    app, window = main()
