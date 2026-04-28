#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script: busqueda_por_examen_hecho.py
Descripción: Script de prueba que busca "Examen Hecho" (y variantes OCR) en TODA
la pantalla usando Tesseract con bounding boxes, luego extrae una franja de 20px
de alto centrada en cada ocurrencia encontrada y aplica el proceso completo de
validación: fecha, diagnóstico fuzzy y LLM (igual que busqueda_triple_text_only.py).

Estrategia:
  1. Captura pantalla completa.
  2. Tesseract image_to_data → encontrar palabras "Hecho", "Examen", "Stat", "Realizado"
     que aparezcan en posiciones Y consecutivas (misma fila lógica).
  3. Por cada fila candidata a "Examen Hecho":
     - Extrae franja de 20px de alto centrada en esa Y.
     - Re-ejecuta OCR completo con preprocesamiento 3X en esa franja.
     - Verifica fecha + diagnóstico (fuzzy → LLM).
  4. Si confirma → click derecho + Ctrl+D.

Ubicación: rpa_framework/recordings/ocr/busqueda_por_examen_hecho.py
"""

import sys
import logging
import json
import cv2
import pyautogui
import numpy as np
import requests
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from difflib import SequenceMatcher
import time
import os
from dotenv import load_dotenv

load_dotenv()

try:
    import pytesseract
    from pytesseract import Output
except ImportError:
    print("Error: pytesseract no está instalado.")
    sys.exit(1)

try:
    from rapidfuzz import fuzz
except ImportError:
    print("Error: rapidfuzz no está instalado.")
    sys.exit(1)

try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.logging_setup import setup_logging
from ocr.engine import OCREngine
from PIL import Image
from utils.telegram_manager import enviar_alerta_todos
from utils.llm_config import OPENROUTER_BASE_URL, LLM_MODELS, LLM_DEFAULT_TEMPERATURE, LLM_DEFAULT_MAX_TOKENS, LLM_DEFAULT_TIMEOUT

try:
    from recordings.ocr.utilidades.preproceso_ocr import preprocess_high_fidelity, normalize_coordinates
    HAS_PREPROCESS_UTILS = True
except ImportError:
    HAS_PREPROCESS_UTILS = False

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    logger.error("OPENROUTER_API_KEY no está configurada en el archivo .env")
    sys.exit(1)

MODEL_ID = LLM_MODELS[0]

time.sleep(2)

# ─── Variantes OCR conocidas de "Examen Hecho" ────────────────────────────────
# El preprocesamiento binariza las filas resaltadas (fondo blanco), el OCR
# puede leer distintas versiones. Se listan todas las variantes conocidas.
ESTADO_HECHO_VARIANTS = [
    "Hecho",
    "Examen Hecho",
    "Examen Hecho.",
    "Examen-Hecho",
    "Examen_Hecho",
    "ExamenHecho",
    "Hecho",
    "xamen",     # a veces detecta sólo la primera palabra
]

# Palabras clave individuales —  una sola que aparezca en la fila puntúa
KEYWORD_HECHO = ["hecho", "Examen"]


class BusquedaPorExamenHecho:
    def __init__(self):
        self.ocr_engine = OCREngine(
            engine='tesseract',
            language='spa',
            use_gpu=False,
            confidence_threshold=0.05,
            preprocess=False,
            custom_config='--psm 3'
        )
        # Captura pantalla completa
        self.region = None   # None = pantalla completa
        self.ROW_HEIGHT = 20          # Altura de franja exacta por fila (px)
        self.ROW_TOLERANCE = 15       # Tolerancia vertical para agrupar palabras
        self.OFFSET_Y = 180

        try:
            from utils.visual_feedback import VisualFeedback
            self.vf = VisualFeedback()
        except Exception as e:
            logger.warning(f"VisualFeedback no disponible: {e}")
            self.vf = None

    # ── DB helpers (idénticos a busqueda_triple_text_only) ────────────────────

    def update_db_error(self, error_message):
        if not HAS_MYSQL:
            return
        try:
            conn = mysql.connector.connect(host='localhost', user='root',
                                           password='', database='ris')
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE ris.registro_acciones
                SET estado = 'Error'
                WHERE estado = 'En Proceso'
                LIMIT 1;
            """)
            conn.commit(); conn.close()
            logger.info(f"Estado actualizado a 'Error': {error_message}")
        except Exception as e:
            logger.error(f"Error actualizando BBDD error: {e}")

    def update_db_coordinate(self, coordinate_str):
        if not HAS_MYSQL:
            return
        try:
            conn = mysql.connector.connect(host='localhost', user='root',
                                           password='', database='ris')
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE ris.registro_acciones
                SET coordenada = %s
                WHERE estado = 'En Proceso'
                LIMIT 1;
            """, (coordinate_str,))
            conn.commit(); conn.close()
            logger.info(f"Coordenada '{coordinate_str}' actualizada en BBDD.")
        except Exception as e:
            logger.error(f"Error actualizando BBDD coordenada: {e}")

    def buscar_sinonimo(self, examen: str, ocr_text: str) -> str:
        if not HAS_MYSQL:
            return ''
        try:
            conn = mysql.connector.connect(host='localhost', user='root',
                                           password='', database='ris')
            cursor = conn.cursor()
            cursor.execute("""
                SELECT Sugerencia FROM ris.sinonimos
                WHERE examen = %s
                   OR Sugerencia = %s
                   OR (OCR   != '' AND INSTR(%s, OCR)   > 0)
                   OR (examen != '' AND INSTR(%s, examen) > 0)
                LIMIT 1
            """, (examen, examen, ocr_text or '', examen or ''))
            row = cursor.fetchone(); conn.close()
            if row and row[0]:
                logger.info(f"✅ Sinónimo BD: '{row[0]}' para '{examen}'")
                return row[0]
            return ''
        except Exception as e:
            logger.warning(f"No se pudo consultar sinonimos: {e}")
            return ''

    def guardar_sinonimo(self, examen: str, ocr_text: str, sugerencia: str) -> None:
        if not HAS_MYSQL or not sugerencia:
            return
        try:
            conn = mysql.connector.connect(host='localhost', user='root',
                                           password='', database='ris')
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO ris.sinonimos (examen, OCR, Sugerencia)
                VALUES (%s, %s, %s)
            """, (examen[:100], (ocr_text or '')[:100], sugerencia[:100]))
            conn.commit(); conn.close()
            logger.info(f"💾 Sinónimo guardado: '{examen}' → '{sugerencia}'")
        except Exception as e:
            logger.error(f"Error guardando sinónimo: {e}")

    def get_db_targets(self):
        if not HAS_MYSQL:
            logger.error("No hay driver de MySQL.")
            return None, None
        try:
            conn = mysql.connector.connect(host='localhost', user='root',
                                           password='', database='ris')
            cursor = conn.cursor()
            cursor.execute("""
                SELECT SUBSTRING_INDEX(diagnostico, '\\n', 1) AS examen,
                       date(fecha_agendada) as fecha
                FROM ris.registro_acciones
                WHERE estado = 'En Proceso'
                LIMIT 1;
            """)
            result = cursor.fetchone(); conn.close()
            if result:
                logger.info(f"Target DB → Diagnóstico: '{result[0]}', Fecha: '{result[1]}'")
                return result[0], result[1]
            logger.warning("No hay registros 'En Proceso' en BBDD.")
            return None, None
        except Exception as e:
            logger.error(f"Error consultando BBDD: {e}")
            return None, None

    # ── Utilidades texto ──────────────────────────────────────────────────────

    def normalize_text(self, text):
        text = text.lower()
        text = ''.join(c for c in unicodedata.normalize('NFD', text)
                       if unicodedata.category(c) != 'Mn')
        text = re.sub(r'[^a-z0-9\-]', ' ', text)
        text = ' '.join(text.split())
        return text

    # ── LLM ──────────────────────────────────────────────────────────────────

    def call_llm_text_verification(self, ocr_text, target_diag):
        models = LLM_MODELS
        prompt = f"""
Eres un experto clínico en interpretación de terminología radiológica y exámenes de imagen,
especializado en detectar equivalencias incluso con errores de OCR.

Tu rol es determinar si el texto "ENCONTRADO" describe semánticamente el examen "BUSCADO",
siendo extremadamente tolerante a errores tipográficos clásicos del OCR.

BUSCADO: "{target_diag}"
ENCONTRADO (Línea completa OCR): "{ocr_text}"

## REGLAS DE ORO
- RESONANCIA MAGNÉTICA ≈ RM ≈ RMNC ≈ RIM ≈ RNM
- TOMOGRAFÍA COMPUTADA ≈ TC ≈ TAC ≈ CT
- ULTRASONIDO ≈ ECOTOMOGRAFÍA ≈ ECO ≈ US
- RADIOGRAFÍA ≈ RX ≈ Rayos
- "RIM" casi siempre es "RM"; "Ecotomografña" es "Ecotomografía"

RESPONDE SOLO EN FORMATO JSON:
{{
  "es_match": true o false,
  "razonamiento": "Explicación breve",
  "confianza": 0-1
}}
"""
        if self.vf:
            self.vf.show_persistent_message("PROCESANDO OpenRouter...", "llm",
                                            bg_color="#FFEB3B", fg_color="#000000")
        try:
            for current_model in models:
                logger.info(f"🤖 Modelo: {current_model} | TARGET: '{target_diag}' | OCR: '{ocr_text}'")
                try:
                    response = requests.post(
                        f"{OPENROUTER_BASE_URL}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                            "Content-Type": "application/json",
                            "HTTP-Referer": "https://rpa-framework.local"
                        },
                        json={
                            "model": current_model,
                            "messages": [{"role": "user", "content": prompt}],
                            "temperature": LLM_DEFAULT_TEMPERATURE,
                            "max_tokens": LLM_DEFAULT_MAX_TOKENS,
                        },
                        timeout=LLM_DEFAULT_TIMEOUT
                    )
                    if response.status_code == 429:
                        logger.warning(f"429 en {current_model}. Siguiente...")
                        continue
                    response.raise_for_status()
                    content = response.json()['choices'][0]['message'].get('content', '')
                    match = re.search(r'\{.*\}', content, re.DOTALL)
                    if match:
                        try:
                            data = json.loads(match.group(0))
                            if data.get('es_match', False):
                                logger.info(f"✅ LLM match (conf={data.get('confianza', 0)})")
                                return True
                            else:
                                logger.info(f"❌ LLM rechazó (conf={data.get('confianza', 0)})")
                                continue
                        except json.JSONDecodeError:
                            continue
                    if "true" in content.lower() and "match" in content.lower():
                        return True
                    continue
                except Exception as e:
                    logger.error(f"Error con {current_model}: {e}")
                    continue
            return False
        finally:
            if self.vf:
                self.vf.hide_persistent_message("llm")

    # ── OCR helpers ───────────────────────────────────────────────────────────

    def preprocess_strip(self, img_bgr):
        """Preprocesa una franja de fila para OCR."""
        if HAS_PREPROCESS_UTILS:
            try:
                img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(img_rgb)
                processed_pil, scale = preprocess_high_fidelity(pil_img, scale_factor=3)
                return processed_pil, scale
            except Exception as e:
                logger.warning(f"preproceso fallido: {e}")

        # Fallback manual
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        resized = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        _, thresh = cv2.threshold(resized, 0, 255,
                                  cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        pil_out = Image.fromarray(thresh)
        return pil_out, 3.0

    def ocr_strip(self, img_bgr, strip_label=""):
        """OCR completo sobre una franja de imagen."""
        processed_pil, scale = self.preprocess_strip(img_bgr)

        # Guardar debug
        try:
            log_dir = Path("rpa_framework/log/busqueda por examen hecho")
            log_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y-%m-%d %H-%M-%S-%f")
            debug_path = log_dir / f"{ts}_strip_{strip_label}_3X.png"
            processed_pil.save(str(debug_path))
            logger.info(f"📸 Franja preprocesada guardada: {debug_path}")
        except Exception as e:
            logger.warning(f"No se pudo guardar debug strip: {e}")

        text = pytesseract.image_to_string(
            processed_pil,
            config='--psm 3 -l spa --oem 3'  # PSM 3 = Permite leer columnas separadas en la misma tira
        )
        return text.strip()

    # ── Búsqueda principal: "Examen Hecho" en pantalla completa ───────────────

    def find_examen_hecho_rows(self, full_img_bgr):
        """
        Usa Tesseract image_to_data para encontrar bounding boxes de palabras
        que sean variantes de "Examen Hecho".
        Retorna lista de Y-centers (en píxeles de la imagen capturada).
        """
        # Preprocesar imagen completa para la búsqueda inicial (escala 2X para
        # no ser tan agresivo como la franja final, que usa 3X)
        gray = cv2.cvtColor(full_img_bgr, cv2.COLOR_BGR2GRAY)
        # Aplicar CLAHE para mejorar contraste en filas resaltadas
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        # Upscale 2X
        up2x = cv2.resize(enhanced, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        _, thresh = cv2.threshold(up2x, 0, 255,
                                  cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # Guardar imagen de búsqueda para debug
        try:
            log_dir = Path("rpa_framework/log/busqueda por examen hecho")
            log_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
            cv2.imwrite(str(log_dir / f"{ts}_FULL_SCREEN_2X.png"), thresh)
        except Exception:
            pass

        # Tesseract con bounding boxes
        data = pytesseract.image_to_data(
            thresh,
            config='--psm 3 -l spa --oem 3',
            output_type=Output.DICT
        )

        n = len(data['text'])
        # Recopilar palabras con confianza razonable
        words = []
        for i in range(n):
            txt = (data['text'][i] or '').strip()
            conf = int(data['conf'][i]) if data['conf'][i] != '-1' else 0
            if not txt or conf < 20:
                continue
            # Coordenadas en imagen 2X → convertir a 1X
            x = data['left'][i] // 2
            y = data['top'][i] // 2
            w = data['width'][i] // 2
            h = data['height'][i] // 2
            y_center = y + h // 2
            words.append({
                'text': txt,
                'text_norm': self.normalize_text(txt),
                'x': x, 'y': y, 'w': w, 'h': h,
                'y_center': y_center,
                'conf': conf
            })
            logger.debug(f"  Palabra: '{txt}' conf={conf} Y={y_center}")

        logger.info(f"Tesseract encontró {len(words)} palabras en pantalla completa (2X)")

        # Agrupar palabras en filas por Y cercano
        rows = {}
        for word in words:
            assigned = False
            for ky in list(rows.keys()):
                if abs(ky - word['y_center']) <= self.ROW_TOLERANCE:
                    rows[ky].append(word)
                    assigned = True
                    break
            if not assigned:
                rows[word['y_center']] = [word]

        # Para cada fila comprobar si contiene variante de "Examen Hecho"
        candidate_y_centers = []
        logger.info("=== Filas detectadas en pantalla completa ===")
        for ky in sorted(rows.keys()):
            row_words = rows[ky]
            row_text = ' '.join([w['text'] for w in sorted(row_words, key=lambda x: x['x'])])
            row_norm = self.normalize_text(row_text)

            # Score vs variantes
            score_hecho     = fuzz.partial_ratio("hecho",     row_norm)
            score_realizado = fuzz.partial_ratio("realizado", row_norm)
            score_stat      = fuzz.partial_ratio("stat",      row_norm)

            is_hecho = (score_hecho > 70) or (score_realizado > 70) or (score_stat > 85)

            logger.info(
                f"  Fila Y={ky:4.0f} | hecho={score_hecho:3.0f} real={score_realizado:3.0f} "
                f"stat={score_stat:3.0f} → {'✅ CANDIDATA' if is_hecho else '❌'} | {row_text[:100]}"
            )

            if is_hecho:
                avg_y = int(sum(w['y_center'] for w in row_words) / len(row_words))
                candidate_y_centers.append(avg_y)
                logger.info(f"    → Y_center candidata: {avg_y}")

        logger.info(f"Total filas candidatas 'Examen Hecho': {len(candidate_y_centers)}")
        return candidate_y_centers

    def extract_row_strip(self, full_img_bgr, y_center, row_height=None):
        """Recorta una franja horizontal de row_height px centrada en y_center."""
        rh = row_height or self.ROW_HEIGHT
        h, w = full_img_bgr.shape[:2]
        half = rh // 2
        y_start = max(0, y_center - half)
        y_end   = min(h, y_center + half)
        strip = full_img_bgr[y_start:y_end, 0:w]
        return strip, y_start, y_end

    # ── Verificación de fecha ────────────────────────────────────────────────

    def check_fecha_in_text(self, text, target_fecha_str):
        target_digits = ''.join(filter(str.isdigit, target_fecha_str))
        row_digits    = ''.join(filter(str.isdigit, text))
        return (
            (target_fecha_str in text)
            or (target_fecha_str.replace('-', '/') in text)
            or (target_digits and target_digits in row_digits)
            or (fuzz.partial_ratio(target_fecha_str, text) > 80)
        )

    # ── Click ────────────────────────────────────────────────────────────────

    def click_target(self, screen_x, screen_y):
        self.update_db_coordinate(f"{screen_x},{screen_y}")
        logger.info(f"--- Click HUMANIZADO en: {screen_x}, {screen_y} ---")
        if self.vf:
            self.vf.highlight_click(screen_x, screen_y)
        pyautogui.moveTo(screen_x, screen_y, duration=0.5, tween=pyautogui.easeInOutQuad)
        time.sleep(0.1)
        pyautogui.mouseDown(button='right')
        time.sleep(0.15)
        pyautogui.mouseUp(button='right')
        logger.info(f"Click derecho en {screen_x}, {screen_y}")
        time.sleep(1.2)
        pyautogui.hotkey('ctrl', 'd')
        logger.info("Ctrl+D ejecutado")
        time.sleep(5)

    # ── Execute principal ─────────────────────────────────────────────────────

    def execute(self, override_diag: str = None):
        logger.info(">>>> INICIANDO BÚSQUEDA POR EXAMEN HECHO (Pantalla Completa) <<<<")

        # 1. Targets desde BD
        target_diag_original, target_fecha_obj = self.get_db_targets()
        if not target_diag_original:
            return False, ""

        target_diag      = override_diag or target_diag_original
        target_fecha_str = target_fecha_obj.strftime("%d-%m-%Y")
        logger.info(f"Buscando: [{target_fecha_str}] + [Examen Hecho] + [{target_diag}]")

        # 2. Captura pantalla completa
        if self.vf:
            self.vf.show_persistent_message("Capturando pantalla...", "ocr",
                                            bg_color="#FFEB3B", fg_color="#000000")
        screenshot = pyautogui.screenshot()
        img_np  = np.array(screenshot)
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        screen_h, screen_w = img_bgr.shape[:2]
        logger.info(f"Pantalla capturada: {screen_w}x{screen_h} px")

        # Guardar screenshot original
        try:
            log_dir = Path("rpa_framework/log/busqueda por examen hecho")
            log_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
            diag_c = ''.join([c if c.isalnum() else '_' for c in target_diag])[:30]
            cv2.imwrite(str(log_dir / f"{ts}_{diag_c}_FULL.png"), img_bgr)
        except Exception as e:
            logger.warning(f"No se pudo guardar screenshot: {e}")

        if self.vf:
            self.vf.hide_persistent_message("ocr")

        # 3. Encontrar filas con "Examen Hecho" en pantalla completa
        if self.vf:
            self.vf.show_persistent_message("Buscando 'Examen Hecho'...", "ocr",
                                            bg_color="#2196F3", fg_color="#FFFFFF")
        candidate_y_centers = self.find_examen_hecho_rows(img_bgr)
        if self.vf:
            self.vf.hide_persistent_message("ocr")

        if not candidate_y_centers:
            logger.warning("❌ No se encontraron filas con 'Examen Hecho' en pantalla.")
            return False, ""

        logger.info(f"Filas candidatas encontradas: {candidate_y_centers}")

        # 4. Para cada fila candidata → verificar fecha + diagnóstico
        for idx, y_center in enumerate(candidate_y_centers):
            logger.info(f"--- Verificando candidata #{idx+1} (Y_screen={y_center}) ---")

            # Extraer franja de 20px
            strip, y_start, y_end = self.extract_row_strip(img_bgr, y_center,
                                                            row_height=self.ROW_HEIGHT)
            if strip.size == 0:
                logger.warning(f"Franja vacía en Y={y_center}, omitiendo.")
                continue

            # OCR de la franja completa (PSM 7 = línea única)
            strip_text = self.ocr_strip(strip, strip_label=f"{idx+1}_y{y_center}")
            logger.info(f"OCR franja #{idx+1}: '{strip_text}'")

            # ── CHECK FECHA ─────────────────────────────────────────────────
            has_date = self.check_fecha_in_text(strip_text, target_fecha_str)
            logger.info(f"  ¿Tiene fecha '{target_fecha_str}'? → {has_date}")

            if not has_date:
                # Intentar con franja ligeramente más ancha (30px) como fallback si se cortó texto
                strip_wide, _, _ = self.extract_row_strip(img_bgr, y_center, row_height=30)
                strip_text_wide  = self.ocr_strip(strip_wide,
                                                   strip_label=f"{idx+1}_y{y_center}_wide")
                has_date = self.check_fecha_in_text(strip_text_wide, target_fecha_str)
                logger.info(f"  Franja 30px: '{strip_text_wide}' | ¿fecha? → {has_date}")
                if has_date:
                    strip_text = strip_text_wide

            if not has_date:
                logger.info(f"  ⚠️ Fila Y={y_center}: fecha no confirmada. Omitiendo.")
                continue

            # ── CHECK DIAGNÓSTICO ───────────────────────────────────────────
            ocr_norm    = self.normalize_text(strip_text)
            target_norm = self.normalize_text(target_diag)

            # Nivel 0: sinónimos BD
            sinonimo_bd = self.buscar_sinonimo(target_diag, strip_text)
            if sinonimo_bd:
                sin_norm = self.normalize_text(sinonimo_bd)
                if (fuzz.partial_ratio(sin_norm, ocr_norm) > 72
                        or fuzz.token_set_ratio(sin_norm, ocr_norm) > 72):
                    logger.info("✅ MATCH POR SINÓNIMO BD")
                    self.click_target(screen_x=screen_w // 2, screen_y=y_center)
                    return True, strip_text

            # Nivel 1: fuzzy local
            sc_partial = fuzz.partial_ratio(target_norm, ocr_norm)
            sc_token   = fuzz.token_set_ratio(target_norm, ocr_norm)
            logger.info(f"  Fuzzy → partial={sc_partial} token={sc_token}")
            if sc_partial > 85 or sc_token > 85:
                logger.info("✅ MATCH FUZZY LOCAL")
                self.click_target(screen_x=screen_w // 2, screen_y=y_center)
                return True, strip_text

            # Nivel 2: LLM
            logger.info("  ⚠️ Fuzzy insuficiente. Consultando LLM...")
            if self.vf:
                self.vf.show_persistent_message("PROCESANDO LLM...", "llm",
                                                bg_color="#FFEB3B", fg_color="#000000")
            is_match_llm = self.call_llm_text_verification(strip_text, target_diag)
            if self.vf:
                self.vf.hide_persistent_message("llm")

            if is_match_llm:
                logger.info("✅ MATCH LLM CONFIRMADO")
                self.click_target(screen_x=screen_w // 2, screen_y=y_center)
                return True, strip_text
            else:
                logger.info(f"❌ LLM rechazó candidata Y={y_center}")

        logger.warning("Ninguna candidata confirmó fecha + diagnóstico.")
        best = ""
        if candidate_y_centers:
            strip, _, _ = self.extract_row_strip(img_bgr, candidate_y_centers[0])
            best = self.ocr_strip(strip, "best_fallback")
        return False, best


def main():
    setup_logging()

    while True:
        search = BusquedaPorExamenHecho()

        target_diag_raw, _ = search.get_db_targets()
        override_diag = None
        last_ocr_text = ""

        if target_diag_raw:
            sinonimo = search.buscar_sinonimo(target_diag_raw, "")
            if sinonimo:
                logger.info(f"📚 Sinónimo BD: '{sinonimo}' para '{target_diag_raw}'")
                override_diag = sinonimo

        MAX_RETRIES = 1
        found = False
        for attempt in range(MAX_RETRIES + 1):
            logger.info("=" * 60)
            logger.info(f"INTENTO {attempt + 1} DE {MAX_RETRIES + 1}")
            logger.info("=" * 60)
            try:
                result, last_ocr_text = search.execute(override_diag=override_diag)
                if result:
                    logger.info("✅ Proceso completado exitosamente")
                    found = True
                    break
                else:
                    if attempt < MAX_RETRIES:
                        logger.warning(f"⚠️ Intento {attempt+1} falló. Reintentando...")
                        time.sleep(2)
            except Exception as e:
                logger.error(f"Error durante ejecución: {e}", exc_info=True)
                if attempt < MAX_RETRIES:
                    time.sleep(2)

        if found:
            sys.exit(0)

        logger.warning("⚠️ Todos los reintentos fallaron. Mostrando diálogo al usuario.")

        if search.vf:
            dialog_result = search.vf.show_synonym_dialog(
                db_name=target_diag_raw or "(desconocido)",
                ocr_text=last_ocr_text
            )
            action  = dialog_result.get("action", "cancel")
            synonym = dialog_result.get("synonym", "").strip()

            if action == "save_retry":
                if synonym:
                    search.guardar_sinonimo(target_diag_raw or "", last_ocr_text, synonym)
                    logger.info(f"💾 Sinónimo guardado: '{synonym}'. Reintentando...")
                    try:
                        enviar_alerta_todos(f"💾 <b>Sinónimo registrado</b>\n{synonym}")
                    except:
                        pass
                    override_diag = synonym
                else:
                    override_diag = None
                time.sleep(1)
                continue

            elif action == "retry":
                logger.info("🔄 Reintentando sin cambios.")
                try:
                    enviar_alerta_todos("🔄 <b>Búsqueda: Reintentando</b>")
                except:
                    pass
                override_diag = None
                time.sleep(1)
                continue

            else:
                logger.info("❌ Cancelado por el usuario.")
                try:
                    enviar_alerta_todos("❌ <b>Búsqueda: Cancelada</b>")
                except:
                    pass
                search.update_db_error("Cancelado por usuario")
                sys.exit(1)
        else:
            search.update_db_error("Fallo búsqueda sin interfaz")
            sys.exit(1)


if __name__ == "__main__":
    main()
