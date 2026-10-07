"""
Script: seleccion_int_2_v2.py
Versión optimizada de seleccion int 2.py:
- Detección rápida de cliente ya seleccionado para evitar reescribir 'integramedica' innecesariamente.
- No utiliza feedback visual obstructivo cuando está en modo background.
- Tiempos de espera optimizados.
"""

import time
import sys
import os
import socket
from pathlib import Path
from typing import Optional

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options as ChromeOptions
except ImportError:
    print("Error: Missing 'selenium' library.")
    sys.exit(1)

try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False


class SeleccionInt2V2:
    def __init__(self, background=False):
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None
        self.background = background
        self.script_name = "seleccion int 2 v2"
        self.db_config = {
            'host': 'localhost',
            'user': 'root',
            'password': '',
            'database': 'ris'
        }

    def _get_db_connection(self):
        if not HAS_MYSQL:
            return None
        try:
            return mysql.connector.connect(**self.db_config)
        except Exception:
            return None

    def db_update_node(self, status='En Proceso'):
        conn = self._get_db_connection()
        if not conn:
            return
        try:
            cursor = conn.cursor()
            query = """
            UPDATE registro_acciones 
            SET `update` = NOW(), ultimo_nodo = %s, estado = %s 
            WHERE estado = 'En Proceso'
            """
            cursor.execute(query, (self.script_name, status))
            conn.commit()
            conn.close()
        except Exception:
            pass

    def setup_browser(self):
        try:
            options = ChromeOptions()
            options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
            self.driver = webdriver.Chrome(options=options)
            self.wait = WebDriverWait(self.driver, 8)
        except Exception as e:
            print(f"[ERROR v2] No se pudo conectar a Chrome en 9222: {e}")
            raise

    def find_element(self, xpath: str, css: str = "", timeout: int = 6, clickable: bool = False):
        condition = EC.element_to_be_clickable if clickable else EC.presence_of_element_located
        try:
            return WebDriverWait(self.driver, timeout).until(condition((By.XPATH, xpath)))
        except Exception:
            if css:
                try:
                    return WebDriverWait(self.driver, timeout).until(condition((By.CSS_SELECTOR, css)))
                except Exception:
                    pass
        return None

    def run(self):
        try:
            self.db_update_node(status='En Proceso')
            self.setup_browser()

            print("[INFO v2] Configurando filtros en lista RIS...")

            # 1. Comprobar si Integramédica ya está seleccionado en el select2
            select2_text = ""
            try:
                selected_container = self.driver.find_element(By.CSS_SELECTOR, "div#s2id_filtro_cliente span.select2-chosen")
                select2_text = selected_container.text.strip().lower()
            except Exception:
                pass

            if "integra" not in select2_text:
                print("[ACTION v2] Seleccionando Integramédica...")
                opener = self.find_element(r"//div[@id='s2id_filtro_cliente']/a", r"div#s2id_filtro_cliente > a", clickable=True)
                if opener:
                    opener.click()
                    time.sleep(0.3)
                    
                    search_input = self.find_element(r"//div[@id='select2-drop']//input[contains(@class,'select2-input')]", r"#select2-drop input.select2-input", clickable=True)
                    if search_input:
                        search_input.clear()
                        search_input.send_keys('integramedica')
                        time.sleep(0.5)
                        search_input.send_keys(Keys.ENTER)
                        time.sleep(0.3)
            else:
                print("[INFO v2] ⚡ Integramédica ya estaba seleccionado en el filtro.")

            # 2. Checkbox de examen validado si aplica
            try:
                chk = self.find_element(r"//input[contains(@class, '__rpa-highlight')]", r"form#frm_buscar > table > tbody > tr:nth-of-type(2) > td > input:nth-of-type(4)", timeout=2, clickable=True)
                if chk and not chk.is_selected():
                    chk.click()
            except Exception:
                pass

            # 3. Clic en Buscar estudios
            print("[ACTION v2] Click en 'Buscar estudios'...")
            btn_buscar = self.find_element(r"//*[@id='buscar']", r"button#buscar", timeout=5, clickable=True)
            if btn_buscar:
                self.driver.execute_script("arguments[0].click();", btn_buscar)
                time.sleep(0.8)

            print("[INFO v2] Filtros aplicados exitosamente.")
            self.db_update_node(status='En Proceso')

        except Exception as e:
            print(f"[ERROR v2] {e}")
            sys.exit(1)


def main():
    background_mode = os.environ.get("VAR_RIS_BACKGROUND", "0") == "1"
    automation = SeleccionInt2V2(background=background_mode)
    automation.run()

if __name__ == "__main__":
    main()
