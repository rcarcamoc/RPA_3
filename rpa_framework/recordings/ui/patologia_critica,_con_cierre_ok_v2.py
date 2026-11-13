#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script autogenerado: 1
Generado: 2026-03-23 05:50:25
Total de acciones: 5
"""

import sys
import time
import logging
import threading
import tkinter as tk
import pyautogui
import cv2
import numpy as np
import unicodedata
import re
import os
import requests
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Configuración de LLM será importada de utils.llm_config

load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

try:
    from rapidfuzz import fuzz
except ImportError:
    fuzz = None

# Agregar raíz del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.llm_config import OPENROUTER_BASE_URL, LLM_MODELS, LLM_DEFAULT_TEMPERATURE, LLM_DEFAULT_MAX_TOKENS, get_llm_request_params

from pywinauto import Application, findwindows
from core.executor import ActionExecutor
from core.action import Action, ActionType
from ocr.engine import OCREngine
from utils.logging_setup import setup_logging

# Configuración de MySQL (opcional)
try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

logger = logging.getLogger(__name__)

class VisualFeedbackLocal:
    """Feedback visual integrado para ser independiente del framework."""
    def highlight_click(self, x, y, color="#FF0000", duration=0.5):
        try:
            t = threading.Thread(target=self._draw_circle, args=(x, y, color, duration), daemon=True)
            t.start()
        except: pass

    def _draw_circle(self, x, y, color, duration):
        try:
            root = tk.Tk()
            root.overrideredirect(True)
            root.attributes("-topmost", True)
            root.attributes("-alpha", 0.7)
            size = 60
            root.geometry(f"{size}x{size}+{int(x)-30}+{int(y)-30}")
            canvas = tk.Canvas(root, width=size, height=size, bg='white', highlightthickness=0)
            canvas.pack()
            try: root.wm_attributes("-transparentcolor", "white")
            except: pass
            canvas.create_oval(4, 4, size-4, size-4, outline=color, width=5)
            canvas.create_oval(28, 28, 32, 32, fill=color, outline=color)
            root.update()
            time.sleep(duration)
            root.destroy()
        except: pass

    def highlight_region(self, x, y, width, height, color="#FF0000", duration=1.0):
        try:
            t = threading.Thread(target=self._draw_rect, args=(x, y, width, height, color, duration), daemon=True)
            t.start()
        except: pass

    def _draw_rect(self, x, y, width, height, color, duration):
        try:
            root = tk.Tk()
            root.overrideredirect(True)
            root.attributes("-topmost", True)
            root.attributes("-alpha", 0.7)
            root.geometry(f"{width}x{height}+{int(x)}+{int(y)}")
            canvas = tk.Canvas(root, width=width, height=height, bg='white', highlightthickness=0)
            canvas.pack()
            try: root.wm_attributes("-transparentcolor", "white")
            except: pass
            canvas.create_rectangle(2, 2, width-2, height-2, outline=color, width=4)
            root.update()
            time.sleep(duration)
            root.destroy()
        except: pass

    def show_persistent_message(self, text, name, bg_color="#333333", fg_color="#FFFFFF"):
        if not hasattr(self, '_persistent_windows'): self._persistent_windows = {}
        self.hide_persistent_message(name)
        def _create():
            root = tk.Tk()
            root.overrideredirect(True)
            root.attributes("-topmost", True)
            root.attributes("-alpha", 0.9)
            label = tk.Label(root, text=text, bg=bg_color, fg=fg_color, font=("Segoe UI", 12, "bold"), padx=25, pady=12)
            label.pack()
            root.update_idletasks()
            x = (root.winfo_screenwidth() // 2) - (root.winfo_width() // 2)
            root.geometry(f"+{x}+50")
            self._persistent_windows[name] = root
            root.mainloop()
        threading.Thread(target=_create, daemon=True).start()

    def hide_persistent_message(self, name):
        if hasattr(self, '_persistent_windows') and name in self._persistent_windows:
            root = self._persistent_windows.pop(name)
            root.after(0, root.destroy)

    def show_message(self, text, duration=2.0):
        def _show():
            root = tk.Tk()
            root.overrideredirect(True)
            root.attributes("-topmost", True)
            label = tk.Label(root, text=text, bg="#333333", fg="#00FF00", font=("Consolas", 12, "bold"), padx=20, pady=10)
            label.pack()
            root.update_idletasks()
            x = (root.winfo_screenwidth() // 2) - (root.winfo_width() // 2)
            root.geometry(f"+{x}+30")
            root.update()
            time.sleep(duration)
            root.destroy()
        threading.Thread(target=_show, daemon=True).start()

vf = VisualFeedbackLocal()


class Automation1:
    """Automatización generada: 1"""
    
    def __init__(self):
        self.app = None
        self.executor = None
        self.main_window = None
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
            script_name = "1"
            query = "UPDATE registro_acciones SET `update` = NOW(), ultimo_nodo = %s, estado = %s WHERE estado = 'En Proceso'"
            cursor.execute(query, (script_name, status))
            conn.commit()
            conn.close()
            logger.info(f"[DB] Tracking actualizado: {script_name} ({status})")
        except Exception as e:
            logger.warning(f"[DB Error] {e}")

    def db_get_detected_patology(self):
        """Obtiene la patología detectada de la BD."""
        if not HAS_MYSQL: return None
        try:
            conn = mysql.connector.connect(host='localhost', user='root', password='', database='ris')
            cursor = conn.cursor()
            query = "SELECT patologia_critica_detectada FROM registro_acciones WHERE estado = 'En Proceso' LIMIT 1"
            cursor.execute(query)
            result = cursor.fetchone()
            conn.close()
            return result[0] if result and result[0] else None
        except Exception as e:
            logger.warning(f"[DB Get Error] {e}")
            return None

    def call_llm_text_verification(self, ocr_text, target_diag):
        """Valida si el texto OCR coincide semánticamente con el objetivo usando LLM."""
        if not OPENROUTER_API_KEY:
            logger.warning("OPENROUTER_API_KEY no configurado, omitiendo validación LLM.")
            return False
            
        models = LLM_MODELS
        prompt = f"""
Eres un experto clínico en interpretación de terminología médica y facturación.
Tu rol es determinar si el texto "ENCONTRADO" es exactamente el mismo diagnóstico que el "BUSCADO".
ERES TOLERANTE a dedazos o errores tipográficos (ej: "tomografia" y "tomografa"), pero ERES ESTRICTAMENTE INTRANSIGENTE con los NÚMEROS, GRADOS, TIPOS y LATERALIDAD (Izquierdo/Derecho).
Si el diagnóstico buscado dice Nivel 3 o Grado 3 o BIRADS 3, y el encontrado dice 0, 1, 2 o 4 (cualquier otro número), DEBES DAR FALSO (es_match: false). No perdonarás diferencias de grados.

BUSCADO: "{target_diag}"
ENCONTRADO (Línea OCR): "{ocr_text}"

RESPONDE SOLO EN FORMATO JSON:
{{
  "es_match": true o false,
  "razonamiento": "Explicación breve",
  "confianza": 0.93
}}
"""
        for current_model in models:
            logger.info(f"🤖 Consultando LLM {current_model}...")
            try:
                base_url, target_key, provider = get_llm_request_params(current_model)
                if not target_key:
                    target_key = OPENROUTER_API_KEY
                response = requests.post(
                    f"{base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {target_key}", "Content-Type": "application/json"},
                    json={"model": current_model, "messages": [{"role": "user", "content": prompt}], "temperature": LLM_DEFAULT_TEMPERATURE, "max_tokens": LLM_DEFAULT_MAX_TOKENS},
                    timeout=15 # Aumentamos timeout por latencia de modelos gratuitos
                )
                if response.status_code == 429: continue
                response.raise_for_status()
                
                resp_data = response.json()
                if 'choices' not in resp_data or not resp_data['choices']:
                    logger.warning(f"Respuesta sin choices de {current_model}: {resp_data}")
                    continue
                    
                content = resp_data['choices'][0]['message'].get('content', '')
                logger.info(f"Respuesta Raw LLM ({current_model}): {content[:100]}...")
                
                match = re.search(r'\{.*\}', content, re.DOTALL)
                if match:
                    data = json.loads(match.group(0))
                    if data.get('es_match'): return True
                    else: continue
                
                # Fallback simple si no es JSON puro
                if "true" in content.lower() and "match" in content.lower(): return True
            except Exception as e:
                logger.warning(f"Error LLM {current_model}: {e}")
                continue
        return False

    def enfocar_pacs(self):
        """Busca y enfoca la ventana de Carestream Vue PACS."""
        try:
            logger.info("Buscando visor Vue PACS para cambio de contexto final...")
            target_title = ".*Carestream Vue PACS.*"
            titulos = findwindows.find_elements(title_re=target_title, backend='uia')
            
            if not titulos:
                logger.warning("⚠️ No se encontró la ventana de Carestream Vue PACS abierta.")
                return False

            app_pacs = Application(backend='uia').connect(handle=titulos[0].handle)
            win_pacs = app_pacs.window(handle=titulos[0].handle)

            logger.info(f"✨ Trayendo a primer plano: {titulos[0].name}")
            
            # Restaurar si está minimizada
            if win_pacs.get_show_state() == 2: 
                win_pacs.restore()
                time.sleep(0.3)
                
            win_pacs.set_focus()
            time.sleep(0.25)
            win_pacs.set_focus() # Refuerzo para asegurar el foco
            
            if vf: vf.show_message("Cambiado a Vue PACS", duration=0.8)
            return True
        except Exception as e:
            logger.error(f"❌ Error al intentar enfocar PACS: {e}")
            return False

    def focus_carestream_ris(self):
        """Intenta traer el RIS al frente (Carestream o Philips). No es error si falla."""
        try:
            # Lista de posibles títulos
            titles = ["Carestream RIS", "Workflow Information Management", "Carestream RIS V11"]
            for title in titles:
                try:
                    logger.debug(f"Intentando enfocar ventana con título: {title}")
                    titulos = findwindows.find_elements(title_re=f".*{title}.*", backend='uia')
                    if titulos:
                        app_ris = Application(backend='uia').connect(handle=titulos[0].handle)
                        win_ris = app_ris.window(handle=titulos[0].handle)
                        if win_ris.get_show_state() == 2: win_ris.restore()
                        win_ris.set_focus()
                        logger.info(f"✅ Ventana enfocada: {titulos[0].name}")
                        return True
                except:
                    continue
            return False
        except Exception as e:
            logger.warning(f"Error al intentar enfocar RIS: {e}")
            return False

    def stop_with_error(self, message):
        """Detiene la ejecución con un error y actualiza la BD."""
        logger.error(f"🛑 Error crítico: {message}")
        if vf: vf.show_message(f"ERROR: {message}", duration=5.0)
        self.db_update_status('error')
        raise Exception(message)

    def normalize_text(self, text):
        """Normaliza texto para comparación."""
        t = text.lower()
        t = ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')
        t = re.sub(r'[^a-z0-9\-]', ' ', t)
        return ' '.join(t.split())

    def agrupar_por_filas(self, results):
        """Agrupa bloques de texto OCR en líneas coherentes."""
        if not results: return []
        sorted_y = sorted([r for r in results if r['text'].strip()], key=lambda x: x['center']['y'])
        rows = []
        for item in sorted_y:
            matched = False
            for row in rows:
                if abs(row['y_center'] - item['center']['y']) < 15:
                    row['items'].append(item)
                    row['y_center'] = sum(i['center']['y'] for i in row['items']) / len(row['items'])
                    matched = True
                    break
            if not matched: rows.append({'y_center': item['center']['y'], 'items': [item]})
        
        candidatos = []
        for r in sorted(rows, key=lambda x: x['y_center']):
            items_x = sorted(r['items'], key=lambda x: x['center']['x'])
            candidatos.append({
                'text': " ".join([i['text'] for i in items_x]),
                'center': {'x': sum(i['center']['x'] for i in items_x) / len(items_x), 'y': r['y_center']}
            })
        return candidatos

    def humanized_click(self, x, y, duration=0.2, is_double=False):
        """Mueve, resalta con círculo rojo y hace clic sostenido."""
        logger.info(f"Posicionando mouse en ({x}, {y}) para clic {'doble' if is_double else 'sostenido'}...")
        pyautogui.moveTo(x, y, duration=0.2, tween=pyautogui.easeInOutQuad)
        time.sleep(0.05)
        
        if vf:
            vf.highlight_click(x, y, color="#FF0000", duration=0.3) # Círculo ROJO
            time.sleep(0.1)
            
        if is_double:
            pyautogui.doubleClick()
        else:
            pyautogui.mouseDown()
            time.sleep(duration)
            pyautogui.mouseUp()
        time.sleep(0.1)

    def execute_click_action(self, action):
        """Ejecuta un clic usando Pywinauto Native con timeout acotado y fallback rápido a coordenadas."""
        if action.selector:
            try:
                element = self.executor.selector_helper.find_element(
                    action.selector,
                    timeout=self.executor.config.get("element_timeout", 0.8),
                    app_context=action.app_context
                )
                
                # Asegurar foco antes de cualquier técnica
                try:
                    element.set_focus()
                    time.sleep(0.15)
                except: pass
                
                is_double = (action.type == ActionType.DOUBLE_CLICK)
                
                logger.info(f"Haciendo clic nativo en: {action.selector}")
                if is_double:
                    element.double_click_input()
                else:
                    element.click_input()
                
                time.sleep(0.3) # Pausa tras interacción
                return
                
            except Exception as e:
                logger.warning(f"Error al usar selector nativo: {e}. Reintentando con coordenadas...")

        # Fallback a coordenadas si falla el selector o no existe
        if action.position and "x" in action.position and "y" in action.position:
            x, y = action.position["x"], action.position["y"]
            logger.info(f"Fallback: Haciendo clic en coordenadas ({x}, {y})")
            if self.main_window:
                try: self.main_window.set_focus()
                except: pass
            
            # Si no hay elemento, usamos pyautogui como fallback de bajo nivel
            if action.type == ActionType.DOUBLE_CLICK:
                pyautogui.doubleClick(x, y)
            else:
                pyautogui.click(x, y)
        else:
            raise Exception("No hay selector válido ni coordenadas para el clic")
    
    def setup(self) -> bool:
        """Conecta a la aplicación objetivo de forma robusta."""
        logger.info("Configurando conexión a la aplicación...")
        
        try:
            # Estrategia de conexión robusta con reintentos para Carestream RIS
            target_title = ".*(Carestream RIS|Workflow Information Management|Carestream RIS V11).*"
            connected = False
            
            for attempt in range(1, 4):
                try:
                    logger.debug(f"Intento {attempt} de conexión a {target_title}...")
                    # 1. Buscar por título para obtener un handle estable
                    titulos = findwindows.find_elements(title_re=target_title, backend='uia')
                    
                    if titulos:
                        logger.info(f"Ventana encontrada por título: {titulos[0].name}")
                        self.app = Application(backend='uia').connect(handle=titulos[0].handle)
                    else:
                        # 2. Fallback a conectar por process path o title_re directo
                        try:
                            self.app = Application(backend='uia').connect(path="Carestream RIS.exe")
                        except:
                            self.app = Application(backend='uia').connect(title_re=target_title)
                    
                    # 3. Validar existencia y dar foco
                    self.main_window = self.app.window(title_re=target_title)
                    if self.main_window.exists(timeout=5):
                        self.main_window.set_focus()
                        time.sleep(0.5)
                        self.main_window.set_focus() # Segundo foco para asegurar
                        connected = True
                        break
                    else:
                        logger.warning(f"Intento {attempt}: La ventana no parece estar lista")
                except Exception as connect_e:
                    logger.warning(f"Intento {attempt} fallido: {connect_e}")
                    time.sleep(0.5)
            
            if not connected:
                # Fallback final a Desktop
                logger.warning("No se pudo conectar a la ventana específica, usando Desktop como root")
                self.app = Application(backend='uia')
                self.main_window = None
            
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
            "total_actions": 5,
            "completed": 0,
            "failed": 0,
            "errors": [],
            "start_time": datetime.now().isoformat(),
        }
        
        logger.info(f"🚀 Iniciando ejecución: {results['total_actions']} acciones")
        
        # DB Tracking: Start
        self.db_update_status('En Proceso')
        

        try:
            # Acción 1: Cambiar a la ventana de Carestream RIS
            try:
                time.sleep(1)
                logger.info("Buscando y enfocando la ventana de Carestream RIS...")
                
                # Estrategia de conexión robusta con reintentos
                connected = False
                for attempt in range(1, 4):
                    try:
                        logger.debug(f"Intento {attempt} de conexión a Carestream RIS...")
                        # 1. Buscar por título para obtener un handle estable
                        titulos = findwindows.find_elements(title_re=".*(Carestream RIS|Workflow Information Management|Carestream RIS V11).*", backend='uia')
                        
                        if titulos:
                            logger.info(f"Ventana encontrada por título: {titulos[0].name}")
                            self.app = Application(backend='uia').connect(handle=titulos[0].handle)
                        else:
                            # 2. Fallback a conectar por process path o title_re directo
                            try:
                                self.app = Application(backend='uia').connect(path="Carestream RIS.exe")
                            except:
                                self.app = Application(backend='uia').connect(title_re=".*(Carestream RIS|Workflow Information Management|Carestream RIS V11).*")
                        
                        # 3. Validar existencia y dar foco (específico en vez de top_window)
                        main_window = self.app.window(title_re=".*(Carestream RIS|Workflow Information Management|Carestream RIS V11).*")
                        if main_window.exists(timeout=5):
                            main_window.set_focus()
                            # A veces requiere un segundo intento o esperar un poco
                            time.sleep(0.5)
                            main_window.set_focus()
                            connected = True
                            break
                        else:
                            logger.warning(f"Intento {attempt}: La ventana no parece estar lista")
                            
                    except Exception as connect_e:
                        logger.warning(f"Intento {attempt} fallido: {connect_e}")
                        time.sleep(2) # Esperar antes de reintentar
                
                if not connected:
                    # Fallback final: intentar top_window pero con captura de error
                    try:
                        logger.info("Intentando fallback final con top_window...")
                        window = self.app.top_window()
                        window.set_focus()
                    except Exception as final_e:
                        raise Exception(f"Fallo total al conectar con Carestream RIS: {final_e}")
                
                # Actualizar el executor con el nuevo contexto de aplicación
                self.executor = ActionExecutor(self.app, {})
                
                results["completed"] += 1
                logger.info("[1/16] ✅ Ventana de Carestream RIS enfocada")
            except Exception as e:
                self.stop_with_error(f"No se pudo encontrar o activar la ventana de Carestream RIS: {e}")

            # Acción 2: CLICK en resultado critico
            # Mover antes de hacer clic
            time.sleep(0.5)
            self.executor.execute(Action(
                type=ActionType.MOVE,
                position={'x': 750, 'y': 84},
                timestamp=datetime.now()
            ))
            action = Action(
                type=ActionType.DOUBLE_CLICK,
                duration=0.3,
                selector=None,
                position={'x': 750, 'y': 84},
                timestamp=datetime.fromisoformat("2026-01-14T15:10:39.561316")
            )
            self.execute_click_action(action)
            results["completed"] += 1
            logger.info(f"[2/16] ✅ double_click")
            time.sleep(0.8)  # Esperar a que cargue la pestaña Resultado Crítico before clicking ComboBox



            results["status"] = "SUCCESS"
            
        except Exception as e:
            self.stop_with_error(str(e))









        try:
            # Acción 1: CLICK en ComboBox "¿Resultado crítico?" y selección por teclado (3x Flecha Abajo = Sí)
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector=None,
                    position={'x': 294, 'y': 127},
                    timestamp=datetime.fromisoformat("2026-03-23T05:50:05.533783")
                )
                self.execute_click_action(action)
                results["completed"] += 1
                logger.info(f"[1/5] ✅ click en (294, 127)")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 1, "type": "click", "reason": str(e)})
                logger.error(f"[1/5] ❌ click: {e}")

            # Selección de "Sí" con teclado: 2x Down = No, 3x Down = Sí
            time.sleep(0.3)
            try:
                logger.info("Seleccionando 'Sí' con teclado (3x Flecha Abajo + Enter)...")
                for _ in range(3):
                    pyautogui.press('down')
                    time.sleep(0.08)
                pyautogui.press('enter')
                time.sleep(0.35)
                results["completed"] += 1
                logger.info("✅ Selección de 'Sí' por teclado completada")
            except Exception as e_si:
                logger.error(f"Error seleccionando 'Sí' por teclado: {e_si}")
                results["failed"] += 1
                results["errors"].append({"action_idx": 2, "type": "key_select_si", "reason": str(e_si)})
                raise


            # Acción 2: Obtener patología y pre-inicializar OCR ANTES de abrir el ComboBox
            # (evita que el menú desplegable se cierre por demora de inicialización o foco de overlays)
            patologia_detectada = getattr(self, "override_patologia", None) or self.db_get_detected_patology()
            if not patologia_detectada:
                raise Exception("No se pudo obtener la patología detectada de la BD (use --patologia 'NOMBRE' para pruebas).")

            patologia_detectada = patologia_detectada.upper()
            primera_letra = patologia_detectada[0].upper()

            def normalize_text(text):
                t = text.lower()
                t = ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')
                t = re.sub(r'[^a-z0-9\-]', ' ', t)
                return ' '.join(t.split())

            target_norm = normalize_text(patologia_detectada)

            def get_combo_selected_text(ctrl):
                if ctrl is None:
                    return ""
                for getter in (
                    lambda: ctrl.selected_text(),
                    lambda: ctrl.window_text(),
                    lambda: ctrl.legacy_properties().get("Value", ""),
                ):
                    try:
                        val = getter()
                        if val and str(val).strip():
                            return str(val).strip()
                    except Exception:
                        pass
                return ""

            def is_selected_match(selected_txt):
                if not selected_txt:
                    return False
                sel_norm = normalize_text(selected_txt)
                if not sel_norm:
                    return False
                if sel_norm == target_norm:
                    return True
                if fuzz and fuzz.ratio(target_norm, sel_norm) >= 90:
                    return True
                return False

            def agrupar_por_filas(results_ocr):
                if not results_ocr:
                    return []
                sorted_y = sorted([r for r in results_ocr if r['text'].strip()], key=lambda x: x['center']['y'])
                rows = []
                for item in sorted_y:
                    matched = False
                    for row in rows:
                        if abs(row['y_center'] - item['center']['y']) < 8:
                            row['items'].append(item)
                            matched = True
                            break
                    if not matched:
                        rows.append({'y_center': item['center']['y'], 'items': [item]})

                candidatos = []
                for r in rows:
                    items_x = sorted(r['items'], key=lambda x: x['center']['x'])
                    bloques = []
                    bloque_actual = [items_x[0]]
                    for i in range(1, len(items_x)):
                        dist_x = items_x[i]['center']['x'] - items_x[i-1]['center']['x']
                        if dist_x > 120:
                            bloques.append(bloque_actual)
                            bloque_actual = [items_x[i]]
                        else:
                            bloque_actual.append(items_x[i])
                    bloques.append(bloque_actual)

                    for bloque in bloques:
                        texto_completo = " ".join([i['text'] for i in bloque])
                        avg_x = sum(i['center']['x'] for i in bloque) / len(bloque)
                        candidatos.append({
                            'text': texto_completo,
                            'center': {'x': avg_x, 'y': r['y_center']},
                            'items': bloque
                        })
                return candidatos

            def merge_ocr_passes(list1, list2):
                final = list(list1)
                for item2 in list2:
                    is_duplicate = False
                    for item1 in list1:
                        dist = abs(item1['center']['x'] - item2['center']['x']) + abs(item1['center']['y'] - item2['center']['y'])
                        if dist < 8:
                            is_duplicate = True
                            break
                    if not is_duplicate:
                        final.append(item2)
                return final

            def buscar_mejor_match_local(lineas):
                best_m = None
                best_base = 0
                best_ratio = 0
                for res in lineas:
                    ocr_text = res['text']
                    found_norm = normalize_text(ocr_text)
                    if not found_norm or len(found_norm) < 3:
                        continue
                    if len(found_norm) < len(target_norm) * 0.3:
                        if not target_norm.startswith(found_norm):
                            continue
                    if target_norm == found_norm:
                        logger.info(f"✅ MATCH EXACTO ABSOLUTO: '{ocr_text}'")
                        return res, 100, 100

                    long_diff = len(found_norm) / float(len(target_norm) if len(target_norm) > 0 else 1)
                    if fuzz:
                        score_partial = fuzz.partial_ratio(target_norm, found_norm)
                        score_token = fuzz.token_set_ratio(target_norm, found_norm)
                        score_ratio = fuzz.ratio(target_norm, found_norm)
                    else:
                        score_partial = 100 if target_norm in found_norm else 0
                        score_token = score_partial
                        score_ratio = 100 if target_norm == found_norm else (50 if score_partial else 0)

                    if long_diff > 2.0:
                        penalizacion = int((long_diff - 1.0) * 15)
                        score_token = max(0, score_token - penalizacion)
                        score_partial = max(0, score_partial - penalizacion)

                    target_nums = set(re.findall(r'\d+', target_norm))
                    found_nums = set(re.findall(r'\d+', found_norm))
                    if target_nums and target_nums != found_nums:
                        score_token = 0
                        score_partial = 0

                    base_score = max(score_partial, score_token)
                    res['score'] = base_score

                    if len(found_norm) >= 4 and target_norm.endswith(found_norm[1:]) and target_norm.startswith(target_norm[0]):
                        if len(found_norm) >= len(target_norm) - 2:
                            logger.info(f"✅ MATCH POR PREFIJO TRUNCADO: '{ocr_text}' ≈ '{patologia_detectada}'")
                            return res, 97, score_ratio

                    if base_score > 88:
                        if base_score > best_base or (base_score == best_base and score_ratio > best_ratio):
                            best_base = base_score
                            best_ratio = score_ratio
                            best_m = res

                return best_m, best_base, best_ratio

            paddle_engine = None
            try:
                paddle_engine = OCREngine(
                    engine='paddleocr',
                    language='es',
                    use_gpu=True
                )
            except Exception as e_pad_init:
                logger.warning(f"⚠️ No se pudo inicializar PaddleOCR, se usará Tesseract como respaldo: {e_pad_init}")

            tesseract_engine = None
            def get_tesseract_engine():
                nonlocal tesseract_engine
                if tesseract_engine is None:
                    tesseract_engine = OCREngine(
                        engine='tesseract',
                        language='spa',
                        use_gpu=False,
                        confidence_threshold=0.05,
                        preprocess=False,
                        custom_config='--psm 11'
                    )
                return tesseract_engine

            region_x, region_y = 50, 170
            region_w, region_h = 610, 610

            element_diag = None
            seleccion_confirmada = False
            max_intentos_combo = 3

            for intento in range(1, max_intentos_combo + 1):
                logger.info(f"🔄 Intento {intento}/{max_intentos_combo} de selección de patología '{patologia_detectada}'...")
                time.sleep(0.25)

                try:
                    logger.info("Buscando ComboBox de diagnóstico (cbxClCodigodiagnostico1)...")
                    element_diag = self.main_window.child_window(auto_id='cbxClCodigodiagnostico1', control_type="ComboBox", found_index=0)
                    if element_diag.exists(timeout=1.5):
                        element_diag.click_input()
                    else:
                        raise Exception("ComboBox 'cbxClCodigodiagnostico1' no encontrado")
                    if intento == 1:
                        results["completed"] += 1
                    logger.info("[2/5] ✅ clic en ComboBox diagnóstico (Pywinauto Native)")
                except Exception as e_diag:
                    logger.warning(f"Selector de combo diagnóstico falló: {e_diag}. Usando coordenadas...")
                    self.humanized_click(608, 192)
                    if intento == 1:
                        results["completed"] += 1
                    logger.info("[2/5] ✅ clic (fallback coords) en ComboBox diagnóstico")

                time.sleep(0.35)
                logger.info(f"Tecleando letra '{primera_letra}' sobre el control...")
                pyautogui.press(primera_letra)
                if intento == 1:
                    results["completed"] += 1
                logger.info(f"✅ Letra '{primera_letra}' tecleada exitosamente")

                time.sleep(0.5)  # Esperar al despliegue sin overlays que roben foco
                logger.info(">>>> INICIANDO BÚSQUEDA OCR <<<<")

                screenshot = pyautogui.screenshot(region=(region_x, region_y, region_w, region_h))
                img_np = np.array(screenshot)
                img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
                img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

                lineas_ocr = []
                best_match = None
                best_base_score = 0
                best_ratio_score = 0

                # Motor primario: PaddleOCR GPU (resolución nativa 1x, lectura por líneas)
                if paddle_engine is not None:
                    try:
                        res_paddle = paddle_engine.extract_text_with_location(img_rgb)
                        if res_paddle:
                            lineas_ocr = agrupar_por_filas(res_paddle)
                            best_match, best_base_score, best_ratio_score = buscar_mejor_match_local(lineas_ocr)
                    except Exception as e_pad:
                        logger.warning(f"⚠️ Error en PaddleOCR, usando fallback Tesseract: {e_pad}")

                # Fallback automático a Tesseract 3x si PaddleOCR no encontró match o no estuvo disponible
                if not best_match:
                    logger.info("🔄 Ejecutando fallback OCR con Tesseract 3x...")
                    tess = get_tesseract_engine()
                    h, w = img_bgr.shape[:2]
                    img_rgb_up = cv2.resize(img_rgb, (w * 3, h * 3), interpolation=cv2.INTER_LANCZOS4)

                    res_norm = tess.extract_text_with_location(img_rgb_up)
                    for r in res_norm:
                        r['center']['x'] /= 3.0
                        r['center']['y'] /= 3.0

                    lineas_ocr = agrupar_por_filas(res_norm)
                    best_match, best_base_score, best_ratio_score = buscar_mejor_match_local(lineas_ocr)

                    if not best_match or best_base_score < 95:
                        gray_up = cv2.cvtColor(cv2.resize(img_bgr, (w * 3, h * 3), interpolation=cv2.INTER_LANCZOS4), cv2.COLOR_BGR2GRAY)
                        inv_gray = 255 - gray_up
                        _, res_inv_bin = cv2.threshold(inv_gray, 140, 255, cv2.THRESH_BINARY)
                        res_inv = tess.extract_text_with_location(res_inv_bin)
                        for r in res_inv:
                            r['center']['x'] /= 3.0
                            r['center']['y'] /= 3.0
                        ocr_results = merge_ocr_passes(res_norm, res_inv)
                        lineas_ocr = agrupar_por_filas(ocr_results)
                        best_match, best_base_score, best_ratio_score = buscar_mejor_match_local(lineas_ocr)

                logger.info(f"--- TEXTO OCR DETECTADO ({len(lineas_ocr)} líneas) ---")
                for i, row in enumerate(lineas_ocr):
                    logger.info(f"Línea {i+1}: '{row['text']}' (y={row['center']['y']:.1f})")
                logger.info("------------------------------------------")

                if best_match and best_base_score < 100:
                    logger.info(f"✅ MATCH LOCAL CERCANO: '{best_match['text']}' (Base={best_base_score}, Ratio={best_ratio_score})")

                if not best_match and lineas_ocr:
                    logger.info("⚠️ No hubo match local >88%. Consultando LLM con los textos detectados (top 5 candidatos)...")
                    candidatos_llm = [r for r in lineas_ocr if len(r['text'].strip()) >= 3]
                    candidatos_llm.sort(key=lambda x: x.get('score', 0), reverse=True)
                    for res in candidatos_llm[:5]:
                        ocr_text = res['text']
                        logger.info(f"Analizando semántica de: '{ocr_text}' (score: {res.get('score', 0)})")
                        if self.call_llm_text_verification(ocr_text, patologia_detectada):
                            logger.info(f"✅ MATCH LLM CONFIRMADO para '{ocr_text}'")
                            best_match = res
                            break

                # Log visual
                try:
                    log_dir = Path("rpa_framework/log/patologia_critica")
                    log_dir.mkdir(parents=True, exist_ok=True)
                    now_str = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
                    filename = f"patologia_{now_str}.png"
                    img_log = img_bgr.copy()
                    if best_match:
                        cx, cy = int(best_match['center']['x']), int(best_match['center']['y'])
                        cv2.circle(img_log, (cx, cy), 20, (0, 0, 255), 3)
                        cv2.putText(img_log, "MATCH OK", (cx + 25, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                    else:
                        cv2.rectangle(img_log, (0, 0), (img_log.shape[1] - 1, img_log.shape[0] - 1), (0, 0, 255), 3)
                    cv2.imwrite(str(log_dir / filename), img_log)
                    logger.info(f"📸 Log visual guardado en: {log_dir / filename}")
                except Exception as e_log:
                    logger.warning(f"No se pudo guardar el log visual OCR: {e_log}")

                if best_match:
                    screen_x = region_x + int(best_match['center']['x'])
                    screen_y = region_y + int(best_match['center']['y'])
                    logger.info(f"✅ OCR Match final listo: '{best_match['text']}' -> Clic rápido en ({screen_x}, {screen_y})")

                    # Clic directo y rápido (sin overlays) para evitar que el menú desplegable desaparezca
                    pyautogui.moveTo(screen_x, screen_y, duration=0.15, tween=pyautogui.easeInOutQuad)
                    pyautogui.click()
                    time.sleep(0.4)

                    selected_val = get_combo_selected_text(element_diag)
                    logger.info(f"🔎 Valor en ComboBox tras clic: '{selected_val}' (esperado: '{patologia_detectada}')")
                    if is_selected_match(selected_val):
                        seleccion_confirmada = True
                        logger.info(f"✅ Selección confirmada en ComboBox: '{selected_val}'")
                        break
                    else:
                        logger.warning(f"⚠️ El ComboBox quedó en '{selected_val}' en lugar de '{patologia_detectada}'. Reintentando...")
                else:
                    logger.warning(f"❌ No se encontró '{patologia_detectada}' en OCR ni con validación LLM (intento {intento}/{max_intentos_combo})")

            if not seleccion_confirmada:
                raise Exception(f"No se pudo confirmar la selección de '{patologia_detectada}' en el ComboBox tras {max_intentos_combo} intentos.")

            results["status"] = "SUCCESS" if results["failed"] == 0 else "PARTIAL"
            
            # PASO FINAL: Si todo salió bien, pasar a Vue PACS
            if results["status"] == "SUCCESS":
                time.sleep(0.4)
                self.enfocar_pacs()
                
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
    import argparse
    parser = argparse.ArgumentParser(description="Selección de patología crítica v2")
    parser.add_argument("--patologia", type=str, default=None, help="Patología de prueba (opcional si no hay registro 'En Proceso' en BD)")
    args, _ = parser.parse_known_args()

    setup_logging()
    
    automation = Automation1()
    automation.override_patologia = args.patologia
    results = automation.run()
    
    print("\n" + "="*50)
    print(f"Resultado: {results['status']}")
    print(f"Completadas: {results['completed']}/{results['total_actions']}")
    print(f"Fallidas: {results['failed']}")
    print("="*50)
    
    return 0 if results["status"] == "SUCCESS" else 1


if __name__ == "__main__":
    sys.exit(main())
