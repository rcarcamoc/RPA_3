# -*- coding: utf-8 -*-
"""
validator_candidates.py
=======================
Obtención de modelos candidatos de Nvidia NIM y OpenRouter Free y
lectura/escritura atómica de llm_config.py. Extraído de utils/llm_validator.py.
"""

import os
import re
from .validator_probes import CONFIG_FILE, FALLBACK_POPULAR_FREE


def get_popular_nvidia_candidates(nvidia_key, openrouter_key):
    """
    Descarga los modelos disponibles en Nvidia NIM y los ordena 
    según la popularidad de uso registrada en OpenRouter.
    """
    import requests
    from datetime import datetime, timedelta
    
    nvidia_models = []
    try:
        headers = {"Authorization": f"Bearer {nvidia_key}"}
        r = requests.get("https://integrate.api.nvidia.com/v1/models", headers=headers, timeout=10)
        if r.status_code == 200:
            exclude_keywords = [
                "embed", "rerank", "parse", "pii", "clip", "translation", "translate", 
                "reward", "safety", "guard", "diffusion", "deplot", "fuyu", "vila", "detector", "calibration"
            ]
            include_keywords = [
                "instruct", "-it", "chat", "large", "medium", "small", "pro", "flash", "nemotron"
            ]
            for m in r.json().get("data", []):
                m_id = m["id"]
                m_lower = m_id.lower()
                if any(kw in m_lower for kw in exclude_keywords):
                    continue
                if any(kw in m_lower for kw in include_keywords):
                    nvidia_models.append(m_id)
    except Exception as e:
        print(f"[llm_validator] Error obteniendo catalogo de Nvidia: {e}")
        return []
        
    if not nvidia_models:
        return []
        
    openrouter_rankings = []
    try:
        headers = {
            "Authorization": f"Bearer {openrouter_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://rpa-framework.local",
        }
        r = requests.get("https://openrouter.ai/api/v1/datasets/rankings-daily", headers=headers, timeout=10)
        if r.status_code == 200:
            openrouter_rankings = r.json().get("data", [])
    except Exception as e:
        print(f"[llm_validator] Error obteniendo rankings de OpenRouter: {e}")
        
    if not openrouter_rankings:
        known_good = [
            "meta/llama-3.3-70b-instruct",
            "nvidia/llama-3.1-nemotron-70b-instruct",
            "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
            "google/gemma-3-12b-it",
            "google/gemma-4-31b-it",
            "meta/llama-3.1-70b-instruct",
            "openai/gpt-oss-120b"
        ]
        return [m for m in known_good if m in nvidia_models] + [m for m in nvidia_models if m not in known_good]

    def normalize(model_id):
        base = model_id.split(":")[0]
        base = base.replace("meta-llama/", "meta/")
        base = base.replace("nv-mistralai/", "mistralai/")
        return base.lower()

    nvidia_map = {}
    for m in nvidia_models:
        norm = normalize(m)
        nvidia_map[norm] = m

    usage = {}
    dates = sorted(list(set(item.get("date") for item in openrouter_rankings if item.get("date"))), reverse=True)
    if dates:
        latest_date = datetime.strptime(dates[0], "%Y-%m-%d")
        start_date = latest_date - timedelta(days=7)
        start_date_str = start_date.strftime("%Y-%m-%d")
        
        for item in openrouter_rankings:
            d_str = item.get("date")
            if not d_str or d_str < start_date_str:
                continue
            slug = item.get("model_permaslug")
            tokens = int(item.get("total_tokens", 0))
            
            norm_slug = normalize(slug)
            if norm_slug in nvidia_map:
                real_id = nvidia_map[norm_slug]
                usage[real_id] = usage.get(real_id, 0) + tokens

    sorted_nvidia = [m for m, _ in sorted(usage.items(), key=lambda x: x[1], reverse=True)]
    
    for m in nvidia_models:
        if m not in sorted_nvidia:
            sorted_nvidia.append(m)
            
    return sorted_nvidia


def get_popular_free_candidates(api_key):
    """Descarga los modelos populares gratuitos de OpenRouter."""
    import requests
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://rpa-framework.local",
    }
    
    free_models = {}
    try:
        r = requests.get("https://openrouter.ai/api/v1/models", timeout=10)
        if r.status_code == 200:
            all_models = r.json().get("data", [])
            for m in all_models:
                pricing = m.get("pricing", {})
                prompt = float(pricing.get("prompt", 0))
                completion = float(pricing.get("completion", 0))
                if prompt == 0 and completion == 0:
                    free_models[m["id"]] = m
                    if m.get("canonical_slug"):
                        free_models[m["canonical_slug"]] = m
        else:
            print(f"[llm_validator] Error catalogo modelos: HTTP {r.status_code}")
    except Exception as e:
        print(f"[llm_validator] Error conectando a catalogo: {e}")
        
    candidates = []
    try:
        r = requests.get("https://openrouter.ai/api/v1/datasets/rankings-daily", headers=headers, timeout=10)
        if r.status_code == 200:
            rankings = r.json().get("data", [])
            from datetime import datetime, timedelta
            dates = sorted(list(set(item.get("date") for item in rankings if item.get("date"))), reverse=True)
            if dates:
                latest_date = datetime.strptime(dates[0], "%Y-%m-%d")
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
                        
                sorted_usage = sorted(usage.items(), key=lambda x: x[1], reverse=True)
                candidates = [m_id for m_id, _ in sorted_usage]
        else:
            print(f"[llm_validator] Error rankings: HTTP {r.status_code}")
    except Exception as e:
        print(f"[llm_validator] Error conectando a rankings: {e}")
        
    for fb in FALLBACK_POPULAR_FREE:
        if fb not in candidates:
            candidates.append(fb)
            
    return candidates


def read_models_from_config():
    """Lee y extrae BASE_LLM_MODELS de llm_config.py usando expresiones regulares."""
    try:
        if not CONFIG_FILE.exists():
            return []
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        match = re.search(r"BASE_LLM_MODELS\s*=\s*\[(.*?)\]", content, re.DOTALL)
        if match:
            block = match.group(1)
            models = re.findall(r'"([^"]+)"|\'([^\']+)\'', block)
            return [m[0] or m[1] for m in models]
    except Exception as e:
        print(f"[llm_validator] Error leyendo llm_config.py: {e}")
    return []


def update_llm_config_file(active_models):
    """Guarda la lista de modelos de forma atomica en llm_config.py."""
    try:
        if not CONFIG_FILE.exists():
            return False
            
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            content = f.read()
            
        new_list = "BASE_LLM_MODELS = [\n"
        for i, model in enumerate(active_models):
            role = "Primario" if i == 0 else f"Fallback {i}"
            line = f'   "{model}",'
            new_list += f"{line:<60} # {role} - Validado OK\n"
        new_list += "]"
        
        updated, count = re.subn(
            r"BASE_LLM_MODELS\s*=\s*\[.*?\]", new_list, content, flags=re.DOTALL
        )
        if count == 0:
            updated, count = re.subn(
                r"LLM_MODELS\s*=\s*\[.*?\]", new_list.replace("BASE_LLM_MODELS", "LLM_MODELS"), content, flags=re.DOTALL
            )
            
        if count > 0:
            tmp_path = CONFIG_FILE.with_suffix(".py.tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(updated)
            
            os.replace(tmp_path, CONFIG_FILE)
            print(f"[llm_validator] llm_config.py actualizado automaticamente con {len(active_models)} modelos.")
            return True
    except Exception as e:
        print(f"[llm_validator] Error escribiendo config: {e}")
    return False
