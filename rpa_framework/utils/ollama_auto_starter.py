#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ollama_auto_starter.py - Módulo para la verificación e inicio automático del servicio local Ollama.
Optimizado para ejecución en segundo plano y compatibilidad con el entorno RPA Framework.
"""

import os
import sys
import time
import socket
import subprocess
import requests
from pathlib import Path
from typing import Tuple

OLLAMA_HOST = "127.0.0.1"
OLLAMA_PORT = 11434
OLLAMA_BASE_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"
DEFAULT_MODEL = "qwen2.5:3b"

def is_ollama_running(timeout: float = 1.0) -> bool:
    """Verifica si la API de Ollama está respondiendo en el puerto 11434."""
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/version", timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False

def find_ollama_executable() -> str:
    """Busca el ejecutable de Ollama en las ubicaciones estándar de Windows."""
    candidates = []
    
    localappdata = os.environ.get("LOCALAPPDATA")
    if localappdata:
        candidates.append(os.path.join(localappdata, "Programs", "Ollama", "ollama.exe"))
        candidates.append(os.path.join(localappdata, "Programs", "Ollama", "ollama app.exe"))
        
    programfiles = os.environ.get("ProgramFiles")
    if programfiles:
        candidates.append(os.path.join(programfiles, "Ollama", "ollama.exe"))
        
    # Verificar si está en PATH
    try:
        import shutil
        in_path = shutil.which("ollama")
        if in_path:
            candidates.insert(0, in_path)
    except Exception:
        pass
        
    for p in candidates:
        if p and os.path.exists(p):
            return p
            
    return ""

def ensure_ollama_running(max_wait_seconds: int = 12) -> Tuple[bool, str]:
    """
    Verifica si Ollama está en ejecución. Si no lo está, lo inicia en segundo plano
    y espera hasta que la API responda.
    
    Returns:
        (True, "Mensaje de éxito") o (False, "Motivo del error")
    """
    if is_ollama_running():
        return True, "Ollama ya está activo y respondiendo"

    exe_path = find_ollama_executable()
    if not exe_path:
        return False, "Ejecutable de Ollama no encontrado en el sistema"

    print(f"⚠️ Ollama no está activo. Iniciando servicio local desde: {exe_path}...")
    
    try:
        # Configurar variables de entorno óptimas
        env = os.environ.copy()
        env["OLLAMA_KEEP_ALIVE"] = "24h"
        env["OLLAMA_NUM_PARALLEL"] = "1"
        env["CUDA_VISIBLE_DEVICES"] = "0"
        
        # Iniciar en segundo plano totalmente desacoplado (detached)
        creationflags = 0
        if os.name == 'nt':
            DETACHED_PROCESS = 0x00000008
            CREATE_NEW_PROCESS_GROUP = 0x00000200
            CREATE_NO_WINDOW = 0x08000000
            creationflags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW

        # Si el ejecutable es ollama.exe, pasamos el argumento 'serve'
        args = [exe_path]
        if exe_path.lower().endswith("ollama.exe"):
            args.append("serve")

        subprocess.Popen(
            args,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
            close_fds=True
        )
    except Exception as e:
        return False, f"Error al ejecutar Ollama: {e}"

    # Esperar a que la API responda
    start_time = time.time()
    while time.time() - start_time < max_wait_seconds:
        if is_ollama_running(timeout=0.8):
            elapsed = time.time() - start_time
            return True, f"Ollama iniciado exitosamente en {elapsed:.1f}s"
        time.sleep(0.5)

    return False, f"Timeout ({max_wait_seconds}s) esperando a que Ollama responda en {OLLAMA_BASE_URL}"

def verify_model_available(model_name: str = DEFAULT_MODEL) -> bool:
    """Verifica si el modelo especificado está descargado en Ollama."""
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2.0)
        if r.status_code == 200:
            models = [m.get("name", "") for m in r.json().get("models", [])]
            return any(model_name in m for m in models)
    except Exception:
        pass
    return False

if __name__ == "__main__":
    ok, msg = ensure_ollama_running()
    print("Estado Ollama:", "ACTIVO" if ok else "ERROR")
    print("Detalle:", msg)
    if ok:
        has_model = verify_model_available()
        print(f"Modelo '{DEFAULT_MODEL}' disponible:", "SÍ" if has_model else "NO")
