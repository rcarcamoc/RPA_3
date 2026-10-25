# -*- coding: utf-8 -*-
"""
candidates_and_diagnostics_mixin.py — Análisis y filtrado de candidatos OCR en tabla PACS,
diagnóstico de causa raíz ante fallos y comparativa Tesseract vs PaddleOCR.
Extraído de busqueda_triple_text_only.py.
"""

import re
import logging
from rapidfuzz import fuzz

logger = logging.getLogger(__name__)


class TripleSearchCandidatesMixin:
    """Mixin para filtrado de filas candidatas y diagnóstico de fallos en BusquedaTextOnly."""

    def _analyze_candidates(self, ocr_results, target_fecha_str):
        """Analiza resultados OCR y devuelve candidatos.

        REGLA ESTRICTA (inamovible por confiabilidad clínica): en la MISMA
        fila deben aparecer TODOS:
          1. La fecha agendada del examen
          2. El estado 'Examen Hecho' o 'Realizado'
        Sin esta coincidencia simultánea no se genera ningún candidato.
        """
        rows_data = self.agrupar_por_filas(ocr_results)
        candidates = []

        rows_sorted = sorted(rows_data, key=lambda r: r['y_center'])
        for row in rows_sorted:
            row_items  = sorted(row['items'], key=lambda x: x['center']['x'])
            row['full_text'] = " ".join([i['text'] for i in row_items])

        for row in rows_sorted:
            row_text   = row['full_text']
            row_norm   = self.normalize_text(row_text)

            # ── CHECK 0: FILTRO DE ENCABEZADOS Y METADATOS DE TABLA PACS ───────
            header_max_y = getattr(self, 'HEADER_MAX_Y', 42)
            if row['y_center'] < header_max_y:
                logger.info(f"🚫 Fila descartada por zona de encabezado PACS (Y={int(row['y_center'])} < {header_max_y}): {row_text[:80]}")
                continue

            PATRONES_ENCABEZADO = [
                r'\bfecha\s+agendada\b',
                r'\bfacha\s+ager\b',
                r'\bnro\.?\s*pacs\b',
                r'\bexamen\s*:\s*(?:fecha|facha|dada|stado|estado)',
                r'\bcexamen\b',
                r'\bprioridad\b',
                r'\bmodalidad\b',
            ]
            es_encabezado = False
            for pat in PATRONES_ENCABEZADO:
                if re.search(pat, row_norm):
                    logger.info(f"🚫 Fila descartada por contener encabezado PACS '{pat}' (Y={int(row['y_center'])}): {row_text[:80]}")
                    es_encabezado = True
                    break
            if es_encabezado:
                continue

            if len(row_norm.split()) <= 2 and not any(w in row_norm for w in ['hecho', 'realizado']):
                logger.info(f"🚫 Fila descartada por ser fragmento espurio (Y={int(row['y_center'])}): {row_text[:80]}")
                continue

            # ── CHECK 1: LISTA NEGRA DE ESTADOS (Anti-Falsos Positivos) ────────
            ESTADOS_EXCLUIDOS = [
                'cancelado', 'cancelada', 'anulado', 'anulada',
                'agendado', 'agendada', 'citado', 'citada',
                'ordenado', 'ordenada', 'en espera', 'solicitado', 'solicitada',
                'aprobado', 'aprobada', 'preliminar', 'informado', 'informada'
            ]
            es_excluido = False
            for est in ESTADOS_EXCLUIDOS:
                if re.search(r'\b' + re.escape(est) + r'\b', row_norm):
                    logger.info(f"🚫 Fila descartada por estado excluido '{est.upper()}' (Y={int(row['y_center'])}): {row_text[:80]}")
                    es_excluido = True
                    break
            if es_excluido:
                continue

            # ── CHECK 2: FECHA (Blindado con Auditor Clínico) ────────────────
            if self.auditor:
                has_date, motivo_fecha, score_fecha = self.auditor.auditar_fecha(target_fecha_str, row_text)
            else:
                target_fecha_short = target_fecha_str[:-4] + target_fecha_str[-2:] if len(target_fecha_str) == 10 else ""
                has_date = (target_fecha_str in row_text) or (target_fecha_short in row_text)
                score_fecha = 100 if has_date else 0
                motivo_fecha = "Fallback exacto sin auditor"

            # ── CHECK 3: ESTADO TÉCNICO (Examen Hecho / Realizado / Variantes OCR) ───
            score_examen_hecho = fuzz.partial_ratio("examen hecho", row_norm)
            row_words          = row_norm.split()
            score_hecho        = max((fuzz.ratio("hecho", w) for w in row_words if len(w) >= 4), default=0)
            score_realizado    = max((fuzz.ratio("realizado", w) for w in row_words if len(w) >= 6), default=0)

            REGEX_HECHO_VARIANTES = re.compile(
                r'\b(?:examen\s*he[cd]h?o|realizad[ao]|he[cd]h?o|e[a-z]*m[a-z]*t[ao]t[ao]|ex[a-z]*t[ao]t[ao])\b',
                re.IGNORECASE
            )
            has_variante_regex = bool(REGEX_HECHO_VARIANTES.search(row_norm))

            tiene_raiz_hecho = (
                score_hecho >= 80 or
                score_realizado >= 80 or
                has_variante_regex
            )

            has_estado = (
                ((score_examen_hecho >= 80 and tiene_raiz_hecho) or
                (score_hecho >= 85) or
                (score_realizado >= 85) or
                has_variante_regex)
            )

            logger.debug(
                f"Fila Y={int(row['y_center'])}: ex_hecho={score_examen_hecho} hecho={score_hecho} "
                f"variante={has_variante_regex} fecha={has_date} ({motivo_fecha}) | {row_text[:80]}"
            )

            if has_estado:
                if not has_date or score_fecha == 0:
                    logger.info(
                        f"🚫 Fila con 'Examen Hecho' descartada por fecha incompatible "
                        f"(Y={int(row['y_center'])} | score_fecha={score_fecha} | {motivo_fecha}): {row_text[:80]}"
                    )
                    continue

                all_y_min = [i['bounds']['y_min'] for i in row['items'] if 'bounds' in i]
                all_y_max = [i['bounds']['y_max'] for i in row['items'] if 'bounds' in i]
                row['y_min'] = min(all_y_min) if all_y_min else (row['y_center'] - self.CROP_HEIGHT // 2)
                row['y_max'] = max(all_y_max) if all_y_max else (row['y_center'] + self.CROP_HEIGHT // 2)
                row['y_click'] = row['y_center']
                row['score_fecha'] = score_fecha
                row['has_date'] = has_date
                row['motivo_fecha'] = motivo_fecha
                row['es_fallback_fecha'] = ("fallback" in motivo_fecha.lower())
                row['score_estado'] = max(score_examen_hecho, score_hecho, 100 if has_variante_regex else 0)
                candidates.append(row)
                logger.info(
                    f"✅ Candidato con Examen Hecho (Y_center={int(row['y_center'])} | y_min={int(row['y_min'])} "
                    f"y_max={int(row['y_max'])} y_click={int(row['y_click'])}, "
                    f"score_fecha={score_fecha} ({motivo_fecha}) ex_hecho={score_examen_hecho} hecho={score_hecho} "
                    f"variante={has_variante_regex}): {row_text[:120]}"
                )

        candidates = sorted(candidates, key=lambda c: (c.get('score_fecha', 0), c.get('score_estado', 0)), reverse=True)
        return candidates, rows_data

    def diagnosticar_falla(self, rows_data, candidates, target_fecha_str, target_diag, ocr_results=None, motivos_descarte=None):
        """
        Analiza detalladamente por qué falló la búsqueda para entregar un diagnóstico
        preciso y comprensible al usuario en lugar de un error genérico.
        """
        total_palabras = len(ocr_results) if ocr_results else sum(len(r.get('items', [])) for r in rows_data)
        if not candidates and total_palabras < 5:
            return f"Pantalla en blanco o visor PACS no cargó (solo {total_palabras} palabras detectadas en pantalla)"

        # Combinar filas de PaddleOCR y Tesseract para no perder filas resaltadas en azul en PACS
        all_rows_sources = list(rows_data or [])
        for extra_attr in ('last_paddle_rows_data', 'last_tesseract_rows_data'):
            extra_rows = getattr(self, extra_attr, None)
            if extra_rows:
                all_rows_sources.extend(extra_rows)

        seen_texts = set()
        combined_rows = []
        for r in all_rows_sources:
            txt = (r.get('full_text') or '').strip()
            if not txt and r.get('items'):
                row_items = sorted(r['items'], key=lambda x: x['center']['x'])
                txt = " ".join([i['text'] for i in row_items]).strip()
                r['full_text'] = txt
            if txt and txt not in seen_texts:
                seen_texts.add(txt)
                combined_rows.append(r)

        regex_fechas = re.compile(r'\b(\d{2}[-/]\d{2}[-/]\d{4})\b')
        fechas_detectadas = set()
        for r in combined_rows:
            txt = r.get('full_text', '')
            for m in regex_fechas.findall(txt):
                fechas_detectadas.add(m.replace('/', '-'))

        # 1. Si hubo candidatos con (Fecha + Examen Hecho) pero ninguno coincidió con target_diag
        if candidates:
            if motivos_descarte:
                return f"Discrepancia en examen ({motivos_descarte[0]})"
            
            examenes_pacs = []
            for c in candidates:
                frag = self.extraer_fragmento_estudio(c.get('full_text', ''))
                if frag and len(frag) > 3:
                    examenes_pacs.append(frag)
                else:
                    examenes_pacs.append(c.get('full_text', '')[:50])
            
            examenes_str = " | ".join(list(dict.fromkeys(examenes_pacs))[:3])
            return (
                f"Examen no coincide: Fecha '{target_fecha_str}' y 'Examen Hecho' confirmados, "
                f"pero el estudio en PACS es diferente (Buscado: '{target_diag}' | En PACS: '{examenes_str}')"
            )

        # 2. Si NO hubo candidatos: Analizar si fue por FECHA, ESTADO HECHO o si ya está APROBADO (Ya Validado)
        filas_con_fecha = []
        filas_ya_validadas = []
        estados_excluidos_encontrados = []
        ESTADOS_KEYWORDS = [
            'cancelado', 'cancelada', 'anulado', 'anulada',
            'agendado', 'agendada', 'citado', 'citada',
            'ordenado', 'ordenada', 'en espera', 'solicitado', 'solicitada',
            'aprobado', 'aprobada', 'preliminar', 'informado', 'informada'
        ]

        header_max_y = getattr(self, 'HEADER_MAX_Y', 42)
        for r in combined_rows:
            if r.get('y_center', 200) < header_max_y:
                continue
            r_text = r.get('full_text', '')
            r_norm = self.normalize_text(r_text)
            
            has_date = False
            score_fecha = 0
            if self.auditor:
                has_date, _, score_fecha = self.auditor.auditar_fecha(target_fecha_str, r_text)
            else:
                target_fecha_short = target_fecha_str[:-4] + target_fecha_str[-2:] if len(target_fecha_str) == 10 else ""
                has_date = (target_fecha_str in r_text) or (target_fecha_short in r_text)
                score_fecha = 100 if has_date else 0
            
            estados_fila = []
            for est in ESTADOS_KEYWORDS:
                if re.search(r'\b' + re.escape(est) + r'\b', r_norm):
                    estados_fila.append(est.upper())
            
            if has_date and score_fecha >= 80:
                filas_con_fecha.append({
                    'text': r_text,
                    'estados': estados_fila
                })
                # REGLA EXCLUYENTE PARA 'YA VALIDADO':
                # Dado que todos los reportes históricos quedan en 'Aprobado' por defecto,
                # SOLO se clasifica como 'Ya Validado' si en la MISMA FILA aparecen simultáneamente:
                #   1. Estado 'Aprobado' / 'Aprobada' (sin estados pendientes/agendados/ordenados)
                #   2. La Fecha Agendada exacta del registro (has_date=True y score_fecha >= 80)
                #   3. El Diagnóstico/Examen registrado (validado por normalización médica + Auditor Clínico)
                tiene_aprobado = any(est in ('APROBADO', 'APROBADA') for est in estados_fila)
                tiene_otro_estado = any(
                    est in ('AGENDADO', 'AGENDADA', 'ORDENADO', 'ORDENADA', 'CANCELADO', 'CANCELADA', 'ANULADO', 'ANULADA')
                    for est in estados_fila
                )
                if tiene_aprobado and not tiene_otro_estado and target_diag:
                    frag_estudio = self.extraer_fragmento_estudio(r_text)
                    frag_estudio_clean = re.sub(r'\b(?:aprobado[as]?|normal|urgente)\b', '', frag_estudio, flags=re.IGNORECASE).strip()
                    if len(frag_estudio_clean) >= 4 and frag_estudio_clean.strip() != r_text.strip():
                        target_med = self.normalizar_terminologia_medica(target_diag)
                        frag_med = self.normalizar_terminologia_medica(frag_estudio_clean)
                        score_diag = max(
                            fuzz.ratio(target_med, frag_med),
                            fuzz.token_set_ratio(target_med, frag_med)
                        ) if (target_med and frag_med) else 0

                        if score_diag < 75 and hasattr(self, 'buscar_sinonimo'):
                            sin_bd = self.buscar_sinonimo(target_diag, frag_estudio_clean)
                            if sin_bd:
                                sin_med = self.normalizar_terminologia_medica(sin_bd)
                                score_diag = max(
                                    score_diag,
                                    fuzz.ratio(sin_med, frag_med),
                                    fuzz.token_set_ratio(sin_med, frag_med)
                                )

                        if score_diag >= 75:
                            auditor_ok = True
                            if self.auditor:
                                auditor_ok, _, _ = self.auditor.auditar(
                                    target_diag=target_diag,
                                    ocr_candidato=r_text,
                                    metodo="ya_validado_check",
                                    score=score_diag,
                                    requiere_llm=False
                                )
                            elif hasattr(self, 'verificar_lateralidad'):
                                auditor_ok = self.verificar_lateralidad(target_diag, r_text)

                            if auditor_ok:
                                filas_ya_validadas.append(r_text)
            
            estados_excluidos_encontrados.extend(estados_fila)

        if filas_ya_validadas:
            fila_ej = filas_ya_validadas[0][:100]
            return (
                f"Ya Validado: El examen '{target_diag}' con fecha agendada '{target_fecha_str}' "
                f"ya figura en estado 'Aprobado' en PACS (Fila detectada: '{fila_ej}')"
            )

        if filas_con_fecha:
            estados_fecha = []
            for f in filas_con_fecha:
                estados_fecha.extend(f['estados'])
            estados_str = ", ".join(sorted(set(estados_fecha))) if estados_fecha else "No indica 'Examen Hecho'"
            return (
                f"Texto 'Examen Hecho' no encontrado: La fecha '{target_fecha_str}' existe en PACS, "
                f"pero los estudios figuran en estado '{estados_str}'"
            )

        fechas_vistas_str = ", ".join(sorted(fechas_detectadas)) if fechas_detectadas else "ninguna detectada"
        if estados_excluidos_encontrados:
            estados_globales = ", ".join(sorted(set(estados_excluidos_encontrados))[:4])
            return (
                f"Fecha no encontrada: Se buscaba '{target_fecha_str}', pero no figura en pantalla "
                f"(Fechas detectadas: {fechas_vistas_str} | Estados visibles: {estados_globales})"
            )
        else:
            return (
                f"Fecha no encontrada: Se buscaba '{target_fecha_str}', pero no figura en pantalla "
                f"(Fechas detectadas: {fechas_vistas_str})"
            )

    def get_ocr_comparison_info(self, target_fecha_str="", target_diag=""):
        """
        Genera un resumen comparativo de las detecciones de Tesseract y PaddleOCR
        para ser enviado en la alerta de Telegram ante fallos de búsqueda.
        """
        def format_rows(rows_data):
            if not rows_data:
                return []
            formatted = []
            for r in rows_data:
                items = sorted(r.get('items', []), key=lambda x: x.get('center', {}).get('x', 0))
                txt = " ".join([it.get('text', '') for it in items if it.get('text', '').strip()])
                y = int(r.get('y_center', 0))
                if txt.strip():
                    formatted.append(f"Y={y}: {txt}")
            keywords = ["hecho", "realizado", "aprobado", "cancelado", "agendado"]
            if target_fecha_str:
                d_p = target_fecha_str.split("-")
                if len(d_p) == 3:
                    keywords.extend([f"{d_p[0]}-{d_p[1]}", f"{d_p[1]}/{d_p[0]}", f"{d_p[0]}/{d_p[1]}", d_p[0], d_p[2]])
            if target_diag:
                words = [w.lower() for w in target_diag.split() if len(w) > 3]
                keywords.extend(words)

            relevantes = [r for r in formatted if any(k.lower() in r.lower() for k in keywords)]
            otros = [r for r in formatted if r not in relevantes]
            res = (relevantes + otros)[:5]
            return [r[:120] for r in res]

        paddle_list = format_rows(getattr(self, 'last_paddle_rows_data', []))
        if not paddle_list and getattr(self, 'last_img_bgr', None) is not None:
            try:
                ocr_results_paddle = self.execute_paddle_ocr(self.last_img_bgr)
                _, rows_data_paddle = self._analyze_candidates(ocr_results_paddle, target_fecha_str)
                self.last_paddle_results = ocr_results_paddle
                self.last_paddle_rows_data = rows_data_paddle
                paddle_list = format_rows(rows_data_paddle)
            except Exception as e:
                paddle_list = [f"Error ejecutando PaddleOCR: {e}"]

        tess_list = format_rows(getattr(self, 'last_tesseract_rows_data', []))
        if not tess_list and getattr(self, 'last_img_bgr', None) is not None:
            try:
                ocr_results_tess = self.execute_ocr_data(self.last_img_bgr, use_preprocessing=True)
                _, rows_data_tess = self._analyze_candidates(ocr_results_tess, target_fecha_str)
                self.last_tesseract_results = ocr_results_tess
                self.last_tesseract_rows_data = rows_data_tess
                tess_list = format_rows(rows_data_tess)
            except Exception as e:
                tess_list = [f"Error ejecutando Tesseract: {e}"]

        return {
            "tesseract": tess_list if tess_list else ["Sin filas detectadas por Tesseract"],
            "paddle": paddle_list if paddle_list else ["Sin filas detectadas por PaddleOCR"]
        }
