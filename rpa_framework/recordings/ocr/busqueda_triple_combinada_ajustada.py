#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script: busqueda_triple_combinada_ajustada.py
Descripción: Script de búsqueda ajustada que:
1. Busca "Examen Hecho" + Fecha en toda la imagen.
2. Itera sobre los candidatos encontrados.
3. Realiza un recorte de 20px de alto centrado en cada candidato.
4. Intenta validar Diagnóstico en el recorte con Tesseract + RapidFuzz.
5. Si falla el OCR local, envía el recorte + texto OCR + objetivo al LLM (Nemotron) para validación semántica.

Ubicación: rpa_framework/recordings/ocr/busqueda_triple_combinada_ajustada.py
"""

import sys
import logging
import json
import base64
import cv2
import pyautogui
import numpy as np
import requests
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Tuple, List
from difflib import SequenceMatcher

# Imports condicionales
try:
    import pytesseract
except ImportError:
    pass

try:
    from rapidfuzz import fuzz, process
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
MODEL_ID = "nvidia/nemotron-nano-12b-v2-vl:free"

class BusquedaAjustada:
    def __init__(self):
        self.ocr_engine = OCREngine(engine='tesseract', language='es', use_gpu=False, confidence_threshold=0.05)
        self.region = (190, 70, 1900, 650)
        self.ROW_TOLERANCE = 15
        self.CROP_HEIGHT = 20  # Altura fija de recorte (20px)

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

    def similarity(self, a, b):
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    def agrupar_por_filas(self, results):
        rows_data = []
        for item in results:
            y_item = item['center']['y']
            matched = False
            for row in rows_data:
                if abs(row['y_center'] - y_item) < self.ROW_TOLERANCE:
                    row['items'].append(item)
                    row['y_center'] = sum([i['center']['y'] for i in row['items']]) / len(row['items'])
                    matched = True
                    break
            if not matched:
                rows_data.append({'y_center': y_item, 'items': [item]})
        return rows_data

    def preprocess_image(self, img_bgr):
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        denoised = cv2.medianBlur(thresh, 3)
        return denoised

    def execute_ocr_basic(self, img_bgr, psm=6):
        """Ejecuta OCR básico."""
        scale_factor = 2
        img_resized = cv2.resize(img_bgr, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)
        img_processed = self.preprocess_image(img_resized)
        
        custom_config = f'--psm {psm} -l spa'
        try:
            # Obtener string directo para busquedas simples
            text = pytesseract.image_to_string(img_processed, config=custom_config)
            return text.strip()
        except Exception as e:
            logger.error(f"Error en OCR Basic: {e}")
            return ""

    def execute_ocr_data(self, img_bgr):
        """Devuelve datos estructurados de OCR (cajas)."""
        scale_factor = 2
        img_resized = cv2.resize(img_bgr, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)
        img_processed = self.preprocess_image(img_resized)
        
        all_results = []
        custom_config = r'--psm 6 -l spa'
        
        try:
            ocr_data = pytesseract.image_to_data(img_processed, config=custom_config, output_type=pytesseract.Output.DICT)
            n_boxes = len(ocr_data['text'])
            for i in range(n_boxes):
                confidence = float(ocr_data['conf'][i])
                text = ocr_data['text'][i].strip()
                if confidence > 5 and text:
                    x, y, w, h = (ocr_data['left'][i], ocr_data['top'][i],
                                 ocr_data['width'][i], ocr_data['height'][i])
                    result = {
                        'text': text,
                        'confidence': confidence,
                        'center': {
                            'x': (x + w/2) / scale_factor,
                            'y': (y + h/2) / scale_factor
                        }
                    }
                    all_results.append(result)
        except Exception as e:
            logger.error(f"Error OCR Data: {e}")
            
        return all_results

    def get_crop_image(self, full_img, y_center):
        """Obtiene un recorte de 20px de alto centrado en y_center."""
        h, w = full_img.shape[:2]
        half_h = self.CROP_HEIGHT // 2
        
        y_start = int(max(0, y_center - half_h))
        y_end = int(min(h, y_center + half_h))
        
        # El ancho es todo el ancho de la region
        return full_img[y_start:y_end, 0:w]

    # --- LLM FUNCTIONS ---
    def encode_image_to_base64(self, img_bgr: np.ndarray) -> str:
        _, buffer = cv2.imencode('.png', img_bgr)
        return base64.b64encode(buffer).decode('utf-8')

    def call_nemotron_verification(self, crop_img, target_diag, ocr_text):
        """Consulta al LLM si el texto/imagen coincide con el diagnóstico."""
        logger.info("🤖 Consultando a Nemotron (Validación)...")
        
        img_base64 = self.encode_image_to_base64(crop_img)
        
        prompt = f"""
Eres un experto validando datos médicos en capturas de pantalla de baja calidad.
TU TAREA: Determinar si la imagen recortada (y el texto detectado por OCR) corresponde al examen médico buscado.

EXAMEN BUSCADO: "{target_diag}"
TEXTO DETECTADO POR OCR (REFERENCIA): "{ocr_text}"

CRITERIOS DE COINCIDENCIA (SEMÁNTICA) - ¡MUY IMPORTANTE!:
1. EQUIVALENCIAS DE TIPO DE EXAMEN (SON LO MISMO):
   - "Ultrasonido" == "Ecotomografia" == "Eco" == "US"
   - "Radiografia" == "Rx" == "Rayos X"
   - "Scanner" == "TC" == "Tomografia"
   - "Resonancia" == "RM" == "RMN"
2. EQUIVALENCIAS ANATÓMICAS (ZONAS RELACIONADAS):
   - "Torax" o "Toracica" INCLUYE region "Dorsal" o "Espalda".
   - "Abdomen" puede incluir "Pelvis" en ciertos contextos generales.
   - "Mano", "Muñeca", "Codo" son "Extremidad Superior".
3. Acepta ABREVIATURAS COMUNES (ej: "Abd" = "Abdomen", "Ext" = "Extremidades", "Bilat" = "Bilateral").
4. IGNORA TEXTO IRRELEVANTE: Nombres de pacientes, fechas, estados ("Examen Hecho"), o códigos internos.
5. Céntrate en la INTENCIÓN CLINICA: ¿Es el mismo estudio sobre la misma zona corporal? --> SI = Match.

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
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
                            ]
                        }
                    ],
                    "temperature": 0.0,
                    "max_tokens": 500,
                },
                timeout=20
            )
            response.raise_for_status()
            result = response.json()
            content = result['choices'][0]['message'].get('content', '')
            
            # Parse JSON
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                return data.get('es_match', False)
            return False
            
        except Exception as e:
            logger.error(f"Error LLM Verification: {e}")
            return False

    def execute(self):
        logger.info(">>>> INICIANDO BÚSQUEDA AJUSTADA (Hybrid) <<<<")
        
        # 1. Obtener Targets
        target_diag, target_fecha_obj = self.get_db_targets()
        if not target_diag:
            return False
            
        target_fecha_str = target_fecha_obj.strftime("%d-%m-%Y")
        logger.info(f"Buscando: [{target_fecha_str}] + [Examen Hecho] + [{target_diag}]")

        # 2. Captura Inicial
        screenshot = pyautogui.screenshot(region=self.region)
        img_np = np.array(screenshot)
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

        # Guardar imagen para log (Igual que busqueda_triple_combinada.py)
        try:
            log_dir = Path("rpa_framework/log/busqueda triple")
            log_dir.mkdir(parents=True, exist_ok=True)
            
            now_str = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
            diag_clean = "".join([c if c.isalnum() else "_" for c in target_diag])[:30]
            filename = f"{now_str} {diag_clean} {target_fecha_str}_ajustada.png"
            filepath = log_dir / filename
            cv2.imwrite(str(filepath), img_bgr)
            logger.info(f"Imagen de log guardada en: {filepath}")
        except Exception as e:
            logger.error(f"Error guardando imagen de log: {e}")
        
        # 3. OCR General para encontrar candidatos (Fecha + Estado)
        # Usamos psm 4 o 6 para tener bloques de texto o lineas
        ocr_results = self.execute_ocr_data(img_bgr)
        rows_data = self.agrupar_por_filas(ocr_results)
        
        candidates = []
        
        TARGET_ESTADO = "examen hecho" # o simplemente "hecho"
        
        for row in rows_data:
            # Reconstruir texto de la fila ordenado por X
            row_items = sorted(row['items'], key=lambda x: x['center']['x'])
            row_text = " ".join([i['text'] for i in row_items])
            row_norm = self.normalize_text(row_text)
            
            # Verificar Fecha Y Estado
            # Fecha match simple
            has_date = (target_fecha_str in row_text.replace(" ", "") or 
                        self.similarity(target_fecha_str, row_text) > 0.7) # Un poco laxo
            
            # Estado match
            has_estado = "hecho" in row_norm or "realizado" in row_norm
            
            if has_date and has_estado:
                candidates.append(row)
                
        logger.info(f"Candidatos iniciales (Fecha + Estado): {len(candidates)}")
        
        if not candidates:
            # Fallback: Intentar buscar SOLO "Examen Hecho" si la fecha falla mucho?
            # Por ahora retornamos Fail
            logger.warning("No se encontraron filas con Fecha y Estado 'Hecho'.")
            return False

        # 4. Iterar Candidatos y Verificar Diagnóstico
        for idx, cand in enumerate(candidates):
            y_center = cand['y_center']
            logger.info(f"--- Verificando Candidato #{idx+1} (Y={y_center}) ---")
            
            # A. Recorte 20px
            crop_img = self.get_crop_image(img_bgr, y_center)
            
            # Guardar debug crop
            try:
                cv2.imwrite(f"rpa_framework/log/debug_crop_{idx}.png", crop_img)
            except: pass
            
            # B. OCR en Crop (Tesseract)
            ocr_text_crop = self.execute_ocr_basic(crop_img, psm=6) # 7 = single text line
            logger.info(f"Texto OCR en Crop: '{ocr_text_crop}'")
            
            ocr_norm = self.normalize_text(ocr_text_crop)
            target_norm = self.normalize_text(target_diag)
            
            # C. Verificación Local (Fuzzy)
            is_match_local = False
            if fuzz.partial_ratio(target_norm, ocr_norm) > 85 or \
               fuzz.token_set_ratio(target_norm, ocr_norm) > 85:
                is_match_local = True
                logger.info("✅ MATCH LOCAL CONFIRMADO")
            
            if is_match_local:
                # Click
                screen_x = int(self.region[0] + (self.region[2]/2)) # Click al centro X aprox
                screen_y = int(self.region[1] + y_center)
                pyautogui.click(screen_x, screen_y, button='right')
                logger.info(f"Click secundario realizado en {screen_x}, {screen_y}")
                return True
            
            # D. Verificación LLM (Fallback)
            logger.info("⚠️ No hubo match local claro. Consultando LLM...")
            is_match_llm = self.call_nemotron_verification(crop_img, target_diag, ocr_text_crop)
            
            if is_match_llm:
                logger.info("✅ MATCH LLM CONFIRMADO")
                screen_x = int(self.region[0] + (self.region[2]/2))
                screen_y = int(self.region[1] + y_center)
                pyautogui.click(screen_x, screen_y, button='right')
                logger.info(f"Click secundario realizado en {screen_x}, {screen_y}")
                return True
            else:
                logger.info("❌ LLM rechazó el candidato.")

        logger.warning("Ningún candidato coincidió con el diagnóstico.")
        return False

def main():
    setup_logging()
    search = BusquedaAjustada()
    search.execute()

if __name__ == "__main__":
    main()
