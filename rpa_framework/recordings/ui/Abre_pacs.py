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

try:
    from rpa_framework.utils.window_utils import maximize_hwnd, maximize_pacs_windows, force_foreground_window
except ImportError:
    try:
        from utils.window_utils import maximize_hwnd, maximize_pacs_windows, force_foreground_window
    except ImportError:
        maximize_hwnd = None
        maximize_pacs_windows = None
        force_foreground_window = None

try:
    from rpa_framework.utils.screen_utils import attach_to_interactive_desktop
    attach_to_interactive_desktop()
except Exception:
    try:
        from utils.screen_utils import attach_to_interactive_desktop
        attach_to_interactive_desktop()
    except Exception:
        pass

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
    "ckmvs.exe",
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
        cflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, creationflags=cflags)
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

def minimizar_navegadores():
    """Minimiza ventanas de Chrome o navegadores para despejar la pantalla para el PACS."""
    try:
        import win32gui
        import win32con
        import win32process
        import psutil

        def cb(hwnd, _):
            if win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd) and not win32gui.IsIconic(hwnd):
                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    pname = psutil.Process(pid).name().lower()
                    if "chrome" in pname or "msedge" in pname:
                        win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                except Exception:
                    pass
            return True

        win32gui.EnumWindows(cb, None)
    except Exception as e:
        logger.debug(f"Aviso minimizando navegadores: {e}")

def abrir_vue_pacs():
    """Abre solo Vue PACS."""
    logger.info("Minimizando navegadores para despejar escritorio...")
    minimizar_navegadores()

    logger.info("Abriendo Vue PACS en escritorio interactivo (WinSta0\\Default)...")
    
    work_dir = os.path.dirname(RUTA_EXE)
    try:
        import win32process
        import win32con
        si = win32process.STARTUPINFO()
        si.lpDesktop = "WinSta0\\Default"
        si.dwFlags = win32process.STARTF_USESHOWWINDOW
        si.wShowWindow = win32con.SW_SHOWNORMAL
        hProcess, hThread, pid, tid = win32process.CreateProcess(
            RUTA_EXE,
            f'"{RUTA_EXE}"',
            None,
            None,
            False,
            0,
            None,
            work_dir,
            si
        )
        app = Application(backend="win32").connect(process=pid)
    except Exception as cp_err:
        logger.warning(f"CreateProcess directo falló ({cp_err}), usando Application.start...")
        app = Application(backend="win32").start(f'"{RUTA_EXE}"', work_dir=work_dir)
        pid = app.process
    logger.info(f"   PID: {pid} (work_dir: {work_dir})")

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

    # 1. Esperar activamente y detectar ventanas de Carestream Vue PACS
    logger.info("Esperando que las ventanas de Carestream Vue PACS se inicialicen...")
    todas_pacs = []
    start_wait = time.time()
    while (time.time() - start_wait) < 20:
        for titulo in TITULOS_CARESTREAM:
            try:
                ventanas = fw.find_windows(title_re=re.compile(f".*{re.escape(titulo)}.*", re.I))
                for h in ventanas:
                    if h not in todas_pacs:
                        todas_pacs.append(h)
            except Exception:
                pass
        if todas_pacs:
            break
        time.sleep(1)

    if not todas_pacs:
        logger.error("PACS demoró demasiado en abrir (> 20s). No se detectaron ventanas de Carestream.")
        raise Exception("Timeout apertura PACS")

    logger.info(f"   Detectadas {len(todas_pacs)} ventana(s) de Carestream: {todas_pacs}")

    # 2. Forzar que TODAS las ventanas de Carestream pasen al primer plano visible (sin maximizar login)
    logger.info("   Restaurando y trayendo ventana(s) de Vue PACS al primer plano (sin maximizar)...")
    for hwnd in todas_pacs:
        if force_foreground_window:
            force_foreground_window(hwnd, maximize=False)
        else:
            try:
                import win32gui
                import win32con
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                else:
                    win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                win32gui.SetForegroundWindow(hwnd)
            except Exception:
                pass

    # 3. Vincular ventana principal
    main_window = Desktop(backend="win32").window(handle=todas_pacs[0])
    titulo_real = main_window.window_text()
    logger.info(f"   Ventana principal Carestream vinculada: '{titulo_real}' (hwnd: {main_window.handle})")

    if vf:
        vf.wait(3, "Finalizando apertura Vue PACS...")
    else:
        time.sleep(3)

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
