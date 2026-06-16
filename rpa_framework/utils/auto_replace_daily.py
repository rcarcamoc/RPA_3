# -*- coding: utf-8 -*-
"""
auto_replace_daily.py
=====================
Script de fondo para verificar y actualizar automáticamente la lista de modelos LLM.
Diseñado para ejecutarse una vez al día.
"""

import os
import sys
import json
import time
import re
import requests
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Configuración de rutas
UTILS_DIR = Path(__file__).parent.resolve()
ROOT_DIR = UTILS_DIR.parent.parent
CONFIG_FILE = UTILS_DIR / "llm_config.py"
ENV_FILE = ROOT_DIR / ".env"
TIMESTAMP_FILE = UTILS_DIR / "last_llm_update.txt"

# Cargar variables de entorno
load_dotenv(ENV_FILE, override=True)
API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# Reconfigurar codificación de consola para Windows
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

def check_should_run(force=False):
    """Retorna True si han pasado más de 24 horas desde la última ejecución."""
    if force:
        return True
    if not TIMESTAMP_FILE.exists():
        return True
    try:
        with open(TIMESTAMP_FILE, "r") as f:
            ts_str = f.read().strip()
        last_run = datetime.fromisoformat(ts_str)
        elapsed = datetime.now() - last_run
        return elapsed >= timedelta(hours=24)
    except Exception as e:
        log(f"Error leyendo timestamp, se ejecutará validación: {e}")
        return True

def save_timestamp():
    """Guarda la fecha y hora actuales como última ejecución exitosa."""
    try:
        with open(TIMESTAMP_FILE, "w") as f:
            f.write(datetime.now().isoformat())
    except Exception as e:
        log(f"Error guardando timestamp: {e}")

def run_daily_update(force=False):
    if not API_KEY:
        log("❌ Error: OPENROUTER_API_KEY no encontrada.")
        return False

    if not check_should_run(force):
        log("📅 La verificación diaria ya se realizó en las últimas 24 horas. Omitiendo.")
        return True

    log("🚀 Iniciando verificación diaria de vigencia de modelos LLM...")

    # Importar BASE_LLM_MODELS
    try:
        sys.path.insert(0, str(ROOT_DIR))
        import rpa_framework.utils.llm_config as llm_cfg
        current_models = list(llm_cfg.BASE_LLM_MODELS)
    except Exception as e:
        log(f"❌ Error importando llm_config: {e}")
        return False

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type":  "application/json",
        "HTTP-Referer":  "https://rpa-framework.local",
    }

    # 1. Validar modelos actuales
    log("🔍 Paso 1: Validando modelos actuales...")
    current_status = {}
    for m in current_models:
        url = "https://openrouter.ai/api/v1/chat/completions"
        payload = {
            "model": m,
            "messages": [{"role": "user", "content": "Di solo: OK"}],
            "max_tokens": 10,
            "temperature": 0.0,
        }
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=8)
            current_status[m] = (r.status_code == 200)
        except Exception:
            current_status[m] = False

    offline_models = [m for m, active in current_status.items() if not active]
    if not offline_models:
        log("✅ Todos los modelos actuales están online. No se requieren cambios.")
        save_timestamp()
        return True

    log(f"❌ Modelos caídos detectados ({len(offline_models)}): {offline_models}")

    # 2. Descargar todos los modelos libres de OpenRouter
    log("📥 Paso 2: Descargando lista de modelos de OpenRouter...")
    try:
        r = requests.get("https://openrouter.ai/api/v1/models", timeout=10)
        if r.status_code != 200:
            log(f"Error descargando modelos: HTTP {r.status_code}")
            return False
        all_models = r.json().get("data", [])
    except Exception as e:
        log(f"Excepción descargando modelos: {e}")
        return False

    free_models = {}
    for m in all_models:
        pricing = m.get("pricing", {})
        prompt = float(pricing.get("prompt", 0))
        completion = float(pricing.get("completion", 0))
        if prompt == 0 and completion == 0:
            free_models[m["id"]] = m
            if m.get("canonical_slug"):
                free_models[m["canonical_slug"]] = m

    # 3. Descargar datasets de rankings diarios de OpenRouter
    log("📊 Paso 3: Descargando rankings de uso semanal...")
    try:
        r = requests.get("https://openrouter.ai/api/v1/datasets/rankings-daily", headers=headers, timeout=10)
        if r.status_code != 200:
            log(f"Error descargando rankings: HTTP {r.status_code}")
            return False
        rankings = r.json().get("data", [])
    except Exception as e:
        log(f"Excepción descargando rankings: {e}")
        return False

    dates = sorted(list(set(item.get("date") for item in rankings)), reverse=True)
    if not dates:
        log("El dataset de rankings no contiene fechas válidas.")
        return False

    latest_date_str = dates[0]
    latest_date = datetime.strptime(latest_date_str, "%Y-%m-%d")
    start_date = latest_date - timedelta(days=7)
    start_date_str = start_date.strftime("%Y-%m-%d")

    usage = {}
    for item in rankings:
        d_str = item.get("date")
        if not d_str or d_str < start_date_str:
            continue
        slug = item.get("model_permaslug")
        tokens = int(item.get("total_tokens", 0))

        matched = None
        if slug in free_models:
            matched = free_models[slug]
        else:
            for m_id, m_info in free_models.items():
                if m_id in slug or slug in m_id:
                    matched = m_info
                    break
        if matched:
            model_id = matched["id"]
            usage[model_id] = usage.get(model_id, 0) + tokens

    sorted_popular_free = [m_id for m_id, _ in sorted(usage.items(), key=lambda x: x[1], reverse=True)]

    # 4. Validar candidatos populares usando un PROMPT CLÍNICO REAL
    log("🩺 Paso 4: Validando candidatos con prompt clínico...")
    validated_candidates = []
    prompt_clinico = """
    Determina si el siguiente texto coincide con el examen de forma semántica.
    BUSCADO: "RESONANCIA MAGNÉTICA DE COLUMNA LUMBAR"
    ENCONTRADO: "28-04-2026 Examen Hecho RM de Columna Lumbar"
    Responde ÚNICAMENTE en formato JSON:
    {"es_match": true, "confianza": 1.0}
    """

    for cand in sorted_popular_free[:10]:
        if cand in current_models and current_status.get(cand, False):
            continue
        
        url = "https://openrouter.ai/api/v1/chat/completions"
        payload = {
            "model": cand,
            "messages": [{"role": "user", "content": prompt_clinico}],
            "max_tokens": 50,
            "temperature": 0.0,
        }
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=8)
            if r.status_code == 200:
                content = r.json()['choices'][0]['message'].get('content', '')
                if "es_match" in content:
                    validated_candidates.append(cand)
                    log(f"  ✅ Candidato VÁLIDO: {cand}")
                else:
                    log(f"  ⚠️ Candidato RECHAZADO (no JSON): {cand}")
        except Exception:
            pass

    # 5. Realizar el reemplazo de los caídos
    log("⚡ Paso 5: Reemplazando modelos caídos...")
    new_models = []
    cand_idx = 0

    for m in current_models:
        if current_status.get(m, False):
            new_models.append(m)
        else:
            replaced = False
            while cand_idx < len(validated_candidates):
                cand = validated_candidates[cand_idx]
                cand_idx += 1
                if cand not in current_models and cand not in new_models:
                    new_models.append(cand)
                    log(f"🔄 Reemplazado '{m}' por '{cand}'")
                    replaced = True
                    break
            if not replaced:
                new_models.append(m)

    # 6. Escribir cambios en llm_config.py
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            content = f.read()

        new_list = "BASE_LLM_MODELS = [\n"
        for i, model in enumerate(new_models):
            role = "Primario" if i == 0 else f"Fallback {i}"
            line = f'   "{model}",'
            new_list += f"{line:<60} # {role} — Validado OK\n"
        new_list += "]"

        updated, count = re.subn(
            r"BASE_LLM_MODELS\s*=\s*\[.*?\]", new_list, content, flags=re.DOTALL
        )
        if count > 0:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                f.write(updated)
            log("💾 Archivo llm_config.py actualizado exitosamente con la lista diaria.")
        else:
            log("❌ No se pudo actualizar el archivo llm_config.py.")
    except Exception as e:
        log(f"❌ Error actualizando archivo de configuración: {e}")
        return False

    save_timestamp()
    return True

if __name__ == "__main__":
    force_run = "--force" in sys.argv
    run_daily_update(force=force_run)
