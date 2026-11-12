#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
paddle_auto_starter.py - Módulo para verificar, iniciar y reiniciar automáticamente
el microservicio PaddleOCR GPU.
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

def get_paddle_status_info(port=8095) -> dict:
    """
    Obtiene el estado actual y métricas de ejecución de PaddleOCR GPU:
    - online: bool
    - cuda: bool
    - device: str
    - pid: int or None
    - started_at_str: str (ej: "13:01" o "03/11 13:01")
    - uptime_str: str (ej: "5m", "1h 20m")
    - summary_short: str (ej: "Online (13:01)" o "Offline ❌")
    """
    health = check_paddle_health(port=port, timeout=1.0)
    is_online = (health is not None and health.get("status") == "ok")
    cuda = health.get("cuda", False) if health else False
    device = health.get("device", "N/A") if health else "N/A"
    
    pid = None
    started_at_str = ""
    uptime_str = ""
    
    if is_online:
        try:
            import psutil
            import datetime
            target_proc = None
            for conn in psutil.net_connections(kind='tcp'):
                if conn.laddr and conn.laddr.port == port and conn.pid:
                    try:
                        target_proc = psutil.Process(conn.pid)
                        break
                    except Exception:
                        pass
            if not target_proc:
                for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                    try:
                        cmdline = ' '.join(proc.info.get('cmdline') or [])
                        if 'worker_paddle_gpu.py' in cmdline:
                            target_proc = proc
                            break
                    except Exception:
                        pass
            
            if target_proc:
                pid = target_proc.pid
                st = datetime.datetime.fromtimestamp(target_proc.create_time())
                now = datetime.datetime.now()
                if st.date() == now.date():
                    started_at_str = st.strftime("%H:%M")
                else:
                    started_at_str = st.strftime("%d/%m %H:%M")
                
                total_sec = max(0, int((now - st).total_seconds()))
                if total_sec < 60:
                    uptime_str = f"{total_sec}s"
                elif total_sec < 3600:
                    uptime_str = f"{total_sec // 60}m"
                elif total_sec < 86400:
                    uptime_str = f"{total_sec // 3600}h {(total_sec % 3600) // 60}m"
                else:
                    uptime_str = f"{total_sec // 86400}d {(total_sec % 86400) // 3600}h"
        except Exception:
            pass

    if is_online:
        time_tag = f" ({started_at_str})" if started_at_str else ""
        summary_short = f"Online{time_tag}"
    else:
        summary_short = "Offline ❌"

    return {
        "online": is_online,
        "cuda": cuda,
        "device": device,
        "pid": pid,
        "started_at_str": started_at_str,
        "uptime_str": uptime_str,
        "summary_short": summary_short
    }

def stop_paddle_service(port=8095) -> bool:
    """
    Detiene cualquier instancia previa de PaddleOCR GPU (por puerto TCP o proceso worker_paddle_gpu.py).
    """
    stopped = False
    try:
        import psutil
        pids_killed = []
        for conn in psutil.net_connections(kind='tcp'):
            if conn.laddr and conn.laddr.port == port and conn.pid:
                try:
                    p = psutil.Process(conn.pid)
                    print(f"🛑 [PaddleStarter] Deteniendo proceso en puerto {port} (PID {p.pid})...")
                    p.terminate()
                    pids_killed.append(p)
                    stopped = True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info.get('cmdline') or [])
                if 'worker_paddle_gpu.py' in cmdline:
                    print(f"🛑 [PaddleStarter] Deteniendo worker PaddleOCR (PID {proc.pid})...")
                    proc.terminate()
                    pids_killed.append(proc)
                    stopped = True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        for p in pids_killed:
            try:
                p.wait(timeout=3)
            except (psutil.TimeoutExpired, psutil.NoSuchProcess):
                try:
                    p.kill()
                except Exception:
                    pass
    except Exception as e:
        print(f"⚠️ [PaddleStarter] Error al detener servicio PaddleOCR: {e}")
    return stopped

def start_paddle_service(port=8095) -> bool:
    """
    Lanza el proceso de PaddleOCR GPU en segundo plano con resolución óptima.
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
        env = os.environ.copy()
        env["PADDLE_DET_LIMIT_SIDE_LEN"] = "2048"
        env["PADDLE_DET_LIMIT_TYPE"] = "max"

        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        cmd = [str(venv_gpu_python), str(worker_script), "--server", "--port", str(port)]
        
        subprocess.Popen(
            cmd,
            cwd=str(project_root),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags
        )
        return True
    except Exception as e:
        print(f"❌ [PaddleStarter] Error al lanzar proceso: {e}")
        return False

def restart_paddle_service(port=8095, max_wait_sec=35) -> bool:
    """
    Reinicia forzosamente el microservicio PaddleOCR GPU:
    1. Detiene cualquier proceso previo en el puerto 8095.
    2. Inicia una nueva instancia con resolución nativa completa (det_limit_side_len=2048).
    3. Espera confirmación del endpoint /health.
    """
    print(f"🔄 [PaddleStarter] Reiniciando microservicio PaddleOCR GPU en puerto {port}...")
    stop_paddle_service(port=port)
    time.sleep(1.0)
    
    if not start_paddle_service(port=port):
        return False

    print(f"⏳ [PaddleStarter] Esperando inicio del nuevo servicio (hasta {max_wait_sec}s)...")
    start_time = time.time()
    while time.time() - start_time < max_wait_sec:
        time.sleep(1.0)
        health = check_paddle_health(port=port, timeout=1.0)
        if health and health.get("status") == "ok":
            cuda = health.get("cuda", False)
            dev = health.get("device", "cpu")
            elapsed = time.time() - start_time
            print(f"✅ [PaddleStarter] PaddleOCR GPU reiniciado exitosamente en {elapsed:.1f}s (CUDA: {cuda}, Device: {dev})!")
            return True

    print("⚠️ [PaddleStarter] Tiempo de espera agotado al reiniciar PaddleOCR.")
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
    restart_paddle_service()
