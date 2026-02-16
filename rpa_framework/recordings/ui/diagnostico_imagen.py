import cv2
import numpy as np
import os
import pyautogui

def diagnosticar_busqueda():
    base_path = r"c:\Desarrollo\RPA_3"
    image_rel_path = r"rpa_framework\utils\word.png"
    template_path = os.path.join(base_path, image_rel_path)

    if not os.path.exists(template_path):
        print(f"Error: No existe la imagen de referencia: {template_path}")
        return

    print("--- INICIANDO DIAGNÓSTICO DE IMAGEN ---")
    print(f"1. Cargando imagen de referencia (template): {template_path}")
    
    # Cargar template
    template = cv2.imread(template_path)
    if template is None:
        print("Error: No se pudo leer la imagen con cv2. Verifique formato.")
        return
        
    print(f"   Dimensiones del template: {template.shape}")

    print("2. Tomando captura de pantalla actual...")
    screenshot = pyautogui.screenshot()
    screenshot = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
    print(f"   Dimensiones del screenshot: {screenshot.shape}")

    print("3. Ejecutando Template Matching (cv2.TM_CCOEFF_NORMED)...")
    
    # Verificar que el template no sea más grande que el screenshot
    if template.shape[0] > screenshot.shape[0] or template.shape[1] > screenshot.shape[1]:
        print("ERROR CRÍTICO: La imagen de referencia es más grande que la pantalla.")
        return

    result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)

    print("\n--- RESULTADOS ---")
    print(f"Mejor coincidencia encontrada: {max_val:.4f} ({max_val*100:.2f}%)")
    print(f"Posición (Top-Left): {max_loc}")
    print(f"Umbral requerido por el usuario: 0.90 (90.00%)")

    if max_val >= 0.90:
        print("\nCONCLUSIÓN: Debería funcionar. La imagen ES visible con >90% de confianza.")
        print("Posible causa del error previo: El momento de la captura fue distinto, o problema de pyautgui.")
    else:
        print("\nCONCLUSIÓN: No se alcanza el 90% de confianza.")
        print("Posibles causas:")
        print(" - La imagen en pantalla es ligeramente diferente (colores, zoom, resolución).")
        print(" - Renderizado de fuentes (anti-aliasing).")
        print(" - Fondo diferente (transparencia).")
        print(f"SUGERENCIA: Bajar la confianza a {max_val - 0.05:.2f} ({(max_val-0.05)*100:.0f}%) o recapturar la imagen de referencia.")

    # Opcional: Guardar resultado visual
    output_path = os.path.join(base_path, "rpa_framework", "log", "diagnostico_match.png")
    
    # Dibujar rectángulo en el mejor match
    w, h = template.shape[1], template.shape[0]
    top_left = max_loc
    bottom_right = (top_left[0] + w, top_left[1] + h)
    cv2.rectangle(screenshot, top_left, bottom_right, (0, 0, 255), 2)
    
    cv2.putText(screenshot, f"Confianza: {max_val:.2f}", (top_left[0], top_left[1]-10), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0,0,255), 2)
    
    cv2.imwrite(output_path, screenshot)
    print(f"\nImagen de diagnóstico guardada en: {output_path}")

if __name__ == "__main__":
    diagnosticar_busqueda()
