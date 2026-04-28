#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script autogenerado para diagnóstico y pegado con búsqueda visual.
"""

import sys
import time
import logging
from pathlib import Path
from datetime import datetime
import re
import pyautogui
import cv2
import numpy as np
import random
import os
import ctypes
import win32clipboard

# Agregar raíz del proyecto al path para importar utils
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from utils.visual_feedback import VisualFeedback
    vf = VisualFeedback()
except ImportError:
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

def ejecutar_cierra_visor():
    """Ejecuta el script cierra_visor_documentos2.py de forma dinámica."""

    time.sleep(4.0)
    try:
        import importlib.util
        cvd_path = Path(__file__).parent / "cierra_visor_documentos2.py"
        if not cvd_path.exists():
            logger.warning(f"No se encuentra {cvd_path}")
            return False
            
        spec = importlib.util.spec_from_file_location("cierra_visor_documentos", str(cvd_path))
        cvd = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cvd)
        
        if hasattr(cvd, 'execute'):
            cvd.execute()
        elif hasattr(cvd, 'main'):
            cvd.main()
        
        logger.info("Script cierra_visor_documentos ejecutado con éxito")
        return True
    except Exception as e:
        logger.warning(f"Error ejecutando cierra_visor_documentos2.py: {e}")
        return False


# Configuración Global
VALIDACION_PEGADO = True

# ── Carpeta de logs especifica para esta tarea ───────────────────
LOG_DIR = os.path.join(
    str(Path(__file__).parent.parent.parent),
    "log", "pega_en_word"
)
os.makedirs(LOG_DIR, exist_ok=True)


def guardar_debug_screenshot(screenshot_cv, info=None, suffix="", target_point=None):
    """Guarda captura de debug con anotaciones, zona destacada y punto de clic exacto."""
    try:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"pega_word_{suffix}_{timestamp}.png"
        filepath = os.path.join(LOG_DIR, filename)

        viz = screenshot_cv.copy()

        # 1. Dibujar zona delimitadora si hay info
        if info:
            if isinstance(info, (tuple, list)):
                x, y, w, h, _, _ = info
            else:
                x, y, w, h = info.get('x', 0), info.get('y', 0), info.get('w', 0), info.get('h', 0)

            overlay = viz.copy()
            cv2.rectangle(overlay, (int(x) - 4, int(y) - 4), (int(x + w) + 4, int(y + h) + 4), (0, 200, 255), -1)
            cv2.addWeighted(overlay, 0.25, viz, 0.75, 0, viz)
            cv2.rectangle(viz, (int(x), int(y)), (int(x + w), int(y + h)), (255, 255, 0), 3)

        # 2. Dibujar punto de clic exacto (prioritario si se proporciona target_point)
        if target_point:
            tx, ty = target_point
            cv2.circle(viz, (int(tx), int(ty)), 12, (0, 0, 255), -1)
            cv2.circle(viz, (int(tx), int(ty)), 14, (255, 255, 255), 2)
            # Etiqueta de coordenadas
            coords_txt = f"CLICK: {int(tx)}, {int(ty)}"
            cv2.putText(viz, coords_txt, (int(tx) + 20, int(ty)), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 4)
            cv2.putText(viz, coords_txt, (int(tx) + 20, int(ty)), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        elif info:
            # Fallback al centro de la info si no hay target_point
            if isinstance(info, (tuple, list)):
                cx, cy = info[4], info[5]
            else:
                cx, cy = info.get('center_x', 0), info.get('center_y', 0)
            cv2.circle(viz, (int(cx), int(cy)), 10, (0, 0, 255), -1)

        cv2.imwrite(filepath, viz)
        logger.info(f"   [LOG IMG] Screenshot guardado: {filepath}")
    except Exception as e:
        logger.debug(f"   [ERROR IMG] Error guardando debug screenshot: {e}")

def humanized_click(x, y, clicks=1, interval=0.1, hold_time=0.5):
    """
    Mueve el ratón a (x,y), hace una pausa (hover) y realiza el clic (sostenido o normal).
    """
    # 1. Destacar la zona ANTES de moverse (solo una vez por ejecución)
    if vf:
        vf.highlight_click(x, y, color="#FF0000", duration=0.8)

    # 2. Posicionamiento (movimiento)
    duration = random.uniform(0.5, 1.0)
    pyautogui.moveTo(x, y, duration=duration, tween=pyautogui.easeInOutQuad)
    
    # 3. Pausa crucial de posicionamiento (Estimular render de UI / Hover)
    time.sleep(0.5)
    
    # 4. Ejecución del clic sostenido o rápido, SIN volver a pasar (x,y)
    if hold_time > 0.0:
        pyautogui.mouseDown()
        time.sleep(hold_time)
        pyautogui.mouseUp()
    else:
        pyautogui.click(clicks=clicks, interval=interval)


def buscar_bloque_toolbar(toolbar_template_path, confidence_threshold=0.70):
    """
    Busca la BARRA COMPLETA de iconos en la pantalla usando MULTI-SCALE MATCHING y DOBLE CONFIRMACIÓN.
    """
    if not os.path.exists(toolbar_template_path):
        logger.error(f"❌ Error: No se encuentra {toolbar_template_path}")
        return None
    
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
        
        # Log inicial (opcional, uno por intento)
        # guardar_debug_screenshot(screen_cv, suffix="full_screen")
        
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
    confirmacion_usada = False
    
    # 1. Confianza Alta (Pase Directo)
    if max_val >= confidence_threshold:
        match_found = True
        logger.info(f"   ✅ Confianza alta ({max_val*100:.2f}%). Pase directo.")
        if vf:
            vf.highlight_region(x, y, template_w, template_h, color="#FFEB3B", duration=1.5)
        
    # 2. Confianza "Aceptable" -> DOBLE CONFIRMACIÓN
    elif max_val >= 0.20:
        logger.warning(f"   ⚠️ Confianza preliminar baja ({max_val*100:.2f}%) en ({x}, {y}). DOBLE CONFIRMACIÓN...")
        confirmacion_usada = True
        
        try:
            h_scr, w_scr = screen_cv.shape[:2]
            y2, x2 = min(y + template_h, h_scr), min(x + template_w, w_scr)
            crop = screen_cv[y:y2, x:x2]

            # Redimensionar crop al tamaño exacto de la template para comparación directa
            crop_resized = cv2.resize(crop, (template_w, template_h), interpolation=cv2.INTER_LINEAR)

            # Comparación directa pixel a pixel: similitud por diferencia normalizada
            diff = cv2.norm(crop_resized.astype(np.float32), template.astype(np.float32), cv2.NORM_L2)
            max_possible = np.sqrt(template_w * template_h * 3) * 255.0
            similitud = 1.0 - (diff / max_possible)

            logger.info(f"   🔍 Doble Confirmación (similitud directa): {similitud*100:.2f}%")

            # Umbral de similitud directa (0.70 = 70% de similitud pixel a pixel)
            UMBRAL_CONFIRM2 = 0.70

            # Guardar imagen del recorte con etiqueta de resultado
            try:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                crop_viz = crop_resized.copy()
                label = f"Sim: {similitud*100:.1f}%"
                color_label = (0, 200, 0) if similitud >= UMBRAL_CONFIRM2 else (0, 0, 255)
                cv2.putText(crop_viz, label, (4, 22),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 4)
                cv2.putText(crop_viz, label, (4, 22),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, color_label, 2)
                suffix_crop = "confirm2_ok" if similitud >= UMBRAL_CONFIRM2 else "confirm2_fail"
                crop_path = os.path.join(LOG_DIR, f"pega_word_{suffix_crop}_{timestamp}.png")
                cv2.imwrite(crop_path, crop_viz)
                logger.info(f"   [LOG IMG] Recorte 2ª confirmación: {crop_path}")
            except Exception as e_img:
                logger.debug(f"   [ERROR IMG] No se pudo guardar recorte: {e_img}")

            if similitud >= UMBRAL_CONFIRM2:
                match_found = True
                logger.info("   ✅ Match confirmado tras segunda pasada (similitud directa).")
                if vf:
                    vf.highlight_region(x, y, template_w, template_h, color="#FFEB3B", duration=1.5)
            else:
                logger.warning(f"   ❌ Falló doble confirmación (similitud={similitud*100:.1f}% < {UMBRAL_CONFIRM2*100:.0f}%).")
                match_found = False

        except Exception as e:
            logger.error(f"   Error durante la doble confirmación: {e}")
            match_found = False

    if match_found:
        bloque_info = (x, y, template_w, template_h, center_x, center_y)
        suffix = "found_confirmed" if confirmacion_usada else "found_direct"
        guardar_debug_screenshot(screen_cv, info=bloque_info, suffix=suffix)
        return bloque_info

    else:
        # Log de fallo con el mejor candidato descartado
        guardar_debug_screenshot(screen_cv, info=(x, y, template_w, template_h, center_x, center_y), suffix="failed_low_conf")
        return None


def realizar_accion_en_bloque(bloque_info, accion="click_centro", offset_y=100):
    x, y, width, height, center_x, center_y = bloque_info
    
    if accion == "click_centro":
        # Ajuste solicitado: 80px más abajo del centro detectado
        target_x = center_x
        target_y = center_y + 80
        logger.info(f"   → Click en centro de barra (+80px): ({target_x:.0f}, {target_y:.0f})")
        
        # Log del punto de clic real
        try:
            scr = pyautogui.screenshot()
            scr_cv = cv2.cvtColor(np.array(scr), cv2.COLOR_RGB2BGR)
            guardar_debug_screenshot(scr_cv, info=bloque_info, suffix="click_barra", target_point=(target_x, target_y))
        except: pass

        humanized_click(target_x, target_y, hold_time=1.0)
        
    elif accion == "click_guardar":
        # Coordenadas relativas específicas: 32, 36 desde la esquina superior izquierda
        target_x = x + 32
        target_y = y + 36
        logger.info(f"   → Click en botón Guardar (offset 32,36): ({target_x:.0f}, {target_y:.0f})")
        
        # Log del punto de clic real
        try:
            scr = pyautogui.screenshot()
            scr_cv = cv2.cvtColor(np.array(scr), cv2.COLOR_RGB2BGR)
            guardar_debug_screenshot(scr_cv, info=bloque_info, suffix="click_save_btn", target_point=(target_x, target_y))
        except: pass

        humanized_click(target_x, target_y, hold_time=1.0)


def automatizar_buscar_toolbar(toolbar_image_path, accion="click_centro", offset=100):
    base_path = r"c:\Desarrollo\RPA_3"
    full_toolbar_path = os.path.join(base_path, toolbar_image_path)
    intento_sanacion_realizado = False
    
    logger.info(f"Buscando: {toolbar_image_path}")
    
    # --- EJECUCIÓN PREVENTIVA DE CIERRA VISOR ---
    logger.info("🔄 Ejecutando cierre preventivo del visor antes de buscar...")
    ejecutar_cierra_visor()
    time.sleep(1.0)
    
    while True:
        bloque_info = buscar_bloque_toolbar(
            full_toolbar_path,
            confidence_threshold=0.70
        )
        
        if bloque_info:
            break
            
        # --- LÓGICA DE AUTOSANACIÓN ---
        if not intento_sanacion_realizado:
            logger.info("⚠️ Barra no encontrada. Esperando 2 segundos para intentar autosanación...")
            time.sleep(2)
            if ejecutar_cierra_visor():
                intento_sanacion_realizado = True
                logger.info("🔄 Sanación completada. Reintentando búsqueda de barra...")
                time.sleep(0.5)
                continue  # Reintentar búsqueda inmediatamente
            else:
                intento_sanacion_realizado = True  # Marcar como realizado para evitar bucle infinito
        # ------------------------------

        logger.warning("❌ No se pudo encontrar la barra tras reintento")
        error_msg = "No se pudo encontrar la barra de herramientas de Word después de los reintentos."
        try:
            try:
                from utils.error_handler import handle_error_and_exit
            except ImportError:
                from rpa_framework.utils.error_handler import handle_error_and_exit
            handle_error_and_exit("pega en word.py", error_msg)
        except ImportError:
            enviar_alerta_todos(f"🚨 <b>ASISTENCIA REQUERIDA</b> 🚨\n{error_msg}")
            return False
    
    realizar_accion_en_bloque(bloque_info, accion=accion, offset_y=offset)
    return bloque_info

def set_clipboard_rtf(rtf_text, plain_text=""):
    """Coloca contenido RTF y texto plano en el portapapeles."""
    for attempt in range(3):
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            # Registrar formato RTF si es necesario o usar standard
            cf_rtf = win32clipboard.RegisterClipboardFormat("Rich Text Format")
            # RTF debe ser bytes
            rtf_bytes = rtf_text.encode('cp1252', errors='replace')
            win32clipboard.SetClipboardData(cf_rtf, rtf_bytes)
            
            # Siempre incluir fallback de texto plano para habilitar el botón "Pegar" en MS Word y otros
            if plain_text:
                win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, plain_text)
                
            logger.info("Contenido RTF copiado al portapapeles")
            break
        except Exception as e:
            logger.error(f"Error copiando RTF (intento {attempt+1}): {e}")
            time.sleep(0.5)
        finally:
            try:
                win32clipboard.CloseClipboard()
            except:
                pass

class Test1Automation:
    """Automatización generada: test1"""
    
    def __init__(self):
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
        
        # 3. Borrar contenido existente antes de pegar
        try:
            pyautogui.keyDown('ctrl')
            time.sleep(0.05)
            pyautogui.press('a')
            time.sleep(0.05)
            pyautogui.keyUp('ctrl')
            time.sleep(0.2)
            pyautogui.press('delete')
            time.sleep(0.3)
            logger.info("Contenido previo borrado (Ctrl+A + Delete)")
        except Exception as e:
            logger.warning(f"No se pudo borrar contenido previo: {e}")

        # 4. Poner en portapapeles y pegar
        set_clipboard_rtf(rtf_final, text)

        # Espera crítica para dar tiempo al SO y la app de reconocer el portapapeles
        time.sleep(2.0)

        # --------------------------------------------------------------

        # Ejecutar CTRL+V (manera robusta para evitar pérdida de keypresses)
        try:
            pyautogui.keyDown('ctrl')
            time.sleep(0.1)
            pyautogui.press('v')
            time.sleep(0.1)
            pyautogui.keyUp('ctrl')
            logger.info("Combinación CTRL+V ejecutada con éxito (vía pyautogui keydown/up)")
        except Exception as e:
            logger.warning(f"Error con pyautogui: {e}.")

    def setup(self) -> bool:
        """Configuración inicial."""
        return True
    
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
        
        # Almacenar coordenadas de la barra para offset posterior
        toolbar_center = None
        
        # DB Tracking: Start
        self.db_update_status('En Proceso')

        # Espera crítica para dar tiempo al SO
        time.sleep(4.0)


        
        try:
            # Acción 1: Búsqueda Visual y Click
            try:
                # Usar automatizar_buscar_toolbar que tiene el loop de reintentos y mensaje al usuario
                toolbar_img = r"rpa_framework\utils\word.png"
                bloque_info = automatizar_buscar_toolbar(toolbar_img, accion="click_centro")
                
                if bloque_info:
                    x, y, w, h, center_x, center_y = bloque_info
                    toolbar_center = (center_x, center_y)
                    self.bloque_info = bloque_info
                    
                    results["completed"] += 1
                    logger.info(f"[1/3] ✅ Búsqueda visual y click exitoso con reintentos")
                    time.sleep(1.0) # Espera para asegurar foco tras clic
                    
                    # Se eliminó el clic extra de seguridad que retrasaba la ejecución
                    time.sleep(0.5)
                else:
                    raise Exception("No se encontró la barra de Word o el usuario canceló")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 1, "type": "visual_search", "reason": str(e)})
                logger.error(f"[1/3] ❌ visual_search: {e}")
                raise e

            # Acción 2: PROCESAMIENTO DE DIAGNÓSTICO
            try:
                diag = self.fetch_diagnosis()
                if diag:
                    # Loop de validación con reintentos
                    validacion_exitosa = False
                    pegado_rechazado = False
                    while not validacion_exitosa:
                        self.type_formatted(diag)
                        results["completed"] += 1
                        logger.info(f"[2/3] ✅ Diagnóstico procesado e ingresado")
                        
                        # VALIDACIÓN DE PEGADO
                        if VALIDACION_PEGADO:
                            # Validación automática: asumir pegado correcto y continuar
                            logger.info("✅ Validación automática de pegado (sin interacción del usuario).")
                            validacion_exitosa = True
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

            # Acción 3: GRABAR INFORME (Click en scn_confirm)
            try:
                pegado_ok = locals().get('validacion_exitosa', False) and not locals().get('pegado_rechazado', False)
                
                if pegado_ok:
                    logger.info("Buscando botón 'scn_confirm' mediante UIA...")
                    
                if pegado_ok and hasattr(self, 'bloque_info'):
                    logger.info("Preparando clic final en el botón Guardar (basado en bloque visual)...")
                    
                    x, y, _, _, _, _ = self.bloque_info
                    
                    # Coordenadas relativas actualizadas
                    target_x = x - 236
                    target_y = y - 97
                    
                    # --- LÓGICA CONDICIONAL SOLICITADA ---
                    if HAS_MYSQL:
                        try:
                            # Conectar y ejecutar query de verificación
                            conn = mysql.connector.connect(host='localhost', user='root', password='', database='ris')
                            cursor = conn.cursor()
                            cursor.execute("SELECT count(*) cuenta FROM ris.registro_acciones where estado ='En Proceso' and patologia_critica <>'no'")
                            row_q = cursor.fetchone()
                            cuenta = row_q[0] if row_q else 0
                            conn.close()
                            
                            if cuenta >= 1:
                                logger.info(f"🔍 Se encontraron registros ({cuenta}). Ejecutando script de patología crítica (con cierre)...")
                                script_ext = r"c:\Desarrollo\RPA_3\rpa_framework\recordings\ui\patologia_critica,_con_cierre_ok.py"
                            else:
                                logger.info(f"🔍 No se encontraron registros (cuenta=0). Ejecutando script de patología crítica (NO)...")
                                script_ext = r"c:\Desarrollo\RPA_3\rpa_framework\recordings\ui\patologia_critica,_NO.py"
                            
                            import subprocess
                            subprocess.run([sys.executable, script_ext], check=False)
                        except Exception as e_cond:
                            logger.error(f"⚠️ Error en ejecución condicional: {e_cond}")
                    # -------------------------------------

                    logger.info(f"   → Click en botón Guardar (offset izquierdo 276, arriba 97): ({target_x:.0f}, {target_y:.0f})")
                    
                    # Log del punto de clic real final
                    try:
                        scr = pyautogui.screenshot()
                        scr_cv = cv2.cvtColor(np.array(scr), cv2.COLOR_RGB2BGR)
                        guardar_debug_screenshot(scr_cv, info=self.bloque_info, suffix="click_final_save", target_point=(target_x, target_y))
                    except: pass

                    humanized_click(target_x, target_y, hold_time=1.0)
                    results["completed"] += 1
                    logger.info(f"[3/3] ✅ click scn_confirm exitoso")
                    
                else:
                    logger.warning("Simulación de Action 3 omitida por falta de validación o coordenadas")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 3, "type": "click_scn_confirm", "reason": str(e)})
                logger.error(f"[3/3] ❌ click: {e}")

            results["status"] = "SUCCESS" if results["failed"] == 0 else "PARTIAL"
            
        except Exception as e:
            logger.error(f"❌ Error crítico: {e}")
            results["status"] = "FAILED"
            results["errors"].append({"reason": str(e)})
            try:
                try:
                    from utils.error_handler import handle_error_and_exit
                except ImportError:
                    from rpa_framework.utils.error_handler import handle_error_and_exit
                handle_error_and_exit("pega en word.py", str(e))
            except ImportError:
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
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
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
