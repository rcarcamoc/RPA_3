import sys, pytesseract
sys.path.insert(0, '.')
from PIL import Image
import glob, numpy as np, cv2

# Cargar la imagen ORIGINAL del screenshot (no preprocessada)
files = sorted(glob.glob(r'rpa_framework/log/busqueda triple/*_TEXT.png'))
img_path = files[-1]
print(f'Analizando original: {img_path}')
img_pil = Image.open(img_path)
img_rgb = np.array(img_pil.convert('RGB'))

# Recortar la zona de la fila roja aproximada (Y=210-240 en imagen original de 820px)
# La imagen guardada tiene el borde rojo de 3px, la fila roja está en ~Y=227
# Primero detectar toda la region roja
img_hsv = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2HSV)
h, s, v = cv2.split(img_hsv)

# Detectar pixels rojos
red_mask = ((h < 10) | (h > 160)) & (s > 60) & (v > 60)
# Tambien naranja (celda Estado "Examen Hecho" podria ser naranja)
orange_mask = (h >= 10) & (h <= 25) & (s > 80) & (v > 80)

print(f'\nPixels rojos detectados: {np.sum(red_mask)}')
print(f'Pixels naranjas detectados: {np.sum(orange_mask)}')

# Encontrar las filas (Y) con mayor cantidad de pixels rojos
red_per_row = np.sum(red_mask, axis=1)
orange_per_row = np.sum(orange_mask, axis=1)

print('\nFilas con mas de 50 pixels rojos:')
for y in range(len(red_per_row)):
    if red_per_row[y] > 50:
        print(f'  Y={y:4d}  rojos={red_per_row[y]:5d}  naranjas={orange_per_row[y]:5d}')

# Recortar la region roja para ver su HSV en detalle
# Buscar rango Y de la fila roja
red_rows = [y for y in range(len(red_per_row)) if red_per_row[y] > 100]
if red_rows:
    y_min = min(red_rows)-2
    y_max = max(red_rows)+2
    print(f'\nFila roja entre Y={y_min} y Y={y_max}')
    
    # Recortar y analizar colores en la zona del Estado (approx X=700-900)
    crop = img_rgb[y_min:y_max, 690:900]
    crop_hsv = cv2.cvtColor(crop, cv2.COLOR_RGB2HSV)
    print('Sample HSV en zona Estado (X=690-900):')
    for y in range(0, crop_hsv.shape[0], 3):
        for x in range(0, crop_hsv.shape[1], 20):
            pixel_h, pixel_s, pixel_v = crop_hsv[y, x]
            if pixel_s > 30:
                r,g,b = crop[y,x]
                print(f'  y={y_min+y} x={690+x}  H={pixel_h:3d} S={pixel_s:3d} V={pixel_v:3d}  RGB=({r},{g},{b})')
