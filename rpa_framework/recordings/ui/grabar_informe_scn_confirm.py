#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script simple y directo: GRABAR INFORME (Click en scn_confirm / guardar_2.png)
Basado en la búsqueda visual de pega en word.py.
"""

import sys
import time
import os
import random
import logging
from pathlib import Path
import pyautogui
import cv2
import numpy as np

# Asegurar encoding UTF-8 en Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Agregar raíz del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from utils.visual_feedback import VisualFeedback
    vf = VisualFeedback()
except ImportError:
    vf = None


def humanized_click(x, y, clicks=1, interval=0.1, hold_time=0.5):
    """
    Mueve el ratón a (x,y), hace una pausa (hover) y realiza el clic (sostenido o normal).
    """
    # 1. Destacar la zona ANTES de moverse (solo una vez por ejecución)
    if vf:
        vf.highlight_click(x, y, color="#FF0000", duration=0.8)

    # 2. Posicionamiento (movimiento)
    duration = random.uniform(0.5, 1.0)
    pyautogui.moveTo(x, y, duration=duration, tween=pyautogui.easeInOutQuad)
    
    # 3. Pausa crucial de posicionamiento (Estimular render de UI / Hover)
    time.sleep(0.5)
    
    # 4. Ejecución del clic sostenido o rápido, SIN volver a pasar (x,y)
    if hold_time > 0.0:
        pyautogui.mouseDown()
        time.sleep(hold_time)
        pyautogui.mouseUp()
    else:
        pyautogui.click(clicks=clicks, interval=interval)


# ── Carpeta de logs especifica para esta tarea ───────────────────
LOG_DIR = os.path.join(
    str(Path(__file__).parent.parent.parent),
    "log", "grabar_informe_scn_confirm"
)
os.makedirs(LOG_DIR, exist_ok=True)


def guardar_debug_screenshot(screenshot_cv, info=None, suffix="", target_point=None):
    """Guarda captura de debug con anotaciones, zona destacada y punto de clic exacto."""
    try:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"grabar_scn_{suffix}_{timestamp}.png"
        filepath = os.path.join(LOG_DIR, filename)

        viz = screenshot_cv.copy()

        # 1. Dibujar zona delimitadora si hay info
        if info:
            if isinstance(info, (tuple, list)):
                x, y, w, h, _, _ = info
            else:
                x, y, w, h = info.get('x', 0), info.get('y', 0), info.get('w', 0), info.get('h', 0)

            overlay = viz.copy()
            cv2.rectangle(overlay, (int(x) - 4, int(y) - 4), (int(x + w) + 4, int(y + h) + 4), (0, 200, 255), -1)
            cv2.addWeighted(overlay, 0.25, viz, 0.75, 0, viz)
            cv2.rectangle(viz, (int(x), int(y)), (int(x + w), int(y + h)), (255, 255, 0), 3)

        # 2. Dibujar punto de clic exacto (prioritario si se proporciona target_point)
        if target_point:
            tx, ty = target_point
            cv2.circle(viz, (int(tx), int(ty)), 12, (0, 0, 255), -1)
            cv2.circle(viz, (int(tx), int(ty)), 14, (255, 255, 255), 2)
            # Etiqueta de coordenadas
            coords_txt = f"CLICK: {int(tx)}, {int(ty)}"
            cv2.putText(viz, coords_txt, (int(tx) + 20, int(ty)), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4)
            cv2.putText(viz, coords_txt, (int(tx) + 20, int(ty)), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        elif info:
            if isinstance(info, (tuple, list)):
                cx, cy = info[4], info[5]
            else:
                cx, cy = info.get('center_x', 0), info.get('center_y', 0)
            cv2.circle(viz, (int(cx), int(cy)), 10, (0, 0, 255), -1)

        cv2.imwrite(filepath, viz)
    except Exception as e:
        pass


def buscar_y_click_guardar(imagen_relativa=r"rpa_framework\utils\guardar_2.png", confidence_threshold=0.70):
    """
    Busca la imagen de referencia en pantalla y realiza el clic humanizado con offset.
    """
    base_path = r"c:\Desarrollo\RPA_3"
    template_path = os.path.join(base_path, imagen_relativa)
    
    if not os.path.exists(template_path):
        print(f"❌ No se encuentra la plantilla: {template_path}")
        return False

    template = cv2.imread(template_path)
    if template is None:
        print(f"❌ Error al leer la imagen: {template_path}")
        return False

    original_h, original_w = template.shape[:2]

    # Captura de pantalla
    try:
        screen = pyautogui.screenshot()
        screen_np = np.array(screen)
        screen_cv = cv2.cvtColor(screen_np, cv2.COLOR_RGB2BGR)
    except Exception as e:
        print(f"❌ Error capturando pantalla: {e}")
        return False

    # Coincidencia de plantilla (Template Matching)
    result = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
    x, y = max_loc

    center_x = x + original_w / 2
    center_y = y + original_h / 2
    
    # Ajuste: 90px a la izquierda del centro
    target_x = center_x - 90
    target_y = center_y

    bloque_info = (x, y, original_w, original_h, center_x, center_y)

    # 1. Confianza directa
    if max_val >= confidence_threshold:
        print(f"✅ Botón encontrado (Confianza: {max_val*100:.2f}%) en ({center_x:.0f}, {center_y:.0f}) -> Clic en ({target_x:.0f}, {target_y:.0f})")
        if vf:
            vf.highlight_region(x, y, original_w, original_h, color="#FFEB3B", duration=1.5)
        
        guardar_debug_screenshot(screen_cv, info=bloque_info, suffix="click_guardar", target_point=(target_x, target_y))
        humanized_click(target_x, target_y, hold_time=1.0)
        return True

    # 2. Doble confirmación para umbrales medios
    elif max_val >= 0.20:
        h_scr, w_scr = screen_cv.shape[:2]
        crop = screen_cv[y:min(y + original_h, h_scr), x:min(x + original_w, w_scr)]
        crop_resized = cv2.resize(crop, (original_w, original_h), interpolation=cv2.INTER_LINEAR)
        
        diff = cv2.norm(crop_resized.astype(np.float32), template.astype(np.float32), cv2.NORM_L2)
        max_possible = np.sqrt(original_w * original_h * 3) * 255.0
        similitud = 1.0 - (diff / max_possible)

        if similitud >= 0.70:
            print(f"✅ Botón confirmado tras 2da pasada ({similitud*100:.2f}%) en ({center_x:.0f}, {center_y:.0f}) -> Clic en ({target_x:.0f}, {target_y:.0f})")
            if vf:
                vf.highlight_region(x, y, original_w, original_h, color="#FFEB3B", duration=1.5)
            
            guardar_debug_screenshot(screen_cv, info=bloque_info, suffix="click_guardar_confirm2", target_point=(target_x, target_y))
            humanized_click(target_x, target_y, hold_time=1.0)
            return True

    guardar_debug_screenshot(screen_cv, info=bloque_info, suffix="failed_not_found")
    print(f"❌ No se encontró el botón de guardar en pantalla (Max confianza: {max_val*100:.2f}%)")
    return False


def main():
    print("🚀 Ejecutando clic en botón Guardar...")
    exito = buscar_y_click_guardar()
    return 0 if exito else 1


if __name__ == "__main__":
    sys.exit(main())
