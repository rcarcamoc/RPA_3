# -*- coding: utf-8 -*-
"""
llm_cascade_mixin.py — Pre-filtro clínico anti-alucinación y cascada multi-proveedor
(Ollama GPU / Nvidia NIM / OpenRouter) para validación semántica de exámenes OCR.
Extraído de busqueda_triple_text_only.py.
"""

import os
import re
import json
import time
import logging
import requests
from rapidfuzz import fuzz

from utils.llm_config import (
    OCR_DEFAULT_MODELS,
    LLM_DEFAULT_TEMPERATURE,
    get_ranked_models,
    get_llm_request_params,
)

logger = logging.getLogger(__name__)

# Umbral mínimo de similitud fuzzy para siquiera consultar al LLM.
MIN_FUZZY_FOR_LLM = 30

# Confianza mínima que el LLM debe reportar para aceptar un match.
LLM_MIN_CONFIDENCE = 0.70

# Circuit Breaker en memoria para modelos caídos ({model_id: timestamp_fallo})
_CIRCUIT_BREAKER_DOWN_MODELS = {}


class TripleSearchLLMCascadeMixin:
    """Mixin con pre-filtro clínico y cascada LLM para BusquedaTextOnly."""

    def _pre_filter_llm(self, ocr_text: str, target_diag: str) -> bool:
        """
        Pre-filtro anti-alucinación y seguridad clínica:
        1. Calcula la similitud fuzzy y médica (fila completa y fragmento normalizado).
        2. Si la similitud supera el 70% de confianza, se deriva al LLM para revisión médica experta,
           incluso si fue objetado inicialmente por el filtro del auditor determinista
           (salvo conflicto explícito de lateralidad opuesta).
        3. Si la similitud es < 70%, exige aprobación estricta del Auditor Clínico
           y al menos MIN_FUZZY_FOR_LLM.
        """
        target_norm = self.normalize_text(target_diag)
        ocr_norm    = self.normalize_text(ocr_text)

        score_partial = fuzz.partial_ratio(target_norm, ocr_norm)
        score_token   = fuzz.token_set_ratio(target_norm, ocr_norm)
        score_full    = max(score_partial, score_token)

        frag_estudio    = self.extraer_fragmento_estudio(ocr_text)
        frag_med_norm   = self.normalizar_terminologia_medica(frag_estudio)
        target_med_norm = self.normalizar_terminologia_medica(target_diag)
        score_frag      = max(
            fuzz.ratio(target_med_norm, frag_med_norm),
            fuzz.token_set_ratio(target_med_norm, frag_med_norm),
            fuzz.partial_ratio(target_med_norm, frag_med_norm)
        ) if frag_med_norm else 0

        confianza = max(score_full, score_frag)

        logger.info(
            f"🔍 Pre-filtro LLM | target='{target_diag}' | ocr='{ocr_text[:60]}' "
            f"| full={score_full} frag={score_frag} → confianza={confianza:.1f}% (min={MIN_FUZZY_FOR_LLM}%)"
        )

        # 1. Auditoría Clínica Determinista de Nivel 1
        auditor_aprobado = True
        auditor_razon = "OK"
        if self.auditor:
            auditor_aprobado, auditor_razon, _ = self.auditor.auditar(
                target_diag, ocr_text, metodo='pre_filtro_llm', requiere_llm=False
            )
        else:
            if not self.verificar_lateralidad(target_diag, ocr_text):
                auditor_aprobado = False
                auditor_razon = "Incompatibilidad de lateralidad anatómica"

        # Caso A: El auditor aprueba
        if auditor_aprobado:
            if confianza < MIN_FUZZY_FOR_LLM:
                logger.warning(
                    f"🚫 Pre-filtro RECHAZA llamar al LLM (score={confianza:.1f} < {MIN_FUZZY_FOR_LLM}). "
                    f"Los textos son demasiado diferentes para ser el mismo examen."
                )
                return False
            return True

        # Caso B: El auditor rechaza, pero la confianza es >= 70%
        if confianza >= 70:
            if "Modalidad" in auditor_razon or "Lateralidad" in auditor_razon:
                logger.warning(
                    f"🚫 Pre-filtro RECHAZA llamar al LLM por bloqueo clínico duro ({auditor_razon}): "
                    f"target='{target_diag}' vs ocr='{ocr_text[:60]}'."
                )
                return False

            t_words = set(target_norm.split())
            o_words = set(ocr_norm.split())
            der_set = {'derecho', 'derecha', 'der', 'dcha', 'dcho'}
            izq_set = {'izquierdo', 'izquierda', 'izq', 'izda'}
            t_es_der = bool(t_words & der_set) and not bool(t_words & izq_set)
            t_es_izq = bool(t_words & izq_set) and not bool(t_words & der_set)
            o_es_der = bool(o_words & der_set) and not bool(o_words & izq_set)
            o_es_izq = bool(o_words & izq_set) and not bool(o_words & der_set)

            if (t_es_der and o_es_izq) or (t_es_izq and o_es_der):
                logger.warning(
                    f"🚫 Pre-filtro RECHAZA llamar al LLM por conflicto crítico de lateralidad opuesta: "
                    f"target='{target_diag}' vs ocr='{ocr_text[:60]}'."
                )
                return False

            logger.info(
                f"🤖 [DERIVACIÓN LLM >70%] Confianza={confianza:.1f}% >= 70%. "
                f"Candidato no pasó filtro del auditor ({auditor_razon}), pero se deriva al LLM para revisión médica experta."
            )
            return True

        # Caso C: Rechazado por auditor y confianza < 70%
        logger.warning(
            f"🚫 Pre-filtro RECHAZA llamar al LLM: {auditor_razon} y confianza={confianza:.1f}% < 70% "
            f"(target='{target_diag}' | ocr='{ocr_text[:60]}')."
        )
        return False

    def call_llm_text_verification(self, ocr_text, target_diag, target_fecha_str=None, id_registro=0):
        """
        Consulta al LLM si el texto encontrado coincide semánticamente con el objetivo.
        Implementa fallback entre varios modelos si falla uno.
        Cada intento se registra en 'log_llm_ranking' para evaluar desempeño.
        """
        if not self._pre_filter_llm(ocr_text, target_diag):
            return False

        models = get_ranked_models(OCR_DEFAULT_MODELS, contexto='busqueda_ocr')

        fecha_linea_buscado = f'\n- Fecha agendada objetivo: "{target_fecha_str}" (formato estándar DD-MM-YYYY: día-mes-año)' if target_fecha_str else ""
        fecha_paso = """5. Comprueba si la fecha visible en la fila OCR corresponde a la fecha agendada buscada (admitiendo DD/MM/YYYY o MM/DD/YYYY). Si la fecha no coincide, responde es_match: false.\n""" if target_fecha_str else ""

        prompt = f"""
Eres un experto clínico en interpretación de terminología radiológica, exámenes de imagen y registros en sistemas PACS/RIS.
Tu tarea es determinar si la línea ENCONTRADA en el visor PACS (puede tener errores típicos de OCR) 
describe el mismo examen Y corresponde a la misma fecha agendada que el registro BUSCADO.

BUSCADO:
- Examen: "{target_diag}"{fecha_linea_buscado}

ENCONTRADO (línea completa OCR): "{ocr_text}"

---
## REGLAS DE EQUIVALENCIA (Tolerancia OCR razonable)

1. **ACRÓNIMOS Y MODALIDADES**:
   - RESONANCIA MAGNÉTICA ≈ RM ≈ RMNC ≈ RIM ≈ RNM ≈ RAM ≈ MRI.
   - TOMOGRAFÍA COMPUTADA ≈ TC ≈ TAC ≈ CT ≈ T.C.
   - ULTRASONIDO ≈ ECOTOMOGRAFÍA ≈ ECO ≈ US.
   - RADIOGRAFÍA ≈ RX ≈ R-X (incluye prefijos unidos: "RxAbdomen" ≈ "RX Abdomen", "RxTorax" ≈ "RX Tórax").
   - MAMOGRAFÍA ≈ KIAMOGRAFÍA ≈ HIAMOGRAFÍA ≈ HAMOGRAFÍA ≈ KMAMOGRAFÍA ≈ IAMOGRAFÍA ≈ HAMOG... (aberraciones frecuentes por corte central de la letra 'M' en el PACS).

2. **PROYECCIONES RADIOLÓGICAS (F-O / Frente-Oblicua / Frontal / Decúbito)**:
   - (F-O) ≈ F-O ≈ F-O: ≈ Frente y Oblicua ≈ Front y Oblicua ≈ Frente Oblicua ≈ Front Oblicua (en radiología se abrevia habitualmente 'front').
   - AP - L ≈ AP Lateral ≈ PA - Lat ≈ PA Lateral.
   - "Simple AP Decúbito" o "Decúbito Supino" en RX de Abdomen equivale clínicamente a "AP - L" o "Abdomen Simple".

3. **EQUIVALENCIAS ANATÓMICAS Y CONVENCIONES CLÍNICAS**:
   - **REGIÓN PERIAURICULAR / PREAURICULAR / RETROAURICULAR / PAROTÍDEA ↔ CARA / CUELLO**:
     La región periauricular, preauricular, retroauricular o parotídea pertenece anatómicamente a partes blandas de cara/cuello. 'Ecotomografía de partes blandas periauricular' (o preauricular/parotídea) es CLÍNICAMENTE EQUIVALENTE a 'Ecotomografía partes blandas de cara' o 'partes blandas cabeza y cuello'. Si en PACS está codificado como 'Partes blandas de cara' sin lateralidad explícita, acéptalo como coincidencia válida (es_match: true).
   - **ECOTOMOGRAFÍA MAMARIA / MAMOGRAFÍA (Protocolo Bilateral por defecto)**:
     Por protocolo clínico institucional en centros de salud, la ecografía mamaria y la mamografía son bilaterales por defecto. Si el examen buscado es 'Ecotomografía mamaria bilateral' o 'Mamografía bilateral' y en el PACS figura simplemente 'Ecotomografía Mamaria' o 'Mamografía' (sin especificar derecha ni izquierda) o aberraciones como 'IiMamografía Bilate' / 'Mamografía Bilater..', DEBES considerarlo EQUIVALENTE (es_match: true), dado que cuando es unilateral el PACS siempre especifica expresamente el lado ('Derecha' o 'Izquierda'). NO descartes por lateralidad si ambos son mamografía bilateral o mamografía general.
   - **PROYECCIONES COMPLEMENTARIAS DE MAMA (MAMOGRAFÍA)**:
     En radiología mamaria, las órdenes de 'Proyecciones complementarias, en mama derecha / izquierda' o 'Proyecciones adicionales' corresponden en el PACS a estudios nombrados como 'Proyección Magnificada', 'Proyección Focalizada', 'Cono de Compresión' o 'Proyección Tangencial' con la misma lateralidad (ej. 'Proyección Magnificada Mama Derecha' == 'Proyecciones complementarias, en mama derecha'). DEBES considerarlas CLÍNICAMENTE EQUIVALENTES (es_match: true).

4. **CORRECCIÓN OCR PERMITIDA** (errores de carácter simples y fechas PACS):
   - Dígito '0' leído como '9' en meses (ej: '15-19-2026' corresponde clínicamente al 15 de Octubre '15-10-2026'). NO descartes si día y año coinciden.
   - Un carácter cambiado: "S"↔"5", "I"↔"1"↔"|", "O"↔"0", "B"↔"8".
   - Letras adicionales o faltantes al inicio/fin por segmentación (ej: "TAC" → "TAC ").
   - Acento o ñ incorrectos (ej: "Ecotomografia" ≈ "Ecotomografía").

5. **REGIÓN ANATÓMICA Y LATERALIDAD ESTRICTA**:
   - La región anatómica debe coincidir (considerando las equivalencias de cara/cuello y mamarias descritas en punto 3).
   - **LATERALIDAD OBLIGATORIA Y EXCLUYENTE**: Si el examen buscado especifica DERECHO/DERECHA o IZQUIERDO/IZQUIERDA o BILATERAL, el texto ENCONTRADO DEBE coincidir con dicha lateralidad (salvo la excepción del protocolo bilateral mamario y partes blandas de cara descritas en el punto 3). "Bilater.." o "Bilat" representa BILATERAL. Un examen de 'Tobillo Izquierdo' NUNCA es equivalente a 'Tobillo Derecho'. Si la lateralidad es contraria o diferente, DEBES responder es_match: false.
---
## PROHIBICIONES ESTRICTAS (estas situaciones = es_match: false)

- ❌ NO aceptar si la lateralidad anatómica difiere en absoluto (derecho vs izquierdo, der vs izq, bilateral vs unilateral).
- ❌ NO aceptar si la corrección requiere cambiar MÁS DE 3 caracteres simultáneamente.
- ❌ NO inventar palabras completas: si el OCR dice "Prortario" NO puede ser "TAC Cerebro".
- ❌ NO aceptar si la modalidad (TAC, RM, RX, ECO) no tiene ninguna representación reconocible en el ENCONTRADO.
- ❌ NO aceptar si la región anatómica no coincide en absoluto.
- ❌ NO aceptar si tienes dudas razonables (usa confianza baja → es_match: false).

---
## PROCESO DE RAZONAMIENTO

1. Extrae del ENCONTRADO el segmento que parece el nombre del examen.
2. Comprueba si la lateralidad coincide exactamente (derecho/izquierdo/bilateral). Si no coincide, es_match: false.
3. Aplica corrección OCR MÍNIMA (≤3 caracteres). ¿Qué examen queda?
4. ¿Ese examen equivale al BUSCADO?
{fecha_paso}6. Si en algún paso necesitaste cambiar palabras enteras o cambiar de extremidad o la fecha no corresponde, responde es_match: false.

RESPONDE SOLO EN FORMATO JSON:
{{
  "es_match": true o false,
  "razonamiento": "Explicación concreta y breve (máx 100 chars)",
  "confianza": 0.0-1.0
}}
"""

        if self.vf:
            self.vf.show_persistent_message("PROCESANDO LLM (Cascada)...", "llm", bg_color="#FFEB3B", fg_color="#000000")

        models_to_evaluate = models if models else get_ranked_models(contexto='busqueda_ocr')
        LLM_OCR_MAX_TOKENS = 1500
        LLM_OCR_TIMEOUT = (3.0, 20.0)
        CURRENT_TIME = time.time()
        CIRCUIT_BREAKER_COOLDOWN = 60
        openrouter_key = os.getenv("OPENROUTER_API_KEY", "")

        try:
            for idx, model_id in enumerate(models_to_evaluate):
                if model_id in _CIRCUIT_BREAKER_DOWN_MODELS:
                    down_time = _CIRCUIT_BREAKER_DOWN_MODELS[model_id]
                    if CURRENT_TIME - down_time < CIRCUIT_BREAKER_COOLDOWN:
                        logger.info(f"⚡ [Circuit Breaker] Saltando {model_id} (en enfriamiento por fallo reciente).")
                        continue
                    else:
                        del _CIRCUIT_BREAKER_DOWN_MODELS[model_id]

                start_time = time.time()
                base_url, target_key, provider = get_llm_request_params(model_id)
                if provider == "ollama":
                    logger.info(f"🧠 [Cascada LLM Tier {idx+1} - OLLAMA LOCAL GPU] Consultando {model_id} en GTX 1070...")
                    current_timeout = (3.0, 15.0)
                    tokens_limit = 250
                else:
                    logger.info(f"🧠 [Cascada LLM Tier {idx+1} - CLOUD WEB FALLBACK] Consultando {model_id} ({provider})...")
                    current_timeout = LLM_OCR_TIMEOUT
                    tokens_limit = LLM_OCR_MAX_TOKENS

                try:
                    if not target_key and provider != "ollama":
                        target_key = openrouter_key
                    response = requests.post(
                        f"{base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {target_key}",
                            "Content-Type":  "application/json",
                            "HTTP-Referer":  "https://rpa-framework.local",
                        },
                        json={
                            "model":       model_id,
                            "messages":    [{"role": "user", "content": prompt}],
                            "temperature": LLM_DEFAULT_TEMPERATURE,
                            "max_tokens":  tokens_limit,
                        },
                        timeout=current_timeout,
                    )

                    elapsed_ms = int((time.time() - start_time) * 1000)

                    if response.status_code == 429:
                        logger.warning(f"⚠️ [Cascada] {model_id} → 429 Rate Limit. Activando Circuit Breaker y pasando a siguiente Tier.")
                        _CIRCUIT_BREAKER_DOWN_MODELS[model_id] = time.time()
                        continue
                    elif response.status_code != 200:
                        logger.warning(f"⚠️ [Cascada] {model_id} → HTTP {response.status_code}. Pasando a siguiente Tier.")
                        _CIRCUIT_BREAKER_DOWN_MODELS[model_id] = time.time()
                        continue

                    response.raise_for_status()
                    result = response.json()

                    if not result or "choices" not in result or not result["choices"]:
                        logger.warning(f"⚠️ [Cascada] {model_id} → Respuesta vacía o sin choices.")
                        continue

                    content = (result["choices"][0].get("message") or {}).get("content") or ""
                    logger.info(f"[Cascada] {model_id}: {content[:160]}...")

                    cleaned_content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
                    if not cleaned_content:
                        cleaned_content = content

                    json_match = re.search(r"\{[^{}]*\"es_match\"[^{}]*\}", cleaned_content, re.DOTALL)
                    if not json_match:
                        json_match = re.search(r"\{.*?\"es_match\".*?\}", cleaned_content, re.DOTALL)
                    if not json_match:
                        json_match = re.search(r"\{.*?\}", cleaned_content, re.DOTALL)

                    data = None
                    if json_match:
                        try:
                            data = json.loads(json_match.group(0))
                        except Exception:
                            data = None

                    if data is not None and "es_match" in data:
                        is_match = bool(data.get("es_match", False))
                        confianza = float(data.get("confianza", 0.0))
                        razonamiento = str(data.get("razonamiento", ""))
                    else:
                        logger.warning(f"⚠️ [Cascada] {model_id} → Sin JSON estructurado válido con 'es_match' en respuesta.")
                        continue

                    logger.info(
                        f"📊 [Cascada Tier {idx+1}] {model_id} ({elapsed_ms}ms) → "
                        f"match={is_match} conf={confianza:.2f} | {razonamiento[:80]}"
                    )

                    try:
                        self.log_llm_ranking(
                            id_registro=id_registro,
                            modelo=model_id,
                            target_buscado=target_diag,
                            texto_ocr=ocr_text,
                            es_match=is_match,
                            razonamiento=razonamiento,
                            confianza=confianza,
                            tiempo_ms=elapsed_ms,
                            es_primer_intento=(idx == 0)
                        )
                    except Exception as log_err:
                        logger.warning(f"No se pudo registrar log_llm_ranking: {log_err}")

                    if is_match and confianza >= LLM_MIN_CONFIDENCE:
                        logger.info(f"🏆 [Cascada] Coincidencia positiva confirmada por {model_id} en {elapsed_ms}ms.")
                        return True
                    elif not is_match and (confianza >= 0.85 or confianza == 0.0):
                        logger.info(f"🛑 [Cascada] Descarte certero confirmado por {model_id} en {elapsed_ms}ms. Rechazando candidato.")
                        return False
                    else:
                        logger.info(f"⚖️ [Cascada] Decisión dudosa ({confianza:.2f}) de {model_id}. Escalando a siguiente Tier...")
                        continue

                except Exception as e:
                    elapsed_ms = int((time.time() - start_time) * 1000)
                    logger.warning(f"❌ [Cascada] {model_id} falló ({elapsed_ms}ms): {e}. Conmutando a siguiente Tier de inmediato...")
                    _CIRCUIT_BREAKER_DOWN_MODELS[model_id] = time.time()
                    continue

            logger.warning("⚠️ [Cascada] Ningún modelo de la cascada confirmó coincidencia positiva.")
            return False

        finally:
            if self.vf:
                self.vf.hide_persistent_message("llm")
