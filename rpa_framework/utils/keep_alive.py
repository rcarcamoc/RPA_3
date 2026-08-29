#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
keep_alive.py - Prevención de suspensión e inactividad en Windows (Keep-Alive).

Usa la API nativa de Windows (SetThreadExecutionState) para evitar que
el sistema operativo entre en suspensión o apague la pantalla mientras
se ejecutan flujos RPA o tareas desatendidas.
"""

import sys
import ctypes
import logging
from contextlib import contextmanager

logger = logging.getLogger("KeepAlive")

# Banderas de SetThreadExecutionState
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002
ES_AWAYMODE_REQUIRED = 0x00000040

_is_preventing_sleep = False


def is_windows() -> bool:
    """Verifica si el sistema operativo es Windows."""
    return sys.platform.startswith("win")


def prevent_sleep(keep_display: bool = True) -> bool:
    """
    Indica a Windows que el sistema y/o la pantalla están en uso continuo,
    evitando que el equipo entre en modo de suspensión o suspenda el procesador.

    Args:
        keep_display (bool): Si es True, mantiene también la pantalla encendida.
                             Si es False, solo evita la suspensión del CPU.

    Returns:
        bool: True si la llamada a la API de Windows fue exitosa.
    """
    global _is_preventing_sleep
    if not is_windows():
        return False

    try:
        flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        if keep_display:
            flags |= ES_DISPLAY_REQUIRED

        prev_state = ctypes.windll.kernel32.SetThreadExecutionState(flags)
        if prev_state != 0:
            _is_preventing_sleep = True
            logger.info(f"🔒 Keep-Alive activado (display={keep_display}, flags={hex(flags)})")
            return True
        else:
            logger.warning("⚠️ SetThreadExecutionState devolvió 0 (no se pudo activar Keep-Alive).")
            return False
    except Exception as e:
        logger.error(f"❌ Error al activar Keep-Alive: {e}")
        return False


def restore_sleep() -> bool:
    """
    Restaura el comportamiento normal de administración de energía de Windows,
    permitiendo la suspensión y el apagado de pantalla por inactividad.

    Returns:
        bool: True si la llamada a la API de Windows fue exitosa.
    """
    global _is_preventing_sleep
    if not is_windows():
        return False

    try:
        prev_state = ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
        _is_preventing_sleep = False
        logger.info("🔓 Keep-Alive desactivado. Estado de energía de Windows restaurado.")
        return prev_state != 0
    except Exception as e:
        logger.error(f"❌ Error al restaurar estado de energía: {e}")
        return False


@contextmanager
def keep_system_awake(keep_display: bool = True):
    """
    Context manager para envolver bloques de código que requieran que el sistema
    no se suspenda ni apague la pantalla durante su ejecución.

    Ejemplo:
        with keep_system_awake():
            ejecutar_workflow_largo()
    """
    activated = prevent_sleep(keep_display=keep_display)
    try:
        yield activated
    finally:
        restore_sleep()


if __name__ == "__main__":
    import time
    logging.basicConfig(level=logging.INFO)
    print("Probando Keep-Alive durante 3 segundos...")
    with keep_system_awake(keep_display=True):
        print("  -> Sistema bloqueado contra suspensión.")
        time.sleep(3)
    print("  -> Sistema restaurado.")
