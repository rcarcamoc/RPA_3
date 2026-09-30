#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Módulo: auditor_clinico.py
Descripción: Auditor Clínico especializado para validación pre-clic en el flujo
de Búsqueda Triple (PACS/OCR). Intercepta y audita todas las coincidencias
(sinónimos BD, fuzzy local y LLM) garantizando compatibilidad de:
1. Modalidad (RX, TC, RM, ECO).
2. Sub-modalidad y técnica (Doppler/Vascular vs. Simple, Angio vs. Estándar, Colangio, Pielo).
3. Región anatómica estricta (Columna por segmentos, EESS, EEII, Abdomen vs. Pelvis).
4. Lateralidad clínica (Derecho, Izquierdo, Bilateral).

Ubicación: rpa_framework/recordings/ocr/auditor_clinico.py
"""

import re
import unicodedata
import logging
import os
import json
import time
from typing import Tuple, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Cargar variables de entorno si están disponibles
try:
    from dotenv import load_dotenv
    from pathlib import Path
    project_root = Path(__file__).parent.parent.parent.parent
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=True)
    else:
        load_dotenv()
except Exception:
    pass

# Importar configuración de LLMs si está disponible
try:
    from rpa_framework.utils.llm_config import (
        get_llm_request_params,
        get_ranked_models,
        get_models_for_context,
        LLM_DEFAULT_TEMPERATURE
    )
    HAS_LLM_CONFIG = True
except ImportError:
    try:
        from utils.llm_config import (
            get_llm_request_params,
            get_ranked_models,
            get_models_for_context,
            LLM_DEFAULT_TEMPERATURE
        )
        HAS_LLM_CONFIG = True
    except ImportError:
        HAS_LLM_CONFIG = False
        get_ranked_models = None
        get_models_for_context = None
        LLM_DEFAULT_TEMPERATURE = 0.0

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")


class AuditorClinico:
    """
    Auditor Clínico Pre-Clic.
    Garantiza que ningún examen reciba un clic erróneo debido a falsos positivos
    en OCR, fuzzy matching o alucinaciones de modelos LLM.
    """

    def __init__(self):
        # Tokens de Lateralidad (sin letras individuales para evitar falsos positivos con códigos o columnas como 'Normal B')
        self.TOKENS_DER = {'derecho', 'derecha', 'der', 'dcha', 'dcho'}
        self.TOKENS_IZQ = {'izquierdo', 'izquierda', 'izq', 'izda'}
        self.TOKENS_BILAT = {'bilateral', 'ambos', 'ambas', 'eeii', 'eess', 'bilat'}

    def obtener_modelos_auditor(self) -> list:
        """
        Obtiene dinámicamente los modelos activos desde la tabla ris.catalogo_modelos_llm
        y los ordena por rendimiento histórico en ris.log_llm_ranking.
        """
        if HAS_LLM_CONFIG and get_ranked_models:
            try:
                modelos = get_ranked_models(contexto='busqueda_ocr')
                if modelos:
                    return modelos
            except Exception as e:
                logger.warning(f"Error consultando catálogo de modelos dinámicos: {e}")
        return [
            "cohere/north-mini-code:free",
            "nvidia/nemotron-3-super-120b-a12b:free",
            "openrouter/free"
        ]

    # =========================================================================
    # 0. AUDITORÍA ESTRICTA DE FECHA (Anti-Estudios Antiguos)
    # =========================================================================
    def auditar_fecha(self, target_fecha_str: str, ocr_text: str) -> Tuple[bool, str, int]:
        """
        Valida que la fecha en el texto OCR coincida con la fecha agendada.
        Previene la trampa de fuzzy matching que aceptaba fechas de años anteriores.
        
        Retorna:
        (es_valida: bool, motivo: str, score_fecha: int [0-100])
        """
        if not target_fecha_str:
            return True, "Sin fecha objetivo para validar", 50

        # Normalizar fecha objetivo: DD-MM-YYYY
        parts = re.split(r'[-/.]', target_fecha_str.strip())
        if len(parts) != 3:
            # Fallback simple si no es formato estándar
            return (target_fecha_str in ocr_text), "Búsqueda directa de fecha", 100 if target_fecha_str in ocr_text else 0

        t_dia, t_mes, t_anio = parts[0].zfill(2), parts[1].zfill(2), parts[2]
        t_anio_short = t_anio[-2:] if len(t_anio) == 4 else t_anio

        # 1. Búsqueda exacta literal
        exact_patterns = [
            f"{t_dia}-{t_mes}-{t_anio}",
            f"{t_dia}/{t_mes}/{t_anio}",
            f"{t_dia}-{t_mes}-{t_anio_short}",
            f"{t_dia}/{t_mes}/{t_anio_short}",
        ]
        for p in exact_patterns:
            if p in ocr_text:
                return True, f"Fecha exacta encontrada: {p}", 100

        # 2. Extracción de fechas candidatas en el texto OCR mediante Regex
        # Soporta separadores comunes -, /, ., :, ; o espacios
        date_matches = re.findall(r'\b(\d{1,2})[-/.:;](\d{1,2})[-/.:;](\d{2,4})\b', ocr_text)
        
        if date_matches:
            for d, m, a in date_matches:
                d_str = d.zfill(2)
                m_str = m.zfill(2)
                a_str = a[-2:] if len(a) == 4 else a

                # El año DEBE coincidir obligatoriamente
                if a_str != t_anio_short:
                    continue

                # Caso 1: Mes exacto
                if m_str == t_mes:
                    # Si día coincide exacto
                    if d_str == t_dia:
                        return True, f"Fecha coincidente por regex: {d_str}-{m_str}-{a_str}", 100

                    # Tolerancia OCR leve solo en el DÍA si año y mes son idénticos
                    # (ej. confusión 1↔7, 0↔8, 3↔8 o diferencia de 1 dígito)
                    day_diff_chars = sum(1 for c1, c2 in zip(d_str, t_dia) if c1 != c2)
                    if day_diff_chars == 1:
                        return True, f"Fecha coincidente con tolerancia OCR en día: {d_str} vs {t_dia} (Mes/Año OK)", 80

                # Caso 2: Tolerancia OCR en el MES solo si DÍA y AÑO son IDÉNTICOS
                # (ej. '09' leído como '99' u '89' por binarizado de alto contraste).
                # SEGURIDAD CLÍNICA: Solo se tolera si el mes leído es inválido en calendario
                # (ej. 99, 89, 00) y difiere en 1 dígito del mes objetivo. Si es un mes válido (1 a 12),
                # se rechaza para no confundir meses clínicos reales distintos (ej. Junio vs Septiembre).
                elif d_str == t_dia:
                    if m_str.isdigit() and not (1 <= int(m_str) <= 12):
                        month_diff_chars = sum(1 for c1, c2 in zip(m_str, t_mes) if c1 != c2)
                        if month_diff_chars <= 1:
                            return True, f"Fecha coincidente con tolerancia OCR en mes: {d_str}-{m_str}-{a_str} vs target {target_fecha_str} (Día/Año exactos)", 85

            # Si se detectaron fechas pero ninguna coincidió en año/mes
            return False, "Fechas detectadas en fila pertenecen a otro año o mes", 0

        # 3. Búsqueda de dígitos continuos (ej. 10092026 o 100926)
        digits_target = f"{t_dia}{t_mes}{t_anio}"
        digits_target_short = f"{t_dia}{t_mes}{t_anio_short}"
        row_digits = "".join(filter(str.isdigit, ocr_text))

        if digits_target in row_digits:
            return True, f"Secuencia de dígitos de fecha completa encontrada: {digits_target}", 95
        if digits_target_short in row_digits:
            return True, f"Secuencia de dígitos de fecha corta encontrada: {digits_target_short}", 90

        return False, f"Fecha objetivo {target_fecha_str} no encontrada en la fila", 0

    # =========================================================================
    # 1. NORMALIZACIÓN
    # =========================================================================
    @staticmethod
    def normalizar_texto(texto: str) -> str:
        """Limpia tildes, signos de puntuación y espacios redundantes."""
        if not texto:
            return ""
        texto = texto.lower()
        texto = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
        texto = re.sub(r'[^a-z0-9\s]', ' ', texto)
        return ' '.join(texto.split())

    # =========================================================================
    # 2. AUDITORÍA DE LATERALIDAD
    # =========================================================================
    def auditar_lateralidad(self, target: str, ocr: str) -> Tuple[bool, str]:
        """
        Valida clínicamente la concordancia de lateralidad anatómica.
        Retorna (es_compatible, motivo).
        """
        t_norm = self.normalizar_texto(target)
        o_norm = self.normalizar_texto(ocr)

        t_words = set(t_norm.split())
        o_words = set(o_norm.split())

        t_has_der = bool(t_words & self.TOKENS_DER)
        t_has_izq = bool(t_words & self.TOKENS_IZQ)
        t_has_bilat = bool(t_words & self.TOKENS_BILAT)

        o_has_der = bool(o_words & self.TOKENS_DER)
        o_has_izq = bool(o_words & self.TOKENS_IZQ)
        o_has_bilat = bool(o_words & self.TOKENS_BILAT)

        # Caso Bilateral
        if t_has_bilat:
            if not o_has_bilat and not (o_has_der and o_has_izq):
                return False, "Target es BILATERAL pero candidato es unilateral"
        elif o_has_bilat:
            if (t_has_der or t_has_izq) and not (t_has_der and t_has_izq):
                return False, "Candidato es BILATERAL pero target es unilateral"

        # Caso Derecho estricto
        if t_has_der and not t_has_izq:
            if o_has_izq and not o_has_der:
                return False, "Target exige DERECHO pero candidato contiene IZQUIERDO"

        # Caso Izquierdo estricto
        if t_has_izq and not t_has_der:
            if o_has_der and not o_has_izq:
                return False, "Target exige IZQUIERDO pero candidato contiene DERECHO"

        return True, "Lateralidad concordante o no aplicable"

    # =========================================================================
    # 3. AUDITORÍA DE MODALIDAD
    # =========================================================================
    def detectar_modalidad(self, texto: str) -> str:
        """
        Detecta la modalidad de imagen principal: ECO, TC, RM, RX o DESCONOCIDA.
        """
        t = self.normalizar_texto(texto)
        words = set(t.split())

        # TC / Tomografía
        tc_tokens = {'tc', 'tac', 'ct', 'tomografia', 'angiotac', 'urotac', 'pielografia'}
        if bool(words & tc_tokens) or re.search(r'\bangio\s*tc\b', t) or 'angiotc' in words:
            return 'TC'

        # RM / Resonancia
        rm_tokens = {'rm', 'rmn', 'mri', 'resonancia', 'colangioresonancia'}
        if bool(words & rm_tokens) or re.search(r'\bcolangio\s*rm\b', t) or re.search(r'\bangio\s*rm\b', t):
            return 'RM'

        # RX / Radiografía (Evaluado con prioridad ante indicadores claros de radiografía)
        rx_tokens = {'rx', 'radiografia', 'proyecciones', 'proy', 'exp', 'fluoroscopia', 'panoramica'}
        has_rx = bool(words & rx_tokens) or bool(re.search(r'\br\s*x\b', t))
        if has_rx:
            return 'RX'

        # ECO / Ecotomografía
        # 'us' solo se considera si no hay indicadores de RX para evitar falsos positivos
        # con columnas/estados del PACS (ej: 'CRISM US N')
        eco_tokens = {'eco', 'ecografia', 'ecotomografia', 'ultrasonido', 'doppler'}
        if bool(words & eco_tokens):
            return 'ECO'
        if 'us' in words and not has_rx:
            return 'ECO'

        return 'DESCONOCIDA'

    def auditar_modalidad(self, target: str, ocr: str) -> Tuple[bool, str]:
        """Valida que no exista cruce prohibido de modalidades."""
        mod_t = self.detectar_modalidad(target)
        mod_o = self.detectar_modalidad(ocr)

        if mod_t != 'DESCONOCIDA' and mod_o != 'DESCONOCIDA':
            if mod_t != mod_o:
                return False, f"Conflicto de modalidad: Target es {mod_t} pero candidato es {mod_o}"

        return True, f"Modalidades compatibles ({mod_t} ~ {mod_o})"

    # =========================================================================
    # 4. AUDITORÍA DE SUB-MODALIDAD / TÉCNICA ESPECIALIZADA
    # =========================================================================
    def auditar_submodalidad(self, target: str, ocr: str) -> Tuple[bool, str]:
        """
        Valida que técnicas especializadas no se confundan con estudios estándar:
        - ECO Doppler / Vascular vs. ECO Partes Blandas / Articular / Simple (Fix ID 595).
        - Angio (Angiotac / Angio-RM) vs. Estudio simple.
        - Colangio-RM vs. RM general.
        - Pielo / Uro-TC.
        """
        t_norm = self.normalizar_texto(target)
        o_norm = self.normalizar_texto(ocr)

        t_words = set(t_norm.split())
        o_words = set(o_norm.split())

        # 1. Caso Especial: Glosa genérica de arancel Fonasa
        # 'ECOTOMOGRAFIA VASCULAR PERIFERICA, ARTICULAR O DE PARTES BLANDAS'
        # Al ser un paquete Fonasa amplio que engloba vascular, articular o partes blandas,
        # es flexible si la anatomía coincide.
        es_fonasa_sombrilla = ('vascular periferica' in t_norm and 'partes blandas' in t_norm)

        # 2. ECO Doppler / Vascular vs. Simple
        doppler_tokens = {'doppler', 'vascular', 'arterial', 'venosa', 'venoso', 'carotidea', 'carotideo', 'flujo'}
        t_is_doppler = bool(t_words & doppler_tokens) and not es_fonasa_sombrilla
        o_is_doppler = bool(o_words & doppler_tokens)

        if t_is_doppler and not o_is_doppler:
            return False, "Target exige ecografía DOPPLER/VASCULAR pero candidato es ecografía simple o articular"

        if o_is_doppler and not t_is_doppler and not es_fonasa_sombrilla:
            return False, "Candidato es ECO DOPPLER/VASCULAR pero target pide ecografía simple/partes blandas (Falso positivo tipo ID 595)"

        # 3. Colangio-RM (evaluar antes de angio para máxima especificidad)
        colangio_tokens = {'colangio', 'colangioresonancia'}
        t_is_colangio = bool(t_words & colangio_tokens) or bool(re.search(r'\bcolangio\s*rm\b', t_norm))
        o_is_colangio = bool(o_words & colangio_tokens) or bool(re.search(r'\bcolangio\s*rm\b', o_norm))

        if t_is_colangio and not o_is_colangio:
            return False, "Target exige COLANGIO RESONANCIA pero candidato no especifica técnica colangio"
        if o_is_colangio and not t_is_colangio:
            return False, "Candidato es COLANGIO RM pero target es otro tipo de resonancia"

        # 4. Angiografía (Angio-TC o Angio-RM) vs. Simple (usar \b para no chocar con colangio)
        angio_tokens = {'angio', 'angiografia', 'angiotac', 'angiotc'}
        t_is_angio = bool(t_words & angio_tokens) or bool(re.search(r'\bangio\s*(?:tc|tac|rm|rmn)\b', t_norm))
        o_is_angio = bool(o_words & angio_tokens) or bool(re.search(r'\bangio\s*(?:tc|tac|rm|rmn)\b', o_norm))

        if t_is_angio and not o_is_angio:
            return False, "Target exige ANGIOGRAFIA pero candidato es estudio convencional sin técnica angio"
        if o_is_angio and not t_is_angio:
            return False, "Candidato es ANGIOGRAFIA especializada pero target pide estudio estándar no-angio"

        # 5. Urografía / Pielografía
        pielo_tokens = {'pielografia', 'urografia', 'urotac'}
        t_is_pielo = bool(t_words & pielo_tokens)
        o_is_pielo = bool(o_words & pielo_tokens)

        if t_is_pielo and not o_is_pielo:
            return False, "Target exige PIELOGRAFIA/UROGRAFIA pero candidato no cuenta con dicha técnica"

        return True, "Sub-modalidad y técnica compatibles"

    # =========================================================================
    # 5. AUDITORÍA DE REGIÓN ANATÓMICA
    # =========================================================================
    def extraer_regiones_anatomicas(self, texto: str) -> Dict[str, Any]:
        """
        Extrae y clasifica las referencias anatómicas en compartimentos clínicos.
        """
        t = self.normalizar_texto(texto)
        words = set(t.split())

        res = {
            'columna': set(),
            'eess': set(),
            'eeii': set(),
            'torax': False,
            'abdomen': False,
            'pelvis': False,
            'cabeza_cuello': set(),
        }

        # --- Columna ---
        if bool(words & {'cervical', 'cervico', 'atlas', 'axis', 'c1', 'c2', 'c3', 'c4', 'c5', 'c6', 'c7'}):
            res['columna'].add('cervical')
        if bool(words & {'dorsal', 'toracica', 'dorsolumbar'}):
            res['columna'].add('dorsal')
        if bool(words & {'lumbar', 'lumbosacra', 'l1', 'l2', 'l3', 'l4', 'l5'}) or 'quinto espacio' in t:
            res['columna'].add('lumbar')
        if bool(words & {'sacro', 'sacrocoxis', 'coxis', 'sacroiliaca', 'sacroiliacas'}):
            res['columna'].add('sacro')
        if 'columna total' in t or ('columna' in words and 'total' in words):
            res['columna'].add('total')

        # --- Extremidad Superior (EESS) ---
        if bool(words & {'hombro', 'clavicula', 'escapula', 'acromioclavicular', 'manguito'}):
            res['eess'].add('hombro')
        if bool(words & {'brazo', 'humero'}) and 'antebrazo' not in words:
            res['eess'].add('brazo')
        if bool(words & {'codo', 'olecranon', 'epicondilo'}):
            res['eess'].add('codo')
        if bool(words & {'antebrazo', 'radio', 'cubito'}):
            res['eess'].add('antebrazo')
        if bool(words & {'muneca', 'carpo', 'escafoides', 'carpiano'}):
            res['eess'].add('muneca')
        if bool(words & {'mano', 'dedos', 'metacarpo', 'falanges'}) and 'pie' not in words:
            res['eess'].add('mano')

        # --- Extremidad Inferior (EEII) ---
        if bool(words & {'cadera', 'coxofemoral', 'lawenstein'}):
            res['eeii'].add('cadera')
        if bool(words & {'femur', 'muslo'}):
            res['eeii'].add('femur')
        if bool(words & {'rodilla', 'rotula', 'rotulas', 'menisco', 'popliteo', 'sesamoideos'}):
            res['eeii'].add('rodilla')
        if bool(words & {'pierna', 'tibia', 'perone', 'pantorrilla', 'gastrocnemio'}):
            res['eeii'].add('pierna')
        if bool(words & {'tobillo', 'maleolo', 'aquiles'}):
            res['eeii'].add('tobillo')
        if bool(words & {'pie', 'fascia', 'tarso', 'metatarso', 'plantar'}):
            res['eeii'].add('pie')

        # --- Tórax ---
        if bool(words & {'torax', 'pulmon', 'costal', 'costilla', 'costillas', 'esternon', 'parrilla'}):
            res['torax'] = True

        # --- Abdomen y Pelvis ---
        if bool(words & {'abdomen', 'abdominal', 'higado', 'vesicula', 'pancreas', 'bazo', 'renal', 'rinon', 'rinones'}):
            res['abdomen'] = True
        if bool(words & {'pelvis', 'pelviana', 'pelvica', 'prostata', 'vejiga', 'ginecologica', 'utero', 'ovario', 'ovarica'}):
            res['pelvis'] = True

        # --- Cabeza y Cuello ---
        if bool(words & {'craneo', 'cerebro', 'encefalo', 'encefalica', 'cerebral'}):
            res['cabeza_cuello'].add('cerebro')
        if bool(words & {'cuello', 'tiroides', 'tiroidea', 'laringe', 'cavum', 'rinofaringe'}):
            res['cabeza_cuello'].add('cuello')
        if bool(words & {'orbitas', 'orbita'}):
            res['cabeza_cuello'].add('orbitas')
        if bool(words & {'perinasales', 'paranasales', 'sinus', 'malar', 'maxilar', 'nasales'}):
            res['cabeza_cuello'].add('senos_cara')
        if bool(words & {'atm', 'temporomandibular'}):
            res['cabeza_cuello'].add('atm')

        return res

    def auditar_anatomia(self, target: str, ocr: str) -> Tuple[bool, str]:
        """
        Valida clínicamente que no existan conflictos anatómicos excluyentes.
        Ej: Columna Lumbar ≠ Columna Cervical; Hombro ≠ Codo; Abdomen puro ≠ Pelvis pura.
        """
        t_reg = self.extraer_regiones_anatomicas(target)
        o_reg = self.extraer_regiones_anatomicas(ocr)

        # 1. Conflicto de Segmentos en Columna
        if t_reg['columna'] and o_reg['columna']:
            # Si target pide segmento específico y candidato es otro incompatible
            if 'total' not in t_reg['columna'] and 'total' not in o_reg['columna']:
                # Cervical vs Lumbar / Sacro
                if 'cervical' in t_reg['columna'] and not ('cervical' in o_reg['columna']):
                    return False, f"Incompatibilidad de Columna: Target es Cervical pero candidato es {list(o_reg['columna'])}"
                if 'lumbar' in t_reg['columna'] and 'cervical' in o_reg['columna']:
                    return False, "Incompatibilidad de Columna: Target es Lumbar pero candidato es Cervical"
                if 'dorsal' in t_reg['columna'] and 'cervical' in o_reg['columna'] and 'dorsal' not in o_reg['columna']:
                    return False, "Incompatibilidad de Columna: Target es Dorsal pero candidato es Cervical"

        # 2. Cruce incompatible entre Extremidad Superior e Inferior (EESS vs. EEII)
        if t_reg['eess'] and o_reg['eeii'] and not t_reg['eeii']:
            return False, f"Cruce incompatible EESS vs EEII: Target es extremidad superior ({list(t_reg['eess'])}) y candidato es inferior ({list(o_reg['eeii'])})"
        if t_reg['eeii'] and o_reg['eess'] and not t_reg['eess']:
            return False, f"Cruce incompatible EEII vs EESS: Target es extremidad inferior ({list(t_reg['eeii'])}) y candidato es superior ({list(o_reg['eess'])})"

        # 3. Conflicto entre Segmentos de Extremidad Superior (EESS)
        # Si target especifica un segmento único (ej. hombro) y candidato es otro (ej. codo)
        if len(t_reg['eess']) == 1 and len(o_reg['eess']) == 1:
            t_seg = next(iter(t_reg['eess']))
            o_seg = next(iter(o_reg['eess']))
            # Reglas estrictas de exclusión
            if {t_seg, o_seg} in [{'hombro', 'codo'}, {'hombro', 'muneca'}, {'hombro', 'mano'}, {'codo', 'muneca'}, {'codo', 'mano'}]:
                return False, f"Incompatibilidad anatómica EESS: Target pide {t_seg.upper()} pero candidato es {o_seg.upper()}"

        # 4. Conflicto entre Segmentos de Extremidad Inferior (EEII)
        if len(t_reg['eeii']) == 1 and len(o_reg['eeii']) == 1:
            t_seg = next(iter(t_reg['eeii']))
            o_seg = next(iter(o_reg['eeii']))
            # Reglas estrictas de exclusión
            if {t_seg, o_seg} in [{'cadera', 'rodilla'}, {'cadera', 'tobillo'}, {'cadera', 'pie'}, {'rodilla', 'tobillo'}, {'rodilla', 'pie'}]:
                return False, f"Incompatibilidad anatómica EEII: Target pide {t_seg.upper()} pero candidato es {o_seg.upper()}"

        # 5. Conflicto Abdomen puro vs. Pelvis pura
        # Si uno es exclusivamente Abdomen y el otro es exclusivamente Pelvis
        if t_reg['abdomen'] and not t_reg['pelvis'] and o_reg['pelvis'] and not o_reg['abdomen']:
            return False, "Conflicto anatómico: Target es exclusivamente Abdomen pero candidato es exclusivamente Pelvis"
        if t_reg['pelvis'] and not t_reg['abdomen'] and o_reg['abdomen'] and not o_reg['pelvis']:
            return False, "Conflicto anatómico: Target es exclusivamente Pelvis pero candidato es exclusivamente Abdomen"

        # Si Target exige Abdomen Y Pelvis, pero el candidato solo cubre uno de ellos de forma parcial
        if t_reg['abdomen'] and t_reg['pelvis']:
            if o_reg['pelvis'] and not o_reg['abdomen']:
                return False, "Conflicto anatómico: Target exige Abdomen Y Pelvis pero candidato solo cubre Pelvis"
            if o_reg['abdomen'] and not o_reg['pelvis']:
                return False, "Conflicto anatómico: Target exige Abdomen Y Pelvis pero candidato solo cubre Abdomen"

        # 6. Conflicto Tórax vs. Cabeza/Cuello / Abdomen / Pelvis / EEII
        if t_reg['torax'] and not t_reg['cabeza_cuello'] and not t_reg['abdomen']:
            if o_reg['cabeza_cuello'] and not o_reg['torax']:
                return False, "Conflicto anatómico: Target es Tórax pero candidato es Cabeza/Cuello"
            if o_reg['pelvis'] and not o_reg['torax']:
                return False, "Conflicto anatómico: Target es Tórax pero candidato es Pelvis"
            if o_reg['eeii'] and not o_reg['torax']:
                return False, "Conflicto anatómico: Target es Tórax pero candidato es Extremidad Inferior"

        # 7. Cabeza / Cuello vs. Tronco / Extremidades (Simétrico)
        if t_reg['cabeza_cuello'] and not o_reg['cabeza_cuello']:
            if o_reg['torax'] or o_reg['abdomen'] or o_reg['pelvis'] or o_reg['eess'] or o_reg['eeii']:
                return False, "Conflicto anatómico: Target es Cabeza/Cuello pero candidato es de Tronco o Extremidades"
        if o_reg['cabeza_cuello'] and not t_reg['cabeza_cuello']:
            if t_reg['torax'] or t_reg['abdomen'] or t_reg['pelvis'] or t_reg['eess'] or t_reg['eeii']:
                return False, "Conflicto anatómico: Candidato es Cabeza/Cuello pero target es de Tronco o Extremidades"

        return True, "Región anatómica compatible"

    # =========================================================================
    # 6. AUDITORÍA ASISTIDA POR IA (Nivel 2 - Para casos límite)
    # =========================================================================
    def auditar_con_llm(self, target: str, ocr: str, id_registro: int = 0) -> Tuple[bool, str, float]:
        """
        Consulta a los modelos LLM auditores de alta capacidad para verificar
        casos semánticos complejos o ambiguos que pasaron el Nivel 1 determinista.
        """
        if not OPENROUTER_API_KEY:
            logger.warning("No hay API KEY para auditoría LLM. Aprobando por reglas Nivel 1.")
            return True, "Nivel 1 aprobado (sin API KEY para Nivel 2)", 1.0

        import requests

        prompt = f"""
Eres un Auditor Médico Radiólogo Senior de alta precisión clínica.
Tu misión es AUDITAR si el estudio de imagen ENCONTRADO en el PACS corresponde 
exactamente a la misma orden médica del estudio BUSCADO.

BUSCADO: "{target}"
ENCONTRADO (Línea OCR): "{ocr}"

CRITERIOS ESTRICTOS DE RECHAZO (RECHAZAR = false):
- Si la lateralidad no coincide exactamente (Derecho ≠ Izquierdo, Bilateral ≠ Unilateral).
- Si la modalidad no coincide (Radiografía ≠ TAC ≠ RM ≠ Ecografía).
- Si la técnica no coincide (Doppler vascular ≠ Partes blandas/Articular; Angio ≠ Simple).
- Si la región anatómica difiere (Columna Lumbar ≠ Cervical; Codo ≠ Rodilla; etc.).

RESPONDE EXCLUSIVAMENTE EN JSON:
{{
  "aprobado": true o false,
  "justificacion": "Motivo clínico conciso (máx 100 caracteres)",
  "confianza": 0.0 a 1.0
}}
"""
        modelos_auditor = self.obtener_modelos_auditor()
        for modelo in modelos_auditor:
            try:
                base_url, target_key, _ = get_llm_request_params(modelo) if HAS_LLM_CONFIG else ("https://openrouter.ai/api/v1", OPENROUTER_API_KEY, "openrouter")
                if not target_key:
                    target_key = OPENROUTER_API_KEY

                resp = requests.post(
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {target_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://rpa-framework.local",
                    },
                    json={
                        "model": modelo,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.0,
                        "max_tokens": 500,
                    },
                    timeout=(3.0, 10.0),
                )

                if resp.status_code == 200:
                    data = resp.json()
                    content = (data.get("choices", [{}])[0].get("message") or {}).get("content", "")
                    match = re.search(r"\{.*?\}", content, re.DOTALL)
                    if match:
                        res = json.loads(match.group(0))
                        aprobado = res.get("aprobado", False)
                        justificacion = res.get("justificacion", "")
                        confianza = float(res.get("confianza", 0.0))
                        logger.info(f"🧠 [Auditor IA] {modelo} → aprobado={aprobado} conf={confianza:.2f} | {justificacion}")
                        return aprobado, f"[Auditor IA: {modelo}] {justificacion}", confianza
            except Exception as e:
                logger.warning(f"Auditor IA {modelo} falló o timeout: {e}")
                continue

        # Si fallan los LLMs de auditoría, se confía en las reglas deterministas de Nivel 1
        return True, "Aprobado por Reglas Deterministas (Auditor LLM no disponible)", 0.85

    # =========================================================================
    # 7. MÉTODO PRINCIPAL DE AUDITORÍA
    # =========================================================================
    def auditar(
        self,
        target_diag: str,
        ocr_candidato: str,
        metodo: str = "fuzzy_local",
        score: float = 0.0,
        requiere_llm: bool = False,
        id_registro: int = 0
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Punto central de auditoría clínica antes de realizar un clic.
        
        Parámetros:
        - target_diag: Diagnóstico objetivo buscado (desde BBDD / orden médica).
        - ocr_candidato: Texto OCR extraído de la fila candidata en pantalla.
        - metodo: 'sinonimo_bd', 'fuzzy_local', o 'llm'.
        - score: Puntuación de similitud o confianza obtenida.
        - requiere_llm: Si es True, ejecuta también la validación LLM de Nivel 2.
        
        Retorna:
        (es_aprobado: bool, razon: str, detalles: dict)
        """
        detalles = {
            'target': target_diag,
            'ocr': ocr_candidato,
            'metodo': metodo,
            'score': score,
            'reglas_n1': {}
        }

        logger.info(f"🛡️ [AUDITOR] Iniciando auditoría pre-clic | Método: {metodo} | Target: '{target_diag}' | Candidato: '{ocr_candidato[:60]}'")

        # ── 1. Nivel 1: Lateralidad ──────────────────────────────────────────
        ok_lat, razon_lat = self.auditar_lateralidad(target_diag, ocr_candidato)
        detalles['reglas_n1']['lateralidad'] = {'ok': ok_lat, 'razon': razon_lat}
        if not ok_lat:
            logger.warning(f"🚫 [AUDITOR RECHAZA] Lateralidad: {razon_lat}")
            return False, f"Rechazado por Auditor Clínico (Lateralidad): {razon_lat}", detalles

        # ── 2. Nivel 1: Modalidad ────────────────────────────────────────────
        ok_mod, razon_mod = self.auditar_modalidad(target_diag, ocr_candidato)
        detalles['reglas_n1']['modalidad'] = {'ok': ok_mod, 'razon': razon_mod}
        if not ok_mod:
            logger.warning(f"🚫 [AUDITOR RECHAZA] Modalidad: {razon_mod}")
            return False, f"Rechazado por Auditor Clínico (Modalidad): {razon_mod}", detalles

        # ── 3. Nivel 1: Sub-modalidad y Técnica ──────────────────────────────
        ok_sub, razon_sub = self.auditar_submodalidad(target_diag, ocr_candidato)
        detalles['reglas_n1']['submodalidad'] = {'ok': ok_sub, 'razon': razon_sub}
        if not ok_sub:
            logger.warning(f"🚫 [AUDITOR RECHAZA] Sub-modalidad: {razon_sub}")
            return False, f"Rechazado por Auditor Clínico (Técnica/Sub-modalidad): {razon_sub}", detalles

        # ── 4. Nivel 1: Región Anatómica ─────────────────────────────────────
        ok_anat, razon_anat = self.auditar_anatomia(target_diag, ocr_candidato)
        detalles['reglas_n1']['anatomia'] = {'ok': ok_anat, 'razon': razon_anat}
        if not ok_anat:
            logger.warning(f"🚫 [AUDITOR RECHAZA] Anatomía: {razon_anat}")
            return False, f"Rechazado por Auditor Clínico (Anatomía): {razon_anat}", detalles

        # ── 5. Nivel 2: Asistido por IA (Opcional o para casos LLM / dudosos) ─
        if requiere_llm:
            ok_llm, razon_llm, conf_llm = self.auditar_con_llm(target_diag, ocr_candidato, id_registro=id_registro)
            detalles['auditor_ia'] = {'ok': ok_llm, 'razon': razon_llm, 'confianza': conf_llm}
            if not ok_llm:
                logger.warning(f"🚫 [AUDITOR RECHAZA] IA Nivel 2: {razon_llm}")
                return False, f"Rechazado por Auditor Clínico (IA Nivel 2): {razon_llm}", detalles

        logger.info(f"✅ [AUDITOR APRUEBA] Coincidencia validada clínicamente para clic (Método: {metodo})")
        return True, "Aprobado por Auditor Clínico", detalles
