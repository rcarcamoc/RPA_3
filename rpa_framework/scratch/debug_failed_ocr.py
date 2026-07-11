# -*- coding: utf-8 -*-
import sys
from pathlib import Path
import pytesseract
from PIL import Image

def main():
    img_path = Path("rpa_framework/log/busqueda triple/2026-06-16 16-37-38_OCR_PREPROCESSED_3X.png")
    if not img_path.exists():
        print(f"❌ Image not found: {img_path}")
        return

    print(f"Reading: {img_path}")
    img = Image.open(img_path)
    
    # Run Tesseract with custom config used in the code
    custom_config = '--psm 6 -l spa --oem 3'
    text = pytesseract.image_to_string(img, config=custom_config)
    
    print("\n--- OCR TEXT OUTPUT ---")
    print(text)
    print("-----------------------")

    # Let's also run image_to_data to see what coordinates we get
    print("\n--- OCR DATA WORDS ---")
    data = pytesseract.image_to_data(img, config=custom_config, output_type=pytesseract.Output.DICT)
    words = []
    for i in range(len(data['text'])):
        word = data['text'][i].strip()
        if word:
            words.append(word)
    print(" ".join(words))

if __name__ == "__main__":
    main()
