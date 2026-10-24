#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
paddle_auto_starter.py - Módulo para verificar e iniciar automáticamente el microservicio PaddleOCR GPU.
"""

import os
import sys

if hasattr(sys.stdout, 'reconfigure') and sys.stdout is not None:
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import time
import socket
import urllib.request
import urllib.error
import json
import subprocess
from pathlib import Path
import logging

logger = logging.getLogger("PaddleAutoStarter")

def is_port_open(host="127.0.0.1", port=8095, timeout=1.0) -> bool:
    """Verifica si el puerto responde a nivel TCP."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False

def check_paddle_health(port=8095, timeout=2.0) -> dict:
    """
    Consulta el endpoint /health de PaddleOCR GPU.
    Retorna un diccionario con el estado o None si no responde.
    """
    url = f"http://127.0.0.1:{port}/health"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8"))
    except Exception:
        pass
    return None

def start_paddle_service(port=8095) -> bool:
    """
    Lanza el proceso de PaddleOCR GPU en segundo plano.
    """
    # Localizar raíz del proyecto
    curr = Path(__file__).resolve()
    # curr: rpa_framework/utils/paddle_auto_starter.py -> parents[2] es RPA_3
    project_root = curr.parents[2]
    venv_gpu_python = project_root / "venv_gpu" / "Scripts" / "python.exe"
    worker_script = project_root / "rpa_framework" / "recordings" / "ocr" / "worker_paddle_gpu.py"
    
    if not venv_gpu_python.exists():
        print(f"⚠️ [PaddleStarter] No se encontró el entorno venv_gpu: {venv_gpu_python}")
        return False
        
    if not worker_script.exists():
        print(f"⚠️ [PaddleStarter] No se encontró el worker script: {worker_script}")
        return False

    print(f"🚀 [PaddleStarter] Lanzando microservicio PaddleOCR GPU en puerto {port}...")
    try:
        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        cmd = [str(venv_gpu_python), str(worker_script), "--server", "--port", str(port)]
        
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags
        )
        return True
    except Exception as e:
        print(f"❌ [PaddleStarter] Error al lanzar proceso: {e}")
        return False

def ensure_paddle_running(port=8095, max_wait_sec=25) -> bool:
    """
    Valida que el servicio PaddleOCR GPU esté corriendo y responda correctamente.
    Si no está corriendo, intenta iniciarlo automáticamente y espera su disponibilidad.
    """
    print(f"🔍 [PaddleStarter] Verificando disponibilidad de PaddleOCR GPU (puerto {port})...")
    
    # 1. Verificar si ya está activo y respondiendo
    health = check_paddle_health(port=port)
    if health and health.get("status") == "ok":
        cuda = health.get("cuda", False)
        dev = health.get("device", "cpu")
        print(f"✅ [PaddleStarter] PaddleOCR GPU ya está activo y respondiendo (CUDA: {cuda}, Device: {dev}).")
        return True
        
    # 2. Si no responde, intentar arrancarlo
    if not start_paddle_service(port=port):
        return False
        
    # 3. Esperar a que el servicio inicialice y responda
    print(f"⏳ [PaddleStarter] Esperando inicio del servicio (hasta {max_wait_sec}s)...")
    start_time = time.time()
    while time.time() - start_time < max_wait_sec:
        time.sleep(1.0)
        health = check_paddle_health(port=port, timeout=1.0)
        if health and health.get("status") == "ok":
            cuda = health.get("cuda", False)
            dev = health.get("device", "cpu")
            elapsed = time.time() - start_time
            print(f"✅ [PaddleStarter] PaddleOCR GPU inicializado y listo en {elapsed:.1f}s (CUDA: {cuda}, Device: {dev})!")
            return True
            
    print("⚠️ [PaddleStarter] Tiempo de espera agotado; el servicio aún no responde. Se usará modo CLI bajo demanda.")
    return False

if __name__ == "__main__":
    ensure_paddle_running()
