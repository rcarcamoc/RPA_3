# rpa_framework/ocr/actions.py

import pyautogui
import time
import logging
from typing import Dict, List, Optional, Tuple
import numpy as np
from mss import mss
import cv2

from .engine import OCREngine
from .matcher import OCRMatcher

logger = logging.getLogger(__name__)


class OCRActions:
    """
    Acciones de alto nivel basadas en OCR.
    
    Integra Engine + Matcher para ejecutar
    operaciones como click, copy, select, type.
    """
    
    def __init__(
        self,
        ocr_engine: Optional[OCREngine] = None,
        ocr_matcher: Optional[OCRMatcher] = None,
        delay: float = 0.3
    ):
        """
        Inicializar acciones OCR.
        
        Args:
            ocr_engine: Instancia de OCREngine (se crea si no se proporciona)
            ocr_matcher: Instancia de OCRMatcher (se crea si no se proporciona)
            delay: Delay entre acciones (segundos)
        """
        self.ocr_engine = ocr_engine or OCREngine()
        self.ocr_matcher = ocr_matcher or OCRMatcher()
        self.delay = delay
        self.last_screenshot = None
        self.last_ocr_results = None
        
        logger.info("OCRActions inicializado")
    
    def capture_screenshot(self, monitor_index: int = 0) -> np.ndarray:
        """
        Captura pantalla actual.
        
        Args:
            monitor_index: Índice del monitor (0=Todos, 1=Principal, etc)

        Returns:
            Array numpy con captura
        """
        try:
            with mss() as sct:
                # Validar índice
                if monitor_index < 0 or monitor_index >= len(sct.monitors):
                    logger.warning(f"Índice de monitor {monitor_index} inválido. Usando 0 (All).")
                    monitor_index = 0
                
                monitor = sct.monitors[monitor_index]
                screenshot = sct.grab(monitor)
                self.last_screenshot = np.array(screenshot)
                logger.debug(f"Screenshot capturado del monitor {monitor_index}")
                return self.last_screenshot
        except Exception as e:
            logger.error(f"Error capturando screenshot: {e}")
            raise
    
    def capture_and_find(
        self,
        search_term: str,
        fuzzy: bool = True,
        case_sensitive: bool = False,
        take_screenshot: bool = True,
        return_all: bool = False,
        monitor_index: int = 0
    ) -> List[Dict]:
        """
        Captura pantalla y busca texto.
        
        Args:
            search_term: Texto a buscar
            fuzzy: Usar búsqueda fuzzy
            case_sensitive: Distinguir mayúsculas/minúsculas
            take_screenshot: Capturar nueva screenshot
            return_all: Retornar todos los matches
            monitor_index: Índice del monitor a capturar
        
        Returns:
            Lista de matches con ubicación
        """
        if take_screenshot:
            self.capture_screenshot(monitor_index=monitor_index)
        
        if self.last_screenshot is None:
            raise ValueError("No hay screenshot disponible")
        
        # Extraer texto con OCR
        try:
            self.last_ocr_results = self.ocr_engine.extract_text_with_location(
                self.last_screenshot
            )
            logger.debug(f"OCR: {len(self.last_ocr_results)} textos extraídos")
        except Exception as e:
            logger.error(f"Error en OCR: {e}")
            raise
        
        # Buscar término
        matches = self.ocr_matcher.find_text(
            self.last_ocr_results,
            search_term,
            # search_term, # Duplicate arg removed
            fuzzy=fuzzy,
            case_sensitive=case_sensitive,
            return_all=return_all
        )
        
        return matches
    
    def click_on_text(
        self,
        search_term: str,
        offset_x: int = 0,
        offset_y: int = 0,
        fuzzy: bool = True,
        case_sensitive: bool = False,
        button: str = 'left',
        clicks: int = 1,
        interval: float = 0.1
    ) -> Dict:
        """
        Busca texto y hace click en él.
        
        Args:
            search_term: Texto a buscar
            offset_x: Desplazamiento X desde el centro
            offset_y: Desplazamiento Y desde el centro
            fuzzy: Usar búsqueda fuzzy
            case_sensitive: Distinguir mayúsculas/minúsculas
            button: 'left', 'right', 'middle'
            clicks: Número de clicks
            interval: Intervalo entre clicks (segundos)
        
        Returns:
            Dict con info de la acción ejecutada
        """
        matches = self.capture_and_find(
            search_term,
            fuzzy=fuzzy,
            case_sensitive=case_sensitive,
            take_screenshot=True
        )
        
        if not matches:
            raise ValueError(f"No se encontró texto: '{search_term}'")
        
        best_match = matches[0]
        
        # Calcular coordenadas
        click_x = int(best_match['center']['x'] + offset_x)
        click_y = int(best_match['center']['y'] + offset_y)
        
        # Hacer click
        try:
            pyautogui.click(
                x=click_x,
                y=click_y,
                button=button,
                clicks=clicks,
                interval=interval
            )
            time.sleep(self.delay)
            
            logger.info(f"Click ejecutado en '{best_match['text']}' en ({click_x}, {click_y})")
            
            return {
                'action': 'click',
                'status': 'success',
                'text_found': best_match['text'],
                'confidence': best_match['confidence'],
                'position': {'x': click_x, 'y': click_y},
                'similarity': best_match.get('match_similarity', 100)
            }
        
        except Exception as e:
            logger.error(f"Error ejecutando click: {e}")
            raise
    
    def double_click_on_text(
        self,
        search_term: str,
        offset_x: int = 0,
        offset_y: int = 0,
        fuzzy: bool = True,
        case_sensitive: bool = False
    ) -> Dict:
        """Double-click en texto encontrado."""
        return self.click_on_text(
            search_term,
            offset_x=offset_x,
            offset_y=offset_y,
            fuzzy=fuzzy,
            case_sensitive=case_sensitive,
            clicks=2,
            interval=0.1
        )
    
    def right_click_on_text(
        self,
        search_term: str,
        offset_x: int = 0,
        offset_y: int = 0,
        fuzzy: bool = True,
        case_sensitive: bool = False
    ) -> Dict:
        """Right-click en texto encontrado."""
        return self.click_on_text(
            search_term,
            offset_x=offset_x,
            offset_y=offset_y,
            fuzzy=fuzzy,
            case_sensitive=case_sensitive,
            button='right'
        )
    
    def select_text(
        self,
        search_term: str,
        fuzzy: bool = True,
        case_sensitive: bool = False
    ) -> Dict:
        """
        Busca texto, hace triple-click para seleccionar.
        
        Args:
            search_term: Texto a buscar
            fuzzy: Usar búsqueda fuzzy
            case_sensitive: Distinguir mayúsculas/minúsculas
        
        Returns:
            Info de la acción
        """
        matches = self.capture_and_find(
            search_term,
            fuzzy=fuzzy,
            case_sensitive=case_sensitive,
            take_screenshot=True
        )
        
        if not matches:
            raise ValueError(f"No se encontró: '{search_term}'")
        
        best_match = matches[0]
        click_x = int(best_match['center']['x'])
        click_y = int(best_match['center']['y'])
        
        # Triple-click para seleccionar
        try:
            pyautogui.click(click_x, click_y, clicks=3, interval=0.1)
            time.sleep(self.delay)
            
            logger.info(f"Texto seleccionado: '{best_match['text']}'")
            
            return {
                'action': 'select',
                'status': 'success',
                'text': best_match['text'],
                'position': {'x': click_x, 'y': click_y}
            }
        
        except Exception as e:
            logger.error(f"Error seleccionando texto: {e}")
            raise
    
    def copy_text_by_ocr(
        self,
        search_term: str,
        fuzzy: bool = True,
        case_sensitive: bool = False
    ) -> Dict:
        """
        Busca, selecciona y copia texto.
        
        Args:
            search_term: Texto a buscar
            fuzzy: Usar búsqueda fuzzy
            case_sensitive: Distinguir mayúsculas/minúsculas
        
        Returns:
            Info de la acción
        """
        # Seleccionar
        self.select_text(search_term, fuzzy=fuzzy, case_sensitive=case_sensitive)
        
        # Copiar
        try:
            pyautogui.hotkey('ctrl', 'c')
            time.sleep(0.5)
            
            logger.info(f"Texto copiado: '{search_term}'")
            
            return {
                'action': 'copy',
                'status': 'success',
                'text_searched': search_term,
                'timestamp': time.time()
            }
        
        except Exception as e:
            logger.error(f"Error copiando texto: {e}")
            raise
    
    def type_near_text(
        self,
        reference_text: str,
        text_to_type: str,
        offset_x: int = 50,
        offset_y: int = 0,
        fuzzy: bool = True,
        case_sensitive: bool = False,
        interval: float = 0.05
    ) -> Dict:
        """
        Encuentra un texto de referencia y escribe cerca de él.
        
        Útil para rellenar campos de entrada cercanos a etiquetas.
        
        Args:
            reference_text: Texto de referencia a buscar
            text_to_type: Texto a escribir
            offset_x: Desplazamiento X desde referencia
            offset_y: Desplazamiento Y desde referencia
            fuzzy: Usar búsqueda fuzzy
            case_sensitive: Distinguir mayúsculas/minúsculas
            interval: Intervalo entre caracteres
        
        Returns:
            Info de la acción
        """
        # Encontrar referencia
        matches = self.capture_and_find(
            reference_text,
            fuzzy=fuzzy,
            case_sensitive=case_sensitive,
            take_screenshot=True
        )
        
        if not matches:
            raise ValueError(f"No se encontró referencia: '{reference_text}'")
        
        best_match = matches[0]
        
        # Calcular posición
        click_x = int(best_match['center']['x'] + offset_x)
        click_y = int(best_match['center']['y'] + offset_y)
        
        try:
            # Click en la posición
            pyautogui.click(click_x, click_y)
            time.sleep(0.2)
            
            # Escribir texto
            pyautogui.typewrite(text_to_type, interval=interval)
            time.sleep(self.delay)
            
            logger.info(f"Texto escrito cerca de '{best_match['text']}'")
            
            return {
                'action': 'type_near_text',
                'status': 'success',
                'reference': best_match['text'],
                'typed': text_to_type,
                'position': {'x': click_x, 'y': click_y}
            }
        
        except Exception as e:
            logger.error(f"Error escribiendo texto: {e}")
            raise
    
    def set_delay(self, delay: float):
        """Cambiar delay entre acciones"""
        self.delay = delay
        logger.info(f"Delay actualizado a {delay}s")
    
    def save_screenshot(self, filepath: str):
        """Guardar screenshot actual como imagen"""
        if self.last_screenshot is None:
            raise ValueError("No hay screenshot disponible")
        
        try:
            cv2.imwrite(filepath, self.last_screenshot)
            logger.info(f"Screenshot guardado en: {filepath}")
        except Exception as e:
            logger.error(f"Error guardando screenshot: {e}")
            raise


# Ejemplo de uso
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # Inicializar
    engine = OCREngine(engine='easyocr', language='es')
    matcher = OCRMatcher(threshold=80)
    actions = OCRActions(engine, matcher)
    
    try:
        # Buscar y clickear
        # result = actions.click_on_text('Enviar', fuzzy=True)
        # print(f"Resultado: {result}")
        
        # Buscar y copiar
        # result = actions.copy_text_by_ocr('Email')
        # print(f"Resultado: {result}")
        
        # Escribir cerca de etiqueta
        # result = actions.type_near_text('Email:', 'usuario@example.com')
        # print(f"Resultado: {result}")
        
        print("OCRActions importado correctamente")
    
    except Exception as e:
        logger.error(f"Error: {e}")
