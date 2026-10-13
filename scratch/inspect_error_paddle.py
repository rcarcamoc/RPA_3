import sys
import os
import time
import cv2
from pathlib import Path

# Load error image
img = cv2.imread(r'c:\Desarrollo\RPA_3\rpa_framework\log\error_20261008_095444.png')
# Triple region: (188, 93, 1720, 900)
crop = img[93:93+900, 188:188+1720]
cv2.imwrite(r'c:\Desarrollo\RPA_3\scratch\crop_error_095444.png', crop)

from paddleocr import PaddleOCR
print("Iniciando PaddleOCR sin unwarping ni orientación...")
t0 = time.time()
paddle_ocr = PaddleOCR(
    lang='es',
    use_doc_orientation_classify=False,
    use_doc_unwarping=False,
    use_textline_orientation=False,
    text_recognition_batch_size=16
)
print(f"PaddleOCR inicializado en {time.time()-t0:.2f}s")

t1 = time.time()
res = paddle_ocr.predict(crop)
elapsed = time.time() - t1
print(f"Inferencia completada en {elapsed:.2f}s")

if res:
    rec_texts = res[0].get('rec_texts', [])
    rec_scores = res[0].get('rec_scores', [])
    rec_boxes = res[0].get('rec_boxes', [])
    
    print(f"\nTotal detectado: {len(rec_texts)} textos")
    lines_sorted = sorted(zip(rec_texts, rec_scores, rec_boxes), key=lambda x: (x[2][1], x[2][0]))
    for txt, score, box in lines_sorted:
        print(f"Y={int(box[1]):3d} X={int(box[0]):3d} (score={score:.2f}): {txt}")
