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

# Importar utilidades de preprocesamiento
try:
    from recordings.ocr.utilidades.preproceso_ocr import preprocess_high_fidelity, normalize_coordinates
    HAS_PREPROCESS_UTILS = True
except ImportError:
    HAS_PREPROCESS_UTILS = False

logger = logging.getLogger(__name__)

# Configuración LLM
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    logger.error("OPENROUTER_API_KEY no está configurada en el archivo .env")
    sys.exit(1)
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MODEL_ID = "tngtech/deepseek-r1t2-chimera:free"


time.sleep(2) # Dar tiempo para ocultar esta ventana

class BusquedaTextOnly:
    def __init__(self):
        # Inicializar motor OCR (sin preproceso interno para hacerlo manualmente y tener control total)
        self.ocr_engine = OCREngine(
            engine='tesseract', 
            language='spa', 
            use_gpu=False, 
            confidence_threshold=0.05,
            preprocess=False, # Lo haremos manualmente
            custom_config='--psm 3'
        )
        # Región ajustada: Comienza en (180, 180) y llega hasta (1900, 1000)
        # Formato: (left, top, width, height)
        self.region = (100, 100, 1720, 820)
        self.ROW_TOLERANCE = 15  # Aumentado de 15 a 25 para mayor robustez
        self.CROP_HEIGHT = 30  # Altura de recorte un poco mayor
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
    def call_llm_text_verification(self, ocr_text, target_diag):
        """
        Consulta al LLM si el texto encontrado coincide semánticamente con el objetivo.
        Implementa fallback entre varios modelos gratuitos si falla uno.
        """
        models = [
            "tngtech/deepseek-r1t2-chimera:free",
            "openai/gpt-oss-120b:free",
            "arcee-ai/trinity-large-preview:free",
            "deepseek/deepseek-r1-0528:free"
        ]
        
        prompt = f"""
Eres un experto clínico en interpretación de terminología radiológica y exámenes de imagen.
Tu rol es determinar si dos textos diagnósticos describen el MISMO EXAMEN, aunque estén escritos de forma diferente por diferentes tecnólogos, médicos o centros.

NO DEPENDES de una lista rígida de sinónimos. En su lugar, aplicarás RAZONAMIENTO CLÍNICO Y SEMÁNTICO.

---

## TAREA
1. **EXTRACCIÓN**: Identifica dentro del texto "ENCONTRADO" el segmento que corresponde al NOMBRE DEL EXAMEN. Ignora nombres de pacientes (ej: "Javiera..."), edades ("23a"), fechas ("30-12-2025") y estados ("Examen Hecho", "Normal").
2. **COMPARACIÓN**: Compara ese segmento extraído con el "BUSCADO".

BUSCADO: "{target_diag}"
ENCONTRADO (Línea completa OCR): "{ocr_text}"

---

## MARCO DE ANÁLISIS

1. **MODALIDAD TÉCNICA** (tipo de examen)
   - Ultrasonido ≈ Ecotomografía ≈ Eco ≈ US
   - Radiografía ≈ Rx
   - Clave: ¿El segmento extraído describe el mismo método físico?

2. **REGIÓN ANATÓMICA**
   - Dorsal ≈ Espalda ≈ Torácica Posterior
   - Torácica ≈ Tórax
   - Clave: ¿La zona es anatómicamente equivalente?
   - IMPORTANTE: "Torácica" puede implicar "Dorsal" si es columna o partes blandas posteriores.

---

## PROCESO DE RAZONAMIENTO (Cadena de Pensamiento)

1. **Segmento Candidato en OCR**: [Escribe aquí SOLO la parte del texto OCR que parece ser el examen, ej: "Ecotomografña Partes Blandas Toracica"]
2. **Análisis de Equivalencia**:
   - Modalidad: ¿"Ecotomografña" (OCR) equivale a "Ultrasonido" (Target)? -> SI/NO
   - Región: ¿"Toracica" (OCR) cubre la intención de "Dorsal derecha" (Target)? -> SI/NO
   - Nota: Acepta errores de OCR en el segmento (ej: ñ por í, espacios extra).


4. **Evaluación de Similitud**:
   - Si TODOS los componentes principales coinciden → es_match: true
   - Si componentes principales NO coinciden → es_match: false
   - IMPORTANTE: El texto ENCONTRADO proviene de OCR y puede tener errores de lectura en acentos y caracteres especiales (ej: "Ecotomografña" en lugar de "Ecotomografía", o "Toracica" por "Torácica"). Debes ser permisivo con estos errores tipográficos de OCR.
   - Si hay AMBIGÜEDAD (ej: región implícita, falta claridad):
     * Evalúa en favor del match SI el contexto clínico lo permite
     * Indica el grado de confianza en el razonamiento

RESPONDE SOLO EN FORMATO JSON:
{{
  "es_match": true o false,
  "razonamiento": "Explicación detallada de la equivalencia encontrada (o falta de ella)",
  "confianza": 0-1 (float)
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
                            "messages": [
                                {
                                    "role": "user",
                                    "content": prompt
                                }
                            ],
                            "temperature": 0.0,
                            "max_tokens": 800,
                        },
                        timeout=30
                    )
                    
                    if response.status_code == 429:
                        logger.warning(f"⚠️ Modelo {current_model} devolvió 429 (Límite excedido). Probando siguiente...")
                        continue
                        
                    response.raise_for_status()
                    result = response.json()
                    content = result['choices'][0]['message'].get('content', '')
                    
                    logger.info(f"Respuesta Raw LLM ({current_model}): {content[:200]}...")
                    
                    # Parse JSON
                    match = re.search(r'\{.*\}', content, re.DOTALL)
                    if match:
                        data = json.loads(match.group(0))
                        # Si el modelo respondió correctamente, retornamos el resultado
                        return data.get('es_match', False)
                    
                    # Fallback simple
                    if "true" in content.lower() and "match" in content.lower():
                        return True
                    
                    # Si llegamos aquí sin retornar, es que no hubo match o no se entendió la respuesta,
                    # pero el modelo respondió. Consideramos esto como un resultado válido (False).
                    return False
                    
                except Exception as e:
                    logger.error(f"❌ Error con modelo {current_model}: {e}")
                    if current_model == models[-1]:
                        logger.error("Todos los modelos han fallado.")
                    else:
                        logger.info("Probando con el siguiente modelo de respaldo...")
                    continue
                    
            return False

        finally:
            if self.vf:
                self.vf.hide_persistent_message("llm")

    def _analyze_candidates(self, ocr_results, target_fecha_str):
        """Analiza resultados OCR y devuelve candidatos (Filas con Fecha + Estado)."""
        rows_data = self.agrupar_por_filas(ocr_results)
        candidates = []
        
        for row in rows_data:
            # Reconstruir texto de la fila ordenado por X
            row_items = sorted(row['items'], key=lambda x: x['center']['x'])
            row_text = " ".join([i['text'] for i in row_items])
            row_norm = self.normalize_text(row_text)
            
            # Verificar Fecha Y Estado CON FORMATO FLEXIBLE
            # 1. Normalizar fecha objetivo (solo números)
            target_fecha_digits = "".join(filter(str.isdigit, target_fecha_str)) # 29012026
            
            # Limpiar texto fila para búsqueda de fecha (quitar espacios y símbolos excepto / - .)
            # Simplemente quitamos todo lo que no sea numero para el check de digitos
            row_digits = "".join(filter(str.isdigit, row_text))

            # Check A: Fecha exacta en bloque (permite 29-01-2026 o 29/01/2026)
            has_date_literal = (target_fecha_str in row_text) or (target_fecha_str.replace("-", "/") in row_text)
            
            # Check B: Match solo digitos (muy robusto a separadores basura como . , |)
            has_date_digits = target_fecha_digits in row_digits

            # Check C: Fuzzy sobre la fila completa (fallback)
            score_date = fuzz.partial_ratio(target_fecha_str, row_text)
            
            # Check D: Fuzzy Status
            score_hecho = fuzz.partial_ratio("hecho", row_norm)
            score_realizado = fuzz.partial_ratio("realizado", row_norm)
            
            has_date = has_date_literal or has_date_digits or (score_date > 80)
            has_estado = (score_hecho > 80) or (score_realizado > 80)
            
            # Guardamos el texto completo en el candidato para usarlo despues
            row['full_text'] = row_text

            if has_date and has_estado:
                candidates.append(row)
                logger.info(f"✅ Candidato encontrado (Digits: {has_date_digits}, Score Fecha: {score_date}, Score Estado: {max(score_hecho, score_realizado)}): {row_text}")
                
        return candidates, rows_data

    def execute(self):
        logger.info(">>>> INICIANDO BÚSQUEDA TEXT-ONLY (DeepSeek) <<<<")
        
        # 1. Obtener Targets
        target_diag, target_fecha_obj = self.get_db_targets()
        if not target_diag:
            return False
            
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

        # Log visual
        try:
            log_dir = Path("rpa_framework/log/busqueda triple")
            log_dir.mkdir(parents=True, exist_ok=True)
            now_str = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
            diag_clean = "".join([c if c.isalnum() else "_" for c in target_diag])[:30]
            filename = f"{now_str} {diag_clean} {target_fecha_str}_TEXT.png"
            
            # Crear una copia para el log con un recuadro rojo que resalte la zona
            img_log = img_bgr.copy()
            cv2.rectangle(img_log, (0, 0), (img_log.shape[1]-1, img_log.shape[0]-1), (0, 0, 255), 3)
            cv2.imwrite(str(log_dir / filename), img_log)
        except Exception as e: 
            logger.warning(f"No se pudo guardar el log visual: {e}")
        
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
        
        if not candidates:
            logger.warning("No se encontraron filas con Fecha y Estado 'Hecho' en ninguno de los intentos.")
            
            # DEBUG: Imprimir qué está viendo para diagnóstico
            logger.info("=== DEBUG: Contenido de filas detectadas (Último intento) ===")
            for i, r in enumerate(rows_data):
                row_items = sorted(r['items'], key=lambda x: x['center']['x'])
                txt = " ".join([item['text'] for item in row_items])
                logger.info(f"Fila {i} (Y={int(r['y_center'])}): {txt}")
            logger.info("============================================")
            
            return False
                
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
            
            return False

        # 4. Iterar Candidatos y Verificar Diagnóstico
        for idx, cand in enumerate(candidates):
            y_center = cand['y_center']
            logger.info(f"--- Verificando Candidato #{idx+1} (Y={y_center}) ---")
            
            # USAR EL TEXTO YA DETECTADO (Más robusto que re-hacer OCR con recorte)
            # El paso anterior ya demostró que este texto tiene buena calidad (encontró fecha y estado)
            ocr_text_candidate = cand.get('full_text', "")
            logger.info(f"Texto OCR Candidato: '{ocr_text_candidate}'")
            
            ocr_norm = self.normalize_text(ocr_text_candidate)
            target_norm = self.normalize_text(target_diag)
            
            # Verificación Local (Fuzzy)
            if fuzz.partial_ratio(target_norm, ocr_norm) > 85 or \
               fuzz.token_set_ratio(target_norm, ocr_norm) > 85:
                logger.info("✅ MATCH LOCAL CONFIRMADO")
                self.click_target(y_center)
                return True
            
            # Verificación LLM (DeepSeek)
            logger.info("⚠️ No hubo match local claro. Consultando LLM...")
            is_match_llm = self.call_llm_text_verification(ocr_text_candidate, target_diag)
            
            if is_match_llm:
                logger.info("✅ MATCH LLM CONFIRMADO")
                self.click_target(y_center)
                return True
            else:
                logger.info("❌ LLM rechazó el candidato.")

        logger.warning("Ningún candidato coincidió con el diagnóstico.")
        return False

    def click_target(self, y_center):
        # Coordenada base calculada a partir de la fila detectada por OCR
        screen_x = int(self.region[0] + (self.region[2]/2))
        screen_y = int(self.region[1] + y_center)
        
        logger.info(f"--- Iniciando secuencia de clic HUMANIZADA en: {screen_x}, {screen_y} ---")

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

def main():
    setup_logging()
    search = BusquedaTextOnly()
    
    # Intentar ejecutar con reintentos
    for attempt in range(search.MAX_RETRIES + 1):
        attempt_num = attempt + 1
        logger.info(f"{'='*60}")
        logger.info(f"INTENTO {attempt_num} DE {search.MAX_RETRIES + 1}")
        logger.info(f"{'='*60}")
        
        try:
            result = search.execute()
            
            if result:
                logger.info("✅ Proceso completado exitosamente")
                sys.exit(0)
            else:
                if attempt < search.MAX_RETRIES:
                    logger.warning(f"⚠️ Intento {attempt_num} falló. Reintentando...")
                    time.sleep(2)  # Pausa antes de reintentar
                else:
                    # Último intento falló
                    error_msg = "No se encontró coincidencia después de reintentos"
                    logger.error(f"❌ {error_msg}")
                    
                    # Actualizar base de datos
                    search.update_db_error(error_msg)
                    
                    # Mostrar mensaje al usuario
                    if search.vf:
                        search.vf.show_persistent_message(
                            "❌ ERROR: No se encontró el examen buscado",
                            "error",
                            bg_color="#F44336",
                            fg_color="#FFFFFF"
                        )
                        time.sleep(5)  # Mostrar mensaje por 5 segundos
                        search.vf.hide_persistent_message("error")
                    
                    # Salir con código de error
                    logger.error("Cerrando ejecución con error")
                    sys.exit(1)
                    
        except Exception as e:
            logger.error(f"Error durante ejecución: {e}", exc_info=True)
            
            # Limpieza de mensajes persistentes por si acaso
            if search.vf:
                try:
                    search.vf.hide_persistent_message("ocr")
                    search.vf.hide_persistent_message("llm")
                except:
                    pass
            
            if attempt < search.MAX_RETRIES:
                logger.warning(f"⚠️ Error en intento {attempt_num}. Reintentando...")
                time.sleep(2)
            else:
                error_msg = f"Error crítico: {str(e)[:100]}"
                logger.error(f"❌ {error_msg}")
                
                # Actualizar base de datos
                search.update_db_error(error_msg)
                
                # Mostrar mensaje al usuario
                if search.vf:
                    search.vf.show_persistent_message(
                        f"❌ ERROR CRÍTICO: {str(e)[:50]}",
                        "error",
                        bg_color="#F44336",
                        fg_color="#FFFFFF"
                    )
                    time.sleep(5)
                    search.vf.hide_persistent_message("error")
                
                # Salir con código de error
                logger.error("Cerrando ejecución con error crítico")
                sys.exit(1)

if __name__ == "__main__":
    main()
