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

# Configuración de rutas
UTILS_DIR = Path(__file__).parent
ROOT_DIR = UTILS_DIR.parent.parent
CONFIG_FILE = UTILS_DIR / "llm_config.py"
ENV_FILE = ROOT_DIR / ".env"

# Cargar variables de entorno
load_dotenv(ENV_FILE, override=True)
API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# Lista de modelos candidata por defecto
DEFAULT_CANDIDATES = [
    "google/gemma-4-31b-it:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
    "openai/gpt-oss-120b:free",
    "openrouter/owl-alpha",
    "meta-llama/llama-3.3-70b-instruct:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "qwen/qwen3-235b-a22b-thinking-2507",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "google/gemma-4-26b-a4b-it:free",
    "meta-llama/llama-3.2-3b-instruct:free",
]

def check_model(model_id):
    """Verifica si el modelo está activo en OpenRouter."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://rpa-framework.local",
    }
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": "Di solo la palabra: OK"}],
        "max_tokens": 10,
        "temperature": 0.0,
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            return True, "Online"
        else:
            try:
                err_msg = response.json().get("error", {}).get("message", "Error desconocido")
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
