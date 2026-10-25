# -*- coding: utf-8 -*-
"""
medical_text_mixin.py — Normalización médica, verificación de lateralidad anatómica,
agrupamiento por filas y motores OCR (PaddleOCR / Tesseract) para BusquedaTextOnly.
Extraído de busqueda_triple_text_only.py.
"""

import re
import unicodedata
import logging
from datetime import datetime
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

try:
    import pytesseract
except ImportError:
    pytesseract = None

from ocr.engine import OCREngine

try:
    from recordings.ocr.utilidades.preproceso_ocr import preprocess_high_fidelity, normalize_coordinates
    HAS_PREPROCESS_UTILS = True
except ImportError:
    HAS_PREPROCESS_UTILS = False

logger = logging.getLogger(__name__)


class TripleSearchMedicalTextMixin:
    """Mixin con normalización médica, lateralidad y ejecución OCR para BusquedaTextOnly."""

    def normalize_text(self, text):
        text = text.lower()
        text = ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
        text = re.sub(r'\b(?:kiamograf\w*|hiamograf\w*|kamograf\w*|kmamograf\w*|iamograf\w*|hamograf\w*|mamogratia|marnografia)\b', 'mamografia', text)
        text = re.sub(r'\b(?:kiamari\w*|hiamari\w*|liamari\w*|kamari\w*|iamari\w*|hamari\w*|marnari\w*|inamari\w*)\b', 'mamaria', text)
        text = re.sub(r'\bmamaria\s+infantil\b', 'mamaria', text)
        text = re.sub(r'[^a-z0-9\-]', ' ', text)
        text = ' '.join(text.split())
        return text

    def verificar_lateralidad(self, text_target: str, text_ocr: str) -> bool:
        """
        Valida clínicamente que la lateralidad del examen buscado (target)
        sea compatible con la detectada en el texto OCR.
        """
        target_norm = self.normalize_text(text_target)
        ocr_norm = self.normalize_text(text_ocr)

        der_tokens = {'derecho', 'derecha', 'der', 'dcha', 'dcho'}
        izq_tokens = {'izquierdo', 'izquierda', 'izq', 'izda'}
        bilat_tokens = {'bilateral', 'ambos', 'ambas', 'eeii', 'eess', 'bilat', 'bilater', 'eell', 'ee11', 'ee55'}

        target_words = set(target_norm.split())
        ocr_words = set(ocr_norm.split())

        target_has_der = bool(target_words & der_tokens)
        target_has_izq = bool(target_words & izq_tokens)
        target_has_bilat = bool(target_words & bilat_tokens) or any(w.startswith('bilat') for w in target_words) or bool(re.search(r'\bee\s*(?:ii|ll|11|li|il|ss|55)\b', target_norm)) or bool(re.search(r'\bamb(?:os|as)\b', target_norm))

        ocr_has_der = bool(ocr_words & der_tokens)
        ocr_has_izq = bool(ocr_words & izq_tokens)
        ocr_has_bilat = bool(ocr_words & bilat_tokens) or any(w.startswith('bilat') for w in ocr_words) or bool(re.search(r'\bee\s*(?:ii|ll|11|li|il|ss|55)\b', ocr_norm)) or bool(re.search(r'\bamb(?:os|as)\b', ocr_norm))

        # Caso Bilateral
        if target_has_bilat:
            if not ocr_has_bilat and not (ocr_has_der and ocr_has_izq):
                es_estudio_mamario = any(w in target_norm or w in ocr_norm for w in ['mamaria', 'mamario', 'mamografia', 'mama', 'mamas'])
                if es_estudio_mamario and not (ocr_has_der or ocr_has_izq):
                    logger.info("ℹ️ Estudio mamario sin especificar lateralidad: compatible con BILATERAL por convención clínica.")
                else:
                    logger.info("🚫 Lateralidad incompatible: Target es BILATERAL pero OCR es unilateral.")
                    return False
        elif ocr_has_bilat:
            if target_has_der or target_has_izq:
                logger.info("🚫 Lateralidad incompatible: OCR es BILATERAL pero Target es unilateral.")
                return False

        # Caso Derecho estricto
        if target_has_der and not target_has_izq:
            if ocr_has_izq and not ocr_has_der:
                logger.info("🚫 Lateralidad incompatible: Target pide DERECHO pero OCR tiene IZQUIERDO.")
                return False

        # Caso Izquierdo estricto
        if target_has_izq and not target_has_der:
            if ocr_has_der and not ocr_has_izq:
                logger.info("🚫 Lateralidad incompatible: Target pide IZQUIERDO pero OCR tiene DERECHO.")
                return False

        return True

    @staticmethod
    def normalizar_terminologia_medica(texto: str) -> str:
        """
        Normaliza abreviaturas radiológicas y médicas frecuentes para permitir
        coincidencias léxicas exactas o fuzzy locales sin depender de LLMs.
        """
        if not texto:
            return ""
        t = texto.lower()
        t = ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')
        reemplazos = [
            (r'\brx[\s\-_]?([a-z]+)\b', r'radiografia \1'),
            (r'\br\s*x\b', 'radiografia'),
            (r'\bradiografias\b', 'radiografia'),
            (r'\(?\bf[\s\-_/]*o\b\)?\:?', 'front oblicua'),
            (r'\b(?:frente|frontal|front)\s*(?:y\s*)?oblicua\b', 'front oblicua'),
            (r'\bap\s*-\s*l\b|\bap\s*-\s*lat\b|\bap\s*lat\b|\bpa\s*-\s*lat\b|\bpa\s*lat\b|\bap-lat\b|\bpa-lat\b', 'ap lateral'),
            (r'\b(?:pa|ap)\s*y\s*lat(?:eral)?\b', 'ap lateral'),
            (r'\bsimple\s+ap\s+decubito\b', 'ap lateral simple'),
            (r'\bdecubito(?:\s+supino)?\b', 'ap'),
            (r'\br\s*m\b', 'resonancia magnetica'),
            (r'\brmn\b', 'resonancia magnetica'),
            (r'\brnm\b', 'resonancia magnetica'),
            (r'\brim\b', 'resonancia magnetica'),
            (r'\bram\b', 'resonancia magnetica'),
            (r'\bmri\b', 'resonancia magnetica'),
            (r'\bt\s*c\b', 'tomografia computada'),
            (r'\btac\b', 'tomografia computada'),
            (r'\bct\b', 'tomografia computada'),
            (r'\beco\b', 'ecotomografia'),
            (r'\becografia\b', 'ecotomografia'),
            (r'\becoo\b', 'ecotomografia'),
            (r'\beoo\b', 'ecotomografia'),
            (r'\b(?:coppler|eoppler|dopler|doopler|oppler|cappler|goppler|toppler)\b', 'doppler'),
            (r'\b(?:kiamograf\w*|hiamograf\w*|kamograf\w*|kmamograf\w*|iamograf\w*|hamograf\w*|hamog\w*|xamograf\w*|mamogratia|marnografia)\b', 'mamografia'),
            (r'\b(?:kiamari\w*|hiamari\w*|liamari\w*|kamari\w*|iamari\w*|hamari\w*|marnari\w*|inamari\w*)\b', 'mamaria'),
            (r'\bmamaria\s+infantil\b', 'mamaria'),
            (r'\beco\s+mamaria\s+infantil\b', 'ecotomografia mamaria'),
            (r'\bproyecci[oó]n(?:es)?\s+magnificad[ao]s?\b', 'proyecciones complementarias'),
            (r'\bproyecci[oó]n(?:es)?\s+focalizad[ao]s?\b', 'proyecciones complementarias'),
            (r'\bcono(?:s)?\s+de\s+compresi[oó]n\b', 'proyecciones complementarias'),
            (r'\bproyecci[oó]n(?:es)?\s+tangencial(?:es)?\b', 'proyecciones complementarias'),
            (r'\bproyecci[oó]n(?:es)?\s+adicional(?:es)?\b', 'proyecciones complementarias'),
            (r'\bpartes\s+blandas\s+(?:de\s+)?(?:cara\s+y\s+cuello|cara|cuello)\b', 'partes blandas cara'),
            (r'\b(?:partes\s+blandas\s+(?:de\s+)?)?(?:periauricular|preauricular|retroauricular|parotidea|parotida)\b', 'partes blandas cara'),
            (r'\b(?:urolac|urotac|uro-tac)\b', 'urotac'),
            (r'\b(?:pielotc|pielotac|pielo-tc|pielografia)\b', 'pielografia'),
            (r'\bcolangio\s*rm\b|\bcolangiorm\b|\bcolangioresonancia\b', 'colangioresonancia'),
            (r'\bee\s*(?:ii|ll|11|li|il)\b', 'extremidades inferiores'),
            (r'\b(?:eeii|eell|ee11)\b', 'extremidades inferiores'),
            (r'\bee\s*(?:ss|55)\b', 'extremidades superiores'),
            (r'\b(?:eess|ee55)\b', 'extremidades superiores'),
            (r'\brot\b', 'rotula'),
            (r'\bfemoropatelar\b', 'patelofemoral'),
        ]
        for patron, reemplazo in reemplazos:
            t = re.sub(patron, reemplazo, t)

        if ('mamografia' in t or 'mamaria' in t) and not any(w in t for w in ['derecha', 'derecho', 'der', 'izquierda', 'izquierdo', 'izq', 'unilateral', 'bilateral']):
            t = t + ' bilateral'

        t = re.sub(r'[^a-z0-9\s]', ' ', t)
        return re.sub(r'\s+', ' ', t).strip()

    @staticmethod
    def extraer_fragmento_estudio(ocr_text: str) -> str:
        """
        Extrae el nombre del estudio de la fila OCR, habitualmente ubicado
        entre 'Examen Hecho'/'Hecho'/'Realizado' y la fecha del examen.
        """
        if not ocr_text:
            return ""
        m = re.search(r'(?:examen\s*hecho|hecho|realizado)\s*(.*?)\s*\d{2}[-/]\d{2}[-/]\d{2,4}', ocr_text, re.IGNORECASE)
        if m and m.group(1).strip():
            return m.group(1).strip()
        m_fecha = re.search(r'^(.*?)\s*\d{2}[-/]\d{2}[-/]\d{2,4}', ocr_text)
        if m_fecha and m_fecha.group(1).strip():
            fragmento = m_fecha.group(1).strip()
            fragmento = re.sub(r'^(?:examen\s*hecho|hecho|realizado)\s*', '', fragmento, flags=re.IGNORECASE)
            return fragmento.strip()
        return ocr_text

    def agrupar_por_filas(self, results):
        if not results:
            return []
            
        results_sorted = sorted(results, key=lambda x: x['center']['y'])
        
        rows_data = []
        for item in results_sorted:
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
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        contrast = clahe.apply(gray)
        blurred = cv2.GaussianBlur(contrast, (3, 3), 0)
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2,2))
        processed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        return processed

    def execute_ocr_basic(self, img_bgr, psm=6):
        """Ejecuta OCR usando explícitamente el módulo de preproceso_ocr."""
        if not HAS_PREPROCESS_UTILS:
            logger.warning("Módulo preproceso_ocr no disponible, usando OCR básico.")
            return pytesseract.image_to_string(img_bgr, config=f'--psm {psm} -l spa')
            
        try:
            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img_rgb)
            processed_pil, _ = preprocess_high_fidelity(pil_img, scale_factor=3)
            custom_config = f'--psm {psm} -l spa --oem 3'
            text = pytesseract.image_to_string(processed_pil, config=custom_config)
            return text.strip()
        except Exception as e:
            logger.error(f"Error en OCR Basic (Manual Preprocess): {e}")
            return ""

    def _get_tesseract_engine(self):
        """Retorna motor Tesseract (instanciado bajo demanda como fallback)."""
        if self._tesseract_engine is None:
            logger.info("🔧 Inicializando motor Tesseract (Fallback)...")
            self._tesseract_engine = OCREngine(
                engine='tesseract',
                language='spa',
                use_gpu=False,
                confidence_threshold=0.0,
                preprocess=False,
                custom_config='--psm 6'
            )
        return self._tesseract_engine

    def execute_ocr_data(self, img_bgr, use_preprocessing=True, mode='high_fidelity'):
        """
        Devuelve datos estructurados de OCR.
        Permite activar/desactivar pre-procesamiento manual (use_preprocessing=False para fallback).
        """
        if not HAS_PREPROCESS_UTILS:
            logger.warning("Faltan utilidades de preproceso, usando motor directo.")
            use_preprocessing = False

        if not use_preprocessing:
            logger.info("ℹ️ Ejecutando OCR en imagen RAW (Sin Preprocesamiento 3X)...")
            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            return self._get_tesseract_engine().extract_text_with_location(img_rgb)

        try:
            img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img_rgb)
            
            from recordings.ocr.utilidades.preproceso_ocr import preprocess_adaptive
            if mode == 'high_fidelity':
                processed_pil, scale = preprocess_adaptive(pil_img, mode='high_fidelity', scale_factor=3)
            elif mode == 'remove_blue':
                processed_pil, scale = preprocess_adaptive(pil_img, mode='remove_blue')
                scale = 1.0
            else:
                processed_pil, scale = pil_img, 1.0
            
            try:
                log_dir = Path("rpa_framework/log/busqueda triple")
                log_dir.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
                debug_path = log_dir / f"{timestamp}_OCR_PREPROCESSED_3X.png"
                processed_pil.save(str(debug_path))
                logger.info(f"📸 Imagen preprocesada (3X BW) guardada en: {debug_path}")
            except Exception as e:
                logger.warning(f"No se pudo guardar la imagen de debug OCR: {e}")

            processed_np = np.array(processed_pil)
            results_scaled = self._get_tesseract_engine().extract_text_with_location(processed_np)
            
            normalized_results = []
            for res in results_scaled:
                norm_res = normalize_coordinates(res, scale)
                normalized_results.append(norm_res)
                
            logger.info(f"OCR detectó {len(normalized_results)} palabras (Preproceso Manual + Normalización OK)")
            return normalized_results

        except Exception as e:
            logger.error(f"Error en execute_ocr_data (Manual): {e}")
            return []

    def execute_paddle_ocr(self, img_bgr):
        """
        Ejecuta PaddleOCR como motor primario en GPU.
        Utiliza el microservicio HTTP o worker de alta robustez ante fechas y acrónimos.
        """
        if self._paddle_engine is None:
            self._paddle_engine = self.ocr_engine
        # PaddleOCR (worker GPU vía cv2.imwrite y motor local) trabaja en BGR.
        # Pasarle RGB invertía los canales: las franjas rojas llegaban como azules.
        return self._paddle_engine.extract_text_with_location(img_bgr)

    def get_crop_image(self, full_img, y_center):
        h, w = full_img.shape[:2]
        half_h = self.CROP_HEIGHT // 2
        y_start = int(max(0, y_center - half_h))
        y_end = int(min(h, y_center + half_h))
        return full_img[y_start:y_end, 0:w]
