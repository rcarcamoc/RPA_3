#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
mysql_auto_starter.py - Módulo para la verificación e inicio automático de MySQL mediante WAMP Server.
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
import subprocess
from pathlib import Path

def is_mysql_port_open(host="127.0.0.1", port=3306, timeout=1.5):
    """Verifica si el puerto 3306 responde a conexiones TCP."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False

def find_wamp_executable():
    """Busca el ejecutable wampmanager.exe de WampServer."""
    candidates = [
        r"C:\wamp64\wampmanager.exe",
        r"C:\wamp\wampmanager.exe"
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None

def find_wamp_mysqld_executable():
    """Busca el ejecutable mysqld.exe dentro de la estructura binaria de WampServer."""
    wamp_mysql_paths = [
        r"C:\wamp64\bin\mysql",
        r"C:\wamp\bin\mysql"
    ]
    for base in wamp_mysql_paths:
        base_path = Path(base)
        if base_path.exists():
            found = list(base_path.glob("**/mysqld.exe"))
            if found:
                return str(found[0])
    return None

def launch_wamp_manager():
    """Lanza WampManager.exe para iniciar los servicios WAMP (Apache + MySQL/MariaDB)."""
    wamp_path = find_wamp_executable()
    if wamp_path:
        print(f"⚠️ Iniciando WampServer desde: {wamp_path}")
        try:
            import ctypes
            result = ctypes.windll.shell32.ShellExecuteW(None, "runas", wamp_path, None, None, 1)
            if result > 32:
                print("✅ Solicitud de inicio de WampManager enviada con éxito.")
                return True
        except Exception as e:
            print(f"⚠️ Error al lanzar WampManager vía ShellExecute: {e}")

        creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        try:
            subprocess.Popen([wamp_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creation_flags)
            print("✅ Proceso WampManager lanzado en segundo plano.")
            return True
        except Exception as e:
            print(f"⚠️ Error al lanzar WampManager vía Popen: {e}")
    else:
        print("⚠️ No se encontró wampmanager.exe en C:\\wamp64 ni C:\\wamp.")
    return False

def ensure_mysql_running(host="127.0.0.1", port=3306, max_wait_seconds=15):
    """
    Verifica si MySQL está activo.
    Si está caído, intenta iniciar el servicio WAMP (wampmysqld64), lanzar WampManager.exe 
    o iniciar directamente el motor mysqld.exe de WAMP en segundo plano (oculto).
    """
    if is_mysql_port_open(host, port):
        return True
        
    print(f"⚠️ MySQL (WAMP) no está activo en {host}:{port}. Iniciando servicios WAMP...")
    
    # 1. Intentar iniciar el servicio de Windows WAMP (wampmysqld64 / wampmariadb64)
    service_names = ["wampmysqld64", "wampmysqld", "wampmariadb64"]
    for svc in service_names:
        try:
            res = subprocess.run(["net", "start", svc], capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                print(f"✅ Servicio WAMP '{svc}' iniciado exitosamente.")
                break
        except Exception:
            pass

    # Verificar si ya levantó con el servicio
    if is_mysql_port_open(host, port, timeout=2):
        print(f"✅ Conexión a MySQL (WAMP) en {host}:{port} establecida.")
        return True

    # 2. Iniciar WampManager
    launch_wamp_manager()

    # 3. Como respaldo inmediato, lanzar el motor mysqld.exe de WAMP si el puerto aún no abre (100% oculto)
    if not is_mysql_port_open(host, port, timeout=2):
        mysqld_path = find_wamp_mysqld_executable()
        if mysqld_path:
            print(f"🚀 Iniciando motor MySQL WAMP en segundo plano ({mysqld_path})...")
            try:
                creation_flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                subprocess.Popen([mysqld_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creation_flags)
            except Exception as e:
                print(f"⚠️ Error al lanzar mysqld de WAMP: {e}")

    # 4. Esperar a que el puerto 3306 esté listo
    start_time = time.time()
    while time.time() - start_time < max_wait_seconds:
        if is_mysql_port_open(host, port, timeout=1.0):
            print(f"✅ MySQL (WAMP) se encuentra en ejecución en {host}:{port}.")
            return True
        time.sleep(1)

    print(f"❌ No se pudo confirmar el inicio de MySQL (WAMP) tras {max_wait_seconds} segundos.")
    return False

if __name__ == "__main__":
    status = ensure_mysql_running()
    print("Estado MySQL WAMP:", "ACTIVO" if status else "INACTIVO")
