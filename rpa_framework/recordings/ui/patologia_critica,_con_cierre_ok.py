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

# --- CONFIGURACIÓN INTEGRADA PARA OCR Y LLM ---
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
LLM_MODELS = [
    "google/gemma-3-27b-it:free",

]
LLM_DEFAULT_TEMPERATURE = 0.2
LLM_DEFAULT_MAX_TOKENS = 150

load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

try:
    from rapidfuzz import fuzz
except ImportError:
    fuzz = None

# Agregar raíz del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

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
  "confianza": 0.95
}}
"""
        for current_model in models:
            logger.info(f"🤖 Consultando LLM {current_model}...")
            try:
                response = requests.post(
                    f"{OPENROUTER_BASE_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
                    json={"model": current_model, "messages": [{"role": "user", "content": prompt}], "temperature": 0.2, "max_tokens": 150},
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
            time.sleep(0.5)
            win_pacs.set_focus() # Refuerzo para asegurar el foco
            
            if vf: vf.show_message("Cambiado a Vue PACS", duration=2.0)
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

    def humanized_click(self, x, y, duration=0.6, is_double=False):
        """Mueve, resalta con círculo rojo y hace clic sostenido."""
        logger.info(f"Posicionando mouse en ({x}, {y}) para clic {'doble' if is_double else 'sostenido'}...")
        pyautogui.moveTo(x, y, duration=0.4, tween=pyautogui.easeInOutQuad)
        time.sleep(0.1)
        
        if vf:
            vf.highlight_click(x, y, color="#FF0000", duration=0.8) # Círculo ROJO
            time.sleep(0.2)
            
        if is_double:
            pyautogui.doubleClick()
        else:
            pyautogui.mouseDown()
            time.sleep(duration)
            pyautogui.mouseUp()
        time.sleep(0.2)

    def execute_click_action(self, action):
        # Acción nativa especial en tabControl1 por coordenadas
        try:
            element = self.executor.selector_helper.find_element(
                {'automation_id': 'tabControl1'},
                timeout=2.0
            )                 
            # Asegurar foco antes de cualquier técnica
            try:
                element.set_focus()
                time.sleep(0.3)
            except: pass
            
            is_double = (action.type == ActionType.DOUBLE_CLICK)
            
            # Resaltado visual para feedback (opcional pero solicitado)
            if vf: 
                vf.highlight_click(744, 84, color="#FF0000", duration=0.8)
                time.sleep(0.2)
                
            logger.info(f"Haciendo clic nativo en tabControl1 en: (744, 84)")
            if is_double:
                element.double_click_input(coords=(744, 84))
            else:
                element.click_input(coords=(744, 84))
            
            time.sleep(0.5) 
        except Exception as e:
            logger.warning(f"Error al usar clic nativo en coordenadas fijas: {e}")
        """Ejecuta un clic usando EXCLUSIVAMENTE la técnica Pywinauto Native."""
        if action.selector:
            try:
                element = self.executor.selector_helper.find_element(
                    action.selector,
                    timeout=self.executor.config.get("element_timeout", 2.0),
                    app_context=action.app_context
                )
                
                # Asegurar foco antes de cualquier técnica
                try:
                    element.set_focus()
                    time.sleep(0.3)
                except: pass
                
                is_double = (action.type == ActionType.DOUBLE_CLICK)
                
                logger.info(f"Haciendo clic nativo en: {action.selector}")
                if is_double:
                    element.double_click_input()
                else:
                    element.click_input()
                
                time.sleep(0.5) # Pausa tras interacción
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
                    time.sleep(1)
            
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
                duration=0.5,
                selector={'automation_id': 'tabControl1'},
                position={'x': 750, 'y': 84},
                timestamp=datetime.fromisoformat("2026-01-14T15:10:39.561316")
            )
            self.execute_click_action(action)
            results["completed"] += 1
            logger.info(f"[2/16] ✅ double_click")



            results["status"] = "SUCCESS"
            
        except Exception as e:
            self.stop_with_error(str(e))









        try:
            # Acción 1: CLICK
            try:
                action = Action(
                    type=ActionType.CLICK,
                    selector={'name': 'Abrir', 'control_type': 'Button'},
                    position={'x': 294, 'y': 127},
                    timestamp=datetime.fromisoformat("2026-03-23T05:50:05.533783")
                )
                self.execute_click_action(action)
                results["completed"] += 1
                logger.info(f"[1/5] ✅ click")
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({"action_idx": 1, "type": "click", "reason": str(e)})
                logger.error(f"[1/5] ❌ click: {e}")

            # Intervención manual tras primer clic: Confirmación de "Sí"
            time.sleep(2)
            try:
                logger.info("Buscando elemento 'Sí'...")
                element_si = self.main_window.child_window(title='Sí', control_type='ListItem')
                
                if element_si.exists(timeout=3):
                    rect = element_si.rectangle()
                    self.humanized_click(rect.mid_point().x, rect.mid_point().y)
                else:
                    raise Exception("Elemento 'Sí' no encontrado")
                
                # Pausa tras el clic para que se vea la selección
                time.sleep(0.5)
                results["completed"] += 1
                logger.info("✅ clic humanizado en 'Sí' exitoso")
            except Exception as e_si:
                logger.info("Esperando un poco más para el fallback de 'Sí'...")
                time.sleep(1)
                logger.error(f"Error en clic 'Sí': {e_si}")
                # Fallback a coordenadas
                logger.warning("Fallo en selector de 'Sí', intentando fallback por coordenadas...")
                try:
                    self.humanized_click(201, 190)
                    results["completed"] += 1
                    logger.info("✅ clic humanizado (fallback) exitoso")
                except Exception as e_coord:
                    logger.error(f"Fallo total en búsqueda de 'Sí': {e_coord}")


            # Acción 2: CLICK en ComboBox de diagnóstico
            time.sleep(1)
            try:
                logger.info("Buscando ComboBox de diagnóstico (cbxClCodigodiagnostico1)...")
                element_diag = self.main_window.child_window(auto_id='cbxClCodigodiagnostico1', control_type="ComboBox")
                
                if element_diag.exists(timeout=3):
                    element_diag.click_input()
                else:
                    raise Exception("ComboBox 'cbxClCodigodiagnostico1' no encontrado")
                    
                results["completed"] += 1
                logger.info("[2/5] ✅ clic en ComboBox diagnóstico (Pywinauto Native)")
            except Exception as e_diag:
                logger.warning(f"Selector de combo diagnóstico falló: {e_diag}. Usando coordenadas...")
                try:
                    self.humanized_click(608, 192)
                    results["completed"] += 1
                    logger.info("[2/5] ✅ clic (fallback coords) en ComboBox diagnóstico")
                except Exception as e2:
                    logger.error(f"[2/5] ❌ fallo total: {e2}")

            # === NUEVA SECCIÓN: TECLEO Y BÚSQUEDA OCR FINAL ===
              # Acción Extra: Teclear "P" (ahora será la primera letra de la BD) (sin cambiar foco)
            patologia_detectada = self.db_get_detected_patology()
            if not patologia_detectada:
                raise Exception("No se pudo obtener la patología detectada de la BD.")
            
            # Forzar texto en mayúsculas para la búsqueda OCR y LLM
            patologia_detectada = patologia_detectada.upper()
                
            primera_letra = patologia_detectada[0].upper()
            time.sleep(0.5)
            try:
                import pyautogui
                logger.info(f"Tecleando letra '{primera_letra}' sobre el control...")
                pyautogui.press(primera_letra)
                results["completed"] += 1
                logger.info(f"✅ Letra '{primera_letra}' tecleada exitosamente")
            except Exception as e_p:
                logger.error(f"Error tecleando '{primera_letra}': {e_p}")

            # === NUEVA ACCION OCR ===
            time.sleep(1) # Esperar al despliegue
            region_x, region_y = 50, 170
            region_w, region_h = 610, 610 # 660-50, 780-170

            logger.info(">>>> INICIANDO BÚSQUEDA OCR <<<<")
            if vf:
                vf.highlight_region(region_x, region_y, region_w, region_h, duration=1.0)
                vf.show_persistent_message("PROCESANDO OCR...", "ocr", bg_color="#FFEB3B", fg_color="#000000")
            
            try:
                screenshot = pyautogui.screenshot(region=(region_x, region_y, region_w, region_h))
                img_np = np.array(screenshot)
                img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

                # Motor OCR
                ocr_engine = OCREngine(
                    engine='tesseract', 
                    language='spa', 
                    use_gpu=False, 
                    confidence_threshold=0.05,
                    preprocess=False, 
                    custom_config='--psm 11'
                )

                # Mejora OCR Crítica: Escalado 3x y Binarización para el ítem seleccionado (Azul)
                h, w = img_bgr.shape[:2]
                img_rgb_up = cv2.resize(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB), (w*3, h*3), interpolation=cv2.INTER_LANCZOS4)
                
                # 1. Pasada normal (Imagen Escalada 3x)
                res_norm = ocr_engine.extract_text_with_location(img_rgb_up)
                
                # 2. Pasada de contraste para Selección (Invertida + Threshold)
                # El texto blanco sobre azul, al invertirse, da mejor contraste si binarizamos
                gray_up = cv2.cvtColor(cv2.resize(img_bgr, (w*3, h*3), interpolation=cv2.INTER_LANCZOS4), cv2.COLOR_BGR2GRAY)
                inv_gray = 255 - gray_up
                # Umbral: lo que no sea texto oscuro (letras blancas originales) se va al blanco
                _, res_inv_bin = cv2.threshold(inv_gray, 140, 255, cv2.THRESH_BINARY)
                res_inv = ocr_engine.extract_text_with_location(res_inv_bin)
                
                # Función para mezclar y escalar coordenadas de vuelta a 1x
                def clean_and_rescale(list_up, factor=3.0):
                    for r in list_up:
                        r['center']['x'] /= factor
                        r['center']['y'] /= factor
                    return list_up

                ocr_results = clean_and_rescale(res_norm)
                ocr_results_inv = clean_and_rescale(res_inv)
                
                # Combinar resultados (priorizando invertida si hay conflicto en esa zona)
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

                ocr_results = merge_ocr_passes(ocr_results, ocr_results_inv)
                
                # Agrupador de palabras por filas (Eje Y) estricto
                def agrupar_por_filas(results):
                    if not results: return []
                    sorted_y = sorted([r for r in results if r['text'].strip()], key=lambda x: x['center']['y'])
                    
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

                lineas_ocr = agrupar_por_filas(ocr_results)
                
                logger.info(f"--- TEXTO OCR DETECTADO ({len(lineas_ocr)} líneas) ---")
                for i, row in enumerate(lineas_ocr):
                    logger.info(f"Línea {i+1}: '{row['text']}' (y={row['center']['y']:.1f})")
                logger.info("------------------------------------------")

                def normalize_text(text):
                    t = text.lower()
                    t = ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn')
                    t = re.sub(r'[^a-z0-9\-]', ' ', t)
                    return ' '.join(t.split())

                target_norm = normalize_text(patologia_detectada)
                
                # Iterar para validación Local (Buscando el mejor absoluto)
                best_match = None
                best_base_score = 0
                best_ratio_score = 0
                candidatos_validos = []

                for res in lineas_ocr:
                    ocr_text = res['text']
                    found_norm = normalize_text(ocr_text)
                    
                    # Filtramos ruido o elementos muy cortos (Acrónimos clínicos suelen ser de 3: TEP, AVE, HTE)
                    if not found_norm or len(found_norm) < 3: continue
                    
                    # Filtro "Sub-Representación" relajado: si es muy corto comparado al objetivo, 
                    # solo lo permitimos si es un match exacto del inicio del objetivo (ej. "TEP")
                    if len(found_norm) < len(target_norm) * 0.3:
                        if not target_norm.startswith(found_norm): continue                    
                    # === MATCH EXACTO INMEDIATO ===
                    if target_norm == found_norm:
                        logger.info(f"✅ MATCH EXACTO ABSOLUTO: '{ocr_text}'")
                        best_match = res
                        best_base_score = 100
                        best_ratio_score = 100
                        break # Contamos con el mejor candidato posible, detenemos búsqueda local
                    
                    # Filtro "Sobre-Representación" (Nuevo): Si lo leído en OCR (ej. línea completa con ruido u otros diagnósticos)
                    # es inmensamente más largo que lo que busco, lo penalizamos. "RESULTADO BIRADS 3" (18 chars)
                    # vs "RUPTURA RESULTADO DE BIRADS LIGAMENTO 3 RODILLA" (47 chars). 
                    long_diff = len(found_norm) / float(len(target_norm) if len(target_norm)>0 else 1)
                    
                    if fuzz:
                        score_partial = fuzz.partial_ratio(target_norm, found_norm)
                        score_token = fuzz.token_set_ratio(target_norm, found_norm)
                        score_ratio = fuzz.ratio(target_norm, found_norm) # Desempate y pureza
                    else:
                        score_partial = 100 if target_norm in found_norm else 0
                        score_token = score_partial
                        score_ratio = 100 if target_norm == found_norm else (50 if score_partial else 0)

                    # Si el target es muy pequeño adentro de una oración enorme, TokenSet tiende a dar 100%.
                    # Lo castigamos rebajándole puntos si la longitud de la oración OCR es más del doble de lo esperado.
                    if long_diff > 2.0:
                        penalizacion = int((long_diff - 1.0) * 15) # Le restamos un % según qué tan largo sea
                        score_token = max(0, score_token - penalizacion)
                        score_partial = max(0, score_partial - penalizacion)

                    # === FILTRO NUMÉRICO CRÍTICO ===
                    # Si hay números (como grados o niveles BIRADS), no podemos confiar en similitud parcial
                    target_nums = set(re.findall(r'\d+', target_norm))
                    found_nums = set(re.findall(r'\d+', found_norm))
                    
                    # Si el objetivo tiene números pero el encontrado no lo tiene, o si son distintos (ej. 3 vs 0), es un mismatch inaceptable
                    if target_nums and target_nums != found_nums:
                        score_token = 0
                        score_partial = 0

                    base_score = max(score_partial, score_token)
                    res['score'] = base_score
                    
                    # === ESTRÉS LOCAL ELEVADO (>95%) ===
                    # Para diagnósticos críticos exigimos que sea casi idéntico
                    if base_score > 95:
                        candidatos_validos.append(res)
                        if base_score > best_base_score or (base_score == best_base_score and score_ratio > best_ratio_score):
                            best_base_score = base_score
                            best_ratio_score = score_ratio
                            best_match = res

                if best_match and best_base_score < 100:
                    logger.info(f"✅ MATCH LOCAL CERCANO: '{best_match['text']}' (Base={best_base_score}, Ratio={best_ratio_score})")

                # Si falló local (no hubo nada sobre 95 limpios), intentamos LLM con los textos capturados
                if not best_match and lineas_ocr:
                    logger.info("⚠️ No hubo match local >95%. Consultando LLM con los textos detectados (top 5 candidatos)...")
                    if vf: vf.show_persistent_message("Validando con LLM...", "llm", bg_color="#FF9800", fg_color="#000000")
                    
                    # Filtrar basura y ordenar por mejor score local, limitando a 5
                    candidatos_llm = [r for r in lineas_ocr if len(r['text'].strip()) >= 3]
                    candidatos_llm.sort(key=lambda x: x.get('score', 0), reverse=True)
                    
                    for res in candidatos_llm[:5]:
                        ocr_text = res['text']
                        logger.info(f"Analizando semántica de: '{ocr_text}' (score: {res.get('score', 0)})")
                        is_match_llm = self.call_llm_text_verification(ocr_text, patologia_detectada)
                        if is_match_llm:
                            logger.info(f"✅ MATCH LLM CONFIRMADO para '{ocr_text}'")
                            best_match = res
                            break
                    if vf: vf.hide_persistent_message("llm")

                # Log visual (carpeta solicitada y marcado de clic)
                try:
                    log_dir = Path("rpa_framework/log/patologia_critica")
                    log_dir.mkdir(parents=True, exist_ok=True)
                    now_str = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
                    filename = f"patologia_{now_str}.png"
                    img_log = img_bgr.copy()
                    
                    if best_match:
                        cx, cy = int(best_match['center']['x']), int(best_match['center']['y'])
                        cv2.circle(img_log, (cx, cy), 20, (0, 0, 255), 3) # Círculo ROJO en el log (BGR: 0,0,255)
                        cv2.putText(img_log, f"MATCH OK", (cx+25, cy), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                    else:
                        cv2.rectangle(img_log, (0, 0), (img_log.shape[1]-1, img_log.shape[0]-1), (0, 0, 255), 3)
                    
                    cv2.imwrite(str(log_dir / filename), img_log)
                    logger.info(f"📸 Log visual guardado en: {log_dir / filename}")
                except Exception as e_log:
                    logger.warning(f"No se pudo guardar el log visual OCR: {e_log}")

                if best_match:
                    logger.info(f"✅ OCR Match final listo: '{best_match['text']}'")
                    
                    # Coordenadas relativas a pantalla completa
                    screen_x = region_x + int(best_match['center']['x'])
                    screen_y = region_y + int(best_match['center']['y'])
                    
                    # Clic humanizado en el texto OCR
                    self.humanized_click(screen_x, screen_y)
                    logger.info(f"✅ Clic humanizado en texto OCR realizado en ({screen_x}, {screen_y})")
                else:
                    logger.warning(f"❌ No se encontró '{patologia_detectada}' en OCR ni con validación LLM")
                    if vf: vf.show_message(f"No se encontró: '{patologia_detectada}'", duration=3)
                    
            except Exception as e_ocr:
                logger.error(f"Error en paso OCR: {e_ocr}")
            finally:
                if vf: vf.hide_persistent_message("ocr")
            
            results["status"] = "SUCCESS" if results["failed"] == 0 else "PARTIAL"
            
            # PASO FINAL: Si todo salió bien, pasar a Vue PACS
            if results["status"] == "SUCCESS":
                time.sleep(1)
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
    setup_logging()
    
    automation = Automation1()
    results = automation.run()
    
    print("\n" + "="*50)
    print(f"Resultado: {results['status']}")
    print(f"Completadas: {results['completed']}/{results['total_actions']}")
    print(f"Fallidas: {results['failed']}")
    print("="*50)
    
    return 0 if results["status"] == "SUCCESS" else 1


if __name__ == "__main__":
    sys.exit(main())
