#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
check_models_openrouter.py
Script temporal para verificar si los modelos de llm_config.py están activos en OpenRouter.
"""

import os
import sys
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

# --- Setup path ---
ROOT_DIR = Path(__file__).parent.parent.parent
load_dotenv(ROOT_DIR / ".env", override=True)

API_KEY = os.getenv("OPENROUTER_API_KEY", "")
BASE_URL = "https://openrouter.ai/api/v1"

# Modelos actuales en llm_config.py
LLM_MODELS = [
    "google/gemma-4-31b-it:free",
    "qwen/qwen3-235b-a22b-thinking-2507",
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "arcee-ai/trinity-large-preview:free",
    "stepfun/step-3.5-flash:free",
]

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
    "HTTP-Referer": "https://rpa-framework.local",
}

def get_available_models():
    """Obtiene todos los modelos disponibles en OpenRouter."""
    try:
        r = requests.get(f"{BASE_URL}/models", headers=HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return {m["id"]: m for m in data.get("data", [])}
        else:
            print(f"❌ Error al obtener lista de modelos: HTTP {r.status_code}")
            return {}
    except Exception as e:
        print(f"❌ Excepción al obtener modelos: {e}")
        return {}

def test_model_call(model_id):
    """Hace una llamada mínima de prueba al modelo."""
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": "Di solo: OK"}],
        "max_tokens": 5,
        "temperature": 0.0,
    }
    try:
        r = requests.post(
            f"{BASE_URL}/chat/completions",
            headers=HEADERS,
            json=payload,
            timeout=20,
        )
        if r.status_code == 200:
            data = r.json()
            reply = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            return "✅ OK", f"Respuesta: '{reply}'"
        elif r.status_code == 429:
            return "⚠️  CUOTA", "Rate limit / cuota excedida"
        elif r.status_code == 404:
            return "❌ NO EXISTE", f"Modelo no encontrado (404)"
        elif r.status_code == 400:
            detail = r.json().get("error", {}).get("message", r.text[:120])
            return "❌ ERROR 400", detail
        else:
            return f"⚠️  HTTP {r.status_code}", r.text[:120]
    except requests.Timeout:
        return "⏱️  TIMEOUT", "Sin respuesta en 20s"
    except Exception as e:
        return "❌ EXCEPCIÓN", str(e)

def main():
    if not API_KEY or API_KEY == "tu_api_key_aqui":
        print("❌ OPENROUTER_API_KEY no configurada en .env")
        sys.exit(1)

    print(f"\n{'='*65}")
    print(f"  VERIFICACIÓN DE MODELOS OPENROUTER")
    print(f"  API Key: {API_KEY[:12]}...{API_KEY[-6:]}")
    print(f"{'='*65}\n")

    # 1. Obtener lista maestra de modelos disponibles
    print("📡 Obteniendo lista de modelos disponibles en OpenRouter...")
    available = get_available_models()
    print(f"   → {len(available)} modelos encontrados en el catálogo.\n")

    # 2. Verificar cada modelo configurado
    results = []
    for model_id in LLM_MODELS:
        in_catalog = model_id in available
        catalog_str = "✅ En catálogo" if in_catalog else "❌ No en catálogo"

        # Si está en catálogo, hacer prueba real
        if in_catalog:
            status, detail = test_model_call(model_id)
        else:
            status, detail = "❌ INACTIVO", "No aparece en el catálogo de OpenRouter"

        results.append({
            "model": model_id,
            "catalog": in_catalog,
            "status": status,
            "detail": detail,
        })

        print(f"  Modelo : {model_id}")
        print(f"  Catálogo: {catalog_str}")
        print(f"  Test    : {status} — {detail}")
        print(f"  {'-'*60}")

    # 3. Resumen
    print(f"\n{'='*65}")
    print("  RESUMEN")
    print(f"{'='*65}")
    ok = [r for r in results if r["status"].startswith("✅")]
    warn = [r for r in results if r["status"].startswith("⚠️")]
    fail = [r for r in results if r["status"].startswith("❌") or r["status"].startswith("⏱️")]

    print(f"  ✅ Funcionales  : {len(ok)}/{len(LLM_MODELS)}")
    print(f"  ⚠️  Con advertencia: {len(warn)}/{len(LLM_MODELS)}")
    print(f"  ❌ Con fallo    : {len(fail)}/{len(LLM_MODELS)}")

    if fail or warn:
        print(f"\n  Modelos que requieren atención:")
        for r in fail + warn:
            print(f"    • {r['model']}  → {r['status']}")

    # 4. Sugerir reemplazos para modelos fallidos (top gratuitos del catálogo)
    if fail and available:
        print(f"\n  💡 Modelos gratuitos disponibles para reemplazar los fallidos:")
        free_models = [
            m for mid, m in available.items()
            if ":free" in mid and mid not in LLM_MODELS
        ]
        # Ordenar por nombre
        free_models = sorted(free_models, key=lambda x: x["id"])[:10]
        for m in free_models:
            ctx = m.get("context_length", "?")
            print(f"    • {m['id']}  (ctx: {ctx})")

    print(f"\n{'='*65}\n")

if __name__ == "__main__":
    main()
