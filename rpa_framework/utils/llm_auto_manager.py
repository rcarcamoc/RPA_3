# -*- coding: utf-8 -*-
"""
llm_auto_manager.py
===================
Módulo de gestión centralizada para la autoverificación diaria, reemplazo de modelos LLM
y persistencia del historial de los últimos 5 días.

Refactorizado de forma modular en rpa_framework/utils/llm/ manteniendo 100% compatibilidad.
"""

from .llm.auto_config_store import (
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
from .llm.auto_verification_engine import (
    registrar_en_catalogo_bd,
    _agente_clasificar_candidato,
    check_and_refresh_llm_cache,
    run_auto_verification_logic,
)

__all__ = [
    "UTILS_DIR",
    "ROOT_DIR",
    "CONFIG_DIR",
    "CONFIG_FILE",
    "ENV_FILE",
    "AUTO_CONFIG_FILE",
    "LOG_HISTORIAL_FILE",
    "TIMESTAMP_FILE",
    "get_default_config",
    "load_auto_config",
    "save_auto_config",
    "load_verification_log",
    "save_verification_logs",
    "add_verification_log",
    "should_run_auto_verification",
    "get_llm_status_summary",
    "registrar_en_catalogo_bd",
    "_agente_clasificar_candidato",
    "check_and_refresh_llm_cache",
    "run_auto_verification_logic",
]
