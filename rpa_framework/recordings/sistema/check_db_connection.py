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
    connection = None
    try:
        # Parámetros tomados de rpa_framework/recordings/ocr/busqueda_triple_combinada.py
        config = {
            'host': 'localhost',
            'user': 'root',
            'password': '',
            'database': 'ris'
        }
        
        print(f"Intentando conectar a MySQL en {config['host']}...")
        
        connection = mysql.connector.connect(**config)
        
        if connection.is_connected():
            db_info = connection.get_server_info()
            print(f"Exito: Conexión activa a MySQL Server versión {db_info}")
            print(f"Base de datos seleccionada: {config['database']}")
            sys.exit(0) # Salida exitosa
            
    except Error as e:
        print(f"Error: Falló la conexión a la base de datos.")
        print(f"Detalle: {e}")
        
        # Acción de recuperación: Abrir WampManager
        launch_wamp()
        
        sys.exit(1) # Salida con error (aunque intentamos recuperar, esta ejecución falló)
        
    except Exception as e:
        print(f"Error: Ocurrió un error inesperado al comprobar la conexión.")
        print(f"Detalle: {e}")
        
        # Intento de recuperación también aquí por sie s error de red local
        launch_wamp()
        
        sys.exit(1) # Salida con error
        
    finally:
        if connection and connection.is_connected():
            connection.close()
            print("Conexión cerrada.")

if __name__ == "__main__":
    check_connection()
