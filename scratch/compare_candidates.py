import sys
import os
import cv2
import re
import numpy as np
from pathlib import Path
from rapidfuzz import fuzz

sys.path.insert(0, str(Path(r'c:\Desarrollo\RPA_3\rpa_framework')))
from ocr.engine import OCREngine

# Load image
img = cv2.imread(r'c:\Desarrollo\RPA_3\rpa_framework\log\error_20261008_095444.png')
crop = img[93:93+900, 188:188+1720]

target_diag = "TC abdomen y pelvis."
target_fecha = "06-10-2026"

# 1. Run Tesseract (using exact logic from busqueda_triple_text_only)
tess_engine = OCREngine(
    engine='tesseract',
    language='spa',
    use_gpu=False,
    confidence_threshold=0.0,
    preprocess=False,
    custom_config='--psm 6'
)

# Also test with 3X preprocessing (high fidelity) like busqueda_triple does
from recordings.ocr.utilidades.preproceso_ocr import preprocess_adaptive, normalize_coordinates
from PIL import Image

crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
pil_img = Image.fromarray(crop_rgb)
proc_pil, scale = preprocess_adaptive(pil_img, mode='high_fidelity', scale_factor=3)
tess_results_raw = tess_engine.extract_text_with_location(crop_rgb)
tess_results_3x_scaled = tess_engine.extract_text_with_location(np.array(proc_pil))
tess_results_3x = [normalize_coordinates(r, scale) for r in tess_results_3x_scaled]

# 2. Run PaddleOCR
from paddleocr import PaddleOCR
paddle_ocr = PaddleOCR(
    lang='es',
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    text_recognition_batch_size=16
)
paddle_res_raw = paddle_ocr.predict(crop_rgb)
paddle_results = []
if paddle_res_raw:
    res = paddle_res_raw[0]
    for txt, score, box in zip(res.get('rec_texts', []), res.get('rec_scores', []), res.get('rec_boxes', [])):
        x1, y1, x2, y2 = box
        w = x2 - x1
        h = y2 - y1
        paddle_results.append({
            'text': txt,
            'confidence': float(score) * 100,
            'bounds': {'x_min': int(x1), 'y_min': int(y1), 'x_max': int(x2), 'y_max': int(y2)},
            'center': {'x': int(x1 + w // 2), 'y': int(y1 + h // 2)},
            'size': {'width': int(w), 'height': int(h)}
        })

# Grouping function from busqueda_triple_text_only.py
def agrupar_por_filas(results, row_tolerance=10):
    if not results:
        return []
    results_sorted = sorted(results, key=lambda x: x['center']['y'])
    rows_data = []
    for item in results_sorted:
        y_item = item['center']['y']
        matched = False
        for row in rows_data:
            if abs(row['y_center'] - y_item) < row_tolerance:
                row['items'].append(item)
                row['y_center'] = sum([i['center']['y'] for i in row['items']]) / len(row['items'])
                matched = True
                break
        if not matched:
            rows_data.append({'y_center': y_item, 'items': [item]})
    rows_data.sort(key=lambda x: x['y_center'])
    final_rows = []
    if rows_data:
        current_row = rows_data[0]
        for i in range(1, len(rows_data)):
            next_row = rows_data[i]
            if abs(current_row['y_center'] - next_row['y_center']) < (row_tolerance * 0.8):
                current_row['items'].extend(next_row['items'])
                current_row['y_center'] = sum([it['center']['y'] for it in current_row['items']]) / len(current_row['items'])
            else:
                final_rows.append(current_row)
                current_row = next_row
        final_rows.append(current_row)
    for row in final_rows:
        row_items = sorted(row['items'], key=lambda x: x['center']['x'])
        row['full_text'] = " ".join([i['text'] for i in row_items])
    return final_rows

def analyze_candidates_test(rows, target_date):
    candidates = []
    ESTADOS_EXCLUIDOS = ['cancelado', 'cancelada', 'anulado', 'anulada', 'agendado', 'agendada', 'citado', 'citada', 'ordenado', 'ordenada', 'en espera', 'solicitado']
    REGEX_HECHO = re.compile(r'\b(?:examen\s*he[cd]h?o|realizado|hecho)\b', re.IGNORECASE)
    
    for r in rows:
        text = r['full_text'].lower()
        # check exclude
        if any(re.search(r'\b' + re.escape(e) + r'\b', text) for e in ESTADOS_EXCLUIDOS):
            continue
        has_date = (target_date in text) or (target_date[:-4] + target_date[-2:] in text)
        has_hecho = bool(REGEX_HECHO.search(text)) or (fuzz.partial_ratio("examen hecho", text) >= 70) or (fuzz.partial_ratio("hecho", text) >= 70)
        if has_date and has_hecho:
            candidates.append(r)
    return candidates

print("\n" + "="*80)
print(f"ANÁLISIS COMPARATIVO EN CASO DE ERROR REAL (error_20261008_095444.png)")
print(f"Target Buscado: '{target_diag}' | Fecha: '{target_fecha}'")
print("="*80)

# Evaluate Tesseract RAW
rows_tess_raw = agrupar_por_filas(tess_results_raw)
cands_tess_raw = analyze_candidates_test(rows_tess_raw, target_fecha)
print(f"\n1. Tesseract RAW:")
print(f"   - Palabras detectadas: {len(tess_results_raw)}")
print(f"   - Filas agrupadas: {len(rows_tess_raw)}")
print(f"   - Candidatos con Fecha + Hecho: {len(cands_tess_raw)}")
for c in cands_tess_raw:
    print(f"     -> Y={int(c['y_center'])}: {c['full_text']}")

# Evaluate Tesseract 3X
rows_tess_3x = agrupar_por_filas(tess_results_3x)
cands_tess_3x = analyze_candidates_test(rows_tess_3x, target_fecha)
print(f"\n2. Tesseract 3X Preprocesado:")
print(f"   - Palabras detectadas: {len(tess_results_3x)}")
print(f"   - Filas agrupadas: {len(rows_tess_3x)}")
print(f"   - Candidatos con Fecha + Hecho: {len(cands_tess_3x)}")
for c in cands_tess_3x:
    print(f"     -> Y={int(c['y_center'])}: {c['full_text']}")

# Evaluate PaddleOCR
rows_paddle = agrupar_por_filas(paddle_results)
cands_paddle = analyze_candidates_test(rows_paddle, target_fecha)
print(f"\n3. PaddleOCR:")
print(f"   - Textos detectados: {len(paddle_results)}")
print(f"   - Filas agrupadas: {len(rows_paddle)}")
print(f"   - Candidatos con Fecha + Hecho: {len(cands_paddle)}")
for c in cands_paddle:
    print(f"     -> Y={int(c['y_center'])}: {c['full_text']}")

print("\n" + "="*80)
