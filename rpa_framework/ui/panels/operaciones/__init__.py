"""
Subpaquete para el Centro de Control de Operaciones (ModernOperacionesPanel y ActionTile).
Extraído de main_gui_final.py manteniendo 100% de compatibilidad.
"""

from .styles_and_tiles import CUSTOM_STYLESHEET, FINAL_STYLESHEET, ActionTile
from .operaciones_panel import ModernOperacionesPanel

__all__ = [
    "CUSTOM_STYLESHEET",
    "FINAL_STYLESHEET",
    "ActionTile",
    "ModernOperacionesPanel",
]
