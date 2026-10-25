# -*- coding: utf-8 -*-
"""Subpaquete de gestión, validación y autoreemplazo de modelos LLM."""

from .auto_config_store import (
    UTILS_DIR,
    ROOT_DIR,
    CONFIG_DIR,
    CONFIG_FILE,
    ENV_FILE,
    AUTO_CONFIG_FILE,
    LOG_HISTORIAL_FILE,
    TIMESTAMP_FILE,
    get_default_config,
    load_auto_config,
    save_auto_config,
    load_verification_log,
    save_verification_logs,
    add_verification_log,
    should_run_auto_verification,
    get_llm_status_summary,
)
from .auto_verification_engine import (
    registrar_en_catalogo_bd,
    _agente_clasificar_candidato,
    check_and_refresh_llm_cache,
    run_auto_verification_logic,
)
from .validator_probes import (
    DEFAULT_TEST_CASES,
    FALLBACK_POPULAR_FREE,
    get_recently_active_models,
    get_recently_failed_models,
    is_nvidia_model,
    get_abbreviation_test_cases,
    test_model_case,
    evaluate_model,
)
from .validator_candidates import (
    get_popular_nvidia_candidates,
    get_popular_free_candidates,
    read_models_from_config,
    update_llm_config_file,
)
from .validator_runner import (
    _validation_and_update_flow,
    run_background_llm_validation,
)
