# -*- coding: utf-8 -*-
"""
auto_replace_daily.py
=====================
Script de fondo para verificar y actualizar automáticamente la lista de modelos LLM.
Diseñado para ejecutarse una vez al día (vía CLI o Tarea Programada de Windows).
"""

import sys
from pathlib import Path

# Configuración de rutas
UTILS_DIR = Path(__file__).parent.resolve()
ROOT_DIR = UTILS_DIR.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from rpa_framework.utils.llm_auto_manager import (
    run_auto_verification_logic,
    should_run_auto_verification
)

def run_daily_update(force=False):
    res = run_auto_verification_logic(force=force)
    status = res.get("status", "")
    return status in ["Éxito", "🔄 Reemplazo Realizado", "Omitido"]

if __name__ == "__main__":
    force_run = "--force" in sys.argv
    run_daily_update(force=force_run)
