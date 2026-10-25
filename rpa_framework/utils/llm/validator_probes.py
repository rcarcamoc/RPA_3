# -*- coding: utf-8 -*-
"""
validator_probes.py
===================
Consultas de actividad reciente en BD, obtención de casos de prueba con abreviaciones
clínicas y sondeo/evaluación de modelos LLM. Extraído de utils/llm_validator.py.
"""

import re
import sys
import time
from pathlib import Path

UTILS_DIR = Path(__file__).resolve().parent.parent
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
    "meta/llama-3.1-8b-instruct",
    "nvidia/llama-3.3-nemotron-super-49b-v1",
    "nvidia/nemotron-nano-12b-v2-vl:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "meta/llama-3.2-11b-vision-instruct",
    "nvidia/nemotron-nano-12b-v2-vl",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "openai/gpt-oss-20b:free",
    "openrouter/free"
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
    
    try:
        from utils.llm_config import get_llm_request_params, log_llm_result
    except ImportError:
        parent_dir = str(UTILS_DIR.parent)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        from utils.llm_config import get_llm_request_params, log_llm_result
    
    base_url, target_key, provider = get_llm_request_params(model_id)
    if not target_key:
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
        "max_tokens": 300,
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
            r = requests.post(url, headers=headers, json=payload, timeout=10)
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
                    
                res = None
                try:
                    res = json.loads(content)
                except Exception:
                    match = re.search(r"\{.*\}", content, re.DOTALL)
                    if match:
                        try:
                            res = json.loads(match.group(0))
                        except Exception:
                            pass
                            
                if res is None:
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
            
        if (total_cases - failed_count) < required:
            break
            
    return passed_count >= required
