# rpa_framework/config.py

"""
Configuración centralizada para módulo OCR del RPA Framework.
"""

import os
from pathlib import Path

# Directorio base del proyecto
BASE_DIR = Path(__file__).parent.parent

# ============================================================================
# CONFIGURACIÓN OCR ENGINE
# ============================================================================

OCR_CONFIG = {
    # Motor OCR principal: 'easyocr', 'tesseract', 'paddleocr'
    'engine': 'easyocr',
    
    # Idioma por defecto
    'language': 'es',
    
    # Idiomas soportados
    'supported_languages': ['es', 'en', 'pt', 'fr', 'de', 'it'],
    
    # Umbrales de confianza
    'confidence_threshold': 0.5,  # Mínima confianza para considerar un texto
    'fuzzy_match_threshold': 80,  # Similitud mínima para fuzzy matching (0-100)
    
    # Configuración por engine
    'engines': {
        'easyocr': {
            'gpu': False,  # True si tienes CUDA disponible
            'model_storage_dir': str(BASE_DIR / '.ocr_models'),
            'gpu_batch_size': 4,
        },
        'tesseract': {
            'path_windows': r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            'path_linux': '/usr/bin/tesseract',
            'path_macos': '/usr/local/bin/tesseract',
        },
        'paddleocr': {
            'use_gpu': False,
            'enable_mkldnn': True,
        }
    },
    
    # Configuración de rendimiento
    'performance': {
        'screenshot_quality': 95,  # Calidad de captura (1-100)
        'preprocessing': True,     # Aplicar filtros antes de OCR
        'cache_results': True,     # Cachear resultados OCR
        'cache_ttl': 300,          # TTL del cache (segundos)
        'lazy_load_model': True,   # Cargar modelo solo cuando sea necesario
    },
    
    # Configuración de logging
    'logging': {
        'level': 'INFO',  # DEBUG, INFO, WARNING, ERROR, CRITICAL
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        'file': str(BASE_DIR / 'logs' / 'ocr.log'),
    },
    
    # Timeouts
    'timeouts': {
        'ocr_extraction': 30,      # Segundos para extracción OCR
        'action_execution': 10,    # Segundos para ejecutar acción
        'screenshot_capture': 5,   # Segundos para capturar screenshot
    },
    
    # Opciones de preprocesamiento
    'preprocessing': {
        'enhance_contrast': True,
        'clahe_clip_limit': 2.0,
        'clahe_tile_size': 8,
        'grayscale': True,
    }
}

# ============================================================================
# CONFIGURACIÓN GUI
# ============================================================================

GUI_CONFIG = {
    'title': 'RPA Framework with OCR',
    'window_size': (1200, 800),
    'theme': 'clam',  # tkinter theme
    
    'ocr_tab': {
        'enabled': True,
        'icon_size': 20,
    }
}

# ============================================================================
# CONFIGURACIÓN DE DIRECTORIOS
# ============================================================================

DIRECTORIES = {
    'ocr_modules': BASE_DIR / 'rpa_framework' / 'ocr',
    'generated_modules': BASE_DIR / 'rpa_framework' / 'modules' / 'generated',
    'ocr_models': BASE_DIR / '.ocr_models',
    'screenshots': BASE_DIR / '.screenshots',
    'logs': BASE_DIR / 'logs',
}

# Crear directorios si no existen
for dirname in DIRECTORIES.values():
    dirname.mkdir(parents=True, exist_ok=True)

# ============================================================================
# CONFIGURACIÓN DE DEPENDENCIAS
# ============================================================================

REQUIRED_PACKAGES = {
    'easyocr': '>=1.7.0',
    'pytesseract': '>=0.3.10',
    'opencv-python': '>=4.8.0',
    'pillow': '>=10.0.0',
    'numpy': '>=1.24.0',
    'fuzzywuzzy': '>=0.18.0',
    'python-Levenshtein': '>=0.21.0',
    'mss': '>=9.0.1',
    'pyautogui': '>=0.9.53',
}

# ============================================================================
# CONFIGURACIÓN AVANZADA
# ============================================================================

# Patrones regex comunes
REGEX_PATTERNS = {
    'email': r'[\w\.-]+@[\w\.-]+\.\w+',
    'phone': r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',
    'date': r'\d{1,2}[/-]\d{1,2}[/-]\d{4}',
    'url': r'https?://[^\s]+',
    'ip_address': r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}',
    'ipv4': r'(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)',
}

# Mapeo de colores para visualización en GUI
COLORS = {
    'match_found': '#00AA00',      # Verde
    'no_match': '#AA0000',         # Rojo
    'processing': '#FFAA00',       # Naranja
    'confidence_high': '#00AA00',  # Verde
    'confidence_medium': '#FFAA00', # Naranja
    'confidence_low': '#AA0000',   # Rojo
}

# ============================================================================
# HELPERS
# ============================================================================

def get_ocr_config():
    """Obtener configuración OCR actual"""
    return OCR_CONFIG


def get_gui_config():
    """Obtener configuración GUI actual"""
    return GUI_CONFIG


def get_directory(name: str):
    """Obtener ruta de un directorio"""
    if name not in DIRECTORIES:
        raise ValueError(f"Directorio desconocido: {name}")
    return DIRECTORIES[name]


def validate_engine(engine: str) -> bool:
    """Validar que engine es soportado"""
    return engine in OCR_CONFIG['engines']


def validate_language(language: str) -> bool:
    """Validar que idioma es soportado"""
    return language in OCR_CONFIG['supported_languages']
