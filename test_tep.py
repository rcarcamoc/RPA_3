import sys
from pathlib import Path
import cv2
import numpy as np

# Agregar ruta base
base_path = Path("c:/Desarrollo/RPA_3/rpa_framework")
sys.path.insert(0, str(base_path))

from ocr.engine import OCREngine

def test_specific_image(image_path):
    img = cv2.imread(image_path)
    if img is None:
        print(f"No se pudo cargar {image_path}")
        return
        
    # Probar con y sin preprocesamiento para ver cuál captura el azul
    configs = [
        {'name': 'PSM 6 Normal', 'preprocess': False, 'psm': '--psm 6'},
        {'name': 'PSM 11 Normal', 'preprocess': False, 'psm': '--psm 11'},
        {'name': 'PSM 6 Inverted', 'preprocess': 'invert', 'psm': '--psm 6'}
    ]
    
    for cfg in configs:
        print(f"\n--- Probando: {cfg['name']} ---")
        
        proc_img = img.copy()
        if cfg['preprocess'] == 'invert':
            proc_img = 255 - proc_img # Invertir para texto blanco sobre fondo oscuro
            
        engine = OCREngine(
            engine='tesseract',
            language='spa',
            use_gpu=False,
            confidence_threshold=0.01,
            preprocess=False, # Manualmente lo manejo arriba
            custom_config=cfg['psm']
        )
        
        results = engine.extract_text_with_location(proc_img)
        results.sort(key=lambda x: x['center']['y'])
        
        for r in results:
            if 'TEP' in r['text'].upper() or 'TROMBO' in r['text'].upper():
                print(f"ENCONTRADO: '{r['text']}' en Y={r['center']['y']:.1f}")
            elif len(r['text']) > 4:
                # Mostrar lo que hay cerca de Y=260-290 (donde dice el usuario)
                if 240 < r['center']['y'] < 300:
                   print(f"Cerca (Y={r['center']['y']:.1f}): '{r['text']}'")

if __name__ == '__main__':
    img_path = r"c:\Desarrollo\RPA_3\rpa_framework\log\patologia_critica\patologia_2026-03-23 23-45-35.png"
    test_specific_image(img_path)
