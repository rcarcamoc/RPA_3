"""
Módulo de utilidades de pantalla para RPA Framework 3.

Proporciona detección robusta y con soporte DPI de la resolución de pantalla actual
en Windows, asegurando valores exactos incluso con escalado de pantalla (125%, 150%, etc.).
"""

import sys
import logging

logger = logging.getLogger(__name__)

def get_screen_resolution() -> str:
    """
    Obtiene la resolución de la pantalla principal en formato 'ANCHOxALTO' (ej. '1920x1080').
    
    Aplica técnicas de reconocimiento DPI para garantizar que en Windows se obtenga la resolución
    física real del monitor y no una resolución escalada virtual.
    """
    # 1. Intentar ctypes nativo de Windows con DPI Awareness
    if sys.platform == "win32":
        try:
            import ctypes
            user32 = ctypes.windll.user32
            try:
                # SetProcessDPIAware() asegura coordenadas reales de hardware
                user32.SetProcessDPIAware()
            except Exception:
                pass
            w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
            h = user32.GetSystemMetrics(1)  # SM_CYSCREEN
            if w > 0 and h > 0:
                return f"{w}x{h}"
        except Exception as e:
            logger.debug(f"Error detectando resolución con ctypes: {e}")

    # 2. Intentar con mss (biblioteca ya presente en el proyecto)
    try:
        import mss
        with mss.mss() as sct:
            monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            w = monitor.get("width", 0)
            h = monitor.get("height", 0)
            if w > 0 and h > 0:
                return f"{w}x{h}"
    except Exception as e:
        logger.debug(f"Error detectando resolución con mss: {e}")

    # 3. Intentar con pyautogui
    try:
        import pyautogui
        w, h = pyautogui.size()
        if w > 0 and h > 0:
            return f"{w}x{h}"
    except Exception as e:
        logger.debug(f"Error detectando resolución con pyautogui: {e}")

    # Fallback predeterminado estándar Full HD
    return "1920x1080"


def attach_to_interactive_desktop():
    """
    Asegura que el hilo y proceso actual estén vinculados a la estación de ventana interactiva
    (WinSta0\\Default) de Windows. Esto previene fallos de 'Acceso denegado' y 'screen grab failed'
    cuando se ejecuta como subproceso, tarea programada o servicio.
    """
    if sys.platform == "win32":
        try:
            import ctypes
            user32 = ctypes.windll.user32
            hwinsta = user32.OpenWindowStationW('WinSta0', False, 0x037F)
            if hwinsta:
                user32.SetProcessWindowStation(hwinsta)
                hdesk = user32.OpenDesktopW('Default', 0, False, 0x01FF)
                if hdesk:
                    user32.SetThreadDesktop(hdesk)
        except Exception as e:
            logger.debug(f"Aviso adjuntando a WinSta0\\Default: {e}")


def safe_screenshot(filepath=None, region=None):
    """
    Toma captura de pantalla completa o de una región específica de manera resiliente.
    
    Motor primario: mss (captura directa por DIBits, inmune a 'screen grab failed' de BitBlt).
    Fallback secundario: pyautogui / Pillow.
    
    Args:
        filepath: Ruta opcional donde guardar la imagen en disco.
        region: Tupla opcional (left, top, width, height) para capturar solo una región.
        
    Returns:
        PIL.Image.Image o None si fallaron todos los métodos.
    """
    attach_to_interactive_desktop()
    img = None
    
    # 1. Intentar con mss (más rápido, robusto e inmune a bloqueos GDI)
    try:
        import mss
        from PIL import Image
        with mss.mss() as sct:
            if region:
                bbox = {
                    "left": int(region[0]),
                    "top": int(region[1]),
                    "width": int(region[2]),
                    "height": int(region[3])
                }
                grab = sct.grab(bbox)
            else:
                mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                grab = sct.grab(mon)
            img = Image.frombytes("RGB", grab.size, grab.bgra, "raw", "BGRX")
    except Exception as e:
        logger.debug(f"Aviso capturando pantalla con mss: {e}")

    # 2. Fallback con pyautogui
    if img is None:
        try:
            import pyautogui
            img = pyautogui.screenshot(region=region)
        except Exception as e:
            logger.warning(f"Aviso capturando pantalla con pyautogui: {e}")

    # 3. Guardar archivo si se especificó ruta
    if img is not None and filepath:
        try:
            import os
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
            img.save(filepath)
            logger.debug(f"Captura guardada en: {filepath}")
        except Exception as e:
            logger.error(f"Error guardando screenshot en '{filepath}': {e}")

    return img


if __name__ == "__main__":
    res = get_screen_resolution()
    print(f"Resolución de pantalla detectada: {res}")
    test_img = safe_screenshot()
    print(f"safe_screenshot resultado: {test_img.size if test_img else 'None'}")
