#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script: update_and_validate_models.py
Descripción: Realiza una consulta rápida a OpenRouter para verificar qué modelos 
de una lista de candidatos están activos (devuelven HTTP 200).
Los modelos validados se guardan y actualizan automáticamente en llm_config.py.
"""

import os
import sys
import re
import requests
from pathlib import Path
from dotenv import load_dotenv

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

# Configuración de rutas
UTILS_DIR = Path(__file__).parent
RPA_DIR = UTILS_DIR.parent
ROOT_DIR = RPA_DIR.parent
CONFIG_FILE = UTILS_DIR / "llm_config.py"
ENV_FILE = ROOT_DIR / ".env"

if str(RPA_DIR) not in sys.path:
    sys.path.insert(0, str(RPA_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Cargar variables de entorno
load_dotenv(ENV_FILE, override=True)
API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# Lista de modelos candidata por defecto (5 Nvidia NIM + 5 OpenRouter Free)
DEFAULT_CANDIDATES = [
    "meta/llama-3.1-8b-instruct",
    "nvidia/llama-3.3-nemotron-super-49b-v1",
    "nvidia/nemotron-nano-12b-v2-vl:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "meta/llama-3.2-11b-vision-instruct",
    "nvidia/nemotron-nano-12b-v2-vl",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "openrouter/free",
]

def check_model(model_id):
    """Verifica si el modelo está activo en su respectivo proveedor (Nvidia NIM u OpenRouter)."""
    try:
        from utils.llm_config import get_llm_request_params
        base_url, target_key, provider = get_llm_request_params(model_id)
    except Exception:
        base_url = "https://openrouter.ai/api/v1"
        target_key = API_KEY
        provider = "openrouter"

    if not target_key:
        target_key = API_KEY

    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {target_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://rpa-framework.local",
    }
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": "Di solo la palabra: OK"}],
        "max_tokens": 250,
        "temperature": 0.0,
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        if response.status_code == 200:
            return True, f"Online ({provider.upper()})"
        else:
            try:
                err_msg = response.json().get("error", {}).get("message", f"HTTP {response.status_code}")
            except Exception:
                err_msg = f"HTTP {response.status_code}"
            return False, err_msg
    except Exception as e:
        return False, str(e)

def update_config_file(active_models):
    """Actualiza la lista BASE_LLM_MODELS en llm_config.py."""
    if not CONFIG_FILE.exists():
        print(f"❌ Error: No se encontró el archivo de configuración en {CONFIG_FILE}")
        return False

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    # Formatear la nueva lista de modelos para escribir
    new_list_str = "BASE_LLM_MODELS = [\n"
    for i, model in enumerate(active_models):
        role = "Primario" if i == 0 else f"Fallback {i}"
        line = f'   "{model}",'
        comment = f"# {role} — Validado OK"
        new_list_str += f"{line:<60} {comment}\n"
    new_list_str += "]"

    # Usar expresiones regulares para reemplazar el bloque de BASE_LLM_MODELS
    pattern = r"BASE_LLM_MODELS\s*=\s*\[.*?\]"
    modified_content, count = re.subn(pattern, new_list_str, content, flags=re.DOTALL)

    if count == 0:
        print("❌ Error: No se pudo localizar la variable LLM_MODELS en llm_config.py")
        return False

    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        f.write(modified_content)

    return True

def main():
    if not API_KEY:
        print("❌ Error: OPENROUTER_API_KEY no está definida en el archivo .env")
        sys.exit(1)

    # Si se pasan modelos por argumento, usarlos; de lo contrario usar por defecto
    candidates = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_CANDIDATES

    print(f"🔍 Validando {len(candidates)} modelos contra OpenRouter...")
    print("=" * 70)

    active_models = []
    for model in candidates:
        print(f"Testing {model:<55} ... ", end="", flush=True)
        is_ok, msg = check_model(model)
        if is_ok:
            print("✅ ONLINE")
            active_models.append(model)
        else:
            print(f"❌ OFFLINE ({msg})")

    print("=" * 70)
    if not active_models:
        print("⚠️ Advertencia: ¡Ningún modelo de la lista está activo! No se actualizará llm_config.py.")
        sys.exit(1)

    print(f"📝 Modelos activos detectados ({len(active_models)}):")
    for m in active_models:
        print(f" - {m}")

    print("\n✍️ Actualizando llm_config.py...")
    if update_config_file(active_models):
        print("✅ Archivo llm_config.py actualizado correctamente.")
    else:
        print("❌ Error al actualizar llm_config.py.")

if __name__ == "__main__":
    main()
