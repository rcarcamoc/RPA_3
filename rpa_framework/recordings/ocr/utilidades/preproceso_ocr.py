#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════════════════
                    MÓDULO DE PREPROCESAMIENTO OCR
═══════════════════════════════════════════════════════════════════════════════

Funciones reutilizables para mejorar la precisión de Tesseract OCR.

CONTENIDO:
----------
1. preprocess_high_fidelity()      - Preprocesamiento de alta fidelidad (3x upscaling)
2. preprocess_remove_blue_background() - Eliminación de fondos azules (Windows UI)
3. normalize_coordinates()         - Normalización de coordenadas post-upscaling
4. preprocess_adaptive()           - Selector automático de método

═══════════════════════════════════════════════════════════════════════════════
                              GUÍA DE USO
═══════════════════════════════════════════════════════════════════════════════

📌 CASO 1: Preprocesamiento de Alta Fidelidad (Recomendado)
------------------------------------------------------------
Ideal para: Texto claro sobre fondos oscuros/coloreados, headers Windows, 
            texto pequeño que necesita mayor resolución.

Ejemplo básico:
```python
from PIL import Image
from rpa_framework.recordings.ocr.utilidades import preprocess_high_fidelity
import pytesseract

# 1. Cargar imagen
img = Image.open("captura_pantalla.png")

# 2. Preprocesar (upscaling 3x + binarización)
img_procesada, scale_factor = preprocess_high_fidelity(img)

# 3. Aplicar OCR
texto = pytesseract.image_to_string(img_procesada, lang='spa')
print(f"Texto detectado: {texto}")
```

Ejemplo con coordenadas:
```python
from pytesseract import Output
import pytesseract

# Preprocesar
img_procesada, scale = preprocess_high_fidelity(img, scale_factor=3)

# OCR con coordenadas
data = pytesseract.image_to_data(img_procesada, lang='spa', output_type=Output.DICT)

# Normalizar coordenadas a imagen original
for i in range(len(data['text'])):
    if data['text'][i].strip():
        coords = {
            'center': {
                'x': data['left'][i] + data['width'][i]/2,
                'y': data['top'][i] + data['height'][i]/2
            },
            'bounds': {
                'x_min': data['left'][i],
                'y_min': data['top'][i],
                'x_max': data['left'][i] + data['width'][i],
                'y_max': data['top'][i] + data['height'][i]
            }
        }
        
        # Normalizar a coordenadas originales
        coords_real = normalize_coordinates(coords, scale)
        print(f"'{data['text'][i]}' en ({coords_real['center']['x']}, {coords_real['center']['y']})")
```

📌 CASO 2: Eliminación de Fondos Azules
-----------------------------------------
Ideal para: Interfaces Windows con gradientes azules, barras de título,
            headers con fondos de color.

Ejemplo:
```python
from rpa_framework.recordings.ocr.utilidades import preprocess_remove_blue_background

# Cargar imagen con fondo azul
img = Image.open("header_windows.png")

# Eliminar fondo azul y binarizar
img_procesada = preprocess_remove_blue_background(img)

# OCR directo (sin normalización, no hay upscaling)
texto = pytesseract.image_to_string(img_procesada, lang='spa')
```

Personalizar detección de azules:
```python
# Ajustar rango de Hue para otros tonos de azul
img_procesada = preprocess_remove_blue_background(
    img,
    h_range=(90, 140),  # Rango más amplio
    s_threshold=30      # Saturación mínima más baja
)
```

📌 CASO 3: Uso Adaptativo (Automático)
----------------------------------------
Selecciona automáticamente el método según el modo especificado.

Ejemplo:
```python
from rpa_framework.recordings.ocr.utilidades import preprocess_adaptive

# Modo alta fidelidad
img_proc, scale = preprocess_adaptive(img, mode='high_fidelity', scale_factor=3)

# Modo eliminación de azules
img_proc, _ = preprocess_adaptive(img, mode='remove_blue', h_range=(95, 135))
```

📌 CASO 4: Integración con OCREngine
--------------------------------------
Cómo usar con el motor OCR del framework:

```python
from rpa_framework.ocr.engine import OCREngine
from rpa_framework.recordings.ocr.utilidades import preprocess_high_fidelity
from PIL import Image
import numpy as np

# Inicializar OCR
engine = OCREngine(
    engine='tesseract',
    language='spa',
    confidence_threshold=0.6
)

# Capturar y preprocesar
img = Image.open("screenshot.png")
img_procesada, scale = preprocess_high_fidelity(img)

# Convertir a numpy para OCREngine
img_np = np.array(img_procesada)

# Extraer texto
resultados = engine.extract_text_with_location(img_np)

# Normalizar coordenadas
for res in resultados:
    res_normalizado = normalize_coordinates(res, scale)
    print(f"{res['text']}: {res_normalizado['center']}")
```

📌 CASO 5: Uso desde línea de comandos
----------------------------------------
El módulo puede ejecutarse directamente:

```bash
# Alta fidelidad (default)
python preproceso_ocr.py captura.png

# Eliminación de azules
python preproceso_ocr.py captura.png remove_blue

# Salida: captura_processed_high_fidelity.png
```

═══════════════════════════════════════════════════════════════════════════════
                         PARÁMETROS TÉCNICOS
═══════════════════════════════════════════════════════════════════════════════

preprocess_high_fidelity():
  - scale_factor (int): Factor de upscaling, default=3. Mayor = mejor calidad pero más lento
  - threshold_floor (int): Umbral para limpiar fondos oscuros, default=100 (0-255)

preprocess_remove_blue_background():
  - h_range (tuple): Rango Hue para detectar azules, default=(95,135) en escala 0-179
  - s_threshold (int): Saturación mínima para considerar azul, default=40 (0-255)

normalize_coordinates():
  - coords (dict): Debe contener 'center', 'bounds', 'dimensions', o 'bbox'
  - scale_factor (float): Factor usado en preprocesamiento

═══════════════════════════════════════════════════════════════════════════════
"""

import cv2
import numpy as np
from PIL import Image
from typing import Tuple, Optional


def normalize_colored_backgrounds(img_rgb: np.ndarray) -> np.ndarray:
    """
    Detecta regiones con fondos de color (rojo, naranja, rosa, azul oscuro)
    y las normaliza para que el pipeline Otsu pueda binarizarlas correctamente:
      - Fondo coloreado  → blanco
      - Texto claro (blanco) sobre esos fondos → negro

    Colores cubiertos:
      • Rojo      H=  0-10  y H=160-179   (fila seleccionada principal)
      • Naranja   H= 10-25               (celda "Examen Hecho" / Estado)
      • Rosa/Magenta H=140-165           (filas de otro estado)
      • Azul oscuro H= 90-140, V bajo    (cabeceras de tabla)

    Sin este paso, los fondos coloreados convierten a gris ≈80-130 (por debajo
    del threshold_floor=100 o en zona ambigua de Otsu), aplastándose junto con
    el texto blanco y dejando la celda como bloque ilegible para Tesseract.
    """
    img_hsv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2HSV)
    h, s, v = cv2.split(img_hsv)

    # ── Máscara ROJO (Hue 0-10 y 160-179) ───────────────────────────────────
    red_mask    = ((h < 10) | (h > 160)) & (s > 60) & (v > 60)

    # ── Máscara NARANJA (Hue 10-25) — celda "Examen Hecho" ──────────────────
    orange_mask = ((h >= 10) & (h <= 25)) & (s > 80) & (v > 60)

    # ── Máscara ROSA / MAGENTA (Hue 140-165) ────────────────────────────────
    pink_mask   = ((h >= 140) & (h <= 165) & (s > 50))

    # ── Máscara AZUL OSCURO (Hue 90-140, S alta, V bajo-medio) ─────────────
    blue_mask   = ((h >= 90) & (h <= 140) & (s > 60) & (v < 160))

    colored_mask = red_mask | orange_mask | pink_mask | blue_mask

    if not np.any(colored_mask):
        return img_rgb  # Sin fondos coloreados: imagen sin cambios

    result = img_rgb.copy()

    # Texto claro = blanco/casi-blanco → V > 180  (blanco puro tiene V=255)
    # El fondo naranja tiene V≈80-150, bien separado del texto blanco
    text_mask = colored_mask & (v > 180)
    # Fondo = zona coloreada que no es texto claro
    bg_mask   = colored_mask & (v <= 180)

    result[text_mask] = [0,   0,   0  ]  # texto blanco → negro
    result[bg_mask]   = [255, 255, 255]  # fondo coloreado → blanco

    return result



def preprocess_high_fidelity(
    img: Image.Image,
    scale_factor: int = 3,
    threshold_floor: int = 100
) -> Tuple[Image.Image, float]:
    """
    Preprocesamiento de alta fidelidad para OCR.
    Optimizado para texto claro sobre fondos oscuros/coloreados.
    
    Args:
        img: Imagen PIL en formato RGB
        scale_factor: Factor de escalado (default: 3x)
        threshold_floor: Umbral para limpiar fondos oscuros (default: 100)
    
    Returns:
        Tupla (imagen_procesada, scale_factor)
    
    Proceso:
        1. Upscaling 3x con Lanczos4
        2. Conversión a escala de grises
        3. Threshold ToZero para eliminar fondos oscuros
        4. Binarización Otsu automática
        5. Inversión (texto negro sobre blanco)
    """
    # Convertir PIL (RGB) a Numpy (RGB)
    img_np = np.array(img)
    
    # 1. Escalar (Lanczos4) - Mejora significativa en textos pequeños
    upscaled = cv2.resize(
        img_np, 
        None, 
        fx=scale_factor, 
        fy=scale_factor, 
        interpolation=cv2.INTER_LANCZOS4
    )
    
    # 2. Normalizar fondos de color (rojo, rosa, azul) ANTES de pasar a grises.
    #    Sin este paso, Hue rojo → gris ≈85 < threshold_floor=100 → fila entera negra.
    upscaled = normalize_colored_backgrounds(upscaled)

    # 3. Convertir a Grises
    gray = cv2.cvtColor(upscaled, cv2.COLOR_RGB2GRAY)
    
    # 3. Binarización por Umbral de Histograma (Truncated + Otsu)
    # El threshold_floor actúa como piso para limpiar fondos oscuros/medios
    _, thresh_base = cv2.threshold(gray, threshold_floor, 255, cv2.THRESH_TOZERO)
    
    # 4. Aplicar Otsu (determina automáticamente el mejor umbral)
    _, final_binary = cv2.threshold(
        thresh_base, 
        0, 
        255, 
        cv2.THRESH_BINARY + cv2.THRESH_OTSU
    )
    
    # 5. Inversión final (Texto Negro sobre Fondo Blanco para Tesseract)
    final_bw = cv2.bitwise_not(final_binary)
    
    return Image.fromarray(final_bw), float(scale_factor)


def preprocess_remove_blue_background(
    img: Image.Image,
    h_range: Tuple[int, int] = (95, 135),
    s_threshold: int = 40
) -> Image.Image:
    """
    Elimina fondos azules y maximiza contraste.
    Útil para interfaces Windows con gradientes azules.
    
    Args:
        img: Imagen PIL en formato RGB
        h_range: Rango de Hue (matiz) para detectar azules en escala 0-179
        s_threshold: Umbral mínimo de saturación
    
    Returns:
        Imagen procesada (PIL)
    
    Proceso:
        1. Conversión RGB -> HSV
        2. Detección de píxeles azules
        3. Reemplazo de azules por blanco
        4. CLAHE para mejorar contraste
        5. Binarización Otsu
        6. Morphological closing
    """
    # Convertir a numpy RGB
    img_np = np.array(img.convert('RGB'))
    
    # 1. Convertir a HSV para detectar azules
    # OpenCV usa H: 0-179, S: 0-255, V: 0-255
    img_hsv = cv2.cvtColor(img_np, cv2.COLOR_RGB2HSV)
    h, s, v = cv2.split(img_hsv)
    
    # 2. Máscara para fondos azules
    blue_mask = (h > h_range[0]) & (h < h_range[1]) & (s > s_threshold)
    
    # 3. Reemplazar azules con blanco (V=255, S=0)
    img_hsv[blue_mask, 1] = 0   # S = 0
    img_hsv[blue_mask, 2] = 255 # V = 255
    
    # Volver a RGB
    img_clean = cv2.cvtColor(img_hsv, cv2.COLOR_HSV2RGB)
    
    # 4. Escala de grises
    img_gray = cv2.cvtColor(img_clean, cv2.COLOR_RGB2GRAY)
    
    # 5. CLAHE (Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    img_clahe = clahe.apply(img_gray)
    
    # 6. Binarización Otsu
    _, img_bin = cv2.threshold(img_clahe, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # 7. Morph close para conectar letras rotas
    kernel = np.ones((2, 2), np.uint8)
    img_morph = cv2.morphologyEx(img_bin, cv2.MORPH_CLOSE, kernel)
    
    return Image.fromarray(img_morph)


def normalize_coordinates(
    coords: dict,
    scale_factor: float
) -> dict:
    """
    Normaliza coordenadas de OCR cuando se aplicó upscaling.
    
    Args:
        coords: Diccionario con coordenadas (x, y, width, height, center, bounds, bbox)
        scale_factor: Factor de escala aplicado en preprocesamiento
    
    Returns:
        Diccionario con coordenadas normalizadas a imagen original
    """
    if scale_factor == 1.0:
        return coords
    
    normalized = coords.copy()
    
    # Normalizar center
    if 'center' in normalized:
        normalized['center'] = {
            'x': normalized['center']['x'] / scale_factor,
            'y': normalized['center']['y'] / scale_factor
        }
    
    # Normalizar bounds
    if 'bounds' in normalized:
        normalized['bounds'] = {
            'x_min': normalized['bounds']['x_min'] / scale_factor,
            'y_min': normalized['bounds']['y_min'] / scale_factor,
            'x_max': normalized['bounds']['x_max'] / scale_factor,
            'y_max': normalized['bounds']['y_max'] / scale_factor
        }
    
    # Normalizar dimensions
    if 'dimensions' in normalized:
        normalized['dimensions'] = {
            'width': normalized['dimensions']['width'] / scale_factor,
            'height': normalized['dimensions']['height'] / scale_factor
        }
    
    # Normalizar bbox
    if 'bbox' in normalized:
        normalized['bbox'] = [
            [point[0] / scale_factor, point[1] / scale_factor]
            for point in normalized['bbox']
        ]
    
    return normalized


def preprocess_adaptive(
    img: Image.Image,
    mode: str = 'high_fidelity',
    **kwargs
) -> Tuple[Image.Image, Optional[float]]:
    """
    Función adaptativa que selecciona el método de preprocesamiento.
    
    Args:
        img: Imagen PIL
        mode: 'high_fidelity' o 'remove_blue'
        **kwargs: Argumentos adicionales para el método seleccionado
    
    Returns:
        Tupla (imagen_procesada, scale_factor o None)
    """
    if mode == 'high_fidelity':
        return preprocess_high_fidelity(img, **kwargs)
    elif mode == 'remove_blue':
        return preprocess_remove_blue_background(img, **kwargs), None
    else:
        raise ValueError(f"Modo desconocido: {mode}. Use 'high_fidelity' o 'remove_blue'")


# Ejemplo de uso
if __name__ == '__main__':
    import sys
    from pathlib import Path
    
    if len(sys.argv) < 2:
        print("Uso: python preproceso_ocr.py <imagen_entrada> [modo]")
        print("Modos: high_fidelity (default), remove_blue")
        sys.exit(1)
    
    input_path = sys.argv[1]
    mode = sys.argv[2] if len(sys.argv) > 2 else 'high_fidelity'
    
    # Cargar imagen
    img = Image.open(input_path)
    
    # Procesar
    processed, scale = preprocess_adaptive(img, mode=mode)
    
    # Guardar
    output_path = Path(input_path).stem + f"_processed_{mode}.png"
    processed.save(output_path)
    
    print(f"✅ Imagen procesada guardada: {output_path}")
    if scale:
        print(f"   Factor de escala aplicado: {scale}x")
