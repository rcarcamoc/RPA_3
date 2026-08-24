"""
utils/keyboard_utils.py

Módulo de utilidad para verificar y gestionar el estado del teclado (Bloq Mayús / Caps Lock).
"""

import ctypes
import time
import logging

logger = logging.getLogger(__name__)

VK_CAPITAL = 0x14
KEYEVENTF_KEYUP = 0x0002


def is_capslock_on() -> bool:
    """
    Verifica si la tecla Bloq Mayús (Caps Lock) está activada en Windows.
    Retorna True si está activo, False en caso contrario.
    """
    try:
        # GetKeyState devuelve un entero de 16 bits. El bit 0 (LSB) indica el estado toggle (1=ON, 0=OFF).
        return bool(ctypes.windll.user32.GetKeyState(VK_CAPITAL) & 1)
    except Exception as e:
        logger.warning(f"No se pudo verificar el estado de Bloq Mayús: {e}")
        return False


def ensure_capslock_off(log_func=None) -> bool:
    """
    Verifica si Bloq Mayús está activo y, de estarlo, lo desactiva automáticamente
    para asegurar que la escritura se realice en minúsculas.
    
    Args:
        log_func: Función opcional para canalizar mensajes de log (ej. self.logger.log)
        
    Returns:
        bool: True si se tuvo que desactivar, False si ya estaba desactivado.
    """
    def _log(msg: str):
        if log_func:
            try:
                log_func(msg)
            except Exception:
                logger.info(msg)
        else:
            logger.info(msg)

    if is_capslock_on():
        _log("⚠️ Bloq Mayús (Caps Lock) detectado ACTIVADO. Desactivándolo automáticamente para asegurar escritura en minúsculas...")
        try:
            # Alternar Bloq Mayús con la API de Windows keybd_event (Key Down + Key Up)
            ctypes.windll.user32.keybd_event(VK_CAPITAL, 0, 0, 0)
            ctypes.windll.user32.keybd_event(VK_CAPITAL, 0, KEYEVENTF_KEYUP, 0)
            time.sleep(0.1)

            # Fallback en caso de que siga activo
            if is_capslock_on():
                try:
                    import pyautogui
                    pyautogui.press('capslock')
                except Exception:
                    pass

            if not is_capslock_on():
                _log("🔒 Bloq Mayús desactivado con éxito.")
                return True
            else:
                _log("⚠️ Se intentó desactivar Bloq Mayús pero permaneció activo.")
                return False
        except Exception as e:
            _log(f"❌ Error al intentar desactivar Bloq Mayús: {e}")
            return False
    else:
        _log("🔒 Bloq Mayús está DESACTIVADO.")
        return False
