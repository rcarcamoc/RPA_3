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

try:
    from utils.screen_utils import safe_screenshot
except ImportError:
    try:
        from rpa_framework.utils.screen_utils import safe_screenshot
    except ImportError:
        safe_screenshot = None


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


def buscar_y_click_guardar(imagenes_relativas=None, confidence_threshold=0.70):
    """
    Busca la imagen de referencia en pantalla y realiza el clic humanizado con offset.
    Soporta múltiples plantillas (tema oscuro y claro).
    """
    if imagenes_relativas is None:
        imagenes_relativas = [
            r"rpa_framework\utils\guardar_dark.png",  # Tema oscuro (actual)
            r"rpa_framework\utils\guardar_2.png"     # Tema claro (legacy)
        ]
    elif isinstance(imagenes_relativas, str):
        imagenes_relativas = [imagenes_relativas]

    base_path = r"c:\Desarrollo\RPA_3"

    # Captura de pantalla resiliente (safe_screenshot o fallback pyautogui)
    screen_cv = None
    if safe_screenshot:
        try:
            pil_img = safe_screenshot()
            if pil_img:
                screen_cv = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        except Exception as e_sct:
            print(f"⚠️ Aviso safe_screenshot: {e_sct}")

    if screen_cv is None:
        try:
            screen = pyautogui.screenshot()
            screen_np = np.array(screen)
            screen_cv = cv2.cvtColor(screen_np, cv2.COLOR_RGB2BGR)
        except Exception as e:
            print(f"❌ Error capturando pantalla: {e}")
            return False

    mejor_val = -1.0
    mejor_bloque = None
    mejor_tpl_nombre = "ninguna"
    mejor_target = None

    # Evaluar TODAS las plantillas y escalas antes de decidir (evita falsos positivos
    # tempranos en plantillas de otro tema, ej. guardar_dark sobre zonas oscuras).
    escalas = [1.0, 0.95, 1.05, 0.9, 1.1]
    h_scr, w_scr = screen_cv.shape[:2]

    for img_rel in imagenes_relativas:
        template_path = os.path.join(base_path, img_rel)
        if not os.path.exists(template_path):
            continue

        template = cv2.imread(template_path)
        if template is None:
            continue

        original_h, original_w = template.shape[:2]
        tpl_nombre = os.path.basename(img_rel)

        for scale in escalas:
            if scale == 1.0:
                tpl_scaled = template
            else:
                new_w = int(round(original_w * scale))
                new_h = int(round(original_h * scale))
                if new_w < 10 or new_h < 10 or new_w > w_scr or new_h > h_scr:
                    continue
                tpl_scaled = cv2.resize(template, (new_w, new_h), interpolation=cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC)

            sh, sw = tpl_scaled.shape[:2]
            if sw > w_scr or sh > h_scr:
                continue

            result = cv2.matchTemplate(screen_cv, tpl_scaled, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            x, y = max_loc

            center_x = x + sw / 2.0
            center_y = y + sh / 2.0
            target_x = center_x - (90.0 * scale)
            target_y = center_y

            if max_val > mejor_val:
                mejor_val = max_val
                mejor_bloque = (x, y, sw, sh, center_x, center_y)
                mejor_tpl_nombre = f"{tpl_nombre} (escala {scale:.2f})"
                mejor_target = (target_x, target_y)

            # Si encontramos coincidencia muy alta a escala 1.0, no hace falta seguir probando escalas
            if scale == 1.0 and max_val >= 0.85:
                break

    if mejor_val >= confidence_threshold and mejor_bloque is not None and mejor_target is not None:
        x, y, sw, sh, center_x, center_y = mejor_bloque
        target_x, target_y = mejor_target
        print(f"✅ Botón encontrado con '{mejor_tpl_nombre}' (Confianza: {mejor_val*100:.2f}%) en ({center_x:.0f}, {center_y:.0f}) -> Clic en ({target_x:.0f}, {target_y:.0f})")
        if vf:
            vf.highlight_region(x, y, sw, sh, color="#FFEB3B", duration=1.5)

        guardar_debug_screenshot(screen_cv, info=mejor_bloque, suffix="click_guardar", target_point=(target_x, target_y))
        humanized_click(target_x, target_y, hold_time=1.0)
        return True

    guardar_debug_screenshot(screen_cv, info=mejor_bloque, suffix="failed_not_found")
    print(f"❌ No se encontró el botón de guardar en pantalla (Mejor: '{mejor_tpl_nombre}' con {mejor_val*100:.2f}%, umbral={confidence_threshold*100:.0f}%)")
    return False


def main():
    print("🚀 Ejecutando clic en botón Guardar...")
    exito = buscar_y_click_guardar()
    return 0 if exito else 1


if __name__ == "__main__":
    sys.exit(main())
