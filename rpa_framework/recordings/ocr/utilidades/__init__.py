# rpa_framework/recordings/ocr/utilidades/__init__.py
"""
Utilidades OCR
Módulos reutilizables para procesamiento de imágenes y OCR.
"""

from .preproceso_ocr import (
    preprocess_high_fidelity,
    preprocess_remove_blue_background,
    normalize_coordinates,
    preprocess_adaptive
)

__all__ = [
    'preprocess_high_fidelity',
    'preprocess_remove_blue_background',
    'normalize_coordinates',
    'preprocess_adaptive'
]
