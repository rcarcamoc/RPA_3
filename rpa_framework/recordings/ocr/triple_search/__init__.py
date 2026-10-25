# -*- coding: utf-8 -*-
"""Subpaquete modular para BusquedaTextOnly (busqueda_triple_text_only.py y v2)."""

from .db_and_synonyms_mixin import HAS_MYSQL, TripleSearchDBMixin
from .medical_text_mixin import HAS_PREPROCESS_UTILS, TripleSearchMedicalTextMixin
from .llm_cascade_mixin import (
    MIN_FUZZY_FOR_LLM,
    LLM_MIN_CONFIDENCE,
    _CIRCUIT_BREAKER_DOWN_MODELS,
    TripleSearchLLMCascadeMixin,
)
from .candidates_and_diagnostics_mixin import TripleSearchCandidatesMixin
from .visual_and_click_mixin import TripleSearchVisualClickMixin

__all__ = [
    "HAS_MYSQL",
    "HAS_PREPROCESS_UTILS",
    "MIN_FUZZY_FOR_LLM",
    "LLM_MIN_CONFIDENCE",
    "_CIRCUIT_BREAKER_DOWN_MODELS",
    "TripleSearchDBMixin",
    "TripleSearchMedicalTextMixin",
    "TripleSearchLLMCascadeMixin",
    "TripleSearchCandidatesMixin",
    "TripleSearchVisualClickMixin",
]
