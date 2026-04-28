#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script RPA: Cierra el "Visor de documentos" y vuelve a Carestream.

Flujo:
  1. Captura pantalla completa.
  2. Busca el texto "Visor de documentos" mediante OCR (pytesseract directo).
     - Preprocesamiento especial: threshold adaptativo invertido + escalado x4
       para detectar texto claro sobre fondo oscuro (barra de título).
  3. Si lo encuentra, posiciona el cursor y hace clic sostenido.
  4. Envía la combinación Ctrl+F4.
  5. Selecciona (activa) la ventana de Carestream Radiology Client / Vue PACS.
  
  Si NO encuentra el texto, simplemente no hace nada.
"""

import sys
import os
import time
import logging
import re
import random
import pyautogui
import cv2
import numpy as np
from pathlib import Path
from difflib import SequenceMatcher

# ── Tesseract directo ────────────────────────────────────────────
import pytesseract

# ── pywinauto para activar ventana ───────────────────────────────
from pywinauto import Desktop
import pywinauto.findwindows as fw

# Agregar raíz del proyecto al path para importar utils
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# ── Visual Feedback ──────────────────────────────────────────────
try:
    from utils.visual_feedback import VisualFeedback
    vf = VisualFeedback()
except ImportError:
    vf = None

# ── Telegram ─────────────────────────────────────────────────────
try:
    from utils.telegram_manager import enviar_alerta_todos
except ImportError:
    def enviar_alerta_todos(msg): pass

# ── MySQL (opcional) ─────────────────────────────────────────────
try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ── Configuracion ────────────────────────────────────────────────
TEXTO_BUSCAR = "visor de documentos"
MAX_REINTENTOS_OCR = 3
HOLD_TIME = 0.5
FUZZY_THRESHOLD = 0.75  # Un poco mas estricto para evitar confundirse con el nombre del script (.py)

# Preprocesamiento OCR
OCR_SCALE = 2                   # Factor de escala para pantalla completa
OCR_ADAPTIVE_BLOCK = 15         # Tamano de bloque para threshold adaptativo
OCR_ADAPTIVE_C = 5              # Constante para threshold adaptativo

# Confianza minima para busqueda por imagen template
TEMPLATE_CONFIDENCE = 0.65

TITULOS_CARESTREAM = [
    "Carestream Radiology Client",
    "Carestream Vue PACS",
]

id_registro = os.environ.get('VAR_id_registro')

# ── Carpeta de logs especifica para esta tarea ───────────────────
LOG_DIR = os.path.join(
    str(Path(__file__).parent.parent.parent),
    "log", "visor_de_documentos"
)
os.makedirs(LOG_DIR, exist_ok=True)

# Ruta a la imagen template del visor (para busqueda visual fallback)
VISOR_TEMPLATE_PATH = os.path.join(
    str(Path(__file__).parent.parent.parent),
    "rpa_framework", "utils", "visor de documentos2.png"
)


def db_update(status='En Proceso', obs=None, node='cierra_visor_documentos'):
    """Actualiza estado en la BD."""
    if not id_registro or not HAS_MYSQL:
        return
    try:
        conn = mysql.connector.connect(
            host='localhost', user='root', password='', database='ris'
        )
        cursor = conn.cursor()
        if status == 'Error':
            query = "UPDATE registro_acciones SET estado = 'Error', observacion = %s, `update` = NOW() WHERE id = %s"
            cursor.execute(query, (obs, id_registro))
        else:
            query = "UPDATE registro_acciones SET estado = %s, ultimo_nodo = %s, `update` = NOW() WHERE id = %s"
            cursor.execute(query, (status, node, id_registro))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"[DB Error] {e}")


def capturar_pantalla():
    """Captura la pantalla completa y devuelve imagen BGR (OpenCV)."""
    screenshot = pyautogui.screenshot()
    screen_np = np.array(screenshot)
    screen_bgr = cv2.cvtColor(screen_np, cv2.COLOR_RGB2BGR)
    return screen_bgr


def similitud_fuzzy(a: str, b: str) -> float:
    """Calcula similitud entre dos strings (0.0 a 1.0)."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _ocr_extraer_lineas(image):
    """
    Ejecuta Tesseract sobre una imagen y agrupa las palabras detectadas por linea.
    Returns dict de lineas {line_key: [lista de words]}.
    """
    data = pytesseract.image_to_data(image, lang='spa', output_type=pytesseract.Output.DICT)
    lines = {}
    for i in range(len(data['text'])):
        text = data['text'][i].strip()
        if not text:
            continue
        line_key = (data['block_num'][i], data['par_num'][i], data['line_num'][i])
        if line_key not in lines:
            lines[line_key] = []
        lines[line_key].append({
            'text': text,
            'left': data['left'][i],
            'top': data['top'][i],
            'width': data['width'][i],
            'height': data['height'][i],
            'conf': int(data['conf'][i]),
        })
    return lines


def _buscar_frase_en_lineas(lines, texto_buscar, scale_factor):
    """
    Busca la frase objetivo en las lineas OCR usando matching exacto y fuzzy.
    Las coordenadas se dividen por scale_factor para volver al espacio original.
    Returns dict de coordenadas o None.
    """
    palabras_buscar = texto_buscar.lower().split()
    
    for line_key, words in lines.items():
        line_text = " ".join(w['text'] for w in words).lower()
        logger.debug(f"   Linea OCR: '{line_text}'")
        
        # Intento 1: Matching exacto (substring)
        if texto_buscar in line_text:
            return _extraer_coordenadas(words, palabras_buscar, scale_factor)
        
        # Intento 2: Matching fuzzy por ventana deslizante de palabras
        if len(words) >= len(palabras_buscar):
            for start_i in range(len(words) - len(palabras_buscar) + 1):
                window = words[start_i:start_i + len(palabras_buscar)]
                window_text = " ".join(w['text'] for w in window).lower()
                
                sim = similitud_fuzzy(texto_buscar, window_text)
                if sim >= FUZZY_THRESHOLD:
                    logger.info(f"   Match fuzzy: '{window_text}' (similitud={sim:.2f})")
                    return _extraer_coordenadas_directas(window, scale_factor)
    
    return None


def buscar_texto_en_pantalla(texto_buscar: str, screenshot_bgr):
    """
    Busca la frase 'texto_buscar' en la pantalla completa.
    
    Realiza dos pasadas OCR para cubrir ambos escenarios:
      - Pasada A: Escala de grises normal (texto oscuro sobre fondo claro)
      - Pasada B: Threshold adaptativo invertido (texto claro sobre fondo oscuro)
    
    Usa matching fuzzy para tolerar errores menores del OCR.
    
    Returns:
        dict con coordenadas si encuentra, None si no.
    """
    gray = cv2.cvtColor(screenshot_bgr, cv2.COLOR_BGR2GRAY)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    
    # ── Pasada A: Escala de grises normal (texto oscuro sobre claro) ──
    logger.info("   Pasada A: escala de grises normal...")
    scaled_gray = cv2.resize(gray, None, fx=OCR_SCALE, fy=OCR_SCALE, interpolation=cv2.INTER_CUBIC)
    
    lines_a = _ocr_extraer_lineas(scaled_gray)
    resultado = _buscar_frase_en_lineas(lines_a, texto_buscar, OCR_SCALE)
    if resultado:
        resultado['pasada'] = 'A (gris normal)'
        return resultado
    
    # ── Pasada B: Threshold adaptativo invertido (texto claro sobre oscuro) ──
    logger.info("   Pasada A sin resultados. Pasada B: threshold adaptativo invertido...")
    thresh = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        OCR_ADAPTIVE_BLOCK, OCR_ADAPTIVE_C
    )
    scaled_thresh = cv2.resize(thresh, None, fx=OCR_SCALE, fy=OCR_SCALE, interpolation=cv2.INTER_NEAREST)
    
    # Guardar imagen procesada para debug
    try:
        cv2.imwrite(os.path.join(LOG_DIR, f"visor_preprocessed_{timestamp}.png"), scaled_thresh)
    except:
        pass
    
    lines_b = _ocr_extraer_lineas(scaled_thresh)
    resultado = _buscar_frase_en_lineas(lines_b, texto_buscar, OCR_SCALE)
    if resultado:
        resultado['pasada'] = 'B (invertido)'
        return resultado
    
    # Log de diagnostico: mostrar que se detecto en ambas pasadas
    logger.info("   Texto no encontrado en ninguna pasada. Lineas detectadas (pasada B):")
    for line_key, words in lines_b.items():
        line_text = " ".join(w['text'] for w in words)
        if len(line_text) > 3:  # Solo lineas con contenido relevante
            logger.info(f"      '{line_text}'")
    
    return None


def _extraer_coordenadas(words, palabras_buscar, scale_factor):
    """Extrae coordenadas de las palabras que matchean."""
    start_idx = None
    for i in range(len(words)):
        match = True
        for j, pb in enumerate(palabras_buscar):
            if i + j >= len(words):
                match = False
                break
            word_text = words[i + j]['text'].lower()
            if pb not in word_text and similitud_fuzzy(pb, word_text) < FUZZY_THRESHOLD:
                match = False
                break
        if match:
            start_idx = i
            break
    
    if start_idx is not None:
        match_words = words[start_idx:start_idx + len(palabras_buscar)]
    else:
        match_words = words
    
    return _extraer_coordenadas_directas(match_words, scale_factor)


def _extraer_coordenadas_directas(match_words, scale_factor):
    """Calcula bounding box y centro, convirtiendo coords escaladas a coordenadas reales de pantalla."""
    x_min = min(w['left'] for w in match_words) // scale_factor
    y_min = min(w['top'] for w in match_words) // scale_factor
    x_max = max(w['left'] + w['width'] for w in match_words) // scale_factor
    y_max = max(w['top'] + w['height'] for w in match_words) // scale_factor
    
    w_total = x_max - x_min
    h_total = y_max - y_min
    center_x = x_min + w_total // 2
    center_y = y_min + h_total // 2
    
    texto_encontrado = ' '.join(w['text'] for w in match_words)
    
    logger.info(
        f"   Texto: '{texto_encontrado}' "
        f"en ({center_x}, {center_y}) tamano=({w_total}x{h_total})"
    )
    
    return {
        'x': x_min,
        'y': y_min,
        'w': w_total,
        'h': h_total,
        'center_x': center_x,
        'center_y': center_y,
        'text': texto_encontrado
    }


def guardar_debug_screenshot(screenshot_bgr, resultado=None, suffix=""):
    """Guarda captura de debug con anotaciones y zona destacada del print."""
    try:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"visor_doc_{suffix}_{timestamp}.png"
        filepath = os.path.join(LOG_DIR, filename)

        viz = screenshot_bgr.copy()

        if resultado:
            x = resultado['x']
            y = resultado['y']
            w = resultado['w']
            h = resultado['h']
            cx = resultado['center_x']
            cy = resultado['center_y']

            # Sombra semitransparente sobre la zona detectada
            overlay = viz.copy()
            cv2.rectangle(overlay, (x - 4, y - 4), (x + w + 4, y + h + 4), (0, 200, 255), -1)
            cv2.addWeighted(overlay, 0.25, viz, 0.75, 0, viz)

            # Rectangulo verde grueso (borde)
            cv2.rectangle(viz, (x, y), (x + w, y + h), (0, 230, 0), 3)

            # Circulo rojo en el centro (punto de clic)
            cv2.circle(viz, (cx, cy), 10, (0, 0, 255), -1)
            cv2.circle(viz, (cx, cy), 12, (255, 255, 255), 2)

            # Etiqueta con texto encontrado
            label = resultado.get('text', 'detectado')
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            lx = max(x, 0)
            ly = max(y - 10, th + 4)
            cv2.rectangle(viz, (lx, ly - th - 4), (lx + tw + 4, ly + 2), (0, 0, 0), -1)
            cv2.putText(viz, label, (lx + 2, ly - 2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        cv2.imwrite(filepath, viz)
        logger.info(f"   [LOG IMG] Screenshot guardado: {filepath}")
    except Exception as e:
        logger.debug(f"   Error guardando debug screenshot: {e}")


def buscar_por_imagen_template(screenshot_bgr):
    """
    Busca el visor de documentos usando template matching con la imagen de referencia.
    Retorna dict con coordenadas (misma estructura que buscar_texto_en_pantalla) o None.
    """
    template_path = VISOR_TEMPLATE_PATH
    if not os.path.exists(template_path):
        logger.warning(f"   Template no encontrado: {template_path}")
        return None

    template = cv2.imread(template_path)
    if template is None:
        logger.warning(f"   No se pudo leer imagen template: {template_path}")
        return None

    tmpl_h, tmpl_w = template.shape[:2]
    logger.info(f"   Buscando por imagen template ({tmpl_w}x{tmpl_h})...")

    try:
        result = cv2.matchTemplate(screenshot_bgr, template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
        x, y = max_loc

        logger.info(f"   Template matching: confianza={max_val:.3f} en ({x}, {y})")

        if max_val >= TEMPLATE_CONFIDENCE:
            cx = x + tmpl_w // 2
            cy = y + tmpl_h // 2
            logger.info(f"   Match encontrado por imagen: ({cx}, {cy}) confianza={max_val:.2f}")
            return {
                'x': x,
                'y': y,
                'w': tmpl_w,
                'h': tmpl_h,
                'center_x': cx,
                'center_y': cy,
                'text': 'visor de documentos (imagen)',
                'pasada': 'template_matching',
                'confianza': max_val
            }
        else:
            logger.warning(f"   Template matching: confianza insuficiente ({max_val:.3f} < {TEMPLATE_CONFIDENCE})")
            # Guardar imagen de mejor match fallido para diagnostico
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            viz_fail = screenshot_bgr.copy()
            cv2.rectangle(viz_fail, (x, y), (x + tmpl_w, y + tmpl_h), (0, 0, 255), 2)
            cv2.putText(viz_fail, f"best={max_val:.2f}", (x, max(y - 6, 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            cv2.imwrite(os.path.join(LOG_DIR, f"visor_tmpl_fail_{timestamp}.png"), viz_fail)
            return None
    except Exception as e:
        logger.error(f"   Error en template matching: {e}")
        return None


def humanized_click(x, y, hold_time=HOLD_TIME):
    """Mueve el raton, destaca la zona y hace clic sostenido."""
    # 1. Destacar zona (circulo rojo)
    if vf:
        vf.highlight_click(x, y, color="#FF0000", duration=0.8)
        time.sleep(0.3)

    # 2. Movimiento humanizado
    duration = random.uniform(0.4, 0.8)
    pyautogui.moveTo(x, y, duration=duration, tween=pyautogui.easeInOutQuad)
    logger.info(f"   -> Cursor posicionado en ({x}, {y})")

    # 3. Pausa de posicionamiento
    time.sleep(0.5)

    # 4. Clic sostenido
    if hold_time > 0.0:
        logger.info(f"   -> Clic sostenido ({hold_time}s)...")
        pyautogui.mouseDown()
        time.sleep(hold_time)
        pyautogui.mouseUp()
    else:
        pyautogui.click()

    logger.info(f"   -> Clic completado en ({x}, {y})")


def activar_ventana_carestream():
    """Busca y activa la ventana de Carestream."""
    logger.info("Buscando ventana Carestream...")

    for titulo in TITULOS_CARESTREAM:
        try:
            ventanas = fw.find_windows(
                title_re=re.compile(f".*{re.escape(titulo)}.*", re.I)
            )
            if ventanas:
                hwnd = ventanas[0]
                win = Desktop(backend="win32").window(handle=hwnd)
                titulo_real = win.window_text()
                logger.info(f"   Ventana encontrada: '{titulo_real}' (hwnd={hwnd})")

                win.set_focus()
                time.sleep(0.5)

                if vf:
                    vf.show_message("Carestream activado", duration=2.0)

                logger.info(f"   -> Ventana '{titulo_real}' activada.")
                return True

        except Exception as e:
            logger.warning(f"   Error buscando '{titulo}': {e}")
            continue

    logger.warning("No se encontro ninguna ventana de Carestream abierta.")
    return False


def execute():
    """Punto de entrada principal del script."""
    logger.info("=" * 60)
    logger.info("RPA: Cierra Visor de Documentos -> Vuelve a Carestream")
    logger.info("=" * 60)

    db_update(status='En Proceso')

    try:
        # ── Paso 1: Capturar pantalla y buscar texto por OCR ─────
        logger.info(f"[1/3] Buscando texto '{TEXTO_BUSCAR}' en pantalla completa...")
        
        resultado = None
        screenshot = None

        for intento in range(1, MAX_REINTENTOS_OCR + 1):
            logger.info(f"   Intento OCR {intento}/{MAX_REINTENTOS_OCR}...")

            screenshot = capturar_pantalla()
            resultado = buscar_texto_en_pantalla(TEXTO_BUSCAR, screenshot)

            if resultado:
                guardar_debug_screenshot(screenshot, resultado, suffix="ocr_found")
                break

            logger.warning(f"   Texto no encontrado por OCR (intento {intento})")
            if intento < MAX_REINTENTOS_OCR:
                time.sleep(1.0)

        # ── Fallback: busqueda por imagen template si OCR fallo ──
        if not resultado:
            logger.info("   OCR sin resultados. Intentando busqueda por imagen template...")
            screenshot = capturar_pantalla()
            resultado = buscar_por_imagen_template(screenshot)
            if resultado:
                logger.info("   Visor encontrado por template matching.")
                guardar_debug_screenshot(screenshot, resultado, suffix="tmpl_found")
            else:
                logger.info("   Busqueda por imagen tampoco encontro el visor.")
                guardar_debug_screenshot(screenshot, suffix="not_found")

        if not resultado:
            logger.info(f"Texto '{TEXTO_BUSCAR}' no encontrado por OCR ni por imagen. Nada que hacer.")
            return {
                'status': 'skipped',
                'reason': 'Texto no encontrado en pantalla (OCR ni imagen)'
            }

        # ── Paso 2: Feedback visual + Clic sostenido ─────────────
        click_x = resultado['center_x']
        click_y = resultado['center_y']
        
        logger.info(f"[2/3] Clic sostenido en ({click_x}, {click_y})...")
        
        # Resaltar region detectada (rectangulo amarillo)
        if vf:
            vf.highlight_region(
                resultado['x'], resultado['y'],
                resultado['w'], resultado['h'],
                color="#FFEB3B", duration=1.5
            )
            time.sleep(0.5)
        
        humanized_click(click_x, click_y, hold_time=HOLD_TIME)
        time.sleep(1.0) # Aumentamos espera para asegurar foco

        # ── Paso 3: Enviar Alt + F4 ──────────────────────────────
        logger.info("[2/3] Enviando Alt + F4...")
        # hotkey suele ser más robusto para combinaciones de sistema
        pyautogui.hotkey('alt', 'f4', interval=0.1)
        
        logger.info("   -> Alt + F4 enviado.")
        time.sleep(1.5) # Espera a que la ventana se cierre realmente

        # ── Paso 4: Activar ventana Carestream ───────────────────
        logger.info("[3/3] Activando ventana Carestream...")
        carestream_ok = activar_ventana_carestream()

        if not carestream_ok:
            logger.warning("No se pudo activar Carestream. Puede que no este abierto.")

        # ── Exito ────────────────────────────────────────────────
        logger.info("=" * 60)
        logger.info("Visor cerrado y Carestream activado exitosamente.")
        logger.info("=" * 60)

        db_update(status='En Proceso')

        return {
            'status': 'success',
            'text_found': resultado.get('text', TEXTO_BUSCAR),
            'click_position': {'x': click_x, 'y': click_y},
            'carestream_activated': carestream_ok
        }

    except SystemExit:
        sys.exit(1)
    except Exception as e:
        error_msg = f"Excepcion critica: {str(e)}"
        logger.error(f"ERROR: {error_msg}")
        db_update(status='Error', obs=error_msg)
        enviar_alerta_todos(
            f"<b>Error Critico: cierra_visor_documentos</b>\n{error_msg}"
        )
        sys.exit(1)


# Alias para compatibilidad con el framework
main = execute

if __name__ == '__main__':
    print('Ejecutando cierra_visor_documentos...')
    result = execute()
    print(f'Resultado: {result}')
