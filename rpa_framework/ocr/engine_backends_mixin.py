# -*- coding: utf-8 -*-
"""
Mixin de backends OCR (EasyOCR, Tesseract, PaddleOCR) y preprocesamiento de imágenes
para OCREngine. Extraído de rpa_framework/ocr/engine.py.
"""

import os
import logging
from typing import List, Dict, Optional
import cv2
import numpy as np
import pytesseract
from PIL import Image

try:
    from recordings.ocr.utilidades.preproceso_ocr import preprocess_high_fidelity
    HAS_PREPROCESS_UTILS = True
except ImportError:
    HAS_PREPROCESS_UTILS = False

logger = logging.getLogger(__name__)


class OCREngineBackendsMixin:
    """Mixin con la inicialización, extracción por motor y preprocesamiento de OCREngine."""

    def _init_easyocr(self, model_storage_dir: Optional[str]):
        """Inicializar EasyOCR"""
        try:
            import easyocr
            self.reader = easyocr.Reader(
                [self.language],
                gpu=self.use_gpu,
                model_storage_directory=model_storage_dir
            )
            logger.info("EasyOCR inicializado correctamente")
        except ImportError:
            logger.error("EasyOCR no está instalado. Instalar con: pip install easyocr")
            raise
        except Exception as e:
            logger.error(f"Error inicializando EasyOCR: {e}")
            raise

    def _init_tesseract(self):
        """Inicializar Tesseract"""
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

    def _init_paddleocr(self):
        """Inicializar PaddleOCR (priorizando GPU worker via venv_gpu)"""
        try:
            from ocr.paddle_gpu_client import PaddleGPUClient
            client = PaddleGPUClient()
            if client.is_available:
                self.paddle_gpu_client = client
                logger.info("✅ PaddleOCR GPU Client configurado correctamente (venv_gpu)")
                return
        except Exception as e:
            logger.warning(f"No se pudo configurar PaddleGPUClient: {e}")

        try:
            from paddleocr import PaddleOCR
            lang = 'es' if self.language in ['es', 'spa'] else self.language
            self.paddle_ocr = PaddleOCR(
                lang=lang,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False
            )
            logger.info("PaddleOCR (local) inicializado correctamente")
        except ImportError:
            logger.error("PaddleOCR no está instalado localmente ni disponible en venv_gpu.")
            raise
        except Exception as e:
            logger.error(f"Error inicializando PaddleOCR: {e}")
            raise

    def _resize_if_needed(self, image: np.ndarray, max_dimension: int = 6000) -> np.ndarray:
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
            if confidence < self.confidence_threshold:
                continue
            
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
        if len(image.shape) == 2:
            image_rgb = image
        else:
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        if self.preprocess:
            pil_img = Image.fromarray(image_rgb)
            pil_img = self._preprocess_image_pil(pil_img)
            image_to_process = pil_img
            
            processed_np = np.array(pil_img)
            if len(processed_np.shape) == 2:
                self.last_processed_image = cv2.cvtColor(processed_np, cv2.COLOR_GRAY2BGR)
            else:
                self.last_processed_image = cv2.cvtColor(processed_np, cv2.COLOR_RGB2BGR)
        else:
            image_to_process = image_rgb
            if len(image.shape) == 2:
                self.last_processed_image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
            elif image.shape[2] == 3:
                self.last_processed_image = image
            else:
                self.last_processed_image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR) if image.shape[2] == 4 else image
        
        try:
            from pytesseract import Output
            data = pytesseract.image_to_data(
                image_to_process,
                lang=self.language,
                output_type=Output.DICT,
                config=self.custom_config
            )
        except Exception:
            data = pytesseract.image_to_data(image_to_process, lang=self.language, config=self.custom_config)
        
        text_data = []
        scale = self.scale_factor if self.preprocess else 1.0
        
        for i in range(len(data['text'])):
            text = data['text'][i].strip()
            
            if not text:
                continue
            
            confidence = float(data['conf'][i]) / 100.0
            
            if confidence < self.confidence_threshold:
                continue
            
            x_scaled = int(data['left'][i])
            y_scaled = int(data['top'][i])
            w_scaled = int(data['width'][i])
            h_scaled = int(data['height'][i])
            
            x = x_scaled / scale
            y = y_scaled / scale
            w = w_scaled / scale
            h = h_scaled / scale
            
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

    def _extract_paddleocr(self, image: np.ndarray, detail: bool = True) -> List[Dict]:
        """Extraer texto usando PaddleOCR (priorizando GPU worker via venv_gpu)"""
        if hasattr(self, 'paddle_gpu_client') and self.paddle_gpu_client and self.paddle_gpu_client.is_available:
            return self.paddle_gpu_client.extract_text(image, self.confidence_threshold)

        if self.paddle_ocr is None:
            logger.error("PaddleOCR no inicializado")
            return []

        if hasattr(self.paddle_ocr, 'predict'):
            res = self.paddle_ocr.predict(image)
            text_data = []
            if not res:
                return text_data

            rec_texts = res[0].get('rec_texts', [])
            rec_scores = res[0].get('rec_scores', [])
            rec_boxes = res[0].get('rec_boxes', [])

            for text, score, box in zip(rec_texts, rec_scores, rec_boxes):
                text = text.strip()
                if not text:
                    continue
                conf = float(score)
                if conf < self.confidence_threshold:
                    continue

                x_min, y_min, x_max, y_max = float(box[0]), float(box[1]), float(box[2]), float(box[3])
                w = max(0.0, x_max - x_min)
                h = max(0.0, y_max - y_min)

                text_info = {
                    'text': text,
                    'confidence': conf,
                    'bbox': [[x_min, y_min], [x_max, y_min], [x_max, y_max], [x_min, y_max]],
                    'bounds': {
                        'x_min': x_min,
                        'y_min': y_min,
                        'x_max': x_max,
                        'y_max': y_max,
                    },
                    'center': {
                        'x': x_min + w / 2.0,
                        'y': y_min + h / 2.0,
                    },
                    'dimensions': {
                        'width': w,
                        'height': h,
                    }
                }
                text_data.append(text_info)
            logger.info(f"PaddleOCR: Extraídos {len(text_data)} textos")
            return text_data
        else:
            res = self.paddle_ocr.ocr(image, cls=False)
            text_data = []
            if not res or not res[0]:
                return text_data
            for item in res[0]:
                box = item[0]
                text_info = item[1]
                text = str(text_info[0]).strip()
                conf = float(text_info[1])
                if not text or conf < self.confidence_threshold:
                    continue
                xs = [pt[0] for pt in box]
                ys = [pt[1] for pt in box]
                x_min, x_max = float(min(xs)), float(max(xs))
                y_min, y_max = float(min(ys)), float(max(ys))
                w = max(0.0, x_max - x_min)
                h = max(0.0, y_max - y_min)
                text_data.append({
                    'text': text,
                    'confidence': conf,
                    'bbox': box,
                    'bounds': {'x_min': x_min, 'y_min': y_min, 'x_max': x_max, 'y_max': y_max},
                    'center': {'x': x_min + w / 2.0, 'y': y_min + h / 2.0},
                    'dimensions': {'width': w, 'height': h}
                })
            logger.info(f"PaddleOCR: Extraídos {len(text_data)} textos")
            return text_data

    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocesar imagen para mejorar OCR (CV2).
        Aplicable cuando la calidad es baja.
        """
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        return enhanced

    def _preprocess_image_pil(self, img: Image.Image) -> Image.Image:
        """
        Preprocesar imagen usando el módulo de utilidades.
        Wrapper para mantener compatibilidad.
        """
        if HAS_PREPROCESS_UTILS:
            processed, scale = preprocess_high_fidelity(img, scale_factor=3, threshold_floor=100)
            self.scale_factor = scale
            return processed
        else:
            logger.warning("Módulo preproceso_ocr no disponible, usando fallback básico")
            return self._preprocess_image_pil_fallback(img)

    def _preprocess_image_pil_fallback(self, img: Image.Image) -> Image.Image:
        """Preprocesamiento básico de fallback."""
        img_np = np.array(img)
        
        scale = 3
        self.scale_factor = scale
        upscaled = cv2.resize(img_np, None, fx=scale, fy=scale, interpolation=cv2.INTER_LANCZOS4)
        
        gray = cv2.cvtColor(upscaled, cv2.COLOR_RGB2GRAY)
        
        _, thresh_base = cv2.threshold(gray, 100, 255, cv2.THRESH_TOZERO)
        _, final_binary = cv2.threshold(thresh_base, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        final_bw = cv2.bitwise_not(final_binary)
        return Image.fromarray(final_bw)
