"""
Script para detectar patologías críticas en diagnósticos de texto libre
y actualizar la tabla ris.registro_acciones con los resultados.

Utiliza búsqueda inteligente (normalización + fuzzy matching con rapidfuzz).
"""

import pandas as pd
import sqlalchemy
import unicodedata
import re
from rapidfuzz import fuzz, process
from typing import Tuple, Optional
import logging
from datetime import datetime

# Configurar logging para seguimiento de ejecución
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'patologias_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
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
    'database': 'ris'  # ej: 'ris'
}

# Umbral de similitud fuzzy (0-100)
# 70: balance entre precisión y recall (RECOMENDADO)
FUZZY_THRESHOLD = 70

# ============================================================================
# FUNCIONES UTILITARIAS
# ============================================================================

def normalizar_texto(texto: str) -> str:
    """
    Normaliza texto: minúsculas, sin acentos, espacios limpios.
    """
    if not isinstance(texto, str):
        return ""
    
    # Descomponer unicode
    texto_nfd = unicodedata.normalize('NFD', texto)
    # Eliminar marcas diacríticas
    texto_sin_tildes = ''.join(
        c for c in texto_nfd 
        if unicodedata.category(c) != 'Mn'
    )
    
    # Minúsculas, espacios limpios
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
        # Test de conexión
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
# LÓGICA DE DETECCIÓN
# ============================================================================

def detectar_patologia(diagnostico: str, patologias: list, umbral: int = FUZZY_THRESHOLD) -> Optional[str]:
    """
    Detecta patología en el diagnóstico usando 2 métodos:
    
    1. BÚSQUEDA EXACTA NORMALIZADA (rapidez)
    2. BÚSQUEDA FUZZY (captura variaciones)
    
    Retorna: nombre de patología detectada o None
    """
    diagnostico_norm = normalizar_texto(diagnostico)
    
    if not diagnostico_norm:
        return None
    
    # -----------------------------------------------------------------------
    # MÉTODO 1: Búsqueda Exacta (más rápido, sin ruido)
    # -----------------------------------------------------------------------
    patologias_norm = [normalizar_texto(p) for p in patologias]
    
    for patologia_norm, patologia_orig in zip(patologias_norm, patologias):
        # Buscar como palabra completa dentro del diagnóstico
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
    
    return None

# ============================================================================
# ANÁLISIS PRINCIPAL
# ============================================================================

def analizar_diagnosticos(df_acciones: pd.DataFrame, patologias: list) -> pd.DataFrame:
    """Analiza todos los diagnósticos y detecta patologías."""
    logger.info(f"Analizando {len(df_acciones)} diagnosticos...")
    
    df_acciones['patologia_detectada'] = df_acciones['diagnostico'].apply(
        lambda diag: detectar_patologia(diag, patologias)
    )
    
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
    Actualiza la tabla ris.registro_acciones con:
    - patologia_critica: nombre de patología detectada o 'No'
    - update: fecha y hora actual
    """
    logger.info("Actualizando tabla ris.registro_acciones...")
    
    fecha_actual = datetime.now()
    actualizados = 0
    errores = 0
    
    with engine.connect() as connection:
        for idx, row in df_resultados.iterrows():
            try:
                id_registro = row['id']
                patologia = row['patologia_detectada'] if pd.notna(row['patologia_detectada']) else 'No'
                
                # Query de UPDATE con columna 'update' y placeholders
                query_update = """
                UPDATE ris.registro_acciones 
                SET 
                    patologia_critica = :patologia,
                    `update` = :fecha_hora
                WHERE id = :id_registro AND estado = 'En Proceso'
                """
                
                connection.execute(
                    sqlalchemy.text(query_update),
                    {
                        'patologia': patologia,
                        'fecha_hora': fecha_actual,
                        'id_registro': id_registro
                    }
                )
                
                actualizados += 1
                
                if actualizados % 100 == 0:
                    logger.info(f"  {actualizados} registros actualizados...")
                
            except Exception as e:
                logger.error(f"[ERROR] Actualizando registro ID {id_registro}: {e}")
                errores += 1
        
        connection.commit()
    
    logger.info(f"[OK] Actualizacion completada:")
    logger.info(f"  - Registros actualizados: {actualizados}")
    logger.info(f"  - Errores: {errores}")
    logger.info(f"  - Fecha/hora de actualizacion: {fecha_actual}")

# ============================================================================
# GENERACIÓN DE REPORTES
# ============================================================================

def generar_reporte(df_acciones: pd.DataFrame, output_path: str = 'reporte_patologias.xlsx'):
    """Genera reporte en Excel con resultados."""
    logger.info(f"Generando reporte: {output_path}")
    
    try:
        detectadas = df_acciones[df_acciones['patologia_detectada'].notna()].copy()
        no_detectadas = df_acciones[df_acciones['patologia_detectada'].isna()].copy()
        
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            detectadas.to_excel(writer, sheet_name='Patologias Detectadas', index=False)
            no_detectadas.to_excel(writer, sheet_name='Sin Deteccion', index=False)
            
            resumen = pd.DataFrame({
                'Metrica': [
                    'Total de diagnosticos analizados',
                    'Patologias criticas detectadas',
                    'Sin patologias criticas',
                    'Tasa de deteccion (%)',
                    'Fecha/Hora de ejecucion'
                ],
                'Valor': [
                    len(df_acciones),
                    len(detectadas),
                    len(no_detectadas),
                    f"{(len(detectadas) / len(df_acciones) * 100):.2f}%" if len(df_acciones) > 0 else "0%",
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ]
            })
            resumen.to_excel(writer, sheet_name='Resumen', index=False)
        
        logger.info(f"[OK] Reporte generado: {output_path}")
    except Exception as e:
        logger.error(f"[ERROR] No se pudo generar el reporte: {e}")

# ============================================================================
# PUNTO DE ENTRADA
# ============================================================================

def main():
    """Función principal del script."""
    logger.info("="*70)
    logger.info("INICIANDO ANALISIS Y ACTUALIZACION DE PATOLOGIAS CRITICAS")
    logger.info("="*70)
    
    engine = None
    
    try:
        engine = conectar_bd(DB_CONFIG)
        df_acciones, patologias = cargar_datos(engine)
        df_resultados = analizar_diagnosticos(df_acciones, patologias)
        actualizar_registro_acciones(engine, df_resultados)
        generar_reporte(df_resultados)
        
        logger.info("\n--- MUESTRA DE RESULTADOS (primeras 10 filas) ---")
        print(df_resultados[['id', 'diagnostico', 'patologia_detectada']].head(10).to_string(index=False))
        
        logger.info("\n" + "="*70)
        logger.info("[OK] ANALISIS Y ACTUALIZACION COMPLETADOS EXITOSAMENTE")
        logger.info("="*70)
        
    except Exception as e:
        logger.error(f"\n[ERROR] CRITICO: {e}")
    finally:
        if engine:
            engine.dispose()
            logger.info("[OK] Conexion cerrada")

if __name__ == '__main__':
    main()
