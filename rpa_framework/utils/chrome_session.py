#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Utilidad centralizada para gestionar la sesión de Chrome RPA en el puerto de depuración (9222).

Provee:
- Detección rápida de puerto abierto.
- Limpieza selectiva de procesos Chrome/ChromeDriver asociados al perfil RPA (sin tocar sesiones personales)
  y eliminación de archivos de bloqueo residuales (SingletonLock, etc.).
- Conexión a instancia existente con validación de pestaña/URL esperada.
- Lanzamiento con auto-reparación (si falla el perfil o el puerto está colgado, limpia y reintenta),
  evitando el fallback silencioso a Chrome sin puerto de depuración.
"""

import socket
import time
from pathlib import Path
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions

DEFAULT_DEBUG_PORT = 9222
DEFAULT_PROFILE_DIR = (
    Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data" / "RPA_Remote_Profile"
)
_LOCK_FILES = ("SingletonLock", "SingletonCookie", "SingletonSocket", "DevToolsActivePort")


def is_debug_port_open(port: int = DEFAULT_DEBUG_PORT, timeout: float = 0.5) -> bool:
    """Verifica rápidamente si el puerto de depuración local está escuchando."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            return s.connect_ex(("127.0.0.1", port)) == 0
    except Exception:
        return False


def cleanup_rpa_chrome(
    port: int = DEFAULT_DEBUG_PORT,
    profile_dir: Optional[Path] = None,
) -> int:
    """
    Cierra procesos Chrome/ChromeDriver huérfanos asociados al RPA (por puerto o perfil)
    y elimina archivos de bloqueo residuales en el directorio del perfil.
    No afecta ventanas personales de Chrome que usen otro perfil/puerto.
    """
    target_profile = Path(profile_dir) if profile_dir else DEFAULT_PROFILE_DIR
    profile_marker = target_profile.name.lower()
    port_marker = f"--remote-debugging-port={port}"
    terminated = 0

    try:
        import psutil

        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                name = (proc.info.get("name") or "").lower()
                if "chrome" not in name:
                    continue
                cmdline = " ".join(proc.info.get("cmdline") or []).lower()
                if port_marker in cmdline or f" {port}" in cmdline or profile_marker in cmdline:
                    proc.terminate()
                    try:
                        proc.wait(timeout=2)
                    except psutil.TimeoutExpired:
                        proc.kill()
                    terminated += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except ImportError:
        print("[WARNING] psutil no está instalado; omitiendo limpieza de procesos Chrome.", flush=True)
    except Exception as e:
        print(f"[WARNING] Error limpiando procesos Chrome RPA: {e}", flush=True)

    # Eliminar archivos de bloqueo residuales del perfil RPA
    if target_profile.exists():
        for lock_name in _LOCK_FILES:
            lock_file = target_profile / lock_name
            if lock_file.exists():
                try:
                    lock_file.unlink()
                except Exception:
                    pass

    if terminated > 0:
        print(
            f"[AUTO-REPAIR] Se cerraron {terminated} proceso(s) Chrome/Driver huérfanos del RPA.",
            flush=True,
        )
        time.sleep(1.0)
    else:
        time.sleep(0.3)

    return terminated


def focus_tab_matching(driver: webdriver.Chrome, url_substring: str) -> bool:
    """
    Asegura que la pestaña activa contenga `url_substring`.
    Si la pestaña actual no coincide, busca entre todos los window_handles y cambia a la primera coincidente.
    """
    needle = url_substring.lower()
    try:
        current = (driver.current_url or "").lower()
        if needle in current:
            return True
    except Exception:
        pass

    try:
        for handle in driver.window_handles:
            driver.switch_to.window(handle)
            current = (driver.current_url or "").lower()
            if needle in current:
                return True
    except Exception:
        pass

    return False


def _launch_chrome_with_debug_port(
    port: int,
    profile_dir: Path,
    maximize: bool = True,
    headless: bool = False,
    detach: bool = True,
) -> webdriver.Chrome:
    """Lanza una nueva instancia de Chrome con remote-debugging-port y perfil dedicado."""
    launch_options = ChromeOptions()
    launch_options.add_argument(f"--remote-debugging-port={port}")
    launch_options.add_argument("--no-sandbox")
    launch_options.add_argument("--disable-dev-shm-usage")
    launch_options.add_argument(f"--user-data-dir={profile_dir}")
    if maximize and not headless:
        launch_options.add_argument("--start-maximized")
    if headless:
        launch_options.add_argument("--headless=new")
    if detach:
        launch_options.add_experimental_option("detach", True)
    return webdriver.Chrome(options=launch_options)


def connect_or_launch_rpa_chrome(
    port: int = DEFAULT_DEBUG_PORT,
    profile_dir: Optional[Path] = None,
    maximize: bool = True,
    headless: bool = False,
    allow_launch: bool = True,
    expected_url_substr: Optional[str] = None,
    max_launch_attempts: int = 2,
) -> webdriver.Chrome:
    """
    Conecta al Chrome RPA en `port` o lo lanza con auto-reparación si está caído/bloqueado.

    Args:
        port: Puerto de depuración remota (default 9222).
        profile_dir: Directorio de perfil dedicado al RPA.
        maximize: Maximizar ventana si se lanza una nueva instancia.
        headless: Ejecutar en modo headless si se lanza una nueva instancia.
        allow_launch: Si False, exige conectarse a una instancia ya abierta (útil en nodos posteriores).
        expected_url_substr: Si se indica al conectar a una instancia existente, exige que exista
            una pestaña cuya URL contenga este texto (p. ej. 'ris.chile.telemedicina.com').
        max_launch_attempts: Intentos de lanzamiento (el 2do intento ejecuta auto-limpieza previa).
    """
    target_profile = Path(profile_dir) if profile_dir else DEFAULT_PROFILE_DIR

    # --- ESTRATEGIA 1: CONECTAR A INSTANCIA EXISTENTE ---
    if is_debug_port_open(port):
        try:
            print(f"[INFO] Puerto {port} detectado. Intentando conectar...", flush=True)
            attach_options = ChromeOptions()
            attach_options.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
            driver = webdriver.Chrome(options=attach_options)
            print("[INFO] Conexión exitosa al navegador existente.", flush=True)

            if expected_url_substr and not focus_tab_matching(driver, expected_url_substr):
                try:
                    actual_url = driver.current_url
                except Exception:
                    actual_url = "desconocida"
                raise RuntimeError(
                    f"Chrome en puerto {port} no tiene ninguna pestaña activa con "
                    f"'{expected_url_substr}' (URL actual: {actual_url})."
                )
            return driver
        except RuntimeError:
            raise
        except Exception as e:
            print(f"[WARNING] Puerto {port} abierto pero no respondió como Chrome: {e}", flush=True)
            if not allow_launch:
                raise RuntimeError(
                    f"Puerto {port} abierto pero Chrome no respondió al attach: {e}"
                ) from e
            # Puerto colgado -> limpiar antes de relanzar
            cleanup_rpa_chrome(port=port, profile_dir=target_profile)
    elif not allow_launch:
        raise RuntimeError(
            f"No hay navegador Chrome escuchando en el puerto {port}. "
            "Debe ejecutarse primero el nodo de inicio (Inicio_ris)."
        )

    # --- ESTRATEGIA 2: LANZAR NUEVA INSTANCIA CON AUTO-REPARACIÓN ---
    last_error: Optional[Exception] = None
    for attempt in range(1, max_launch_attempts + 1):
        if attempt > 1:
            print(
                f"[AUTO-REPAIR] Reintento {attempt}/{max_launch_attempts}: limpiando procesos/locks de Chrome RPA...",
                flush=True,
            )
            cleanup_rpa_chrome(port=port, profile_dir=target_profile)

        try:
            print(f"[INFO] Iniciando nueva instancia de Chrome con puerto {port}...", flush=True)
            driver = _launch_chrome_with_debug_port(
                port=port,
                profile_dir=target_profile,
                maximize=maximize,
                headless=headless,
                detach=True,
            )
            print("[INFO] Nueva instancia lanzada correctamente.", flush=True)
            return driver
        except Exception as e:
            last_error = e
            print(f"[ERROR] Intento {attempt} al lanzar Chrome en puerto {port} falló: {e}", flush=True)

    raise RuntimeError(
        f"No se pudo iniciar Chrome con depuración en el puerto {port} tras {max_launch_attempts} intentos: {last_error}"
    )
