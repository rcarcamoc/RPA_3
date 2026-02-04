#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script: busqueda_triple_estructurada_v2.py
Descripción: Búsqueda ESTRUCTURADA en 3 pasos con filtrado progresivo y RapidFuzz.

ALGORITMO:
┌─────────────────────────────────────────────────────────────┐
│ PASO 1: Buscar "Examen Hecho" (pocas coincidencias esperadas)  │
│ └─ Si 1 coincidencia: Pasar a Paso 2                       │
│ └─ Si >1 coincidencias: Guardar todas y filtrar en Paso 2  │
│                                                             │
│ PASO 2: Buscar DIAGNÓSTICO (RAPIDFUZZ MEJORADO)             │
│ └─ Si 1 coincidencia: Pasar a Paso 3                       │
│ └─ Si >1 coincidencias: Guardar todas y filtrar en Paso 3  │
│                                                             │
│ PASO 3: Buscar FECHA (último filtro, aquí converge)         │
│ └─ Si 1 coincidencia: ✅ ENCONTRADA                        │
│ └─ Si >1 coincidencias: ERROR (no debería pasar)           │
└─────────────────────────────────────────────────────────────┘

Ventajas:
1. Eficiente: Filtra en cada paso reduciendo candidatos
2. Transparente: Logs detallados de cada filtración
3. Robusto: Maneja múltiples coincidencias en cada paso
4. Debuggeable: Sabe exactamente dónde quedaron los textos
5. Fuzzy Mejorado: Usa RapidFuzz para tolerar variaciones complejas
"""

import sys
import logging
import numpy as np
import cv2
import pyautogui
# Import pytesseract explicitly as requested for multi-config
import pytesseract
from datetime import datetime
from pathlib import Path
from difflib import SequenceMatcher
try:
    from rapidfuzz import fuzz, process
except ImportError:
    print("Error: rapidfuzz no está instalado. Ejecuta 'pip install rapidfuzz'")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.logging_setup import setup_logging
from ocr.engine import OCREngine

try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

logger = logging.getLogger(__name__)

class BusquedaEstructurada:
    def __init__(self):
        # Inicializamos OCREngine para que configure el path de Tesseract si es necesario
        self.ocr_engine = OCREngine(engine='tesseract', language='es', use_gpu=False, confidence_threshold=0.05)
        #self.region = (189, 176, 1125, 832)
        self.region = (190, 70, 1900, 650)
        # Aumentamos a 15 para capturar textos que bailan un poco arriba/abajo en la misma fila
        self.ROW_TOLERANCE = 15
        self.SIMILARITY_THRESHOLD = 0.85  # Para comparar diagnósticos (mayúsculas/minúsculas)
        
        # Guardar candidatos en cada paso
        self.paso1_candidatos = []
        self.paso2_candidatos = []
        self.paso3_resultado = None
        
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
                logger.info(f"Targets de DB - Diagnóstico: '{examen}', Fecha: '{fecha}'")
                return examen, fecha
            else:
                logger.warning("No se encontraron registros 'En Proceso' en la BBDD.")
                return None, None
        except Exception as e:
            logger.error(f"Error consultando BBDD: {e}")
            return None, None

    def normalize_text(self, text):
        """Normaliza texto: minúsculas, sin acentos, soloc alfanumérico y espacios simples."""
        import unicodedata
        import re
        
        # Minúsculas
        text = text.lower()
        
        # Remover acentos
        text = ''.join(
            c for c in unicodedata.normalize('NFD', text)
            if unicodedata.category(c) != 'Mn'
        )
        
        # Reemplazar todo lo que NO sea letra, número o guion por espacio
        # Mantener el guion es vital para las fechas
        text = re.sub(r'[^a-z0-9\-]', ' ', text)
        
        # Espacios simples (reduce múltiples espacios a uno)
        text = ' '.join(text.split())
        
        return text

    def format_as_titulo(self, text):
        """Convierte a formato título (Primera letra mayúscula de cada palabra)."""
        return ' '.join(word.capitalize() for word in text.split())

    def similarity(self, a, b):
        """Calcula similitud entre dos strings (0-1)."""
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

    # --------------------------------------------------------------------------------
    # MEJORAS SUGERIDAS: Preprocesamiento y OCR Multi-Config
    # --------------------------------------------------------------------------------
    def preprocess_image(self, img_bgr):
        """Aplica preprocesamiento optimizado para OCR."""
        # Convertir a escala de grises
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        
        # Aplicar umbralización OTSU (mejor para texto en tablas)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Aplicar filtro de mediana para reducir ruido
        denoised = cv2.medianBlur(thresh, 3)
        
        # Guardar imagen procesada para debug
        debug_preprocessed = Path(__file__).parent / "debug_preprocessed.png"
        try:
            cv2.imwrite(str(debug_preprocessed), denoised)
            logger.info(f"Imagen preprocesada guardada en: {debug_preprocessed}")
        except Exception:
            pass
        
        return denoised

    def execute_ocr_multiconfig(self, img_bgr):
        """Ejecuta OCR con múltiples configuraciones y combina resultados."""
        
        # Escalar imagen
        scale_factor = 2
        img_resized = cv2.resize(img_bgr, None, fx=scale_factor, fy=scale_factor, 
                                interpolation=cv2.INTER_CUBIC)
        
        # Preprocesar
        img_processed = self.preprocess_image(img_resized)
        
        # PSM Modes a probar (según tipo de contenido)
        psm_configs = [
            6,  # Asume bloque uniforme de texto (mejor para tablas)
            4,  # Asume columna única de texto
            3,  # Segmentación automática (default)
        ]
        
        all_results = []
        
        for psm in psm_configs:
            logger.info(f"Ejecutando OCR con PSM={psm}...")
            
            custom_config = f'--psm {psm} -l spa'
            
            try:
                # Usar pytesseract directamente con config
                # Asumimos que OCREngine ya configuró el path si era necesario
                ocr_data = pytesseract.image_to_data(
                    img_processed, 
                    config=custom_config,
                    output_type=pytesseract.Output.DICT
                )
                
                # Procesar resultados
                n_boxes = len(ocr_data['text'])
                for i in range(n_boxes):
                    confidence = float(ocr_data['conf'][i])
                    text = ocr_data['text'][i].strip()
                    
                    if confidence > 5 and text:  # Umbral bajo para capturar más
                        x, y, w, h = (ocr_data['left'][i], ocr_data['top'][i],
                                     ocr_data['width'][i], ocr_data['height'][i])
                        
                        # Ajustar coordenadas al tamaño original
                        result = {
                            'text': text,
                            'confidence': confidence,
                            'center': {
                                'x': (x + w/2) / scale_factor,
                                'y': (y + h/2) / scale_factor
                            },
                            'bounds': {
                                'x_min': x / scale_factor,
                                'y_min': y / scale_factor,
                                'x_max': (x + w) / scale_factor,
                                'y_max': (y + h) / scale_factor
                            },
                            'psm': psm
                        }
                        all_results.append(result)
            except Exception as e:
                logger.error(f"Error en OCR PSM={psm}: {e}")
                
        # Eliminar duplicados (mantener mejor confianza)
        unique_results = {}
        for r in all_results:
            key = (round(r['center']['y']), round(r['center']['x']/10)*10, r['text'].lower())
            if key not in unique_results or r['confidence'] > unique_results[key]['confidence']:
                unique_results[key] = r
        
        return list(unique_results.values())

    # --------------------------------------------------------------------------------
    # MEJORA: RAPIDFUZZ MATCHING
    # --------------------------------------------------------------------------------
    def match_diagnostico_mejorado(self, target, row_text):
        """
        Matching mejorado usando múltiples estrategias de RapidFuzz.
        Retorna (match_encontrado, score, metodo_usado)
        """
        target_norm = self.normalize_text(target)
        row_norm = self.normalize_text(row_text)
        
        # Estrategia 1: Token Set Ratio 
        score_token_set = fuzz.token_set_ratio(target_norm, row_norm)
        if score_token_set >= 85:
            return (True, score_token_set, "token_set")
        
        # Estrategia 2: Partial Ratio
        score_partial = fuzz.partial_ratio(target_norm, row_norm)
        if score_partial >= 90:
            return (True, score_partial, "partial")
        
        # Estrategia 3: Token Sort Ratio
        score_token_sort = fuzz.token_sort_ratio(target_norm, row_norm)
        if score_token_sort >= 85:
            return (True, score_token_sort, "token_sort")
        
        return (False, 0, "no_match")

    def capture_and_process(self):
        """Ejecuta búsqueda estructurada en 3 pasos."""
        
        # Obtener targets
        target_examen_db, target_fecha_obj = self.get_db_targets()
        if not target_examen_db:
            return False

        # Preparar formatos de fecha
        fmt_dd_mm_yyyy = target_fecha_obj.strftime("%d-%m-%Y")
        
        target_examen_titulo = self.format_as_titulo(target_examen_db)
        
        logger.info(f"\n{'='*80}")
        logger.info("🔍 BÚSQUEDA ESTRUCTURADA EN 3 PASOS (VERSION RAPIDFUZZ + MULTI-OCR)")
        logger.info(f"{'='*80}\n")
        
        logger.info(f"Targets de búsqueda:")
        logger.info(f"  1. Estado: 'Examen Hecho'")
        logger.info(f"  2. Diagnóstico (DB): '{target_examen_db}' → Tabla: '{target_examen_titulo}'")
        logger.info(f"  3. Fecha: '{fmt_dd_mm_yyyy}'")

        # Capturar pantalla
        logger.info(f"\nCapturando región: {self.region}")
        screenshot = pyautogui.screenshot(region=self.region)
        img_np = np.array(screenshot)
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

        # Guardar debug
        debug_path = Path(__file__).parent / "debug_capture_v2.png"
        cv2.imwrite(str(debug_path), img_bgr)

        # OCR Multi-Config
        logger.info("Ejecutando OCR con múltiples configuraciones...")
        results = self.execute_ocr_multiconfig(img_bgr)
        logger.info(f"✓ Extraídos {len(results)} textos únicos\n")

        # AGREGAR ESTO PARA DEBUG:
        logger.info("=" * 80)
        logger.info("📋 DUMP COMPLETO DE TEXTOS DETECTADOS (ordenados por Y)")
        logger.info("=" * 80)
        for idx, item in enumerate(sorted(results, key=lambda x: x['center']['y'])):
            logger.info(f"  [{idx:03d}] Y={item['center']['y']:6.1f} | Conf={item['confidence']:5.2f} | '{item['text']}'")
        logger.info("=" * 80 + "\n")

        # Agrupar por filas
        rows_data = self.agrupar_por_filas(results)
        logger.info(f"Se agruparon en {len(rows_data)} filas\n")

        # ════════════════════════════════════════════════════════════════════════════
        # PASO 1: Buscar "Examen Hecho" (Fuzzy Match)
        # ════════════════════════════════════════════════════════════════════════════
        
        logger.info(f"{'='*80}")
        logger.info("PASO 1: Buscar 'Examen Hecho' (Fuzzy Match)")
        logger.info(f"{'='*80}\n")

        self.paso1_candidatos = []
        TARGET_ESTADO = "examen hecho"
        
        logger.info("--- Revisando todas las filas detectadas ---")
        for idx, row in enumerate(rows_data):
            y = row['y_center']
            items = row['items']
            
            row_text_search = " ".join([i['text'] for i in sorted(items, key=lambda x: x['center']['x'])])
            row_text_display = " | ".join([i['text'] for i in sorted(items, key=lambda x: x['center']['x'])])
            row_text_normalized = self.normalize_text(row_text_search)
            
            # Estrategia 1: Buscar palabras individuales con fuzzy
            palabras_row = row_text_normalized.split()
            
            # Buscar "examen" y "hecho" por separado
            match_examen = process.extractOne("examen", palabras_row, scorer=fuzz.ratio, score_cutoff=80)
            match_hecho = process.extractOne("hecho", palabras_row, scorer=fuzz.ratio, score_cutoff=80)
            
            if match_examen and match_hecho:
                logger.info(f"  ✓ [FUZZY PALABRAS] Fila {idx}: {row_text_display}")
                logger.info(f"    Match: 'examen'→'{match_examen[0]}' ({match_examen[1]}%), 'hecho'→'{match_hecho[0]}' ({match_hecho[1]}%)")
                self.paso1_candidatos.append({
                    'fila_idx': idx,
                    'y': y,
                    'items': items,
                    'row_text': row_text_display,
                    'row_text_search': row_text_search
                })
                continue
            
            # Estrategia 2: Token Set Ratio (toda la frase)
            score = fuzz.token_set_ratio(TARGET_ESTADO, row_text_normalized)
            if score >= 75:  # Umbral más bajo
                logger.info(f"  ✓ [TOKEN SET {score}%] Fila {idx}: {row_text_display}")
                self.paso1_candidatos.append({
                    'fila_idx': idx,
                    'y': y,
                    'items': items,
                    'row_text': row_text_display,
                    'row_text_search': row_text_search
                })
                continue
            
            # Estrategia 3: Partial Ratio (subcadenas)
            score_partial = fuzz.partial_ratio(TARGET_ESTADO, row_text_normalized)
            if score_partial >= 85:
                logger.info(f"  ✓ [PARTIAL {score_partial}%] Fila {idx}: {row_text_display}")
                self.paso1_candidatos.append({
                    'fila_idx': idx,
                    'y': y,
                    'items': items,
                    'row_text': row_text_display,
                    'row_text_search': row_text_search
                })

        logger.info(f"\n  Resultado: {len(self.paso1_candidatos)} fila(s) con 'Examen Hecho'\n")

        if not self.paso1_candidatos:
            logger.warning("❌ PASO 1 FALLÓ: No se encontró 'Examen Hecho' en ninguna fila.")
            return False

        # ════════════════════════════════════════════════════════════════════════════
        # PASO 2: Buscar DIAGNÓSTICO (VERSIÓN MEJORADA - RAPIDFUZZ)
        # ════════════════════════════════════════════════════════════════════════════

        logger.info(f"{'='*80}")
        logger.info("PASO 2: Buscar Diagnóstico (Fuzzy Mejorado)")
        logger.info(f"{'='*80}\n")

        logger.info(f"  Target original: '{target_examen_db}'")
        logger.info(f"  Target normalizado: '{self.normalize_text(target_examen_db)}'")

        self.paso2_candidatos = []

        for candidato in self.paso1_candidatos:
            row_text = candidato['row_text_search']
            
            # Usar el nuevo método de matching mejorado
            match_result, score, metodo = self.match_diagnostico_mejorado(
                target_examen_db, 
                row_text
            )
            
            if match_result:
                logger.info(f"  ✓ Fila {candidato['fila_idx']}: Match encontrado")
                logger.info(f"    Método: {metodo} | Score: {score:.1f}%")
                logger.info(f"    Texto leído: '{row_text}'")
                self.paso2_candidatos.append(candidato)
            else:
                logger.debug(f"  ✗ Fila {candidato['fila_idx']}: No match (score: {score:.1f}%)")

        logger.info(f"\n  Resultado: {len(self.paso2_candidatos)} fila(s) con diagnóstico\n")

        if not self.paso2_candidatos:
            logger.warning("❌ PASO 2 FALLÓ: No se encontró diagnóstico")
            return False

        if len(self.paso2_candidatos) == 1:
            logger.info("  ✅ PASO 2 OK: 1 coincidencia exacta → Pasar a PASO 3\n")
        else:
            logger.info(f"  ⚠️  PASO 2: {len(self.paso2_candidatos)} coincidencias → Filtrar en PASO 3\n")

        # ════════════════════════════════════════════════════════════════════════════
        # PASO 3: Buscar FECHA (último filtro)
        # ════════════════════════════════════════════════════════════════════════════
        
        logger.info(f"{'='*80}")
        logger.info("PASO 3: Buscar Fecha (Filtro Final)")
        logger.info(f"{'='*80}\n")
        
        import re
        parts = fmt_dd_mm_yyyy.split('-')
        if len(parts) == 3:
            date_regex = re.compile(f"{parts[0]}.*?{parts[1]}.*?{parts[2]}", re.IGNORECASE)
            logger.info(f"  Fecha a buscar: '{fmt_dd_mm_yyyy}' (Regex: {date_regex.pattern})")
        else:
            date_regex = None
            logger.warning(f"  Formato de fecha inesperado: {fmt_dd_mm_yyyy}")

        resultados_finales = []
        
        for candidato_p2 in self.paso2_candidatos:
            row_text = candidato_p2['row_text_search']
            
            # 1. Intento por Regex
            if date_regex and date_regex.search(row_text):
                logger.info(f"  ✓ Fila {candidato_p2['fila_idx']}: Fecha encontrada con Regex")
                resultados_finales.append(candidato_p2)
            # 2. Intento exacto
            elif fmt_dd_mm_yyyy in row_text.replace(" ", ""):
                logger.info(f"  ✓ Fila {candidato_p2['fila_idx']}: Fecha encontrada (Exacta)")
                resultados_finales.append(candidato_p2)
            # 3. Intento FUZZY
            else:
                sim_fecha = self.similarity(fmt_dd_mm_yyyy, row_text)
                if sim_fecha > 0.6:
                     logger.info(f"  ✓ Fila {candidato_p2['fila_idx']}: Fecha aceptada por SIMILITUD ({sim_fecha:.2%})")
                     resultados_finales.append(candidato_p2)
                else:
                    logger.debug(f"  ✗ Fila {candidato_p2['fila_idx']}: No coincide fecha en '{row_text}'")

        logger.info(f"\n  Resultado: {len(resultados_finales)} fila(s) con los 3 textos\n")

        # ════════════════════════════════════════════════════════════════════════════
        # RESULTADO FINAL Y ACCIÓN
        # ════════════════════════════════════════════════════════════════════════════
        
        logger.info(f"{'='*80}")
        logger.info("📊 RESUMEN")
        logger.info(f"{'='*80}\n")
        
        if len(resultados_finales) == 1:
            fila_encontrada = resultados_finales[0]
            
            logger.info(f"✅ FILA ENCONTRADA - Fila #{fila_encontrada['fila_idx']}")
            
            avg_x = sum([i['center']['x'] for i in fila_encontrada['items']]) / len(fila_encontrada['items'])
            screen_x = self.region[0] + avg_x
            screen_y = self.region[1] + fila_encontrada['y']
            
            logger.info(f"📍 Coordenadas pantalla: ({screen_x:.0f}, {screen_y:.0f})")
            
            pyautogui.moveTo(screen_x, screen_y, duration=0.5)
            pyautogui.rightClick()
            logger.info("🖱️ Click derecho ejecutado")

            import time
            time.sleep(0.3)
            pyautogui.click(screen_x + 100, screen_y + 194)
            logger.info(f"🖱️ Click izquierdo en opción: ({screen_x + 100:.0f}, {screen_y + 194:.0f})")

            print("Row Found and Clicked")
            return True

        elif len(resultados_finales) == 0:
            logger.warning(f"\n❌ NO ENCONTRADA\n")
            return False
        else:
            logger.warning(f"\n⚠️  MÚLTIPLES FILAS ENCONTRADAS ({len(resultados_finales)})")
            # Click en la primera
            fila = resultados_finales[0]
            avg_x = sum([i['center']['x'] for i in fila['items']]) / len(fila['items'])
            pyautogui.rightClick(self.region[0] + avg_x, self.region[1] + fila['y'])
            return True

def main():
    setup_logging()
    script = BusquedaEstructurada()
    script.capture_and_process()

if __name__ == "__main__":
    main()
