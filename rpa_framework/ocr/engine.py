# rpa_framework/ocr/engine.py

import pytesseract
import cv2
import numpy as np
from typing import List, Dict, Union, Optional
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class OCREngine:
    """
    Motor OCR unificado que soporta múltiples engines.
    
    Soportados:
    - easyocr: Mejor para español, flexible
    - tesseract: Rápido, requiere instalación adicional
    """
    
    def __init__(
        self,
        engine: str = 'easyocr',
        language: str = 'es',
        confidence_threshold: float = 0.5,
        use_gpu: bool = False,
        model_storage_dir: Optional[str] = None
    ):
        """
        Inicializar motor OCR.
        
        Args:
            engine: 'easyocr' o 'tesseract'
            language: Código de idioma (ej: 'es', 'en', 'pt')
            confidence_threshold: Umbral mínimo de confianza (0-1)
            use_gpu: Usar GPU si está disponible
            model_storage_dir: Directorio para almacenar modelos
        """
        self.engine = engine
        self.language = language
        self.confidence_threshold = confidence_threshold
        self.use_gpu = use_gpu
        self.reader = None
        
        logger.info(f"Inicializando OCR Engine: {engine} (idioma: {language})")
        
        if engine == 'easyocr':
            self._init_easyocr(model_storage_dir)
        elif engine == 'tesseract':
            self._init_tesseract()
        else:
            raise ValueError(f"Engine no soportado: {engine}")
    
    def _init_easyocr(self, model_storage_dir: Optional[str]):
        """Inicializar EasyOCR"""
        try:
            import easyocr
            self.reader = easyocr.Reader(
                [self.language],
                gpu=self.use_gpu,
                model_storage_directory=model_storage_dir
            )
            logger.info(f"EasyOCR inicializado correctamente")
        except ImportError:
            logger.error("EasyOCR no está instalado. Instalar con: pip install easyocr")
            raise
        except Exception as e:
            logger.error(f"Error inicializando EasyOCR: {e}")
            raise
    
    def _init_tesseract(self):
        """Inicializar Tesseract"""
        # En Windows
        try:
            tess_dir = r'C:\Program Files\Tesseract-OCR'
            tess_exe = os.path.join(tess_dir, 'tesseract.exe')
            
            # Agregar al PATH para que el proceso encuentre las DLLs
            if tess_dir not in os.environ['PATH']:
                os.environ['PATH'] = tess_dir + os.pathsep + os.environ['PATH']
            
            pytesseract.pytesseract.pytesseract_cmd = tess_exe
            
            # Test
            version = pytesseract.get_tesseract_version()
            logger.info(f"Tesseract inicializado correctamente (v{version})")
        except Exception as e:
            logger.error(f"Error inicializando Tesseract: {e}")
            import traceback
            traceback.print_exc()
            raise
    
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
        # Cargar imagen si es ruta
        if isinstance(image, str):
            image = cv2.imread(image)
            if image is None:
                raise ValueError(f"No se pudo cargar imagen: {image}")
        
        # Validar tipo
        if not isinstance(image, np.ndarray):
            raise TypeError(f"Tipo de imagen no válido: {type(image)}")
        
        # Optimización: Redimensionar si es muy grande (ahorra memoria y CPU)
        image = self._resize_if_needed(image)
        
        # Aplicar preprocesamiento solo si está habilitado explícitamente
        # Para capturas de pantalla digitales, el preprocesamiento agresivo (CLAHE) suele empeorar la detección
        if self.confidence_threshold > 0.8: # Ejemplo de condición o flag explícito
             image = self._preprocess_image(image)
        
        try:
            if self.engine == 'easyocr':
                return self._extract_easyocr(image, detail)
            elif self.engine == 'tesseract':
                # Tesseract usa 'spa' para español, no 'es'
                lang = 'spa' if self.language == 'es' else self.language
                original_lang = self.language
                self.language = lang
                results = self._extract_tesseract(image, detail)
                self.language = original_lang
                return results
        except Exception as e:
            logger.error(f"Error en extracción OCR ({self.engine}): {e}")
            raise

    def _resize_if_needed(self, image: np.ndarray, max_dimension: int = 4096) -> np.ndarray:
        """
        Redimensiona la imagen si excede las dimensiones máximas.
        Ayuda a reducir el consumo de memoria y mejorar la velocidad.
        Default aumentado a 4096 para soportar dual monitors sin perder calidad de texto.
        """
        height, width = image.shape[:2]
        if max(height, width) <= max_dimension:
            return image
            
        scale = max_dimension / max(height, width)
        new_width = int(width * scale)
        new_height = int(height * scale)
        
        logger.info(f"Redimensionando imagen de {width}x{height} a {new_width}x{new_height} (scale: {scale:.2f})")
        return cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)

    def _extract_easyocr(self, image: np.ndarray, detail: bool) -> List[Dict]:
        """Extracción con EasyOCR"""
        results = self.reader.readtext(image, detail=1)
        
        text_data = []
        for (bbox, text, confidence) in results:
            # Filtrar por confianza
            if confidence < self.confidence_threshold:
                continue
            
            # bbox = [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            x_coords = [point[0] for point in bbox]
            y_coords = [point[1] for point in bbox]
            
            text_info = {
                'text': text.strip(),
                'confidence': float(confidence),
                'bbox': bbox,
                'bounds': {
                    'x_min': float(min(x_coords)),
                    'y_min': float(min(y_coords)),
                    'x_max': float(max(x_coords)),
                    'y_max': float(max(y_coords)),
                },
                'center': {
                    'x': float((min(x_coords) + max(x_coords)) / 2),
                    'y': float((min(y_coords) + max(y_coords)) / 2),
                },
                'dimensions': {
                    'width': float(max(x_coords) - min(x_coords)),
                    'height': float(max(y_coords) - min(y_coords)),
                }
            }
            
            text_data.append(text_info)
        
        logger.info(f"EasyOCR: Extraídos {len(text_data)} textos")
        return text_data
    
    def _extract_tesseract(self, image: np.ndarray, detail: bool) -> List[Dict]:
        """Extracción con Tesseract"""
        # Convertir BGR a RGB
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Usar pytesseract con output_type
        try:
            from pytesseract import Output
            data = pytesseract.image_to_data(
                image_rgb,
                lang=self.language,
                output_type=Output.DICT
            )
        except:
            # Fallback para versiones antiguas
            data = pytesseract.image_to_data(image_rgb, lang=self.language)
        
        text_data = []
        for i in range(len(data['text'])):
            text = data['text'][i].strip()
            
            # Saltar textos vacíos
            if not text:
                continue
            
            confidence = float(data['conf'][i]) / 100.0
            
            # Filtrar por confianza
            if confidence < self.confidence_threshold:
                continue
            
            x = int(data['left'][i])
            y = int(data['top'][i])
            w = int(data['width'][i])
            h = int(data['height'][i])
            
            text_info = {
                'text': text,
                'confidence': confidence,
                'bbox': [[x, y], [x+w, y], [x+w, y+h], [x, y+h]],
                'bounds': {
                    'x_min': float(x),
                    'y_min': float(y),
                    'x_max': float(x + w),
                    'y_max': float(y + h),
                },
                'center': {
                    'x': float(x + w/2),
                    'y': float(y + h/2),
                },
                'dimensions': {
                    'width': float(w),
                    'height': float(h),
                }
            }
            
            text_data.append(text_info)
        
        logger.info(f"Tesseract: Extraídos {len(text_data)} textos")
        return text_data
    
    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocesar imagen para mejorar OCR.
        
        Aplicable cuando la calidad es baja.
        """
        # Convertir a escala de grises si es color
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # NOTA: CLAHE puede distorsionar texto digital limpio.
        # Se mantiene para casos difíciles pero se debe usar con precaución.
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # Opcional: Threshold adaptativo para textos oscuros
        # enhanced = cv2.adaptiveThreshold(enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        #                                   cv2.THRESH_BINARY, 11, 2)
        
        return enhanced
    
    def extract_language(self, image: Union[str, np.ndarray]) -> str:
        """Detectar idioma predominante en imagen (solo EasyOCR)"""
        if self.engine != 'easyocr':
            return self.language
        
        if isinstance(image, str):
            image = cv2.imread(image)
        
        # Usar detectar idioma (si está disponible en versión)
        # Por ahora retornamos configurado
        return self.language


# Ejemplo de uso
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # Inicializar motor
    engine = OCREngine(engine='easyocr', language='es', use_gpu=False)
    
    # Capturar pantalla
    from mss import mss
    with mss() as sct:
        screenshot = np.array(sct.grab(sct.monitors[1]))
    
    # Extraer texto
    results = engine.extract_text_with_location(screenshot)
    
    # Mostrar resultados
    for result in results[:5]:
        print(f"Texto: {result['text']}")
        print(f"Confianza: {result['confidence']}")
        print(f"Centro: {result['center']}")
        print("---")
