# -*- coding: utf-8 -*-
"""
llm_auto_manager.py
===================
Módulo de gestión centralizada para la autoverificación diaria, reemplazo de modelos LLM
y persistencia del historial de los últimos 5 días.
"""

import os
import sys
import json
import time
import re
import requests
import threading
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Directorios de configuración y logs
UTILS_DIR = Path(__file__).parent.resolve()
ROOT_DIR = UTILS_DIR.parent.parent
CONFIG_DIR = ROOT_DIR / "rpa_framework" / "config"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

CONFIG_FILE = UTILS_DIR / "llm_config.py"
ENV_FILE = ROOT_DIR / ".env"
AUTO_CONFIG_FILE = CONFIG_DIR / "llm_auto_config.json"
LOG_HISTORIAL_FILE = CONFIG_DIR / "llm_verification_log.json"
TIMESTAMP_FILE = UTILS_DIR / "last_llm_update.txt"

# Cargar variables de entorno
load_dotenv(ENV_FILE, override=True)


def get_default_config() -> dict:
    return {
        "enabled": True,
        "frequency": "diario_24h",  # 'diario_24h' o 'hora_fija'
        "scheduled_hour": 3,         # 03:00 AM
        "auto_apply": True,
        "last_run_timestamp": "",
        "last_status": "Sin ejecuciones aún"
    }


def load_auto_config() -> dict:
    """Carga la configuración de verificación automática desde JSON."""
    cfg = get_default_config()
    if AUTO_CONFIG_FILE.exists():
        try:
            with open(AUTO_CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                cfg.update(data)
        except Exception as e:
            print(f"[llm_auto_manager] Error leyendo auto_config: {e}")
    return cfg


def save_auto_config(cfg: dict) -> bool:
    """Guarda la configuración de autoverificación en JSON."""
    try:
        with open(AUTO_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[llm_auto_manager] Error guardando auto_config: {e}")
        return False


def load_verification_log() -> list:
    """
    Carga el historial de verificaciones de los últimos 5 días.
    Filtra y elimina automáticamente los registros de más de 5 días de antigüedad.
    """
    if not LOG_HISTORIAL_FILE.exists():
        return []

    try:
        with open(LOG_HISTORIAL_FILE, "r", encoding="utf-8") as f:
            logs = json.load(f)
    except Exception as e:
        print(f"[llm_auto_manager] Error leyendo log de historial: {e}")
        return []

    # Filtrar solo los últimos 5 días
    hace_5_dias = datetime.now() - timedelta(days=5)
    logs_validos = []
    
    for entry in logs:
        ts_str = entry.get("timestamp", "")
        try:
            # Intentar parsear ISO format o YYYY-MM-DD HH:MM:SS
            if "T" in ts_str:
                dt = datetime.fromisoformat(ts_str)
            else:
                dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            
            if dt >= hace_5_dias:
                logs_validos.append(entry)
        except Exception:
            # Si no se puede parsear fecha, conservar si es reciente
            logs_validos.append(entry)

    # Si se purgaron antiguos, actualizar el archivo JSON
    if len(logs_validos) != len(logs):
        save_verification_logs(logs_validos)

    # Ordenar más recientes primero
    logs_validos.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return logs_validos


def save_verification_logs(logs: list) -> bool:
    """Escribe la lista completa de logs en el archivo JSON."""
    try:
        with open(LOG_HISTORIAL_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[llm_auto_manager] Error guardando historial: {e}")
        return False


def add_verification_log(status: str, models_checked: int, models_online: int,
                         models_replaced: int, details: str, log_messages: list = None) -> dict:
    """
    Agrega una entrada al historial de los últimos 5 días y depura automáticamente
    las entradas antiguas.
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = {
        "timestamp": now_str,
        "status": status,  # "✅ Éxito", "🔄 Reemplazo Realizado", "⚠️ Sin Cambios", "❌ Fallo"
        "models_checked": models_checked,
        "models_online": models_online,
        "models_replaced": models_replaced,
        "details": details,
        "log_messages": log_messages or []
    }

    logs = load_verification_log()
    logs.insert(0, entry)  # Insertar al inicio

    # Purgar manteniendo solo registros dentro de los últimos 5 días
    hace_5_dias = datetime.now() - timedelta(days=5)
    logs_filtrados = []
    for l in logs:
        ts_str = l.get("timestamp", "")
        try:
            dt = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
            if dt >= hace_5_dias:
                logs_filtrados.append(l)
        except Exception:
            logs_filtrados.append(l)

    save_verification_logs(logs_filtrados)

    # Actualizar también timestamp de última ejecución en config
    cfg = load_auto_config()
    cfg["last_run_timestamp"] = now_str
    cfg["last_status"] = f"{status} ({models_online}/{models_checked} online)"
    save_auto_config(cfg)

    # Guardar en TIMESTAMP_FILE para retrocompatibilidad
    try:
        with open(TIMESTAMP_FILE, "w", encoding="utf-8") as f:
            f.write(datetime.now().isoformat())
    except Exception:
        pass

    return entry


def should_run_auto_verification(force=False) -> tuple[bool, str]:
    """
    Evalúa si corresponde ejecutar la verificación periódica según la configuración activa.
    Retorna (should_run: bool, reason: str).
    """
    if force:
        return True, "Ejecución manual forzada"

    cfg = load_auto_config()
    if not cfg.get("enabled", True):
        return False, "Autoverificación desactivada en configuración"

    last_ts_str = cfg.get("last_run_timestamp", "")
    if not last_ts_str:
        return True, "Primera ejecución de autoverificación"

    try:
        if "T" in last_ts_str:
            last_run = datetime.fromisoformat(last_ts_str)
        else:
            last_run = datetime.strptime(last_ts_str, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return True, "No se pudo interpretar última fecha de ejecución"

    now = datetime.now()
    freq = cfg.get("frequency", "diario_24h")

    if freq == "diario_24h":
        elapsed = now - last_run
        if elapsed >= timedelta(hours=24):
            return True, f"Han transcurrido {elapsed.total_seconds()/3600:.1f}h (>= 24h)"
        return False, f"Verificación reciente ({elapsed.total_seconds()/3600:.1f}h transcurridas)"
    
    elif freq == "hora_fija":
        target_hour = cfg.get("scheduled_hour", 3)
        # Si hoy aún no ha corrido y ya pasó o estamos en la hora objetivo
        if last_run.date() < now.date() and now.hour >= target_hour:
            return True, f"Hora programada alcanzada ({now.hour}:00 >= {target_hour}:00)"
        return False, f"Programado para las {target_hour}:00 (Última: {last_run.strftime('%Y-%m-%d %H:%M')})"

    return False, "Frecuencia no definida"


def get_llm_status_summary() -> str:
    """
    Retorna un texto resumido de 1-2 líneas sobre el estado actual de los modelos LLM
    apto para tooltips en la bandeja de sistema y menús contextuales.
    """
    try:
        sys.path.insert(0, str(ROOT_DIR))
        import rpa_framework.utils.llm_config as llm_cfg
        models = list(llm_cfg.BASE_LLM_MODELS)
        total = len(models)
    except Exception:
        models = []
        total = 0

    logs = load_verification_log()
    if not logs:
        return f"🤖 LLM: {total} modelos configurados (Sin verif. reciente)"

    last_log = logs[0]
    ts = last_log.get("timestamp", "Desconocido")
    online = last_log.get("models_online", total)
    checked = last_log.get("models_checked", total)
    replaced = last_log.get("models_replaced", 0)

    # Formatear fecha corta HH:MM
    try:
        dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        time_str = dt.strftime("%d/%m %H:%M")
    except Exception:
        time_str = ts

    if replaced > 0:
        return f"🤖 LLM: {online}/{checked} activos ({replaced} reemplazado{'s' if replaced>1 else ''} {time_str})"
    elif online == checked and checked > 0:
        return f"🤖 LLM: {online}/{checked} Online ✅ ({time_str})"
    else:
        return f"🤖 LLM: {online}/{checked} activos ({time_str})"


def run_auto_verification_logic(force=False, log_callback=None) -> dict:
    """
    Ejecuta el ciclo completo de validación y autoreemplazo de modelos de forma síncrona.
    Puede llamarse desde un hilo secundario en GUI, Tray Icon o script CLI.
    """
    def _log(msg):
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)
        if log_callback:
            try:
                log_callback(msg)
            except Exception:
                pass

    should, reason = should_run_auto_verification(force=force)
    if not should:
        _log(f"ℹ️ Omitiendo autoverificación: {reason}")
        return {"status": "Omitido", "reason": reason}

    _log(f"🚀 Iniciando autoverificación y autoreemplazo diario de modelos LLM... ({reason})")
    
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if not api_key:
        err_msg = "OPENROUTER_API_KEY no encontrada en .env"
        _log(f"❌ {err_msg}")
        add_verification_log("❌ Fallo", 0, 0, 0, err_msg, [err_msg])
        return {"status": "Error", "message": err_msg}

    # Cargar modelos actuales
    try:
        sys.path.insert(0, str(UTILS_DIR.parent))
        sys.path.insert(0, str(ROOT_DIR))
        try:
            import utils.llm_config as llm_cfg
        except ImportError:
            import rpa_framework.utils.llm_config as llm_cfg
        current_models = list(llm_cfg.BASE_LLM_MODELS)
    except Exception as e:
        err_msg = f"Error cargando llm_config: {e}"
        _log(f"❌ {err_msg}")
        add_verification_log("❌ Fallo", 0, 0, 0, err_msg, [err_msg])
        return {"status": "Error", "message": err_msg}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
        "HTTP-Referer":  "https://rpa-framework.local",
    }

    import concurrent.futures
    try:
        from utils.llm_config import get_llm_request_params
    except Exception:
        try:
            from rpa_framework.utils.llm_config import get_llm_request_params
        except Exception:
            def get_llm_request_params(m):
                return "https://openrouter.ai/api/v1", api_key, "openrouter"

    log_msgs = []
    
    def emit_log(m):
        log_msgs.append(m)
        _log(m)

    # 1. Validar modelos actuales con sus respectivos proveedores
    emit_log("🔍 Paso 1: Validando modelos actuales con sus proveedores correspondientes...")
    current_status = {}
    for m in current_models:
        base_url, target_key, provider = get_llm_request_params(m)
        if not target_key:
            target_key = api_key
        emit_log(f"  - Probando {m} ({provider.upper()})...")
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
            if r.status_code == 200:
                emit_log(f"    ✅ Online ({provider.upper()})")
            else:
                emit_log(f"    ❌ Offline (HTTP {r.status_code})")
        except Exception as e:
            current_status[m] = False
            emit_log(f"    ❌ Error ({e})")

    offline_models = [m for m, active in current_status.items() if not active]
    online_count = len(current_models) - len(offline_models)

    if not offline_models:
        msg = f"✅ Todos los modelos actuales están online ({online_count}/{len(current_models)})."
        emit_log(msg)
        add_verification_log(
            status="✅ Éxito",
            models_checked=len(current_models),
            models_online=online_count,
            models_replaced=0,
            details="Todos los modelos configurados están en línea.",
            log_messages=log_msgs
        )
        return {"status": "Éxito", "models_online": online_count, "models_replaced": 0}

    emit_log(f"❌ Modelos caídos detectados ({len(offline_models)}): {offline_models}")

    # 2. Descargar todos los modelos libres de OpenRouter
    emit_log("📥 Paso 2: Descargando catálogo de modelos libres de OpenRouter...")
    free_models = {}
    try:
        r = requests.get("https://openrouter.ai/api/v1/models", headers={"Authorization": f"Bearer {api_key}"}, timeout=10)
        if r.status_code == 200:
            for m in r.json().get("data", []):
                pricing = m.get("pricing", {})
                if float(pricing.get("prompt", 0)) == 0 and float(pricing.get("completion", 0)) == 0:
                    free_models[m["id"]] = m
                    if m.get("canonical_slug"):
                        free_models[m["canonical_slug"]] = m
    except Exception as e:
        emit_log(f"⚠️ Error al obtener modelos libres: {e}")

    # 3. Rankings de uso semanal de OpenRouter
    emit_log("📊 Paso 3: Obteniendo rankings de uso semanal de OpenRouter...")
    usage = {}
    try:
        headers_or = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type":  "application/json",
            "HTTP-Referer":  "https://rpa-framework.local",
        }
        r = requests.get("https://openrouter.ai/api/v1/datasets/rankings-daily", headers=headers_or, timeout=10)
        if r.status_code == 200:
            rankings = r.json().get("data", [])
            dates = sorted(list(set(item.get("date") for item in rankings if item.get("date"))), reverse=True)
            if dates:
                latest_date = datetime.strptime(dates[0], "%Y-%m-%d")
                start_date_str = (latest_date - timedelta(days=7)).strftime("%Y-%m-%d")
                for item in rankings:
                    if item.get("date", "") >= start_date_str:
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
        emit_log(f"⚠️ Error obteniendo rankings: {e}")

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

    # 3.1 Catálogo y sondeo de modelos Nvidia NIM
    nvidia_validated = []
    nvidia_key = os.getenv("NVIDIA_API_KEY", "")
    if nvidia_key:
        emit_log("📥 Paso 3.1: Descargando catálogo y testeando modelos Nvidia NIM...")
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
                    emit_log(f"✨ Modelos Nvidia NIM activos confirmados: {len(nvidia_validated)}")
        except Exception as e:
            emit_log(f"⚠️ Error obteniendo catálogo de Nvidia: {e}")

    # 4. Validar candidatos
    emit_log("🩺 Paso 4: Validando candidatos con prueba clínica estructurada...")
    prompt_clinico = """Determina si el examen en el texto OCR coincide semánticamente con el examen buscado.
TEXTO OCR: "28-04-2026 Examen Hecho RM de Columna Lumbar"
EXAMEN BUSCADO: "RESONANCIA MAGNÉTICA DE COLUMNA LUMBAR"
Responde ÚNICAMENTE en formato JSON plano:
{"es_match": true, "confianza": 1.0}"""

    def _test_candidate_clinical(cand):
        b_url, t_key, prov = get_llm_request_params(cand)
        if not t_key:
            t_key = api_key
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
                    return cand, True, prov
            return cand, False, prov
        except Exception:
            return cand, False, prov

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
            cand, ok, prov = fut.result()
            if ok:
                emit_log(f"  ✅ Candidato válido ({prov.upper()}): {cand}")
                if prov == "nvidia":
                    validated_nvidia.append(cand)
                else:
                    validated_openrouter.append(cand)

    # 5. Reemplazar
    emit_log("⚡ Paso 5: Reconstruyendo lista balanceada de 10 modelos...")
    current_online_nv = [m for m in current_models if current_status.get(m, False) and get_llm_request_params(m)[2] == "nvidia"]
    current_online_or = [m for m in current_models if current_status.get(m, False) and get_llm_request_params(m)[2] == "openrouter"]

    selected_nv = list(current_online_nv)
    for c in validated_nvidia:
        if len(selected_nv) >= 5:
            break
        if c not in selected_nv:
            selected_nv.append(c)

    selected_or = list(current_online_or)
    for c in validated_openrouter:
        if len(selected_or) >= 5:
            break
        if c not in selected_or:
            selected_or.append(c)

    all_pool = selected_nv + selected_or
    for c in validated_nvidia + validated_openrouter:
        if len(all_pool) >= 10:
            break
        if c not in all_pool:
            all_pool.append(c)

    new_models = all_pool[:10]
    replacement_summary = [f"Reemplazado por {m}" for m in new_models if m not in current_models]
    models_replaced_count = len(replacement_summary)

    # 6. Guardar en llm_config.py si auto_apply está activo
    cfg = load_auto_config()
    if cfg.get("auto_apply", True) and models_replaced_count > 0:
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                content = f.read()

            new_list = "BASE_LLM_MODELS = [\n"
            for i, model in enumerate(new_models):
                role = "Primario" if i == 0 else f"Fallback {i}"
                line = f'   "{model}",'
                new_list += f"{line:<60} # {role} — Validado OK\n"
            new_list += "]"

            updated, count = re.subn(r"BASE_LLM_MODELS\s*=\s*\[.*?\]", new_list, content, flags=re.DOTALL)
            if count > 0:
                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    f.write(updated)
                emit_log("💾 llm_config.py actualizado automáticamente con la nueva lista de modelos.")
        except Exception as e:
            emit_log(f"❌ Error actualizando llm_config.py: {e}")

    final_status = "🔄 Reemplazo Realizado" if models_replaced_count > 0 else "⚠️ Sin Reemplazos Disponibles"
    details_str = "; ".join(replacement_summary) if replacement_summary else f"No se encontraron reemplazos para los {len(offline_models)} modelos caídos."

    add_verification_log(
        status=final_status,
        models_checked=len(current_models),
        models_online=online_count,
        models_replaced=models_replaced_count,
        details=details_str,
        log_messages=log_msgs
    )

    return {
        "status": final_status,
        "models_online": online_count,
        "models_replaced": models_replaced_count,
        "details": details_str
    }
