"""
Script para detectar patologías críticas en diagnósticos de texto libre
y actualizar la tabla ris.registro_acciones con los resultados.

Utiliza 3 niveles de búsqueda:
1. Búsqueda exacta normalizada.
2. Búsqueda fuzzy (rapidfuzz).
3. Análisis semántico con LLM (OpenRouter/DeepSeek) como fallback.
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

# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

# Credenciales de BD
DB_CONFIG = {
    'user': 'root',
    'password': '',
    'host': 'localhost',
    'database': 'ris'
}

# Configuración LLM (OpenRouter)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    logger.error("OPENROUTER_API_KEY no está configurada en el archivo .env")
    raise ValueError("OPENROUTER_API_KEY no está configurada")

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Lista de modelos para fallback (siguiendo referencia)
MODELS = [
    "tngtech/deepseek-r1t2-chimera:free",
    "openai/gpt-oss-120b:free",
    "arcee-ai/trinity-large-preview:free",
    "deepseek/deepseek-r1-0528:free"
]


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
    
    # Queries definidas por el usuario / lógica original
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
# INTEGRAZIÓN LLM (OpenRouter)
# ============================================================================

def consultar_llm_patologia(diagnostico: str, lista_patologias: List[str]) -> Optional[str]:
    """
    Consulta al LLM si el diagnóstico corresponde a alguna de las patologías listadas.
    Implementa fallback entre varios modelos gratuitos si falla uno.
    """
    logger.info(f"🤖 Consultando LLM para diagnóstico: '{diagnostico[:50]}...'")
    
    lista_str = "\n".join([f"- {p}" for p in lista_patologias])
    
    prompt = f"""
Eres un experto médico auditor. Tu tarea es analizar un texto de diagnóstico y determinar si indica la presencia de alguna de las patologías críticas listadas.

LISTA DE PATOLOGÍAS CRÍTICAS:
{lista_str}

DIAGNÓSTICO A ANALIZAR:
"{diagnostico}"

INSTRUCCIONES:
1. Analiza el significado semántico del diagnóstico.
2. Si el diagnóstico coincide o implica claramente una de las patologías de la lista, retorna el NOMBRE EXACTO de esa patología según aparece en la lista.
3. Si no hay coincidencia clara o es ambiguo, retorna null.
4. Responde ÚNICAMENTE con un objeto JSON.

FORMATO DE RESPUESTA JSON:
{{
  "patologia_detectada": "Nombre Exacto" o null,
  "razonamiento": "Breve explicación"
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
                    "temperature": 0.0,
                    "max_tokens": 800,
                },
                timeout=30
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
            
            # Extraer JSON
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                patologia = data.get('patologia_detectada')
                
                # Validar que la patología retornada esté en la lista original (seguridad)
                if patologia and patologia in lista_patologias:
                    logger.info(f"✅ LLM detectó: {patologia} (Modelo: {current_model})")
                    return patologia
                elif patologia:
                    logger.warning(f"⚠️ LLM retornó '{patologia}' pero no coincide exactamente con la lista.")
            
            # Si el modelo respondió pero no detectó nada, no intentamos con otros modelos
            # a menos que haya sido un error de parsing o similar. 
            # En este caso, si patologia_detectada es null, asumimos que no hay match.
            return None

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

def detectar_patologia(diagnostico: str, patologias: list, umbral: int = FUZZY_THRESHOLD) -> Optional[str]:
    """
    Detecta patología en el diagnóstico usando 3 métodos en cascada:
    1. BÚSQUEDA EXACTA NORMALIZADA
    2. BÚSQUEDA FUZZY
    3. LLM (OpenRouter)
    """
    diagnostico_norm = normalizar_texto(diagnostico)
    
    if not diagnostico_norm:
        return None
    
    # -----------------------------------------------------------------------
    # MÉTODO 1: Búsqueda Exacta
    # -----------------------------------------------------------------------
    patologias_norm = [normalizar_texto(p) for p in patologias]
    
    for patologia_norm, patologia_orig in zip(patologias_norm, patologias):
        patron = r'\b' + re.escape(patologia_norm) + r'\b'
        if re.search(patron, diagnostico_norm):
            return patologia_orig
    
    # -----------------------------------------------------------------------
    # MÉTODO 2: Búsqueda Fuzzy
    # -----------------------------------------------------------------------
    frases_diagnostico = [
        s.strip() for s in diagnostico_norm.replace(',', '|').split('|')
        if len(s.strip()) > 3
    ]
    
    mejores_coincidencias = []
    
    for frase in frases_diagnostico:
        match = process.extractOne(
            frase,
            patologias_norm,
            scorer=fuzz.token_set_ratio,
            score_cutoff=umbral
        )
        
        if match:
            indice_patologia = patologias_norm.index(match[0])
            puntuacion = match[1]
            mejores_coincidencias.append((puntuacion, patologias[indice_patologia]))
    
    if mejores_coincidencias:
        mejores_coincidencias.sort(reverse=True)
        return mejores_coincidencias[0][1]
    
    # -----------------------------------------------------------------------
    # MÉTODO 3: Consulta LLM (Fallback)
    # -----------------------------------------------------------------------
    # Solo si fallan los anteriores
    logger.info("Iniciando búsqueda por LLM...")
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
        logger.info(f"Analizando ID {id_reg}...")
        
        resultado = detectar_patologia(diag, patologias)
        resultados.append(resultado)
        
    df_acciones['patologia_detectada'] = resultados
    
    # Contar resultados
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
    Actualiza la tabla ris.registro_acciones detectadas.
    Campo objetivo: patologia_critica_detectada
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
                
                # Flag de patología crítica
                patologia_critica_flag = 'si' if pd.notna(patologia) else 'no'
                patologia_val = patologia if pd.notna(patologia) else None
                
                # Query de UPDATE modificado para usar 'patologia_critica_detectada' y 'patologia_critica'
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
    logger.info("="*70)
    logger.info("INICIANDO ANALISIS HIBRIDO (EXACTO + FUZZY + LLM)")
    logger.info("="*70)
    
    engine = None
    
    try:
        engine = conectar_bd(DB_CONFIG)
        df_acciones, patologias = cargar_datos(engine)
        
        if df_acciones.empty:
            logger.info("No hay registros para procesar.")
            return

        df_resultados = analizar_diagnosticos(df_acciones, patologias)
        actualizar_registro_acciones(engine, df_resultados)
        
        logger.info("\n" + "="*70)
        logger.info("[OK] PROCESO COMPLETADO")
        logger.info("="*70)
        
    except Exception as e:
        logger.error(f"\n[ERROR] CRITICO: {e}")
        try:
            enviar_alerta_todos(f"❌ <b>Error Crítico en el script: detecta_patologia_ia</b>\\nFallo durante la ejecución:\\n<code>{str(e)}</code>")
        except Exception as tel_e:
            logger.warning(f"[WARNING] Falló envío Telegram: {tel_e}")
            
        sys.exit(1)
    finally:
        if engine:
            engine.dispose()
            logger.info("[OK] Conexion cerrada")

if __name__ == '__main__':
    main()
