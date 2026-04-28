"""
llm_config.py
=============
Configuración centralizada de modelos LLM para todos los scripts del RPA Framework.

Para cambiar los modelos utilizados en TODOS los scripts, sólo edita esta lista.
Los modelos se intentan en orden; si uno falla (429, 404, error de red), se prueba el siguiente.

Modelos disponibles en OpenRouter (https://openrouter.ai):
  - arcee-ai/trinity-large-preview:free
  - qwen/qwen3-235b-a22b-thinking-2507
  - nvidia/nemotron-3-nano-30b-a3b:free
  - z-ai/glm-4.5-air:free
"""

# ---------------------------------------------------------------------------
# URL base de la API de OpenRouter (no cambiar)
# ---------------------------------------------------------------------------
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# ---------------------------------------------------------------------------
# Lista PRINCIPAL de modelos LLM (orden de prioridad / fallback)
#
# Reglas:
#   1. El primer modelo es el preferido.
#   2. Si devuelve 429 (cuota) o 404 (no disponible), se intenta el siguiente.
#   3. Si todos fallan, el script reporta error.
# ---------------------------------------------------------------------------
LLM_MODELS = [
   "google/gemma-4-31b-it:free"
   "qwen/qwen3-235b-a22b-thinking-2507",
   "nvidia/nemotron-3-nano-30b-a3b:free",
   "arcee-ai/trinity-large-preview:free",
   "stepfun/step-3.5-flash:free",
]

# ---------------------------------------------------------------------------
# Modelo principal (alias conveniente para scripts que usan un solo modelo)
# ---------------------------------------------------------------------------
LLM_MODEL_PRIMARY = LLM_MODELS[0]

# ---------------------------------------------------------------------------
# Parámetros de llamada por defecto (pueden sobrescribirse en cada script)
# ---------------------------------------------------------------------------
LLM_DEFAULT_TEMPERATURE = 0.0
LLM_DEFAULT_MAX_TOKENS = 800
LLM_DEFAULT_TIMEOUT = 30  # segundos
