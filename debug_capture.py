# debug_capture.py
import logging
from mss import mss
import cv2
import numpy as np
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def capture_debug_screenshot():
    print("📸 Iniciando prueba de captura de pantalla...")
    
    try:
        with mss() as sct:
            # Listar monitores
            print(f"Monitores detectados: {len(sct.monitors)}")
            for i, m in enumerate(sct.monitors):
                print(f"  Monitor {i}: {m}")
            
            # Capturar monitor 0 (Todos)
            print("\nCapturando Monitor 0 (Combinado)...")
            monitor = sct.monitors[0]
            screenshot = sct.grab(monitor)
            img = np.array(screenshot)
            
            # Guardar
            filename = "debug_screenshot_all.png"
            cv2.imwrite(filename, img)
            print(f"✅ Captura guardada como: {os.path.abspath(filename)}")
            print(f"   Dimensiones: {img.shape}")
            
            return True
    except Exception as e:
        print(f"❌ Error capturando pantalla: {e}")
        return False

if __name__ == '__main__':
    capture_debug_screenshot()
    print("\nPor favor, abre la imagen 'debug_screenshot_all.png' para verificar si tu texto es visible.")
