"""
Script para detectar patologías críticas en diagnósticos de texto libre
y actualizar la tabla ris.registro_acciones con los resultados.

Utiliza ÚNICAMENTE análisis semántico con LLM (OpenRouter/DeepSeek).
"""

import pandas as pd
import mysql.connector
import unicodedata
import re
import requests
import json
import logging
import os
from dotenv import load_dotenv
from typing import Tuple, Optional, List
from datetime import datetime
import sys
import concurrent.futures
import time

# Agregar al sys.path para imports globales
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from utils.telegram_manager import enviar_alerta_todos
from utils.llm_config import (
    OPENROUTER_BASE_URL, LLM_MODELS, LLM_DEFAULT_TEMPERATURE, 
    LLM_DEFAULT_MAX_TOKENS, LLM_DEFAULT_TIMEOUT, get_llm_request_params, 
    get_models_for_context
)

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

DB_CONFIG = {
    'user': 'root',
    'password': '',
    'host': 'localhost',
    'database': 'ris'
}

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    logger.error("OPENROUTER_API_KEY no está configurada en el archivo .env")
    raise ValueError("OPENROUTER_API_KEY no está configurada")

# Usar exclusivamente modelos especializados para detección de patología (>= 30B / reasoning)
MODELS = get_models_for_context('deteccion_patologia')

# Configuración de concurrencia y reintentos para LLM
MAX_WORKERS = 3
MODELS_TO_USE = 3  # Tomar solo los primeros 3 modelos
MAX_RETRIES = 1
RETRY_DELAY = 2  # Segundos a esperar antes de reintentar
DELAY_BETWEEN_WORKERS = 1.0  # Tiempo en segundos entre el inicio de cada worker

# ============================================================================
# MATRIZ DETERMINISTA DE COMPATIBILIDAD ANATÓMICA (FILTRO DE SEGURIDAD 0 ms)
# ============================================================================

REGLAS_ANATOMICAS = {
    # 1. Neuroaxial / Columna / Médula Espinal
    "Compresión medular": {
        "terminos_permitidos": ["columna", "medul", "raquis", "cervical", "dorsal", "lumbar", "sacr", "tecal", "cordon medular", "canal espinal"],
        "terminos_prohibidos": ["tobillo", "pie", "rodilla", "pierna", "mano", "muneca", "codo", "hombro", "brazo", "antebrazo", "tendon de aquiles", "calcaneo"]
    },
    "Fractura de columna como primer hallazgo (trauma agudo)": {
        "terminos_permitidos": ["columna", "raquis", "cervical", "dorsal", "lumbar", "sacr", "vertebra"],
        "terminos_prohibidos": ["tobillo", "pie", "rodilla", "mano", "muneca", "craneo", "cerebro", "torax", "abdomen"]
    },
    # 2. Intracraneal / Cabeza / Encéfalo
    "AVE agudo o en evolución": {
        "terminos_permitidos": ["cerebr", "crane", "encefal", "cabeza", "angio cerebro", "seno venoso", "carotid"],
        "terminos_prohibidos": ["tobillo", "pie", "rodilla", "mano", "muneca", "abdomen", "pelvis", "torax", "columna"]
    },
    "Hematoma subdural, lobar hemorragia subaracnoidea": {
        "terminos_permitidos": ["cerebr", "crane", "encefal", "cabeza", "subdural", "subaracnoidea"],
        "terminos_prohibidos": ["tobillo", "pie", "rodilla", "mano", "abdomen", "pelvis", "torax"]
    },
    "Hipertensión Endocraneana HTE": {
        "terminos_permitidos": ["cerebr", "crane", "encefal", "cabeza"],
        "terminos_prohibidos": ["tobillo", "pie", "rodilla", "mano", "abdomen", "pelvis"]
    },
    "Trombosis venosa cerebral": {
        "terminos_permitidos": ["cerebr", "crane", "encefal", "seno venoso"],
        "terminos_prohibidos": ["tobillo", "pie", "rodilla", "mano", "abdomen"]
    },
    "Absceso cerebral": {
        "terminos_permitidos": ["cerebr", "crane", "encefal", "cabeza"],
        "terminos_prohibidos": ["tobillo", "pie", "rodilla", "mano", "abdomen", "torax"]
    },
    "Encefalitis": {
        "terminos_permitidos": ["cerebr", "crane", "encefal"],
        "terminos_prohibidos": ["tobillo", "pie", "rodilla", "mano", "abdomen"]
    },
    "Meningitis": {
        "terminos_permitidos": ["cerebr", "crane", "encefal", "mening", "columna"],
        "terminos_prohibidos": ["tobillo", "pie", "rodilla", "mano"]
    },
    "Hidrocefalia": {
        "terminos_permitidos": ["cerebr", "crane", "encefal", "cabeza", "ventricular"],
        "terminos_prohibidos": ["tobillo", "pie", "rodilla", "mano", "abdomen"]
    },
    "Tumor cerebral s/edema HTE": {
        "terminos_permitidos": ["cerebr", "crane", "encefal", "cabeza"],
        "terminos_prohibidos": ["tobillo", "pie", "rodilla", "mano", "abdomen"]
    },
    "Fractura de cráneo como primer hallazgo (trauma agudo)": {
        "terminos_permitidos": ["crane", "cabeza", "facial", "macizo facial", "calota", "orbita"],
        "terminos_prohibidos": ["tobillo", "pie", "rodilla", "columna", "pelvis", "abdomen"]
    },
    "Disección carotídea y/o vertebral": {
        "terminos_permitidos": ["carotid", "vertebral", "cuello", "cervical", "angio cuello"],
        "terminos_prohibidos": ["tobillo", "pie", "rodilla", "mano", "abdomen"]
    },
    "Empiema dural": {
        "terminos_permitidos": ["cerebr", "crane", "encefal", "columna", "dural", "medul"],
        "terminos_prohibidos": ["tobillo", "pie", "rodilla", "mano"]
    },
    # 3. Abdomen y Pelvis
    "Apendicitis aguda": {
        "terminos_permitidos": ["abdomen", "pelvis", "fosa iliaca", "apendic", "ciego"],
        "terminos_prohibidos": ["tobillo", "pie", "rodilla", "mano", "craneo", "cerebro", "torax", "cuello"]
    },
    "Colecistitis aguda": {
        "terminos_permitidos": ["abdomen", "vesicula", "biliar", "hipocondrio derecho", "hepato"],
        "terminos_prohibidos": ["tobillo", "pie", "rodilla", "mano", "craneo", "cerebro", "torax"]
    },
    "Coledocolitiasis c/fiebre": {
        "terminos_permitidos": ["abdomen", "coledoco", "biliar", "colangio", "hepato"],
        "terminos_prohibidos": ["tobillo", "pie", "rodilla", "craneo", "torax"]
    },
    "Pancreatitis aguda": {
        "terminos_permitidos": ["abdomen", "pancreas", "peripancreatic"],
        "terminos_prohibidos": ["tobillo", "pie", "rodilla", "mano", "craneo"]
    },
    "Diverticulitis": {
        "terminos_permitidos": ["abdomen", "pelvis", "colon", "diverticul", "sigmoides"],
        "terminos_prohibidos": ["tobillo", "pie", "rodilla", "mano", "craneo", "torax"]
    },
    "Isquemia mesentérica": {
        "terminos_permitidos": ["abdomen", "mesenteric", "angiotac abdomen", "intestino"],
        "terminos_prohibidos": ["tobillo", "pie", "rodilla", "mano", "craneo"]
    },
    "Neumo o hemoperitoneo": {
        "terminos_permitidos": ["abdomen", "pelvis", "peritone", "subfrenico"],
        "terminos_prohibidos": ["tobillo", "pie", "craneo", "mano"]
    },
    "Obstrucción intestinal": {
        "terminos_permitidos": ["abdomen", "pelvis", "intestino", "colon", "ileon"],
        "terminos_prohibidos": ["tobillo", "pie", "rodilla", "mano", "craneo"]
    },
    "Invaginación intestinal": {
        "terminos_permitidos": ["abdomen", "pelvis", "intestino", "ileon"],
        "terminos_prohibidos": ["tobillo", "pie", "rodilla", "mano", "craneo"]
    },
    "Neumatosis portal": {
        "terminos_permitidos": ["abdomen", "portal", "hepato", "mesenteric"],
        "terminos_prohibidos": ["tobillo", "pie", "craneo", "mano"]
    },
    "Ascitis": {
        "terminos_permitidos": ["abdomen", "pelvis", "peritone"],
        "terminos_prohibidos": ["tobillo", "pie", "craneo", "mano"]
    },
    "Colección subfrénica": {
        "terminos_permitidos": ["abdomen", "subfrenic", "diafragm"],
        "terminos_prohibidos": ["tobillo", "pie", "mano", "craneo"]
    },
    "Absceso psoas": {
        "terminos_permitidos": ["abdomen", "psoas", "pelvis", "retroperitone", "lumbar"],
        "terminos_prohibidos": ["tobillo", "pie", "mano", "craneo"]
    },
    "Fractura de pelvis como primer hallazgo (trauma agudo)": {
        "terminos_permitidos": ["pelvis", "cadera", "femur", "acetabul", "pubis", "iliac", "trocanter"],
        "terminos_prohibidos": ["tobillo", "pie", "mano", "muneca", "craneo", "torax"]
    },
    "Embarazo feto sin latido": {
        "terminos_permitidos": ["obstetr", "embarazo", "pelvis", "utero", "transvaginal", "fetal"],
        "terminos_prohibidos": ["tobillo", "pie", "mano", "craneo", "torax"]
    },
    "Embarazo tubario/ovárico": {
        "terminos_permitidos": ["obstetr", "embarazo", "pelvis", "utero", "transvaginal", "anexo", "ovario", "trompa"],
        "terminos_prohibidos": ["tobillo", "pie", "mano", "craneo", "torax"]
    },
    "Torsión ovárica o testicular": {
        "terminos_permitidos": ["pelvis", "ovario", "escrot", "testicul", "transvaginal", "funicular"],
        "terminos_prohibidos": ["tobillo", "pie", "mano", "craneo", "torax"]
    },
    # 4. Tórax y Pulmón
    "Neumotórax a tensión": {
        "terminos_permitidos": ["torax", "pulmon", "pleur"],
        "terminos_prohibidos": ["tobillo", "pie", "rodilla", "mano", "craneo"]
    },
    "Hemotórax": {
        "terminos_permitidos": ["torax", "pulmon", "pleur"],
        "terminos_prohibidos": ["tobillo", "pie", "rodilla", "mano", "craneo"]
    },
    "Derrame pleural": {
        "terminos_permitidos": ["torax", "pulmon", "pleur"],
        "terminos_prohibidos": ["tobillo", "pie", "rodilla", "mano", "craneo"]
    },
    "Neumonía": {
        "terminos_permitidos": ["torax", "pulmon", "consolidacion", "condensacion"],
        "terminos_prohibidos": ["tobillo", "pie", "rodilla", "mano", "craneo"]
    },
    "TEP tromboembolismo pulmonar": {
        "terminos_permitidos": ["torax", "pulmon", "angiotac pulmonar", "arteria pulmonar"],
        "terminos_prohibidos": ["tobillo", "pie", "rodilla", "mano", "craneo"]
    },
    # 5. Mama
    "Imágenes sospechosas de lesión maligna Birads 4-5": {
        "terminos_permitidos": ["mama", "mamari", "mamograf", "axila", "birads"],
        "terminos_prohibidos": ["tobillo", "pie", "rodilla", "craneo", "abdomen"]
    }
}

# ============================================================================
# FUNCIONES UTILITARIAS Y FILTRO ANATÓMICO
# ============================================================================

def normalizar_texto(texto: str, mantener_puntuacion: bool = False) -> str:
    """Normaliza texto: minúsculas, sin acentos, espacios limpios."""
    if not isinstance(texto, str):
        return ""
    
    texto_nfd = unicodedata.normalize('NFD', texto)
    texto_sin_tildes = ''.join(c for c in texto_nfd if unicodedata.category(c) != 'Mn')
    texto_limpio = re.sub(r'\s+', ' ', texto_sin_tildes.lower().strip())
    if not mantener_puntuacion:
        texto_limpio = re.sub(r'[.,;:]+', '', texto_limpio)
    
    return texto_limpio

def _buscar_en_lista_normalizado(texto: str, lista_patologias: List[str]) -> Optional[str]:
    """Busca texto en la lista comparando versiones normalizadas."""
    texto_norm = normalizar_texto(texto)
    for p_orig in lista_patologias:
        if normalizar_texto(p_orig) == texto_norm:
            return p_orig
    return None

def es_anatomicamente_compatible(patologia: str, examen: str, diagnostico: str) -> Tuple[bool, str]:
    """
    Verifica de manera determinista (0 ms) si la patología detectada es anatómicamente compatible
    con el tipo de examen y el texto diagnóstico. Retorna (es_compatible, motivo).
    """
    if not patologia:
        return True, "Sin patología"
        
    p_norm = normalizar_texto(patologia)
    regla = None
    for p_key, r in REGLAS_ANATOMICAS.items():
        if normalizar_texto(p_key) == p_norm:
            regla = r
            break
            
    if not regla:
        return True, "Sin restricción anatómica estricta"
        
    examen_norm = normalizar_texto(examen or "")
    texto_evaluar = normalizar_texto(f"{examen or ''} {diagnostico or ''}")
    
    # 1. Verificar si el examen corresponde explícitamente a un territorio prohibido
    for prohibido in regla.get("terminos_prohibidos", []):
        prohibido_norm = normalizar_texto(prohibido)
        if prohibido_norm in examen_norm:
            tiene_permitido_en_examen = any(
                normalizar_texto(perm) in examen_norm for perm in regla.get("terminos_permitidos", [])
            )
            if not tiene_permitido_en_examen:
                return False, f"Incompatible: El examen '{examen}' pertenece a territorio corporal prohibido ('{prohibido}') para la patología '{patologia}'."

    # 2. Verificar que al menos uno de los términos permitidos esté presente en el texto
    tiene_permitido = any(normalizar_texto(perm) in texto_evaluar for perm in regla.get("terminos_permitidos", []))
    if not tiene_permitido:
        return False, f"Incompatible: No se encontró ningún término anatómico requerido {regla.get('terminos_permitidos', [])} en el estudio para '{patologia}'."
        
    return True, "Compatible anatómicamente"

def conectar_bd(config: dict):
    """Establece conexión con la base de datos MySQL."""
    try:
        conn = mysql.connector.connect(
            host=config['host'],
            user=config['user'],
            password=config['password'],
            database=config['database']
        )
        logger.info("[OK] Conexion a BD establecida")
        return conn
    except Exception as e:
        logger.error(f"[ERROR] Error al conectar BD: {e}")
        raise

def cargar_datos(conn) -> Tuple[pd.DataFrame, list]:
    """Carga diagnósticos, tipo de examen y patologías de la BD."""
    logger.info("Cargando datos de BD...")

    query_acciones = """
    SELECT id, examen, diagnostico
    FROM ris.registro_acciones
    WHERE estado = 'En Proceso'
    """

    query_patologias = """
    SELECT nombre_patologia
    FROM ris.patologias_criticas
    """

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(query_acciones)
        filas_acciones = cursor.fetchall()
        df_acciones = pd.DataFrame(filas_acciones) if filas_acciones else pd.DataFrame(columns=['id', 'examen', 'diagnostico'])

        cursor.execute(query_patologias)
        filas_pat = cursor.fetchall()
        patologias = [r['nombre_patologia'] for r in filas_pat]
        cursor.close()

        logger.info(f"[OK] {len(df_acciones)} registros cargados")
        logger.info(f"[OK] {len(patologias)} patologias criticas cargadas")

        return df_acciones, patologias

    except Exception as e:
        logger.error(f"[ERROR] Error al cargar datos: {e}")
        raise

# ============================================================================
# INTEGRACIÓN LLM (OpenRouter)
# ============================================================================

def log_llm_result(id_registro: int, modelo: str, es_critica: str, patologia_detectada: Optional[str], razonamiento: str, tiempo_ms: int = 0):
    """Guarda el registro de la consulta al modelo en la base de datos."""
    try:
        import mysql.connector
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        query = """
        INSERT INTO ris.log_llm_patologias 
        (id_registro, modelo, es_critica, patologia_detectada, razonamiento, tiempo_ms)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        cursor.execute(query, (id_registro, modelo, es_critica, patologia_detectada, razonamiento, tiempo_ms))
        conn.commit()

        conn.close()
    except Exception as e:
        logger.error(f"[DB Error] No se pudo guardar el log LLM para {modelo}: {e}")

def _consultar_modelo_llm(
    id_registro: int, 
    current_model: str, 
    prompt: str, 
    lista_patologias: List[str], 
    examen: str = "", 
    diagnostico: str = "", 
    retries: int = MAX_RETRIES
) -> Optional[str]:
    """Realiza la consulta a un modelo específico con reintentos y guarda el log con filtro anatómico."""
    for intento in range(retries + 1):
        start_time = time.time()
        try:
            logger.info(f"[{current_model}] Intentando (Intento {intento + 1}/{retries + 1})...")
            base_url, target_key, provider = get_llm_request_params(current_model)
            if not target_key:
                target_key = OPENROUTER_API_KEY
            response = requests.post(
                f"{base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {target_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://rpa-framework.local"
                },
                json={
                    "model": current_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": LLM_DEFAULT_TEMPERATURE,
                    "max_tokens": LLM_DEFAULT_MAX_TOKENS,
                },
                timeout=LLM_DEFAULT_TIMEOUT
            )

            elapsed_ms = int((time.time() - start_time) * 1000)

            if response.status_code == 404:
                logger.warning(f"⚠️ [{current_model}] No encontrado (404).")
                log_llm_result(id_registro, current_model, 'error', None, "HTTP 404 - Modelo no encontrado", elapsed_ms)
                return None
            elif response.status_code == 429:
                logger.warning(f"⚠️ [{current_model}] Rate limit (429).")
                log_llm_result(id_registro, current_model, 'error', None, "HTTP 429 - Rate Limit", elapsed_ms)
                if intento < retries:
                    time.sleep(RETRY_DELAY)
                    continue
                return None

            response.raise_for_status()
            result = response.json()
            content = result['choices'][0]['message'].get('content', '')

            # Extraer JSON de la respuesta
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                patologia = data.get('patologia_detectada')
                razonamiento = data.get('razonamiento', '')

                logger.info(f"RESULTADO LLM [{current_model}] ({elapsed_ms}ms):")
                logger.info(f"  - Patología: {patologia}")
                logger.info(f"  - Razonamiento: {razonamiento}")

                if patologia:
                    p_validada = _buscar_en_lista_normalizado(patologia, lista_patologias)
                    if p_validada:
                        # ── FILTRO ANATÓMICO DETERMINISTA (0 ms) ──
                        es_compat, motivo_anat = es_anatomicamente_compatible(p_validada, examen, diagnostico)
                        if not es_compat:
                            logger.warning(f"🚫 [{current_model}] FILTRO ANATÓMICO RECHAZÓ '{p_validada}': {motivo_anat}")
                            log_llm_result(
                                id_registro, current_model, 'invalida', p_validada, 
                                f"Filtro Anatómico RECHAZÓ: {motivo_anat} | LLM razonó: {razonamiento}", 
                                elapsed_ms
                            )
                            return None

                        logger.info(f"✅ [{current_model}] VALIDACIÓN EXITOSA Y ANATÓMICAMENTE COMPATIBLE: '{p_validada}'")
                        log_llm_result(id_registro, current_model, 'si', p_validada, razonamiento, elapsed_ms)
                        return p_validada
                    else:
                        logger.warning(f"⚠️ [{current_model}] VALIDACIÓN FALLIDA: '{patologia}' no está en la lista.")
                        log_llm_result(id_registro, current_model, 'invalida', patologia, razonamiento, elapsed_ms)
                        return None

                logger.info(f"ℹ️ [{current_model}] Concluyó que NO es patología crítica.")
                log_llm_result(id_registro, current_model, 'no', None, razonamiento, elapsed_ms)
                return None
                
            # Si responde pero no hay JSON válido
            log_llm_result(id_registro, current_model, 'error', None, f"Sin JSON válido en respuesta: {content[:200]}", elapsed_ms)

        except json.JSONDecodeError as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.warning(f"⚠️ [{current_model}] Error parseando JSON: {e}.")
            log_llm_result(id_registro, current_model, 'error', None, f"JSONDecodeError: {str(e)}", elapsed_ms)
            if intento < retries:
                time.sleep(RETRY_DELAY)
                continue
            return None
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.error(f"❌ [{current_model}] Error: {e}")
            log_llm_result(id_registro, current_model, 'error', None, f"Exception: {str(e)}", elapsed_ms)
            if intento < retries:
                time.sleep(RETRY_DELAY)
                continue
            return None
            
    return None

def consultar_llm_patologia(id_registro: int, examen: str, diagnostico: str, lista_patologias: List[str]) -> Optional[str]:
    """
    Consulta a los LLMs autorizados para patología crítica si el diagnóstico corresponde a alguna de la lista.
    Envía peticiones concurrentes y evalúa con filtro anatómico y consenso seguro.
    """
    # Recargar modelos autorizados para patología crítica (>= 30B / reasoning)
    modelos_disponibles = get_models_for_context('deteccion_patologia')
    modelos_a_usar = modelos_disponibles[:MODELS_TO_USE]

    logger.info("=" * 40)
    logger.info(f"🤖 INICIANDO CONSULTA LLM ({len(modelos_a_usar)} modelos concurrentes: {modelos_a_usar})")
    logger.info("-" * 40)
    logger.info(f"ESTUDIO / EXAMEN: {examen}")
    logger.info(f"TEXTO A ANALIZAR:\n{diagnostico}")
    logger.info("-" * 40)

    lista_str = "\n".join([f"- {p}" for p in lista_patologias])

    prompt = f"""
PRINCIPIO RECTOR DE SEGURIDAD CLÍNICA:
Este sistema opera bajo el criterio de mínimo riesgo. Un falso positivo razonable 
en la misma región anatómica es preferible a un falso negativo. Sin embargo, 
NUNCA debes justificar asociaciones anatómicas físicamente imposibles o que no 
correspondan al estudio solicitado.

---

Eres un médico radiólogo auditor experto. Tu tarea es analizar un texto 
de diagnóstico radiológico e identificar si corresponde a alguna de las 
patologías críticas listadas.

ESTUDIO / TIPO DE EXAMEN SOLICITADO:
"{examen}"

DIAGNÓSTICO A ANALIZAR:
"{diagnostico}"

---

REGLA ESTRICTA DE COHERENCIA ANATÓMICA (OBLIGATORIA):
1. Una patología crítica SOLO puede asignarse si corresponde anatómicamente a la región 
   del cuerpo evaluada en el examen o a una complicación directa demostrada en dicho territorio.
2. EXCLUSIONES ANATÓMICAS TAJANTES:
   - Exámenes de extremidades periféricas (tobillo, pie, pierna, rodilla, mano, muñeca, antebrazo, codo, hombro):
     * NUNCA pueden clasificarse como patologías del Sistema Nervioso Central o Neuroaxiales 
       (ej. "Compresión medular", "AVE agudo", "Hematoma subdural", "Meningitis", "Encefalitis", "Hidrocefalia", etc.).
     * NUNCA pueden clasificarse como patologías intraabdominales o torácicas (ej. "Apendicitis", "Colecistitis", "TEP", "Neumotórax").
   - "Compresión medular" requiere afección directa del canal raquídeo o médula espinal (Columna cervical, dorsal o lumbar). 
     Una rotura de ligamento o formación quística en el tobillo/pie JAMÁS puede comprimir la médula espinal.
   - Si la patología sospechada no pertenece a la región anatómica examinada, responde OBLIGATORIAMENTE "patologia_detectada": null.

IMPORTANTE — SINÓNIMOS Y VARIANTES CLÍNICAS VÁLIDAS:
- "Fractura de cuello femoral", "fractura de cadera", "fractura de fémur proximal" 
  corresponden a "Fractura de pelvis como primer hallazgo (trauma agudo)".
- "Aneurisma de aorta abdominal" o "aneurisma ilíaco" corresponde a 
  "Disección carotídea aortica o aneurisma complicado".
- "Diverticulitis aguda" corresponde a "Diverticulitis".
- "AVE", "ACV", "infarto cerebral" corresponde a "AVE agudo o en evolución".
- "TEP", "tromboembolismo" corresponde a "TEP tromboembolismo pulmonar".
- "Hematoma subdural", "hemorragia subaracnoidea" o "hemorragia lobar" corresponde 
  a "Hematoma subdural, lobar hemorragia subaracnoidea".

LISTA DE PATOLOGÍAS CRÍTICAS:
{lista_str}

INSTRUCCIONES:
1. Analiza el tipo de examen y el significado clínico del diagnóstico completo.
2. Si el diagnóstico describe una patología de la lista que sea anatómicamente coherente 
   con la región examinada, retorna el NOMBRE EXACTO de la lista.
3. Si el diagnóstico es normal, describe lesiones benignas comunes no críticas (ej. esguince, 
   artrosis, rotura ligamentosa periférica aislada, quiste sinovial/ganglión), o si la patología 
   no corresponde a la anatomía examinada, retorna null.
4. Responde ÚNICAMENTE con un objeto JSON válido, sin texto adicional.

FORMATO DE RESPUESTA:
{{
  "patologia_detectada": "Nombre Exacto de la Lista" o null,
  "confianza": "alta" | "media" | "baja",
  "razonamiento": "Breve explicación de por qué corresponde o no"
}}
"""

    deadline = None
    resultado_final = None
    respuestas_positivas = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {}
        for index, model in enumerate(modelos_a_usar):
            if index > 0 and DELAY_BETWEEN_WORKERS > 0:
                time.sleep(DELAY_BETWEEN_WORKERS)
            future = executor.submit(
                _consultar_modelo_llm, id_registro, model, prompt, lista_patologias, examen, diagnostico
            )
            futures[future] = model
        
        try:
            while futures:
                iter_timeout = None
                if deadline is not None:
                    iter_timeout = max(0.0, deadline - time.time())
                    if iter_timeout <= 0:
                        logger.warning("⏱️ [Race] Expiró el tiempo de espera tras la primera respuesta. Cancelando hilos lentos.")
                        break

                done, not_done = concurrent.futures.wait(
                    futures.keys(),
                    timeout=iter_timeout,
                    return_when=concurrent.futures.FIRST_COMPLETED
                )

                if not done:
                    logger.warning("⏱️ [Race] Expiró el tiempo de espera (timeout) para las respuestas restantes.")
                    break

                for future in done:
                    model = futures.pop(future)
                    try:
                        resultado = future.result()
                        if resultado:
                            respuestas_positivas[model] = resultado
                            # Si es el modelo primario (meta/llama-3.2-90b-vision-instruct), corte temprano seguro
                            if model == modelos_a_usar[0]:
                                logger.info(f"🚀 CORTE TEMPRANO: El modelo primario [{model}] confirmó '{resultado}' superando el filtro anatómico.")
                                resultado_final = resultado
                                futures.clear()
                                break
                            else:
                                logger.info(f"🔍 Modelo secundario [{model}] detectó '{resultado}'.")
                                # Si ya tenemos consenso (2 o más modelos) o el primario ya terminó
                                if len(respuestas_positivas) >= 2 or not any(futures.get(f) == modelos_a_usar[0] for f in futures):
                                    resultado_final = resultado
                                    futures.clear()
                                    break

                        # Si el primer modelo respondió None, iniciamos countdown de 15s para el resto
                        if deadline is None:
                            logger.info(f"⏱️ [Race] Primera respuesta recibida de [{model}]. Iniciando countdown de 15s...")
                            deadline = time.time() + 15.0

                    except Exception as exc:
                        logger.error(f"[{model}] generó una excepción: {exc}")

        finally:
            for f in list(futures.keys()):
                f.cancel()

    if resultado_final:
        logger.info(f"🎯 PATOLOGÍA CRÍTICA FINAL DETECTADA: '{resultado_final}'")
        logger.info("=" * 40)
        return resultado_final

    logger.info("ℹ️ Ningún modelo detectó una patología crítica válida y anatómicamente compatible.")
    logger.info("=" * 40)
    return None

# ============================================================================
# LÓGICA DE DETECCIÓN
# ============================================================================

def detectar_patologia(id_registro: int, examen: str, diagnostico: str, patologias: list) -> Optional[str]:
    """Detecta patología usando modelos LLM autorizados con filtro anatómico."""
    return consultar_llm_patologia(id_registro, examen, diagnostico, patologias)

# ============================================================================
# ANÁLISIS PRINCIPAL
# ============================================================================

def analizar_diagnosticos(df_acciones: pd.DataFrame, patologias: list) -> pd.DataFrame:
    """Analiza todos los diagnósticos y detecta patologías."""
    logger.info(f"Analizando {len(df_acciones)} diagnosticos...")

    resultados = []
    for idx, row in df_acciones.iterrows():
        diag = row['diagnostico']
        examen = row.get('examen', '')
        id_reg = row['id']
        logger.info(f"Analizando ID {id_reg} - Examen: '{examen}' - Diagnóstico: '{str(diag)[:60]}...'")

        resultado = detectar_patologia(id_reg, examen, diag, patologias)
        resultados.append(resultado)

    df_acciones = df_acciones.copy()
    df_acciones['patologia_detectada'] = resultados

    detectadas = df_acciones['patologia_detectada'].notna().sum()
    no_detectadas = len(df_acciones) - detectadas

    logger.info(f"[OK] Patologias criticas detectadas: {detectadas}")
    logger.info(f"[INFO] Sin patologias criticas: {no_detectadas}")

    return df_acciones

# ============================================================================
# ACTUALIZACIÓN DE BASE DE DATOS
# ============================================================================

def actualizar_registro_acciones(conn, df_resultados: pd.DataFrame) -> None:
    """
    Actualiza la tabla ris.registro_acciones con los resultados detectados.
    Campos: patologia_critica_detectada, patologia_critica, update.
    """
    logger.info("Actualizando tabla ris.registro_acciones...")

    fecha_actual = datetime.now()
    actualizados = 0
    errores = 0

    cursor = conn.cursor()
    for idx, row in df_resultados.iterrows():
        try:
            id_registro = row['id']
            patologia = row['patologia_detectada']

            patologia_critica_flag = 'si' if pd.notna(patologia) else 'no'
            patologia_val = str(patologia) if pd.notna(patologia) else None

            query_update = """
            UPDATE ris.registro_acciones
            SET
                patologia_critica_detectada = %s,
                patologia_critica = %s,
                `update` = %s
            WHERE id = %s AND estado = 'En Proceso'
            """

            cursor.execute(
                query_update,
                (patologia_val, patologia_critica_flag, fecha_actual, int(id_registro))
            )

            actualizados += 1
            logger.info(f"  → Registro ID {id_registro} actualizado: {patologia_val if patologia_val else '[SIN PATOLOGÍA]'}")

        except Exception as e:
            logger.error(f"[ERROR] Actualizando registro ID {id_registro}: {e}")
            errores += 1

    conn.commit()
    cursor.close()

    logger.info(f"[OK] Actualizacion completada:")
    logger.info(f"  - Registros procesados: {actualizados}")
    logger.info(f"  - Errores: {errores}")

# ============================================================================
# PUNTO DE ENTRADA
# ============================================================================

def main():
    logger.info("=" * 70)
    logger.info("INICIANDO ANALISIS POR IA v3")
    logger.info("=" * 70)

    conn = None

    try:
        conn = conectar_bd(DB_CONFIG)
        df_acciones, patologias = cargar_datos(conn)

        if df_acciones.empty:
            logger.info("No hay registros para procesar.")
            return

        df_resultados = analizar_diagnosticos(df_acciones, patologias)
        actualizar_registro_acciones(conn, df_resultados)

        logger.info("\n" + "=" * 70)
        logger.info("[OK] PROCESO COMPLETADO")
        logger.info("=" * 70)

    except Exception as e:
        try:
            from utils.error_handler import handle_error_and_exit
            handle_error_and_exit("detecta_patologia_ia_v2.py", str(e))
        except Exception:
            try:
                from rpa_framework.utils.error_handler import handle_error_and_exit
                handle_error_and_exit("detecta_patologia_ia_v2.py", str(e))
            except Exception:
                logger.error(f"\n[ERROR] CRITICO: {e}")
                sys.exit(1)
    finally:
        if conn:
            try:
                conn.close()
                logger.info("[OK] Conexion cerrada")
            except Exception:
                pass


if __name__ == '__main__':
    main()
