#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script: preparar_examen_v2.py
Descripción: Nodo orquestador de inicio para Sub_work_v2.
             1. Comprueba si ya existe un examen en estado 'Listo_PACS' (precargado en segundo plano).
             2. Si existe, lo activa pasando a 'En Proceso' y el flujo pasa directo a PACS (0s en RIS).
             3. Si NO existe (por ejemplo, primera iteración), ejecuta la extracción de RIS de forma síncrona.
"""

import os
import sys
import time
import subprocess
import logging
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [ORQUESTADOR_V2] - %(message)s')
logger = logging.getLogger(__name__)

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'ris'
}

def obtener_conexion():
    if not HAS_MYSQL:
        return None
    return mysql.connector.connect(**DB_CONFIG)

def tomar_examen_precargado():
    """Busca un examen en estado 'Listo_PACS' y lo pasa a 'En Proceso'."""
    conn = obtener_conexion()
    if not conn:
        return None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT id, user, pass, numero_documento, diagnostico, patologia_critica FROM registro_acciones WHERE estado = 'Listo_PACS' ORDER BY id ASC LIMIT 1")
        row = cursor.fetchone()
        if row:
            target_id = row['id']
            cursor.execute("UPDATE registro_acciones SET estado = 'En Proceso', ultimo_nodo = 'Orquestador_Listo_PACS', `update` = NOW() WHERE id = %s", (target_id,))
            conn.commit()
            conn.close()
            return row
        conn.close()
        return None
    except Exception as e:
        logger.error(f"Error consultando 'Listo_PACS': {e}")
        return None

def ejecutar_extraccion_ris_sincrona():
    """Ejecuta los pasos de RIS para el primer examen cuando no hay ninguno en cola."""
    logger.info("⏳ No hay exámenes precargados en cola. Ejecutando extracción inicial de RIS...")
    base_dir = Path(__file__).parent.parent / "web"
    
    # 1. Crear registro
    try:
        from recordings.sistema.crear_registro_db_v2 import crear_registro
    except ImportError:
        from rpa_framework.recordings.sistema.crear_registro_db_v2 import crear_registro
        
    target_id = crear_registro(estado_inicial='En Proceso')
    env = os.environ.copy()
    env["VAR_TARGET_ID"] = str(target_id)

    pasos = [
        "Inicio_ris_v2.py",
        "seleccion_int_2_v2.py",
        "busca_doctor_ultima_v2.py",
        "procesar_pdf_doctor_v2.py",
        "detecta_patologia_ia_v2_opt.py"
    ]

    for script in pasos:
        script_path = base_dir / script
        logger.info(f"Ejecutando: {script}...")
        res = subprocess.run([sys.executable, str(script_path), str(target_id)], env=env)
        if res.returncode != 0:
            logger.error(f"Error en paso sincrónico {script}")
            return False

    logger.info("✓ Extracción sincrónica de RIS finalizada exitosamente.")
    return True

def main():
    examen_listo = tomar_examen_precargado()
    if examen_listo:
        logger.info(f"⚡ ¡ÉXITO! Examen ID {examen_listo['id']} (Doc: {examen_listo['numero_documento']}) ya estaba PRECARGADO.")
        logger.info("⚡ Saltando fase de RIS completa. Procediendo DIRECTO a PACS (0 segundos de espera).")
        sys.exit(0)
    else:
        if ejecutar_extraccion_ris_sincrona():
            sys.exit(0)
        else:
            sys.exit(1)

if __name__ == "__main__":
    main()
