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

            # Intervención manual tras primer clic: Confirmación de "No"
            time.sleep(2)
            try:
                logger.info("Buscando elemento 'No'...")
                element_no = self.main_window.child_window(title='No', control_type='ListItem')
                
                if element_no.exists(timeout=3):
                    rect = element_no.rectangle()
                    self.humanized_click(rect.mid_point().x, rect.mid_point().y)
                else:
                    raise Exception("Elemento 'No' no encontrado")
                
                # Pausa tras el clic para que se vea la selección
                time.sleep(0.5)
                results["completed"] += 1
                logger.info("✅ clic humanizado en 'No' exitoso")
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
