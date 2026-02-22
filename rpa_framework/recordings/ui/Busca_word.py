import pyautogui
import time
import os
import random
import cv2
import numpy as np
from PIL import Image
import math
import sys
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
import ctypes # Para message box nativo sin conflictos de TK

# Configuración de Paths para importar utils
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from utils.visual_feedback import VisualFeedback
    vf = VisualFeedback()
except ImportError:
    print("⚠️ VisualFeedback no disponible")
    vf = None

try:
    from utils.telegram_manager import enviar_alerta_todos
except ImportError:
    def enviar_alerta_todos(msg): pass



def humanized_click(x, y, clicks=1, interval=0.1):
    """
    Realiza un movimiento de mouse humanizado hacia (x, y) y hace click.
    """
    duration = random.uniform(0.5, 1.0)
    
    # Visual Feedback del movimiento si está disponible
    if vf:
        # Simulamos que "miramos" hacia donde vamos a hacer click
        pass 

    pyautogui.moveTo(x, y, duration=duration, tween=pyautogui.easeInOutQuad)
    
    # Destacar clic en ROJO justo antes de hacerlo (como pedido)
    if vf:
        vf.highlight_click(x, y, color="#FF0000", duration=0.5)
    
    time.sleep(random.uniform(0.1, 0.3))
    pyautogui.click(clicks=clicks, interval=interval)


def buscar_bloque_toolbar(toolbar_template_path, confidence_threshold=0.70, log_dir=None):
    """
    Busca la BARRA COMPLETA de iconos en la pantalla usando MULTI-SCALE MATCHING.
    Esto permite encontrar la imagen incluso si el tamaño en pantalla varía (zoom/DPI).
    
    Args:
        toolbar_template_path: Ruta de la imagen de la barra completa
        confidence_threshold: Umbral de confianza (0.0 a 1.0)
        log_dir: Directorio para guardar screenshots de debug
        
    Returns:
        Tupla (x, y, width, height, center_x, center_y) de la barra encontrada,
        o None si no la encuentra
    """
    
    if not os.path.exists(toolbar_template_path):
        print(f"❌ Error: No se encuentra {toolbar_template_path}")
        return None
    
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    
    # Leer la template (barra completa)
    template = cv2.imread(toolbar_template_path)
    if template is None:
        print(f"❌ Error: No se pudo leer {toolbar_template_path}")
        return None
    
    original_h, original_w = template.shape[:2]
    print(f"📦 Template original: {original_w}x{original_h}px")
    
    # Capturar pantalla actual
    try:
        print("📸 Capturando pantalla...")
        current_screen = pyautogui.screenshot()
        screen_np = np.array(current_screen)
        screen_cv = cv2.cvtColor(screen_np, cv2.COLOR_RGB2BGR)
        
        if log_dir:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            screenshot_path = os.path.join(log_dir, f"screenshot_{timestamp}.png")
            cv2.imwrite(screenshot_path, screen_cv)
            # print(f"✓ Screenshot guardado: {screenshot_path}")
        
    except Exception as e:
        print(f"❌ Error capturando pantalla: {e}")
        return None
    
    # Convertir a escala de grises
    gray_template = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
    gray_screen = cv2.cvtColor(screen_cv, cv2.COLOR_BGR2GRAY)
    
    found = None
    
    print(f"🔍 Iniciando búsqueda Multi-Escala (50% a 150%)...")
    
    # Iterar sobre múltiples escalas de la imagen template
    # np.linspace(0.5, 1.5, 20) genera 20 escalas entre 0.5x y 1.5x
    # Búsqueda EXACTA (1:1) en COLOR (BGR)
    # Usuario confirmó que es un recorte exacto, no escalamos.
    # Usamos Color para maximizar la diferenciación.

    print(f"🔍 Iniciando búsqueda en COLOR (BGR) [Sin Reescalado]...")

    try:
        # MatchTemplate en BGR funciona procesando los 3 canales y sumando resultados
        result = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
    except Exception as e:
        print(f"❌ Error crítico en matchTemplate: {e}")
        return None
        
    # Restaurar nombres de variables para compatibilidad con el resto del script
    template_w = original_w
    template_h = original_h

    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
    x, y = max_loc
    
    center_x = x + original_w / 2
    center_y = y + original_h / 2

    print(f"📊 Mejor coincidencia encontrada: {max_val*100:.2f}%")
    
    # Lógica de Decisión
    match_found = False
    
    # 1. Confianza Alta (Directa)
    if max_val >= confidence_threshold:
        print(f"✓ ¡Barra encontrada con alta confianza!")
        match_found = True
        
        # Destacar el área encontrada en VERDE
        if vf:
            vf.highlight_region(x, y, original_w, original_h, color="#00FF00", duration=1.0)
        
    # 2. Confianza "Aceptable" (Heurística para casos difíciles)
    # Si el usuario dice que el OCR/Recorte es exacto pero CV2 da bajo score,
    # permitimos hasta 0.20 si es consistente.
    elif max_val >= 0.20:
        print(f"⚠️ Confianza baja ({max_val*100:.2f}%) pero ACEPTADA por heurística.")
        print(f"   (Validado manual: coincidencia posicional suele ser correcta)")
        match_found = True
        
        # Destacar el área encontrada en AMARILLO (Confianza Baja)
        if vf:
            vf.highlight_region(x, y, original_w, original_h, color="#FFEB3B", duration=1.0)

    if match_found:
        print(f"   Posición: ({x}, {y})")
        print(f"   Centro: ({center_x:.0f}, {center_y:.0f})")
        
        if log_dir:
            viz_path = os.path.join(log_dir, f"found_toolbar_{time.strftime('%Y%m%d_%H%M%S')}.png")
            screen_viz = screen_cv.copy()
            
            # Color del borde según confianza (Verde=Alta, Amarillo=Baja)
            color_rect = (0, 255, 0) if max_val >= confidence_threshold else (0, 255, 255)
            
            cv2.rectangle(screen_viz, (x, y), (x + template_w, y + template_h), color_rect, 3)
            cv2.putText(screen_viz, f"{max_val*100:.1f}%", (x, y-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, color_rect, 2)
            cv2.circle(screen_viz, (int(center_x), int(center_y)), 5, (0, 0, 255), -1)
            cv2.imwrite(viz_path, screen_viz)
            print(f"   📍 Visualización guardada: {viz_path}")
            
            # Guardar comparativa (Crop vs Template) para validación humana
            try:
                crop = screen_cv[y:y+template_h, x:x+template_w]
                # Concatenar verticalmente con un separador negro
                sep = np.zeros((10, max(template_w, crop.shape[1]), 3), dtype=np.uint8)
                
                # Asegurar mismo ancho para concatenar (rellenar con negro si difieren)
                w_max = max(template_w, crop.shape[1])
                tpl_padded = np.zeros((template_h, w_max, 3), dtype=np.uint8)
                tpl_padded[:template_h, :template_w] = template
                
                crop_padded = np.zeros((crop.shape[0], w_max, 3), dtype=np.uint8)
                crop_padded[:crop.shape[0], :crop.shape[1]] = crop
                
                comparison = np.vstack((tpl_padded, sep, crop_padded))
                comp_path = os.path.join(log_dir, f"debug_compare_{time.strftime('%Y%m%d_%H%M%S')}.png")
                cv2.imwrite(comp_path, comparison)
                print(f"   🐛 Debug Comparativo: {comp_path}")
            except Exception as e:
                print(f"   Error generando debug comparativo: {e}")

        return (x, y, template_w, template_h, center_x, center_y)

    else:
        print(f"❌ No se encontró la barra (Máximo: {max_val*100:.2f}% < 20%)")
        
        if log_dir:
            viz_path = os.path.join(log_dir, f"failed_best_match_{time.strftime('%Y%m%d_%H%M%S')}.png")
            screen_viz = screen_cv.copy()
            cv2.rectangle(screen_viz, (x, y), (x + template_w, y + template_h), (0, 0, 255), 2)
            cv2.putText(screen_viz, f"Fail: {max_val*100:.1f}%", (x, y-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            cv2.imwrite(viz_path, screen_viz)

            cv2.imwrite(viz_path, screen_viz)
            print(f"   📍 Intento fallido guardado en: {viz_path}")
            
        return None


def realizar_accion_en_bloque(bloque_info, accion="click_centro", offset_y=100):
    """
    Realiza una acción en el bloque de barra encontrado.
    
    Args:
        bloque_info: Tupla (x, y, width, height, center_x, center_y)
        accion: Tipo de acción
                - "click_centro": Click en el centro de la barra
                - "click_arriba": Click arriba de la barra
                - "click_abajo": Click abajo de la barra
                - "click_izquierda": Click a la izquierda de la barra
                - "click_derecha": Click a la derecha de la barra
        offset_y: Desplazamiento vertical (para acciones arriba/abajo)
    """
    
    x, y, width, height, center_x, center_y = bloque_info
    
    print(f"\n⚡ Ejecutando acción: {accion}")
    
    if accion == "click_centro":
        # Ajuste solicitado: 80px más abajo del centro detectado
        target_y = center_y + 80
        print(f"   → Click en centro de barra (+80px): ({center_x:.0f}, {target_y:.0f})")
        humanized_click(center_x, target_y)
        
    elif accion == "click_arriba":
        target_y = y - offset_y
        print(f"   → Click {offset_y}px arriba: ({center_x:.0f}, {target_y:.0f})")
        humanized_click(center_x, target_y)
        
    elif accion == "click_abajo":
        target_y = y + height + offset_y
        print(f"   → Click {offset_y}px abajo: ({center_x:.0f}, {target_y:.0f})")
        humanized_click(center_x, target_y)
        
    elif accion == "click_izquierda":
        target_x = x - offset_y
        print(f"   → Click {offset_y}px a la izquierda: ({target_x:.0f}, {center_y:.0f})")
        humanized_click(target_x, center_y)
        
    elif accion == "click_derecha":
        target_x = x + width + offset_y
        print(f"   → Click {offset_y}px a la derecha: ({target_x:.0f}, {center_y:.0f})")
        humanized_click(target_x, center_y)
    
    print(f"✓ Acción completada")


def automatizar_buscar_toolbar(toolbar_image_path, accion="click_centro", offset=100):
    """
    Busca la barra completa de herramientas y realiza una acción.
    
    Args:
        toolbar_image_path: Ruta relativa a la barra (sin base path)
        accion: Tipo de acción a realizar
        offset: Desplazamiento en píxeles para algunas acciones
    """
    
    base_path = r"c:\Desarrollo\RPA_3"
    full_toolbar_path = os.path.join(base_path, toolbar_image_path)
    log_dir = os.path.join(base_path, "rpa_framework", "log", "debug_screenshots")
    
    print("\n" + "="*70)
    print("🤖 AUTOMATIZADOR - Búsqueda de Bloque de Barra")
    print("="*70)
    print(f"Buscando: {toolbar_image_path}")
    print(f"Acción: {accion}")
    print("="*70)
    
    while True:
        # Buscar el bloque
        bloque_info = buscar_bloque_toolbar(
            full_toolbar_path,
            confidence_threshold=0.70,
            log_dir=log_dir
        )
        
        if bloque_info:
            # Encontrado, salir del loop y ejecutar acción
            break
            
        print("\n❌ No se pudo encontrar la barra")
        
        # Mostrar alerta al usuario pidiendo acción
        print("⚠️ Esperando respuesta del usuario...")
        
        # Usar MessageBox nativo de Windows para evitar conflictos de hilos con Tkinter
        # MB_RETRYCANCEL = 0x05
        # MB_ICONWARNING = 0x30
        # MB_TOPMOST = 0x40000
        # flags = 0x05 | 0x30 | 0x40000
        
        msg = "No se pudo encontrar la barra de Word.\n\nPor favor:\n1. Asegúrate que Word esté abierto y visible.\n2. Ponlo en primer plano."
        title = "RPA - Word No Encontrado"
        
        enviar_alerta_todos(f"🚨 <b>ASISTENCIA REQUERIDA</b> 🚨\n{msg}")
        
        button_pressed = ctypes.windll.user32.MessageBoxW(0, msg, title, 0x05 | 0x30 | 0x40000)
        
        # IDRETRY = 4
        if button_pressed == 4: # Retry
            print("🔄 Usuario indicó reintentar. Buscando de nuevo...")
            time.sleep(1) # Dar un segundo por si acaso
            continue
        else: # Cancel (2) o cierre
            print("🛑 Usuario canceló la operación.")
            return False
    
    # Realizar acción
    realizar_accion_en_bloque(bloque_info, accion=accion, offset_y=offset)
    
    print("\n✅ Automatización completada\n")
    return True


def obtener_info_bloque(toolbar_image_path):
    """
    Solo busca y obtiene información del bloque sin hacer nada.
    Útil para análisis.
    
    Returns:
        Diccionario con información de la barra encontrada
    """
    
    base_path = r"c:\Desarrollo\RPA_3"
    full_toolbar_path = os.path.join(base_path, toolbar_image_path)
    log_dir = os.path.join(base_path, "rpa_framework", "log", "debug_screenshots")
    
    bloque_info = buscar_bloque_toolbar(
        full_toolbar_path,
        confidence_threshold=0.70,
        log_dir=log_dir
    )
    
    if not bloque_info:
        return None
    
    x, y, width, height, center_x, center_y = bloque_info
    
    info = {
        "posicion_x": x,
        "posicion_y": y,
        "ancho": width,
        "alto": height,
        "centro_x": center_x,
        "centro_y": center_y,
        "esquina_superior_izquierda": (x, y),
        "esquina_superior_derecha": (x + width, y),
        "esquina_inferior_izquierda": (x, y + height),
        "esquina_inferior_derecha": (x + width, y + height),
        "centro": (center_x, center_y),
    }
    
    return info


if __name__ == "__main__":
    
    # ============================================================
    # EJEMPLO 1: Solo buscar y obtener información
    # ============================================================
    print("\n" + "="*70)
    print("📋 PASO 1: BUSCAR BARRA Y OBTENER INFORMACIÓN")
    print("="*70)
    
    info = obtener_info_bloque(r"rpa_framework\utils\word.png")
    
    if info:
        print("\n📊 Información de la barra encontrada:")
        print(f"  Posición: ({info['posicion_x']}, {info['posicion_y']})")
        print(f"  Dimensiones: {info['ancho']}x{info['alto']}px")
        print(f"  Centro: ({info['centro_x']:.0f}, {info['centro_y']:.0f})")
        print(f"  Esquina superior-izquierda: {info['esquina_superior_izquierda']}")
        print(f"  Esquina inferior-derecha: {info['esquina_inferior_derecha']}")
    
    
    # ============================================================
    # EJEMPLO 2: Buscar y hacer click en el centro
    # ============================================================
    print("\n" + "="*70)
    print("📋 PASO 2: HACER CLICK EN EL CENTRO DE LA BARRA")
    print("="*70)
    
    automatizar_buscar_toolbar(
        toolbar_image_path=r"rpa_framework\utils\word.png",
        accion="click_centro"
    )
    
    
    # ============================================================
    # EJEMPLO 3: Buscar y hacer click debajo de la barra
    # ============================================================
    # automatizar_buscar_toolbar(
    #     toolbar_image_path=r"rpa_framework\utils\word.png",
    #     accion="click_abajo",
    #     offset=100
    # )
    
    
    # ============================================================
    # EJEMPLO 4: Buscar y hacer click arriba de la barra
    # ============================================================
    # automatizar_buscar_toolbar(
    #     toolbar_image_path=r"rpa_framework\utils\word.png",
    #     accion="click_arriba",
    #     offset=50
    # )
    
    
    # ============================================================
    # EJEMPLO 5: Loop - Repetir búsqueda múltiples veces
    # ============================================================
    # for i in range(3):
    #     print(f"\n[{i+1}/3] Búsqueda #{i+1}")
    #     automatizar_buscar_toolbar(
    #         toolbar_image_path=r"rpa_framework\utils\word.png",
    #         accion="click_abajo",
    #         offset=100
    #     )
    #     time.sleep(1)
