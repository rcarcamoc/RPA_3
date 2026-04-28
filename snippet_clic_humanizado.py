import sys
import time
import logging
import threading
import tkinter as tk
from pathlib import Path
from datetime import datetime
import cv2
import numpy as np
import unicodedata
import re
import os
import requests
import json
import pyautogui
from dotenv import load_dotenv

# --- CONFIGURACIÓN INTEGRADA (Self-contained) ---
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
LLM_MODELS = [
    "google/gemini-2.0-flash-001",
    "anthropic/claude-3.0-haiku",
    "meta-llama/llama-3.1-8b-instruct"
]
LLM_DEFAULT_TEMPERATURE = 0.2
LLM_DEFAULT_MAX_TOKENS = 150
# -----------------------------------------------

try:
    from rapidfuzz import fuzz
except ImportError:
    fuzz = None

try:
    import mysql.connector
except ImportError:
    pass

# Agregar raíz del proyecto al path
sys.path.insert(0, str(Path(__file__).parent / "rpa_framework"))
sys.path.insert(0, str(Path(__file__).parent))

from pywinauto import Application, findwindows
from rpa_framework.core.executor import ActionExecutor
from rpa_framework.core.action import Action, ActionType
from rpa_framework.ocr.engine import OCREngine

load_dotenv()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Feedback visual integrado para no depender de rpa_framework.utils.visual_feedback
class VisualFeedbackLocal:
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

vf = VisualFeedbackLocal()

# Configurar logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MockAutomation:
    def __init__(self):
        self.app = None
        self.executor = None

    def stop_with_error(self, message):
        logger.error(message)
        sys.exit(1)

    def get_patologia_critica(self):
        try:
            conn = mysql.connector.connect(
                host='localhost', user='root', password='', database='ris'
            )
            cursor = conn.cursor()
            query = "SELECT patologia_critica_detectada FROM ris.registro_acciones where estado ='En Proceso' LIMIT 1"
            cursor.execute(query)
            result = cursor.fetchone()
            conn.close()
            if result and result[0]:
                logger.info(f"Target DB - Patología: '{result[0]}'")
                return result[0]
            logger.warning("No se encontró patologia_critica_detectada en DB.")
            return None
        except Exception as e:
            logger.error(f"Error consultando BD: {e}")
            return None

    def call_llm_text_verification(self, ocr_text, target_diag):
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
                    timeout=10
                )
                if response.status_code == 429: continue
                response.raise_for_status()
                content = response.json()['choices'][0]['message'].get('content', '')
                logger.info(f"Respuesta Raw LLM ({current_model}): {content[:100]}...")
                match = re.search(r'\{.*\}', content, re.DOTALL)
                if match:
                    data = json.loads(match.group(0))
                    if data.get('es_match'): return True
                    else: continue
                if "true" in content.lower() and "match" in content.lower(): return True
            except Exception as e:
                logger.warning(f"Error LLM {current_model}: {e}")
                continue
        return False

    def _robust_execute(self, action):
        return self.executor.execute(action)

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

    def run(self):
        results = {"completed": 0}

        patologia_detectada = self.get_patologia_critica()
        if not patologia_detectada:
            self.stop_with_error("No se pudo obtener patologia_critica_detectada de la base de datos.")

    # Acción 2: CLICK en resultado critico
            self.humanized_click(692, 84, is_double=True)
            results["completed"] += 1
            logger.info(f"[2/16] ✅ humanized_double_click")







        # Acción 3: CLICK en combobox resultado critico
        # Mover antes de hacer clic
        try:
            time.sleep(1)
            logger.info("Buscando y enfocando la ventana de Carestream RIS...")
            
            # Estrategia de conexión robusta con reintentos
            connected = False
            for attempt in range(1, 4):
                try:
                    logger.debug(f"Intento {attempt} de conexión a Carestream RIS...")
                    # 1. Buscar por título para obtener un handle estable
                    titulos = findwindows.find_elements(title_re=".*Carestream RIS V11.*", backend='uia')
                    
                    if titulos:
                        logger.info(f"Ventana encontrada por título: {titulos[0].name}")
                        self.app = Application(backend='uia').connect(handle=titulos[0].handle)
                    else:
                        # 2. Fallback a conectar por process path o title_re directo
                        try:
                            self.app = Application(backend='uia').connect(path="Carestream RIS.exe")
                        except:
                            self.app = Application(backend='uia').connect(title_re=".*Carestream RIS V11.*")
                    
                    # 3. Validar existencia y dar foco (específico en vez de top_window)
                    self.main_window = self.app.window(title_re=".*Carestream RIS V11.*")
                    if self.main_window.exists(timeout=5):
                        self.main_window.set_focus()
                        # A veces requiere un segundo intento o esperar un poco
                        time.sleep(0.5)
                        self.main_window.set_focus()
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

            # Acción 3: CLICK en combobox resultado critico (Alternativa 1 - Nativo)
            time.sleep(1)
            try:
                # Buscar elemento de forma precisa
                element = self.main_window.child_window(auto_id='cbxClResultadocritico1', control_type="ComboBox")
                rect = element.rectangle()
                cx, cy = rect.mid_point().x, rect.mid_point().y
                
                # Clic humanizado (incluye movimiento, círculo rojo y sostenido)
                self.humanized_click(cx, cy)
                
                results["completed"] += 1
                logger.info("[3/16] ✅ clic humanizado (Alt 1) exitoso")
            except Exception as e_click:
                logger.error(f"Error en clic nativo (Acción 3): {e_click}")
                raise e_click

            # Acción 4: CLICK en si resultado critico (Robusto)
            # Aumentamos a 2 segundos para dar tiempo a que el combo despliegue la lista
            time.sleep(2)
            try:
                logger.info("Buscando elemento 'Sí'...")
                element_si = self.main_window.child_window(name='Sí', control_type='ListItem')
                
                if element_si.exists(timeout=3):
                    rect = element_si.rectangle()
                    self.humanized_click(rect.mid_point().x, rect.mid_point().y)
                else:
                    raise Exception("Elemento 'Sí' no encontrado")
                
                # Pausa tras el clic para que se vea la selección
                time.sleep(0.5)
                results["completed"] += 1
                logger.info("[4/16] ✅ clic humanizado en 'Sí' exitoso")
            except Exception as e_si:
                logger.info("Esperando un poco más para el fallback de 'Sí'...")
                time.sleep(1)
                logger.error(f"Error en clic 'Sí': {e_si}")
                # Fallback a coordenadas
                logger.warning("Fallo en selector de 'Sí', intentando fallback por coordenadas...")
                try:
                    self.humanized_click(201, 182)
                    results["completed"] += 1
                    logger.info("[4/16] ✅ clic humanizado (fallback) exitoso")
                except Exception as e_coord:
                    logger.error(f"Fallo total en Acción 4: {e_coord}")
                    raise e_coord

            # Acción 5: CLICK (ComboBox diagnóstico) - Robusto
            time.sleep(1)
            try:
                auto_id_diag = 'cbxClCodigodiagnostico1'
                logger.info(f"Buscando ComboBox de diagnóstico ({auto_id_diag})...")
                element_diag = self.main_window.child_window(auto_id=auto_id_diag, control_type="ComboBox")
                rect = element_diag.rectangle()
                self.humanized_click(rect.mid_point().x, rect.mid_point().y)
                
                results["completed"] += 1
                logger.info("[5/16] ✅ clic humanizado en ComboBox diagnóstico exitoso")
            except Exception as e_diag:
                logger.error(f"Error en clic Acción 5: {e_diag}")
                # Fallback a coordenadas
                logger.warning("Fallo en selector de Acción 5, intentando fallback por coordenadas...")
                try:
                    self.humanized_click(612, 185)
                    results["completed"] += 1
                    logger.info("[5/16] ✅ clic humanizado (fallback) en Acción 5 exitoso")
                except Exception as e_coord5:
                    logger.error(f"Fallo total en Acción 5: {e_coord5}")
                    raise e_coord5

            # Acción Extra: Teclear "P" (ahora será la primera letra de la BD) (sin cambiar foco)
            primera_letra = patologia_detectada[0].lower()
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
                    preprocess=True, 
                    custom_config='--psm 6'
                )

                ocr_results = ocr_engine.extract_text_with_location(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))
                
                # Agrupador de palabras por filas (Eje Y) para reconstruir oraciones
                def agrupar_por_filas(results):
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
                        if not matched:
                            rows.append({'y_center': item['center']['y'], 'items': [item]})
                    
                    # Consolidación
                    rows.sort(key=lambda x: x['y_center'])
                    final_rows = []
                    if rows:
                        curr = rows[0]
                        for i in range(1, len(rows)):
                            nxt = rows[i]
                            if abs(curr['y_center'] - nxt['y_center']) < 12:
                                curr['items'].extend(nxt['items'])
                                curr['y_center'] = sum(it['center']['y'] for it in curr['items']) / len(curr['items'])
                            else:
                                final_rows.append(curr)
                                curr = nxt
                        final_rows.append(curr)
                    
                    # Crear candidatos finales (Unir texto y sacar centro promedio)
                    candidatos = []
                    for r in final_rows:
                        # Ordenar por X de izquierda a derecha
                        items_x = sorted(r['items'], key=lambda x: x['center']['x'])
                        texto_completo = " ".join([i['text'] for i in items_x])
                        # Usar el centro X del PRIMER elemento y el centro Y promedio, 
                        # o un punto en el medio de la frase
                        avg_x = sum(i['center']['x'] for i in items_x) / len(items_x)
                        candidatos.append({
                            'text': texto_completo,
                            'center': {'x': avg_x, 'y': r['y_center']},
                            'items': items_x
                        })
                    return candidatos

                lineas_ocr = agrupar_por_filas(ocr_results)

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
                    
                    # Filtramos ruido o elementos muy cortos 
                    if not found_norm or len(found_norm) < 4: continue
                    
                    # Filtro "Sub-Representación": Si lo leído en OCR es minúsculo, no sirve.
                    if len(found_norm) < len(target_norm) * 0.4: continue 
                    
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
                    logger.info("⚠️ No hubo match local >95%. Consultando LLM con los textos detectados...")
                    if vf: vf.show_persistent_message("Validando con LLM...", "llm", bg_color="#FF9800", fg_color="#000000")
                    for res in lineas_ocr:
                        ocr_text = res['text']
                        # Filtramos basurita de muy pocos caracteres
                        if len(ocr_text.strip()) < 4: continue
                        
                        logger.info(f"Analizando semántica de: '{ocr_text}'")
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

        except Exception as e:
            self.stop_with_error(f"Error: {e}")

if __name__ == "__main__":
    automation = MockAutomation()
    automation.run()
