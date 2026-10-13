import sys
import os
import time
import json
import cv2
import numpy as np
from pathlib import Path
from PIL import Image

# Configure Tesseract
import pytesseract
pytesseract.pytesseract.pytesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Configure PaddleOCR
from paddleocr import PaddleOCR
paddle_ocr = PaddleOCR(lang='es')

# Import project utilities
sys.path.insert(0, str(Path(r'c:\Desarrollo\RPA_3\rpa_framework')))
from ocr.engine import OCREngine

tesseract_engine = OCREngine(
    engine='tesseract',
    language='spa',
    use_gpu=False,
    confidence_threshold=0.0,
    preprocess=False,
    custom_config='--psm 6'
)

def run_tesseract(img_bgr):
    t0 = time.time()
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    results = tesseract_engine.extract_text_with_location(img_rgb)
    elapsed = time.time() - t0
    # Combine texts
    all_texts = [r['text'] for r in results if r['text'].strip()]
    return {
        'engine': 'tesseract',
        'elapsed_s': elapsed,
        'count': len(results),
        'items': results,
        'full_text': " ".join(all_texts)
    }

def run_paddle(img_bgr):
    t0 = time.time()
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    results = paddle_ocr.predict(img_rgb)
    elapsed = time.time() - t0
    
    extracted = []
    if results and len(results) > 0:
        res = results[0]
        rec_texts = res.get('rec_texts', [])
        rec_scores = res.get('rec_scores', [])
        rec_boxes = res.get('rec_boxes', [])
        for txt, score, box in zip(rec_texts, rec_scores, rec_boxes):
            x1, y1, x2, y2 = box
            w = x2 - x1
            h = y2 - y1
            extracted.append({
                'text': txt,
                'confidence': float(score),
                'bounds': {'x_min': int(x1), 'y_min': int(y1), 'x_max': int(x2), 'y_max': int(y2)},
                'center': {'x': int(x1 + w // 2), 'y': int(y1 + h // 2)},
                'size': {'width': int(w), 'height': int(h)}
            })
    
    all_texts = [r['text'] for r in extracted if r['text'].strip()]
    return {
        'engine': 'paddleocr',
        'elapsed_s': elapsed,
        'count': len(extracted),
        'items': extracted,
        'full_text': " ".join(all_texts)
    }

def evaluate_case(name, img_path, target_diag=None, target_date=None, region=None):
    print(f"\n=======================================================")
    print(f"EVALUANDO CASO: {name}")
    print(f"Imagen: {img_path}")
    print(f"Target: Diag='{target_diag}' | Fecha='{target_date}'")
    print(f"=======================================================")
    
    img = cv2.imread(str(img_path))
    if img is None:
        print(f"ERROR: No se pudo cargar imagen {img_path}")
        return None
        
    if region:
        rx, ry, rw, rh = region
        img = img[ry:ry+rh, rx:rx+rw]
        
    print(f"Dimensiones imagen evaluada: {img.shape}")
    
    # 1. Tesseract RAW
    tess_res = run_tesseract(img)
    # 2. PaddleOCR RAW
    paddle_res = run_paddle(img)
    
    print(f"\n--- TIEMPOS Y DETECCIONES ---")
    print(f"Tesseract : {tess_res['elapsed_s']:.3f}s | {tess_res['count']} palabras")
    print(f"PaddleOCR : {paddle_res['elapsed_s']:.3f}s | {paddle_res['count']} líneas/textos")
    
    # Search for keywords
    keywords = ['hecho', 'examen', 'realizado', 'ordenado', 'cancelado', 'agendado', 'abdomen', 'pelvis', 'pielotc', 'doppler', 'testicular', 'renal']
    if target_date:
        keywords.append(target_date)
        keywords.append(target_date[:-4] + target_date[-2:] if len(target_date) == 10 else target_date)
        
    print(f"\n--- BÚSQUEDA DE PALABRAS CLAVE EN TEXTO EXTRAÍDO ---")
    print(f"{'Palabra Clave':<20} | {'Tesseract':<25} | {'PaddleOCR':<25}")
    print("-" * 75)
    for kw in keywords:
        in_tess = any(kw.lower() in t.lower() for t in [i['text'] for i in tess_res['items']])
        in_paddle = any(kw.lower() in t.lower() for t in [i['text'] for i in paddle_res['items']])
        t_str = "SI [MATCH]" if in_tess else "NO"
        p_str = "SI [MATCH]" if in_paddle else "NO"
        print(f"{kw:<20} | {t_str:<25} | {p_str:<25}")
        
    print(f"\n--- MUESTRA DE DETECCIONES (Primeras 15) ---")
    print(">> TESSERACT:")
    for it in tess_res['items'][:15]:
        print(f"   Y={it['center']['y']:4d} X={it['center']['x']:4d} conf={it['confidence']:4.1f} | '{it['text']}'")
    print(">> PADDLEOCR:")
    for it in paddle_res['items'][:15]:
        print(f"   Y={it['center']['y']:4d} X={it['center']['x']:4d} conf={it['confidence']:4.2f} | '{it['text']}'")
        
    return {
        'case': name,
        'tesseract': tess_res,
        'paddle': paddle_res
    }

if __name__ == '__main__':
    # Test on Error Case 1: error_20261008_095444.png (PACS table during busqueda triple failure)
    # The busqueda triple region is (188, 93, 1720, 900)
    region_busqueda_triple = (188, 93, 1720, 900)
    
    cases = [
        {
            'name': 'CASO_ERROR_095444_REGION_TRIPLE',
            'path': Path(r'c:\Desarrollo\RPA_3\rpa_framework\log\error_20261008_095444.png'),
            'target_diag': 'TC abdomen y pelvis.',
            'target_date': '06-10-2026',
            'region': region_busqueda_triple
        },
        {
            'name': 'CASO_ERROR_095436_FRANJAS',
            'path': Path(r'c:\Desarrollo\RPA_3\rpa_framework\log\busqueda triple\2026-10-08 09-54-36 TC_abdomen_y_pelvis_ 06-10-2026_FRANJAS.png'),
            'target_diag': 'TC abdomen y pelvis.',
            'target_date': '06-10-2026',
            'region': None
        },
        {
            'name': 'CASO_EXITOSO_093731_FRANJAS',
            'path': Path(r'c:\Desarrollo\RPA_3\rpa_framework\log\busqueda triple\2026-10-08 09-37-31 TC_abdomen_y_pelvis_ 06-10-2026_FRANJAS.png'),
            'target_diag': 'TC abdomen y pelvis.',
            'target_date': '06-10-2026',
            'region': None
        },
        {
            'name': 'CASO_EXITOSO_111323_DOPPLER',
            'path': Path(r'c:\Desarrollo\RPA_3\rpa_framework\log\busqueda triple\2026-10-08 11-13-23 ECOTOMOGRAF?A_DOPPLER_TESTICUL 07-10-2026_FRANJAS.png'),
            'target_diag': 'ECOTOMOGRAFIA DOPPLER TESTICULAR',
            'target_date': '07-10-2026',
            'region': None
        }
    ]
    
    all_results = []
    for c in cases:
        if c['path'].exists():
            res = evaluate_case(c['name'], c['path'], c['target_diag'], c['target_date'], c['region'])
            all_results.append(res)
        else:
            print(f"Archivo no existe: {c['path']}")
