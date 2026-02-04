#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script: nemotron_tabla_medica.py
Descripción: Búsqueda de filas en tabla de exámenes médicos usando Nemotron VLM

ESTRATEGIA:
El modelo Nemotron Nano 12B v2 VL (vision-language) es experto en:
1. Comprensión de tablas y estructuras espaciales
2. Reconocimiento de terminología médica y abreviaturas
3. Matching semántico (eco = ecotomografía)
4. Extracción de datos estructurados con coordenadas exactas

VENTAJAS sobre OCR+Fuzzy:
- Entiende sinónimos médicos (eco/ecotomografía/ecografía)
- Maneja variaciones morfológicas sin fuzzy matching
- Procesa contexto visual (toda la tabla de una vez)
- Especialmente diseñado para OCRBench tasks
"""

import sys
import logging
import json
import base64
import cv2
import pyautogui
import numpy as np
import requests
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from utils.logging_setup import setup_logging
except:
    # Fallback si no existe
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ════════════════════════════════════════════════════════════════════════════

OPENROUTER_API_KEY = "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"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Modelo Nemotron (GRATIS en OpenRouter)
MODEL_ID = "nvidia/nemotron-nano-12b-v2-vl:free"

# ════════════════════════════════════════════════════════════════════════════
# CLASE PRINCIPAL
# ════════════════════════════════════════════════════════════════════════════

class BusquedaNemotronTabla:
    """
    Búsqueda de filas en tabla de exámenes médicos usando vision-language model.
    """
    
    def __init__(self):
        """Inicializa el buscador con configuraciones."""
        self.region = (190, 70, 1900, 650)  # ROI para captura
        self.openrouter_key = OPENROUTER_API_KEY
        self.model = MODEL_ID
        
        # Estado de búsqueda
        self.ultima_imagen_path = None
        self.ultima_respuesta_vlm = None
        
    def get_db_targets(self) -> Tuple[Optional[str], Optional[datetime]]:
        """Obtiene diagnóstico y fecha desde la base de datos."""
        if not HAS_MYSQL:
            logger.error("No hay driver de MySQL instalado.")
            return None, None

        try:
            conn = mysql.connector.connect(
                host='localhost',
                user='root',
                password='',
                database='ris'
            )
            cursor = conn.cursor()
            
            query = """
            SELECT SUBSTRING_INDEX(diagnostico, '\n', 1) AS examen, date(fecha_agendada) as fecha
            FROM ris.registro_acciones
            WHERE estado = 'En Proceso'
            LIMIT 1;
            """
            cursor.execute(query)
            result = cursor.fetchone()
            conn.close()

            if result:
                examen = result[0]
                fecha = result[1]
                logger.info(f"✓ Targets de DB - Diagnóstico: '{examen}', Fecha: '{fecha}'")
                return examen, fecha
            else:
                logger.warning("⚠️ No se encontraron registros 'En Proceso' en la BBDD.")
                return None, None
        except Exception as e:
            logger.error(f"❌ Error consultando BBDD: {e}")
            return None, None

    def capture_region(self) -> np.ndarray:
        """
        Captura la región especificada de la pantalla.
        
        Returns:
            np.ndarray: Imagen en formato BGR (OpenCV)
        """
        logger.info(f"📸 Capturando región: {self.region}")
        
        screenshot = pyautogui.screenshot(region=self.region)
        img_np = np.array(screenshot)
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
        
        # Guardar para debug
        debug_path = Path(__file__).parent / "debug_capture_nemotron.png"
        cv2.imwrite(str(debug_path), img_bgr)
        self.ultima_imagen_path = str(debug_path)
        
        logger.info(f"✓ Imagen capturada y guardada en: {debug_path}")
        return img_bgr

    def encode_image_to_base64(self, img_bgr: np.ndarray) -> str:
        """
        Codifica imagen OpenCV a base64 para enviar a OpenRouter.
        
        Args:
            img_bgr: Imagen en formato BGR
            
        Returns:
            str: Imagen codificada en base64
        """
        _, buffer = cv2.imencode('.png', img_bgr)
        img_base64 = base64.b64encode(buffer).decode('utf-8')
        logger.debug(f"✓ Imagen codificada a base64 ({len(img_base64)} chars)")
        return img_base64

    def build_prompt(self, target_examen: str, target_fecha: str) -> str:
        """
        Construye prompt especializado en terminología médica para Nemotron.
        
        El prompt incluye:
        1. Contexto médico chileno
        2. Reglas de equivalencia de abreviaturas
        3. Instrucciones precisas de extracción
        
        Args:
            target_examen: Diagnóstico/examen a buscar
            target_fecha: Fecha a buscar (formato DD-MM-YYYY)
            
        Returns:
            str: Prompt optimizado para el VLM
        """
        
        prompt = f"""TAREA: Análisis de tabla de exámenes médicos

Eres un experto en interpretación de tablas médicas del sistema RIS (Radiology Information System) de Chile.

═══════════════════════════════════════════════════════════════════════════════

CRITERIOS DE BÚSQUEDA:

1. ESTADO: Debe decir "Examen Hecho" o variantes muy similares
   - Acepta: "Examen hecho", "EXAMEN HECHO", "Exam. Hecho", "Completado"
   
2. DIAGNÓSTICO/EXAMEN: Debe ser semánticamente equivalente a: "{target_examen}"
   
   TABLA DE EQUIVALENCIAS MÉDICAS (debes aplicar estos criterios):
   ┌─────────────────────────────────────────────────────────────────────┐
   │ ABREVIATURAS COMUNES:                                               │
   │ - "eco" / "ecografia" / "ecotomografia" ↔ SON LO MISMO             │
   │ - "rx" / "radiografia" / "radiografía" ↔ SON LO MISMO              │
   │ - "tac" / "tom" / "tomografia" / "scanner" ↔ SON LO MISMO          │
   │ - "rm" / "resonancia" / "rnm" ↔ SON LO MISMO                       │
   │ - "eco doppler" / "ecografia doppler" ↔ SON LO MISMO               │
   │                                                                      │
   │ ANATOMÍA (lateralidad):                                             │
   │ - "derecha" = "der" = "dcha" = "D" = "derech"                      │
   │ - "izquierda" = "izq" = "izda" = "I" = "izquierdo"                 │
   │ - "bilateral" = "bil" = "ambos lados"                              │
   │                                                                      │
   │ IGNORAR:                                                             │
   │ - Diferencias en artículos: "de", "del", "de la", "de los"         │
   │ - Espaciado y puntuación                                            │
   │ - Mayúsculas/minúsculas                                             │
   │ - Orden de palabras (ej: "mano derecha" vs "derecha mano")          │
   └─────────────────────────────────────────────────────────────────────┘
   
   EJEMPLOS DE COINCIDENCIAS:
   - "eco de mano derecha" ≈ "ecotomografia de mano derecha" ✓
   - "rx torax AP" ≈ "radiografia de tórax AP" ✓
   - "tac abdomen" ≈ "tomografia computarizada abdomen" ✓
   - "eco doppler carótida" ≈ "ecografia doppler arteria carotida" ✓
   
3. FECHA: Debe ser exactamente: {target_fecha}
   - Acepta formatos: DD-MM-YYYY, DD/MM/YYYY, DD.MM.YYYY
   - Variaciones de día/mes/año en distinto orden

═══════════════════════════════════════════════════════════════════════════════

INSTRUCCIONES DE EXTRACCIÓN:

Analiza la tabla completa y:

1. Identifica la fila que cumple TODOS los tres criterios simultáneamente
2. Localiza el CENTRO DE LA FILA (punto medio en eje Y, centro en eje X)
3. Las coordenadas deben ser RELATIVAS a la imagen capturada (no a pantalla)

RESPUESTA (SOLO JSON, sin texto adicional):

{{
  "encontrada": true|false,
  "fila_indice": <numero del renglón encontrado o null>,
  "texto_estado": "<texto exacto que encontraste en estado>",
  "texto_examen": "<texto exacto que encontraste en diagnóstico>",
  "texto_fecha": "<texto exacto que encontraste en fecha>",
  "coordenada_x": <numero entero>,
  "coordenada_y": <numero entero>,
  "confianza": <0.0 a 1.0>,
  "razonamiento": "<explicación breve de por qué coincide>"
}}

Si no encuentras fila que cumpla los tres criterios, devuelve encontrada=false.

═══════════════════════════════════════════════════════════════════════════════
"""
        
        return prompt

    def call_nemotron(self, prompt: str, img_base64: str) -> Optional[Dict]:
        """
        Realiza llamada a Nemotron via OpenRouter API.
        
        Args:
            prompt: Prompt especializado
            img_base64: Imagen codificada en base64
            
        Returns:
            Dict: Respuesta parseada del modelo, o None si hay error
        """
        
        logger.info(f"🤖 Enviando request a Nemotron ({self.model})...")
        
        try:
            response = requests.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.openrouter_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/rcarcamoc/scripts",  # Buena práctica
                    "X-Title": "Nemotron Tabla Médica"
                },
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "RESPUESTA DIRECTA REQUERIDA. Analiza la imagen y devuelve ÚNICAMENTE el JSON solicitado. NO incluyas razonamiento, comentarios ni explicaciones.\n\n" + prompt
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{img_base64}"
                                    }
                                }
                            ]
                        }
                    ],
                    "temperature": 0.0,
                    "max_tokens": 2000,
                },
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            if 'choices' not in result or not result['choices']:
                logger.error("❌ La respuesta de OpenRouter no contiene 'choices'")
                return None
                
            # Extraer contenido
            content = result['choices'][0]['message'].get('content', '')
            
            # Si content es vacío, intentar tomar de 'reasoning' (algunos modelos divagan ahí)
            if not content and 'reasoning' in result['choices'][0]['message']:
                reasoning = result['choices'][0]['message']['reasoning']
                if reasoning:
                    content = reasoning
            
            if not content:
                logger.warning("⚠️ El modelo devolvió una respuesta vacía.")
                return None

            # 1. Intento directo de parseo JSON
            try:
                # Limpiar posibles bloques de código markdown
                clean_content = re.sub(r'```(?:json)?\s*(\{.*?\})\s*```', r'\1', content, flags=re.DOTALL)
                if clean_content == content:
                    # Si no hubo bloques, intentar buscar el primer { y el último }
                    json_match = re.search(r'(\{.*\})', content, re.DOTALL)
                    clean_content = json_match.group(1) if json_match else content
                
                parsed = json.loads(clean_content)
                self.ultima_respuesta_vlm = parsed
                return parsed
            except Exception:
                logger.warning("⚠️ No se pudo parsear como JSON puro. Usando extracción robusta por Regex...")

            # 2. Extracción Robusta por Regex (Fallback)
            # Este método extrae campo por campo, permitiendo recuperar datos de JSON parciales o mal formados
            extracted = {
                "encontrada": False,
                "fila_indice": None,
                "texto_estado": "",
                "texto_examen": "",
                "texto_fecha": "",
                "coordenada_x": None,
                "coordenada_y": None,
                "confianza": 0.0,
                "razonamiento": ""
            }

            # Regex para cada campo
            patterns = {
                "encontrada": r'"encontrada":\s*(true|false)',
                "fila_indice": r'"fila_indice":\s*(null|\d+)',
                "texto_estado": r'"texto_estado":\s*"([^"]*)"',
                "texto_examen": r'"texto_examen":\s*"([^"]*)"',
                "texto_fecha": r'"texto_fecha":\s*"([^"]*)"',
                "coordenada_x": r'"coordenada_x":\s*(\d+)',
                "coordenada_y": r'"coordenada_y":\s*(\d+)',
                "confianza": r'"confianza":\s*([0-9.]+)',
                "razonamiento": r'"razonamiento":\s*"([^"]*)"'
            }

            found_any = False
            for key, pattern in patterns.items():
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    val = match.group(1)
                    if key == "encontrada":
                        extracted[key] = val.lower() == "true"
                    elif key == "fila_indice":
                        extracted[key] = int(val) if val.isdigit() else None
                    elif key in ["coordenada_x", "coordenada_y"]:
                        extracted[key] = int(val)
                    elif key == "confianza":
                        extracted[key] = float(val)
                    else:
                        extracted[key] = val
                    found_any = True

            if found_any:
                logger.info("✓ Datos extraídos exitosamente mediante Regex")
                self.ultima_respuesta_vlm = extracted
                return extracted
            
            logger.error(f"❌ Falló toda extracción de la respuesta.")
            logger.error(f"Respuesta cruda del modelo:\n{content}")
            return None
                
        except requests.exceptions.Timeout:
            logger.error("❌ Timeout en request a OpenRouter (>30s)")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error en request: {e}")
            return None
        except KeyError as e:
            logger.error(f"❌ Error parsing response: {e}")
            logger.debug(f"Response completa: {result}")
            return None

    def execute(self) -> bool:
        """
        Ejecuta búsqueda completa en tabla de exámenes.
        
        Returns:
            bool: True si encontró y ejecutó acción, False si no
        """
        
        logger.info("\n" + "="*80)
        logger.info("🔍 BÚSQUEDA DE FILA EN TABLA MÉDICA - NEMOTRON VLM")
        logger.info("="*80 + "\n")
        
        # PASO 1: Obtener targets de BD
        logger.info("PASO 1: Obtener criterios de búsqueda")
        logger.info("-" * 80)
        
        target_examen, target_fecha_obj = self.get_db_targets()
        
        if not target_examen or not target_fecha_obj:
            logger.error("❌ No se pudieron obtener targets de la BD")
            return False
        
        target_fecha_str = target_fecha_obj.strftime("%d-%m-%Y")
        logger.info(f"✓ Examen a buscar: '{target_examen}'")
        logger.info(f"✓ Fecha a buscar: '{target_fecha_str}'\n")
        
        # PASO 2: Capturar pantalla
        logger.info("PASO 2: Capturar región de tabla")
        logger.info("-" * 80)
        
        img_bgr = self.capture_region()
        if img_bgr is None:
            logger.error("❌ Error capturando pantalla")
            return False
        
        logger.info(f"✓ Imagen capturada: {img_bgr.shape}\n")
        
        # PASO 3: Codificar imagen
        logger.info("PASO 3: Codificar imagen para API")
        logger.info("-" * 80)
        
        img_base64 = self.encode_image_to_base64(img_bgr)
        logger.info(f"✓ Imagen codificada ({len(img_base64)} caracteres base64)\n")
        
        # PASO 4: Construir prompt
        logger.info("PASO 4: Construir prompt especializado")
        logger.info("-" * 80)
        
        prompt = self.build_prompt(target_examen, target_fecha_str)
        logger.debug(f"Prompt construido ({len(prompt)} caracteres)")
        logger.info("✓ Prompt listo\n")
        
        # PASO 5: Llamar a Nemotron
        logger.info("PASO 5: Llamar a Nemotron VLM")
        logger.info("-" * 80)
        
        response = self.call_nemotron(prompt, img_base64)
        
        if not response:
            logger.error("❌ Error al procesar respuesta de Nemotron")
            return False
        
        logger.info(f"✓ Respuesta recibida\n")
        
        # PASO 6: Procesar respuesta
        logger.info("PASO 6: Procesar resultado")
        logger.info("-" * 80)
        
        if not response.get('encontrada'):
            logger.warning(f"⚠️ Nemotron no encontró fila con los criterios especificados")
            logger.info(f"   Razonamiento: {response.get('razonamiento', 'N/A')}")
            return False
        
        # Extraer coordenadas
        coord_x = response.get('coordenada_x')
        coord_y = response.get('coordenada_y')
        confianza = response.get('confianza', 0)
        
        # Validar que tenemos lo necesario
        if coord_x is None or coord_y is None:
            logger.error("❌ La respuesta del modelo no contiene coordenadas ('coordenada_x', 'coordenada_y')")
            logger.debug(f"JSON recibido: {response}")
            return False
        
        logger.info(f"✅ FILA ENCONTRADA")
        logger.info(f"   Estado: '{response.get('texto_estado')}'")
        logger.info(f"   Examen: '{response.get('texto_examen')}'")
        logger.info(f"   Fecha: '{response.get('texto_fecha')}'")
        logger.info(f"   Confianza: {confianza:.0%}")
        logger.info(f"   Coordenadas (imagen): ({coord_x}, {coord_y})\n")
        
        if confianza < 0.6:
            logger.warning(f"⚠️ Confianza baja ({confianza:.0%}). Proceder con cautela.")
        
        # PASO 7: Convertir a coordenadas de pantalla y ejecutar click
        logger.info("PASO 7: Ejecutar acciones de mouse")
        logger.info("-" * 80)
        
        # Las coordenadas vienen relativas a la imagen, convertir a pantalla
        screen_x = int(self.region[0] + coord_x)
        screen_y = int(self.region[1] + coord_y)
        
        logger.info(f"📍 Coordenadas pantalla: ({screen_x}, {screen_y})")
        logger.info(f"🖱️ Realizando click derecho...")
        
        pyautogui.moveTo(screen_x, screen_y, duration=0.5)
        pyautogui.rightClick()
        
        logger.info(f"✓ Click derecho ejecutado")
        
        # Esperar a que aparezca menú
        import time
        time.sleep(0.5)
        
        # Click en opción (offset aproximado)
        logger.info(f"🖱️ Realizando click izquierdo en opción...")
        pyautogui.click(screen_x + 100, screen_y + 194)
        
        logger.info(f"✓ Click izquierdo ejecutado\n")
        
        logger.info("="*80)
        logger.info("✅ PROCESO COMPLETADO EXITOSAMENTE")
        logger.info("="*80 + "\n")
        
        return True


# ════════════════════════════════════════════════════════════════════════════
# FUNCIÓN PRINCIPAL
# ════════════════════════════════════════════════════════════════════════════

def main():
    """Función principal."""
    try:
        setup_logging()
    except:
        pass
    
    logger.info("\n" + "🚀 "*40)
    logger.info("Iniciando búsqueda con Nemotron Nano 12B v2 VL")
    logger.info("🚀 "*40 + "\n")
    
    buscador = BusquedaNemotronTabla()
    
    try:
        resultado = buscador.execute()
        
        if resultado:
            print("\n✅ Row Found and Clicked")
            sys.exit(0)
        else:
            print("\n❌ Row Not Found")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.info("\n\n⚠️ Proceso interrumpido por usuario")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"❌ Error no manejado: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
