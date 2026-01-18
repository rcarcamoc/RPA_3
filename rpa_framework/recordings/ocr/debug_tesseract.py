import sys
import os
import mss
import numpy as np

# Add framework root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from ocr.engine import OCREngine
from ocr.actions import OCRActions
from ocr.matcher import OCRMatcher

def debug_ocr():
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        region = {
            "top": monitor["top"],
            "left": monitor["left"],
            "width": int(monitor["width"] * 0.20), # 20% total width
            "height": monitor["height"]
        }
        
    engine = OCREngine(engine='tesseract', language='es', confidence_threshold=0.1)
    actions = OCRActions(engine)
    
    print(f"Capturando región: {region}")
    screenshot = actions.capture_screenshot(region=region)
    
    results = engine.extract_text_with_location(screenshot)
    
    print(f"--- Textos encontrados ({len(results)}) ---")
    for r in results:
        print(f"[{r['confidence']:.2f}] {r['text']}")
    print("---------------------------------")

if __name__ == "__main__":
    debug_ocr()
