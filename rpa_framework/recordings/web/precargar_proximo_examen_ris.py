#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script: precargar_proximo_examen_ris.py
Descripción: Ejecutor en segundo plano del flujo RIS para el PRÓXIMO examen.
             Se dispara durante la fase de PACS (búsqueda triple / pegado) para que,
             cuando PACS termine, el siguiente examen ya esté 100% parseado y diagnosticado
             con estado 'Listo_PACS' en MySQL.

No interactúa con ventanas del escritorio, no maximiza Chrome y no roba el foco.
"""

import os
import sys
import time
import logging
import subprocess
from pathlib import Path

# Configurar path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [PRECARGA_RIS] - %(message)s')
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

def hay_examen_en_cola():
    """Verifica si ya existe un examen listo o en preparación."""
    conn = obtener_conexion()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM registro_acciones WHERE estado IN ('Listo_PACS', 'Preparando_RIS')")
        cuenta = cursor.fetchone()[0]
        conn.close()
        return cuenta > 0
    except Exception as e:
        logger.error(f"Error verificando cola: {e}")
        return False

def crear_registro_precarga():
    """Crea un nuevo registro con estado 'Preparando_RIS'."""
    conn = obtener_conexion()
    if not conn:
        return None
    try:
        cursor = conn.cursor()
        query = """
        INSERT INTO registro_acciones (inicio, `update`, ultimo_nodo, estado)
        VALUES (NOW(), NOW(), 'Precarga_Inicio', 'Preparando_RIS')
        """
        cursor.execute(query)
        new_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return new_id
    except Exception as e:
        logger.error(f"Error creando registro de precarga: {e}")
        return None

def marcar_listo_pacs(target_id):
    """Marca el registro como 'Listo_PACS' para que el orquestador lo tome directamente."""
    conn = obtener_conexion()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        query = """
        UPDATE registro_acciones 
        SET estado = 'Listo_PACS', ultimo_nodo = 'Listo_PACS', `update` = NOW()
        WHERE id = %s
        """
        cursor.execute(query, (target_id,))
        conn.commit()
        conn.close()
        logger.info(f"⚡ [PRECARGA] ✓ Examen ID {target_id} marcado como 'Listo_PACS'.")
        return True
    except Exception as e:
        logger.error(f"Error marcando Listo_PACS: {e}")
        return False

def marcar_error(target_id, error_msg):
    conn = obtener_conexion()
    if not conn:
        return
    try:
        cursor = conn.cursor()
        query = """
        UPDATE registro_acciones 
        SET estado = 'Error_Precarga', observacion = %s, `update` = NOW()
        WHERE id = %s
        """
        cursor.execute(query, (error_msg[:500], target_id))
        conn.commit()
        conn.close()
    except Exception:
        pass

def ejecutar_paso_ris(script_name, target_id):
    """Ejecuta un script de RIS pasando VAR_TARGET_ID y modo background."""
    base_dir = Path(__file__).parent
    script_path = base_dir / script_name
    if not script_path.exists():
        logger.error(f"No existe el script: {script_path}")
        return False

    env = os.environ.copy()
    env["VAR_TARGET_ID"] = str(target_id)
    env["VAR_RIS_BACKGROUND"] = "1"

    cflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    res = subprocess.run([sys.executable, str(script_path), str(target_id)], env=env, creationflags=cflags)
    return res.returncode == 0

def precargar():
    logger.info("Iniciando verificación de precarga de próximo examen...")
    
    if hay_examen_en_cola():
        logger.info("Ya existe un examen en estado 'Listo_PACS' o 'Preparando_RIS'. No se requiere precarga.")
        return

    target_id = crear_registro_precarga()
    if not target_id:
        logger.error("No se pudo inicializar registro de precarga.")
        return

    logger.info(f"Iniciando extracción en segundo plano para nuevo examen ID: {target_id}...")

    pasos = [
        ("Inicio_ris_v2.py", "Iniciando/reutilizando sesión RIS web"),
        ("seleccion_int_2_v2.py", "Aplicando filtros en lista"),
        ("busca_doctor_ultima_v2.py", "Extrayendo médico y abriendo PDF"),
        ("procesar_pdf_doctor_v2.py", "Parseando PDF de diagnóstico"),
        ("detecta_patologia_ia_v2_opt.py", "Evaluando patología crítica con IA")
    ]

    for script, desc in pasos:
        logger.info(f">> Paso: {desc} ({script})...")
        if not ejecutar_paso_ris(script, target_id):
            logger.error(f"Falló paso {script}. Abortando precarga.")
            marcar_error(target_id, f"Falló {script}")
            return

    # Si todo salió bien:
    marcar_listo_pacs(target_id)
    logger.info(f"🎉 ¡ÉXITO! Examen ID {target_id} listo para PACS sin esperas.")

if __name__ == "__main__":
    precargar()
