"""
Script para detectar patologías críticas en diagnósticos de texto libre
y actualizar la tabla ris.registro_acciones con los resultados.

Utiliza ÚNICAMENTE análisis semántico con LLM (OpenRouter/DeepSeek).
"""

import pandas as pd
import sqlalchemy
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
from utils.llm_config import OPENROUTER_BASE_URL, LLM_MODELS, LLM_DEFAULT_TEMPERATURE, LLM_DEFAULT_MAX_TOKENS, LLM_DEFAULT_TIMEOUT

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

MODELS = LLM_MODELS

# Configuración de concurrencia y reintentos para LLM
MAX_WORKERS = 3
MODELS_TO_USE = 3  # Tomar solo los primeros 3 modelos
MAX_RETRIES = 1
RETRY_DELAY = 2  # Segundos a esperar antes de reintentar
DELAY_BETWEEN_WORKERS = 1.0  # Tiempo en segundos entre el inicio de cada worker

# ============================================================================
# FUNCIONES UTILITARIAS
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



def conectar_bd(config: dict) -> sqlalchemy.Engine:
    """Establece conexión con la base de datos MySQL."""
    connection_string = (
        f"mysql+mysqlconnector://{config['user']}:{config['password']}"
        f"@{config['host']}/{config['database']}"
    )
    try:
        engine = sqlalchemy.create_engine(connection_string)
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text("SELECT 1"))
        logger.info("[OK] Conexion a BD establecida")
        return engine
    except Exception as e:
        logger.error(f"[ERROR] Error al conectar BD: {e}")
        raise


def cargar_datos(engine: sqlalchemy.Engine) -> Tuple[pd.DataFrame, list]:
    """Carga diagnósticos y patologías de la BD."""
    logger.info("Cargando datos de BD...")

    query_acciones = """
    SELECT id, diagnostico
    FROM ris.registro_acciones
    WHERE estado = 'En Proceso'
    """

    query_patologias = """
    SELECT nombre_patologia
    FROM ris.patologias_criticas
    """

    try:
        df_acciones = pd.read_sql(query_acciones, engine)
        df_patologias = pd.read_sql(query_patologias, engine)

        logger.info(f"[OK] {len(df_acciones)} diagnosticos cargados")
        logger.info(f"[OK] {len(df_patologias)} patologias criticas cargadas")

        return df_acciones, df_patologias['nombre_patologia'].tolist()

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

def _consultar_modelo_llm(id_registro: int, current_model: str, prompt: str, lista_patologias: List[str], retries: int = MAX_RETRIES) -> Optional[str]:
    """Realiza la consulta a un modelo específico con reintentos y guarda el log."""
    for intento in range(retries + 1):
        start_time = time.time()
        try:
            logger.info(f"[{current_model}] Intentando (Intento {intento + 1}/{retries + 1})...")
            response = requests.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
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
                        logger.info(f"✅ [{current_model}] VALIDACIÓN EXITOSA: '{p_validada}'")
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

def consultar_llm_patologia(id_registro: int, diagnostico: str, lista_patologias: List[str]) -> Optional[str]:
    """
    Consulta al LLM si el diagnóstico corresponde a alguna patología.
    Envía peticiones concurrentes a los primeros N modelos y retorna rápida si alguno aprueba.
    """
    logger.info("=" * 40)
    logger.info(f"🤖 INICIANDO CONSULTA LLM ({MODELS_TO_USE} modelos concurrentes)")
    logger.info("-" * 40)
    logger.info(f"TEXTO A ANALIZAR:\n{diagnostico}")
    logger.info("-" * 40)

    lista_str = "\n".join([f"- {p}" for p in lista_patologias])

    prompt = f"""
PRINCIPIO RECTOR DE SEGURIDAD CLÍNICA:
Este sistema opera bajo el criterio de mínimo riesgo. Un falso positivo 
(notificar algo que no era crítico) es SIEMPRE preferible a un falso negativo 
(no notificar algo que sí era crítico). Ante cualquier duda, clasifica como 
patología crítica.

---

Eres un experto médico auditor de radiología. Tu tarea es analizar un texto 
de diagnóstico radiológico e identificar si corresponde a alguna de las 
patologías críticas listadas.

IMPORTANTE — SINÓNIMOS Y VARIANTES CLÍNICAS:
- "Fractura de cuello femoral", "fractura de cadera", "fractura de fémur proximal",
  "fractura pertrocantérica" o "fractura subtrocantérica" corresponden a 
  "Fractura de pelvis como primer hallazgo (trauma agudo)", ya que la radiografía 
  de pelvis AP es el estudio estándar para estos hallazgos y se notifican con la 
  misma urgencia clínica.
- "Aneurisma de aorta abdominal" o "aneurisma ilíaco" corresponde a 
  "Disección carotídea aortica o aneurisma complicado"
- "Diverticulitis aguda" corresponde a "Diverticulitis"
- "AVE", "ACV", "infarto cerebral" o "accidente cerebrovascular" corresponde a 
  "AVE agudo o en evolución"
- "TEP", "tromboembolismo" corresponde a "TEP tromboembolismo pulmonar"
- "Hematoma subdural", "hemorragia subaracnoidea" o "hemorragia lobar" corresponde 
  a "Hematoma subdural, lobar hemorragia subaracnoidea"
- Evalúa el SIGNIFICADO CLÍNICO, no solo las palabras exactas.

CONTEXTO ANATÓMICO RELEVANTE:
- "Pelvis" en contexto radiológico incluye: anillo pelviano, acetábulo, cabeza 
  femoral, cuello femoral y región trocantérica.
- "Columna" incluye: cervical, dorsal, lumbar y sacra.
- El tipo de examen solicitado es contexto válido: una Rx de pelvis AP que muestra 
  fractura de cuello femoral es un hallazgo crítico de esa región anatómica.

LISTA DE PATOLOGÍAS CRÍTICAS:
{lista_str}

DIAGNÓSTICO A ANALIZAR:
"{diagnostico}"

INSTRUCCIONES:
0. Antes de evaluar, pregúntate: ¿Este hallazgo requeriría notificación urgente 
   al médico tratante? ¿Implica riesgo vital o quirúrgico inmediato? Si la 
   respuesta es sí, busca activamente en qué categoría de la lista encaja.
1. Analiza el significado clínico del diagnóstico completo.
2. Si el diagnóstico coincide, se relaciona, sugiere o podría implicar clínicamente 
   una patología de la lista (incluyendo sinónimos, variantes anatómicas y 
   equivalencias clínicas), retorna el NOMBRE EXACTO de la patología más cercana. 
   El beneficio de la duda siempre es hacia la notificación.
3. Ante cualquier duda razonable, PREFIERE retornar la patología más cercana de 
   la lista antes que retornar null. Solo retorna null cuando el diagnóstico sea 
   CLARAMENTE no crítico y no tenga ninguna relación posible con la lista.
4. Responde ÚNICAMENTE con un objeto JSON válido, sin texto adicional.

FORMATO DE RESPUESTA:
{{
  "patologia_detectada": "Nombre Exacto de la Lista" o null,
  "confianza": "alta" | "media" | "baja",
  "razonamiento": "Breve explicación de por qué corresponde o no"
}}

Donde:
- "alta"  → coincidencia directa o sinónimo claro
- "media" → equivalencia clínica o variante anatómica
- "baja"  → duda razonable, se notifica por principio de seguridad
"""

    modelos_a_usar = MODELS[:MODELS_TO_USE]
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Iniciamos las tareas concurrentes con un leve desfase
        futures = {}
        for index, model in enumerate(modelos_a_usar):
            if index > 0 and DELAY_BETWEEN_WORKERS > 0:
                time.sleep(DELAY_BETWEEN_WORKERS)
            future = executor.submit(_consultar_modelo_llm, id_registro, model, prompt, lista_patologias)
            futures[future] = model
        
        for future in concurrent.futures.as_completed(futures):
            model = futures[future]
            try:
                resultado = future.result()
                if resultado:
                    logger.info(f"🚀 CORTE TEMPRANO: El modelo [{model}] detectó '{resultado}'.")
                    logger.info("=" * 40)
                    # Intentamos cancelar los demás
                    for f in futures:
                        f.cancel()
                    return resultado
            except Exception as exc:
                logger.error(f"[{model}] generó una excepción al obtener el resultado: {exc}")

    logger.info("ℹ️ Ningún modelo detectó una patología crítica válida.")
    logger.info("=" * 40)
    return None

# ============================================================================
# LÓGICA DE DETECCIÓN
# ============================================================================

def detectar_patologia(id_registro: int, diagnostico: str, patologias: list) -> Optional[str]:
    """Detecta patología usando únicamente el modelo de IA (LLM)."""
    return consultar_llm_patologia(id_registro, diagnostico, patologias)

# ============================================================================
# ANÁLISIS PRINCIPAL
# ============================================================================

def analizar_diagnosticos(df_acciones: pd.DataFrame, patologias: list) -> pd.DataFrame:
    """Analiza todos los diagnósticos y detecta patologías."""
    logger.info(f"Analizando {len(df_acciones)} diagnosticos...")

    resultados = []
    for idx, row in df_acciones.iterrows():
        diag = row['diagnostico']
        id_reg = row['id']
        logger.info(f"Analizando ID {id_reg}: '{str(diag)[:60]}...'")

        resultado = detectar_patologia(id_reg, diag, patologias)
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

def actualizar_registro_acciones(engine: sqlalchemy.Engine, df_resultados: pd.DataFrame) -> None:
    """
    Actualiza la tabla ris.registro_acciones con los resultados detectados.
    Campos: patologia_critica_detectada, patologia_critica, update.
    """
    logger.info("Actualizando tabla ris.registro_acciones...")

    fecha_actual = datetime.now()
    actualizados = 0
    errores = 0

    with engine.connect() as connection:
        for idx, row in df_resultados.iterrows():
            try:
                id_registro = row['id']
                patologia = row['patologia_detectada']

                patologia_critica_flag = 'si' if pd.notna(patologia) else 'no'
                patologia_val = patologia if pd.notna(patologia) else None

                query_update = """
                UPDATE ris.registro_acciones
                SET
                    patologia_critica_detectada = :patologia,
                    patologia_critica = :patologia_critica_flag,
                    `update` = :fecha_hora
                WHERE id = :id_registro AND estado = 'En Proceso'
                """

                connection.execute(
                    sqlalchemy.text(query_update),
                    {
                        'patologia': patologia_val,
                        'patologia_critica_flag': patologia_critica_flag,
                        'fecha_hora': fecha_actual,
                        'id_registro': id_registro
                    }
                )

                actualizados += 1
                logger.info(f"  → Registro ID {id_registro} actualizado: {patologia_val if patologia_val else '[SIN PATOLOGÍA]'}")

            except Exception as e:
                logger.error(f"[ERROR] Actualizando registro ID {id_registro}: {e}")
                errores += 1

        connection.commit()

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

    engine = None

    try:
        engine = conectar_bd(DB_CONFIG)
        df_acciones, patologias = cargar_datos(engine)

        if df_acciones.empty:
            logger.info("No hay registros para procesar.")
            return

        df_resultados = analizar_diagnosticos(df_acciones, patologias)
        actualizar_registro_acciones(engine, df_resultados)

        logger.info("\n" + "=" * 70)
        logger.info("[OK] PROCESO COMPLETADO")
        logger.info("=" * 70)

    except Exception as e:
        logger.error(f"\n[ERROR] CRITICO: {e}")
        try:
            enviar_alerta_todos(
                f"❌ <b>Error Crítico en el script: detecta_patologia_ia</b>\n"
                f"Fallo durante la ejecución:\n<code>{str(e)}</code>"
            )
        except Exception as tel_e:
            logger.warning(f"[WARNING] Falló envío Telegram: {tel_e}")

        sys.exit(1)
    finally:
        if engine:
            engine.dispose()
            logger.info("[OK] Conexion cerrada")


if __name__ == '__main__':
    main()
