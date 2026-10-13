import sys
import cv2
import numpy as np
from paddleocr import PaddleOCR

print("Initializing PaddleOCR...")
ocr = PaddleOCR(lang='es')
print("PaddleOCR initialized successfully!")

test_img = np.ones((100, 500, 3), dtype=np.uint8) * 255
cv2.putText(test_img, "Examen Hecho 06-10-2026", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)

result = ocr.ocr(test_img)
print("Type of result:", type(result))
print("Result:", result)
