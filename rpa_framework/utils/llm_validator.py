# -*- coding: utf-8 -*-
"""
llm_validator.py
================
Verificación automática y silenciosa de modelos LLM al inicio de la aplicación.
Evalúa los modelos con una batería de abreviaciones clínicas y realiza
el reemplazo automático por modelos populares gratuitos si alguno falla.

Refactorizado de forma modular en rpa_framework/utils/llm/ manteniendo 100% compatibilidad.
"""

from .llm.validator_probes import (
    UTILS_DIR,
    CONFIG_FILE,
    DEFAULT_TEST_CASES,
    FALLBACK_POPULAR_FREE,
    get_recently_active_models,
    get_recently_failed_models,
    is_nvidia_model,
    get_abbreviation_test_cases,
    test_model_case,
    evaluate_model,
)
from .llm.validator_candidates import (
    get_popular_nvidia_candidates,
    get_popular_free_candidates,
    read_models_from_config,
    update_llm_config_file,
)
from .llm.validator_runner import (
    _validation_and_update_flow,
    run_background_llm_validation,
)

__all__ = [
    "UTILS_DIR",
    "CONFIG_FILE",
    "DEFAULT_TEST_CASES",
    "FALLBACK_POPULAR_FREE",
    "get_recently_active_models",
    "get_recently_failed_models",
    "is_nvidia_model",
    "get_abbreviation_test_cases",
    "test_model_case",
    "evaluate_model",
    "get_popular_nvidia_candidates",
    "get_popular_free_candidates",
    "read_models_from_config",
    "update_llm_config_file",
    "_validation_and_update_flow",
    "run_background_llm_validation",
]


# Para pruebas unitarias o ejecucion standalone
if __name__ == "__main__":
    print("--- MODO DE PRUEBAS STANDALONE ---")
    _validation_and_update_flow()
