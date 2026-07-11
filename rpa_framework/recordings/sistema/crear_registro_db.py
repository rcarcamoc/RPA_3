#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script: crear_registro_db.py
Descripción: Crea el registro inicial en ris.registro_acciones para el seguimiento del workflow.
             Debe ejecutarse como primer nodo del workflow.
"""

import sys
import os
import time
from datetime import datetime

try:
    import mysql.connector
    from mysql.connector import Error
except ImportError:
    print("Error: El módulo 'mysql.connector' no está instalado.")
    sys.exit(1)

# Configuración BD
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'ris'
}

def crear_registro():
    """Limpia registros previos 'En Proceso' y crea uno nuevo."""
    conn = None
    try:
        print(f"[{time.strftime('%H:%M:%S')}] Conectando a BD para inicializar seguimiento...")
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # 1. Limpieza: Marcar como error registros que quedaron colgados 'En Proceso'
        print("[DB] Limpiando registros previos 'En Proceso'...")
        cleanup_query = "UPDATE registro_acciones SET estado = 'Error', observacion = 'Sesión anterior interrumpida' WHERE estado = 'En Proceso'"
        cursor.execute(cleanup_query)
        rows_cleaned = cursor.rowcount
        if rows_cleaned > 0:
            print(f"[DB] Se cerraron {rows_cleaned} registros antiguos.")

        # 2. Insertar nuevo registro
        print("[DB] Creando nuevo registro de ejecución...")
        insert_query = """
        INSERT INTO registro_acciones (inicio, `update`, ultimo_nodo, estado) 
        VALUES (NOW(), NOW(), 'Inicio Workflow', 'En Proceso')
        """
        cursor.execute(insert_query)
        record_id = cursor.lastrowid
        
        conn.commit()
        print(f"✓ Éxito: Registro creado con ID: {record_id}")
        
        cursor.close()
        conn.close()
        sys.exit(0)

    except Exception as e:
        print(f"❌ Error fatal al crear registro en BD: {e}")
        if conn and conn.is_connected():
            conn.close()
        sys.exit(1)

if __name__ == "__main__":
    crear_registro()
