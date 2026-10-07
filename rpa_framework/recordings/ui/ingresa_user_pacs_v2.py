#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script autogenerado: ingresa_user_pacs_v2
Versión optimizada de ingresa_user_pacs.py:
- Elimina el time.sleep(10) innecesario al finalizar (Ahorro directo de 10s).
- Optimiza tiempos de entrada de texto e interacción directa con coordenadas.
"""

import sys
import time
import logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from pywinauto import Application, findwindows
import pyautogui
pyautogui.FAILSAFE = False

try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)


class IngresaUserPacsV2:
    def __init__(self):
        self.app = None
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    def db_update_status(self, status='En Proceso'):
        if not HAS_MYSQL:
            return
        try:
            conn = mysql.connector.connect(host='localhost', user='root', password='', database='ris')
            cursor = conn.cursor()
            script_name = "ingresa_user_pacs_v2"
            query = "UPDATE registro_acciones SET `update` = NOW(), ultimo_nodo = %s, estado = %s WHERE estado = 'En Proceso'"
            cursor.execute(query, (script_name, status))
            conn.commit()
            conn.close()
        except Exception:
            pass

    def get_credentials(self):
        if not HAS_MYSQL:
            return None, None
        try:
            conn = mysql.connector.connect(host='localhost', user='root', password='', database='ris')
            cursor = conn.cursor()
            query = "SELECT user, pass FROM ris.registro_acciones WHERE estado = 'En Proceso' AND user IS NOT NULL AND TRIM(user) != '' ORDER BY id DESC LIMIT 1"
            cursor.execute(query)
            result = cursor.fetchone()
            if result and result[0] and result[1]:
                conn.close()
                return result[0].strip(), result[1].strip()

            # Fallback a médico activo
            cursor.execute("SELECT user, pass FROM medicos WHERE activo = 1 LIMIT 1")
            res_medico = cursor.fetchone()
            conn.close()
            if res_medico:
                return res_medico[0].strip(), res_medico[1].strip()
            return None, None
        except Exception as e:
            logger.error(f"Error obteniendo credenciales: {e}")
            return None, None

    def run(self):
        self.db_update_status('En Proceso')
        db_user, db_pass = self.get_credentials()
        if not db_user or not db_pass:
            logger.error("No se encontraron credenciales en BD.")
            return False

        logger.info(f"Ingresando credenciales v2 (Usuario: {db_user})")

        # Enfocar ventana Carestream
        try:
            wins = findwindows.find_elements(title_re=".*Carestream.*")
            if wins:
                app = Application(backend="win32").connect(handle=wins[0].handle)
                win = app.window(handle=wins[0].handle)
                win.set_focus()
                time.sleep(0.3)
        except Exception:
            pass

        # 1. Clic en campo usuario (980, 435) directo con pyautogui
        pyautogui.click(980, 435)
        time.sleep(0.3)
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.write(db_user, interval=0.03)
        time.sleep(0.2)

        # 2. Tab para pasar a password
        pyautogui.press('tab')
        time.sleep(0.2)
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.write(db_pass, interval=0.03)
        time.sleep(0.2)

        # 3. Enter o clic en botón entrar (980, 572)
        pyautogui.press('enter')
        time.sleep(0.5)
        pyautogui.click(980, 572)

        logger.info("✓ Credenciales enviadas exitosamente. (Sin espera de 10s).")
        self.db_update_status('En Proceso')
        return True


def main():
    autom = IngresaUserPacsV2()
    if autom.run():
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
