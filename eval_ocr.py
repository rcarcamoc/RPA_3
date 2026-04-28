import sys
from pathlib import Path
import cv2

# Agregar ruta base
base_path = Path("c:/Desarrollo/RPA_3/rpa_framework")
sys.path.insert(0, str(base_path))

from ocr.engine import OCREngine

def test_ocr(image_path, psm_mode='--psm 6', preprocess=True):
    img = cv2.imread(image_path)
    if img is None:
        print(f"No se pudo cargar {image_path}")
        return
        
    engine = OCREngine(
        engine='tesseract',
        language='spa',
        use_gpu=False,
        confidence_threshold=0.0,  # Bajar conf para ver todo
        preprocess=preprocess,
        custom_config=psm_mode
    )
    
    results = engine.extract_text_with_location(img)
    
    print(f"\nResultados (PSM: {psm_mode}, Preprocess: {preprocess}):")
    # Agrupar simple para visualización
    results.sort(key=lambda x: x['center']['y'])
    lines = {}
    for r in results:
        y_group = int(r['center']['y']) // 15
        if y_group not in lines: lines[y_group] = []
        lines[y_group].append(r)
        
    for k, v in sorted(lines.items()):
        v.sort(key=lambda x: x['center']['x'])
        # Mostrar X inicio, X fin y el texto
        text_parts = []
        for word in v:
            if word['text'].strip():
                text_parts.append(f"[{word['center']['x']:.0f}] {word['text']} ")
        if text_parts:
            print(f"Y~{k*15}: {' '.join(text_parts)}")

if __name__ == '__main__':
    img_path = r"c:\Desarrollo\RPA_3\rpa_framework\log\patologia_critica\patologia_2026-03-23 06-57-27.png"
    # Probar varias combinaciones
    test_ocr(img_path, '--psm 6', True)
    test_ocr(img_path, '--psm 6', False)
    test_ocr(img_path, '--psm 11', False)
    test_ocr(img_path, '--psm 4', False)
