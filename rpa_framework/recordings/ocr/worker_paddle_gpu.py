"""
Worker PaddleOCR con Aceleración GPU (NVIDIA CUDA).
Ejecutado bajo el entorno aislado venv_gpu (Python 3.11 + CUDA).
Soporta:
1. Modo CLI: python worker_paddle_gpu.py --image "ruta/a/imagen.png"
2. Modo Servidor HTTP: python worker_paddle_gpu.py --server --port 8095
"""

import sys
import os
import json
import argparse
import time
import logging

def _setup_nvidia_paths():
    base = sys.prefix
    nvidia_dir = os.path.join(base, "Lib", "site-packages", "nvidia")
    if os.path.isdir(nvidia_dir):
        for sub in os.listdir(nvidia_dir):
            bin_path = os.path.join(nvidia_dir, sub, "bin")
            if os.path.isdir(bin_path):
                if bin_path not in os.environ["PATH"]:
                    os.environ["PATH"] = bin_path + os.pathsep + os.environ["PATH"]
                if hasattr(os, "add_dll_directory"):
                    try:
                        os.add_dll_directory(bin_path)
                    except Exception:
                        pass

_setup_nvidia_paths()

# Configurar logging básico
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger("PaddleGPUWorker")

_OCR_INSTANCE = None

def get_ocr_engine():
    global _OCR_INSTANCE
    if _OCR_INSTANCE is None:
        import paddle
        from paddleocr import PaddleOCR
        
        has_cuda = paddle.device.is_compiled_with_cuda()
        logger.info(f"Inicializando PaddleOCR... CUDA disponible: {has_cuda}, Device: {paddle.device.get_device()}")
        
        try:
            _OCR_INSTANCE = PaddleOCR(
                use_angle_cls=False,
                lang='es',
                use_gpu=has_cuda,
                show_log=False
            )
            logger.info(f"PaddleOCR inicializado exitosamente (use_gpu={has_cuda}).")
        except Exception as e:
            if has_cuda:
                logger.warning(f"Fallo al inicializar con GPU ({e}). Reintentando con CPU...")
                _OCR_INSTANCE = PaddleOCR(
                    use_angle_cls=False,
                    lang='es',
                    use_gpu=False,
                    show_log=False
                )
                logger.info("PaddleOCR inicializado exitosamente en modo CPU.")
            else:
                raise
    return _OCR_INSTANCE


def process_image(img_path: str, confidence_threshold: float = 0.5):
    """
    Procesa una imagen y retorna los textos formateados en el esquema de OCREngine.
    """
    if not os.path.isfile(img_path):
        raise FileNotFoundError(f"No se encontró el archivo: {img_path}")
        
    ocr = get_ocr_engine()
    
    try:
        t0 = time.perf_counter()
        res = ocr.ocr(img_path, cls=False)
        elapsed = time.perf_counter() - t0
    except Exception as e:
        logger.warning(f"Error en inferencia ({e}). Reintentando con motor de respaldo CPU...")
        from paddleocr import PaddleOCR
        cpu_ocr = PaddleOCR(use_angle_cls=False, lang='es', use_gpu=False, show_log=False)
        t0 = time.perf_counter()
        res = cpu_ocr.ocr(img_path, cls=False)
        elapsed = time.perf_counter() - t0
    
    text_data = []
    if not res or not res[0]:
        return {"elapsed_s": round(elapsed, 4), "results": []}

    for item in res[0]:
        if not item or len(item) < 2:
            continue
        box = item[0]  # [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
        text_info = item[1]  # ('texto', score)
        text = str(text_info[0]).strip()
        confidence = float(text_info[1])
        
        if not text or confidence < confidence_threshold:
            continue
            
        xs = [pt[0] for pt in box]
        ys = [pt[1] for pt in box]
        x_min, x_max = float(min(xs)), float(max(xs))
        y_min, y_max = float(min(ys)), float(max(ys))
        w = x_max - x_min
        h = y_max - y_min
        
        text_data.append({
            'text': text,
            'confidence': round(confidence, 4),
            'bbox': box,
            'bounds': {
                'x_min': round(x_min, 1),
                'y_min': round(y_min, 1),
                'x_max': round(x_max, 1),
                'y_max': round(y_max, 1)
            },
            'center': {
                'x': round(x_min + w / 2, 1),
                'y': round(y_min + h / 2, 1)
            },
            'dimensions': {
                'width': round(w, 1),
                'height': round(h, 1)
            }
        })
        
    return {"elapsed_s": round(elapsed, 4), "results": text_data}


def run_cli(image_path: str, conf_threshold: float = 0.5):
    try:
        out = process_image(image_path, conf_threshold)
        print(json.dumps(out))
    except Exception as e:
        print(json.dumps({"error": str(e), "results": []}))
        sys.exit(1)


def run_server(port: int = 8095):
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
    import uvicorn

    app = FastAPI(title="PaddleOCR GPU Service")

    class OCRRequest(BaseModel):
        image_path: str
        confidence_threshold: float = 0.5

    @app.on_event("startup")
    def startup():
        # Pre-cargar modelos en GPU durante el inicio
        get_ocr_engine()

    @app.get("/health")
    def health():
        import paddle
        return {
            "status": "ok",
            "cuda": paddle.device.is_compiled_with_cuda(),
            "device": paddle.device.get_device()
        }

    @app.post("/ocr")
    def ocr_endpoint(req: OCRRequest):
        try:
            return process_image(req.image_path, req.confidence_threshold)
        except FileNotFoundError as fnf:
            raise HTTPException(status_code=404, detail=str(fnf))
        except Exception as e:
            logger.exception("Error procesando imagen")
            raise HTTPException(status_code=500, detail=str(e))

    logger.info(f"Iniciando PaddleOCR GPU Server en http://127.0.0.1:{port}...")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PaddleOCR GPU Worker")
    parser.add_argument("--image", type=str, help="Ruta a la imagen para OCR (modo CLI)")
    parser.add_argument("--server", action="store_true", help="Iniciar servidor FastAPI continuo")
    parser.add_argument("--port", type=int, default=8095, help="Puerto para servidor FastAPI")
    parser.add_argument("--conf", type=float, default=0.5, help="Umbral de confianza")

    args = parser.parse_args()

    if args.server:
        run_server(args.port)
    elif args.image:
        run_cli(args.image, args.conf)
    else:
        # Si no se pasan argumentos pero se ejecuta directamente, prueba rápida
        print("Modo de uso:")
        print("  python worker_paddle_gpu.py --image <ruta>")
        print("  python worker_paddle_gpu.py --server --port 8095")
