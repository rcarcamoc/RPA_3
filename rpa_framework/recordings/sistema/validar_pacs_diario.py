#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script: validar_pacs_diario.py
Descripción: Ejecuta la validación diaria de PACS corriendo el workflow Valida_pacs.json.
             Registra acciones en ris.registro_acciones y ris.validacion_pacs.
"""

import sys
import os
import time
import json
import argparse
import traceback
from datetime import datetime
from pathlib import Path

# Agregar directorio raíz al sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

if sys.platform.startswith('win'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

try:
    import mysql.connector
    from mysql.connector import Error
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

try:
    from core.models import Workflow
    from core.workflow_executor import WorkflowExecutor
except ImportError:
    WorkflowExecutor = None

try:
    from utils.telegram_manager import enviar_alerta_todos
except ImportError:
    enviar_alerta_todos = None

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'ris'
}

CONFIG_FILE = BASE_DIR / "config" / "pacs_validation_config.json"
STATE_FILE = BASE_DIR / "config" / "execution_state.json"
WF_PATH = BASE_DIR / "workflows" / "Valida_pacs.json"

DOCTOR_NOMBRE = "Cristian Navarro"
DOCTOR_USER = "CNAVARROGA"
DOCTOR_PASS = "cristian"


def load_pacs_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[CONFIG ERROR] Error al cargar pacs_validation_config.json: {e}")
    return {
        "max_reintentos": 3,
        "timeout_minutos": 10,
        "delay_entre_reintentos_seg": 120,
        "telegram": {"enviar_alertas": True}
    }


def asegurar_tabla_validacion(conn):
    """Crea la tabla ris.validacion_pacs si no existe."""
    cursor = conn.cursor()
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS ris.validacion_pacs (
        id INT AUTO_INCREMENT PRIMARY KEY,
        fecha_validacion DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        estado ENUM('En Proceso', 'Exitoso', 'Error') NOT NULL DEFAULT 'En Proceso',
        doctor_validacion VARCHAR(200) DEFAULT 'Cristian Navarro',
        user_validacion VARCHAR(100) DEFAULT 'CNAVARROGA',
        pass_validacion VARCHAR(100) DEFAULT 'cristian',
        registro_acciones_id INT NULL,
        observacion VARCHAR(500),
        duracion_segundos INT,
        intentos INT DEFAULT 1,
        fecha_actualizacion DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
    );
    """
    cursor.execute(create_table_sql)
    conn.commit()
    cursor.close()


def set_bg_execution_state(is_running, workflow_name=""):
    """Actualiza el archivo execution_state.json para bloquear la GUI y el bot."""
    state = {
        "is_running": is_running,
        "workflow": workflow_name,
        "updated_at": time.time()
    }
    try:
        STATE_FILE.parent.mkdir(exist_ok=True)
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f)
    except Exception as e:
        print(f"[STATE ERROR] No se pudo guardar estado: {e}")


def ejecutar_validacion(dry_run=False, manual=False):
    """Ejecuta el proceso completo de validación de PACS."""
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🚀 Iniciando Validación Diaria PACS...")
    
    config = load_pacs_config()
    max_reintentos = config.get("max_reintentos", 3)
    delay_reintentos = config.get("delay_entre_reintentos_seg", 120)
    
    if not HAS_MYSQL:
        print("❌ Error: Módulo mysql.connector no disponible.")
        return False

    conn = None
    reg_acciones_id = None
    val_pacs_id = None
    inicio_ts = time.time()
    
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        asegurar_tabla_validacion(conn)
        cursor = conn.cursor()
        
        # 1. Query 1: Limpieza de registros colgados 'En Proceso'
        print("[DB] Limpiando registros previos 'En Proceso' en registro_acciones...")
        q1 = "UPDATE ris.registro_acciones SET estado = 'Error', observacion = 'Limpieza pre-validación PACS' WHERE estado = 'En Proceso'"
        cursor.execute(q1)
        cleaned_rows = cursor.rowcount
        conn.commit()
        if cleaned_rows > 0:
            print(f"[DB] Se actualizaron {cleaned_rows} registros colgados a estado Error.")
            
        # 2. Query 2: Insert a registro_acciones con id equivalente a 184 (Cristian Navarro)
        print("[DB] Insertando registro de prueba en ris.registro_acciones...")
        q2 = """
        INSERT INTO ris.registro_acciones (inicio, `update`, ultimo_nodo, estado, doctor_detectado, User, Pass)
        VALUES (NOW(), NOW(), 'Validación PACS', 'En Proceso', %s, %s, %s)
        """
        cursor.execute(q2, (DOCTOR_NOMBRE, DOCTOR_USER, DOCTOR_PASS))
        reg_acciones_id = cursor.lastrowid
        conn.commit()
        print(f"✓ Registro acciones creado con ID: {reg_acciones_id}")
        
        # 3. Registrar en ris.validacion_pacs
        q3 = """
        INSERT INTO ris.validacion_pacs (fecha_validacion, estado, doctor_validacion, user_validacion, pass_validacion, registro_acciones_id)
        VALUES (NOW(), 'En Proceso', %s, %s, %s, %s)
        """
        cursor.execute(q3, (DOCTOR_NOMBRE, DOCTOR_USER, DOCTOR_PASS, reg_acciones_id))
        val_pacs_id = cursor.lastrowid
        conn.commit()
        print(f"✓ Registro validación PACS creado con ID: {val_pacs_id}")
        
        cursor.close()
        
        if dry_run:
            print("🔬 [DRY RUN] Simulación finalizada. Revertiendo cambios...")
            cursor = conn.cursor()
            cursor.execute("DELETE FROM ris.registro_acciones WHERE id = %s", (reg_acciones_id,))
            cursor.execute("UPDATE ris.validacion_pacs SET estado = 'Exitoso', observacion = 'Dry-Run Completado' WHERE id = %s", (val_pacs_id,))
            conn.commit()
            cursor.close()
            conn.close()
            return True
            
        # Marca estado ocupado globalmente
        set_bg_execution_state(True, "Validación PACS")
        
        # 4. Ejecución del Workflow Valida_pacs.json con reintentos
        workflow_exitoso = False
        ultimo_error = ""
        
        if not WF_PATH.exists():
            raise FileNotFoundError(f"No se encontró el archivo de workflow: {WF_PATH}")

        for intento in range(1, max_reintentos + 1):
            print(f"\n🔄 Intento {intento}/{max_reintentos} de ejecución de workflow {WF_PATH.name}...")
            
            # Actualizar número de intento en DB
            cursor = conn.cursor()
            cursor.execute("UPDATE ris.validacion_pacs SET intentos = %s WHERE id = %s", (intento, val_pacs_id))
            conn.commit()
            cursor.close()

            try:
                wf = Workflow.from_json(str(WF_PATH))
                executor = WorkflowExecutor(wf)
                res = executor.execute()
                
                if isinstance(res, dict) and res.get("status") in ["success", "completed"]:
                    workflow_exitoso = True
                    print("✅ Workflow Valida_pacs ejecutado EXITOSAMENTE.")
                    break
                else:
                    ultimo_error = str(res.get("error", "Ejecución de workflow no exitosa")) if isinstance(res, dict) else "Error en workflow"
                    print(f"⚠️ Intento {intento} falló: {ultimo_error}")
            except Exception as we:
                ultimo_error = str(we)
                print(f"❌ Excepción en intento {intento}: {ultimo_error}")
                traceback.print_exc()

            if intento < max_reintentos:
                print(f"⏳ Esperando {delay_reintentos} segundos antes del siguiente intento...")
                time.sleep(delay_reintentos)
                
        duracion = int(time.time() - inicio_ts)
        cursor = conn.cursor()

        if workflow_exitoso:
            # 5. Si termina correctamente, ELIMINA el registro temporal de validación de registro_acciones
            print(f"[DB] Eliminando registro temporal de validación {reg_acciones_id} de ris.registro_acciones...")
            cursor.execute("DELETE FROM ris.registro_acciones WHERE id = %s", (reg_acciones_id,))
            
            # Actualizar ris.validacion_pacs a Exitoso
            cursor.execute("""
            UPDATE ris.validacion_pacs 
            SET estado = 'Exitoso', observacion = 'Validación completada correctamente', duracion_segundos = %s 
            WHERE id = %s
            """, (duracion, val_pacs_id))
            conn.commit()
            print(f"🎉 Validación de PACS COMPLETADA CON ÉXITO en {duracion} segundos.")
            
            # Enviar alerta Telegram si está configurado en éxito
            tg_cfg = config.get("telegram", {})
            if tg_cfg.get("enviar_alertas", True) and tg_cfg.get("enviar_en_exito", False):
                if enviar_alerta_todos:
                    msj = f"✅ <b>VALIDACIÓN PACS EXITOSA</b>\nLa validación diaria de PACS se completó correctamente en {duracion}s (Intento {intento})."
                    try:
                        enviar_alerta_todos(msj)
                    except Exception as tge:
                        print(f"⚠️ No se pudo enviar alerta Telegram: {tge}")
            res_final = True
        else:
            # Si falla: ELIMINAR también el registro temporal de registro_acciones para que no ensucie reportes de casos
            print(f"[DB] Eliminando registro temporal de validación {reg_acciones_id} tras fallo de validación...")
            cursor.execute("DELETE FROM ris.registro_acciones WHERE id = %s", (reg_acciones_id,))
            
            obs_fail = f"Falló tras {max_reintentos} intentos. Error: {ultimo_error[:250]}"
            cursor.execute("""
            UPDATE ris.validacion_pacs 
            SET estado = 'Error', observacion = %s, duracion_segundos = %s 
            WHERE id = %s
            """, (obs_fail, duracion, val_pacs_id))
            conn.commit()
            print(f"❌ Validación de PACS FALLIDA. Observación: {obs_fail}")
            
            # Enviar alerta Telegram si está configurado
            tg_cfg = config.get("telegram", {})
            if tg_cfg.get("enviar_alertas", True) and tg_cfg.get("enviar_en_error", True):
                if enviar_alerta_todos:
                    msj = f"🚨 <b>ALERTA VALIDACIÓN PACS</b>\nLa validación diaria de PACS ha fallado tras {max_reintentos} intentos.\n\nDetalle: {ultimo_error[:200]}"
                    try:
                        enviar_alerta_todos(msj)
                    except Exception as tge:
                        print(f"⚠️ No se pudo enviar alerta Telegram: {tge}")
            res_final = False

        cursor.close()
        return res_final

    except Exception as e:
        print(f"💥 Error fatal en validación diaria de PACS: {e}")
        traceback.print_exc()
        if conn and val_pacs_id:
            try:
                dur = int(time.time() - inicio_ts)
                c = conn.cursor()
                c.execute("UPDATE ris.validacion_pacs SET estado = 'Error', observacion = %s, duracion_segundos = %s WHERE id = %s", 
                          (f"Excepción fatal: {str(e)[:250]}", dur, val_pacs_id))
                if reg_acciones_id:
                    c.execute("DELETE FROM ris.registro_acciones WHERE id = %s", (reg_acciones_id,))
                conn.commit()
                c.close()
            except Exception:
                pass
        return False
    finally:
        if conn and conn.is_connected() and reg_acciones_id:
            try:
                c_fin = conn.cursor()
                c_fin.execute("DELETE FROM ris.registro_acciones WHERE id = %s", (reg_acciones_id,))
                conn.commit()
                c_fin.close()
            except Exception:
                pass
        set_bg_execution_state(False)
        if conn and conn.is_connected():
            conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validación diaria de PACS")
    parser.add_argument("--dry-run", action="store_true", help="Simula las queries DB sin correr el workflow")
    parser.add_argument("--manual", action="store_true", help="Indica ejecución manual")
    args = parser.parse_args()
    
    exito = ejecutar_validacion(dry_run=args.dry_run, manual=args.manual)
    sys.exit(0 if exito else 1)
