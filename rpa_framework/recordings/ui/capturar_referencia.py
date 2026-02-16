import pyautogui
import time
import os

def capturar_nueva_referencia():
    """
    Script para capturar una nueva imagen de referencia.
    Instrucciones:
    1. Ejecuta este script
    2. Tienes 5 segundos para abrir Word y posicionar la ventana
    3. El script tomará una captura de pantalla completa
    4. Luego usa una herramienta de recorte para seleccionar la zona exacta
    """
    base_path = r"c:\Desarrollo\RPA_3"
    output_dir = os.path.join(base_path, "rpa_framework", "log", "capturas_referencia")
    os.makedirs(output_dir, exist_ok=True)
    
    print("=" * 60)
    print("CAPTURA DE IMAGEN DE REFERENCIA")
    print("=" * 60)
    print("\nInstrucciones:")
    print("1. Abre Word y asegúrate de que la barra de herramientas esté visible")
    print("2. Posiciona la ventana donde quieras")
    print("3. Espera a que se tome la captura automática")
    print("\nLa captura se tomará en 5 segundos...")
    
    for i in range(5, 0, -1):
        print(f"{i}...")
        time.sleep(1)
    
    print("\n¡CAPTURANDO!")
    screenshot = pyautogui.screenshot()
    
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(output_dir, f"captura_completa_{timestamp}.png")
    screenshot.save(output_path)
    
    print(f"\n✓ Captura guardada en: {output_path}")
    print("\nAhora:")
    print("1. Abre la imagen capturada")
    print("2. Usa una herramienta de recorte (Snipping Tool, Paint, etc.)")
    print("3. Recorta EXACTAMENTE la zona de la barra de herramientas que quieres buscar")
    print("4. Guarda el recorte como: c:\\Desarrollo\\RPA_3\\rpa_framework\\utils\\word.png")
    print("   (reemplaza la imagen existente)")
    print("\nTIPS:")
    print("- Recorta un área distintiva pero no muy grande")
    print("- Evita áreas con texto que pueda cambiar")
    print("- Incluye iconos característicos de la barra de herramientas")

if __name__ == "__main__":
    capturar_nueva_referencia()
