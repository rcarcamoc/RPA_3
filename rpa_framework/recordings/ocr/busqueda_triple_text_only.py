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

logger = logging.getLogger(__name__)

# Configuración LLM
OPENROUTER_API_KEY = "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"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MODEL_ID = "tngtech/deepseek-r1t2-chimera:free"

class BusquedaTextOnly:
    def __init__(self):
        self.ocr_engine = OCREngine(engine='tesseract', language='es', use_gpu=False, confidence_threshold=0.05)
        # Ampliamos región horizontal para asegurar captura completa (0 a 1920)
        self.region = (0, 180, 1920, 1000)
        self.ROW_TOLERANCE = 25  # Aumentado de 15 a 25 para mayor robustez
        self.CROP_HEIGHT = 30  # Altura de recorte un poco mayor

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
        """Ejecuta OCR con pre-procesamiento avanzado."""
        # A. Redimensionar con interpolación de alta calidad (LANCZOS4)
        # Factor 3x para que caracteres de 20px pasen a 60px (ideal para Tesseract)
        scale_factor = 3
        img_resized = cv2.resize(img_bgr, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_LANCZOS4)
        
        # B. Aplicar un filtro de "Sharpening" (Afilado)
        sharpen_kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
        img_sharp = cv2.filter2D(img_resized, -1, sharpen_kernel)
        
        # C. Procesamiento de imagen
        img_processed = self.preprocess_image(img_sharp)
        
        # D. Añadir PADDING (Margen Blanco)
        # Tesseract detecta mucho mejor si hay espacio alrededor del texto
        border = 20
        img_padded = cv2.copyMakeBorder(img_processed, border, border, border, border, 
                                        cv2.BORDER_CONSTANT, value=[255, 255, 255])
        
        custom_config = f'--psm {psm} -l spa --oem 3'
        try:
            text = pytesseract.image_to_string(img_padded, config=custom_config)
            return text.strip()
        except Exception as e:
            logger.error(f"Error en OCR Basic: {e}")
            return ""

    def execute_ocr_data(self, img_bgr):
        """Devuelve datos estructurados de OCR (cajas) con pre-procesamiento optimizado."""
        scale_factor = 3
        img_resized = cv2.resize(img_bgr, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_LANCZOS4)
        
        # Convertir a escala de grises y aplicar CLAHE para mejorar contraste local
        gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        gray = clahe.apply(gray)
        
        # Binarización adaptativa o simple (Tesseract 5 prefiere grises pero binario ayuda en fondos complejos)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Añadir Padding (Margen blanco) para ayudar a Tesseract con bordes
        border = 40
        img_padded = cv2.copyMakeBorder(thresh, border, border, border, border, 
                                        cv2.BORDER_CONSTANT, value=[255, 255, 255])
        
        all_results = []
        # PSM 3 (Auto) es más robusto para capturar toda la extensión de líneas en tablas
        custom_config = r'--psm 3 -l spa'
        
        try:
            ocr_data = pytesseract.image_to_data(img_padded, config=custom_config, output_type=pytesseract.Output.DICT)
            n_boxes = len(ocr_data['text'])
            for i in range(n_boxes):
                text = ocr_data['text'][i].strip()
                if text:
                    confidence = float(ocr_data['conf'][i])
                    # Ajustar coordenadas por el padding y el scale_factor
                    x = ocr_data['left'][i] - border
                    y = ocr_data['top'][i] - border
                    w = ocr_data['width'][i]
                    h = ocr_data['height'][i]
                    
                    result = {
                        'text': text,
                        'confidence': confidence,
                        'center': {
                            'x': (x + w/2) / scale_factor,
                            'y': (y + h/2) / scale_factor
                        }
                    }
                    all_results.append(result)
            logger.info(f"OCR detectó {len(all_results)} palabras en la imagen.")
        except Exception as e:
            logger.error(f"Error OCR Data: {e}")
            
        return all_results

    def get_crop_image(self, full_img, y_center):
        h, w = full_img.shape[:2]
        half_h = self.CROP_HEIGHT // 2
        y_start = int(max(0, y_center - half_h))
        y_end = int(min(h, y_center + half_h))
        return full_img[y_start:y_end, 0:w]

    # --- LLM FUNCTIONS ---
    def call_llm_text_verification(self, ocr_text, target_diag):
        """Consulta al LLM si el texto encontrado coincide semánticamente con el objetivo."""
        logger.info("="*50)
        logger.info(f"🤖 Preparando consulta a LLM ({MODEL_ID})...")
        logger.info(f"🎯 TARGET BUSCADO: '{target_diag}'")
        logger.info(f"📝 TEXTO OCR ENVIADO: '{ocr_text}'")
        logger.info("="*50)
        
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
        try:
            response = requests.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://rpa-framework.local"
                },
                json={
                    "model": MODEL_ID,
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
            response.raise_for_status()
            result = response.json()
            content = result['choices'][0]['message'].get('content', '')
            
            logger.info(f"Respuesta Raw LLM: {content[:200]}...") # Log parcial para debug
            
            # Parse JSON - Intenta buscar el bloque JSON dentro de la respuesta
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                return data.get('es_match', False)
            
            # Fallback simple si responde solo texto "true" o similar
            if "true" in content.lower() and "match" in content.lower():
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error LLM Verification: {e}")
            return False

    def execute(self):
        logger.info(">>>> INICIANDO BÚSQUEDA TEXT-ONLY (DeepSeek) <<<<")
        
        # 1. Obtener Targets
        target_diag, target_fecha_obj = self.get_db_targets()
        if not target_diag:
            return False
            
        target_fecha_str = target_fecha_obj.strftime("%d-%m-%Y")
        logger.info(f"Buscando: [{target_fecha_str}] + [Hecho] + [{target_diag}]")

        # 2. Captura Inicial
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
            cv2.imwrite(str(log_dir / filename), img_bgr)
        except Exception: pass
        
        # 3. OCR General (Fecha + Estado)
        ocr_results = self.execute_ocr_data(img_bgr)
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
                logger.info(f"Candidato encontrado (Digits: {has_date_digits}, Score Fecha: {score_date}, Score Estado: {max(score_hecho, score_realizado)}): {row_text}")
                
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
        screen_x = int(self.region[0] + (self.region[2]/2))
        screen_y = int(self.region[1] + y_center)
        pyautogui.click(screen_x, screen_y, button='right')
        logger.info(f"Click secundario realizado en {screen_x}, {screen_y}")

        # Nuevo click offset 50, 215
        new_x = screen_x + 50
        new_y = screen_y + 215
        pyautogui.click(new_x, new_y, button='left')
        logger.info(f"Click izquierdo realizado en {new_x}, {new_y}")

def main():
    setup_logging()
    search = BusquedaTextOnly()
    search.execute()

if __name__ == "__main__":
    main()
