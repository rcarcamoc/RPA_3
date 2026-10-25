# -*- coding: utf-8 -*-
"""
validator_runner.py
===================
Flujo completo de validación en segundo plano (Ronda 1 100% y Ronda 2 2/3)
para llm_validator.py. Extraído de utils/llm_validator.py.
"""

import os
import threading
import concurrent.futures
from .validator_probes import (
    UTILS_DIR,
    get_recently_active_models,
    get_recently_failed_models,
    is_nvidia_model,
    get_abbreviation_test_cases,
    evaluate_model,
)
from .validator_candidates import (
    get_popular_nvidia_candidates,
    get_popular_free_candidates,
    read_models_from_config,
    update_llm_config_file,
)


def _validation_and_update_flow():
    """Flujo interno de validacion y reemplazo automatico."""
    print("[llm_validator] Iniciando verificacion automatica en segundo plano...")
    
    # 1. Cargar variables de entorno (.env)
    try:
        from dotenv import load_dotenv
        project_root = UTILS_DIR.parent.parent
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
        is_working_priority = 0 if model_id in working_models else 1
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
                    
    if not failed_models:
        active_models_sorted = sorted(active_models, key=sort_key)
        if active_models_sorted != current_models:
            print("[llm_validator] Se detectaron cambios de orden (priorizando Nvidia). Guardando...")
            update_llm_config_file(active_models_sorted)
        print("[llm_validator] Todos los modelos estan funcionales (100% OK).")
        return
        
    print(f"[llm_validator] Modelos fallidos/offline: {failed_models}")
    
    candidates = []
    nvidia_key = os.getenv("NVIDIA_API_KEY", "")
    if nvidia_key:
        print("[llm_validator] Obteniendo candidatos de Nvidia ordenados por popularidad...")
        nvidia_candidates = get_popular_nvidia_candidates(nvidia_key, api_key)
        nvidia_candidates = [c for c in nvidia_candidates if c not in current_models and c not in recently_failed]
        candidates.extend(nvidia_candidates[:5])
        
    print("[llm_validator] Obteniendo candidatos de OpenRouter populares...")
    or_candidates = get_popular_free_candidates(api_key)
    or_candidates = [c for c in or_candidates if c not in current_models and c not in recently_failed and c not in candidates]
    candidates.extend(or_candidates[:5])
        
    candidates = candidates[:10]
    
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
    
    if unresolved_slots > 0:
        print(f"[llm_validator] Ronda 2: Quedan {unresolved_slots} slots vacios. Relajando exigencia a 2 de 3...")
        
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
                        
    new_models_list_sorted = sorted(new_models_list, key=sort_key)
    
    if new_models_list_sorted != current_models:
        print("[llm_validator] Se detectaron cambios en el estado de los modelos. Guardando...")
        update_llm_config_file(new_models_list_sorted)
    else:
        print("[llm_validator] No se requieren cambios en llm_config.py.")


def run_background_llm_validation():
    """Ejecuta la validacion de manera asincrona (no bloqueante) en segundo plano."""
    thread = threading.Thread(target=_validation_and_update_flow, daemon=True, name="LLMAutoValidation")
    thread.start()
