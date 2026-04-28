"""Diagnóstico OCR sobre la captura REAL donde el visor estaba visible."""
import pytesseract
import cv2
import numpy as np

# Usar la captura real donde el texto SÍ era visible
img = cv2.imread(r"c:\Desarrollo\RPA_3\rpa_framework\log\debug_screenshots\visor_doc_not_found_20260320_073005.png")
print(f"Imagen: {img.shape}")

# ── Zona de la pestaña del visor (alto de barra de título) ──
# En la imagen, "Visor de documentos" está aprox en y=25-45, x=45-220  
# Pero la pestaña puede moverse, vamos a probar la zona superior completa
top = img[20:50, 30:250]  # Zona de la pestaña del visor
cv2.imwrite(r"c:\Desarrollo\RPA_3\rpa_framework\log\debug_screenshots\debug_tab_crop.png", top)

# ── Preprocesamiento variado ──
gray = cv2.cvtColor(top, cv2.COLOR_BGR2GRAY)
scale = 4

# A) Gris escalado
gray_sc = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

# B) Invertido (texto claro sobre oscuro → texto oscuro sobre claro)
inv = cv2.bitwise_not(gray)
inv_sc = cv2.resize(inv, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

# C) Threshold adaptativo invertido
thresh_adapt = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 5)
thresh_sc = cv2.resize(thresh_adapt, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)

# D) OTSU invertido escalado
_, otsu_inv = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
otsu_sc = cv2.resize(otsu_inv, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)

cv2.imwrite(r"c:\Desarrollo\RPA_3\rpa_framework\log\debug_screenshots\debug_tab_gray.png", gray_sc)
cv2.imwrite(r"c:\Desarrollo\RPA_3\rpa_framework\log\debug_screenshots\debug_tab_inv.png", inv_sc)
cv2.imwrite(r"c:\Desarrollo\RPA_3\rpa_framework\log\debug_screenshots\debug_tab_thresh.png", thresh_sc)
cv2.imwrite(r"c:\Desarrollo\RPA_3\rpa_framework\log\debug_screenshots\debug_tab_otsu.png", otsu_sc)

for label, image in [
    ("A) Gris x4", gray_sc),
    ("B) Invertido x4", inv_sc),
    ("C) Adaptativo-Inv x4", thresh_sc),
    ("D) OTSU-Inv x4", otsu_sc),
]:
    data = pytesseract.image_to_data(image, lang='spa', output_type=pytesseract.Output.DICT)
    print(f"\n{'='*60}")
    print(f"{label}")
    print(f"{'='*60}")
    for i in range(len(data['text'])):
        txt = data['text'][i].strip()
        if txt:
            print(f"  [{data['conf'][i]:3}%] '{txt}'")

# ── Ahora probar con la pantalla completa con inversión ──
print(f"\n{'='*60}")
print("PANTALLA COMPLETA - Invertida + escalada x2 (solo zona top 80px)")
print(f"{'='*60}")

full_top = img[0:80, :]
gray_full = cv2.cvtColor(full_top, cv2.COLOR_BGR2GRAY)
inv_full = cv2.bitwise_not(gray_full)
inv_full_sc = cv2.resize(inv_full, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

data = pytesseract.image_to_data(inv_full_sc, lang='spa', output_type=pytesseract.Output.DICT)
for i in range(len(data['text'])):
    txt = data['text'][i].strip()
    if txt and int(data['conf'][i]) > 10:
        print(f"  [{data['conf'][i]:3}%] ({data['left'][i]//2:4},{data['top'][i]//2:4}) '{txt}'")

print("\nDONE")
