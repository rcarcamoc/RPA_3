"""
Módulo de utilidades de ventanas para RPA Framework 3.

Proporciona funciones robustas para buscar, enfocar y maximizar
ventanas del sistema operativo Windows, enfocado especialmente en:
- Carestream Vue PACS (mp.exe)
- Carestream RIS / Vue RIS / Workflow Information Management
- RIS Web (Google Chrome)
"""

import sys
import re
import time
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

# Títulos conocidos de Carestream PACS y RIS Desktop
TITULOS_PACS_RIS = [
    "Carestream Vue PACS",
    "Carestream RIS",
    "Carestream RIS V11 Client",
    "RIS Client",
    "Carestream Radiology Client",
    "Carestream Vue RIS",
    "PACS - Carestream",
    "Workflow Information Management",
    "Philips Workflow Information Management",
    "Carestream Client"
]

# Procesos conocidos de PACS y RIS
PROCESOS_PACS_RIS = [
    "mp.exe",
    "Carestream RIS.exe",
    "RISClient.exe",
    "Vue RIS.exe",
    "vv_client.exe"
]

def is_pacs_login_window(hwnd: int) -> bool:
    """
    Detecta si una ventana corresponde al diálogo modal de login de Carestream Vue PACS
    (que nunca debe ser maximizado para no distorsionar su UI ni romper coordenadas).
    """
    if not hwnd:
        return False
    try:
        import win32gui
        # Si la ventana es pequeña, como el diálogo de login (~500x350)
        rect = win32gui.GetWindowRect(hwnd)
        w = rect[2] - rect[0]
        h = rect[3] - rect[1]
        if 0 < w < 850 and 0 < h < 700:
            title = win32gui.GetWindowText(hwnd).strip()
            if any(t.lower() in title.lower() for t in ["carestream", "vue pacs", "pacs"]):
                return True
    except Exception:
        pass
    try:
        from pywinauto import Desktop
        win = Desktop(backend="uia").window(handle=hwnd)
        if win.child_window(auto_id="txtPassword").exists(timeout=0.1) or \
           win.child_window(auto_id="txtUsername").exists(timeout=0.1):
            return True
    except Exception:
        pass
    return False


def force_foreground_window(hwnd: int, maximize: bool = False) -> bool:
    """
    Fuerza a una ventana a pasar al primer plano (foreground) absoluto,
    superando las restricciones de UIPI y bloqueo de foco de Windows 10/11.
    
    Args:
        hwnd: Handle numérico de la ventana.
        maximize: Si es True, maximiza la ventana (a menos que sea el diálogo de login).
                  Si es False (por defecto), solo la muestra/restaura a su tamaño normal.
    """
    if not hwnd:
        return False
    try:
        import win32gui
        import win32con
        import ctypes
        
        # 1. Asegurar desktop interactivo
        try:
            from utils.screen_utils import attach_to_interactive_desktop
            attach_to_interactive_desktop()
        except Exception:
            try:
                from rpa_framework.utils.screen_utils import attach_to_interactive_desktop
                attach_to_interactive_desktop()
            except Exception:
                pass

        if not win32gui.IsWindow(hwnd):
            return False

        # Si está minimizada, restaurar
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            time.sleep(0.1)

        # Si es el diálogo de login de PACS, nunca maximizar
        if maximize and not is_pacs_login_window(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
        else:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)

        # 2. Simulación de Alt-Key para reiniciar timer de bloqueo de foco en Windows
        user32 = ctypes.windll.user32
        user32.keybd_event(0x12, 0, 0, 0)  # ALT down
        user32.keybd_event(0x12, 0, 2, 0)  # ALT up

        # 3. Z-order toggle: HWND_TOPMOST -> HWND_NOTOPMOST
        # Obliga al DWM de Windows a colocar la ventana físicamente al frente de las demás
        win32gui.SetWindowPos(hwnd, win32con.HWND_TOPMOST, 0, 0, 0, 0,
                             win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW)
        win32gui.SetWindowPos(hwnd, win32con.HWND_NOTOPMOST, 0, 0, 0, 0,
                             win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW)

        # 4. Traer al frente y enfocar
        try:
            win32gui.BringWindowToTop(hwnd)
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass
        return True
    except Exception as e:
        logger.debug(f"Error en force_foreground_window (hwnd {hwnd}): {e}")
        return False


def maximize_hwnd(hwnd: int) -> bool:
    """
    Restaura y maximiza una ventana por su HWND, y la trae al frente de forma forzada.
    Si la ventana corresponde al diálogo de login de PACS, la enfoca pero omite la maximización.
    
    Args:
        hwnd: Handle numérico de la ventana de Windows
        
    Returns:
        True si la operación tuvo éxito, False en caso contrario.
    """
    if not hwnd:
        return False
        
    if is_pacs_login_window(hwnd):
        logger.info(f"⏭️ Omitiendo maximización de diálogo de Login PACS (hwnd: {hwnd})")
        return force_foreground_window(hwnd, maximize=False)

    success = force_foreground_window(hwnd, maximize=True)
        
    # Fallback complementario con pywinauto si win32gui no logró el foco completo
    try:
        from pywinauto import Desktop
        win = Desktop(backend="win32").window(handle=hwnd)
        if not success:
            win.maximize()
            success = True
        try:
            win.set_focus()
        except Exception:
            pass
    except Exception:
        pass
        
    return success


def find_windows_by_titles(titles: List[str]) -> List[int]:
    """Busca handles de ventanas que coincidan con la lista de títulos."""
    found_hwnds = []
    try:
        import pywinauto.findwindows as fw
        for title in titles:
            try:
                hwnds = fw.find_windows(title_re=re.compile(f".*{re.escape(title)}.*", re.I))
                for h in hwnds:
                    if h not in found_hwnds:
                        found_hwnds.append(h)
            except Exception:
                pass
    except Exception as e:
        logger.debug(f"Error buscando ventanas por título con findwindows: {e}")
        
    return found_hwnds


def find_windows_by_process_names(process_names: List[str]) -> List[int]:
    """Busca handles de ventanas principales asociadas a nombres de procesos."""
    found_hwnds = []
    try:
        import psutil
        import win32gui
        import win32process
        
        target_pids = set()
        for p in psutil.process_iter(['pid', 'name']):
            try:
                name = p.info.get('name') or ''
                if any(target.lower() == name.lower() for target in process_names):
                    target_pids.add(p.info['pid'])
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
                
        if not target_pids:
            return []

        def enum_callback(hwnd, extra):
            try:
                if win32gui.IsWindowVisible(hwnd):
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    if pid in target_pids:
                        title = win32gui.GetWindowText(hwnd)
                        # Solo ventanas que tengan título visible para evitar tooltips o ventanas auxiliares
                        if title and hwnd not in found_hwnds:
                            found_hwnds.append(hwnd)
            except Exception:
                pass
            return True

        try:
            win32gui.EnumWindows(enum_callback, None)
        except Exception:
            pass
            
    except Exception as e:
        logger.debug(f"Error buscando ventanas por proceso: {e}")
        
    return found_hwnds


def maximize_pacs_windows() -> int:
    """
    Busca y maximiza todas las ventanas activas de Carestream Vue PACS y Carestream RIS.
    
    Returns:
        Cantidad de ventanas que fueron maximizadas exitosamente.
    """
    hwnds_to_maximize = set()
    
    # 1. Búsqueda por títulos conocidos
    by_title = find_windows_by_titles(TITULOS_PACS_RIS)
    for h in by_title:
        hwnds_to_maximize.add(h)
        
    # 2. Búsqueda por procesos conocidos (mp.exe, Carestream RIS.exe, etc.)
    by_proc = find_windows_by_process_names(PROCESOS_PACS_RIS)
    for h in by_proc:
        hwnds_to_maximize.add(h)
        
    count = 0
    for hwnd in hwnds_to_maximize:
        if is_pacs_login_window(hwnd):
            logger.info(f"⏭️ Omitiendo maximización de diálogo de Login PACS (hwnd: {hwnd})")
            continue
        if maximize_hwnd(hwnd):
            count += 1
            try:
                import win32gui
                txt = win32gui.GetWindowText(hwnd)
                logger.info(f"✅ Ventana PACS/RIS maximizada: '{txt}' (hwnd: {hwnd})")
            except Exception:
                logger.info(f"✅ Ventana PACS/RIS maximizada (hwnd: {hwnd})")
                
    return count


def maximize_ris_windows() -> int:
    """
    Busca y maximiza las ventanas de RIS:
    - Web RIS (Chrome abierto en la plataforma Telemedicina / RIS)
    - Carestream RIS Desktop (si aplica)
    
    Returns:
        Cantidad de ventanas maximizadas.
    """
    count = 0
    hwnds_to_maximize = set()
    
    # 1. Buscar ventanas de Chrome con títulos relacionados a RIS / Telemedicina
    try:
        import win32gui
        import win32process
        import psutil

        def chrome_enum_callback(hwnd, extra):
            try:
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if title:
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                        pname = ""
                        try:
                            pname = psutil.Process(pid).name().lower()
                        except Exception:
                            pass
                        
                        if "chrome" in pname:
                            # Si tiene alguna palabra clave de RIS o es la ventana principal de Chrome
                            if any(k.lower() in title.lower() for k in ["ris", "telemedicina", "integra", "pacientes"]):
                                hwnds_to_maximize.add(hwnd)
            except Exception:
                pass
            return True

        try:
            win32gui.EnumWindows(chrome_enum_callback, None)
        except Exception:
            pass
    except Exception as e:
        logger.debug(f"Error buscando ventana Web RIS: {e}")
        
    # 2. Si no se detectó específicamente por título pero hay un Chrome en puerto 9222
    if not hwnds_to_maximize:
        chrome_hwnds = find_windows_by_process_names(["chrome.exe"])
        for h in chrome_hwnds:
            hwnds_to_maximize.add(h)

    # 3. Sumar ventanas desktop de RIS
    by_title = find_windows_by_titles(["Carestream RIS", "Vue RIS", "Workflow Information Management"])
    for h in by_title:
        hwnds_to_maximize.add(h)

    for hwnd in hwnds_to_maximize:
        if maximize_hwnd(hwnd):
            count += 1
            try:
                import win32gui
                txt = win32gui.GetWindowText(hwnd)
                logger.info(f"✅ Ventana RIS maximizada: '{txt}' (hwnd: {hwnd})")
            except Exception:
                logger.info(f"✅ Ventana RIS maximizada (hwnd: {hwnd})")

    return count


def maximize_ris_pacs() -> int:
    """
    Garantiza que cualquier ventana activa tanto de RIS como de PACS sea maximizada.
    
    Returns:
        Total de ventanas maximizadas.
    """
    pacs_count = maximize_pacs_windows()
    ris_count = maximize_ris_windows()
    return pacs_count + ris_count
