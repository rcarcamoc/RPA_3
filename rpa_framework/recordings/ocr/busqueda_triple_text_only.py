#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script: busqueda_triple_text_only.py
Descripción: Script de búsqueda optimizado para validación semántica de texto.
1. Busca "Examen Hecho" (o variantes) + Fecha en toda la imagen.
2. Identifica filas candidatas.
3. Extrae el texto diagnóstico de cada fila usando Tesseract.
4. Si la validación exacta/fuzzy falla, envía el TEXTO al LLM (DeepSeek) con un prompt clínico robusto.

Ubicación: rpa_framework/recordings/ocr/busqueda_triple_text_only.py
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

# Cargar variables de entorno
load_dotenv()

# Imports condicionales
try:
    import pytesseract
except ImportError:
    pass

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

# Configuración de Paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.logging_setup import setup_logging
from ocr.engine import OCREngine
from PIL import Image
from utils.telegram_manager import enviar_alerta_todos

# Importar utilidades de preprocesamiento
try:
    from recordings.ocr.utilidades.preproceso_ocr import preprocess_high_fidelity, normalize_coordinates
    HAS_PREPROCESS_UTILS = True
except ImportError:
    HAS_PREPROCESS_UTILS = False

logger = logging.getLogger(__name__)

# ===========================================================================
# CONFIGURACIÓN LLM (auto-contenida en este archivo)
# Para cambiar modelos o parámetros, edita SOLO este bloque.
# ===========================================================================
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Lista de modelos en orden de prioridad / fallback.
# Si uno devuelve 429 o falla, se intenta el siguiente.
LLM_MODELS = [
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "arcee-ai/trinity-large-preview:free",
    "qwen/qwen3-235b-a22b-thinking-2507",
    "z-ai/glm-4.5-air:free",
    "stepfun/step-3.5-flash:free",
    "google/gemma-3-27b-it:free",
]
LLM_DEFAULT_TEMPERATURE = 0.0
LLM_DEFAULT_MAX_TOKENS  = 800
LLM_DEFAULT_TIMEOUT     = 30   # segundos

# Umbral mínimo de similitud fuzzy para siquiera consultar al LLM.
# Si el texto OCR y el target difieren MÁS que esto, son tan distintos
# que cualquier "match" del LLM sería una alucinación.
# 30 = permisivo (permite acrónimos cortos vs texto largo),
# pero evita casos como "Prortario" vs "TAC Cerebro" (score ~10).
MIN_FUZZY_FOR_LLM = 30

# Confianza mínima que el LLM debe reportar para aceptar un match.
LLM_MIN_CONFIDENCE = 0.70

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    logger.error("OPENROUTER_API_KEY no está configurada en el archivo .env")
    sys.exit(1)
# Alias de retrocompatibilidad
MODEL_ID = LLM_MODELS[0]
# ===========================================================================


time.sleep(2) # Dar tiempo para ocultar esta ventana

class BusquedaTextOnly:
    def __init__(self):
        # Inicializar motor OCR (sin preproceso interno para hacerlo manualmente y tener control total)
        self.ocr_engine = OCREngine(
            engine='tesseract', 
            language='spa', 
            use_gpu=False, 
            confidence_threshold=0.0,
            preprocess=False, # Lo haremos manualmente
            custom_config='--psm 6'
        )
        # Región ajustada: Comienza en (180, 180) y llega hasta (1900, 1000)
        # Formato: (left, top, width, height)
        self.region = (148, 100, 1720, 900)
        self.ROW_TOLERANCE = 8  # Tolerancia estricta (15px) para no mezclar filas adyacentes y dar un click preciso
        self.CROP_HEIGHT = 22  # Altura de recorte para cubrir fila (px en imagen original)
        self.OFFSET_X = 50
        self.OFFSET_Y = 180 # Offset para el submenú despues del click derecho
        self.MAX_RETRIES = 1  # Número de reintentos si falla el proceso
        
        # Init Visual Feedback
        try:
            # Intentar primero import relativo a la raíz del framework (path agregado)
            from utils.visual_feedback import VisualFeedback
            self.vf = VisualFeedback()
        except ImportError as e:
            logger.warning(f"VisualFeedback no disponible (ImportError: {e}), mensajes desactivados.")
            self.vf = None
        except Exception as e:
            logger.warning(f"Error inicializando VisualFeedback: {e}")
            self.vf = None

    def update_db_error(self, error_message):
        """Actualiza el estado a Error en la base de datos."""
        if not HAS_MYSQL:
            logger.error("No hay driver de MySQL para actualizar error.")
            return

        try:
            conn = mysql.connector.connect(
                host='localhost',
                user='root',
                password='',
                database='ris'
            )
            cursor = conn.cursor()
            
            query = """
            UPDATE ris.registro_acciones
            SET estado = 'Error'
            WHERE estado = 'En Proceso'
            LIMIT 1;
            """
            cursor.execute(query)
            conn.commit()
            conn.close()
            logger.info(f"Estado actualizado a 'Error' en BBDD: {error_message}")
        except Exception as e:
            logger.error(f"Error actualizando BBDD con error: {e}")

    def update_db_coordinate(self, coordinate_str):
        """Actualiza el campo coordenada en la base de datos."""
        if not HAS_MYSQL:
            logger.error("No hay driver de MySQL para actualizar coordenada.")
            return

        try:
            conn = mysql.connector.connect(
                host='localhost',
                user='root',
                password='',
                database='ris'
            )
            cursor = conn.cursor()
            
            query = """
            UPDATE ris.registro_acciones
            SET coordenada = %s
            WHERE estado = 'En Proceso'
            LIMIT 1;
            """
            cursor.execute(query, (coordinate_str,))
            conn.commit()
            conn.close()
            logger.info(f"Coordenada '{coordinate_str}' actualizada en BBDD.")
        except Exception as e:
            logger.error(f"Error actualizando BBDD con coordenada: {e}")

    def buscar_sinonimo(self, examen: str, ocr_text: str) -> str:
        """
        Busca en ris.sinonimos si existe alguna coincidencia para este examen/OCR.
        Busca en cualquiera de las columnas (examen, OCR, Sugerencia).
        También comprueba si el texto OCR CONTIENE alguno de los valores guardados.
        Retorna la Sugerencia guardada si encuentra match, o '' (cadena vacía).
        """
        if not HAS_MYSQL:
            return ''
        try:
            conn = mysql.connector.connect(
                host='localhost', user='root', password='', database='ris'
            )
            cursor = conn.cursor()
            # Búsqueda amplia:
            #  1. Coincidencia exacta de examen o Sugerencia con el nombre de BD
            #  2. El texto OCR contiene el valor guardado en columna OCR (INSTR)
            #  3. El nombre de BD contiene el valor guardado en columna examen (INSTR)
            cursor.execute("""
                SELECT Sugerencia FROM ris.sinonimos
                WHERE examen = %s
                   OR Sugerencia = %s
                   OR (OCR   != '' AND INSTR(%s, OCR)   > 0)
                   OR (examen != '' AND INSTR(%s, examen) > 0)
                LIMIT 1
            """, (examen, examen, ocr_text or '', examen or ''))
            row = cursor.fetchone()
            conn.close()
            if row and row[0]:
                logger.info(f"✅ Sinónimo encontrado en BD: '{row[0]}' para examen='{examen}'")
                return row[0]
            return ''
        except Exception as e:
            logger.warning(f"No se pudo consultar ris.sinonimos: {e}")
            return ''

    def guardar_sinonimo(self, examen: str, ocr_text: str, sugerencia: str) -> None:
        """Guarda un nuevo registro en ris.sinonimos."""
        if not HAS_MYSQL or not sugerencia:
            return
        try:
            conn = mysql.connector.connect(
                host='localhost', user='root', password='', database='ris'
            )
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO ris.sinonimos (examen, OCR, Sugerencia)
                VALUES (%s, %s, %s)
            """, (examen[:100], (ocr_text or '')[:100], sugerencia[:100]))
            conn.commit()
            conn.close()
            logger.info(f"💾 Sinónimo guardado: examen='{examen}' | OCR='{ocr_text}' | Sugerencia='{sugerencia}'")
        except Exception as e:
            logger.error(f"Error guardando sinónimo en BD: {e}")

    def get_db_targets(self):
        """Obtiene diagnóstico y fecha desde la base de datos."""
        if not HAS_MYSQL:
            logger.error("No hay driver de MySQL instalado.")
            return None, None

        try:
            conn = mysql.connector.connect(
                host='localhost',
                user='root',
                password='',
                database='ris'
            )
            cursor = conn.cursor()
            
            query = """
            SELECT SUBSTRING_INDEX(diagnostico, '\n', 1) AS examen, date(fecha_agendada) as fecha
            FROM ris.registro_acciones
            WHERE estado = 'En Proceso'
            LIMIT 1;
            """
            cursor.execute(query)
            result = cursor.fetchone()
            conn.close()

            if result:
                examen = result[0]
                fecha = result[1]
                logger.info(f"Target DB - Diagnóstico: '{examen}', Fecha: '{fecha}'")
                return examen, fecha
            else:
                logger.warning("No se encontraron registros 'En Proceso' en la BBDD.")
                return None, None
        except Exception as e:
            logger.error(f"Error consultando BBDD: {e}")
            return None, None

    def normalize_text(self, text):
        text = text.lower()
        text = ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
        text = re.sub(r'[^a-z0-9\-]', ' ', text)
        text = ' '.join(text.split())
        return text

    # Removed similarity method as it was not appropriate for substring checks


    def agrupar_por_filas(self, results):
        if not results:
            return []
            
        # 1. Ordenar todos los items por su posición Y para facilitar el agrupamiento de arriba a abajo
        results_sorted = sorted(results, key=lambda x: x['center']['y'])
        
        rows_data = []
        for item in results_sorted:
            y_item = item['center']['y']
            matched = False
            for row in rows_data:
                # Si el item está dentro de la tolerancia vertical de una fila existente
                if abs(row['y_center'] - y_item) < self.ROW_TOLERANCE:
                    row['items'].append(item)
                    # Recalcular el centro Y de la fila como el promedio de sus elementos
                    row['y_center'] = sum([i['center']['y'] for i in row['items']]) / len(row['items'])
                    matched = True
                    break
            if not matched:
                rows_data.append({'y_center': y_item, 'items': [item]})
        
        # 2. Paso de consolidación: Unir filas que hayan quedado muy cerca tras el primer paso
        rows_data.sort(key=lambda x: x['y_center'])
        final_rows = []
        if rows_data:
            current_row = rows_data[0]
            for i in range(1, len(rows_data)):
                next_row = rows_data[i]
                if abs(current_row['y_center'] - next_row['y_center']) < (self.ROW_TOLERANCE * 0.8):
                    current_row['items'].extend(next_row['items'])
                    current_row['y_center'] = sum([it['center']['y'] for it in current_row['items']]) / len(current_row['items'])
                else:
                    final_rows.append(current_row)
                    current_row = next_row
            final_rows.append(current_row)
            
        return final_rows

    def preprocess_image(self, img_bgr):
        # 1. Convertir a escala de grises
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        
        # 2. Aumentar contraste (CLAHE o simple)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        contrast = clahe.apply(gray)
        
        # 3. Binarización (Otsu es bueno, pero aplicamos un ligero desenfoque antes)
        blurred = cv2.GaussianBlur(contrast, (3, 3), 0)
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # 4. Operación Morfológica para limpiar ruido
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2,2))
        processed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        return processed

    def execute_ocr_basic(self, img_bgr, psm=6):
        """Ejecuta OCR usando explícitamente el módulo de preproceso_ocr."""
        if not HAS_PREPROCESS_UTILS:
            logger.warning("Módulo preproceso_ocr no disponible, usando OCR básico.")
            return pytesseract.image_to_string(img_bgr, config=f'--psm {psm} -l spa')
            
        try:
            # 1. Convertir BGR a PIL RGB
            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img_rgb)
            
            # 2. Preprocesar (Upscaling 3x + Binarización Otsu + Limpieza)
            processed_pil, _ = preprocess_high_fidelity(pil_img, scale_factor=3)
            
            # 3. OCR con Tesseract
            custom_config = f'--psm {psm} -l spa --oem 3'
            text = pytesseract.image_to_string(processed_pil, config=custom_config)
            return text.strip()
        except Exception as e:
            logger.error(f"Error en OCR Basic (Manual Preprocess): {e}")
            return ""

    def execute_ocr_data(self, img_bgr, use_preprocessing=True):
        """
        Devuelve datos estructurados de OCR.
        Permite activar/desactivar pre-procesamiento manual (use_preprocessing=False para fallback).
        """
        if not HAS_PREPROCESS_UTILS:
            logger.warning("Faltan utilidades de preproceso, usando motor directo.")
            use_preprocessing = False

        if not use_preprocessing:
            # Fallback o falta de utils: OCR directo
            logger.info("ℹ️ Ejecutando OCR en imagen RAW (Sin Preprocesamiento 3X)...")
            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            return self.ocr_engine.extract_text_with_location(img_rgb)

        try:
            # 1. Preprocesar la imagen ANTES del OCR
            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img_rgb)
            
            # Aplicar Alta Fidelidad (3x)
            processed_pil, scale = preprocess_high_fidelity(pil_img, scale_factor=3)
            
            # 2. Guardar imagen procesada para depuración (Fundamental para ver qué ve el OCR)
            try:
                log_dir = Path("rpa_framework/log/busqueda triple")
                log_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
                debug_path = log_dir / f"{timestamp}_OCR_PREPROCESSED_3X.png"
                processed_pil.save(str(debug_path))
                logger.info(f"📸 Imagen preprocesada (3X BW) guardada en: {debug_path}")
            except Exception as e:
                logger.warning(f"No se pudo guardar la imagen de debug OCR: {e}")

            # 3. Extraer texto de la imagen YA PROCESADA
            # Como la imagen ya está preprocesada, le decimos al motor que no lo haga de nuevo
            processed_np = np.array(processed_pil)
            # El motor espera RGB si le pasamos numpy
            results_scaled = self.ocr_engine.extract_text_with_location(processed_np)
            
            # 4. NORMALIZAR COORDENADAS (Importante: el OCR vio 3x, necesitamos 1x)
            normalized_results = []
            for res in results_scaled:
                norm_res = normalize_coordinates(res, scale)
                normalized_results.append(norm_res)
                
            logger.info(f"OCR detectó {len(normalized_results)} palabras (Preproceso Manual + Normalización OK)")
            return normalized_results

        except Exception as e:
            logger.error(f"Error en execute_ocr_data (Manual): {e}")
            return []

    def get_crop_image(self, full_img, y_center):
        h, w = full_img.shape[:2]
        half_h = self.CROP_HEIGHT // 2
        y_start = int(max(0, y_center - half_h))
        y_end = int(min(h, y_center + half_h))
        return full_img[y_start:y_end, 0:w]

    # --- LLM FUNCTIONS ---
    def _pre_filter_llm(self, ocr_text: str, target_diag: str) -> bool:
        """
        Pre-filtro anti-alucinación. Devuelve True (proceder con LLM) sólo si
        el texto OCR tiene al menos MIN_FUZZY_FOR_LLM de similitud con el target.

        Esto impide que el LLM "invente" una equivalencia cuando los textos son
        tan distintos que ninguna corrección OCR real podría justificarla.
        (ejemplo: 'Prortario' vs 'TAC Cerebro' → score ~10 → RECHAZADO sin LLM)
        """
        target_norm = self.normalize_text(target_diag)
        ocr_norm    = self.normalize_text(ocr_text)

        score_partial = fuzz.partial_ratio(target_norm, ocr_norm)
        score_token   = fuzz.token_set_ratio(target_norm, ocr_norm)
        best_score    = max(score_partial, score_token)

        logger.info(
            f"🔍 Pre-filtro LLM | target='{target_diag}' | ocr='{ocr_text[:60]}' "
            f"| partial={score_partial} token={score_token} → umbral={MIN_FUZZY_FOR_LLM}"
        )

        if best_score < MIN_FUZZY_FOR_LLM:
            logger.warning(
                f"🚫 Pre-filtro RECHAZA llamar al LLM (score={best_score} < {MIN_FUZZY_FOR_LLM}). "
                f"Los textos son demasiado diferentes para ser el mismo examen."
            )
            return False

        return True

    def call_llm_text_verification(self, ocr_text, target_diag):
        """
        Consulta al LLM si el texto encontrado coincide semánticamente con el objetivo.
        Implementa fallback entre varios modelos si falla uno.

        IMPORTANTE: Antes de llamar al LLM se aplica _pre_filter_llm() para descartar
        candidatos cuya distancia textual hace imposible cualquier match real.
        """
        # Pre-filtro: evitar alucinaciones por textos completamente disímiles
        if not self._pre_filter_llm(ocr_text, target_diag):
            return False

        models = LLM_MODELS

        prompt = f"""
Eres un experto clínico en interpretación de terminología radiológica y exámenes de imagen.
Tu tarea es determinar si el texto ENCONTRADO (puede tener errores típicos de OCR) 
describe el mismo examen que el BUSCADO.

BUSCADO: "{target_diag}"
ENCONTRADO (línea completa OCR): "{ocr_text}"

---
## REGLAS DE EQUIVALENCIA (Tolerancia OCR razonable)

1. **ACRÓNIMOS Y MODALIDADES**:
   - RESONANCIA MAGNÉTICA ≈ RM ≈ RMNC ≈ RIM ≈ RNM ≈ RAM ≈ MRI.
   - TOMOGRAFÍA COMPUTADA ≈ TC ≈ TAC ≈ CT ≈ T.C.
   - ULTRASONIDO ≈ ECOTOMOGRAFÍA ≈ ECO ≈ US.
   - RADIOGRAFÍA ≈ RX ≈ R-X.

2. **CORRECCIÓN OCR PERMITIDA** (errores de carácter simples):
   - Un carácter cambiado: "S"↔"5", "I"↔"1"↔"|", "O"↔"0", "B"↔"8".
   - Letras adicionales o faltantes al inicio/fin por segmentación (ej: "TAC" → "TAC ").
   - Acento o ñ incorrectos (ej: "Ecotomografia" ≈ "Ecotomografía").

3. **REGIÓN ANATÓMICA**: debe coincidir en la zona principal.

---
## PROHIBICIONES ESTRICTAS (estas situaciones = es_match: false)

- ❌ NO aceptar si la corrección requiere cambiar MÁS DE 3 caracteres simultáneamente.
- ❌ NO inventar palabras completas: si el OCR dice "Prortario" NO puede ser "TAC Cerebro".
- ❌ NO aceptar si la modalidad (TAC, RM, RX, ECO) no tiene ninguna representación reconocible en el ENCONTRADO.
- ❌ NO aceptar si la región anatómica no coincide en absoluto.
- ❌ NO aceptar si tienes dudas razonables (usa confianza baja → es_match: false).

---
## PROCESO DE RAZONAMIENTO

1. Extrae del ENCONTRADO el segmento que parece el nombre del examen.
2. Aplica corrección OCR MÍNIMA (≤3 caracteres). ¿Qué examen queda?
3. ¿Ese examen equivale al BUSCADO?
4. Si en algún paso necesitaste cambiar palabras enteras, responde es_match: false.

RESPONDE SOLO EN FORMATO JSON:
{{
  "es_match": true o false,
  "razonamiento": "Explicación concreta y breve (máx 100 chars)",
  "confianza": 0.0-1.0
}}
"""

        if self.vf:
            self.vf.show_persistent_message("PROCESANDO OpenRouter...", "llm", bg_color="#FFEB3B", fg_color="#000000")

        try:
            for current_model in models:
                logger.info("="*50)
                logger.info(f"🤖 Intentando consulta con modelo: {current_model}")
                logger.info(f"🎯 TARGET BUSCADO: '{target_diag}'")
                logger.info(f"📝 TEXTO OCR ENVIADO: '{ocr_text}'")
                logger.info("="*50)

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
                            "max_tokens":  LLM_DEFAULT_MAX_TOKENS,
                        },
                        timeout=LLM_DEFAULT_TIMEOUT
                    )

                    if response.status_code == 429:
                        logger.warning(f"⚠️ Modelo {current_model} devolvió 429. Probando siguiente...")
                        continue

                    response.raise_for_status()
                    result  = response.json()
                    content = result['choices'][0]['message'].get('content', '')

                    logger.info(f"Respuesta Raw LLM ({current_model}): {content[:300]}...")

                    # ── Parse JSON ──────────────────────────────────────────────
                    json_match = re.search(r'\{.*?\}', content, re.DOTALL)
                    if json_match:
                        try:
                            data       = json.loads(json_match.group(0))
                            is_match   = data.get('es_match', False)
                            confianza  = float(data.get('confianza', 0))
                            razonamiento = data.get('razonamiento', '')

                            logger.info(
                                f"LLM → es_match={is_match} | confianza={confianza:.2f} "
                                f"| razon='{razonamiento[:120]}'"
                            )

                            if is_match and confianza >= LLM_MIN_CONFIDENCE:
                                logger.info(
                                    f"✅ Modelo {current_model} confirma match "
                                    f"(confianza={confianza:.2f} ≥ {LLM_MIN_CONFIDENCE})"
                                )
                                return True
                            elif is_match and confianza < LLM_MIN_CONFIDENCE:
                                logger.warning(
                                    f"⚠️ Modelo {current_model} dice match pero confianza baja "
                                    f"({confianza:.2f} < {LLM_MIN_CONFIDENCE}). Rechazando."
                                )
                                continue
                            else:
                                logger.info(f"❌ Modelo {current_model} rechazó (confianza={confianza:.2f}).")
                                continue

                        except (json.JSONDecodeError, ValueError) as je:
                            logger.warning(f"⚠️ No se pudo parsear JSON de {current_model}: {je}")
                            continue

                    # Sin JSON estructurado → respuesta no confiable, ignorar
                    logger.warning(f"⚠️ Respuesta de {current_model} sin JSON. Descartando.")
                    continue

                except Exception as e:
                    logger.error(f"❌ Error con modelo {current_model}: {e}")
                    logger.info("Probando con el siguiente modelo de respaldo...")
                    continue

            logger.warning("Todos los modelos LLM han fallado o rechazado el candidato.")
            return False

        finally:
            if self.vf:
                self.vf.hide_persistent_message("llm")

    def _analyze_candidates(self, ocr_results, target_fecha_str):
        """Analiza resultados OCR y devuelve candidatos.

        REGLA ESTRICTA (inamovible por confiabilidad clínica): en la MISMA
        fila deben aparecer TODOS:
          1. La fecha agendada del examen
          2. El estado 'Examen Hecho' o 'Realizado'
        Sin esta coincidencia simultánea no se genera ningún candidato.
        """
        rows_data = self.agrupar_por_filas(ocr_results)
        candidates = []

        rows_sorted = sorted(rows_data, key=lambda r: r['y_center'])
        for row in rows_sorted:
            row_items  = sorted(row['items'], key=lambda x: x['center']['x'])
            row['full_text'] = " ".join([i['text'] for i in row_items])

        target_fecha_digits = "".join(filter(str.isdigit, target_fecha_str))

        for row in rows_sorted:
            row_text   = row['full_text']
            row_norm   = self.normalize_text(row_text)
            row_digits = "".join(filter(str.isdigit, row_text))

            # ── CHECK FECHA ──────────────────────────────────────────────
            has_date = (
                (target_fecha_str in row_text)
                or (target_fecha_str.replace("-", "/") in row_text)
                or (target_fecha_digits in row_digits)
                or (fuzz.partial_ratio(target_fecha_str, row_text) > 80)
            )

            # ── CHECK ESTADO ────────────────────────────────────────────
            # OBLIGATORIO: Se exige que la fila contenga explícitamente "Examen Hecho" (o "hecho").
            # OCR en esta imagen en particular reconoció "ExamenHedo", lo cual baja el score a 75.0 exactos
            score_examen_hecho = fuzz.partial_ratio("examen hecho", row_norm)
            score_hecho        = fuzz.partial_ratio("hecho",        row_norm)
            has_estado = (score_examen_hecho >= 70) or (score_hecho >= 70)

            logger.debug(
                f"Fila Y={int(row['y_center'])}: ex_hecho={score_examen_hecho} hecho={score_hecho} "
                f"fecha={has_date} | {row_text[:80]}"
            )

            if has_date and has_estado:
                # Calcular rango vertical REAL del bloque (usando bounds de Tesseract)
                all_y_min = [i['bounds']['y_min'] for i in row['items'] if 'bounds' in i]
                all_y_max = [i['bounds']['y_max'] for i in row['items'] if 'bounds' in i]
                row['y_min'] = min(all_y_min) if all_y_min else (row['y_center'] - self.CROP_HEIGHT // 2)
                row['y_max'] = max(all_y_max) if all_y_max else (row['y_center'] + self.CROP_HEIGHT // 2)
                # Usar y_center (promedio de centros de palabras) como punto de clic.
                # Es más estable que (y_min + y_max)/2 porque los bounds de Tesseract
                # sobre imagen 3x normalizada pueden incluir padding que desplaza el resultado.
                row['y_click'] = row['y_center']
                row['score_estado'] = max(score_examen_hecho, score_hecho)
                candidates.append(row)
                logger.info(
                    f"✅ Candidato (Y_center={int(row['y_center'])} | y_min={int(row['y_min'])} "
                    f"y_max={int(row['y_max'])} y_click={int(row['y_click'])}, "
                    f"ex_hecho={score_examen_hecho} hecho={score_hecho}): "
                    f"{row_text[:120]}"
                )

        # Ordenar los candidatos por su score_estado de mayor a menor para priorizar los mejores matches
        candidates = sorted(candidates, key=lambda c: c.get('score_estado', 0), reverse=True)

        return candidates, rows_data


    def execute(self, override_diag: str = None):
        """Ejecuta la búsqueda. Retorna (encontrado: bool, ocr_text_candidato: str)."""
        logger.info(">>>> INICIANDO BÚSQUEDA TEXT-ONLY (DeepSeek) <<<<")
        
        # 1. Obtener Targets
        target_diag_original, target_fecha_obj = self.get_db_targets()
        if not target_diag_original:
            return False, ""

        # Permitir sobrescribir el diagnóstico con un sinónimo
        target_diag = target_diag_original
        if override_diag:
            logger.info(f"🔄 Usando sinónimo/alternativa: '{override_diag}' (original: '{target_diag_original}')")
            target_diag = override_diag
            
        target_fecha_str = target_fecha_obj.strftime("%d-%m-%Y")
        logger.info(f"Buscando: [{target_fecha_str}] + [Hecho] + [{target_diag}]")

        # 2. Captura Inicial
        if self.vf:
            # Resaltar en pantalla la zona de captura
            self.vf.highlight_region(*self.region, duration=1.0)
            time.sleep(0.2) # Pequeña pausa para que el usuario lo vea

        screenshot = pyautogui.screenshot(region=self.region)
        img_np = np.array(screenshot)
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

        # Log visual inicial (screenshot sin anotaciones aún; se guardará anotado tras el OCR)
        log_dir = Path("rpa_framework/log/busqueda triple")
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        now_str = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
        diag_clean = "".join([c if c.isalnum() else "_" for c in target_diag])[:30]
        _log_base_name = f"{now_str} {diag_clean} {target_fecha_str}"
        
        # 3. OCR General (Estrategia: Primero Preprocesado, si falla, Raw)
        candidates = []
        rows_data = [] # Para logging en caso de faloo
        
        # --- PASO 1: OCR CON PREPROCESAMIENTO ---
        logger.info("--- 🔄 Ejecutando OCR Paso 1: Con Preprocesamiento ---")
        if self.vf:
            self.vf.show_persistent_message("PROCESANDO OCR (HQ)...", "ocr", bg_color="#FFEB3B", fg_color="#000000")
            
        try:
            ocr_results = self.execute_ocr_data(img_bgr, use_preprocessing=True)
            candidates, rows_data = self._analyze_candidates(ocr_results, target_fecha_str)
        finally:
            if self.vf:
                self.vf.hide_persistent_message("ocr")
                
        # --- PASO 2: OCR RAW (FALLBACK) ---
        if not candidates:
            logger.warning("⚠️ Paso 1 sin candidatos. Ejecutando Paso 2: OCR RAW (Fallback)...")
            
            if self.vf:
                self.vf.show_persistent_message("PROCESANDO OCR (RAW)...", "ocr", bg_color="#FF9800", fg_color="#000000")
                
            try:
                ocr_results_raw = self.execute_ocr_data(img_bgr, use_preprocessing=False)
                candidates_raw, rows_data_raw = self._analyze_candidates(ocr_results_raw, target_fecha_str)
                
                if candidates_raw:
                     logger.info(f"✅ Fallback de OCR exitoso. Encontrados {len(candidates_raw)} candidatos.")
                     candidates = candidates_raw
                     rows_data = rows_data_raw
                else:
                     logger.warning("❌ Paso 2 también sin candidatos.")
                     # Mantenemos rows_data del paso 1 o combinamos para debug, pero paso 2 es más relevante si es fallback
                     rows_data = rows_data_raw 
            finally:
                if self.vf:
                     self.vf.hide_persistent_message("ocr")

        logger.info(f"Total Candidatos Finales: {len(candidates)}")

        # Guardar imagen de log con franjas de detección OCR
        self.save_detection_log_image(
            img_bgr=img_bgr,
            rows_data=rows_data,
            candidates=candidates,
            log_dir=log_dir,
            base_name=_log_base_name
        )
        
        if not candidates:
            logger.warning("No se encontraron filas con Fecha y Estado 'Hecho' en ninguno de los intentos.")
            
            # DEBUG: Imprimir qué está viendo para diagnóstico
            logger.info("=== DEBUG: Contenido de filas detectadas (Último intento) ===")
            for i, r in enumerate(rows_data):
                row_items = sorted(r['items'], key=lambda x: x['center']['x'])
                txt = " ".join([item['text'] for item in row_items])
                logger.info(f"Fila {i} (Y={int(r['y_center'])}): {txt}")
            logger.info("============================================")
            
            return False, ""
                
        logger.info(f"Candidatos iniciales (Fecha + Estado): {len(candidates)}")
        
        if not candidates:
            logger.warning("No se encontraron filas con Fecha y Estado 'Hecho'.")
            
            # DEBUG: Imprimir qué está viendo para diagnóstico
            logger.info("=== DEBUG: Contenido de filas detectadas ===")
            for i, r in enumerate(rows_data):
                row_items = sorted(r['items'], key=lambda x: x['center']['x'])
                txt = " ".join([item['text'] for item in row_items])
                logger.info(f"Fila {i} (Y={int(r['y_center'])}): {txt}")
            logger.info("============================================")
            
            return False, ""

        # 4. Iterar Candidatos y Verificar Diagnóstico
        for idx, cand in enumerate(candidates):
            y_center = cand['y_center']
            # Usar el centro REAL del bloque de texto (calculado desde bounds de Tesseract)
            y_click = cand.get('y_click', y_center)
            logger.info(
                f"--- Verificando Candidato #{idx+1} "
                f"(Y_center={int(y_center)} | Y_click={int(y_click)}) ---"
            )
            
            # USAR EL TEXTO YA DETECTADO (Más robusto que re-hacer OCR con recorte)
            # El paso anterior ya demostró que este texto tiene buena calidad (encontró fecha y estado)
            ocr_text_candidate = cand.get('full_text', "")
            logger.info(f"Texto OCR Candidato: '{ocr_text_candidate}'")
            
            ocr_norm = self.normalize_text(ocr_text_candidate)
            target_norm = self.normalize_text(target_diag)

            # ── NIVEL 0: Búsqueda en tabla de sinónimos ────────────────────────
            # Se busca ANTES del LLM usando el texto OCR ya detectado.
            # Evita llamadas al LLM para casos ya vistos por el usuario.
            sinonimo_bd = self.buscar_sinonimo(target_diag, ocr_text_candidate)
            if sinonimo_bd:
                sinonimo_norm = self.normalize_text(sinonimo_bd)
                score_sin_partial = fuzz.partial_ratio(sinonimo_norm, ocr_norm)
                score_sin_token   = fuzz.token_set_ratio(sinonimo_norm, ocr_norm)
                logger.info(f"📚 Sinónimo BD: '{sinonimo_bd}' | partial={score_sin_partial} token={score_sin_token}")
                if score_sin_partial > 72 or score_sin_token > 72:
                    logger.info("✅ MATCH POR SINÓNIMO BD CONFIRMADO")
                    self.click_target(y_click, img_bgr=img_bgr, log_dir=log_dir, base_name=_log_base_name)
                    return True, ''

            # ── NIVEL 1: Verificación Local (Fuzzy) ─────────────────────────────
            if fuzz.partial_ratio(target_norm, ocr_norm) > 85 or \
               fuzz.token_set_ratio(target_norm, ocr_norm) > 85:
                logger.info(f"✅ MATCH LOCAL CONFIRMADO → clic en Y={int(y_click)}")
                self.click_target(y_click, img_bgr=img_bgr, log_dir=log_dir, base_name=_log_base_name)
                return True, ''

            # ── NIVEL 2: Verificación LLM (todos los modelos) ───────────────────
            logger.info("⚠️ No hubo match local. Consultando LLM (se probarán todos los modelos)...")
            is_match_llm = self.call_llm_text_verification(ocr_text_candidate, target_diag)
            
            if is_match_llm:
                logger.info(f"✅ MATCH LLM CONFIRMADO → clic en Y={int(y_click)}")
                self.click_target(y_click, img_bgr=img_bgr, log_dir=log_dir, base_name=_log_base_name)
                return True, ''
            else:
                logger.info("❌ LLM rechazó el candidato.")

        logger.warning("Ningún candidato coincidió con el diagnóstico.")
        # Retornar False + el texto del primer candidato (para mostrarlo al usuario)
        best_ocr = candidates[0].get('full_text', '') if candidates else ''
        return False, best_ocr

    def click_target(self, y_click, img_bgr=None, log_dir=None, base_name=None):
        """
        Hace clic en el centro de la fila candidata detectada.
        y_click = y_center (promedio de centros de palabras OCR de la fila).
        Es más estable que (y_min + y_max)/2 de los bounds (propenso a drift por escalado 3x).
        """
        # Coordenada base calculada a partir de la fila detectada por OCR
        screen_x = int(self.region[0] + (self.region[2] / 2))
        screen_y = int(self.region[1] + y_click)
        
        # Actualizar BBDD con la coordenada encontrada
        self.update_db_coordinate(f"{screen_x},{screen_y}")
        
        logger.info(f"--- Iniciando secuencia de clic HUMANIZADA en: {screen_x}, {screen_y} ---")

        # Guardar imagen de log con punto de clic anotado
        if img_bgr is not None and log_dir is not None:
            self.save_click_log_image(
                img_bgr=img_bgr,
                click_x_in_region=int(self.region[2] // 2),
                click_y_in_region=int(y_click),
                screen_x=screen_x,
                screen_y=screen_y,
                log_dir=log_dir,
                base_name=base_name or datetime.now().strftime("%Y-%m-%d %H-%M-%S")
            )

        # 1. Click Secundario (Humanizado)
        if self.vf: self.vf.highlight_click(screen_x, screen_y)
        
        # Mover suavemente al objetivo
        pyautogui.moveTo(screen_x, screen_y, duration=0.5, tween=pyautogui.easeInOutQuad)
        time.sleep(0.1)
        
        # Click manual (Right) con pulsación sostenida breve
        pyautogui.mouseDown(button='right')
        time.sleep(0.15)
        pyautogui.mouseUp(button='right')
        logger.info(f"Click secundario (Derecho) realizado en {screen_x}, {screen_y}")

        # Esperar a que el menú contextual aparezca y se estabilice
        time.sleep(1.2)

        # 2. Combinación de teclas Ctrl+D
        pyautogui.hotkey('ctrl', 'd')
        logger.info("Combinación Ctrl+D ejecutada")
        time.sleep(5)

    def save_detection_log_image(self, img_bgr, rows_data, candidates, log_dir, base_name):
        """Guarda imagen con franjas coloreadas mostrando las filas detectadas por OCR.
        
        - Amarillo semitransparente: todas las filas detectadas por OCR
        - Verde semitransparente:    filas candidatas (tienen Fecha + Estado Hecho)
        - Texto blanco:              texto OCR de cada fila anotado a la derecha
        """
        try:
            img_log = img_bgr.copy()
            overlay = img_bgr.copy()
            h, w = img_log.shape[:2]
            half_h = self.CROP_HEIGHT // 2

            # Conjunto de y_centers de candidatos para distinguirlos
            cand_y_centers = set(int(c['y_center']) for c in candidates)

            # --- Dibujar franjas para TODAS las filas detectadas ---
            for row in rows_data:
                y_c = int(row['y_center'])
                # Usar bounds reales si están disponibles, si no CROP_HEIGHT
                all_ymins = [i['bounds']['y_min'] for i in row['items'] if 'bounds' in i]
                all_ymaxs = [i['bounds']['y_max'] for i in row['items'] if 'bounds' in i]
                if all_ymins and all_ymaxs:
                    y1 = max(0, int(min(all_ymins)) - 2)
                    y2 = min(h, int(max(all_ymaxs)) + 2)
                else:
                    y1 = max(0, y_c - half_h)
                    y2 = min(h, y_c + half_h)
                row_items = sorted(row['items'], key=lambda x: x['center']['x'])
                row_text = " ".join([i['text'] for i in row_items])[:80]

                is_candidate = any(abs(y_c - cy) < self.ROW_TOLERANCE for cy in cand_y_centers)

                if is_candidate:
                    # Verde para candidatos confirmados
                    cv2.rectangle(overlay, (0, y1), (w, y2), (0, 200, 50), -1)
                else:
                    # Amarillo tenue para filas normales
                    cv2.rectangle(overlay, (0, y1), (w, y2), (0, 200, 220), -1)

                # Texto de la fila anotado
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.42
                text_color = (0, 0, 0)
                cv2.putText(img_log, row_text, (4, y2 - 4), font, font_scale, (255, 255, 255), 3, cv2.LINE_AA)
                cv2.putText(img_log, row_text, (4, y2 - 4), font, font_scale, text_color, 1, cv2.LINE_AA)

            # Mezclar overlay con transparencia
            alpha = 0.25
            cv2.addWeighted(overlay, alpha, img_log, 1 - alpha, 0, img_log)

            # --- Redibujar textos ENCIMA (para que queden sobre el overlay mezclado) ---
            for row in rows_data:
                y_c = int(row['y_center'])
                all_ymaxs2 = [i['bounds']['y_max'] for i in row['items'] if 'bounds' in i]
                y2_text = min(h, int(max(all_ymaxs2)) + 2) if all_ymaxs2 else min(h, y_c + half_h)
                row_items = sorted(row['items'], key=lambda x: x['center']['x'])
                row_text = " ".join([i['text'] for i in row_items])[:80]
                is_candidate = any(abs(y_c - cy) < self.ROW_TOLERANCE for cy in cand_y_centers)
                label_color = (0, 80, 0) if is_candidate else (80, 60, 0)
                cv2.putText(img_log, row_text, (4, y2_text - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255,255,255), 3, cv2.LINE_AA)
                cv2.putText(img_log, row_text, (4, y2_text - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.42, label_color, 1, cv2.LINE_AA)

            # --- Líneas de borde para cada franja candidata (verde brillante) ---
            for cand in candidates:
                y_c = int(cand['y_center'])
                # Usar bounds reales del candidato
                all_cy_mins = [i['bounds']['y_min'] for i in cand['items'] if 'bounds' in i]
                all_cy_maxs = [i['bounds']['y_max'] for i in cand['items'] if 'bounds' in i]
                y1 = max(0, int(min(all_cy_mins)) - 2) if all_cy_mins else max(0, y_c - half_h)
                y2 = min(h, int(max(all_cy_maxs)) + 2) if all_cy_maxs else min(h, y_c + half_h)
                y_click_in_img = int(cand.get('y_click', y_c))
                cv2.rectangle(img_log, (0, y1), (w - 1, y2), (0, 255, 80), 2)
                # Línea punteada en el punto de clic
                cv2.line(img_log, (0, y_click_in_img), (w, y_click_in_img), (0, 200, 80), 1)
                # Etiqueta con coordenadas del clic
                click_label = f"CANDIDATO | clic Y={y_click_in_img}"
                cv2.putText(img_log, click_label, (w - 230, y_click_in_img - 3),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 80), 2, cv2.LINE_AA)

            # Marco general rojo
            cv2.rectangle(img_log, (0, 0), (w - 1, h - 1), (0, 0, 220), 3)

            # Leyenda
            cv2.rectangle(img_log, (0, 0), (280, 20), (0, 0, 0), -1)
            cv2.putText(img_log, "AMARILLO=fila OCR  VERDE=candidato",
                        (4, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)

            out_path = log_dir / f"{base_name}_FRANJAS.png"
            cv2.imwrite(str(out_path), img_log)
            logger.info(f"🗺️ Log con franjas OCR guardado: {out_path}")
        except Exception as e:
            logger.warning(f"No se pudo guardar imagen de franjas OCR: {e}")

    def save_click_log_image(self, img_bgr, click_x_in_region, click_y_in_region,
                             screen_x, screen_y, log_dir, base_name):
        """Guarda imagen marcando el punto de clic con cruceta, círculo y coordenadas."""
        try:
            img_click = img_bgr.copy()
            h, w = img_click.shape[:2]
            cx = int(click_x_in_region)
            cy = int(click_y_in_region)

            # Franja horizontal de la fila del clic
            half_h = self.CROP_HEIGHT // 2
            y1 = max(0, cy - half_h)
            y2 = min(h, cy + half_h)
            overlay = img_click.copy()
            cv2.rectangle(overlay, (0, y1), (w, y2), (0, 50, 255), -1)
            cv2.addWeighted(overlay, 0.3, img_click, 0.7, 0, img_click)

            # Cruceta
            cross_color = (0, 0, 255)
            cv2.line(img_click, (0, cy), (w, cy), cross_color, 1)
            cv2.line(img_click, (cx, 0), (cx, h), cross_color, 1)

            # Círculo en el punto de clic
            cv2.circle(img_click, (cx, cy), 14, (0, 0, 255), 2)
            cv2.circle(img_click, (cx, cy), 4,  (0, 0, 255), -1)

            # Texto con coordenadas de PANTALLA (absolutas)
            coord_text = f"CLIC ({screen_x}, {screen_y})"
            font = cv2.FONT_HERSHEY_SIMPLEX
            # Posicionar el texto cerca del punto, evitando bordes
            tx = min(cx + 18, w - 180)
            ty = max(cy - 10, 16)
            # Sombra
            cv2.putText(img_click, coord_text, (tx, ty), font, 0.55, (255, 255, 255), 4, cv2.LINE_AA)
            # Texto principal
            cv2.putText(img_click, coord_text, (tx, ty), font, 0.55, (0, 0, 200), 1, cv2.LINE_AA)

            # Texto adicional con coordenadas relativas a la región
            rel_text = f"(region rel: {cx},{cy})"
            cv2.putText(img_click, rel_text, (tx, ty + 18), font, 0.4, (255, 255, 255), 3, cv2.LINE_AA)
            cv2.putText(img_click, rel_text, (tx, ty + 18), font, 0.4, (0, 0, 160), 1, cv2.LINE_AA)

            # Marco general
            cv2.rectangle(img_click, (0, 0), (w - 1, h - 1), (0, 0, 200), 3)

            out_path = log_dir / f"{base_name}_CLIC.png"
            cv2.imwrite(str(out_path), img_click)
            logger.info(f"🎯 Log con punto de clic guardado: {out_path}  [screen=({screen_x},{screen_y}) | region=({cx},{cy})]")
        except Exception as e:
            logger.warning(f"No se pudo guardar imagen de clic: {e}")

def main():
    setup_logging()

    while True:
        # Inicializar el objeto en cada ciclo para un reinicio limpio "desde cero"
        search = BusquedaTextOnly()

        # --- PASO PREVIO: Buscar en sinónimos antes de ejecutar ---
        # Obtenemos el diagnóstico actual de BD para consultar sinónimos
        target_diag_raw, _ = search.get_db_targets()
        override_diag = None
        last_ocr_text = ""

        if target_diag_raw:
            sinonimo = search.buscar_sinonimo(target_diag_raw, "")
            if sinonimo:
                logger.info(f"📚 Sinónimo hall ado en BD: '{sinonimo}'. Se usará en lugar de '{target_diag_raw}'.")
                override_diag = sinonimo

        # Intentar ejecutar con reintentos automáticos configurados
        found = False
        for attempt in range(search.MAX_RETRIES + 1):
            attempt_num = attempt + 1
            logger.info(f"{'='*60}")
            logger.info(f"INTENTO {attempt_num} DE {search.MAX_RETRIES + 1}")
            logger.info(f"{'='*60}")

            try:
                result, last_ocr_text = search.execute(override_diag=override_diag)

                if result:
                    logger.info("✅ Proceso completado exitosamente")
                    found = True
                    break
                else:
                    if attempt < search.MAX_RETRIES:
                        logger.warning(f"⚠️ Intento {attempt_num} falló. Reintentando...")
                        time.sleep(2)
            except Exception as e:
                logger.error(f"Error durante ejecución: {e}", exc_info=True)
                if attempt < search.MAX_RETRIES:
                    time.sleep(2)

        if found:
            sys.exit(0)

        # ── Si todos los reintentos automáticos fallaron, terminar con error ──────────────────
        logger.warning("⚠️ Todos los reintentos fallaron. Notificando y terminando.")
        error_msg = f"Búsqueda fallida: no se encontró '{target_diag_raw}' (OCR detectó: '{last_ocr_text}') tras {search.MAX_RETRIES + 1} intentos."
        
        _error_handler_llamado = False
        for _mod in ['utils.error_handler', 'rpa_framework.utils.error_handler']:
            try:
                import importlib
                _eh = importlib.import_module(_mod)
                _eh.handle_error_and_exit("busqueda_triple_text_only.py", error_msg)
                _error_handler_llamado = True
                break
            except Exception as _e:
                logger.warning(f"No se pudo importar {_mod}: {_e}")
        
        if not _error_handler_llamado:
            try:
                enviar_alerta_todos(f"❌ <b>Búsqueda Fallida</b>\n{error_msg}")
            except: pass
            search.update_db_error(error_msg)
            sys.exit(1)

if __name__ == "__main__":
    main()
