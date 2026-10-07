#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script: crear_registro_db_v2.py
Descripción: Versión optimizada de inicialización de registro en ris.registro_acciones.
             Soporta el estado 'Listo_PACS' para permitir el flujo concurrente / pipeline.
"""

import sys
import os
import time
from datetime import datetime

if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

try:
    import mysql.connector
    from mysql.connector import Error
except ImportError:
    print("Error: El módulo 'mysql.connector' no está instalado.")
    sys.exit(1)

try:
    from rpa_framework.utils.screen_utils import get_screen_resolution
except ImportError:
    try:
        from utils.screen_utils import get_screen_resolution
    except ImportError:
        def get_screen_resolution():
            return os.environ.get("VAR_screen_resolution", "1920x1080")

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'ris'
}

def crear_registro(estado_inicial='En Proceso'):
    """Crea un nuevo registro para seguimiento sin bloquear registros concurrentes."""
    conn = None
    try:
        print(f"[{time.strftime('%H:%M:%S')}] Conectando a BD para inicializar seguimiento v2...")
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        resolucion = get_screen_resolution()
        print(f"[DB v2] Creando nuevo registro de ejecución (Estado: {estado_inicial}, Res: {resolucion})...")
        insert_query = """
        INSERT INTO registro_acciones (inicio, `update`, ultimo_nodo, estado, resolucion_pantalla) 
        VALUES (NOW(), NOW(), 'Inicio Workflow v2', %s, %s)
        """
        cursor.execute(insert_query, (estado_inicial, resolucion))
        record_id = cursor.lastrowid
        
        conn.commit()
        print(f"✓ Éxito v2: Registro creado con ID: {record_id} (Estado: {estado_inicial})")
        
        cursor.close()
        conn.close()
        return record_id

    except Exception as e:
        print(f"❌ Error fatal al crear registro en BD v2: {e}")
        if conn and conn.is_connected():
            conn.close()
        sys.exit(1)

if __name__ == "__main__":
    crear_registro()
