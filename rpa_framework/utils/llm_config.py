# -*- coding: utf-8 -*-
"""
llm_config.py
=============
Configuración centralizada de modelos LLM para todos los scripts del RPA Framework.

Para cambiar los modelos utilizados en TODOS los scripts, sólo edita BASE_LLM_MODELS.
Los modelos se ordenan dinámicamente en tiempo de ejecución según su rendimiento
histórico registrado en ris.log_llm_ranking.

# Verificado: 2026-08-16 (10 modelos activos y validados)
# Modelos vigentes y probados (5 Nvidia NIM + 5 OpenRouter Free):
#   - meta/llama-3.1-8b-instruct                         ✅ OK (Nvidia NIM, 1.07s)
#   - nvidia/llama-3.3-nemotron-super-49b-v1             ✅ OK (Nvidia NIM, 1.86s)
#   - nvidia/nemotron-nano-12b-v2-vl:free                ✅ OK (OpenRouter Free, 1.41s)
#   - nvidia/nemotron-3-nano-omni-30b-a3b-reasoning      ✅ OK (Nvidia NIM, 2.85s)
#   - nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free ✅ OK (OpenRouter Free, 3.35s)
#   - meta/llama-3.2-11b-vision-instruct                 ✅ OK (Nvidia NIM, 1.35s)
#   - nvidia/nemotron-nano-12b-v2-vl                     ✅ OK (Nvidia NIM, 1.70s)
#   - nvidia/nemotron-3-super-120b-a12b:free             ✅ OK (OpenRouter Free, 2.92s)
#   - openai/gpt-oss-20b:free                            ✅ OK (OpenRouter Free, 100% match)
#   - openrouter/free                                    ✅ OK (OpenRouter Free Router)
"""

import os
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# URL base de la API de OpenRouter (no cambiar)
# ---------------------------------------------------------------------------
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

def get_llm_request_params(model_id):
    """
    Retorna la URL base, API Key y el nombre del proveedor correspondiente para el modelo.
    Detecta si corresponde a NVIDIA NIM o a OpenRouter.
    """
    try:
        from dotenv import load_dotenv
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent
        env_path = project_root / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=True)
    except Exception:
        pass

    nvidia_key = os.getenv("NVIDIA_API_KEY", "")
    if nvidia_key and not model_id.endswith(":free"):
        nvidia_prefixes = (
            "01-ai/", "abacusai/", "adept/", "ai21labs/", "aisingapore/", "baai/", "bigcode/",
            "bytedance/", "databricks/", "deepseek-ai/", "google/", "ibm/", "meta/", "microsoft/",
            "minimaxai/", "mistralai/", "moonshotai/", "nv-mistralai/", "nvidia/", "openai/",
            "poolside/", "qwen/", "sarvamai/", "snowflake/", "stepfun-ai/", "thinkingmachines/",
            "upstage/", "writer/", "z-ai/", "zyphra/"
        )
        if any(model_id.startswith(p) for p in nvidia_prefixes):
            return "https://integrate.api.nvidia.com/v1", nvidia_key, "nvidia"
            
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
    return "https://openrouter.ai/api/v1", openrouter_key, "openrouter"

# ---------------------------------------------------------------------------
# Lista BASE de modelos LLM ampliados y validados (Nvidia NIM y OpenRouter Free)
# ---------------------------------------------------------------------------
BASE_LLM_MODELS = [
   "meta/llama-3.2-11b-vision-instruct",                     # Primario — Validado OK
   "openai/gpt-oss-20b",                                     # Fallback 1 — Validado OK
   "nvidia/nemotron-parse-2.0",                              # Fallback 2 — Validado OK
   "meta/muse-glimmer-30b",                                  # Fallback 3 — Validado OK
   "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",          # Fallback 4 — Validado OK
   "nvidia/nemotron-3-super-120b-a12b:free",                 # Fallback 5 — Validado OK
   "cohere/north-mini-code:free",                            # Fallback 6 — Validado OK
   "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",     # Fallback 7 — Validado OK
   "nvidia/nemotron-3.5-lightning:free",                     # Fallback 8 — Validado OK
   "inclusionai/ling-3.0-flash-vl:free",                     # Fallback 9 — Validado OK
]

# Listas de respaldo por defecto según especialización
OCR_DEFAULT_MODELS = list(BASE_LLM_MODELS)

# Lista ampliada para Patología Crítica (razonamiento clínico, >= 11B-120B / reasoning)
PATOLOGIA_DEFAULT_MODELS = [
    "nex-agi/nex-n2.5-pro:free",
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
LLM_DEFAULT_TIMEOUT = 15  # 15s máximo para no bloquear ejecuciones en APIs caídas

# ---------------------------------------------------------------------------
# DB Config (local, sin contraseña — entorno de producción controlado)
# ---------------------------------------------------------------------------
_DB_CONFIG = dict(host='localhost', user='root', password='', database='ris',
                  connect_timeout=2)


def get_models_for_context(contexto: str = 'busqueda_ocr') -> list:
    """
    Retorna la lista de modelos permitidos y optimizados para un contexto específico.
    Consulta ris.catalogo_modelos_llm. Si la BD no responde, retorna las listas de respaldo.
    Garantiza alternancia balanceada entre proveedores (NVIDIA NIM y OpenRouter)
    para evitar fallos si un proveedor específico experimenta problemas de red.
    
    Contextos soportados:
      - 'busqueda_ocr': Modelos aptos para matching léxico y OCR en pantalla.
      - 'deteccion_patologia': Modelos con capacidad clínica y coherencia anatómica.
    """
    filtro_col = "apto_patologia" if contexto == "deteccion_patologia" else "apto_ocr"
    try:
        import mysql.connector
        conn = mysql.connector.connect(**_DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        query = f"""
            SELECT modelo, proveedor, tiempo_promedio_ms
            FROM ris.catalogo_modelos_llm 
            WHERE {filtro_col} = 1 AND activo = 1
            ORDER BY tiempo_promedio_ms ASC
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        if rows:
            # Separar por proveedor para garantizar mezcla balanceada (no solo NVIDIA ni solo OpenRouter)
            nv_models = [r['modelo'] for r in rows if r['proveedor'] == 'nvidia']
            or_models = [r['modelo'] for r in rows if r['proveedor'] != 'nvidia']

            # Alternar modelos de ambos proveedores (ej: OpenRouter, Nvidia, OpenRouter, Nvidia...)
            balanced = []
            max_len = max(len(nv_models), len(or_models))
            for i in range(max_len):
                if contexto == "deteccion_patologia":
                    # En patología, priorizar nemotron-3-super-120b (OpenRouter) y llama-3.2-11b (NVIDIA)
                    if i < len(or_models):
                        balanced.append(or_models[i])
                    if i < len(nv_models):
                        balanced.append(nv_models[i])
                else:
                    # En OCR, priorizar modelos rápidos
                    if i < len(nv_models):
                        balanced.append(nv_models[i])
                    if i < len(or_models):
                        balanced.append(or_models[i])

            # Eliminar duplicados preservando orden
            seen = set()
            dedup = []
            for m in balanced:
                if m not in seen:
                    seen.add(m)
                    dedup.append(m)
            return dedup
    except Exception as e:
        logger.debug(f"[llm_config] No se pudo consultar catalogo_modelos_llm ({e}), usando fallback.")

    if contexto == "deteccion_patologia":
        return list(PATOLOGIA_DEFAULT_MODELS)
    return list(OCR_DEFAULT_MODELS)


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
        base_list: lista de model IDs a reordenar. Si None, consulta get_models_for_context(contexto).
        contexto:  tipo de tarea para filtrar el ranking ('busqueda_ocr',
                   'deteccion_patologia', etc.)

    Returns:
        Lista reordenada de model IDs (lista nueva, no modifica base_list).
    """
    if base_list is None:
        base_list = get_models_for_context(contexto=contexto)

    offline_models = set()
    try:
        import mysql.connector
        from datetime import datetime, timedelta
        conn = mysql.connector.connect(**_DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        
        # 1. Obtener estadísticas históricas
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
        stats = {r['modelo']: r for r in rows}
        
        # 2. Detectar modelos caídos recientemente (últimas 24 horas con intentos pero 0 éxitos)
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            SELECT 
                modelo,
                SUM(es_match) AS recent_exitos,
                COUNT(*) AS recent_intentos
            FROM ris.log_llm_ranking
            WHERE timestamp >= %s AND contexto = %s
            GROUP BY modelo
        """, (yesterday, contexto))
        recent_rows = cursor.fetchall()
        for r in recent_rows:
            if r['recent_intentos'] > 0 and int(r['recent_exitos'] or 0) == 0:
                offline_models.add(r['modelo'])
                
        conn.close()
    except Exception as e:
        logger.debug(f"[llm_config] DB no disponible para ranking ({e}), usando orden base.")
        return list(base_list)

    def _score(model_id):
        base_url, target_key, provider = get_llm_request_params(model_id)
        provider_priority = 0 if provider == "nvidia" else 1

        if model_id not in stats:
            # Modelo sin historial: score neutro (50%), tiempo asumido 5s
            return (0, provider_priority, -0.5, 5000.0)

        r = stats[model_id]
        exitos  = int(r['exitos'] or 0)
        intentos = int(r['intentos'] or 0)
        tiempo  = float(r['tiempo_prom_ms'] or 5000.0)

        # Si el modelo está en offline_models o está completamente roto históricamente (exitos == 0 y intentos > 0),
        # lo mandamos al final (is_broken = 1). De lo contrario, is_broken = 0.
        is_broken = 1 if (model_id in offline_models or (exitos == 0 and intentos > 0)) else 0

        laplace = (exitos + 1) / (intentos + 2)
        # Retorna tupla para sort:
        # 1. is_broken ASC (0 no rotos, 1 rotos)
        # 2. provider_priority ASC (nvidia=0, openrouter=1)
        # 3. score DESC (negado)
        # 4. tiempo ASC
        return (is_broken, provider_priority, -laplace, tiempo)

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
    proveedor: str = "openrouter",
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
        proveedor:         API que sirvió la consulta ('openrouter', 'nvidia', etc.)
    """
    try:
        import mysql.connector
        conn = mysql.connector.connect(**_DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ris.log_llm_ranking
              (id_registro, modelo, target_buscado, texto_ocr,
               es_match, razonamiento, confianza, tiempo_ms,
               es_primer_intento, contexto, proveedor)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
            proveedor,
        ))
        conn.commit()
        conn.close()
        logger.debug(
            f"[log_llm_result] {modelo} | match={es_match} | "
            f"conf={confianza:.2f} | {tiempo_ms}ms | primer={es_primer_intento} | ctx={contexto} | prov={proveedor}"
        )
    except Exception as e:
        logger.warning(f"[log_llm_result] No se pudo registrar en DB: {e}")
