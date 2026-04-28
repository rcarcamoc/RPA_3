"""
Script para detectar patologías críticas en diagnósticos de texto libre
y actualizar la tabla ris.registro_acciones con los resultados.

Utiliza 3 niveles de búsqueda:
1. Búsqueda exacta normalizada.
2. Búsqueda fuzzy (rapidfuzz) — mejorada con split múltiple y múltiples scorers.
3. Análisis semántico con LLM (OpenRouter/DeepSeek) como fallback.

CORRECCIONES v3:
- [FIX 1] Fuzzy: split por coma, punto, punto y coma y newline (antes solo coma)
          → evita que textos sin comas queden como una sola frase larga y no pasen umbral.
- [FIX 2] Fuzzy: usa 3 scorers (token_set_ratio, partial_ratio, WRatio) y toma el máximo
          → detecta coincidencias semánticas parciales como "aneurisma aorta" ↔ "aneurisma complicado".
- [FIX 3] LLM: validación por texto normalizado (sin tildes/mayúsculas) en lugar de exact match
          → evita fallos cuando el LLM retorna "aórtica" y la BD tiene "aortica".
- [FIX 4] LLM: si la patología retornada no coincide con la lista no sale inmediatamente,
          sigue intentando con el siguiente modelo de respaldo.
- [FIX 5] LLM: el prompt instruye explícitamente sobre sinónimos clínicos y variantes de redacción.
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
from rapidfuzz import fuzz, process
from typing import Tuple, Optional, List
from datetime import datetime
import sys

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

# Umbral de similitud fuzzy
FUZZY_THRESHOLD = 70

# ============================================================================
# FUNCIONES UTILITARIAS
# ============================================================================

def normalizar_texto(texto: str) -> str:
    """Normaliza texto: minúsculas, sin acentos, espacios limpios."""
    if not isinstance(texto, str):
        return ""
    texto_nfd = unicodedata.normalize('NFD', texto)
    texto_sin_tildes = ''.join(c for c in texto_nfd if unicodedata.category(c) != 'Mn')
    texto_limpio = re.sub(r'\s+', ' ', texto_sin_tildes.lower().strip())
    texto_limpio = re.sub(r'[.,;:]+', '', texto_limpio)
    return texto_limpio


def _buscar_en_lista_normalizado(texto: str, lista_patologias: List[str]) -> Optional[str]:
    """
    Busca 'texto' en lista_patologias comparando versiones normalizadas.
    Retorna el nombre original de la BD si hay coincidencia, o None.
    [FIX 3] — reemplaza la comparación con 'in' directo que falla por tildes/mayúsculas.
    """
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

def consultar_llm_patologia(diagnostico: str, lista_patologias: List[str]) -> Optional[str]:
    """
    Consulta al LLM si el diagnóstico corresponde a alguna de las patologías listadas.
    Implementa fallback entre varios modelos gratuitos si falla uno.
    [FIX 3] Valida respuesta con normalización de texto, no con exact match.
    [FIX 4] Si el modelo responde pero la patología no coincide, prueba el siguiente modelo.
    [FIX 5] El prompt incluye instrucción explícita sobre sinónimos y variantes clínicas.
    """
    logger.info(f"🤖 Consultando LLM para diagnóstico: '{diagnostico[:80]}...'")

    lista_str = "\n".join([f"- {p}" for p in lista_patologias])

    prompt = f"""
Eres un experto médico auditor de radiología. Tu tarea es analizar un texto de diagnóstico radiológico e identificar si corresponde a alguna de las patologías críticas listadas.

IMPORTANTE — SINÓNIMOS Y VARIANTES CLÍNICAS:
- Un "aneurisma de aorta abdominal" o "aneurisma ilíaco" corresponde a "Disección carotídea aortica o aneurisma complicado"
- "Diverticulitis aguda" corresponde a "Diverticulitis"
- "AVE", "ACV", "infarto cerebral" o "accidente cerebrovascular" corresponde a "AVE agudo o en evolución"
- "TEP", "tromboembolismo" corresponde a "TEP tromboembolismo pulmonar"
- "hematoma subdural", "hemorragia subaracnoidea" o "hemorragia lobar" corresponde a "Hematoma subdural, lobar hemorragia subaracnoidea"
- Evalúa el SIGNIFICADO CLÍNICO, no solo las palabras exactas.

LISTA DE PATOLOGÍAS CRÍTICAS:
{lista_str}

DIAGNÓSTICO A ANALIZAR:
"{diagnostico}"

INSTRUCCIONES:
1. Analiza el significado clínico del diagnóstico completo.
2. Si el diagnóstico coincide o implica claramente una patología de la lista (incluyendo sinónimos y variantes clínicas), retorna el NOMBRE EXACTO de esa patología tal como aparece en la lista anterior.
3. Si no hay coincidencia clara, retorna null.
4. Responde ÚNICAMENTE con un objeto JSON válido, sin texto adicional.

FORMATO DE RESPUESTA:
{{
  "patologia_detectada": "Nombre Exacto de la Lista" o null,
  "razonamiento": "Breve explicación de por qué corresponde o no"
}}
"""

    for current_model in MODELS:
        try:
            logger.info(f"Intentando con modelo: {current_model}")
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

            if response.status_code == 404:
                logger.warning(f"⚠️ Modelo {current_model} no encontrado (404). Probando siguiente...")
                continue
            elif response.status_code == 429:
                logger.warning(f"⚠️ Límite de cuota alcanzado para {current_model} (429). Probando siguiente...")
                continue

            response.raise_for_status()
            result = response.json()
            content = result['choices'][0]['message'].get('content', '')

            # Extraer JSON de la respuesta
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                patologia = data.get('patologia_detectada')
                razonamiento = data.get('razonamiento', '')

                # [FIX 3] Validar con normalización, no con exact match
                if patologia:
                    p_validada = _buscar_en_lista_normalizado(patologia, lista_patologias)
                    if p_validada:
                        logger.info(f"✅ LLM detectó: '{p_validada}' (Modelo: {current_model})")
                        logger.info(f"   Razonamiento: {razonamiento}")
                        return p_validada
                    else:
                        # [FIX 4] No sale: intenta con el siguiente modelo
                        logger.warning(
                            f"⚠️ LLM retornó '{patologia}' pero no coincide con ninguna "
                            f"patología de la lista (normalizado). Intentando siguiente modelo..."
                        )
                        continue  # <-- antes era return None, ahora prueba el siguiente modelo

                # LLM respondió null → no hay patología, es definitivo para este modelo
                logger.info(f"ℹ️ LLM no detectó patología crítica (Modelo: {current_model}). Razonamiento: {razonamiento}")
                return None

        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ Error parseando JSON del modelo {current_model}: {e}. Intentando siguiente...")
            continue
        except Exception as e:
            logger.error(f"Error con modelo {current_model}: {e}")
            if current_model == MODELS[-1]:
                logger.error("Todos los modelos han fallado.")
            else:
                logger.info("Probando con el siguiente modelo de respaldo...")
            continue

    return None

# ============================================================================
# LÓGICA DE DETECCIÓN
# ============================================================================

def _segmentar_diagnostico(diagnostico: str) -> List[str]:
    """
    [FIX 1 + FIX 2] Divide el texto de diagnóstico en frases usando múltiples
    delimitadores (coma, punto, punto y coma, newline). Incluye también el
    texto completo normalizado para capturar patologías que abarcan toda la frase.
    """
    texto_split = diagnostico
    for sep in [',', '.', ';', '\n', '\r']:
        texto_split = texto_split.replace(sep, '|')

    frases = list(dict.fromkeys(  # preserva orden y elimina duplicados
        normalizar_texto(s)
        for s in texto_split.split('|')
        if len(s.strip()) > 3
    ))

    # Siempre incluir el texto completo normalizado como candidato extra
    diag_completo = normalizar_texto(diagnostico)
    if diag_completo and diag_completo not in frases:
        frases.insert(0, diag_completo)

    return frases


def detectar_patologia(diagnostico: str, patologias: list, umbral: int = FUZZY_THRESHOLD) -> Optional[str]:
    """
    Detecta patología en el diagnóstico usando 3 métodos en cascada:
    1. BÚSQUEDA EXACTA NORMALIZADA
    2. BÚSQUEDA FUZZY (mejorada)
    3. LLM (OpenRouter) como fallback semántico
    """
    diagnostico_norm = normalizar_texto(diagnostico)

    if not diagnostico_norm:
        return None

    # -----------------------------------------------------------------------
    # MÉTODO 1: Búsqueda Exacta Normalizada
    # -----------------------------------------------------------------------
    patologias_norm = [normalizar_texto(p) for p in patologias]

    for patologia_norm, patologia_orig in zip(patologias_norm, patologias):
        patron = r'\b' + re.escape(patologia_norm) + r'\b'
        if re.search(patron, diagnostico_norm):
            logger.info(f"[M1-Exacto] Detectado: '{patologia_orig}'")
            return patologia_orig

    # -----------------------------------------------------------------------
    # MÉTODO 2: Búsqueda Fuzzy (mejorada)
    # [FIX 1] Split múltiple en lugar de solo comas
    # [FIX 2] Tres scorers: token_set_ratio + partial_ratio + WRatio → toma el máximo
    # -----------------------------------------------------------------------
    frases_diagnostico = _segmentar_diagnostico(diagnostico)
    logger.debug(f"[M2-Fuzzy] Frases candidatas ({len(frases_diagnostico)}): {frases_diagnostico}")

    mejores_coincidencias = []

    for frase in frases_diagnostico:
        for scorer in [fuzz.token_set_ratio, fuzz.partial_ratio, fuzz.WRatio]:
            match = process.extractOne(
                frase,
                patologias_norm,
                scorer=scorer,
                score_cutoff=umbral
            )
            if match:
                indice = patologias_norm.index(match[0])
                mejores_coincidencias.append((match[1], patologias[indice]))

    if mejores_coincidencias:
        mejores_coincidencias.sort(reverse=True)
        ganador = mejores_coincidencias[0][1]
        score = mejores_coincidencias[0][0]
        logger.info(f"[M2-Fuzzy] Detectado: '{ganador}' (score: {score:.1f})")
        return ganador

    # -----------------------------------------------------------------------
    # MÉTODO 3: Consulta LLM (Fallback semántico)
    # -----------------------------------------------------------------------
    logger.info("[M3-LLM] Iniciando análisis semántico con LLM...")
    match_llm = consultar_llm_patologia(diagnostico, patologias)
    if match_llm:
        return match_llm

    return None

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

        resultado = detectar_patologia(diag, patologias)
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
                if actualizados % 10 == 0:
                    logger.info(f"  {actualizados} registros procesados...")

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
    logger.info("INICIANDO ANALISIS HIBRIDO (EXACTO + FUZZY + LLM) v3")
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
