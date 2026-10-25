# rpa_framework/ocr/engine.py
"""
Motor OCR unificado que soporta múltiples engines (EasyOCR, Tesseract, PaddleOCR).
Refactorizado de forma modular junto con rpa_framework/ocr/engine_backends_mixin.py.
"""

import cv2
import numpy as np
from typing import List, Dict, Union, Optional
import logging

from .engine_backends_mixin import OCREngineBackendsMixin, HAS_PREPROCESS_UTILS

logger = logging.getLogger(__name__)


class OCREngine(OCREngineBackendsMixin):
    """
    Motor OCR unificado que soporta múltiples engines.
    
    Soportados:
    - easyocr: Mejor para español, flexible
    - tesseract: Rápido, requiere instalación adicional
    - paddleocr: Alta precisión y robustez para texto complejo/fechas
    """
    
    def __init__(
        self,
        engine: str = 'paddleocr',
        language: str = 'spa',
        confidence_threshold: float = 0.5,
        use_gpu: bool = False,
        model_storage_dir: Optional[str] = None,
        custom_config: str = '',
        preprocess: bool = False
    ):
        """
        Inicializar motor OCR.
        
        Args:
            engine: 'easyocr', 'tesseract' o 'paddleocr'
            language: Código de idioma (ej: 'es', 'en', 'pt', 'spa')
            confidence_threshold: Umbral mínimo de confianza (0-1)
            use_gpu: Usar GPU si está disponible
            model_storage_dir: Directorio para almacenar modelos
        """
        self.engine = engine
        self.language = language
        self.confidence_threshold = confidence_threshold
        self.use_gpu = use_gpu
        self.custom_config = custom_config
        self.preprocess = preprocess
        self.reader = None
        self.paddle_ocr = None
        self.paddle_gpu_client = None
        self.last_processed_image = None
        self.scale_factor = 1.0  # Factor de escala aplicado en preprocesamiento
        
        logger.info(f"Inicializando OCR Engine: {engine} (idioma: {language})")
        
        if engine == 'easyocr':
            self._init_easyocr(model_storage_dir)
        elif engine == 'tesseract':
            self._init_tesseract()
        elif engine == 'paddleocr':
            self._init_paddleocr()
        else:
            raise ValueError(f"Engine no soportado: {engine}")

    def extract_text_with_location(
        self,
        image: Union[str, np.ndarray],
        detail: bool = True
    ) -> List[Dict]:
        """
        Extrae texto con ubicación (bounding boxes).
        
        Args:
            image: Ruta a imagen o array numpy
            detail: Si True, retorna bbox detallado
        
        Returns:
            Lista de dicts con texto y ubicación
        """
        if isinstance(image, str):
            image = cv2.imread(image)
            if image is None:
                raise ValueError(f"No se pudo cargar imagen: {image}")
        
        if not isinstance(image, np.ndarray):
            raise TypeError(f"Tipo de imagen no válido: {type(image)}")
        
        image = self._resize_if_needed(image)
        
        if self.confidence_threshold > 0.8:
            image = self._preprocess_image(image)
        
        try:
            if self.engine == 'easyocr':
                return self._extract_easyocr(image, detail)
            elif self.engine == 'tesseract':
                lang = 'spa' if self.language == 'es' else self.language
                original_lang = self.language
                self.language = lang
                results = self._extract_tesseract(image, detail)
                self.language = original_lang
                return results
            elif self.engine == 'paddleocr':
                return self._extract_paddleocr(image, detail)
        except Exception as e:
            logger.error(f"Error en extracción OCR ({self.engine}): {e}")
            raise

    def extract_language(self, image: Union[str, np.ndarray]) -> str:
        """Detectar idioma predominante en imagen (solo EasyOCR)"""
        if self.engine != 'easyocr':
            return self.language
        
        if isinstance(image, str):
            image = cv2.imread(image)
        
        return self.language


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    engine = OCREngine(engine='easyocr', language='es', use_gpu=False)
    from mss import mss
    with mss() as sct:
        screenshot = np.array(sct.grab(sct.monitors[1]))
    results = engine.extract_text_with_location(screenshot)
    for result in results[:5]:
        print(f"Texto: {result['text']}")
        print(f"Confianza: {result['confidence']}")
        print(f"Centro: {result['center']}")
        print("---")
