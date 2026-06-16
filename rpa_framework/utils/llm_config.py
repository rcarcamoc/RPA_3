# -*- coding: utf-8 -*-
"""
llm_config.py
=============
Configuración centralizada de modelos LLM para todos los scripts del RPA Framework.

Para cambiar los modelos utilizados en TODOS los scripts, sólo edita BASE_LLM_MODELS.
Los modelos se ordenan dinámicamente en tiempo de ejecución según su rendimiento
histórico registrado en ris.log_llm_ranking.

Verificado: 2026-06-16  (via update_and_validate_models.py)
Modelos vigentes y probados:
  - google/gemma-4-31b-it:free                          ✅ OK (No reasoning, muy rápido)
  - nvidia/nemotron-3-ultra-550b-a55b:free              ✅ OK (No reasoning, 550B)
  - openai/gpt-oss-120b:free                            ✅ OK (No reasoning, 120B)
  - openrouter/owl-alpha                                ✅ OK (Routing inteligente)
  - nvidia/nemotron-3-super-120b-a12b:free              ✅ OK (No reasoning, 120B)
  - qwen/qwen3-235b-a22b-thinking-2507                  ✅ OK (Reasoning)
  - nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free  ✅ OK (Reasoning)
"""

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# URL base de la API de OpenRouter (no cambiar)
# ---------------------------------------------------------------------------
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# ---------------------------------------------------------------------------
# Lista BASE de modelos LLM (orden de edición manual / fallback estático)
#
# Esta es la lista que edita la GUI y update_and_validate_models.py.
# El orden aquí es el orden de FALLBACK cuando la DB no está disponible.
# En ejecución normal, los scripts llaman a get_ranked_models() que
# reordena esta lista según el rendimiento histórico en log_llm_ranking.
# ---------------------------------------------------------------------------
BASE_LLM_MODELS = [
   "google/gemma-4-31b-it:free",                            # Primario — Validado OK
   "nvidia/nemotron-3-ultra-550b-a55b:free",                # Fallback 1 — Validado OK
   "openai/gpt-oss-120b:free",                              # Fallback 2 — Validado OK
   "openrouter/owl-alpha",                                  # Fallback 3 — Validado OK
   "nvidia/nemotron-3-super-120b-a12b:free",                # Fallback 4 — Validado OK
   "qwen/qwen3-235b-a22b-thinking-2507",                    # Fallback 5 — Validado OK
   "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",    # Fallback 6 — Validado OK
]

# Alias de compatibilidad estática (para scripts que aún no usan get_ranked_models)
LLM_MODELS = BASE_LLM_MODELS

# ---------------------------------------------------------------------------
# Alias conveniente para scripts que usan un solo modelo
# ---------------------------------------------------------------------------
LLM_MODEL_PRIMARY = BASE_LLM_MODELS[0]

# ---------------------------------------------------------------------------
# Parámetros de llamada por defecto (pueden sobrescribirse en cada script)
# ---------------------------------------------------------------------------
LLM_DEFAULT_TEMPERATURE = 0.0
LLM_DEFAULT_MAX_TOKENS = 4000  # Aumentado a 4000 para evitar cortes en modelos de reasoning
LLM_DEFAULT_TIMEOUT = 30  # segundos

# ---------------------------------------------------------------------------
# DB Config (local, sin contraseña — entorno de producción controlado)
# ---------------------------------------------------------------------------
_DB_CONFIG = dict(host='localhost', user='root', password='', database='ris',
                  connect_timeout=2)


def get_ranked_models(base_list=None, contexto='busqueda_ocr'):
    """
    Retorna base_list reordenada según el rendimiento histórico en ris.log_llm_ranking.

    Algoritmo:
      - Solo considera filas con es_primer_intento=1 (excluye intentos de fallback
        contaminados por errores de cuota o red del modelo anterior).
      - Solo considera filas del mismo 'contexto' (busqueda_ocr, deteccion_patologia, …)
        para que el ranking sea relevante al tipo de tarea.
      - Score Laplace = (exitos + 1) / (intentos + 2)  — evita favorecer modelos
        con muy pocos registros (1 éxito de 1 intento ≠ modelo confiable).
      - El tiempo promedio se usa SOLO como desempate (tiebreaker), no como penalización
        matemática. Un modelo lento pero correcto sigue siendo mejor que uno rápido
        pero incorrecto.
      - Si la DB no está disponible, retorna base_list sin modificar (fallback seguro).

    Args:
        base_list: lista de model IDs a reordenar. Si None, usa BASE_LLM_MODELS.
        contexto:  tipo de tarea para filtrar el ranking ('busqueda_ocr',
                   'deteccion_patologia', etc.)

    Returns:
        Lista reordenada de model IDs (lista nueva, no modifica base_list).
    """
    if base_list is None:
        base_list = BASE_LLM_MODELS

    try:
        import mysql.connector
        conn = mysql.connector.connect(**_DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                modelo,
                SUM(es_match)  AS exitos,
                COUNT(*)       AS intentos,
                AVG(tiempo_ms) AS tiempo_prom_ms
            FROM ris.log_llm_ranking
            WHERE es_primer_intento = 1
              AND contexto = %s
            GROUP BY modelo
        """, (contexto,))
        rows = cursor.fetchall()
        conn.close()

        stats = {r['modelo']: r for r in rows}

    except Exception as e:
        logger.debug(f"[llm_config] DB no disponible para ranking ({e}), usando orden base.")
        return list(base_list)

    def _score(model_id):
        if model_id not in stats:
            # Modelo sin historial: score neutro (50%), tiempo asumido 5s
            return (0.5, 5000.0)
        r = stats[model_id]
        exitos  = int(r['exitos'] or 0)
        intentos = int(r['intentos'] or 0)
        tiempo  = float(r['tiempo_prom_ms'] or 5000.0)
        laplace = (exitos + 1) / (intentos + 2)
        # Retorna tupla para sort: score DESC (negado), tiempo ASC
        return (-laplace, tiempo)

    sorted_list = sorted(base_list, key=_score)
    logger.debug(f"[llm_config] Modelos reordenados para contexto='{contexto}': {sorted_list}")
    return sorted_list


def log_llm_result(
    modelo: str,
    es_match: bool,
    confianza: float,
    tiempo_ms: int,
    razonamiento: str = "",
    target_buscado: str = "",
    texto_ocr: str = "",
    id_registro: int = 0,
    es_primer_intento: bool = True,
    contexto: str = "busqueda_ocr",
):
    """
    Registra el resultado de una llamada LLM en ris.log_llm_ranking.

    Función centralizada — todos los scripts deben llamar a esta función
    en lugar de tener su propio INSERT, para garantizar que el schema sea
    consistente y que los campos es_primer_intento y contexto se propaguen.

    Args:
        modelo:            ID del modelo usado (ej. 'google/gemma-4-31b-it:free')
        es_match:          True si el modelo produjo un resultado válido/correcto
        confianza:         Valor 0.0–1.0 reportado por el modelo
        tiempo_ms:         Tiempo de respuesta en milisegundos
        razonamiento:      Texto de razonamiento del modelo (para auditoría)
        target_buscado:    Texto objetivo buscado (diagnóstico, patología, etc.)
        texto_ocr:         Texto fuente enviado al modelo (OCR u otro)
        id_registro:       ID de la fila en registro_acciones (para trazabilidad)
        es_primer_intento: True si este modelo fue el primero intentado en esa llamada.
                           False si fue un fallback (modelo anterior falló por cuota/red).
        contexto:          Tipo de tarea ('busqueda_ocr', 'deteccion_patologia', etc.)
    """
    try:
        import mysql.connector
        conn = mysql.connector.connect(**_DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ris.log_llm_ranking
              (id_registro, modelo, target_buscado, texto_ocr,
               es_match, razonamiento, confianza, tiempo_ms,
               es_primer_intento, contexto)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            id_registro,
            modelo,
            (target_buscado or '')[:255],
            (texto_ocr or '')[:1000],
            1 if es_match else 0,
            (razonamiento or '')[:500],
            float(confianza),
            int(tiempo_ms),
            1 if es_primer_intento else 0,
            contexto,
        ))
        conn.commit()
        conn.close()
        logger.debug(
            f"[log_llm_result] {modelo} | match={es_match} | "
            f"conf={confianza:.2f} | {tiempo_ms}ms | primer={es_primer_intento} | ctx={contexto}"
        )
    except Exception as e:
        logger.warning(f"[log_llm_result] No se pudo registrar en DB: {e}")
