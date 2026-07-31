# -*- coding: utf-8 -*-
"""
llm_validator.py
================
Verificación automática y silenciosa de modelos LLM al inicio de la aplicación.
Evalúa los modelos con una batería de abreviaciones clínicas y realiza
el reemplazo automático por modelos populares gratuitos si alguno falla.
"""

import os
import re
import sys
import time
import threading
import concurrent.futures
from pathlib import Path

# Configuración y Rutas
UTILS_DIR = Path(__file__).parent
CONFIG_FILE = UTILS_DIR / "llm_config.py"

DEFAULT_TEST_CASES = [
    {
        "ocr": "28-04-2026 Examen Hecho RM de Columna Lumbar. Stat.",
        "target": "RESONANCIA MAGNÉTICA DE COLUMNA LUMBAR"
    },
    {
        "ocr": "Ax Torax AP-Lateral 27-04-2026 Examen Hecho GUMERCINDA",
        "target": "Rx de torax pa y lateral."
    },
    {
        "ocr": "15-05-2026 TAC de abdomen y pelvis con contraste",
        "target": "TOMOGRAFÍA COMPUTARIZADA DE ABDOMEN Y PELVIS"
    }
]

FALLBACK_POPULAR_FREE = [
    "meta-llama/llama-3.3-70b-instruct:free",
    "meta-llama/llama-3.2-3b-instruct:free",
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-4-31b-it:free",
    "qwen/qwen3-coder:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "nousresearch/hermes-3-llama-3.1-405b:free"
]


def get_recently_active_models():
    """Retorna un conjunto de modelos que tuvieron algún match exitoso (es_match = 1) en las últimas 12 horas."""
    active = set()
    try:
        import mysql.connector
        from datetime import datetime, timedelta
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='',
            database='ris',
            connect_timeout=2
        )
        cursor = conn.cursor()
        half_day_ago = (datetime.now() - timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            SELECT DISTINCT modelo 
            FROM ris.log_llm_ranking 
            WHERE es_match = 1 AND timestamp >= %s
        """, (half_day_ago,))
        for (m,) in cursor.fetchall():
            active.add(m)
        conn.close()
    except Exception as e:
        print(f"[llm_validator] Advertencia consultando activos recientes: {e}")
    return active


def get_recently_failed_models():
    """Retorna un conjunto de modelos que fallaron (es_match = 0) en las últimas 24 horas."""
    failed = set()
    try:
        import mysql.connector
        from datetime import datetime, timedelta
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='',
            database='ris',
            connect_timeout=2
        )
        cursor = conn.cursor()
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            SELECT DISTINCT modelo 
            FROM ris.log_llm_ranking 
            WHERE es_match = 0 AND timestamp >= %s
        """, (yesterday,))
        for (m,) in cursor.fetchall():
            failed.add(m)
        conn.close()
    except Exception as e:
        print(f"[llm_validator] Advertencia consultando fallidos recientes: {e}")
    return failed


def is_nvidia_model(model_id):
    """Retorna True si el modelo es servido por Nvidia."""
    try:
        from utils.llm_config import get_llm_request_params
        _, _, provider = get_llm_request_params(model_id)
        return provider == "nvidia"
    except Exception:
        return False


def get_abbreviation_test_cases():
    """
    Busca dinámicamente hasta 3 casos exitosos con abreviaciones en la base de datos ris.log_llm_ranking.
    Si no encuentra suficientes o falla la conexión, usa los casos clínicos por defecto.
    """
    cases = []
    try:
        import mysql.connector
        conn = mysql.connector.connect(
            host='localhost',
            user='root',
            password='',
            database='ris',
            connect_timeout=2
        )
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT target_buscado, texto_ocr 
            FROM ris.log_llm_ranking 
            WHERE es_match = 1 
              AND (target_buscado LIKE '%RM%' 
                   OR target_buscado LIKE '%TC%' 
                   OR target_buscado LIKE '%TAC%' 
                   OR target_buscado LIKE '%RX%' 
                   OR target_buscado LIKE '%Rx%' 
                   OR texto_ocr LIKE '%RM%' 
                   OR texto_ocr LIKE '%TC%' 
                   OR texto_ocr LIKE '%TAC%' 
                   OR texto_ocr LIKE '%RX%' 
                   OR texto_ocr LIKE '%Rx%')
            GROUP BY target_buscado, texto_ocr
            LIMIT 3
        """)
        rows = cursor.fetchall()
        conn.close()
        for r in rows:
            # Limpiar codificaciones extrañas si las hay
            target = r["target_buscado"].encode('latin1', errors='ignore').decode('utf-8', errors='ignore') if isinstance(r["target_buscado"], str) else ""
            ocr = r["texto_ocr"].encode('latin1', errors='ignore').decode('utf-8', errors='ignore') if isinstance(r["texto_ocr"], str) else ""
            if not target:
                target = r["target_buscado"]
            if not ocr:
                ocr = r["texto_ocr"]
            cases.append({
                "ocr": ocr,
                "target": target
            })
    except Exception as e:
        print(f"[llm_validator] Advertencia consultando DB: {e}")
        
    # Rellenar con fallbacks
    if len(cases) < 3:
        for fb in DEFAULT_TEST_CASES:
            if not any(c["target"].lower() == fb["target"].lower() for c in cases):
                cases.append(fb)
                if len(cases) == 3:
                    break
    return cases[:3]


def test_model_case(model_id, api_key, ocr_text, target_exam):
    """Prueba un caso individual en la API del proveedor correspondiente y registra en DB."""
    import requests
    import json
    import time
    
    try:
        from utils.llm_config import get_llm_request_params, log_llm_result
    except ImportError:
        parent_dir = str(Path(__file__).parent.parent)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        from utils.llm_config import get_llm_request_params, log_llm_result
    
    base_url, target_key, provider = get_llm_request_params(model_id)
    if not target_key:
        # Usar api_key de OpenRouter como fallback si no hay key especifica en config
        target_key = api_key
        base_url = "https://openrouter.ai/api/v1"
        provider = "openrouter"
        
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {target_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://rpa-framework.local",
    }
    
    prompt = f"""
Determina si el examen encontrado en el texto OCR coincide semánticamente con el examen buscado, considerando abreviaciones médicas comunes (ej. RM = Resonancia Magnética, Rx/Ax = Radiografía, TC/TAC = Tomografía).
TEXTO OCR: "{ocr_text}"
EXAMEN BUSCADO: "{target_exam}"
Responde ÚNICAMENTE en formato JSON plano sin bloques de código markdown:
{{"es_match": true, "confianza": 1.0}}
"""

    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 80,
        "temperature": 0.0,
    }
    
    start_time = time.time()
    ok = False
    msg = ""
    confianza = 0.0
    
    max_retries = 3
    retry_delay = 2.0
    
    for attempt in range(max_retries):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=8)
            if r.status_code == 200:
                try:
                    data = r.json()
                except Exception as parse_err:
                    msg = f"Error parseando JSON de respuesta API: {parse_err}"
                    break
                    
                choices = data.get('choices')
                if not choices or not isinstance(choices, list) or len(choices) == 0:
                    msg = f"Estructura de respuesta de API invalida: {data}"
                    break
                    
                message = choices[0].get('message')
                if not message or not isinstance(message, dict):
                    msg = "No se retorno ningun mensaje en la respuesta"
                    break
                    
                content = message.get('content')
                if content is None:
                    msg = "El contenido retornado por el modelo es vacio (None)"
                    break
                    
                content = content.strip()
                if content.startswith("```"):
                    content = re.sub(r"^```(?:json)?\n", "", content)
                    content = re.sub(r"\n```$", "", content)
                    content = content.strip()
                    
                # Parse JSON robusto
                res = None
                try:
                    res = json.loads(content)
                except Exception:
                    # Intentar extraer el JSON con regex
                    match = re.search(r"\{.*\}", content, re.DOTALL)
                    if match:
                        try:
                            res = json.loads(match.group(0))
                        except Exception:
                            pass
                            
                if res is None:
                    # Fallback analizando texto libre
                    content_lower = content.lower()
                    if re.search(r'"es_match"\s*:\s*true', content_lower) or re.search(r'es_match\s*:\s*true', content_lower):
                        res = {"es_match": True, "confianza": 1.0}
                    elif re.search(r'"es_match"\s*:\s*false', content_lower) or re.search(r'es_match\s*:\s*false', content_lower):
                        res = {"es_match": False, "confianza": 0.0}
                        
                if res is None:
                    msg = f"JSON invalido en la respuesta del modelo: '{content[:50]}'"
                    break
                    
                if res.get("es_match") is True:
                    ok = True
                    confianza = float(res.get("confianza", 1.0))
                    msg = "Match OK"
                    break
                else:
                    confianza = float(res.get("confianza", 0.0))
                    msg = f"No coincide (Confianza: {confianza})"
                    break
            elif r.status_code == 429:
                if attempt < max_retries - 1:
                    sleep_time = retry_delay * (2 ** attempt)
                    print(f"  [test_model] {model_id} recibio HTTP 429 (Rate Limit). Reintentando en {sleep_time}s...")
                    time.sleep(sleep_time)
                    continue
                msg = f"HTTP 429 (Rate Limit) despues de {max_retries} intentos"
                break
            elif r.status_code in [500, 502, 503, 504]:
                if attempt < max_retries - 1:
                    sleep_time = retry_delay * (2 ** attempt)
                    print(f"  [test_model] {model_id} recibio HTTP {r.status_code}. Reintentando en {sleep_time}s...")
                    time.sleep(sleep_time)
                    continue
                msg = f"HTTP {r.status_code}"
                break
            else:
                msg = f"HTTP {r.status_code}"
                break
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                sleep_time = retry_delay * (2 ** attempt)
                print(f"  [test_model] {model_id} error de red: {e}. Reintentando en {sleep_time}s...")
                time.sleep(sleep_time)
                continue
            msg = str(e)
            break
            
    elapsed_ms = int((time.time() - start_time) * 1000)
    
    # Registrar en ris.log_llm_ranking
    try:
        log_llm_result(
            modelo=model_id,
            es_match=ok,
            confianza=confianza,
            tiempo_ms=elapsed_ms,
            razonamiento=msg,
            target_buscado=target_exam,
            texto_ocr=ocr_text,
            id_registro=0,
            es_primer_intento=True,
            contexto="busqueda_ocr",
            proveedor=provider
        )
    except Exception as db_err:
        print(f"[llm_validator] Error al registrar resultado en DB: {db_err}")
        
    return ok, msg


def evaluate_model(model_id, api_key, test_cases, strict=True):
    """Evalúa un modelo con los casos provistos. strict=True requiere 100%, strict=False requiere 2 de 3."""
    passed_count = 0
    failed_count = 0
    total_cases = len(test_cases)
    required = total_cases if strict else 2
    
    for idx, case in enumerate(test_cases):
        if idx > 0:
            time.sleep(1.0)
        ok, msg = test_model_case(model_id, api_key, case["ocr"], case["target"])
        if ok:
            passed_count += 1
        else:
            failed_count += 1
            print(f"  [test_model] {model_id} fallo caso '{case['target'][:30]}...': {msg}")
            
        # Salida temprana (early exit) si ya no es posible cumplir la cuota requerida
        if (total_cases - failed_count) < required:
            break
            
    return passed_count >= required


def get_popular_nvidia_candidates(nvidia_key, openrouter_key):
    """
    Descarga los modelos disponibles en Nvidia NIM y los ordena 
    según la popularidad de uso registrada en OpenRouter.
    """
    import requests
    from datetime import datetime, timedelta
    
    # 1. Obtener modelos de Nvidia NIM
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
                # Descartar no conversacionales
                if any(kw in m_lower for kw in exclude_keywords):
                    continue
                # Aceptar si contiene palabras clave de chat/instruct
                if any(kw in m_lower for kw in include_keywords):
                    nvidia_models.append(m_id)
    except Exception as e:
        print(f"[llm_validator] Error obteniendo catalogo de Nvidia: {e}")
        return []
        
    if not nvidia_models:
        return []
        
    # 2. Descargar rankings de OpenRouter
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
        # Priorizar algunos modelos conocidos de Nvidia si no hay conexión al ranking
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

    # Helper de normalización
    def normalize(model_id):
        base = model_id.split(":")[0]
        base = base.replace("meta-llama/", "meta/")
        base = base.replace("nv-mistralai/", "mistralai/")
        return base.lower()

    # Mapear modelos de Nvidia a sus versiones normalizadas
    nvidia_map = {}
    for m in nvidia_models:
        norm = normalize(m)
        nvidia_map[norm] = m

    # Sumar volumen de uso de OpenRouter
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

    # Ordenar por uso descendente
    sorted_nvidia = [m for m, _ in sorted(usage.items(), key=lambda x: x[1], reverse=True)]
    
    # Agregar los modelos de Nvidia restantes al final
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
        
    # Unir con fallbacks para garantizar una lista minima
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
        
        # Escribir sobre BASE_LLM_MODELS
        updated, count = re.subn(
            r"BASE_LLM_MODELS\s*=\s*\[.*?\]", new_list, content, flags=re.DOTALL
        )
        if count == 0:
            # Fallback
            updated, count = re.subn(
                r"LLM_MODELS\s*=\s*\[.*?\]", new_list.replace("BASE_LLM_MODELS", "LLM_MODELS"), content, flags=re.DOTALL
            )
            
        if count > 0:
            tmp_path = CONFIG_FILE.with_suffix(".py.tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(updated)
            
            # Reemplazo atomico
            os.replace(tmp_path, CONFIG_FILE)
            print(f"[llm_validator] llm_config.py actualizado automaticamente con {len(active_models)} modelos.")
            return True
    except Exception as e:
        print(f"[llm_validator] Error escribiendo config: {e}")
    return False


def _validation_and_update_flow():
    """Flujo interno de validacion y reemplazo automatico."""
    print("[llm_validator] Iniciando verificacion automatica en segundo plano...")
    
    # 1. Cargar variables de entorno (.env)
    try:
        from dotenv import load_dotenv
        project_root = Path(__file__).parent.parent.parent
        env_path = project_root / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
    except Exception as e:
        print(f"[llm_validator] Error cargando .env: {e}")
        
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        print("[llm_validator] Error: OPENROUTER_API_KEY no configurada. Cancelando validacion.")
        return
        
    # 2. Cargar modelos configurados
    current_models = read_models_from_config()
    if not current_models:
        print("[llm_validator] No hay modelos que validar en el config.")
        return
        
    # 3. Cargar bateria de casos de prueba
    test_cases = get_abbreviation_test_cases()
    print(f"[llm_validator] Validando contra {len(test_cases)} casos clinicos.")
    
    # 4. Ronda 1: Evaluar modelos configurados al 100% de exito (estricto)
    active_models = []
    failed_models = []
    working_models = set()
    
    def sort_key(model_id):
        # 1. Estado de funcionamiento (funcionando: 0, fallido: 1)
        is_working_priority = 0 if model_id in working_models else 1
        # 2. Proveedor (nvidia: 0, openrouter: 1)
        provider_priority = 0 if is_nvidia_model(model_id) else 1
        return (is_working_priority, provider_priority)
    
    recently_active = get_recently_active_models()
    recently_failed = get_recently_failed_models()
    
    models_to_test = []
    for m in current_models:
        if m in recently_active:
            active_models.append(m)
            working_models.add(m)
            print(f"  [OK] Modelo activo (reciente en DB): {m}")
        elif m in recently_failed:
            failed_models.append(m)
            print(f"  [FAIL] Modelo fallido (reciente en DB): {m}")
        else:
            models_to_test.append(m)
            
    if models_to_test:
        print(f"[llm_validator] Evaluando {len(models_to_test)} modelos en paralelo...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(evaluate_model, m, api_key, test_cases, True): m for m in models_to_test}
            for future in concurrent.futures.as_completed(futures):
                m = futures[future]
                try:
                    passed = future.result()
                    if passed:
                        active_models.append(m)
                        working_models.add(m)
                        print(f"  [OK] Modelo activo (100%): {m}")
                    else:
                        failed_models.append(m)
                        print(f"  [FAIL] Modelo caido o insuficiente: {m}")
                except Exception as exc:
                    failed_models.append(m)
                    print(f"  [FAIL] Modelo {m} arrojo excepcion en evaluacion: {exc}")
                    
    # Si todo funciona al 100%, reordenamos para priorizar Nvidia y terminamos de inmediato
    if not failed_models:
        active_models_sorted = sorted(active_models, key=sort_key)
        if active_models_sorted != current_models:
            print("[llm_validator] Se detectaron cambios de orden (priorizando Nvidia). Guardando...")
            update_llm_config_file(active_models_sorted)
        print("[llm_validator] Todos los modelos estan funcionales (100% OK).")
        return
        
    # De lo contrario, buscar candidatos
    print(f"[llm_validator] Modelos fallidos/offline: {failed_models}")
    
    candidates = []
    # 1. Obtener candidatos de Nvidia si hay llave configurada
    nvidia_key = os.getenv("NVIDIA_API_KEY", "")
    if nvidia_key:
        print("[llm_validator] Obteniendo candidatos de Nvidia ordenados por popularidad...")
        nvidia_candidates = get_popular_nvidia_candidates(nvidia_key, api_key)
        nvidia_candidates = [c for c in nvidia_candidates if c not in current_models and c not in recently_failed]
        candidates.extend(nvidia_candidates[:5]) # Tomar los top 5 de Nvidia
        
    # 2. Obtener candidatos de OpenRouter siempre (como fallback o alternativas adicionales)
    print("[llm_validator] Obteniendo candidatos de OpenRouter populares...")
    or_candidates = get_popular_free_candidates(api_key)
    or_candidates = [c for c in or_candidates if c not in current_models and c not in recently_failed and c not in candidates]
    candidates.extend(or_candidates[:5]) # Tomar los top 5 de OpenRouter
        
    # Limitar candidates a un maximo de 10 en total para rapidez y diversidad
    candidates = candidates[:10]
    
    # Evaluar candidatos al 100% de exito
    valid_candidates = []
    
    if candidates:
        print(f"[llm_validator] Evaluando {len(candidates)} candidatos en paralelo (Ronda 1 - Exigencia 100%)...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(evaluate_model, cand, api_key, test_cases, True): cand for cand in candidates}
            for future in concurrent.futures.as_completed(futures):
                cand = futures[future]
                try:
                    passed = future.result()
                    if passed:
                        valid_candidates.append(cand)
                        working_models.add(cand)
                        print(f"  [OK] Candidato calificado (100%): {cand}")
                    else:
                        print(f"  [FAIL] Candidato descartado en Ronda 1: {cand}")
                except Exception as exc:
                    print(f"  [FAIL] Candidato {cand} arrojo excepcion: {exc}")
                    
    # Intentar reemplazar con los calificados
    new_models_list = list(current_models)
    replaced_count = 0
    cand_idx = 0
    
    for idx, m in enumerate(new_models_list):
        if m in failed_models:
            if cand_idx < len(valid_candidates):
                new_models_list[idx] = valid_candidates[cand_idx]
                print(f"[llm_validator] Reemplazando '{m}' por '{valid_candidates[cand_idx]}'")
                cand_idx += 1
                replaced_count += 1
                
    unresolved_slots = len(failed_models) - replaced_count
    
    # Ronda 2: Relajar exigencia a 2 de 3 si quedaron slots sin cubrir
    if unresolved_slots > 0:
        print(f"[llm_validator] Ronda 2: Quedan {unresolved_slots} slots vacios. Relajando exigencia a 2 de 3...")
        
        # Filtrar candidatos que no pasaron Ronda 1
        failed_candidates = [c for c in candidates if c not in valid_candidates]
        
        relaxed_candidates = []
        if failed_candidates:
            print(f"[llm_validator] Evaluando {len(failed_candidates)} candidatos fallidos en paralelo (Ronda 2 - Exigencia 2/3)...")
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                futures = {executor.submit(evaluate_model, cand, api_key, test_cases, False): cand for cand in failed_candidates}
                for future in concurrent.futures.as_completed(futures):
                    cand = futures[future]
                    try:
                        passed = future.result()
                        if passed:
                            relaxed_candidates.append(cand)
                            working_models.add(cand)
                            print(f"  [WARN] Candidato calificado (2/3): {cand}")
                        else:
                            print(f"  [FAIL] Candidato descartado en Ronda 2: {cand}")
                    except Exception as exc:
                        print(f"  [FAIL] Candidato {cand} fallo en Ronda 2: {exc}")
                        
        # Aplicar candidatos de ronda 2 o evaluar si el original pasa al menos 2/3
        relaxed_idx = 0
        original_to_test_relaxed = []
        original_indices = []
        
        for idx, m in enumerate(new_models_list):
            if m in failed_models and new_models_list[idx] == m:
                if relaxed_idx < len(relaxed_candidates):
                    new_models_list[idx] = relaxed_candidates[relaxed_idx]
                    print(f"[llm_validator] Reemplazando '{m}' por '{relaxed_candidates[relaxed_idx]}' (Ronda 2)")
                    relaxed_idx += 1
                else:
                    original_to_test_relaxed.append(m)
                    original_indices.append(idx)
                    
        # Evaluar originales restantes con regla 2/3
        if original_to_test_relaxed:
            print(f"[llm_validator] Probando {len(original_to_test_relaxed)} originales restantes con regla 2/3 en paralelo...")
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                futures = {executor.submit(evaluate_model, m, api_key, test_cases, False): (m, idx) 
                           for m, idx in zip(original_to_test_relaxed, original_indices)}
                for future in concurrent.futures.as_completed(futures):
                    m, idx = futures[future]
                    try:
                        passed = future.result()
                        if passed:
                            working_models.add(m)
                            print(f"  [WARN] Conservando '{m}' (pasa 2/3)")
                        else:
                            print(f"  [FAIL] '{m}' no cumple ni regla 2/3. Se deja en lista pero fallido.")
                    except Exception as exc:
                        print(f"  [FAIL] Excepcion evaluando original {m}: {exc}")
                        
    # Priorizar modelos de Nvidia en la lista final (sólo los que estén funcionando)
    new_models_list_sorted = sorted(new_models_list, key=sort_key)
    
    # 5. Escribir si hay cambios
    if new_models_list_sorted != current_models:
        print("[llm_validator] Se detectaron cambios en el estado de los modelos. Guardando...")
        update_llm_config_file(new_models_list_sorted)
    else:
        print("[llm_validator] No se requieren cambios en llm_config.py.")


def run_background_llm_validation():
    """Ejecuta la validacion de manera asincrona (no bloqueante) en segundo plano."""
    thread = threading.Thread(target=_validation_and_update_flow, daemon=True, name="LLMAutoValidation")
    thread.start()


# Para pruebas unitarias o ejecucion standalone
if __name__ == "__main__":
    print("--- MODO DE PRUEBAS STANDALONE ---")
    _validation_and_update_flow()
