# test_ocr_basic.py

import logging
import sys
import os

# Asegurar que podemos importar rpa_framework
sys.path.append(os.getcwd())

try:
    from rpa_framework.ocr import OCREngine, OCRMatcher, OCRActions
except ImportError as e:
    print(f"❌ Error importando librerías: {e}")
    sys.exit(1)

logging.basicConfig(level=logging.INFO)

def test_ocr_initialization():
    """Test 1: Inicializar OCR Engine"""
    try:
        print("--- Test 1: Initialization ---")
        # Usar idioma 'en' o 'es' dependiendo de lo que se descargue más rápido/exista
        # easyocr descargará el modelo si no existe
        engine = OCREngine(engine='easyocr', language='en', use_gpu=False)
        print("✓ OCREngine inicializado correctamente")
        return True
    except Exception as e:
        print(f"✗ Error inicializando OCREngine: {e}")
        return False

def test_ocr_matcher():
    """Test 2: Matcher"""
    try:
        print("\n--- Test 2: Matcher ---")
        matcher = OCRMatcher(threshold=80)
        
        # Datos simulados
        mock_data = [
            {
                'text': 'Enviar',
                'confidence': 0.95,
                'center': {'x': 100, 'y': 50}
            }
        ]
        
        matches = matcher.find_text(mock_data, 'Enviar', fuzzy=True)
        if len(matches) > 0:
            print(f"[OK] Matcher funciona: encontrado '{matches[0]['text']}'")
            return True
        else:
            print("[FAIL] Matcher fallo: no encontró texto")
            return False
            
    except Exception as e:
        print(f"[FAIL] Error en Matcher: {e}")
        return False

def test_ocr_code_generation():
    """Test 3: Code Generator"""
    try:
        print("\n--- Test 3: Code Generator ---")
        from rpa_framework.ocr import OCRCodeGenerator
        
        gen = OCRCodeGenerator(engine='easyocr', language='es')
        module = gen.generate_click_module('Enviar')
        
        if gen.validate_code(module['code']):
            print(f"[OK] Código generado válido: {module['name']}")
            return True
        else:
            print("[FAIL] Código generado inválido")
            return False
            
    except Exception as e:
        print(f"[FAIL] Error en Code Generation: {e}")
        return False

def test_ocr_extraction():
    """Test 4: Real Extraction (Dummy Image)"""
    try:
        print("\n--- Test 4: Real Extraction ---")
        import numpy as np
        import cv2
        
        # Crear imagen negra con texto blanco
        img = np.zeros((100, 300, 3), dtype=np.uint8)
        cv2.putText(img, "TEST", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        engine = OCREngine(engine='easyocr', language='en', use_gpu=False)
        # Suppress verbose download if possible? No easy way, but we hope 
        # the error inside easyocr is skipped if we don't catch it?? 
        # Actually easyocr's internal print failure might not stop execution if they handle it,
        # but the traceback verified it crashed the script.
        # We can try to wrap initialization in valid try/except.
        results = engine.extract_text_with_location(img)
        
        print(f"[OK] Extracción ejecutada sin errores (detectados: {len(results)})")
        return True
    except Exception as e:
        print(f"[FAIL] Error en extracción: {e}")
        return False

def test_ocr_initialization():
    """Test 1: Inicializar OCR Engine"""
    try:
        print("--- Test 1: Initialization ---")
        engine = OCREngine(engine='easyocr', language='en', use_gpu=False)
        print("[OK] OCREngine inicializado correctamente")
        return True
    except Exception as e:
        print(f"[FAIL] Error inicializando OCREngine: {e}")
        return False

if __name__ == '__main__':
    print("\n=== OCR Initialization Tests ===\n")
    
    tests = [
        test_ocr_initialization, 
        test_ocr_extraction,     
        test_ocr_matcher,       
        test_ocr_code_generation, 
    ]
    
    results = [test() for test in tests]
    
    print(f"\n[DONE] Tests passed: {sum(results)}/{len(results)}\n")
