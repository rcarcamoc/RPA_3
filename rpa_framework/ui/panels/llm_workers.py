# -*- coding: utf-8 -*-
"""
llm_workers.py — Workers en segundo plano para validación y autoreemplazo en LLMPanel.
Extraído de ui/panels/llm_panel.py.
"""

import os
from PyQt6.QtCore import QThread, pyqtSignal, QObject


class BackgroundAutoVerificationSignals(QObject):
    log = pyqtSignal(str)
    finished = pyqtSignal(dict)


class BackgroundAutoVerificationWorker(QThread):
    def __init__(self, force=False):
        super().__init__()
        self.force = force
        self.signals = BackgroundAutoVerificationSignals()

    def run(self):
        try:
            from utils.llm_auto_manager import run_auto_verification_logic
            res = run_auto_verification_logic(
                force=self.force,
                log_callback=lambda msg: self.signals.log.emit(msg)
            )
            self.signals.finished.emit(res)
        except Exception as e:
            self.signals.finished.emit({"status": "Error", "message": str(e)})


class ValidationSignals(QObject):
    model_result  = pyqtSignal(str, bool, str)   # model_id, is_ok, msg
    finished      = pyqtSignal(list)              # lista de modelos activos
    log           = pyqtSignal(str)


class ValidationWorker(QThread):
    """Worker para validar el estado básico (HTTP 200) de una lista de modelos."""
    def __init__(self, models: list, api_key: str):
        super().__init__()
        self.models  = models
        self.api_key = api_key
        self.signals = ValidationSignals()

    def run(self):
        import requests
        try:
            from utils.llm_config import get_llm_request_params
        except Exception:
            try:
                from rpa_framework.utils.llm_config import get_llm_request_params
            except Exception:
                def get_llm_request_params(m):
                    return "https://openrouter.ai/api/v1", self.api_key, "openrouter"

        active = []
        for model_id in self.models:
            base_url, target_key, provider = get_llm_request_params(model_id)
            if not target_key:
                target_key = self.api_key
            self.signals.log.emit(f"⏳ Validando {model_id} ({provider.upper()})…")
            url = f"{base_url}/chat/completions"
            headers = {
                "Authorization": f"Bearer {target_key}",
                "Content-Type":  "application/json",
                "HTTP-Referer":  "https://rpa-framework.local",
            }
            payload = {
                "model":       model_id,
                "messages":    [{"role": "user", "content": "Di solo: OK"}],
                "max_tokens":  250,
                "temperature": 0.0,
            }
            try:
                r = requests.post(url, headers=headers, json=payload, timeout=15)
                if r.status_code == 200:
                    self.signals.model_result.emit(model_id, True, f"Online ({provider.upper()})")
                    active.append(model_id)
                else:
                    try:
                        err = r.json().get("error", {}).get("message", f"HTTP {r.status_code}")
                    except Exception:
                        err = f"HTTP {r.status_code}"
                    self.signals.model_result.emit(model_id, False, err[:80])
            except Exception as e:
                self.signals.model_result.emit(model_id, False, str(e)[:80])

        self.signals.finished.emit(active)


class AutoReplaceSignals(QObject):
    log           = pyqtSignal(str)
    finished      = pyqtSignal(list, list) # new_models_list, replacement_log_messages
    error         = pyqtSignal(str)


class AutoReplaceWorker(QThread):
    """Worker que descarga catálogos de Nvidia NIM y OpenRouter, valida y reemplaza los caídos."""
    def __init__(self, current_models: list, api_key: str):
        super().__init__()
        self.current_models = list(current_models)
        self.api_key = api_key
        self.signals = AutoReplaceSignals()

    def run(self):
        import requests
        import concurrent.futures
        from datetime import datetime, timedelta

        try:
            from utils.llm_config import get_llm_request_params
        except Exception:
            try:
                from rpa_framework.utils.llm_config import get_llm_request_params
            except Exception:
                def get_llm_request_params(m):
                    return "https://openrouter.ai/api/v1", self.api_key, "openrouter"

        # 1. Validar primero cuáles de los modelos actuales están caídos
        self.signals.log.emit("🔍 Paso 1: Validando modelos actuales con sus respectivos proveedores...")
        current_status = {}
        for m in self.current_models:
            base_url, target_key, provider = get_llm_request_params(m)
            if not target_key:
                target_key = self.api_key
            self.signals.log.emit(f"  - Probando {m} ({provider.upper()})...")
            url = f"{base_url}/chat/completions"
            headers_call = {
                "Authorization": f"Bearer {target_key}",
                "Content-Type":  "application/json",
                "HTTP-Referer":  "https://rpa-framework.local",
            }
            payload = {
                "model": m,
                "messages": [{"role": "user", "content": "Di solo: OK"}],
                "max_tokens": 250,
                "temperature": 0.0,
            }
            try:
                r = requests.post(url, headers=headers_call, json=payload, timeout=15)
                current_status[m] = (r.status_code == 200)
            except Exception:
                current_status[m] = False

        offline_models = [m for m, active in current_status.items() if not active]
        self.signals.log.emit(f"❌ Modelos caídos detectados ({len(offline_models)}): {offline_models}")

        if not offline_models:
            self.signals.log.emit("✅ Todos los modelos actuales están online. No se requiere reemplazo.")
            self.signals.finished.emit(self.current_models, ["No se requirieron reemplazos, todos online."])
            return

        # 2. Descargar todos los modelos libres de OpenRouter
        self.signals.log.emit("📥 Paso 2: Descargando lista de modelos de OpenRouter...")
        free_models = {}
        try:
            r = requests.get("https://openrouter.ai/api/v1/models", headers={"Authorization": f"Bearer {self.api_key}"}, timeout=10)
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
                self.signals.log.emit(f"✨ Modelos OpenRouter gratuitos identificados: {len(set(id(x) for x in free_models.values()))}")
            else:
                self.signals.log.emit(f"⚠️ Error descargando modelos OpenRouter: HTTP {r.status_code}")
        except Exception as e:
            self.signals.log.emit(f"⚠️ Excepción descargando modelos OpenRouter: {e}")

        # 3. Descargar datasets de rankings diarios de OpenRouter
        self.signals.log.emit("📊 Paso 3: Descargando rankings de uso semanal de OpenRouter...")
        usage = {}
        try:
            headers_or = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type":  "application/json",
                "HTTP-Referer":  "https://rpa-framework.local",
            }
            r = requests.get("https://openrouter.ai/api/v1/datasets/rankings-daily", headers=headers_or, timeout=10)
            if r.status_code == 200:
                rankings = r.json().get("data", [])
                dates = sorted(list(set(item.get("date") for item in rankings if item.get("date"))), reverse=True)
                if dates:
                    latest_date = datetime.strptime(dates[0], "%Y-%m-%d")
                    start_date = latest_date - timedelta(days=7)
                    start_date_str = start_date.strftime("%Y-%m-%d")
                    self.signals.log.emit(f"📈 Agrupando estadísticas OpenRouter desde {start_date_str} hasta {dates[0]}")

                    for item in rankings:
                        d_str = item.get("date")
                        if not d_str or d_str < start_date_str:
                            continue
                        slug = item.get("model_permaslug")
                        tokens = int(item.get("total_tokens", 0))

                        matched = free_models.get(slug)
                        if not matched:
                            for m_id, m_info in free_models.items():
                                if m_id in slug or slug in m_id:
                                    matched = m_info
                                    break
                        if matched:
                            mid = matched["id"]
                            usage[mid] = usage.get(mid, 0) + tokens
        except Exception as e:
            self.signals.log.emit(f"⚠️ Excepción procesando rankings OpenRouter: {e}")

        # Asegurar fallbacks clave de OpenRouter
        for fallback_or in [
            "nvidia/nemotron-nano-12b-v2-vl:free",
            "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
            "nvidia/nemotron-3-super-120b-a12b:free",
            "nvidia/nemotron-3-ultra-550b-a55b:free",
            "openai/gpt-oss-20b:free",
            "openrouter/free",
            "nvidia/nemotron-3.5-lightning:free",
            "google/gemma-4-26b-a4b-it:free",
            "google/gemma-4-31b-it:free"
        ]:
            if fallback_or in free_models and fallback_or not in usage:
                usage[fallback_or] = 1

        sorted_openrouter_free = [m_id for m_id, _ in sorted(usage.items(), key=lambda x: x[1], reverse=True)]

        # 3.1 Descargar y sondear modelos activos de Nvidia NIM
        nvidia_validated = []
        nvidia_key = os.getenv("NVIDIA_API_KEY", "")
        if nvidia_key:
            self.signals.log.emit("📥 Paso 3.1: Descargando catálogo y testeando modelos activos de Nvidia NIM...")
            try:
                r_nv = requests.get("https://integrate.api.nvidia.com/v1/models", headers={"Authorization": f"Bearer {nvidia_key}"}, timeout=10)
                if r_nv.status_code == 200:
                    exclude_keywords = [
                        "embed", "rerank", "parse", "pii", "clip", "translation", "translate", 
                        "reward", "safety", "guard", "diffusion", "deplot", "fuyu", "vila", "detector", "calibration"
                    ]
                    include_keywords = [
                        "instruct", "-it", "chat", "large", "medium", "small", "pro", "flash", "nemotron", "super", "omni", "nano"
                    ]
                    raw_nvidia_models = []
                    for m in r_nv.json().get("data", []):
                        m_id = m["id"]
                        m_lower = m_id.lower()
                        if any(kw in m_lower for kw in exclude_keywords):
                            continue
                        if any(kw in m_lower for kw in include_keywords):
                            raw_nvidia_models.append(m_id)

                    known_priority_nv = [
                        "meta/llama-3.1-8b-instruct",
                        "nvidia/llama-3.3-nemotron-super-49b-v1",
                        "meta/llama-3.2-11b-vision-instruct",
                        "nvidia/nemotron-nano-12b-v2-vl",
                        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
                        "nvidia/nemotron-3-super-120b-a12b",
                        "meta/llama-3.1-70b-instruct",
                        "nvidia/nemotron-3-nano-30b-a3b"
                    ]
                    ordered_nv = [m for m in known_priority_nv if m in raw_nvidia_models] + [m for m in raw_nvidia_models if m not in known_priority_nv]
                    
                    def _probe_nv(mid):
                        u = "https://integrate.api.nvidia.com/v1/chat/completions"
                        h = {"Authorization": f"Bearer {nvidia_key}", "Content-Type": "application/json"}
                        p = {"model": mid, "messages": [{"role": "user", "content": "OK"}], "max_tokens": 10, "temperature": 0.0}
                        try:
                            res = requests.post(u, headers=h, json=p, timeout=5)
                            return mid, (res.status_code == 200)
                        except Exception:
                            return mid, False

                    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
                        probe_results = dict(ex.map(lambda mid: _probe_nv(mid), ordered_nv[:25]))
                        nvidia_validated = [mid for mid in ordered_nv[:25] if probe_results.get(mid, False)]
                        self.signals.log.emit(f"✨ Modelos Nvidia NIM activos confirmados: {len(nvidia_validated)}")
            except Exception as e:
                self.signals.log.emit(f"⚠️ Error obteniendo catálogo de Nvidia: {e}")

        # 4. Validar candidatos con prompt clínico estructurado
        self.signals.log.emit("🩺 Paso 4: Validando candidatos con prueba de coincidencia clínica...")
        
        prompt_clinico = """Determina si el examen en el texto OCR coincide semánticamente con el examen buscado.
TEXTO OCR: "28-04-2026 Examen Hecho RM de Columna Lumbar"
EXAMEN BUSCADO: "RESONANCIA MAGNÉTICA DE COLUMNA LUMBAR"
Responde ÚNICAMENTE en formato JSON plano:
{"es_match": true, "confianza": 1.0}"""

        def _test_candidate_clinical(cand):
            b_url, t_key, prov = get_llm_request_params(cand)
            if not t_key:
                t_key = self.api_key
            u = f"{b_url}/chat/completions"
            h = {
                "Authorization": f"Bearer {t_key}",
                "Content-Type":  "application/json",
                "HTTP-Referer":  "https://rpa-framework.local",
            }
            p = {
                "model": cand,
                "messages": [{"role": "user", "content": prompt_clinico}],
                "max_tokens": 300,
                "temperature": 0.0,
            }
            try:
                res = requests.post(u, headers=h, json=p, timeout=10)
                if res.status_code == 200:
                    cnt = res.json().get('choices', [{}])[0].get('message', {}).get('content') or ""
                    cnt_l = cnt.lower()
                    if '"es_match": true' in cnt_l or '"es_match":true' in cnt_l or 'es_match: true' in cnt_l or 'es_match": 1' in cnt_l:
                        return cand, True, prov, "OK"
                    return cand, False, prov, f"No JSON match: {cnt[:40]}"
                return cand, False, prov, f"HTTP {res.status_code}"
            except Exception as exc:
                return cand, False, prov, str(exc)

        candidates_to_test = []
        for c in nvidia_validated[:8]:
            if c not in candidates_to_test:
                candidates_to_test.append(c)
        for c in sorted_openrouter_free[:10]:
            if c not in candidates_to_test:
                candidates_to_test.append(c)

        validated_nvidia = []
        validated_openrouter = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
            futures = {ex.submit(_test_candidate_clinical, cand): cand for cand in candidates_to_test}
            for fut in concurrent.futures.as_completed(futures):
                cand, ok, prov, msg = fut.result()
                if ok:
                    self.signals.log.emit(f"  ✅ Candidato VÁLIDO ({prov.upper()}): {cand}")
                    if prov == "nvidia":
                        validated_nvidia.append(cand)
                    else:
                        validated_openrouter.append(cand)
                else:
                    self.signals.log.emit(f"  ❌ Candidato descartado ({prov.upper()}): {cand} ({msg})")

        # 5. Reemplazo y conformación de la lista balanceada (5 Nvidia + 5 OpenRouter)
        self.signals.log.emit("⚡ Paso 5: Reconstruyendo lista balanceada de 10 modelos (5 Nvidia + 5 OpenRouter)...")
        new_models = []
        replacement_log = []

        current_online_nv = [m for m in self.current_models if current_status.get(m, False) and get_llm_request_params(m)[2] == "nvidia"]
        current_online_or = [m for m in self.current_models if current_status.get(m, False) and get_llm_request_params(m)[2] == "openrouter"]

        selected_nv = list(current_online_nv)
        for c in validated_nvidia:
            if len(selected_nv) >= 5:
                break
            if c not in selected_nv:
                selected_nv.append(c)
                replacement_log.append(f"Agregado Nvidia NIM: {c}")

        selected_or = list(current_online_or)
        for c in validated_openrouter:
            if len(selected_or) >= 5:
                break
            if c not in selected_or:
                selected_or.append(c)
                replacement_log.append(f"Agregado OpenRouter Free: {c}")

        all_pool = selected_nv + selected_or
        for c in validated_nvidia + validated_openrouter:
            if len(all_pool) >= 10:
                break
            if c not in all_pool:
                all_pool.append(c)

        new_models = all_pool[:10]
        self.signals.log.emit(f"🎯 Nueva lista consolidada ({len(new_models)} modelos): {new_models}")
        self.signals.finished.emit(new_models, replacement_log)
