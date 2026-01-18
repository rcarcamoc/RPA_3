#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script: busqueda_triple_estructurada.py
Descripción: Búsqueda ESTRUCTURADA en 3 pasos con filtrado progresivo.

ALGORITMO:
┌─────────────────────────────────────────────────────────────┐
│ PASO 1: Buscar "Examen Hecho" (pocas coincidencias esperadas)  │
│ └─ Si 1 coincidencia: Pasar a Paso 2                       │
│ └─ Si >1 coincidencias: Guardar todas y filtrar en Paso 2  │
│                                                             │
│ PASO 2: Buscar DIAGNÓSTICO (convertir a formato tabla)      │
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
"""

import sys
import logging
import numpy as np
import cv2
import pyautogui
from datetime import datetime
from pathlib import Path
from difflib import SequenceMatcher

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
        # Bajamos el umbral de confianza porque las fechas suelen tener menor score en Tesseract
        self.ocr_engine = OCREngine(engine='tesseract', language='es', use_gpu=False, confidence_threshold=0.05)
        self.region = (189, 176, 1125, 832)
        
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

    def capture_and_process(self):
        """Ejecuta búsqueda estructurada en 3 pasos."""
        
        # Obtener targets
        target_examen_db, target_fecha_obj = self.get_db_targets()
        if not target_examen_db:
            return False

        # Preparar formatos de fecha
        fmt_dd_mm_yyyy = target_fecha_obj.strftime("%d-%m-%Y")
        
        # Preparar diagnóstico: convertir a formato título (como aparece en tabla)
        target_examen_titulo = self.format_as_titulo(target_examen_db)
        
        logger.info(f"\n{'='*80}")
        logger.info("🔍 BÚSQUEDA ESTRUCTURADA EN 3 PASOS")
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

        # Guardar debug con OTRO nombre para no pisar la imagen de prueba 'gold'
        debug_path = Path(__file__).parent / "debug_capture_last_run.png"
        cv2.imwrite(str(debug_path), img_bgr)

        # MODO DEBUG: Usar imagen existente (COMENTADO PARA PRODUCCIÓN)
        # debug_path = Path(__file__).parent / "debug_capture_estructurada.png"
        # logger.info(f"DEBUG MODE: Cargando imagen desde {debug_path}")
        # img_bgr = cv2.imread(str(debug_path))
        
        # if img_bgr is None:
        #     logger.error(f"No se pudo cargar la imagen de debug: {debug_path}")
        #     return False

        # OCR con Reescalado para mejorar precisión en números (Upscale x2)
        logger.info("Ejecutando OCR (con reescalado x2 para precisión)...")
        # Tesseract funciona mucho mejor con imágenes grandes (300 DPI aprox)
        scale_factor = 2
        img_resized = cv2.resize(img_bgr, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)
        
        results_raw = self.ocr_engine.extract_text_with_location(img_resized)
        
        # Ajustar coordenadas de vuelta al tamaño original
        results = []
        for item in results_raw:
            item['center']['x'] /= scale_factor
            item['center']['y'] /= scale_factor
            # Ajustar bounds también por si acaso
            item['bounds']['x_min'] /= scale_factor
            item['bounds']['y_min'] /= scale_factor
            item['bounds']['x_max'] /= scale_factor
            item['bounds']['y_max'] /= scale_factor
            results.append(item)

        logger.info(f"✓ Extraídos {len(results)} textos\n")

        # Agrupar por filas
        rows_data = self.agrupar_por_filas(results)
        logger.info(f"Se agruparon en {len(rows_data)} filas\n")

        # DEBUG: Ver todas las palabras detectadas por el OCR y su Y
        logger.debug("--- DUMP DE PALABRAS DETECTADAS (Confianza > 0.1) ---")
        for item in sorted(results, key=lambda x: x['center']['y']):
            logger.debug(f"  Y={item['center']['y']:.1f} | Conf={item['confidence']:.2f} | Texto: '{item['text']}'")

        # ════════════════════════════════════════════════════════════════════════════
        # PASO 1: Buscar "Examen Hecho"
        # ════════════════════════════════════════════════════════════════════════════
        
        logger.info(f"{'='*80}")
        logger.info("PASO 1: Buscar 'Examen Hecho'")
        logger.info(f"{'='*80}\n")

        self.paso1_candidatos = []
        
        logger.info("--- Revisando todas las filas detectadas ---")
        for idx, row in enumerate(rows_data):
            y = row['y_center']
            items = row['items']
            # Texto con separadores visuales
            row_text_display = " | ".join([i['text'] for i in sorted(items, key=lambda x: x['center']['x'])])
            
            # Texto limpio para búsqueda (sin pipes, solo espacios)
            row_text_search = " ".join([i['text'] for i in sorted(items, key=lambda x: x['center']['x'])])
            row_text_normalized = self.normalize_text(row_text_search)
            
            # Buscar 'examen hecho' (exacto o fuzzy)
            found_cancelado = False
            
            if "examen hecho" in row_text_normalized:
                found_cancelado = True
                logger.info(f"  ✓ [EXACT] Fila {idx}: {row_text_display}")
            else:
                # Intento fuzzy palabra por palabra
                for word in row_text_normalized.split():
                    sim = self.similarity("examen hecho", word)
                    if sim >= 0.80: # Tolerancia para 'examen hecho'
                        found_cancelado = True
                        logger.info(f"  ✓ [FUZZY {sim:.0%}] Fila {idx}: {row_text_display} (match: '{word}')")
                        break
            
            if found_cancelado:
                self.paso1_candidatos.append({
                    'fila_idx': idx,
                    'y': y,
                    'items': items,
                    'row_text': row_text_display, # Guardamos el visual para logs
                    'row_text_search': row_text_search # Guardamos el limpio para búsquedas
                })
            else:
                # Loguear filas descartadas solo si parecen relevantes o para debug
                # logger.debug(f"  ✗ Fila {idx}: {row_text_display}")
                pass

        logger.info(f"\n  Resultado: {len(self.paso1_candidatos)} fila(s) con 'Examen Hecho'\n")

        if not self.paso1_candidatos:
            logger.warning("❌ PASO 1 FALLÓ: No se encontró 'Examen Hecho' en ninguna fila.")
            logger.warning("Revisar archivo 'debug_capture_estructurada.png' y logs anteriores.")
            # Imprimir primeras 10 filas para dar contexto
            logger.info("Muestra de lo que se leyó (primeras 10 filas):")
            for idx, row in enumerate(rows_data[:10]):
                 t = " | ".join([i['text'] for i in sorted(row['items'], key=lambda x: x['center']['x'])])
                 logger.info(f"  Fila {idx}: {t}")
            return False

        if len(self.paso1_candidatos) == 1:
            logger.info("  ✅ PASO 1 OK: 1 coincidencia → Pasar a PASO 2\n")
        else:
            logger.info(f"  ⚠️  PASO 1: {len(self.paso1_candidatos)} coincidencias → Filtrar en PASO 2\n")

        # ════════════════════════════════════════════════════════════════════════════
        # PASO 2: Buscar DIAGNÓSTICO (filtrar entre candidatos de PASO 1)
        # ════════════════════════════════════════════════════════════════════════════
        
        logger.info(f"{'='*80}")
        logger.info("PASO 2: Buscar Diagnóstico")
        logger.info(f"{'='*80}\n")
        
        target_normalized = self.normalize_text(target_examen_db)
        logger.info(f"  Buscando: '{target_normalized}'")

        self.paso2_candidatos = []
        
        for candidato in self.paso1_candidatos:
            # Usamos el texto limpio de búsqueda, no el que tiene pipes
            row_text_search_norm = self.normalize_text(candidato['row_text_search'])
            
            # Búsqueda 1: Coincidencia de frase exacta (normalized)
            if target_normalized in row_text_search_norm:
                logger.info(f"  ✓ Fila {candidato['fila_idx']}: Coincidencia EXACTA")
                logger.info(f"    Contenido: {candidato['row_text']}")
                self.paso2_candidatos.append(candidato)
                continue
            
            # Búsqueda 2: Fuzzy
            # Si el diagnóstico tiene varias palabras ("Agenda Rayos"), SequenceMatcher directo sobre la frase
            sim_phrase = self.similarity(target_normalized, row_text_search_norm)
            
            if sim_phrase > 0.6: # Si toda la frase se parece algo
                 logger.debug(f"    Similitud frase completa: {sim_phrase:.2f}")

            # Check simplificado: ¿Están todas las palabras clave presentes?
            target_words = target_normalized.split()
            found_words_count = 0
            
            for t_word in target_words:
                # Búsqueda exacta de palabra o muy similar
                word_found = False
                if t_word in row_text_search_norm:
                    word_found = True
                else:
                    # Intentar buscar palabra similar en la fila
                    for row_word in row_text_search_norm.split():
                        if self.similarity(t_word, row_word) > 0.85:
                            word_found = True
                            break
                
                if word_found:
                    found_words_count += 1
            
            # ACEPTAR SI:
            # 1. Todas las palabras están (exactas o fuzzy)
            # 2. O la similitud global es muy alta ( > 0.85 )
            # 3. O (caso Agenda Rayos) encontramos la mayoría de palabras importantes
            
            if found_words_count == len(target_words):
                 logger.info(f"  ✓ Fila {candidato['fila_idx']}: Diagnóstico OK (Todas las palabras)")
                 self.paso2_candidatos.append(candidato)
                 continue
            
            # Fallback scan: Si falta algo pero la similitud es decente
            if found_words_count >= len(target_words) - 1 and len(target_words) > 1:
                 logger.info(f"  ✓ Fila {candidato['fila_idx']}: Diagnóstico OK (Fuzzy Match)")
                 self.paso2_candidatos.append(candidato)
                 continue

            logger.debug(f"  ✗ Fila {candidato['fila_idx']}: No coincide diagnóstico '{target_normalized}'")

        logger.info(f"\n  Resultado: {len(self.paso2_candidatos)} fila(s) con diagnóstico\n")

        if not self.paso2_candidatos:
            logger.warning("❌ PASO 2 FALLÓ: No se encontró diagnóstico")
            # Loguear qué falló
            for c in self.paso1_candidatos:
                logger.warning(f"  Candidato Fila {c['fila_idx']} (Examen Hecho OK): No match con '{target_normalized}'")
                logger.warning(f"  Texto leido: '{self.normalize_text(c['row_text_search'])}'")
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
        # Preparamos un regex de la fecha 02-08-2023 -> 02.*08.*2023
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
            
            # 1. Intento por Regex (flexible con ruidos)
            if date_regex and date_regex.search(row_text):
                logger.info(f"  ✓ Fila {candidato_p2['fila_idx']}: Fecha encontrada con Regex")
                resultados_finales.append(candidato_p2)
            # 2. Intento exacto (sin espacios)
            elif fmt_dd_mm_yyyy in row_text.replace(" ", ""):
                logger.info(f"  ✓ Fila {candidato_p2['fila_idx']}: Fecha encontrada (Exacta)")
                resultados_finales.append(candidato_p2)
            # 3. Intento FUZZY (si el diagnostico fue perfecto, aceptamos errores tipicos 8->0, 6->5)
            else:
                sim_fecha = self.similarity(fmt_dd_mm_yyyy, row_text)
                if sim_fecha > 0.6: # Tolerancia alta por si lee "00-01-2025" por "08-01-2026"
                     logger.info(f"  ✓ Fila {candidato_p2['fila_idx']}: Fecha aceptada por SIMILITUD ({sim_fecha:.2%})")
                     logger.info(f"    Leído: '{row_text}' vs Esperado: '{fmt_dd_mm_yyyy}'")
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
            
            # Calcular coordenadas reales de pantalla
            # self.region = (x, y, w, h)
            # ocr_x, ocr_y son relativos a la captura
            
            # Usamos el centro de la fila (Y) y el centro promedio de los items de esa fila (X)
            avg_x = sum([i['center']['x'] for i in fila_encontrada['items']]) / len(fila_encontrada['items'])
            
            screen_x = self.region[0] + avg_x
            screen_y = self.region[1] + fila_encontrada['y']
            
            logger.info(f"📍 Coordenadas pantalla: ({screen_x:.0f}, {screen_y:.0f})")
            
            # Mover y Click Derecho
            pyautogui.moveTo(screen_x, screen_y, duration=0.5)
            pyautogui.rightClick()
            logger.info("🖱️ Click derecho ejecutado")

            # Esperar 0.3s y click en opción (relativo 100, 194)
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
            # En caso de duda, click en la primera
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
