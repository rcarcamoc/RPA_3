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
WAIT_TIMEOUT = 61

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
        self.max_wait_seconds = 600  # 10 minutos
        self.interval_seconds = 10   # 10 segundos
        self.confidence_threshold = 0.7  # 70% de similitud
        
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
        logger.info(f"Iniciando verificacion de inicio (ciclo reintento: {WAIT_TIMEOUT}s)")
        logger.info(f"Imagen de referencia: {self.image_path}")
        
        # DB Tracking: Start
        self.db_update_status('En Proceso')
        
        total_start_time = time.time()
        
        while True:
            start_time = time.time()
            found = False
            elapsed = 0
            
            logger.info("Iniciando ciclo de búsqueda de 61 segundos...")
            
            while elapsed < WAIT_TIMEOUT:
                # Intentar poner Carestream RIS en primer plano antes de comparar
                self.focus_carestream_ris()
                
                try:
                    # Intentar localizar la imagen en pantalla con el nivel de confianza solicitado
                    location = pyautogui.locateOnScreen(self.image_path, confidence=self.confidence_threshold)
                    
                    if location:
                        logger.info("Pantalla de inicio detectada (similitud >= 70%)")
                        found = True
                        break
                    else:
                        logger.info(f"Escaneando pantalla... ({elapsed}s trascurridos)")
                        
                except Exception:
                    logger.info(f"Escaneando pantalla... ({elapsed}s trascurridos)")
                
                time.sleep(self.interval_seconds)
                elapsed = int(time.time() - start_time)

            if found:
                return {"status": "SUCCESS", "message": "Inicio verificado"}
            
            # Si no se encontró en el ciclo de 61s, ejecutar login y reintentar
            logger.warning(f"No se encontro la pantalla en {WAIT_TIMEOUT}s. Ejecutando ingresa_user_pacs.py...")
            
            login_script = Path(__file__).parent / "ingresa_user_pacs.py"
            try:
                # Ejecutamos el script de login y esperamos a que termine
                subprocess.run([sys.executable, str(login_script)], check=False)
                logger.info("Script de login ejecutado. Volviendo a comprobar inicio...")
            except Exception as e:
                logger.error(f"Error al ejecutar el script de login: {e}")
            
            # Verificamos si hemos excedido el tiempo total de seguridad (10 minutos)
            if (time.time() - total_start_time) > self.max_wait_seconds:
                logger.error(f"No se encontro la pantalla tras {self.max_wait_seconds/60} minutos de intentos fallidos.")
                return {"status": "FAILED", "reason": "Timeout total: Fallo persistente tras multiples intentos"}

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
            enviar_alerta_todos(f"❌ <b>Error Crítico en el script: verifica_inicio</b>\\nNo se pudo detectar PACS:\\n<code>{results.get('reason', 'Desconocido')}</code>")
        except:
            pass
        return 1

if __name__ == "__main__":
    sys.exit(main())
