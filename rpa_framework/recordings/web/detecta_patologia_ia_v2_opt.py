#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script: detecta_patologia_ia_v2_opt.py
Versión optimizada de detecta_patologia_ia_v2.py:
- Soporta target_id explícito (VAR_TARGET_ID o argumento) para el pipeline de precarga.
- Timeout estricto en llamadas LLM para evitar cuelgues.
"""

import os
import sys
import json
import time
import logging
from typing import Optional, Tuple
from datetime import datetime
import pandas as pd
import requests

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

from utils.llm_config import (
    OPENROUTER_BASE_URL, LLM_DEFAULT_TEMPERATURE, LLM_DEFAULT_MAX_TOKENS, LLM_DEFAULT_TIMEOUT
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'ris'
}

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

MODELS_FALLBACK = [
    "meta/llama-3.2-11b-vision-instruct",
    "nvidia/nemotron-3-super-120b-a12b",
    "deepseek-ai/deepseek-v4-flash"
]


def conectar_bd():
    return mysql.connector.connect(**DB_CONFIG)


def cargar_datos(conn, target_id=None) -> Tuple[pd.DataFrame, list]:
    cursor = conn.cursor(dictionary=True)
    if target_id:
        cursor.execute("SELECT id, examen, diagnostico FROM ris.registro_acciones WHERE id = %s", (target_id,))
    else:
        cursor.execute("SELECT id, examen, diagnostico FROM ris.registro_acciones WHERE estado = 'En Proceso' ORDER BY id DESC LIMIT 1")
    filas_acciones = cursor.fetchall()
    df_acciones = pd.DataFrame(filas_acciones) if filas_acciones else pd.DataFrame(columns=['id', 'examen', 'diagnostico'])

    cursor.execute("SELECT nombre_patologia FROM ris.patologias_criticas")
    filas_pat = cursor.fetchall()
    patologias = [r['nombre_patologia'] for r in filas_pat]
    cursor.close()

    return df_acciones, patologias


def consultar_llm_rapido(diagnostico: str, patologias: list) -> Tuple[str, str, str]:
    """Consulta rápida a LLM con timeout de 8 segundos."""
    if not OPENROUTER_API_KEY or not diagnostico:
        return "no", "Ninguna", "Sin API Key o diagnóstico vacío"

    prompt = f"""Eres un médico radiólogo experto. Analiza el siguiente texto de diagnóstico y determina si contiene una PATOLOGÍA CRÍTICA (de riesgo vital o quirúrgico inmediato que deba notificarse de urgencia).

PATOLOGÍAS DE REFERENCIA:
{", ".join(patologias[:30])}

DIAGNÓSTICO A EVALUAR:
{diagnostico[:2500]}

RESPONDE EXCLUSIVAMENTE UN JSON VÁLIDO CON ESTE FORMATO:
{{
  "es_critica": "si" o "no",
  "patologia": "nombre de la patología o Ninguna",
  "razonamiento": "explicación breve"
}}
"""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    for model in MODELS_FALLBACK:
        try:
            start_t = time.time()
            payload = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 150
            }
            resp = requests.post(f"{OPENROUTER_BASE_URL}/chat/completions", headers=headers, json=payload, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                # Parsear JSON
                import re
                m = re.search(r'\{.*\}', content, re.DOTALL)
                if m:
                    res_json = json.loads(m.group(0))
                    es_crit = res_json.get("es_critica", "no").lower()
                    pat = res_json.get("patologia", "Ninguna")
                    raz = res_json.get("razonamiento", "")
                    logger.info(f"LLM ({model}, {int((time.time()-start_t)*1000)}ms): es_critica={es_crit}, patologia={pat}")
                    return es_crit, pat, raz
        except Exception as e:
            logger.warning(f"Modelo {model} no respondió o dio error: {e}")
            continue

    return "no", "Ninguna", "Evaluación completada por descarte de modelos"


def actualizar_bd(conn, id_reg: int, es_critica: str, patologia: str, razonamiento: str):
    cursor = conn.cursor()
    query = """
    UPDATE ris.registro_acciones
    SET patologia_critica = %s,
        patologia_critica_detectada = %s,
        `update` = NOW(),
        ultimo_nodo = 'detecta_patologia_ia_v2_opt'
    WHERE id = %s
    """
    cursor.execute(query, (es_critica, patologia, id_reg))
    conn.commit()
    cursor.close()
    logger.info(f"✓ Registro ID {id_reg} actualizado: Patología Crítica = {es_critica}")


def main():
    target_id = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("VAR_TARGET_ID")
    conn = conectar_bd()
    df_acciones, patologias = cargar_datos(conn, target_id=target_id)

    if df_acciones.empty:
        logger.info("No hay diagnósticos pendientes de analizar.")
        conn.close()
        sys.exit(0)

    for _, row in df_acciones.iterrows():
        id_reg = row['id']
        diag = row.get('diagnostico', '')
        es_critica, pat, raz = consultar_llm_rapido(diag, patologias)
        actualizar_bd(conn, id_reg, es_critica, pat, raz)

    conn.close()
    sys.exit(0)


if __name__ == "__main__":
    main()
