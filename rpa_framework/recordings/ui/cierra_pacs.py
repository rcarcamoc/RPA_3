#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script RPA: Cierra la aplicación Carestream RIS / Vue PACS y procesos asociados.
Cierra:
- Carestream Vue PACS (mp.exe)
- Carestream RIS V11 Client / RIS Client (Carestream RIS.exe / RISClient.exe)
- csps_win.exe, vv_client.exe y procesos relacionados.
"""

import sys
import os
import re
import time
import logging
import psutil
import subprocess
from pathlib import Path

# Configurar path para importar utilidades del framework
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pywinauto import Application, Desktop
import pywinauto.findwindows as fw

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("cierra_pacs")

# Feedback visual
try:
    from rpa_framework.utils.visual_feedback import VisualFeedback
    vf = VisualFeedback()
except Exception:
    try:
        from utils.visual_feedback import VisualFeedback
        vf = VisualFeedback()
    except Exception:
        vf = None

# Lista de títulos a cerrar
TITULOS_CARESTREAM = [
    "Carestream Vue PACS",
    "Carestream RIS",
    "Carestream RIS V11 Client",
    "RIS Client",
    "Carestream Radiology Client",
    "Carestream Vue RIS",
    "PACS - Carestream",
    "Workflow Information Management",
    "Philips Workflow Information Management"
]

# Procesos conocidos que deben cerrarse
PROCESOS_CARESTREAM = [
    "mp.exe", 
    "csps_win.exe", 
    "RISClient.exe", 
    "CarestreamRIS.exe",
    "Carestream RIS.exe",
    "Vue RIS.exe",
    "vv_client.exe"
]


def cerrar_pacs():
    """Cierra todos los programas y procesos Carestream / RIS PACS."""
    logger.info("🔒 Iniciando cierre de Carestream RIS PACS...")
    if vf:
        vf.wait(1, "Cerrando RIS PACS...")

    # 1. CERRAR POR VENTANAS
    for titulo in TITULOS_CARESTREAM:
        try:
            ventanas = fw.find_windows(title_re=re.compile(f".*{re.escape(titulo)}.*", re.I))
            if ventanas:
                logger.info(f"   Cerrando {len(ventanas)} ventana(s) de '{titulo}'")
                for hwnd in ventanas:
                    try:
                        app_tmp = Application(backend="win32").connect(handle=hwnd, timeout=1)
                        app_tmp.kill()
                        time.sleep(0.3)
                    except Exception:
                        pass
        except Exception:
            pass

    # 2. DETENER PROCESOS POR POWERSHELL
    logger.info("   Deteniendo procesos Carestream por comando de sistema...")
    ps_cmd = 'Get-Process | Where-Object { $_.Description -match "Carestream Radiology Client|Carestream Vue PACS|Carestream RIS" -or $_.MainWindowTitle -match "Carestream" } | Where-Object { $_.Name -notmatch "svchost|carestream_host" } | Stop-Process -Force'
    try:
        cflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True, creationflags=cflags)
    except Exception as e:
        logger.warning(f"Error al ejecutar powershell stop-process: {e}")

    # 3. MATAR PROCESOS DIRECTAMENTE
    logger.info("   Verificando y terminando procesos remanentes...")
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            name_lower = proc.info['name'].lower()
            if any(p.lower() == name_lower for p in PROCESOS_CARESTREAM) or \
               ("carestream" in name_lower and name_lower != "carestream_host.exe"):
                logger.info(f"      Terminando {name_lower} (PID: {proc.pid})")
                proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # 4. ESPERA DE CONFIRMACIÓN
    timeout = 5
    while timeout > 0:
        pacs_vivos = [
            p for p in psutil.process_iter(['name']) 
            if p.info['name'].lower() in [n.lower() for n in PROCESOS_CARESTREAM]
        ]
        if not pacs_vivos:
            break
        time.sleep(1)
        timeout -= 1

    logger.info("✅ Cierre de Carestream RIS PACS completado.")
    return True


def main():
    try:
        cerrar_pacs()
        return 0
    except Exception as e:
        logger.error(f"Error durante el cierre de PACS: {e}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
