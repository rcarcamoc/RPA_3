import sys, pytesseract, glob
sys.path.insert(0, '.')
from PIL import Image
import numpy as np
from pytesseract import Output
from rpa_framework.recordings.ocr.utilidades.preproceso_ocr import preprocess_high_fidelity

# Cargar imagen original del log
files = sorted(glob.glob(r'rpa_framework/log/busqueda triple/*_TEXT.png'))
img_path = files[-1]
print(f'Usando: {img_path}')
img = Image.open(img_path)

# Preprocesar con el nuevo umbral V=155
result, scale = preprocess_high_fidelity(img, scale_factor=3)
result.save(r'rpa_framework/log/busqueda triple/TEST_v155.png')
print(f'Imagen guardada (scale={scale})')

# OCR directo
data = pytesseract.image_to_data(result, lang='spa', output_type=Output.DICT, config='--psm 3 --oem 3')

print('\n--- Busqueda de palabras clave en toda la imagen ---')
keywords = ['hecho', 'examen', '11-03', 'colangio', 'stat', 'hech']
found = set()
for i in range(len(data['text'])):
    txt = data['text'][i].strip()
    if not txt:
        continue
    tl = txt.lower()
    for kw in keywords:
        if kw in tl and kw not in found:
            y = data['top'][i] + data['height'][i]//2
            x = data['left'][i]
            conf = data['conf'][i]
            print(f'  KW={kw!r:14s}  Y={y:5d} X={x:5d} conf={conf:3d}  "{txt}"')
            found.add(kw)

print('\n--- Zona Y=950-1150 (fila roja 3x) ---')
for i in range(len(data['text'])):
    txt = data['text'][i].strip()
    if not txt:
        continue
    y = data['top'][i] + data['height'][i]//2
    if 950 <= y <= 1150:
        x = data['left'][i]
        conf = data['conf'][i]
        print(f'  Y={y:5d} X={x:5d} conf={conf:3d}  "{txt}"')
