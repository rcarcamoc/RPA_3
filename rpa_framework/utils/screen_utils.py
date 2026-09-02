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


if __name__ == "__main__":
    res = get_screen_resolution()
    print(f"Resolución de pantalla detectada: {res}")
