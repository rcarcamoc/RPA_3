#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
setup_startup_service.py - Configura el inicio automático del Servicio de Notificaciones en Windows.
"""

import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
import subprocess
import winreg
from pathlib import Path

TASK_NAME = "RPA_Servicio_Notificaciones_Telegram"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENV_PYTHONW = PROJECT_ROOT / "venv" / "Scripts" / "pythonw.exe"
BOT_SCRIPT = PROJECT_ROOT / "rpa_framework" / "servicio_bot_telegram.py"
BAT_SCRIPT = PROJECT_ROOT / "Iniciar_Servicio_Notificaciones.bat"

def get_startup_folder():
    appdata = os.environ.get("APPDATA")
    if appdata:
        startup_path = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        if startup_path.exists():
            return startup_path
    return None

def install_service():
    print("🚀 Configurando inicio automático del servicio de notificaciones...")
    
    pythonw_path = str(VENV_PYTHONW) if VENV_PYTHONW.exists() else "pythonw.exe"
    bot_path = str(BOT_SCRIPT)
    bat_path = str(BAT_SCRIPT)
    
    # 1. Programador de Tareas de Windows (schtasks)
    cmd = [
        "schtasks", "/Create",
        "/TN", TASK_NAME,
        "/TR", f'"{pythonw_path}" "{bot_path}"',
        "/SC", "ONLOGON",
        "/F"
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if res.returncode == 0:
            print("  ✅ Tarea programada registrada exitosamente en Windows (schtasks).")
        else:
            print(f"  ⚠️ Advertencia en schtasks: {res.stderr.strip()}")
    except Exception as e:
        print(f"  ⚠️ Error al intentar registrar tarea programada: {e}")

    # 2. Carpeta de Inicio de Windows (shell:startup) mediante VBS (ejecución invisible)
    startup_dir = get_startup_folder()
    if startup_dir:
        vbs_file = startup_dir / "RPA_Servicio_Notificaciones.vbs"
        vbs_content = f'Set WshShell = CreateObject("WScript.Shell")\n' \
                      f'WshShell.Run """{pythonw_path}"" ""{bot_path}""", 0, False\n'
        try:
            with open(vbs_file, "w", encoding="utf-8") as f:
                f.write(vbs_content)
            print(f"  ✅ Script de inicio VBS creado en Startup: {vbs_file}")
        except Exception as e:
            print(f"  ⚠️ Error al crear script en carpeta Startup: {e}")

    # 3. Registro de Windows (HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run)
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "RPA_Servicio_Notificaciones", 0, winreg.REG_SZ, f'"{pythonw_path}" "{bot_path}"')
        winreg.CloseKey(key)
        print("  ✅ Clave agregada al Registro de Windows (HKCU Run).")
    except Exception as e:
        print(f"  ⚠️ Error al actualizar Registro de Windows: {e}")

    print("\n🎉 ¡El servicio de notificaciones quedará activo automáticamente al iniciar Windows!")

def remove_service():
    print("🗑️ Removiendo inicio automático del servicio de notificaciones...")
    
    # 1. Eliminar tarea schtasks
    cmd = ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if res.returncode == 0:
            print("  ✅ Tarea programada eliminada.")
        else:
            print(f"  ℹ️ Tarea programada no encontrada o ya eliminada.")
    except Exception as e:
        print(f"  ⚠️ Error al eliminar tarea programada: {e}")

    # 2. Eliminar VBS de Startup
    startup_dir = get_startup_folder()
    if startup_dir:
        vbs_file = startup_dir / "RPA_Servicio_Notificaciones.vbs"
        if vbs_file.exists():
            try:
                vbs_file.unlink()
                print("  ✅ Script VBS eliminado de carpeta Startup.")
            except Exception as e:
                print(f"  ⚠️ Error al eliminar script VBS: {e}")

    # 3. Eliminar clave de Registro
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_ALL_ACCESS)
        winreg.DeleteValue(key, "RPA_Servicio_Notificaciones")
        winreg.CloseKey(key)
        print("  ✅ Clave eliminada del Registro de Windows.")
    except Exception:
        print("  ℹ️ Clave del registro no encontrada o ya eliminada.")

    print("\n✅ Inicio automático removido correctamente.")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "remove":
        remove_service()
    else:
        install_service()
