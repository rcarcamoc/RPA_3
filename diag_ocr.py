import sys, pytesseract
sys.path.insert(0, '.')
from PIL import Image
import glob, os

# Usar la imagen preprocesada mas reciente
files = sorted(glob.glob(r'rpa_framework/log/busqueda triple/*PREPROCESSED_3X.png'))
img_path = files[-1]
print(f'Analizando: {img_path}')
img = Image.open(img_path)
print(f'Imagen size: {img.size}')

from pytesseract import Output
data = pytesseract.image_to_data(img, lang='spa', output_type=Output.DICT, config='--psm 3 --oem 3')

# Imprimir palabras en zona Y=800-1200 (zona roja estimada en 3x)
print('\n--- Palabras en zona Y=800-1200 (fila roja / 3x) ---')
for i in range(len(data['text'])):
    txt = data['text'][i].strip()
    if not txt:
        continue
    y = data['top'][i] + data['height'][i]//2
    if 800 <= y <= 1200:
        x = data['left'][i]
        conf = data['conf'][i]
        print(f'  Y={y:5d} X={x:5d} conf={conf:3d}  "{txt}"')

print('\n--- Busqueda de palabras clave en TODA la imagen ---')
keywords = ['hecho', 'examen', '11-03', 'colangio', 'stat']
for i in range(len(data['text'])):
    txt = data['text'][i].strip()
    if not txt:
        continue
    tl = txt.lower()
    for kw in keywords:
        if kw in tl:
            y = data['top'][i] + data['height'][i]//2
            x = data['left'][i]
            print(f'  KW={kw!r:12s}  Y={y:5d} X={x:5d}  "{txt}"')
            break
