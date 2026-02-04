#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script: busqueda_triple_combinada.py
Descripción: Script híbrido que combina dos estrategias de búsqueda:
1. Intenta búsqueda ESTRUCTURADA local (Tesseract + RapidFuzz)
2. Si falla, recurre a búsqueda VISUAL con IA (Nemotron VLM via OpenRouter)

Ubicación: rpa_framework/recordings/ocr/busqueda_triple_combinada.py
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
from typing import Optional, Dict, Tuple
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
# Se asume que este script está en rpa_framework/recordings/ocr/
# Queremos llegar a la raíz de rpa_framework para importar utils y ocr
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.logging_setup import setup_logging
from ocr.engine import OCREngine

logger = logging.getLogger(__name__)

# =================================================================================================
# ESTRATEGIA A: BUSQUEDA ESTRUCTURADA (Tesseract + RapidFuzz)
# Copiado y adaptado de: rpa_framework/recordings/ui/busqueda_triple_estructurada_v2.py
# =================================================================================================

class BusquedaEstructurada:
    def __init__(self):
        # Inicializamos OCREngine para que configure el path de Tesseract si es necesario
        self.ocr_engine = OCREngine(engine='tesseract', language='es', use_gpu=False, confidence_threshold=0.05)
        self.region = (190, 70, 1900, 650)
        self.ROW_TOLERANCE = 15
        
        # Guardar candidatos en cada paso
        self.paso1_candidatos = []
        self.paso2_candidatos = []
        
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
                logger.info(f"Target DB (Estructurada) - Diagnóstico: '{examen}', Fecha: '{fecha}'")
                return examen, fecha
            else:
                logger.warning("No se encontraron registros 'En Proceso' en la BBDD.")
                return None, None
        except Exception as e:
            logger.error(f"Error consultando BBDD: {e}")
            return None, None

    def normalize_text(self, text):
        """Normaliza texto: minúsculas, sin acentos, soloc alfanumérico y espacios simples."""
        # Minúsculas
        text = text.lower()
        
        # Remover acentos
        text = ''.join(
            c for c in unicodedata.normalize('NFD', text)
            if unicodedata.category(c) != 'Mn'
        )
        
        # Reemplazar todo lo que NO sea letra, número o guion por espacio
        text = re.sub(r'[^a-z0-9\-]', ' ', text)
        
        # Espacios simples
        text = ' '.join(text.split())
        
        return text

    def format_as_titulo(self, text):
        return ' '.join(word.capitalize() for word in text.split())

    def similarity(self, a, b):
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    def agrupar_por_filas(self, results):
        """Agrupa textos por proximidad Y."""
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
        """Aplica preprocesamiento optimizado para OCR."""
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        denoised = cv2.medianBlur(thresh, 3)
        return denoised

    def execute_ocr_multiconfig(self, img_bgr):
        """Ejecuta OCR con múltiples configuraciones y combina resultados."""
        # Escalar imagen
        scale_factor = 2
        img_resized = cv2.resize(img_bgr, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)
        
        # Preprocesar
        img_processed = self.preprocess_image(img_resized)
        
        # PSM Modes a probar
        psm_configs = [6, 4, 3]
        
        all_results = []
        
        for psm in psm_configs:
            custom_config = f'--psm {psm} -l spa'
            try:
                ocr_data = pytesseract.image_to_data(
                    img_processed, 
                    config=custom_config,
                    output_type=pytesseract.Output.DICT
                )
                
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
                            },
                            'psm': psm
                        }
                        all_results.append(result)
            except Exception as e:
                logger.error(f"Error en OCR PSM={psm}: {e}")
                
        # Eliminar duplicados
        unique_results = {}
        for r in all_results:
            key = (round(r['center']['y']), round(r['center']['x']/10)*10, r['text'].lower())
            if key not in unique_results or r['confidence'] > unique_results[key]['confidence']:
                unique_results[key] = r
        
        return list(unique_results.values())

    def match_diagnostico_mejorado(self, target, row_text):
        target_norm = self.normalize_text(target)
        row_norm = self.normalize_text(row_text)
        
        score_token_set = fuzz.token_set_ratio(target_norm, row_norm)
        if score_token_set >= 85:
            return (True, score_token_set, "token_set")
        
        score_partial = fuzz.partial_ratio(target_norm, row_norm)
        if score_partial >= 90:
            return (True, score_partial, "partial")
        
        score_token_sort = fuzz.token_sort_ratio(target_norm, row_norm)
        if score_token_sort >= 85:
            return (True, score_token_sort, "token_sort")
        
        return (False, 0, "no_match")

    def capture_and_process(self):
        """Ejecuta búsqueda estructurada en 3 pasos."""
        target_examen_db, target_fecha_obj = self.get_db_targets()
        if not target_examen_db or not target_fecha_obj:
            logger.error("No se pudo obtener el examen o la fecha de la base de datos.")
            return False, None

        fmt_dd_mm_yyyy = target_fecha_obj.strftime("%d-%m-%Y")
        
        logger.info(f"\n{'='*60}")
        logger.info("INTENTO 1: BÚSQUEDA ESTRUCTURADA (OCR + RapidFuzz)")
        logger.info(f"{'='*60}\n")
        
        logger.info(f"Targets: Estado='Examen Hecho', Diagnóstico='{target_examen_db}', Fecha='{fmt_dd_mm_yyyy}'")

        # Capturar pantalla
        screenshot = pyautogui.screenshot(region=self.region)
        img_np = np.array(screenshot)
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

        # Guardar imagen para log
        try:
            log_dir = Path("rpa_framework/log/busqueda triple")
            log_dir.mkdir(parents=True, exist_ok=True)
            
            now_str = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
            diag_clean = "".join([c if c.isalnum() else "_" for c in target_examen_db])[:30]
            filename = f"{now_str} {diag_clean} {fmt_dd_mm_yyyy}.png"
            filepath = log_dir / filename
            cv2.imwrite(str(filepath), img_bgr)
            logger.info(f"Imagen de log guardada en: {filepath}")
        except Exception as e:
            logger.error(f"Error guardando imagen de log: {e}")

        # OCR
        results = self.execute_ocr_multiconfig(img_bgr)
        rows_data = self.agrupar_por_filas(results)
        
        # PASO 1: Buscar "Examen Hecho"
        self.paso1_candidatos = []
        TARGET_ESTADO = "examen hecho"
        
        for idx, row in enumerate(rows_data):
            items = row['items']
            row_text_search = " ".join([i['text'] for i in sorted(items, key=lambda x: x['center']['x'])])
            row_text_normalized = self.normalize_text(row_text_search)
            
            palabras_row = row_text_normalized.split()
            match_examen = process.extractOne("examen", palabras_row, scorer=fuzz.ratio, score_cutoff=80)
            match_hecho = process.extractOne("hecho", palabras_row, scorer=fuzz.ratio, score_cutoff=80)
            
            if (match_examen and match_hecho) or \
               (fuzz.token_set_ratio(TARGET_ESTADO, row_text_normalized) >= 75) or \
               (fuzz.partial_ratio(TARGET_ESTADO, row_text_normalized) >= 85):
                
                self.paso1_candidatos.append({
                    'fila_idx': idx,
                    'y': row['y_center'],
                    'items': items,
                    'row_text_search': row_text_search
                })

        if not self.paso1_candidatos:
            logger.warning("❌ ESTRUCTURADA: Paso 1 falló (no se halló 'Examen Hecho').")
            return False, None

        # PASO 2: Buscar Diagnóstico
        self.paso2_candidatos = []
        for candidato in self.paso1_candidatos:
            match_result, _, _ = self.match_diagnostico_mejorado(target_examen_db, candidato['row_text_search'])
            if match_result:
                self.paso2_candidatos.append(candidato)

        if not self.paso2_candidatos:
            logger.warning("❌ ESTRUCTURADA: Paso 2 falló (no se halló diagnóstico).")
            return False, None

        # PASO 3: Buscar Fecha
        parts = fmt_dd_mm_yyyy.split('-')
        if len(parts) == 3:
            date_regex = re.compile(f"{parts[0]}.*?{parts[1]}.*?{parts[2]}", re.IGNORECASE)
        else:
            date_regex = None

        resultados_finales = []
        for candidato_p2 in self.paso2_candidatos:
            row_text = candidato_p2['row_text_search']
            
            if (date_regex and date_regex.search(row_text)) or \
               (fmt_dd_mm_yyyy in row_text.replace(" ", "")) or \
               (self.similarity(fmt_dd_mm_yyyy, row_text) > 0.6):
                 resultados_finales.append(candidato_p2)

        # RESULTADO
        if len(resultados_finales) > 0:
            fila_encontrada = resultados_finales[0]
            logger.info(f"✅ ESTRUCTURADA: Encontrada fila #{fila_encontrada['fila_idx']}")
            
            
            avg_x = sum([i['center']['x'] for i in fila_encontrada['items']]) / len(fila_encontrada['items'])
            screen_x = self.region[0] + avg_x
            screen_y = self.region[1] + fila_encontrada['y']
            
            return True, (screen_x, screen_y)
        else:
            logger.warning("❌ ESTRUCTURADA: Paso 3 falló (no se halló fecha).")
            return False, None


# =================================================================================================
# ESTRATEGIA B: BUSQUEDA VISUAL IA (Nemotron VLM)
# Copiado y adaptado de: rpa_framework/recordings/ocr/busqueda triple open.py
# =================================================================================================

OPENROUTER_API_KEY = "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"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MODEL_ID = "nvidia/nemotron-nano-12b-v2-vl:free"

class BusquedaNemotronTabla:
    def __init__(self):
        self.region = (190, 70, 1900, 650)
        self.openrouter_key = OPENROUTER_API_KEY
        self.model = MODEL_ID
        
    def get_db_targets(self) -> Tuple[Optional[str], Optional[datetime]]:
        # Reutilizamos la lógica de DB, pero es idéntica
        if not HAS_MYSQL: return None, None
        try:
            conn = mysql.connector.connect(host='localhost', user='root', password='', database='ris')
            cursor = conn.cursor()
            query = "SELECT SUBSTRING_INDEX(diagnostico, '\n', 1) AS examen, date(fecha_agendada) as fecha FROM ris.registro_acciones WHERE estado = 'En Proceso' LIMIT 1;"
            cursor.execute(query)
            result = cursor.fetchone()
            conn.close()
            if result:
                return result[0], result[1]
            return None, None
        except Exception:
            return None, None

    def capture_region(self) -> np.ndarray:
        screenshot = pyautogui.screenshot(region=self.region)
        img_np = np.array(screenshot)
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        return img_bgr

    def encode_image_to_base64(self, img_bgr: np.ndarray) -> str:
        _, buffer = cv2.imencode('.png', img_bgr)
        return base64.b64encode(buffer).decode('utf-8')

    def build_prompt(self, target_examen: str, target_fecha: str) -> str:
        return f"""Eres un TECNÓLOGO MÉDICO experto revisando una lista de trabajo en un sistema RIS.
TU MISIÓN: Encontrar la fila que corresponde el examen solicitado, incluso si el nombre en el sistema varía ligeramente.

DATOS A BUSCAR:
1. ESTADO (REQUISITO): Debe ser "Examen Hecho" (o "Exam. Hecho", "Realizado").
2. FECHA (REQUISITO): {target_fecha} (o fecha muy cercana, formato dd-mm-yyyy).
3. EXAMEN (FLEXIBLE): Buscas "{target_examen}".

RAZONAMIENTO CLÍNICO REQUERIDO:
- El nombre del examen en la lista puede ser diferente al de la orden médica. Debes usar tu criterio clínico.
- EQUIVALENCIAS COMUNES (Ejemplos):
  * "Ultrasonido" <-> "Ecotomografia" <-> "Eco"
  * "Radiografía" <-> "Rx" <-> "Placa"
  * "Scanner" <-> "TAC" <-> "TC"
  * "Resonancia" <-> "RM" <-> "RMN"
- REGIONES ANATÓMICAS:
  * "Dorsal" puede aparecer como "Torácica" (y viceversa).
  * "Cervical", "Dorsal", "Lumbar" son segmentos de "Columna".
  * "EESS" son Extremidades Superiores (Brazo, Codo, Muñeca, Mano).
  * "EEII" son Extremidades Inferiores (Muslo, Rodilla, Tobillo, Pie).
- LATERALIDAD:
  * "Izq" = "Izquierda", "Der" = "Derecha". Si no se especifica, asume que puede coincidir si el resto del nombre es igual.

INSTRUCCIONES DE SALIDA:
- Identifica la fila que mejor coincida conceptualmente.
- Si encuentras el examen con un nombre técnico distinto pero equivalente (ej: "Eco Abdominal" vs "Ultrasonido Abdomen"), ES UN MATCH VÁLIDO.
- Devuelve las COORDENADAS NORMALIZADAS (0-1000) del centro. (0,0)=Arriba-Izquierda.

RESPUESTA (JSON PURO):
{{
  "encontrada": true|false,
  "fila_indice": null,
  "texto_estado": "...",
  "texto_examen": "...",
  "texto_fecha": "...",
  "coordenada_x": 123,
  "coordenada_y": 456,
  "confianza": 0.9,
  "razonamiento": "..."
}}
"""

    def call_nemotron(self, prompt: str, img_base64: str) -> Optional[Dict]:
        logger.info(f"🤖 Enviando imagen a Nemotron ({self.model})...")
        try:
            response = requests.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.openrouter_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://rpa-framework.local"
                },
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "JSON ONLY.\n" + prompt},
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
                            ]
                        }
                    ],
                    "temperature": 0.0,
                    "max_tokens": 1000,
                },
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            content = result['choices'][0]['message'].get('content', '') or result['choices'][0]['message'].get('reasoning', '')
            
            # Limpieza JSON mejorada
            content = content.strip()
            # Intentar encontrar bloque JSON
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                clean_content = match.group(0)
                return json.loads(clean_content)
            else:
                # Si no encuentra llaves, intentar limpiar markdown
                clean_content = content.replace('```json', '').replace('```', '').strip()
                return json.loads(clean_content)
            
        except Exception as e:
            logger.error(f"Error Nemotron: {e}")
            return None

    def execute(self) -> bool:
        logger.info(f"\n{'='*60}")
        logger.info("INTENTO 2: BÚSQUEDA OPENROUTER / NEMOTRON")
        logger.info(f"{'='*60}\n")
        
        target_examen, target_fecha_obj = self.get_db_targets()
        if not target_examen or not target_fecha_obj: 
            logger.error("No se pudo obtener el examen o la fecha de la base de datos (Nemotron).")
            return False, None
        
        target_fecha_str = target_fecha_obj.strftime("%d-%m-%Y")
        
        img_bgr = self.capture_region()
        
        # Guardar imagen para log (Estrategia Nemotron)
        try:
            log_dir = Path("rpa_framework/log/busqueda triple")
            log_dir.mkdir(parents=True, exist_ok=True)
            
            now_str = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
            diag_clean = "".join([c if c.isalnum() else "_" for c in target_examen])[:30]
            filename = f"{now_str} {diag_clean} {target_fecha_str}_nemotron.png"
            filepath = log_dir / filename
            cv2.imwrite(str(filepath), img_bgr)
            logger.info(f"Imagen de log (Nemotron) guardada en: {filepath}")
        except Exception as e:
            logger.error(f"Error guardando imagen de log Nemotron: {e}")

        img_base64 = self.encode_image_to_base64(img_bgr)
        prompt = self.build_prompt(target_examen, target_fecha_str)
        
        response = self.call_nemotron(prompt, img_base64)
        
        if response and response.get('encontrada'):
            cx_norm = response.get('coordenada_x')
            cy_norm = response.get('coordenada_y')
            
            if cx_norm is not None and cy_norm is not None:
                # Obtener dimensiones reales de la imagen capturada
                h_img, w_img = img_bgr.shape[:2]
                
                # Des-normalizar coordenadas (0-1000 -> Pixeles)
                pixel_x = (cx_norm / 1000.0) * w_img
                pixel_y = (cy_norm / 1000.0) * h_img
                
                screen_x = int(self.region[0] + pixel_x)
                screen_y = int(self.region[1] + pixel_y)
                
                logger.info(f"✅ NEMOTRON: Fila encontrada (conf: {response.get('confianza')})")
                return True, (screen_x, screen_y)
        
        logger.warning("❌ NEMOTRON: No encontró la fila o falló.")
        return False, None

# =================================================================================================
# LÓGICA PRINCIPAL COMBINADA
# =================================================================================================

def main():
    setup_logging()
    
    logger.info(">>>> INICIANDO BÚSQUEDA TRIPLE COMBINADA <<<<")
    
    candidate_click_pos = None

    # 1. Intentar Estrategia Estructurada
    estructurada = BusquedaEstructurada()
    found, pos = estructurada.capture_and_process()
    if found:
        print("Row Found (Estructurada)")
        candidate_click_pos = pos

    if not candidate_click_pos:
        # 2. Si falla, intentar Estrategia IA
        logger.info("⚠️ Falló Estrategia 1. Intentando fallback con IA...")
        nemotron = BusquedaNemotronTabla()
        found, pos = nemotron.execute()
        if found:
            print("Row Found (Nemotron)")
            candidate_click_pos = pos

    if candidate_click_pos:
        logger.info(f"Haciendo click secundario en: {candidate_click_pos}")
        pyautogui.click(candidate_click_pos[0], candidate_click_pos[1], button='right')
        import time
        time.sleep(0.3)
        # Click menu context (opcional, basado en logica previa si fuese necesario)
        # pyautogui.click(candidate_click_pos[0] + 100, candidate_click_pos[1] + 194)
    else:
        print("Row Not Found")

if __name__ == "__main__":
    main()
