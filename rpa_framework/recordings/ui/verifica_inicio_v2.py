#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script: verifica_inicio_v2 (Prueba Dinámica)
Descripción: Verifica si la pantalla de inicio del PACS está presente mediante
comprobación del estado del proceso (mp.exe) y ventana usando pywinauto, en lugar de imágenes.
Frecuencia dinámica con periodo de gracia.
Tiempo máximo: 90 segundos.
"""

import sys
import time
import logging
from pathlib import Path
from datetime import datetime
import pyautogui
from pywinauto import Desktop
import pywinauto.findwindows as fw
import subprocess
import re
import psutil

# Variable de espera definida al inicio
WAIT_TIMEOUT = 90

# Agregar raíz del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.logging_setup import setup_logging
from utils.telegram_manager import enviar_alerta_todos

# Configuración de MySQL (opcional, siguiendo el estándar del proyecto)
try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

logger = logging.getLogger(__name__)

class VerificaInicioAutomationV2:
    """Automatización: verifica_inicio (Versión 2 Dinámica)"""
    
    def __init__(self):
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.error_image_path = str(Path(__file__).parent.parent.parent / "utils" / "error_ris.png")
        self.max_retries = 3  # Límite de ejecuciones de ingresa_user_pacs.py
        self.max_error_restarts = 3 # Límite de reinicios completos por error
        self.interval_seconds = 2   # Más dinámico: cada 2 segundos
        self.confidence_threshold = 0.8  # 80% de similitud para errores (evitar falsos positivos)
        self.grace_period = 15      # Segundos de gracia antes de buscar errores
        
    def db_update_status(self, status='En Proceso'):
        """Actualiza el estado en la BD"""
        if not HAS_MYSQL:
            return
        try:
            conn = mysql.connector.connect(
                host='localhost',
                user='root',
                password='',
                database='ris'
            )
            cursor = conn.cursor()
            script_name = "verifica_inicio" # Mantiene el mismo nombre para la BD
            query = "UPDATE registro_acciones SET `update` = NOW(), ultimo_nodo = %s, estado = %s WHERE estado = 'En Proceso'"
            cursor.execute(query, (script_name, status))
            conn.commit()
            conn.close()
            logger.info(f"[DB] Tracking actualizado: {script_name} ({status})")
        except Exception as e:
            logger.warning(f"[DB Error] {e}")

    def focus_carestream_ris(self):
        """Intenta traer el RIS al frente (Carestream o Philips). No es error si falla."""
        try:
            # Lista de posibles títulos
            titles = ["Carestream RIS", "Workflow Information Management"]
            for title in titles:
                windows = fw.find_windows(title_re=re.compile(f".*{re.escape(title)}.*", re.I))
                
                if windows:
                    hwnd = windows[0]
                    win = Desktop(backend="win32").window(handle=hwnd)
                    win.set_focus()
                    return True
        except Exception:
            pass
        return False

    def run(self) -> dict:
        """Busca el programa en ejecución comprobando el estado de su ventana principal."""
        logger.info(f"Iniciando verificacion de inicio (V2 Dinámica) (Timeout: {WAIT_TIMEOUT}s)")
        
        # DB Tracking: Start
        self.db_update_status('En Proceso')
        
        retries = 0
        
        while retries <= self.max_retries:
            start_time = time.time()
            found = False
            elapsed = 0
            
            logger.info(f"Iniciando ciclo de búsqueda de {WAIT_TIMEOUT} segundos observando 'Vue RIS.exe' / 'Carestream RIS.exe'...")
            error_restarts = 0
            
            while elapsed < WAIT_TIMEOUT:
                # Intentar poner Carestream RIS en primer plano antes de comparar
                self.focus_carestream_ris()
                
                # 1. Comprobar si el proceso de Carestream RIS está corriendo y su ventana está lista
                pacs_running = False
                for p in psutil.process_iter(['name']):
                    try:
                        # Buscamos Carestream RIS.exe o el nuevo Vue RIS.exe (Philips)
                        name_lower = p.info['name'].lower()
                        if 'carestream ris.exe' in name_lower or 'vue ris.exe' in name_lower:
                            pacs_running = True
                            break
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

                if pacs_running:
                    # Encontrar ventana de Carestream RIS o Workflow Information Management
                    try:
                        # Regex combinada para ambos posibles nombres de ventana
                        windows = fw.find_windows(title_re=re.compile(".*(Carestream RIS|Workflow Information Management).*", re.I))
                        if windows:
                            hwnd = windows[0]
                            # Usa uia o win32
                            win = Desktop(backend="uia").window(handle=hwnd)
                            
                            is_visible = win.is_visible()
                            try:
                                is_enabled = win.is_enabled()
                            except:
                                is_enabled = False
                                
                            logger.info(f"RIS Client detectado. Ventana '{win.window_text()}' -> Visible: {is_visible}, Habilitada: {is_enabled}")
                            
                            if is_visible and is_enabled:
                                logger.info("¡Ventana de inicio de RIS Client detectada como lista y habilitada!")
                                # Asegurar que la dejamos en primer plano
                                try:
                                    win.set_focus()
                                except Exception as e:
                                    logger.debug(f"No se pudo poner en primer plano: {e}")
                                found = True
                                break
                    except Exception as e:
                        logger.debug(f"Error consultando ventana: {e}")
                else:
                    logger.info("El proceso RIS (Carestream/Vue RIS.exe) aún no está en ejecución...")
                
                # 2. Buscar imagen de error (solo tras el periodo de gracia y si no hemos encontrado la ventana aún)
                error_location = None
                if elapsed > self.grace_period and not found:
                    try:
                        error_location = pyautogui.locateOnScreen(self.error_image_path, confidence=self.confidence_threshold)
                    except Exception:
                        error_location = None

                if error_location:
                    logger.error(f"¡Pantalla de error detectada! (Similitud >= {self.confidence_threshold * 100}%)")
                    if error_restarts < self.max_error_restarts:
                        error_restarts += 1
                        logger.warning(f"Reiniciando PACS por error visual (Intento de reinicio {error_restarts}/{self.max_error_restarts})...")
                        
                        clean_script = Path(__file__).parent.parent.parent.parent / "clean_ris_folders.py"
                        abre_pacs_script = Path(__file__).parent / "Abre_pacs.py"
                        login_script = Path(__file__).parent / "ingresa_user_pacs.py"
                        
                        try:
                            logger.info("Ejecutando clean_ris_folders.py...")
                            subprocess.run([sys.executable, str(clean_script)], check=False)
                            
                            logger.info("Ejecutando Abre_pacs.py...")
                            subprocess.run([sys.executable, str(abre_pacs_script)], check=False)
                            
                            logger.info("Ejecutando ingresa_user_pacs.py...")
                            subprocess.run([sys.executable, str(login_script)], check=False)
                            
                            logger.info("Reinicio completado. Reiniciando ciclo de búsqueda...")
                            start_time = time.time()
                            elapsed = 0
                            continue # Volver al inicio del ciclo while
                        except Exception as e:
                            logger.error(f"Error al intentar reiniciar PACS tras detectar error visual: {e}")
                    else:
                        logger.error(f"Se alcanzó el límite de reinicios por error ({self.max_error_restarts}). Abortando.")
                        return {"status": "FAILED", "reason": f"Fallo persistente: error visual recurrente tras {self.max_error_restarts} reinicios.", "error_type": "VISUAL"}
                elif not found:
                    pass # Solo logueamos si no encontró nada
                
                if not found:
                    time.sleep(self.interval_seconds)
                    elapsed = int(time.time() - start_time)

            if found:
                return {"status": "SUCCESS", "message": "Inicio verificado (V2)"}
            
            retries += 1
            if retries > self.max_retries:
                logger.error(f"No se encontro la ventana lista tras {self.max_retries} reintentos.")
                return {"status": "FAILED", "reason": f"Fallo persistente tras {self.max_retries} intentos."}
            
            # Si no se encontró en el ciclo, intentar re-login
            logger.warning(f"No se detectó login activo en {WAIT_TIMEOUT}s. Ejecutando ingresa_user_pacs.py (Intento {retries}/{self.max_retries})...")
            
            login_script = Path(__file__).parent / "ingresa_user_pacs.py"
            try:
                subprocess.run([sys.executable, str(login_script)], check=False)
                logger.info("Script de login ejecutado. Volviendo a comprobar inicio...")
            except Exception as e:
                logger.error(f"Error al ejecutar el script de login: {e}")

def main():
    """Punto de entrada principal."""
    setup_logging()
    
    automation = VerificaInicioAutomationV2()
    results = automation.run()
    
    if results["status"] == "SUCCESS":
        print("ok")
        return 0
    else:
        print(f"Error: {results.get('reason', 'Desconocido')}")
        try:
            msg = f"❌ <b>Error Crítico</b>\nDespués de {automation.max_retries} intentos, no se pudo iniciar el RIS de Integramédica.\n<code>{results.get('reason', 'Fallo persistente')}</code>"
            enviar_alerta_todos(msg)
        except Exception as e:
            logger.error(f"Error al enviar alerta Telegram: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
