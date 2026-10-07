#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script: busqueda_paciente_v2.py
Versión optimizada de busqueda_paciente.py:
- Tiempos de tabulación y tipeo acelerados (Ahorro ~6-8s).
- Clics directos y doble clic ágil en la fila del paciente.
"""

import sys
import time
import logging
from pathlib import Path
from datetime import datetime
import pyautogui
pyautogui.FAILSAFE = False

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pywinauto import Application, findwindows

try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


class BusquedaPacienteV2:
    def __init__(self):
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    def db_update_status(self, status='En Proceso'):
        if not HAS_MYSQL:
            return
        try:
            conn = mysql.connector.connect(host='localhost', user='root', password='', database='ris')
            cursor = conn.cursor()
            script_name = "busqueda_paciente_v2"
            query = "UPDATE registro_acciones SET `update` = NOW(), ultimo_nodo = %s, estado = %s WHERE estado = 'En Proceso'"
            cursor.execute(query, (script_name, status))
            conn.commit()
            conn.close()
        except Exception:
            pass

    def get_patient_id(self):
        if not HAS_MYSQL:
            return None
        try:
            conn = mysql.connector.connect(host='localhost', user='root', password='', database='ris')
            cursor = conn.cursor()
            query = "SELECT replace(numero_documento,'-','') FROM registro_acciones WHERE estado ='En Proceso' ORDER BY id DESC LIMIT 1"
            cursor.execute(query)
            row = cursor.fetchone()
            conn.close()
            return str(row[0]).strip() if row and row[0] else None
        except Exception as e:
            logger.error(f"Error obteniendo patient_id: {e}")
            return None

    def run(self):
        self.db_update_status('En Proceso')
        patient_id = self.get_patient_id()
        if not patient_id:
            logger.error("No se encontró patient_id en BD.")
            return False

        logger.info(f"Ingresando ID de paciente v2: {patient_id}")

        # Asegurar foco
        try:
            titulos = findwindows.find_elements(title_re=".*Carestream.*")
            if titulos:
                app = Application(backend='win32').connect(handle=titulos[0].handle)
                app.window(handle=titulos[0].handle).set_focus()
                time.sleep(0.2)
        except Exception:
            pass

        # 1. 5 Tabulaciones rápidas
        for _ in range(5):
            pyautogui.press('tab')
            time.sleep(0.06)
        time.sleep(0.15)

        # 2. Escribir ID del paciente
        pyautogui.write(patient_id, interval=0.03)
        time.sleep(0.2)

        # 3. Clic en botón Buscar (1702, 291)
        pyautogui.click(1702, 291)
        time.sleep(0.5)

        # 4. Doble clic en paciente (1010, 368)
        pyautogui.doubleClick(1010, 368)
        time.sleep(0.3)

        logger.info("✓ Búsqueda de paciente completada exitosamente.")
        self.db_update_status('En Proceso')
        return True


def main():
    autom = BusquedaPacienteV2()
    if autom.run():
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
