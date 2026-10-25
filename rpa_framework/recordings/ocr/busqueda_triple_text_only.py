#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script: busqueda_triple_text_only.py
Descripción: Script de búsqueda optimizado para validación semántica de texto.
1. Busca "Examen Hecho" (o variantes) + Fecha en toda la imagen.
2. Identifica filas candidatas.
3. Extrae el texto diagnóstico de cada fila usando PaddleOCR GPU / Tesseract.
4. Si la validación exacta/fuzzy falla, envía el TEXTO al LLM con un prompt clínico robusto.

Ubicación: rpa_framework/recordings/ocr/busqueda_triple_text_only.py
Refactorizado de forma modular junto con rpa_framework/recordings/ocr/triple_search/.
"""

import sys
import os
import time
import logging
from datetime import datetime
from pathlib import Path
import cv2
import numpy as np
import pyautogui
pyautogui.FAILSAFE = False
from dotenv import load_dotenv

load_dotenv()

try:
    from rapidfuzz import fuzz
except ImportError:
    print("Error: rapidfuzz no está instalado.")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from utils.logging_setup import setup_logging
from ocr.engine import OCREngine
from utils.telegram_manager import enviar_alerta_todos
from utils.llm_config import (
    OPENROUTER_BASE_URL, BASE_LLM_MODELS, LLM_MODELS, OCR_DEFAULT_MODELS,
    LLM_DEFAULT_TEMPERATURE, LLM_DEFAULT_MAX_TOKENS, LLM_DEFAULT_TIMEOUT,
    get_ranked_models, log_llm_result, get_llm_request_params,
)

try:
    from recordings.ocr.auditor_clinico import AuditorClinico
except ImportError:
    try:
        from rpa_framework.recordings.ocr.auditor_clinico import AuditorClinico
    except ImportError:
        AuditorClinico = None

from recordings.ocr.triple_search import (
    HAS_MYSQL,
    HAS_PREPROCESS_UTILS,
    MIN_FUZZY_FOR_LLM,
    LLM_MIN_CONFIDENCE,
    _CIRCUIT_BREAKER_DOWN_MODELS,
    TripleSearchDBMixin,
    TripleSearchMedicalTextMixin,
    TripleSearchLLMCascadeMixin,
    TripleSearchCandidatesMixin,
    TripleSearchVisualClickMixin,
)

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    logger.error("OPENROUTER_API_KEY no está configurada en el archivo .env")
    sys.exit(1)

MODEL_ID = LLM_MODELS[0]


class BusquedaTextOnly(
    TripleSearchDBMixin,
    TripleSearchMedicalTextMixin,
    TripleSearchLLMCascadeMixin,
    TripleSearchCandidatesMixin,
    TripleSearchVisualClickMixin,
):
    def __init__(self):
        # Motor OCR principal: PaddleOCR en GPU (máxima precisión y rapidez ~200ms)
        self.ocr_engine = OCREngine(
            engine='paddleocr', 
            language='es', 
            use_gpu=True, 
            confidence_threshold=0.3,
            preprocess=False
        )
        self._paddle_engine = None
        self._tesseract_engine = None
        self.region = (188, 93, 1720, 900)
        self.ROW_TOLERANCE = 8
        self.CROP_HEIGHT = 22
        self.OFFSET_X = 50
        self.OFFSET_Y = 180
        self.MAX_RETRIES = 2
        self.POST_CLICK_SLEEP = 5.0
        
        try:
            from utils.visual_feedback import VisualFeedback
            self.vf = VisualFeedback()
        except Exception as e:
            logger.warning(f"VisualFeedback no disponible ({e}), mensajes desactivados.")
            self.vf = None

        if AuditorClinico:
            self.auditor = AuditorClinico()
            logger.info("🛡️ Auditor Clínico Pre-Clic inicializado y activo.")
        else:
            self.auditor = None
            logger.warning("⚠️ AuditorClinico no disponible; auditoría pre-clic desactivada.")

        self.last_diagnostic = ""

    def execute(self, override_diag: str = None):
        """Ejecuta la búsqueda. Retorna (encontrado: bool, ocr_text_candidato: str)."""
        logger.info(">>>> INICIANDO BÚSQUEDA TEXT-ONLY (DeepSeek) <<<<")
        
        id_registro, target_diag_original, target_fecha_obj = self.get_db_targets()
        if not target_diag_original:
            return False, ""

        target_diag = target_diag_original
        if override_diag:
            logger.info(f"🔄 Usando sinónimo/alternativa: '{override_diag}' (original: '{target_diag_original}')")
            target_diag = override_diag
            
        target_fecha_str = target_fecha_obj.strftime("%d-%m-%Y")
        logger.info(f"Buscando: [{target_fecha_str}] + [Hecho] + [{target_diag}]")
        motivos_descarte = []

        if self.vf:
            self.vf.highlight_region(*self.region, duration=1.0)
            time.sleep(0.2)

        screenshot = pyautogui.screenshot(region=self.region)
        img_np = np.array(screenshot)
        img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

        log_dir = Path("rpa_framework/log/busqueda triple")
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        now_str = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
        diag_clean = "".join([c if c.isalnum() else "_" for c in target_diag])[:30]
        _log_base_name = f"{now_str} {diag_clean} {target_fecha_str}"
        
        candidates = []
        rows_data = []
        
        # --- PASO 1: PADDLEOCR GPU (MOTOR PRINCIPAL) ---
        logger.info("--- ⚡ Ejecutando OCR Paso 1: PaddleOCR GPU (Motor Principal) ---")
        if self.vf:
            self.vf.show_persistent_message("PROCESANDO OCR (PADDLE GPU)...", "ocr", bg_color="#9C27B0", fg_color="#FFFFFF")
            
        try:
            ocr_results_paddle = self.execute_paddle_ocr(img_bgr)
            if len(ocr_results_paddle) < 3:
                for wait_attempt in range(1, 4):
                    logger.warning(
                        f"⏳ Pantalla PACS posiblemente no renderizada (solo {len(ocr_results_paddle)} textos detectados). "
                        f"Esperando estabilización ({wait_attempt}/3)..."
                    )
                    time.sleep(2.0)
                    screenshot = pyautogui.screenshot(region=self.region)
                    img_np = np.array(screenshot)
                    img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
                    ocr_results_paddle = self.execute_paddle_ocr(img_bgr)
                    if len(ocr_results_paddle) >= 3:
                        logger.info(f"✅ Pantalla PACS estabilizada: {len(ocr_results_paddle)} textos detectados.")
                        break

            candidates_paddle, rows_data_paddle = self._analyze_candidates(ocr_results_paddle, target_fecha_str)
            self.last_img_bgr = img_bgr
            self.last_paddle_results = ocr_results_paddle
            self.last_paddle_rows_data = rows_data_paddle

            if candidates_paddle:
                logger.info(f"✅ PaddleOCR GPU detectó {len(candidates_paddle)} candidatos con Fecha y Estado Hecho.")
                candidates = candidates_paddle
                rows_data = rows_data_paddle
            else:
                logger.warning("⚠️ PaddleOCR GPU no encontró candidatos con Fecha y Estado Hecho.")
                rows_data = rows_data_paddle
        except Exception as e:
            logger.error(f"Error ejecutando PaddleOCR GPU: {e}")
            rows_data = []
        finally:
            if self.vf:
                self.vf.hide_persistent_message("ocr")
                
        # --- PASO 2: TESSERACT (FALLBACK SECUNDARIO) ---
        if not candidates:
            logger.warning("⚠️ Paso 1 (PaddleOCR GPU) sin candidatos. Ejecutando Paso 2: Tesseract (Fallback con Preprocesamiento)...")
            if self.vf:
                self.vf.show_persistent_message("PROCESANDO OCR (TESSERACT)...", "ocr", bg_color="#FFEB3B", fg_color="#000000")
            try:
                ocr_results_tess = self.execute_ocr_data(img_bgr, use_preprocessing=True)
                candidates_tess, rows_data_tess = self._analyze_candidates(ocr_results_tess, target_fecha_str)
                self.last_tesseract_results = ocr_results_tess
                self.last_tesseract_rows_data = rows_data_tess
                
                if candidates_tess:
                    logger.info(f"✅ Fallback de Tesseract exitoso. Encontrados {len(candidates_tess)} candidatos.")
                    candidates = candidates_tess
                    rows_data = rows_data_tess
                else:
                    logger.warning("❌ Paso 2 (Tesseract) también sin candidatos.")
            except Exception as e:
                logger.error(f"Error en fallback Tesseract: {e}")
            finally:
                if self.vf:
                    self.vf.hide_persistent_message("ocr")

        logger.info(f"Total Candidatos Finales: {len(candidates)}")

        self.save_detection_log_image(
            img_bgr=img_bgr,
            rows_data=rows_data,
            candidates=candidates,
            log_dir=log_dir,
            base_name=_log_base_name
        )
        
        if not candidates:
            logger.warning("No se encontraron filas con Fecha y Estado 'Hecho' en ninguno de los intentos.")
            logger.info("=== DEBUG: Contenido de filas detectadas (Último intento) ===")
            for i, r in enumerate(rows_data):
                row_items = sorted(r['items'], key=lambda x: x['center']['x'])
                txt = " ".join([item['text'] for item in row_items])
                logger.info(f"Fila {i} (Y={int(r['y_center'])}): {txt}")
            logger.info("============================================")
            
            self.last_diagnostic = self.diagnosticar_falla(
                rows_data=rows_data,
                candidates=[],
                target_fecha_str=target_fecha_str,
                target_diag=target_diag,
                ocr_results=locals().get('ocr_results', None),
                motivos_descarte=motivos_descarte
            )
            logger.warning(f"📋 Diagnóstico de causa raíz: {self.last_diagnostic}")
            return False, ""
                
        logger.info(f"Candidatos iniciales (Fecha + Estado): {len(candidates)}")
        
        # FASE 1: Búsqueda Local Rápida
        logger.info(f"=== FASE 1: Búsqueda Local Rápida ({len(candidates)} candidatos) ===")
        for idx, cand in enumerate(candidates):
            y_center = cand['y_center']
            y_click = cand.get('y_click', y_center)
            ocr_text_candidate = cand.get('full_text', "")

            score_f = cand.get('score_fecha', 0)
            if score_f < 80 or cand.get('es_fallback_fecha', False) or not cand.get('has_date', False):
                logger.info(
                    f"ℹ️ [Fase 1] Candidato #{idx+1} tiene 'Examen Hecho' pero la fecha requiere validación "
                    f"({cand.get('motivo_fecha', '')}, score={score_f}). Se deriva a FASE 2 (LLM)."
                )
                continue

            if not self.verificar_lateralidad(target_diag, ocr_text_candidate):
                logger.info(f"🚫 [Fase 1] Candidato #{idx+1} descartado por lateralidad anatómica incompatible: '{ocr_text_candidate[:60]}'")
                motivos_descarte.append(f"Lateralidad anatómica incompatible ('{target_diag}' vs '{ocr_text_candidate[:50]}')")
                continue

            ocr_norm = self.normalize_text(ocr_text_candidate)
            target_norm = self.normalize_text(target_diag)

            # NIVEL 0: Sinónimos BD
            sinonimo_bd = self.buscar_sinonimo(target_diag, ocr_text_candidate)
            if sinonimo_bd:
                sinonimo_norm = self.normalize_text(sinonimo_bd)
                score_sin_partial = fuzz.partial_ratio(sinonimo_norm, ocr_norm)
                score_sin_token   = fuzz.token_set_ratio(sinonimo_norm, ocr_norm)
                logger.info(f"📚 Sinónimo BD: '{sinonimo_bd}' | partial={score_sin_partial} token={score_sin_token}")
                if score_sin_partial > 72 or score_sin_token > 72:
                    if self.auditor:
                        if self.vf: self.vf.show_persistent_message("🛡️ AUDITANDO SINÓNIMO...", "audit")
                        aprobado, razon, _ = self.auditor.auditar(
                            target_diag=target_diag,
                            ocr_candidato=ocr_text_candidate,
                            metodo="sinonimo_bd",
                            score=max(score_sin_partial, score_sin_token),
                            id_registro=id_registro
                        )
                        if self.vf: self.vf.hide_persistent_message("audit")
                        if not aprobado:
                            logger.warning(f"🛡️ [AUDITOR RECHAZA] Candidato por Sinónimo BD descartado: {razon}")
                            continue

                    score_sin = max(score_sin_partial, score_sin_token)
                    if score_sin >= 90:
                        logger.info(f"✅ MATCH POR SINÓNIMO BD ALTA CERTEZA + AUDITOR (Fase 1, score={score_sin} >= 90%) → clic directo en Y={int(y_click)}")
                        self.click_target(y_click, img_bgr=img_bgr, log_dir=log_dir, base_name=_log_base_name)
                        return True, ''

                    logger.info(f"🤖 [CHECK LLM INTERMEDIO] Ejecutando validación semántica con LLM antes de hacer clic (Sinónimo BD={score_sin})...")
                    if self.vf:
                        self.vf.show_persistent_message("🤖 VALIDACIÓN FINAL LLM ANTES DE CLIC...", "llm", bg_color="#2196F3", fg_color="#FFFFFF")
                    is_match_llm = self.call_llm_text_verification(ocr_text_candidate, target_diag, target_fecha_str=target_fecha_str, id_registro=id_registro)
                    if not is_match_llm:
                        logger.warning(f"🚫 [CHECK FINAL LLM RECHAZADO] LLM rechazó el candidato de Sinónimo BD '{ocr_text_candidate[:50]}'. Descartando fila...")
                        continue

                    logger.info(f"✅ MATCH POR SINÓNIMO BD + AUDITOR + LLM CONFIRMADO (Fase 1) → clic en Y={int(y_click)}")
                    self.click_target(y_click, img_bgr=img_bgr, log_dir=log_dir, base_name=_log_base_name)
                    return True, ''

            # NIVEL 1: Verificación Local
            frag_estudio = self.extraer_fragmento_estudio(ocr_text_candidate)
            frag_med_norm = self.normalizar_terminologia_medica(frag_estudio)
            target_med_norm = self.normalizar_terminologia_medica(target_diag)

            score_frag_ratio = fuzz.ratio(target_med_norm, frag_med_norm) if frag_med_norm else 0
            score_frag_token = fuzz.token_set_ratio(target_med_norm, frag_med_norm) if frag_med_norm else 0
            score_frag_partial = fuzz.partial_ratio(target_med_norm, frag_med_norm) if frag_med_norm else 0
            best_frag_score = max(score_frag_ratio, score_frag_token, score_frag_partial)

            score_partial = fuzz.partial_ratio(target_norm, ocr_norm)
            score_token = fuzz.token_set_ratio(target_norm, ocr_norm)

            es_match_local = False
            metodo_match = "fuzzy_local"
            score_utilizado = max(score_partial, score_token)

            if best_frag_score >= 75:
                es_match_local = True
                metodo_match = "acronimo_medico_local"
                score_utilizado = best_frag_score
                logger.info(f"🩺 Match local por normalización médica ({best_frag_score}%): target='{target_med_norm}' vs frag='{frag_med_norm}'")
            elif score_partial > 85 or score_token > 85:
                es_match_local = True
                score_utilizado = max(score_partial, score_token)

            if es_match_local:
                if self.auditor:
                    if self.vf: self.vf.show_persistent_message("🛡️ AUDITANDO OCR LOCAL...", "audit")
                    aprobado, razon, _ = self.auditor.auditar(
                        target_diag=target_diag,
                        ocr_candidato=ocr_text_candidate,
                        metodo=metodo_match,
                        score=score_utilizado,
                        id_registro=id_registro
                    )
                    if self.vf: self.vf.hide_persistent_message("audit")
                    if not aprobado:
                        logger.warning(f"🛡️ [AUDITOR RECHAZA] Match {metodo_match} descartado: {razon}")
                        motivos_descarte.append(f"Auditor rechazó: {razon}")
                        continue

                umbral_directo = 85 if metodo_match == 'acronimo_medico_local' else 90
                if score_utilizado >= umbral_directo:
                    logger.info(f"✅ MATCH LOCAL DE ALTA FIDELIDAD + AUDITOR CONFIRMADO (Fase 1, {metodo_match}={score_utilizado} >= {umbral_directo}%) → clic directo en Y={int(y_click)}")
                    self.click_target(y_click, img_bgr=img_bgr, log_dir=log_dir, base_name=_log_base_name)
                    return True, ''

                logger.info(f"🤖 [CHECK LLM INTERMEDIO] Ejecutando validación semántica con LLM antes de hacer clic ({metodo_match}={score_utilizado})...")
                if self.vf:
                    self.vf.show_persistent_message("🤖 VALIDACIÓN FINAL LLM ANTES DE CLIC...", "llm", bg_color="#2196F3", fg_color="#FFFFFF")
                is_match_llm = self.call_llm_text_verification(ocr_text_candidate, target_diag, target_fecha_str=target_fecha_str, id_registro=id_registro)
                if not is_match_llm:
                    logger.warning(f"🚫 [CHECK LLM RECHAZADO] LLM rechazó el candidato local ({metodo_match}) '{ocr_text_candidate[:50]}'. Descartando fila...")
                    motivos_descarte.append(f"LLM rechazó coincidencia semántica con '{ocr_text_candidate[:50]}'")
                    continue

                logger.info(f"✅ MATCH LOCAL + AUDITOR + LLM CONFIRMADO (Fase 1, {metodo_match}={score_utilizado}) → clic en Y={int(y_click)}")
                self.click_target(y_click, img_bgr=img_bgr, log_dir=log_dir, base_name=_log_base_name)
                return True, ''

        # FASE 2: Verificación con LLM
        logger.info("=== FASE 2: Sin coincidencia local previa. Evaluando con LLM ===")
        valid_llm_candidates = []
        for cand in candidates:
            if not cand.get('has_date', False) or cand.get('score_fecha', 0) == 0:
                continue
            ocr_text_cand = cand.get('full_text', "")
            if not self._pre_filter_llm(ocr_text_cand, target_diag):
                continue

            t_norm = self.normalize_text(target_diag)
            o_norm = self.normalize_text(ocr_text_cand)
            score_full = max(fuzz.partial_ratio(t_norm, o_norm), fuzz.token_set_ratio(t_norm, o_norm))

            frag_estudio = self.extraer_fragmento_estudio(ocr_text_cand)
            frag_med_norm = self.normalizar_terminologia_medica(frag_estudio)
            target_med_norm = self.normalizar_terminologia_medica(target_diag)
            score_frag = max(
                fuzz.ratio(target_med_norm, frag_med_norm),
                fuzz.token_set_ratio(target_med_norm, frag_med_norm),
                fuzz.partial_ratio(target_med_norm, frag_med_norm)
            ) if frag_med_norm else 0

            cand['_fuzzy_score'] = max(score_full, score_frag)
            valid_llm_candidates.append(cand)

        valid_llm_candidates.sort(key=lambda c: c.get('_fuzzy_score', 0), reverse=True)

        for idx, cand in enumerate(valid_llm_candidates):
            y_center = cand['y_center']
            y_click = cand.get('y_click', y_center)
            ocr_text_candidate = cand.get('full_text', "")
            logger.info(
                f"--- [LLM] Verificando Candidato #{idx+1} (Score={cand.get('_fuzzy_score', 0)} | "
                f"Y_center={int(y_center)} | Y_click={int(y_click)}) ---"
            )
            is_match_llm = self.call_llm_text_verification(ocr_text_candidate, target_diag, target_fecha_str=target_fecha_str, id_registro=id_registro)
            if is_match_llm:
                if self.auditor:
                    if self.vf: self.vf.show_persistent_message("🛡️ AUDITANDO MATCH LLM...", "audit")
                    aprobado, razon, _ = self.auditor.auditar(
                        target_diag=target_diag,
                        ocr_candidato=ocr_text_candidate,
                        metodo="llm",
                        score=1.0,
                        requiere_llm=False,
                        id_registro=id_registro
                    )
                    if self.vf: self.vf.hide_persistent_message("audit")
                    if not aprobado:
                        fuzzy_c = cand.get('_fuzzy_score', 0)
                        es_bloqueo_duro = any(k in razon for k in ("IZQUIERDO", "DERECHO", "Lateralidad", "Modalidad"))
                        if fuzzy_c >= 70 and not es_bloqueo_duro:
                            logger.info(f"✅ [REVISIÓN LLM VALIDADA] Candidato ({fuzzy_c:.1f}%) aprobado por LLM superando objeción determinista del auditor: {razon}")
                            aprobado = True
                        else:
                            logger.warning(f"🛡️ [AUDITOR RECHAZA] Match LLM descartado por auditoría clínica: {razon}")
                            continue

                logger.info(f"✅ MATCH LLM CONFIRMADO (Fase 2) → clic en Y={int(y_click)}")
                self.click_target(y_click, img_bgr=img_bgr, log_dir=log_dir, base_name=_log_base_name)
                return True, ''
            else:
                logger.info("❌ LLM rechazó el candidato.")
                motivos_descarte.append(f"LLM rechazó coincidencia semántica con '{ocr_text_candidate[:50]}'")

        logger.warning("Ningún candidato coincidió con el diagnóstico.")
        self.last_diagnostic = self.diagnosticar_falla(
            rows_data=rows_data,
            candidates=candidates,
            target_fecha_str=target_fecha_str,
            target_diag=target_diag,
            ocr_results=locals().get('ocr_results', None),
            motivos_descarte=motivos_descarte
        )
        logger.warning(f"📋 Diagnóstico de causa raíz: {self.last_diagnostic}")
        best_ocr = candidates[0].get('full_text', '') if candidates else ''
        return False, best_ocr


def main():
    time.sleep(2)  # Dar tiempo para ocultar esta ventana
    setup_logging()

    while True:
        search = BusquedaTextOnly()

        id_registro, target_diag_raw, target_fecha_obj = search.get_db_targets()
        override_diag = None
        last_ocr_text = ""

        if target_diag_raw:
            sinonimo = search.buscar_sinonimo(target_diag_raw, "")
            if sinonimo:
                if search.auditor:
                    aprobado, razon, _ = search.auditor.auditar(
                        target_diag=target_diag_raw,
                        ocr_candidato=sinonimo,
                        metodo="sinonimo_bd",
                        score=100
                    )
                    if aprobado:
                        logger.info(f"📚 Sinónimo validado por Auditor Clínico: '{sinonimo}'. Se usará en lugar de '{target_diag_raw}'.")
                        override_diag = sinonimo
                    else:
                        logger.warning(f"🚫 Sinónimo en BD '{sinonimo}' RECHAZADO por Auditor Clínico ({razon}). Se mantiene original: '{target_diag_raw}'.")
                else:
                    logger.info(f"📚 Sinónimo hallado en BD: '{sinonimo}'. Se usará en lugar de '{target_diag_raw}'.")
                    override_diag = sinonimo

        found = False
        for attempt in range(search.MAX_RETRIES + 1):
            attempt_num = attempt + 1
            logger.info(f"{'='*60}")
            logger.info(f"INTENTO {attempt_num} DE {search.MAX_RETRIES + 1}")
            logger.info(f"{'='*60}")

            try:
                result, last_ocr_text = search.execute(override_diag=override_diag)

                if result:
                    logger.info("✅ Proceso completado exitosamente")
                    found = True
                    break
                else:
                    if attempt < search.MAX_RETRIES:
                        logger.warning(f"⚠️ Intento {attempt_num} falló. Reintentando...")
                        time.sleep(2)
            except Exception as e:
                logger.error(f"Error durante ejecución: {e}", exc_info=True)
                if attempt < search.MAX_RETRIES:
                    time.sleep(2)

        if found:
            sys.exit(0)

        logger.warning("⚠️ Todos los reintentos fallaron. Notificando y terminando.")
        if getattr(search, 'last_diagnostic', None):
            error_msg = f"Búsqueda fallida: {search.last_diagnostic} (tras {search.MAX_RETRIES + 1} intentos)."
        else:
            error_msg = f"Búsqueda fallida: no se encontró '{target_diag_raw}' (OCR detectó: '{last_ocr_text}') tras {search.MAX_RETRIES + 1} intentos."
        
        target_f_str = target_fecha_obj.strftime("%d-%m-%Y") if target_fecha_obj else ""
        ocr_info = search.get_ocr_comparison_info(target_fecha_str=target_f_str, target_diag=target_diag_raw)

        _error_handler_llamado = False
        for _mod in ['utils.error_handler', 'rpa_framework.utils.error_handler']:
            try:
                import importlib
                _eh = importlib.import_module(_mod)
                import inspect
                sig = inspect.signature(_eh.handle_error_and_exit)
                if "ocr_info" in sig.parameters:
                    _eh.handle_error_and_exit("busqueda_triple_text_only.py", error_msg, record_id=id_registro, ocr_info=ocr_info)
                else:
                    _eh.handle_error_and_exit("busqueda_triple_text_only.py", error_msg, record_id=id_registro)
                _error_handler_llamado = True
                break
            except Exception as _e:
                logger.warning(f"No se pudo importar {_mod}: {_e}")
        
        if not _error_handler_llamado:
            try:
                tess_lines = "\n".join([f"  • {t}" for t in ocr_info.get('tesseract', [])])
                padd_lines = "\n".join([f"  • {p}" for p in ocr_info.get('paddle', [])])
                msg_alerta = (
                    f"❌ <b>Búsqueda Fallida</b>\n{error_msg}\n\n"
                    f"<b>🔍 Tesseract:</b>\n{tess_lines}\n\n"
                    f"<b>⚡ PaddleOCR:</b>\n{padd_lines}"
                )
                enviar_alerta_todos(msg_alerta)
            except Exception:
                pass
            search.update_db_error(error_msg)
            sys.exit(1)


if __name__ == "__main__":
    main()
