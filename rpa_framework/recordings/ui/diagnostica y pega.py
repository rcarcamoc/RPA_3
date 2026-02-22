#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script autogenerado: test1
Generado: 2026-01-11 23:06:05
Total de acciones: 6
"""

import sys
import time
import logging
from pathlib import Path
from datetime import datetime

# Agregar raíz del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pywinauto import Application, findwindows
from core.executor import ActionExecutor
from core.action import Action, ActionType
from utils.logging_setup import setup_logging
import re
import pyautogui
import cv2
import numpy as np
import random
import os
import ctypes
import win32clipboard

try:
    from utils.visual_feedback import VisualFeedback
    vf = VisualFeedback()
except ImportError:
    logger.warning("⚠️ VisualFeedback no disponible")
    vf = None

try:
    from utils.telegram_manager import enviar_alerta_todos
except ImportError:
    def enviar_alerta_todos(msg): pass


# Configuración de MySQL (opcional)
try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

logger = logging.getLogger(__name__)



# Configuración Global
VALIDACION_PEGADO = True

def humanized_click(x, y, clicks=1, interval=0.1):
    """
    Realiza un movimiento de mouse humanizado hacia (x, y) y hace click.
    """
    duration = random.uniform(0.5, 1.0)
    
    # Visual Feedback del movimiento si está disponible
    if vf:
        # Simulamos que "miramos" hacia donde vamos a hacer click
        pass 

    pyautogui.moveTo(x, y, duration=duration, tween=pyautogui.easeInOutQuad)
    
    # Destacar clic en ROJO justo antes de hacerlo
    if vf:
        vf.highlight_click(x, y, color="#FF0000", duration=0.5)
    
    time.sleep(random.uniform(0.1, 0.3))
    pyautogui.click(clicks=clicks, interval=interval)


def buscar_bloque_toolbar(toolbar_template_path, confidence_threshold=0.70, log_dir=None):
    """
    Busca la BARRA COMPLETA de iconos en la pantalla usando MULTI-SCALE MATCHING.
    """
    if not os.path.exists(toolbar_template_path):
        logger.error(f"❌ Error: No se encuentra {toolbar_template_path}")
        return None
    
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
    
    # Leer la template (barra completa)
    template = cv2.imread(toolbar_template_path)
    if template is None:
        logger.error(f"❌ Error: No se pudo leer {toolbar_template_path}")
        return None
    
    original_h, original_w = template.shape[:2]
    
    # Capturar pantalla actual
    try:
        current_screen = pyautogui.screenshot()
        screen_np = np.array(current_screen)
        screen_cv = cv2.cvtColor(screen_np, cv2.COLOR_RGB2BGR)
        
        if log_dir:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            screenshot_path = os.path.join(log_dir, f"screenshot_{timestamp}.png")
            cv2.imwrite(screenshot_path, screen_cv)
        
    except Exception as e:
        logger.error(f"❌ Error capturando pantalla: {e}")
        return None
    
    # Búsqueda EXACTA (1:1) en COLOR (BGR)
    try:
        result = cv2.matchTemplate(screen_cv, template, cv2.TM_CCOEFF_NORMED)
    except Exception as e:
        logger.error(f"❌ Error crítico en matchTemplate: {e}")
        return None
        
    template_w = original_w
    template_h = original_h

    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(result)
    x, y = max_loc
    
    center_x = x + original_w / 2
    center_y = y + original_h / 2

    match_found = False
    
    # 1. Confianza Alta (Directa)
    if max_val >= confidence_threshold:
        match_found = True
        if vf:
            vf.highlight_region(x, y, original_w, original_h, color="#00FF00", duration=1.0)
        
    # 2. Confianza "Aceptable"
    elif max_val >= 0.20:
        logger.warning(f"⚠️ Confianza baja ({max_val*100:.2f}%) pero ACEPTADA por heurística.")
        match_found = True
        if vf:
            vf.highlight_region(x, y, original_w, original_h, color="#FFEB3B", duration=1.0)

    if match_found:
        if log_dir:
            viz_path = os.path.join(log_dir, f"found_toolbar_{time.strftime('%Y%m%d_%H%M%S')}.png")
            screen_viz = screen_cv.copy()
            color_rect = (0, 255, 0) if max_val >= confidence_threshold else (0, 255, 255)
            cv2.rectangle(screen_viz, (x, y), (x + template_w, y + template_h), color_rect, 3)
            cv2.imwrite(viz_path, screen_viz)

        return (x, y, template_w, template_h, center_x, center_y)

    else:
        if log_dir:
            viz_path = os.path.join(log_dir, f"failed_best_match_{time.strftime('%Y%m%d_%H%M%S')}.png")
            screen_viz = screen_cv.copy()
            cv2.rectangle(screen_viz, (x, y), (x + template_w, y + template_h), (0, 0, 255), 2)
            cv2.imwrite(viz_path, screen_viz)
            
        return None


def realizar_accion_en_bloque(bloque_info, accion="click_centro", offset_y=100):
    x, y, width, height, center_x, center_y = bloque_info
    
    if accion == "click_centro":
        # Ajuste solicitado: 80px más abajo del centro detectado
        target_y = center_y + 80
        logger.info(f"   → Click en centro de barra (+80px): ({center_x:.0f}, {target_y:.0f})")
        humanized_click(center_x, target_y)
        
    elif accion == "click_guardar":
        # Coordenadas relativas específicas: 32, 36 desde la esquina superior izquierda
        target_x = x + 32
        target_y = y + 36
        logger.info(f"   → Click en botón Guardar (offset 32,36): ({target_x:.0f}, {target_y:.0f})")
        
        # Destacar zona en rojo antes de clicar
        if vf:
            vf.highlight_click(target_x, target_y, color="#FF0000", duration=0.8)
            
        humanized_click(target_x, target_y)


def automatizar_buscar_toolbar(toolbar_image_path, accion="click_centro", offset=100):
    base_path = r"c:\Desarrollo\RPA_3"
    full_toolbar_path = os.path.join(base_path, toolbar_image_path)
    log_dir = os.path.join(base_path, "rpa_framework", "log", "debug_screenshots")
    
    logger.info(f"Buscando: {toolbar_image_path}")
    
    while True:
        bloque_info = buscar_bloque_toolbar(
            full_toolbar_path,
            confidence_threshold=0.70,
            log_dir=log_dir
        )
        
        if bloque_info:
            break
            
        logger.warning("❌ No se pudo encontrar la barra")
        
        # Mostrar alerta al usuario pidiendo acción
        msg = "No se pudo encontrar la barra de Word.\n\nPor favor:\n1. Asegúrate que Word esté abierto y visible.\n2. Ponlo en primer plano."
        title = "RPA - Word No Encontrado"
        
        enviar_alerta_todos(f"🚨 <b>ASISTENCIA REQUERIDA</b> 🚨\n{msg}")
        
        button_pressed = ctypes.windll.user32.MessageBoxW(0, msg, title, 0x05 | 0x30 | 0x40000)
        
        if button_pressed == 4: # Retry
            logger.info("🔄 Usuario indicó reintentar. Buscando de nuevo...")
            time.sleep(1)
            continue
        else: # Cancel
            logger.info("🛑 Usuario canceló la operación.")
            return False
    
    realizar_accion_en_bloque(bloque_info, accion=accion, offset_y=offset)
    return True



def set_clipboard_rtf(rtf_text):
    """Coloca contenido RTF en el portapapeles."""
    try:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        # Registrar formato RTF si es necesario o usar standard
        cf_rtf = win32clipboard.RegisterClipboardFormat("Rich Text Format")
        # RTF debe ser bytes
        rtf_bytes = rtf_text.encode('cp1252', errors='replace')
        win32clipboard.SetClipboardData(cf_rtf, rtf_bytes)
        logger.info("Contenido RTF copiado al portapapeles")
    except Exception as e:
        logger.error(f"Error copiando RTF: {e}")
    finally:
        try:
            win32clipboard.CloseClipboard()
        except:
            pass


class Test1Automation:
    """Automatización generada: test1"""
    
    def __init__(self):
        self.app = None
        self.executor = None
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
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
            script_name = "test1"
            query = "UPDATE registro_acciones SET `update` = NOW(), ultimo_nodo = %s, estado = %s WHERE estado = 'En Proceso'"
            cursor.execute(query, (script_name, status))
            conn.commit()
            conn.close()
            logger.info(f"[DB] Tracking actualizado: {script_name} ({status})")
        except Exception as e:
            logger.warning(f"[DB Error] {e}")
    
    def fetch_diagnosis(self):
        """Consulta el diagnóstico desde la base de datos."""
        if not HAS_MYSQL:
            logger.error("MySQL no disponible.")
            return None
        try:
            conn = mysql.connector.connect(
                host='localhost',
                user='root',
                password='',
                database='ris'
            )
            cursor = conn.cursor()
            query = "SELECT diagnostico AS diagnostico_primera_linea FROM ris.registro_acciones WHERE estado = 'En Proceso';"
            cursor.execute(query)
            result = cursor.fetchone()
            conn.close()
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Error consultando DB: {e}")
            return None

    def type_formatted(self, text):
        """Procesa y escribe el texto usando RTF para asegurar formato sin depender del estado del editor."""
        if not text:
            logger.warning("No hay texto para procesar")
            return
            
        # 1. Omitir la primera línea
        lines = text.splitlines()
        if len(lines) > 1:
            text = "\n".join(lines[1:])
            logger.info("1ra línea omitida")
        else:
            logger.warning("Texto demasiado corto")
            return

        # 2. Construir RTF
        # Header básico RTF - Calibri
        rtf_header = r"{\rtf1\ansi\ansicpg1252\deff0\nouicompat\deflang1034{\fonttbl{\f0\fnil\fcharset0 Calibri;}}"
        # Calibri 10pt (\fs20), Interlineado Sencillo (\sl0 = auto/single, \sa0 = sin espacio posterior)
        rtf_start = r"\viewkind4\uc1 \pard\sa0\sl0\slmult1\f0\fs20 " 
        rtf_body = ""
        
        # Dividir por palabras clave manteniendo separadores
        parts = re.split(r'(Hallazgos: |Impresión: )', text)
        
        for part in parts:
            if not part:
                continue
            
            # Escapar caracteres especiales RTF en el contenido
            safe_part = part.replace('\\', '\\\\').replace('{', r'\{').replace('}', r'\}')
            
            if "Hallazgos: " in part:
                 # Negrita
                 rtf_body += r"\b " + safe_part + r"\b0 "
            elif "Impresión: " in part:
                 # Enter antes + Negrita + Enter después (simulando lógica original)
                 # Lógica original: Enter antes, Escribe H/I, Enter despues.
                 # RTF: \par inicia nuevo parrafo.
                 rtf_body += r"\par \b " + safe_part + r"\b0 \par "
            else:
                 # Texto normal con saltos de línea convertidos a \par
                 content = safe_part.replace('\n', r'\par ')
                 rtf_body += content

        rtf_final = rtf_header + rtf_start + rtf_body + r"}"
        
        # 3. Poner en portapapeles y pegar
        set_clipboard_rtf(rtf_final)
        
        # Espera crítica para dar tiempo al SO y la app de reconocer el portapapeles
        time.sleep(1.0)
        
        # Ejecutar CTRL+V (sin 'clipboard_content' para no sobrescribir nuestro RTF)
        self.executor.execute(Action(type=ActionType.KEY_COMBINATION, combination="CTRL+V", timestamp=datetime.now()))

    
    def setup(self) -> bool:
        """Conecta a la aplicación objetivo."""
        logger.info("Configurando conexión a la aplicación...")
        
        try:
            # Intentar conectar a ventana activa o Desktop
            try:
                self.app = Application(backend='uia').connect(path="explorer.exe")
            except:
                logger.warning("Usando modo Desktop")
                self.app = Application(backend='uia')
            
            self.executor = ActionExecutor(self.app, {})
            logger.info("✅ Conexión establecida")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error en setup: {e}")
            return False
    
    def run(self) -> dict:
        """Ejecuta todas las acciones grabadas."""
        if not self.setup():
            return {"status": "FAILED", "reason": "Setup failed"}
        
        results = {
            "session_id": self.session_id,
            "status": "RUNNING",
            "total_actions": 3,
            "completed": 0,
            "failed": 0,
            "errors": [],
            "start_time": datetime.now().isoformat(),
        }
        
        logger.info(f"🚀 Iniciando ejecución: {results['total_actions']} acciones")
        
        # DB Tracking: Start
        self.db_update_status('En Proceso')
        
        try:
            # Acción 1: Búsqueda Visual y Click
            try:
                # Reemplazo de lógica de clicks iniciales con búsqueda visual
                toolbar_img = r"rpa_framework\utils\word.png"
                if automatizar_buscar_toolbar(toolbar_img, accion="click_centro"):
                    results["completed"] += 1
                    logger.info(f"[1/3] ✅ Búsqueda visual y click exitoso")
                    time.sleep(1.0) # Espera para asegurar foco tras clic
                else:
                    raise Exception("No se encontró la barra de Word tras reintentos")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 1, "type": "visual_search", "reason": str(e)})
                logger.error(f"[1/3] ❌ visual_search: {e}")
                # Si falla la búsqueda, abortamos
                raise e

            # Acción 2: PROCESAMIENTO DE DIAGNÓSTICO
            try:
                diag = self.fetch_diagnosis()
                if diag:
                    # Loop de validación con reintentos
                    validacion_exitosa = False
                    while not validacion_exitosa:
                        self.type_formatted(diag)
                        results["completed"] += 1
                        logger.info(f"[2/3] ✅ Diagnóstico procesado e ingresado")
                        
                        # VALIDACIÓN DE PEGADO
                        if VALIDACION_PEGADO:
                            # Preguntar al usuario con 3 opciones: Sí / No / Reintentar
                            msg = "El texto ha sido pegado.\n\n¿Es correcto el formato y contenido?\n\n• SÍ: Guardar y continuar\n• NO: Cancelar sin guardar\n• CANCELAR: Reintentar pegado"
                            title = "Validación de Pegado"
                            
                            enviar_alerta_todos(f"🚨 <b>ASISTENCIA REQUERIDA</b> 🚨\n{msg}")
                            
                            # Flags: MB_YESNOCANCEL (3) | MB_ICONQUESTION (20) | MB_TOPMOST (40000) | MB_SETFOREGROUND (10000)
                            layout_confirm = ctypes.windll.user32.MessageBoxW(0, msg, title, 0x03 | 0x20 | 0x40000 | 0x10000)
                            
                            if layout_confirm == 6: # IDYES
                                logger.info("✅ Usuario validó el pegado. Procediendo a GUARDAR.")
                                
                                # Reemplazo de búsqueda visual por atajo de teclado CTRL+1
                                try:
                                    self.executor.execute(Action(type=ActionType.KEY_COMBINATION, combination="CTRL+1", timestamp=datetime.now()))
                                    logger.info("✅ Comando de guardado (CTRL+1) enviado exitosamente.")
                                except Exception as e_save:
                                    logger.error(f"❌ Error al enviar CTRL+1: {e_save}")
                                validacion_exitosa = True
                                
                            elif layout_confirm == 7: # IDNO
                                logger.warning("🛑 Usuario RECHAZÓ el pegado. No se guardará.")
                                validacion_exitosa = True
                                
                            elif layout_confirm == 2: # IDCANCEL (Reintentar)
                                logger.info("🔄 Usuario solicitó REINTENTAR el pegado.")
                                # Seleccionar todo y borrar antes de reintentar
                                try:
                                    self.executor.execute(Action(type=ActionType.KEY_COMBINATION, combination="CTRL+A", timestamp=datetime.now()))
                                    time.sleep(0.2)
                                    self.executor.execute(Action(type=ActionType.KEY_PRESS, key_code="DELETE", timestamp=datetime.now()))
                                    time.sleep(0.5)
                                    logger.info("📝 Contenido borrado. Reintentando pegado...")
                                except Exception as e_clear:
                                    logger.error(f"❌ Error al limpiar contenido: {e_clear}")
                                # El loop continuará y volverá a pegar
                        else:
                            validacion_exitosa = True

                else:
                    logger.warning("No se obtuvo diagnóstico de la DB")
                    results["failed"] += 1
                    results["errors"].append({"action_idx": 2, "type": "db_process", "reason": "No diagnosis data"})
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 2, "type": "db_process", "reason": str(e)})
                logger.error(f"[2/3] ❌ db_process: {e}")

            # Acción 6: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'position': {'x': 433, 'y': 338}},
                    position={'x': 433, 'y': 338},
                    timestamp=datetime.fromisoformat("2026-01-11T23:06:00.058182")
                )
                self.executor.execute(action)
                results["completed"] += 1
                logger.info(f"[3/3] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 3, "type": "click", "reason": str(e)})
                logger.error(f"[3/3] ❌ click: {e}")

            
            results["status"] = "SUCCESS" if results["failed"] == 0 else "PARTIAL"
            
        except Exception as e:
            logger.error(f"❌ Error crítico: {e}")
            results["status"] = "FAILED"
            results["errors"].append({"reason": str(e)})
            self.db_update_status('error')
        
        results["end_time"] = datetime.now().isoformat()
        
        logger.info(f"📊 RESUMEN: {results['completed']} OK, {results['failed']} FAILED")
        logger.info(f"Status: {results['status']}")
        
        # DB Tracking: Final
        if results["status"] == "SUCCESS":
            self.db_update_status('En Proceso')
        
        return results


def main():
    """Punto de entrada principal."""
    setup_logging()
    
    automation = Test1Automation()
    results = automation.run()
    
    print("\n" + "="*50)
    print(f"Resultado: {results['status']}")
    print(f"Completadas: {results['completed']}/{results['total_actions']}")
    print(f"Fallidas: {results['failed']}")
    print("="*50)
    
    return 0 if results["status"] == "SUCCESS" else 1


if __name__ == "__main__":
    sys.exit(main())
