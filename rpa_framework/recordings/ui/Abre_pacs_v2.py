"""
Script RPA: Abre_pacs_v2.py
Versión optimizada de Abre_pacs.py:
- Reduce esperas estáticas (sleep 3s -> 0.5s).
- Detección ágil de ventanas Carestream Vue PACS.
- Elimina pausas de depuración innecesarias.
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

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

try:
    from rpa_framework.utils.visual_feedback import VisualFeedback
    vf_instance = VisualFeedback()
except:
    vf_instance = None

try:
    from rpa_framework.utils.window_utils import force_foreground_window
except ImportError:
    force_foreground_window = None

RUTA_EXE = r"C:\Program Files\Carestream\PACS\cshpacs\mv_client\mp.exe"

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

PROCESOS_CARESTREAM = [
    "mp.exe", 
    "ckmvs.exe",
    "csps_win.exe", 
    "RISClient.exe", 
    "CarestreamRIS.exe",
    "Vue RIS.exe",
    "vv_client.exe"
]


def cerrar_todos_carestream():
    """Cierra todos los programas Carestream de forma rápida."""
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'].lower() in [p.lower() for p in PROCESOS_CARESTREAM]:
                proc.kill()
        except:
            pass


def abrir_vue_pacs():
    """Abre solo Vue PACS de forma rápida."""
    work_dir = os.path.dirname(RUTA_EXE)
    try:
        import win32process
        import win32con
        si = win32process.STARTUPINFO()
        si.lpDesktop = "WinSta0\\Default"
        si.dwFlags = win32process.STARTF_USESHOWWINDOW
        si.wShowWindow = win32con.SW_SHOWNORMAL
        hProcess, hThread, pid, tid = win32process.CreateProcess(
            RUTA_EXE, f'"{RUTA_EXE}"', None, None, False, 0, None, work_dir, si
        )
        app = Application(backend="win32").connect(process=pid)
    except Exception:
        app = Application(backend="win32").start(f'"{RUTA_EXE}"', work_dir=work_dir)
        pid = app.process
    logger.info(f"   Vue PACS lanzado con PID: {pid}")

    # Esperar CPU brevemente (máx 3s)
    try:
        app.wait_cpu_usage_lower(threshold=15, timeout=3)
    except:
        pass

    # Esperar activamente ventana de login
    todas_pacs = []
    start_wait = time.time()
    while (time.time() - start_wait) < 15:
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
        time.sleep(0.3)

    if not todas_pacs:
        raise Exception("Timeout esperando ventana de Carestream Vue PACS")

    # Traer al frente
    for hwnd in todas_pacs:
        if force_foreground_window:
            force_foreground_window(hwnd, maximize=False)
        else:
            try:
                import win32gui, win32con
                win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                win32gui.SetForegroundWindow(hwnd)
            except Exception:
                pass

    main_window = Desktop(backend="win32").window(handle=todas_pacs[0])
    print(f"\nVue PACS listo!\nhwnd: {main_window.handle}")
    return app, main_window


def main():
    logger.info("RPA CARESTREAM: APERTURA OPTIMIZADA V2")
    cerrar_todos_carestream()
    time.sleep(0.5)
    return abrir_vue_pacs()


if __name__ == "__main__":
    app, window = main()
