"""
Diagnóstico final: simula exactamente lo que hace busqueda_triple_text_only.py
sobre la imagen de log para verificar que encuentra el candidato Colangio RM.
"""
import sys, pytesseract, glob
sys.path.insert(0, '.')
from PIL import Image
from pytesseract import Output
from rapidfuzz import fuzz

from rpa_framework.recordings.ocr.utilidades.preproceso_ocr import preprocess_high_fidelity

# ── Parámetros target ─────────────────────────────────────────────────────
TARGET_FECHA   = "11-03-2026"
TARGET_SINONIMO = "Colangio RM"
ROW_TOLERANCE  = 15

# ── Cargar imagen ─────────────────────────────────────────────────────────
files = sorted(glob.glob(r'rpa_framework/log/busqueda triple/*_TEXT.png'))
img_path = files[-1]
print(f"Imagen: {img_path}\n")
img = Image.open(img_path)

# ── Preprocesar ───────────────────────────────────────────────────────────
preprocessed, scale = preprocess_high_fidelity(img, scale_factor=3)
print(f"Scale: {scale}")

# ── OCR ───────────────────────────────────────────────────────────────────
data = pytesseract.image_to_data(preprocessed, lang='spa',
                                  output_type=Output.DICT,
                                  config='--psm 3 --oem 3')

# ── Agrupar por filas (igual que agrupar_por_filas) ───────────────────────
ocr_items = []
for i in range(len(data['text'])):
    txt = data['text'][i].strip()
    if not txt or int(data['conf'][i]) < 0:
        continue
    cx = data['left'][i] + data['width'][i] // 2
    cy = data['top'][i]  + data['height'][i] // 2
    # Normalizar al espacio original
    nx = cx / scale
    ny = cy / scale
    ocr_items.append({'text': txt, 'cx': nx, 'cy': ny})

print(f"Palabras OCR extraídas: {len(ocr_items)}\n")

# Agrupar
rows = {}
for item in ocr_items:
    placed = False
    for yk in list(rows.keys()):
        if abs(item['cy'] - yk) <= ROW_TOLERANCE:
            rows[yk].append(item)
            placed = True
            break
    if not placed:
        rows[item['cy']] = [item]

# Construir texto de cada fila
rows_list = []
for yk in sorted(rows.keys()):
    items = sorted(rows[yk], key=lambda x: x['cx'])
    text = " ".join(i['text'] for i in items)
    rows_list.append({'y': yk, 'text': text})

print(f"Total filas agrupadas: {len(rows_list)}\n")

# ── Verificar candidatos ──────────────────────────────────────────────────
target_digits = "".join(filter(str.isdigit, TARGET_FECHA))
print("── Análisis de candidatos ──────────────────────────────────────────")
found = 0
for row in rows_list:
    txt   = row['text']
    norm  = txt.lower()
    digs  = "".join(filter(str.isdigit, txt))

    has_date = (
        (TARGET_FECHA in txt)
        or (TARGET_FECHA.replace("-", "/") in txt)
        or (target_digits in digs)
        or (fuzz.partial_ratio(TARGET_FECHA, txt) > 80)
    )
    score_hecho    = fuzz.partial_ratio("hecho",    norm)
    score_realizado = fuzz.partial_ratio("realizado", norm)
    has_estado = (score_hecho > 80) or (score_realizado > 80)
    has_exam   = fuzz.partial_ratio(TARGET_SINONIMO.lower(), norm) > 70

    date_score = fuzz.partial_ratio(TARGET_FECHA, txt)
    if has_date or has_estado:
        print(f"  Y={int(row['y']):4d}  fecha={'✓' if has_date else '·'}({date_score})  "
              f"hecho={'✓' if has_estado else '·'}({score_hecho})  "
              f"exam={'✓' if has_exam else '·'}  ➜  "
              f"{'✅ CANDIDATO' if (has_date and has_estado) else '❌'}  |  {txt[:100]}")
        if has_date and has_estado:
            found += 1

print(f"\n{'✅ ÉXITO: '+str(found)+' candidato(s) encontrado(s)' if found else '❌ SIN CANDIDATOS'}")
