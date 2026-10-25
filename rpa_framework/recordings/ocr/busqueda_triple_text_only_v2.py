#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script: busqueda_triple_text_only_v2.py
Descripción: Script de búsqueda optimizado v2 (con precarga en segundo plano y pausa reducida)
para validación semántica de texto en visor PACS.

Ubicación: rpa_framework/recordings/ocr/busqueda_triple_text_only_v2.py
Refactorizado de forma modular junto con rpa_framework/recordings/ocr/triple_search/.
"""

import sys
import os
import time
import logging
import subprocess
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from utils.logging_setup import setup_logging
from utils.telegram_manager import enviar_alerta_todos
from utils.llm_config import (
    OPENROUTER_BASE_URL, BASE_LLM_MODELS, LLM_MODELS,
    LLM_DEFAULT_TEMPERATURE, LLM_DEFAULT_MAX_TOKENS, LLM_DEFAULT_TIMEOUT,
    get_ranked_models, log_llm_result, get_llm_request_params,
)

from recordings.ocr.triple_search import (
    HAS_MYSQL,
    HAS_PREPROCESS_UTILS,
    MIN_FUZZY_FOR_LLM,
    LLM_MIN_CONFIDENCE,
    _CIRCUIT_BREAKER_DOWN_MODELS,
)
from recordings.ocr.busqueda_triple_text_only import (
    BusquedaTextOnly as _BaseBusquedaTextOnly,
    OPENROUTER_API_KEY,
    MODEL_ID,
)

logger = logging.getLogger(__name__)


class BusquedaTextOnly(_BaseBusquedaTextOnly):
    """Versión v2 de BusquedaTextOnly con pausa post-clic reducida (1.2s)."""

    def __init__(self):
        super().__init__()
        self.POST_CLICK_SLEEP = 1.2


def disparar_precarga_fondo():
    """Dispara la extracción en segundo plano del próximo examen en RIS (pipeline)."""
    try:
        script_precarga = Path(__file__).parent.parent / "web" / "precargar_proximo_examen_ris.py"
        if script_precarga.exists():
            cflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            subprocess.Popen([sys.executable, str(script_precarga)], creationflags=cflags)
            logger.info("🚀 [PIPELINE v2] Precarga en segundo plano del PRÓXIMO examen iniciada.")
    except Exception as e:
        logger.warning(f"Aviso disparando precarga en segundo plano: {e}")


def main():
    time.sleep(0.1)  # Pausa mínima v2
    setup_logging()
    disparar_precarga_fondo()

    while True:
        search = BusquedaTextOnly()

        id_registro, target_diag_raw, _ = search.get_db_targets()
        override_diag = None
        last_ocr_text = ""

        if target_diag_raw:
            sinonimo = search.buscar_sinonimo(target_diag_raw, "")
            if sinonimo:
                if search.auditor:
                    aprobado, razon, _ = search.auditor.auditar(
                        target_diag=target_diag_raw,
                        ocr_candidato=sinonimo,
                        metodo="sinonimo_bd",
                        score=100
                    )
                    if aprobado:
                        logger.info(f"📚 Sinónimo validado por Auditor Clínico: '{sinonimo}'. Se usará en lugar de '{target_diag_raw}'.")
                        override_diag = sinonimo
                    else:
                        logger.warning(f"🚫 Sinónimo en BD '{sinonimo}' RECHAZADO por Auditor Clínico ({razon}). Se mantiene original: '{target_diag_raw}'.")
                else:
                    logger.info(f"📚 Sinónimo hallado en BD: '{sinonimo}'. Se usará en lugar de '{target_diag_raw}'.")
                    override_diag = sinonimo

        found = False
        for attempt in range(search.MAX_RETRIES + 1):
            attempt_num = attempt + 1
            logger.info(f"{'='*60}")
            logger.info(f"INTENTO {attempt_num} DE {search.MAX_RETRIES + 1}")
            logger.info(f"{'='*60}")

            try:
                result, last_ocr_text = search.execute(override_diag=override_diag)

                if result:
                    logger.info("✅ Proceso completado exitosamente")
                    found = True
                    break
                else:
                    if attempt < search.MAX_RETRIES:
                        logger.warning(f"⚠️ Intento {attempt_num} falló. Reintentando...")
                        time.sleep(2)
            except Exception as e:
                logger.error(f"Error durante ejecución: {e}", exc_info=True)
                if attempt < search.MAX_RETRIES:
                    time.sleep(2)

        if found:
            sys.exit(0)

        logger.warning("⚠️ Todos los reintentos fallaron. Notificando y terminando.")
        if getattr(search, 'last_diagnostic', None):
            error_msg = f"Búsqueda fallida: {search.last_diagnostic} (tras {search.MAX_RETRIES + 1} intentos)."
        else:
            error_msg = f"Búsqueda fallida: no se encontró '{target_diag_raw}' (OCR detectó: '{last_ocr_text}') tras {search.MAX_RETRIES + 1} intentos."

        _error_handler_llamado = False
        for _mod in ['utils.error_handler', 'rpa_framework.utils.error_handler']:
            try:
                import importlib
                _eh = importlib.import_module(_mod)
                _eh.handle_error_and_exit("busqueda_triple_text_only.py", error_msg)
                _error_handler_llamado = True
                break
            except Exception as _e:
                logger.warning(f"No se pudo importar {_mod}: {_e}")
        
        if not _error_handler_llamado:
            try:
                enviar_alerta_todos(f"❌ <b>Búsqueda Fallida</b>\n{error_msg}")
            except Exception:
                pass
            search.update_db_error(error_msg)
            sys.exit(1)


if __name__ == "__main__":
    main()
