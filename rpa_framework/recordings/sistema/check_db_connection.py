#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script: check_db_connection.py
Ubicación: rpa_framework/recordings/sistema/check_db_connection.py
Descripción: Valida que la conexión a la base de datos MySQL 'ris' esté activa.
             Si no lo está, termina con código de error (1).
"""

import sys
import ctypes
import os
import time

try:
    import mysql.connector
    from mysql.connector import Error
except ImportError:
    print("Error: El módulo 'mysql.connector' no está instalado.")
    print("Intenta: pip install mysql-connector-python")
    sys.exit(1)

def launch_wamp():
    """Intenta ejecutar WampManager con permisos de administrador."""
    wamp_path = r"C:\wamp64\wampmanager.exe"
    
    if os.path.exists(wamp_path):
        print(f"⚠️ Intentando iniciar WampManager desde: {wamp_path}")
        try:
            # ShellExecuteW con verbo 'runas' solicita elevación (UAC)
            # hwnd, operation, file, parameters, directory, showCmd (1=SW_SHOWNORMAL)
            result = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", wamp_path, None, None, 1
            )
            if result > 32:
                print("✓ Solicitud de inicio de WampManager enviada correctamente.")
            else:
                print(f"❌ Error al solicitar inicio de WampManager (código: {result}).")
        except Exception as e:
            print(f"❌ Excepción al intentar lanzar WampManager: {e}")
    else:
        print(f"❌ No se encontró WampManager en: {wamp_path}")

def check_connection():
    """
    Intenta conectar a MySQL. Si falla, inicia WAMP y reintenta cada 10 segundos
    hasta que la conexión sea exitosa.
    """
    wamp_launched = False
    config = {
        'host': 'localhost',
        'user': 'root',
        'password': '',
        'database': 'ris'
    }
    
    while True:
        connection = None
        try:
            print(f"[{time.strftime('%H:%M:%S')}] Intentando conectar a MySQL en {config['host']}...")
            
            # Agregamos un timeout corto para la conexión para que no cuelgue demasiado
            connection = mysql.connector.connect(**config, connect_timeout=5)
            
            if connection.is_connected():
                db_info = connection.server_info
                print(f"✓ Éxito: Conexión activa a MySQL Server versión {db_info}")
                print(f"✓ Base de datos seleccionada: {config['database']}")
                sys.exit(0) # Salida exitosa del script
                
        except (Error, Exception) as e:
            print(f"⚠️ Falló la conexión a la base de datos.")
            print(f"   Detalle: {e}")
            
            if not wamp_launched:
                launch_wamp()
                wamp_launched = True
                print("⏳ Se ha solicitado el inicio de WAMP. Esperando que los servicios se activen...")
            
            print("⏳ Reintentando en 10 segundos...")
            time.sleep(10)
            
        finally:
            if connection and connection.is_connected():
                connection.close()

if __name__ == "__main__":
    check_connection()

