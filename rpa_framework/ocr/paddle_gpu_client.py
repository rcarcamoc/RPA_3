# rpa_framework/ocr/paddle_gpu_client.py

import os
import sys
import json
import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Optional, Union
import cv2
import numpy as np

logger = logging.getLogger(__name__)

class PaddleGPUClient:
    """
    Cliente para PaddleOCR ejecutado en GPU mediante el entorno aislado venv_gpu.
    
    Estrategia de conexión dual:
    1. HTTP Microservice (localhost:8095): Si el servicio está activo, tiempo de respuesta ~150-300ms.
    2. Subprocess CLI: Si el microservicio no está activo, ejecuta directamente venv_gpu/python worker_paddle_gpu.py
    """
    
    def __init__(self, port: int = 8095):
        self.port = port
        self.server_url = f"http://127.0.0.1:{port}"
        
        # Localizar paths
        # Buscamos la raíz del proyecto (donde reside venv_gpu)
        curr = Path(__file__).resolve()
        # curr: rpa_framework/ocr/paddle_gpu_client.py -> parents[2] es RPA_3
        self.project_root = curr.parents[2]
        self.venv_gpu_python = self.project_root / "venv_gpu" / "Scripts" / "python.exe"
        self.worker_script = self.project_root / "rpa_framework" / "recordings" / "ocr" / "worker_paddle_gpu.py"
        
        # Directorio temporal para imágenes numpy
        self.temp_dir = self.project_root / "rpa_framework" / "log"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.temp_img_path = str(self.temp_dir / "_paddle_gpu_temp.png")
        
        self.is_available = self.venv_gpu_python.exists() and self.worker_script.exists()
        if not self.is_available:
            logger.warning(f"PaddleGPUClient: No se encontró venv_gpu ({self.venv_gpu_python}) o worker ({self.worker_script})")

    def _call_http(self, img_path: str, confidence_threshold: float) -> Optional[List[Dict]]:
        """Intenta llamar al servidor HTTP si está levantado."""
        try:
            import urllib.request
            import urllib.error
            
            req_data = json.dumps({
                "image_path": img_path,
                "confidence_threshold": confidence_threshold
            }).encode('utf-8')
            
            req = urllib.request.Request(
                f"{self.server_url}/ocr",
                data=req_data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            # Timeout corto de 5s para no bloquear si no está corriendo
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                if resp.status == 200:
                    payload = json.loads(resp.read().decode('utf-8'))
                    elapsed = payload.get("elapsed_s", 0)
                    results = payload.get("results", [])
                    logger.info(f"⚡ PaddleOCR GPU (HTTP) procesó imagen en {elapsed*1000:.1f}ms - {len(results)} textos.")
                    return results
        except Exception as e:
            # Fallo silencioso hacia CLI
            logger.debug(f"PaddleOCR HTTP no disponible ({e}), usando CLI...")
        return None

    def _call_cli(self, img_path: str, confidence_threshold: float) -> List[Dict]:
        """Ejecuta el worker directamente en un subproceso aislado."""
        if not self.is_available:
            logger.error("PaddleGPUClient no disponible.")
            return []
            
        cmd = [
            str(self.venv_gpu_python),
            str(self.worker_script),
            "--image", img_path,
            "--conf", str(confidence_threshold)
        ]
        
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            if proc.returncode != 0:
                logger.error(f"Error ejecutando PaddleGPU CLI: {proc.stderr}")
                return []
                
            stdout = proc.stdout.strip()
            # Buscar el bloque JSON en stdout (evitando posibles logs de CUDA)
            json_start = stdout.find('{')
            json_end = stdout.rfind('}')
            if json_start != -1 and json_end != -1:
                data = json.loads(stdout[json_start:json_end+1])
                elapsed = data.get("elapsed_s", 0)
                results = data.get("results", [])
                logger.info(f"🚀 PaddleOCR GPU (CLI) procesó imagen en {elapsed*1000:.1f}ms - {len(results)} textos.")
                return results
            else:
                logger.error(f"Formato no JSON recibido de worker: {stdout}")
                return []
        except subprocess.TimeoutExpired:
            logger.error("Timeout (30s) esperando resultado de PaddleOCR GPU.")
            return []
        except Exception as e:
            logger.error(f"Excepción en PaddleGPU CLI: {e}")
            return []

    def extract_text(self, image: Union[str, np.ndarray], confidence_threshold: float = 0.5) -> List[Dict]:
        """
        Extrae texto de una ruta o imagen np.ndarray con aceleración GPU.
        Retorna la lista de diccionarios en formato estandarizado.
        """
        temp_created = False
        img_path = ""
        
        if isinstance(image, str):
            img_path = os.path.abspath(image)
        elif isinstance(image, np.ndarray):
            # Guardar temporal
            cv2.imwrite(self.temp_img_path, image)
            img_path = self.temp_img_path
            temp_created = True
        else:
            raise TypeError(f"Tipo de imagen no soportado: {type(image)}")
            
        try:
            # 1. Intentar HTTP
            results = self._call_http(img_path, confidence_threshold)
            if results is not None:
                return results
                
            # 2. Fallback a CLI
            return self._call_cli(img_path, confidence_threshold)
        finally:
            # No eliminamos temp_img_path necesariamente para no crear I/O lock,
            # pero podemos mantenerlo sobrescribible
            pass
