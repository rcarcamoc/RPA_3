"""
Script integral para cerrar el 'Asistente de audio' en Windows:
1. Busca la ventana principal del Asistente y hace clic en 'Cancelar'.
2. Espera 1 a 2 segundos a que aparezca la ventana de confirmación ('¿Desea cancelar el Asistente de audio?').
3. Hace clic en el botón 'Sí' para confirmar y cerrar definitivamente.

Soporta dos motores:
- PaddleOCR GPU (a través del microservicio localhost:8095 de rpa_framework).
- Visión Artificial OpenCV multi-escala (instantáneo y sin dependencias de servicios).
"""

import os
import sys
import time
import argparse
import ctypes
import numpy as np
import cv2
import pyautogui
import mss

# Habilitar DPI Awareness en Windows para coordenadas exactas del mouse
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per monitor DPI aware
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# Rutas y configuración de paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

ASSETS_DIR = os.path.join(BASE_DIR, "assets")

# Plantillas de la ventana principal
IMG_DIALOGO = os.path.join(ASSETS_DIR, "asistente_audio.png")
IMG_HEADER = os.path.join(ASSETS_DIR, "asistente_audio_header.png")
IMG_BOTON_CANCELAR = os.path.join(ASSETS_DIR, "boton_cancelar.png")

# Plantillas de la ventana de confirmación ('¿Desea cancelar...? -> Sí')
IMG_CONFIRMACION = os.path.join(ASSETS_DIR, "confirmacion_cancelar.png")
IMG_BOTON_SI = os.path.join(ASSETS_DIR, "boton_si.png")

# Intentar importar el cliente de PaddleOCR GPU del proyecto
try:
    from rpa_framework.ocr.paddle_gpu_client import PaddleGPUClient
    PADDLE_DISPONIBLE = True
except Exception:
    PADDLE_DISPONIBLE = False


def capturar_pantalla(ruta_imagen=None):
    """
    Captura la pantalla completa usando mss (rápido y eficiente) o carga una imagen de prueba.
    Retorna (imagen_BGR, offset_x, offset_y).
    """
    if ruta_imagen and os.path.exists(ruta_imagen):
        img = cv2.imread(ruta_imagen)
        return img, 0, 0

    with mss.mss() as sct:
        mon = sct.monitors[0]
        screenshot = sct.grab(mon)
        img = np.array(screenshot)
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR), mon["left"], mon["top"]


def buscar_plantilla_multiescala(img_pantalla, img_plantilla, umbral=0.75, escalas=None):
    """
    Busca la plantilla en la pantalla probando múltiples escalas (para soportar DPI del 100%, 125%, 150%).
    Retorna (max_val, (x, y, w, h)) si supera el umbral, o None.
    """
    if escalas is None:
        escalas = [1.0, 1.25, 1.5, 0.9, 0.8, 1.1]

    h_tpl, w_tpl = img_plantilla.shape[:2]
    h_scr, w_scr = img_pantalla.shape[:2]

    mejor_val = -1
    mejor_box = None

    for escala in escalas:
        nuevo_w = int(w_tpl * escala)
        nuevo_h = int(h_tpl * escala)

        if nuevo_w > w_scr or nuevo_h > h_scr or nuevo_w < 10 or nuevo_h < 10:
            continue

        tpl_redimensionada = cv2.resize(img_plantilla, (nuevo_w, nuevo_h), interpolation=cv2.INTER_LINEAR)
        res = cv2.matchTemplate(img_pantalla, tpl_redimensionada, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

        if max_val > mejor_val:
            mejor_val = max_val
            mejor_box = (max_loc[0], max_loc[1], nuevo_w, nuevo_h)

        if mejor_val >= 0.95:
            break

    if mejor_val >= umbral:
        return mejor_val, mejor_box
    return mejor_val, None


# =========================================================================
# PASO 1: DETECCIÓN Y CLIC EN 'CANCELAR' (VENTANA PRINCIPAL)
# =========================================================================

def buscar_cancelar_paddle(pantalla, offset_x=0, offset_y=0):
    """Detecta la ventana principal y botón Cancelar usando PaddleOCR."""
    if not PADDLE_DISPONIBLE:
        return None, None
    try:
        client = PaddleGPUClient()
        detecciones = client.extract_text(pantalla)
        if not detecciones:
            return None, None

        hay_asistente = False
        y_dialogo_ref = None

        for item in detecciones:
            txt = item.get("text", "").lower()
            if "asistente de audio" in txt or "bienvenido al asistente" in txt:
                hay_asistente = True
                y_dialogo_ref = item.get("center", {}).get("y", 0)
                print(f"[Paso 1 - PaddleOCR] Ventana detectada: '{item['text']}' ({item.get('confidence', 0):.2f})")
                break

        if not hay_asistente:
            return None, None

        for item in detecciones:
            txt = item.get("text", "").strip().lower()
            if txt == "cancelar":
                c = item.get("center", {})
                cx, cy = c.get("x", 0), c.get("y", 0)
                if y_dialogo_ref and cy > y_dialogo_ref and (cy - y_dialogo_ref) < 400:
                    print(f"[Paso 1 - PaddleOCR] Botón 'Cancelar' en ({cx}, {cy})")
                    return int(offset_x + cx), int(offset_y + cy)

    except Exception as e:
        print(f"[Paso 1 - WARN] Error en PaddleOCR: {e}")
    return None, None


def buscar_cancelar_cv(pantalla, offset_x=0, offset_y=0, umbral=0.75):
    """Detecta la ventana principal y botón Cancelar usando OpenCV multi-escala."""
    tpl_dialogo = cv2.imread(IMG_DIALOGO) if os.path.exists(IMG_DIALOGO) else None
    tpl_boton = cv2.imread(IMG_BOTON_CANCELAR) if os.path.exists(IMG_BOTON_CANCELAR) else None

    if tpl_dialogo is not None:
        val, box = buscar_plantilla_multiescala(pantalla, tpl_dialogo, umbral=umbral)
        if box:
            x, y, w, h = box
            print(f"[Paso 1 - OpenCV] Ventana principal detectada ({val*100:.1f}%) en ({x}, {y}, {w}x{h})")

            # Buscar botón dentro del cuadrante inferior derecho de la ventana
            if tpl_boton is not None:
                roi_y1 = int(y + h * 0.8)
                roi_y2 = y + h
                roi_x1 = int(x + w * 0.5)
                roi_x2 = x + w
                roi = pantalla[roi_y1:roi_y2, roi_x1:roi_x2]

                val_btn, box_btn = buscar_plantilla_multiescala(roi, tpl_boton, umbral=0.70)
                if box_btn:
                    bx, by, bw, bh = box_btn
                    click_x = offset_x + roi_x1 + bx + bw // 2
                    click_y = offset_y + roi_y1 + by + bh // 2
                    return click_x, click_y

            # Si no, usar coordenadas proporcionales estándar (x=72.6%, y=93.5%)
            click_x = int(offset_x + x + w * 0.7257)
            click_y = int(offset_y + y + h * 0.9345)
            return click_x, click_y

    return None, None


def hacer_clic_cancelar(pantalla, offset_x=0, offset_y=0, metodo="auto", umbral=0.75, dry_run=False):
    """Ejecuta la búsqueda y clic en Cancelar según el método seleccionado."""
    click_x, click_y = None, None

    if metodo in ("ocr", "auto") and PADDLE_DISPONIBLE:
        click_x, click_y = buscar_cancelar_paddle(pantalla, offset_x, offset_y)

    if click_x is None and metodo in ("cv", "auto"):
        click_x, click_y = buscar_cancelar_cv(pantalla, offset_x, offset_y, umbral=umbral)

    if click_x is not None and click_y is not None:
        if dry_run:
            print(f"[DRY-RUN] Localizado botón 'Cancelar' en ({click_x}, {click_y})")
            return True
        print(f"[ACCIÓN] Clic en 'Cancelar': ({click_x}, {click_y})")
        pyautogui.moveTo(click_x, click_y, duration=0.2)
        pyautogui.click(click_x, click_y)
        return True

    return False


# =========================================================================
# PASO 2: DETECCIÓN Y CLIC EN 'SÍ' (VENTANA DE CONFIRMACIÓN)
# =========================================================================

def buscar_si_paddle(pantalla, offset_x=0, offset_y=0):
    """Detecta el cuadro de confirmación y el botón 'Sí' con PaddleOCR."""
    if not PADDLE_DISPONIBLE:
        return None, None
    try:
        client = PaddleGPUClient()
        detecciones = client.extract_text(pantalla)
        if not detecciones:
            return None, None

        hay_confirmacion = False
        y_ref = None

        for item in detecciones:
            txt = item.get("text", "").lower()
            if any(k in txt for k in ["desea cancelar", "configuraci", "asistente de audio"]):
                hay_confirmacion = True
                y_ref = item.get("center", {}).get("y", 0)

        if not hay_confirmacion:
            return None, None

        # Buscar el botón 'Sí' o 'si'
        for item in detecciones:
            txt = item.get("text", "").strip().lower()
            if txt in ("sí", "si"):
                c = item.get("center", {})
                cx, cy = c.get("x", 0), c.get("y", 0)
                if y_ref is None or cy >= y_ref:
                    print(f"[Paso 2 - PaddleOCR] Botón 'Sí' detectado en ({cx}, {cy}) (confianza: {item.get('confidence', 0):.2f})")
                    return int(offset_x + cx), int(offset_y + cy)

    except Exception as e:
        print(f"[Paso 2 - WARN] Error en PaddleOCR: {e}")
    return None, None


def buscar_si_cv(pantalla, offset_x=0, offset_y=0, umbral=0.75):
    """Detecta el cuadro de confirmación y el botón 'Sí' usando OpenCV."""
    tpl_conf = cv2.imread(IMG_CONFIRMACION) if os.path.exists(IMG_CONFIRMACION) else None
    tpl_si = cv2.imread(IMG_BOTON_SI) if os.path.exists(IMG_BOTON_SI) else None

    # Si encontramos la ventana de confirmación completa
    if tpl_conf is not None:
        val, box = buscar_plantilla_multiescala(pantalla, tpl_conf, umbral=umbral)
        if box:
            x, y, w, h = box
            print(f"[Paso 2 - OpenCV] Ventana de confirmación detectada ({val*100:.1f}%) en ({x}, {y}, {w}x{h})")

            # Buscar botón 'Sí' dentro del cuadro
            if tpl_si is not None:
                roi = pantalla[int(y + h * 0.6): y + h, int(x + w * 0.4): int(x + w * 0.85)]
                val_btn, box_btn = buscar_plantilla_multiescala(roi, tpl_si, umbral=0.70)
                if box_btn:
                    bx, by, bw, bh = box_btn
                    click_x = offset_x + int(x + w * 0.4) + bx + bw // 2
                    click_y = offset_y + int(y + h * 0.6) + by + bh // 2
                    return click_x, click_y

            # Posición proporcional estándar del botón 'Sí' en este diálogo (x=66.8%, y=87.8%)
            click_x = int(offset_x + x + w * 0.6677)
            click_y = int(offset_y + y + h * 0.8783)
            return click_x, click_y

    # Si no se detectó la ventana completa, buscar el botón 'Sí'
    if tpl_si is not None:
        val, box = buscar_plantilla_multiescala(pantalla, tpl_si, umbral=0.82)
        if box:
            x, y, w, h = box
            click_x = offset_x + x + w // 2
            click_y = offset_y + y + h // 2
            print(f"[Paso 2 - OpenCV] Botón 'Sí' encontrado directamente en ({click_x}, {click_y})")
            return click_x, click_y

    return None, None


def hacer_clic_si(pantalla, offset_x=0, offset_y=0, metodo="auto", umbral=0.75, dry_run=False):
    """Ejecuta la búsqueda y clic en 'Sí'."""
    click_x, click_y = None, None

    if metodo in ("ocr", "auto") and PADDLE_DISPONIBLE:
        click_x, click_y = buscar_si_paddle(pantalla, offset_x, offset_y)

    if click_x is None and metodo in ("cv", "auto"):
        click_x, click_y = buscar_si_cv(pantalla, offset_x, offset_y, umbral=umbral)

    if click_x is not None and click_y is not None:
        if dry_run:
            print(f"[DRY-RUN] Localizado botón 'Sí' en ({click_x}, {click_y})")
            return True
        print(f"[ACCIÓN] Clic en 'Sí': ({click_x}, {click_y})")
        pyautogui.moveTo(click_x, click_y, duration=0.2)
        pyautogui.click(click_x, click_y)
        return True

    return False


# =========================================================================
# FLUJO COMPLETO EN CADENA (CANCELAR -> ESPERA 1-2s -> SÍ)
# =========================================================================

def resolver_asistente_audio(espera_segundos=1.5, metodo="auto", umbral=0.75, dry_run=False, timeout_confirmacion=5.0):
    """
    Resuelve el flujo completo:
    1. Si está el diálogo principal: Clic en 'Cancelar'.
    2. Espera 1 a 2 segundos a que aparezca la confirmación.
    3. Clic en 'Sí'.
    Si el diálogo de confirmación ya estaba abierto previamente, hace clic en 'Sí' directamente.
    """
    pantalla, off_x, off_y = capturar_pantalla()

    # Primero verificar si por casualidad ya está en pantalla el diálogo de confirmación ('Sí / No')
    if hacer_clic_si(pantalla, off_x, off_y, metodo=metodo, umbral=umbral, dry_run=dry_run):
        print("[ÉXITO] Ventana de confirmación resuelta directamente con clic en 'Sí'.")
        return True

    # Paso 1: Buscar ventana principal y dar clic en 'Cancelar'
    cancelar_exito = hacer_clic_cancelar(pantalla, off_x, off_y, metodo=metodo, umbral=umbral, dry_run=dry_run)
    if not cancelar_exito:
        return False

    # Paso 2: Espera de 1 a 2 segundos indicada por el usuario
    print(f"[INFO] Clic en 'Cancelar' ejecutado. Esperando {espera_segundos}s a que aparezca la ventana de confirmación...")
    time.sleep(espera_segundos)

    # Paso 3: Esperar y buscar el botón 'Sí' en la confirmación (con reintentos hasta timeout)
    tiempo_inicio_conf = time.time()
    while time.time() - tiempo_inicio_conf <= timeout_confirmacion:
        pantalla_conf, off_x2, off_y2 = capturar_pantalla()
        if hacer_clic_si(pantalla_conf, off_x2, off_y2, metodo=metodo, umbral=umbral, dry_run=dry_run):
            print("[ÉXITO] Proceso completado: Cancelado y confirmado con 'Sí'.")
            return True
        time.sleep(0.5)

    print("[WARN] Se hizo clic en 'Cancelar', pero no se detectó la ventana de confirmación dentro del tiempo esperado.")
    return True


def ejecutar(timeout=10.0, intervalo=0.8, espera_confirmacion=1.5, bucle=False, umbral=0.75, metodo="auto", dry_run=False):
    """
    Bucle principal de ejecución para uso directo o vigía continuo.
    """
    print("=" * 65)
    print(" Asistente de Audio -> Flujo Completo: Cancelar + Espera + 'Sí'")
    print("=" * 65)
    print(f"Motor: {metodo.upper()} (PaddleOCR: {'Activo' if PADDLE_DISPONIBLE else 'No disponible'}, OpenCV: Activo)")
    print(f"Modo: {'Bucle continuo (Daemon)' if bucle else f'Espera con timeout de {timeout}s'}")
    print(f"Espera entre ventanas: {espera_confirmacion}s")
    print(f"Umbral de coincidencia: {umbral*100:.0f}%")
    print("Presiona Ctrl + C para detener.\n")

    tiempo_inicio = time.time()

    try:
        while True:
            exito = resolver_asistente_audio(
                espera_segundos=espera_confirmacion,
                metodo=metodo,
                umbral=umbral,
                dry_run=dry_run
            )

            if exito:
                if not bucle:
                    print("\n Flujo finalizado con éxito.")
                    return True
                else:
                    print("[INFO] Asistente cerrado. Esperando siguientes apariciones...")
                    time.sleep(2.0)
                    continue

            if not bucle:
                if timeout > 0 and (time.time() - tiempo_inicio) >= timeout:
                    print(f"\n[INFO] Timeout alcanzado ({timeout}s). No se encontró ninguna ventana del Asistente.")
                    return False

            time.sleep(intervalo)

    except KeyboardInterrupt:
        print("\n[INFO] Ejecución detenida por el usuario.")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cierra el 'Asistente de audio' haciendo clic en Cancelar y luego en 'Sí'.")
    parser.add_argument("--timeout", type=float, default=10.0, help="Segundos de espera a que aparezca la ventana inicial (defecto: 10s).")
    parser.add_argument("--wait", type=float, default=1.5, help="Segundos de espera tras pulsar Cancelar antes de buscar 'Sí' (defecto: 1.5s).")
    parser.add_argument("--interval", type=float, default=0.8, help="Intervalo entre chequeos de la ventana inicial (defecto: 0.8s).")
    parser.add_argument("--loop", action="store_true", help="Ejecutar en bucle continuo de supervisión en segundo plano.")
    parser.add_argument("--confidence", type=float, default=0.75, help="Umbral de coincidencia visual (0.0 a 1.0, defecto: 0.75).")
    parser.add_argument("--method", choices=["auto", "ocr", "cv"], default="auto", help="Motor: 'ocr' (PaddleOCR GPU), 'cv' (OpenCV), 'auto' (ambos).")
    parser.add_argument("--dry-run", action="store_true", help="Simular sin hacer clics reales.")

    args = parser.parse_args()
    ejecutar(
        timeout=args.timeout,
        intervalo=args.interval,
        espera_confirmacion=args.wait,
        bucle=args.loop,
        umbral=args.confidence,
        metodo=args.method,
        dry_run=args.dry_run
    )
