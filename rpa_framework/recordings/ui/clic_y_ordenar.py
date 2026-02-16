#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script autogenerado: clic_y_ordenar
Generado: 2026-01-02 14:37:33
Total de acciones: 5
"""

import sys
import time
import logging
import random
import os
from pathlib import Path
from datetime import datetime


# --- CONFIGURACIÓN DE DEPURACIÓN ---
SAVE_DEBUG_IMAGE = True  # Cambiar a False para no guardar capturas OCR
# -----------------------------------

# --- CONFIGURACIÓN DE BÚSQUEDA ---
# Lista de palabras a buscar (se intentarán en orden hasta encontrar una)
# NOTA: "Fecha agendada" aparece como dos palabras juntas en la UI
SEARCH_WORDS = ["Fecha agendada","Fecha", "Estado"]
# ----------------------------------
# NOTA: El OCREngine ahora usa automáticamente el módulo
#       rpa_framework/recordings/ocr/utilidades/preproceso_ocr.py
#       para preprocesamiento de alta fidelidad (3x upscaling + binarización Otsu)
# -----------------------------------

# Agregar raíz del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pywinauto import Application, findwindows
from core.executor import ActionExecutor
from core.action import Action, ActionType
from ocr.engine import OCREngine
from ocr.matcher import OCRMatcher
from ocr.actions import OCRActions
from utils.logging_setup import setup_logging

# Configuración de MySQL (opcional)
try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

logger = logging.getLogger(__name__)


class ClicYOrdenarAutomation:
    """Automatización generada: clic_y_ordenar"""
    
    def __init__(self):
        self.app = None
        self.executor = None
        self.ocr_actions = None
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Carpeta de logs específica
        self.log_dir = Path("rpa_framework/log/clic_y_ordenar")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
    def db_update_status(self, status='En Proceso', obs=None):
        """Actualiza el estado en la BD"""
        if not HAS_MYSQL:
            return
        try:
            conn = mysql.connector.connect(
                host='localhost',
                user='root',
                password='',
                database='ris'
            )
            cursor = conn.cursor()
            script_name = "clic_y_ordenar"
            
            if status == 'Error':
                query = "UPDATE ris.registro_acciones SET estado = 'Error', observacion = %s, `update` = NOW() WHERE estado = 'En Proceso'"
                cursor.execute(query, (obs,))
            else:
                query = "UPDATE ris.registro_acciones SET `update` = NOW(), ultimo_nodo = %s, estado = %s WHERE estado = 'En Proceso'"
                cursor.execute(query, (script_name, status))
            
            conn.commit()
            conn.close()
            logger.info(f"[DB] Tracking actualizado: {script_name} ({status})")
        except Exception as e:
            logger.warning(f"[DB Error] {e}")

    def fatal_error(self, message):
        """Actualiza la BD con el error y detiene la ejecución inmediatamente."""
        logger.error(f"❌ ERROR CRÍTICO: {message}")
        self.db_update_status('Error', obs=message)
        print(f"ERROR: {message}") # Esto aparecerá en el log de la UI
        sys.exit(1) # Código 1 indica fallo y detiene el workflow
    
    def setup(self) -> bool:
        """Conecta a la aplicación objetivo."""
        logger.info("Configurando conexión a la aplicación...")
        
        try:
            # Intentar conectar a ventana activa o Desktop
            try:
                self.app = Application(backend='uia').connect(path="explorer.exe")
            except:
                logger.warning("Usando modo Desktop")
                self.app = Application(backend='uia')
            
            self.executor = ActionExecutor(self.app, {})
            
            # Inicializar OCR para detección robusta
            try:
                logger.info("Inicializando OCR (Tesseract)...")
                # PSM 6 = Uniform block of text (mejor para tablas)
                # Sin whitelist para permitir mayor flexibilidad en la detección
                custom_config = r'--oem 3 --psm 6'
                engine = OCREngine(
                    engine='tesseract',
                    language='spa',  # 'es' -> 'spa'
                    confidence_threshold=0.6,  # Sube a 0.6
                    custom_config=custom_config,
                    preprocess=True,  # Si tienes esta opción
                    use_gpu=True
                )
                # Threshold reducido para mejorar detección, validación de longitud previene falsos positivos
                matcher = OCRMatcher(threshold=75)
                self.ocr_actions = OCRActions(engine, matcher)
                logger.info("✅ OCR Inicializado")
            except Exception as e:
                logger.warning(f"⚠️ Error inicializando OCR: {e}")

            logger.info("✅ Conexión establecida")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error en setup: {e}")
            return False
    
    def run(self) -> dict:
        """Ejecuta todas las acciones grabadas."""
        # DB Tracking: Start
        self.db_update_status('En Proceso')

        if not self.setup():
            self.fatal_error("Falló el inicio de la aplicación (setup)")
        
        results = {
            "session_id": self.session_id,
            "status": "RUNNING",
            "total_actions": 5,
            "completed": 0,
            "failed": 0,
            "errors": [],
            "start_time": datetime.now().isoformat(),
        }
        
        logger.info(f"🚀 Iniciando ejecución: {results['total_actions']} acciones")
        
        try:
            # Acción 1: OCR Find 'Estado' + 2 Left Clicks (Human-like)
            try:
                # Verificar inicialización de OCR
                if not self.ocr_actions:
                    self.fatal_error("OCR no inicializado. No se puede buscar el texto.")

                # PASO 1: Buscar "Estado" primero para establecer la región de búsqueda
                estado_y = None
                initial_region = {'left': 200, 'top': 100, 'width': 1720, 'height': 80}
                
                logger.info(f"🔍 Buscando 'Estado' para establecer región...")
                try:
                    estado_matches = self.ocr_actions.capture_and_find(
                        search_term="Estado", 
                        fuzzy=True,
                        take_screenshot=True,
                        region=initial_region
                    )
                    
                    if estado_matches:
                        estado_y = int(estado_matches[0]['center']['y'])
                        logger.info(f"✅ 'Estado' encontrado en Y={estado_y}. Región restringida activada.")
                    else:
                        logger.warning(f"⚠️ 'Estado' no encontrado. Buscando en región completa.")
                    
                    # Mostrar TODAS las palabras detectadas en el escaneo inicial
                    if self.ocr_actions.last_ocr_results:
                        print("\n" + "="*60)
                        print("📋 DIAGNÓSTICO: Palabras detectadas en escaneo inicial")
                        print("="*60)
                        sorted_words = sorted(
                            self.ocr_actions.last_ocr_results,
                            key=lambda r: (r['center']['y'], r['center']['x'])
                        )
                        for idx, res in enumerate(sorted_words, 1):
                            txt = res.get('text', '')
                            cx = int(res.get('center', {}).get('x', 0))
                            cy = int(res.get('center', {}).get('y', 0))
                            conf = res.get('confidence', 0)
                            print(f"{idx:2d}. '{txt:<25}' @ ({cx:4d}, {cy:3d}) | Conf: {conf:.1f}%")
                        print("="*60 + "\n")
                except Exception as e:
                    logger.warning(f"⚠️ Error buscando 'Estado': {e}")
                
                # PASO 2: Buscar las palabras objetivo en la región apropiada
                matches = []
                target_word = None
                ocr_exception = None
                
                for word in SEARCH_WORDS:
                    logger.info(f"🔍 Intentando buscar: '{word}'")
                    
                    # Si encontramos "Estado", usar región estrecha; si no, usar región completa
                    if estado_y is not None:
                        # Región estrecha: ±9px desde la Y de "Estado", ancho completo de pantalla
                        search_region = {
                            'left': 0,  # Desde el borde izquierdo
                            'top': max(0, estado_y - 9),  # 9px arriba (sin valores negativos)
                            'width': 1920,  # Ancho completo de pantalla
                            'height': 18  # Total: 9px arriba + 9px abajo = 18px
                        }
                        logger.info(f"   Región estrecha: Y={search_region['top']} a {search_region['top'] + search_region['height']}")
                    else:
                        search_region = initial_region
                    
                    try:
                        matches = self.ocr_actions.capture_and_find(
                            search_term=word, 
                            fuzzy=True,
                            take_screenshot=True,
                            region=search_region
                        )
                        
                        if matches:
                            # Validación adicional: verificar que el texto detectado no sea trivial
                            detected_text = matches[0].get('text', '')
                            # Si el texto detectado es muy corto comparado con lo buscado, es falso positivo
                            if len(detected_text) >= max(3, len(word) * 0.3):
                                target_word = word
                                logger.info(f"✅ Palabra encontrada: '{word}' (detectado: '{detected_text}')")
                                break
                            else:
                                logger.warning(f"⚠️ Falso positivo: '{detected_text}' no coincide con '{word}'")
                        else:
                            logger.warning(f"⚠️ No se encontró '{word}', intentando siguiente opción...")
                    except Exception as e:
                        ocr_exception = e
                        logger.warning(f"⚠️ Excepción durante OCR con '{word}': {e}")
                        continue
                
                # Si no se encontró ninguna palabra, usar la última para guardar debug
                if not target_word:
                    target_word = SEARCH_WORDS[-1]
                
                # Guardar imagen de depuración SIEMPRE, incluso si falla o hay excepción
                if SAVE_DEBUG_IMAGE:
                    img_name = f"ocr_{target_word.lower()}_{self.session_id}.png"
                    img_path = str(self.log_dir / img_name)
                    try:
                        self.ocr_actions.save_processed_screenshot(img_path)
                        logger.info(f"📸 Captura de depuración guardada: {img_path}")
                    except Exception as img_err:
                        logger.warning(f"No se pudo guardar la captura: {img_err}")

                # Imprimir resultados del OCR en consola
                if self.ocr_actions.last_ocr_results:
                    print("\n--- PALABRAS DETECTADAS POR TESSERACT ---")
                    # Ordenar por coordenada Y, luego X para lectura natural
                    sorted_results = sorted(
                        self.ocr_actions.last_ocr_results, 
                        key=lambda r: (r['center']['y'], r['center']['x'])
                    )
                    
                    for res in sorted_results:
                        txt = res.get('text', '')
                        cx = int(res.get('center', {}).get('x', 0))
                        cy = int(res.get('center', {}).get('y', 0))
                        print(f"Texto: '{txt:<20}' | Coords: ({cx}, {cy})")
                    print("-------------------------------------------\n")

                if ocr_exception:
                    self.fatal_error(f"Error crítico en OCR: {ocr_exception}")

                if matches:
                    best = matches[0]
                    base_x = int(best['center']['x'])
                    base_y = int(best['center']['y'])
                    logger.info(f"👁️ OCR encontró '{target_word}' en ({base_x}, {base_y})")
                else:
                    words_tried = "', '".join(SEARCH_WORDS)
                    self.fatal_error(f"OCR no encontró ninguna de las palabras: '{words_tried}'.")
                
                
                # Posicionar puntero antes de hacer clic
                move_action = Action(
                    type=ActionType.MOVE,
                    position={'x': base_x, 'y': base_y},
                    timestamp=datetime.now()
                )
                self.executor.execute(move_action)
                time.sleep(0.2) # Pequeña pausa tras mover

                # Click 1 with slight jitter
                jx1, jy1 = random.randint(-1, 1), random.randint(-1, 1)
                action1 = Action(
                    type=ActionType.CLICK,
                    position={'x': base_x + jx1, 'y': base_y + jy1},
                    timestamp=datetime.fromisoformat("2026-01-02T14:37:03.221837")
                )
                self.executor.execute(action1)
                
                # Human-like delay between clicks (80ms to 180ms)
                time.sleep(random.uniform(0.3, 0.8))

                # Click 2 with different slight jitter
                jx2, jy2 = random.randint(-1, 1), random.randint(-1, 1)
                action2 = Action(
                    type=ActionType.CLICK,
                    position={'x': base_x + jx2, 'y': base_y + jy2},
                    timestamp=datetime.now()
                )
                self.executor.execute(action2)
                time.sleep(random.uniform(0.3, 0.8))
                # Click 2 with different slight jitter
                jx2, jy2 = random.randint(-1, 1), random.randint(-1, 1)
                action2 = Action(
                    type=ActionType.CLICK,
                    position={'x': base_x + jx2, 'y': base_y + jy2},
                    timestamp=datetime.now()
                )
                self.executor.execute(action2)

                results["completed"] += 1
                logger.info(f"[1/2] ✅ 2 clicks (OCR/Humanized)")
            except Exception as e:
                self.fatal_error(f"Error en paso 1 (OCR 2 Clicks): {e}")

            results["status"] = "SUCCESS"
            
        except SystemExit:
            raise
        except Exception as e:
            self.fatal_error(f"Error inesperado: {e}")
        
        results["end_time"] = datetime.now().isoformat()
        logger.info(f"📊 RESUMEN: {results['completed']} OK, {results['failed']} FAILED")
        
        # DB Tracking: Final
        self.db_update_status('En Proceso')
        
        return results


def main():
    """Punto de entrada principal."""
    setup_logging()
    
    automation = ClicYOrdenarAutomation()
    results = automation.run()
    
    print("\n" + "="*50)
    print(f"Resultado: {results['status']}")
    print(f"Completadas: {results['completed']}/5")
    print(f"Fallidas: 0")
    print("="*50)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

