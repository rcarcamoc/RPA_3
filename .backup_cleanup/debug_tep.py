import sys
from pathlib import Path
import cv2
import numpy as np

# Agregar ruta base
base_path = Path("c:/Desarrollo/RPA_3/rpa_framework")
sys.path.insert(0, str(base_path))

from ocr.engine import OCREngine

def debug_ocr_variants(image_path):
    img = cv2.imread(image_path)
    if img is None:
        print(f"No se pudo cargar {image_path}")
        return
        
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    # Variante 1: Invertida Simple
    img_inv = 255 - img_rgb
    cv2.imwrite("debug_inverted.png", cv2.cvtColor(img_inv, cv2.COLOR_RGB2BGR))
    
    # Variante 2: Grayscale + Threshold (para capturar blanco sobre color)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Si el fondo es azul oscuro y texto es blanco, el azul tendrá valor ~100 y el blanco ~255
    _, thresh = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)
    cv2.imwrite("debug_threshold.png", thresh)

    # Variante 3: Invertida + Threshold
    gray_inv = 255 - gray
    _, thresh_inv = cv2.threshold(gray_inv, 150, 255, cv2.THRESH_BINARY)
    cv2.imwrite("debug_thresh_inv.png", thresh_inv)

    variants = [
        ('Original', img_rgb),
        ('Inverted', img_inv),
        ('Threshold', thresh),
        ('ThreshInv', thresh_inv)
    ]
    
    for name, proc_img in variants:
        print(f"\n--- Testing variant: {name} ---")
        engine = OCREngine(engine='tesseract', language='spa', confidence_threshold=0.01, preprocess=False, custom_config='--psm 11')
        res = engine.extract_text_with_location(proc_img)
        
        found = False
        for r in res:
            t = r['text'].upper()
            if 'TEP' in t or 'PULMONAR' in t or 'TROMBO' in t:
                print(f"Found match: '{r['text']}' (Conf: {r['confidence']:.2f}) en Y={r['center']['y']:.1f}")
                found = True
            # Ver cercanía a Y=270
            elif 250 < r['center']['y'] < 290 and len(t) > 2:
                print(f"Near Y=270: '{r['text']}' (Conf: {r['confidence']:.2f}) en Y={r['center']['y']:.1f}")
        if not found:
            print("No TEP found in this variant.")

if __name__ == '__main__':
    img_path = r"c:\Desarrollo\RPA_3\rpa_framework\log\patologia_critica\patologia_2026-03-23 23-54-43.png"
    debug_ocr_variants(img_path)
