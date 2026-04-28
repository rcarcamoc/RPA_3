#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script: verifica_inicio
Descripción: Verifica si la pantalla de inicio del PACS está presente mediante comparación de imágenes.
Frecuencia: Cada 10 segundos.
Tiempo máximo: 10 minutos.
Similitud requerida: 70% (0.7)
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

class VerificaInicioAutomation:
    """Automatización: verifica_inicio"""
    
    def __init__(self):
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.image_path = str(Path(__file__).parent / "captura" / "inicio_pacs.png")
        self.error_image_path = str(Path(__file__).parent.parent.parent / "utils" / "error_ris.png")
        self.max_retries = 3  # Límite de ejecuciones de ingresa_user_pacs.py
        self.max_error_restarts = 3 # Límite de reinicios completos por error
        self.interval_seconds = 2   # Más dinámico: cada 2 segundos
        self.confidence_threshold = 0.7  # 70% de similitud
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
            script_name = "verifica_inicio"
            query = "UPDATE registro_acciones SET `update` = NOW(), ultimo_nodo = %s, estado = %s WHERE estado = 'En Proceso'"
            cursor.execute(query, (script_name, status))
            conn.commit()
            conn.close()
            logger.info(f"[DB] Tracking actualizado: {script_name} ({status})")
        except Exception as e:
            logger.warning(f"[DB Error] {e}")

    def focus_carestream_ris(self):
        """Intenta traer 'Carestream RIS' al frente. No es error si falla."""
        try:
            title = "Carestream RIS"
            # Buscamos ventanas que contengan el nombre
            windows = fw.find_windows(title_re=re.compile(f".*{re.escape(title)}.*", re.I))
            
            if windows:
                hwnd = windows[0]
                win = Desktop(backend="win32").window(handle=hwnd)
                # Intentamos set_focus (traer al frente)
                win.set_focus()
                logger.info(f"Ventana '{title}' puesta en primer plano.")
                return True
        except Exception:
            # Si falla (ej: la ventana se está cerrando o no responde), ignoramos
            pass
        return False

    def run(self) -> dict:
        """Busca el patrón de inicio en pantalla con reintentos."""
        logger.info(f"Iniciando verificacion de inicio (ciclo reintento: {WAIT_TIMEOUT}s, max_retries: {self.max_retries})")
        logger.info(f"Imagen de referencia: {self.image_path}")
        
        # DB Tracking: Start
        self.db_update_status('En Proceso')
        
        retries = 0
        
        while retries <= self.max_retries:
            start_time = time.time()
            found = False
            elapsed = 0
            
            logger.info("Iniciando ciclo de búsqueda de 61 segundos...")
            error_restarts = 0
            
            while elapsed < WAIT_TIMEOUT:
                # Intentar poner Carestream RIS en primer plano antes de comparar
                self.focus_carestream_ris()
                
                # 1. Buscar imagen de inicio
                try:
                    location = pyautogui.locateOnScreen(self.image_path, confidence=self.confidence_threshold)
                except Exception:
                    location = None
                    
                if location:
                    logger.info("Pantalla de inicio detectada (similitud >= 70%)")
                    found = True
                    break
                
                # 2. Buscar imagen de error (solo tras el periodo de gracia)
                error_location = None
                if elapsed > self.grace_period:
                    try:
                        error_location = pyautogui.locateOnScreen(self.error_image_path, confidence=self.confidence_threshold + 0.1) # Un poco más estricto
                    except Exception:
                        error_location = None

                if error_location:
                    logger.error(f"¡Pantalla de error detectada! (Similitud >= 70%)")
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
                            continue # Volver al inicio del ciclo while elapsed < WAIT_TIMEOUT
                        except Exception as e:
                            logger.error(f"Error al intentar reiniciar PACS tras detectar error visual: {e}")
                    else:
                        logger.error(f"Se alcanzó el límite de reinicios por error ({self.max_error_restarts}). Abortando.")
                        return {"status": "FAILED", "reason": f"Fallo persistente: error visual recurrente tras {self.max_error_restarts} reinicios.", "error_type": "VISUAL"}
                else:
                    logger.info(f"Escaneando pantalla en busca de inicio o error... ({elapsed}s trascurridos)")
                
                time.sleep(self.interval_seconds)
                elapsed = int(time.time() - start_time)

            if found:
                return {"status": "SUCCESS", "message": "Inicio verificado"}
            
            retries += 1
            if retries > self.max_retries:
                logger.error(f"No se encontro la pantalla tras {self.max_retries} intentos de ejecutar el login.")
                return {"status": "FAILED", "reason": f"Fallo persistente tras {self.max_retries} intentos."}
            
            # Si no se encontró en el ciclo de 61s, ejecutar login y reintentar
            logger.warning(f"No se encontro la pantalla en {WAIT_TIMEOUT}s. Ejecutando ingresa_user_pacs.py (Intento {retries}/{self.max_retries})...")
            
            login_script = Path(__file__).parent / "ingresa_user_pacs.py"
            try:
                # Ejecutamos el script de login y esperamos a que termine
                subprocess.run([sys.executable, str(login_script)], check=False)
                logger.info("Script de login ejecutado. Volviendo a comprobar inicio...")
            except Exception as e:
                logger.error(f"Error al ejecutar el script de login: {e}")

def main():
    """Punto de entrada principal."""
    setup_logging()
    
    automation = VerificaInicioAutomation()
    results = automation.run()
    
    if results["status"] == "SUCCESS":
        print("ok")
        return 0
    else:
        print(f"Error: {results.get('reason', 'Desconocido')}")
        try:
            if results.get("error_type") == "VISUAL":
                 enviar_alerta_todos(f"❌ <b>Error Crítico en el script: verifica_inicio</b>\\nfalla al iniciar ris.\\n<code>{results.get('reason', 'Desconocido')}</code>")
            else:
                 enviar_alerta_todos(f"❌ <b>Error Crítico en el script: verifica_inicio</b>\\nNo se pudo detectar PACS:\\n<code>{results.get('reason', 'Desconocido')}</code>")
        except:
            pass
        return 1

if __name__ == "__main__":
    sys.exit(main())
