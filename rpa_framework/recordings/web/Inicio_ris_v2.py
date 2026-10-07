"""
Script: Inicio_ris_v2.py
Versión optimizada de Inicio_ris.py:
- Reutiliza la sesión activa de Chrome si ya está logueado en https://ris.chile.telemedicina.com/ris/atencion/lista
  (Ahorra ~25 segundos por ciclo al evitar logout, alerta, escritura de usuario, password y re-login).
- Soporta modo background/oculto sin robar foco ni maximizar sobre Carestream Vue PACS.
- Reduce pausas estáticas innecesarias.
"""

import time
import base64
import io
import sys
import os
import socket
from pathlib import Path
from typing import Optional
from datetime import datetime

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait, Select
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
    from utils.telegram_manager import enviar_alerta_todos
    try:
        from utils.window_utils import maximize_ris_windows
    except ImportError:
        try:
            from rpa_framework.utils.window_utils import maximize_ris_windows
        except ImportError:
            maximize_ris_windows = None
except ImportError:
    print("Error: Missing 'selenium' library. Install it with: pip install selenium")
    sys.exit(1)

try:
    import mysql.connector
    HAS_MYSQL = True
except ImportError:
    HAS_MYSQL = False
    print("Warning: Missing 'mysql-connector-python' library. Database tracking will be disabled.")

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


class WebAutomationV2:
    """Auto-generated Web Automation Class v2"""
    
    def __init__(self, headless=False, maximize=False, background=False):
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None
        self.headless = headless
        self.maximize = maximize
        self.background = background
        self.screenshots_dir = None
        self.db_config = {
            'host': 'localhost',
            'user': 'root',
            'password': '',
            'database': 'ris'
        }
        self.current_action_id = None

    def _get_db_connection(self):
        if not HAS_MYSQL:
            return None
        try:
            return mysql.connector.connect(**self.db_config)
        except Exception as e:
            print(f"[ERROR] Could not connect to database: {e}")
            return None

    def db_initialize(self):
        conn = self._get_db_connection()
        if not conn:
            return

        try:
            cursor = conn.cursor()
            print("[DB v2] Actualizando registro 'En Proceso' para Inicio RIS...")
            query = "SELECT id FROM registro_acciones WHERE estado = 'En Proceso' ORDER BY id DESC LIMIT 1"
            cursor.execute(query)
            row = cursor.fetchone()
            
            if row:
                self.current_action_id = row[0]
                update_query = "UPDATE registro_acciones SET `update` = NOW(), ultimo_nodo = 'Inicia RIS v2' WHERE id = %s"
                cursor.execute(update_query, (self.current_action_id,))
                conn.commit()
                print(f"[DB v2] Seguimiento activo para ID: {self.current_action_id}")
            else:
                print("[WARNING v2] No hay registro 'En Proceso' activo.")
        except Exception as e:
            print(f"[ERROR v2] Database init failed: {e}")
        finally:
            if conn and conn.is_connected():
                conn.close()

    def db_finish(self, success=True):
        if not self.current_action_id:
            return

        conn = self._get_db_connection()
        if not conn:
            return

        try:
            cursor = conn.cursor()
            if success:
                print("[DB v2] Actualización exitosa para Inicio RIS...")
                query = "UPDATE registro_acciones SET `update` = NOW(), ultimo_nodo = 'Inicia RIS v2' WHERE id = %s"
                cursor.execute(query, (self.current_action_id,))
            else:
                print("[DB v2] Marcando error para Inicio RIS...")
                query = "UPDATE registro_acciones SET `update` = NOW(), ultimo_nodo = 'Inicia RIS v2', estado = 'error' WHERE id = %s"
                cursor.execute(query, (self.current_action_id,))
            conn.commit()
        except Exception as e:
            print(f"[ERROR v2] Database finish update failed: {e}")
        finally:
            if conn and conn.is_connected():
                conn.close()

    def setup_browser(self):
        """Configures and connects to Chrome with fast port detection without stealing OS focus"""
        print("[INFO v2] Configurando opciones del navegador...", flush=True)
        try:
            is_port_open = False
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.3)
                    if s.connect_ex(('127.0.0.1', 9222)) == 0:
                        is_port_open = True
            except:
                pass

            if is_port_open:
                try:
                    print("[INFO v2] Puerto 9222 detectado. Conectando...", flush=True)
                    attach_options = ChromeOptions()
                    attach_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
                    self.driver = webdriver.Chrome(options=attach_options)
                    print("[INFO v2] Conexión exitosa al navegador existente.", flush=True)
                except Exception as e:
                    print(f"[WARNING v2] Error conectando a puerto 9222: {e}", flush=True)

            if not self.driver:
                print("[INFO v2] Iniciando nueva instancia de Chrome con puerto 9222...", flush=True)
                launch_options = ChromeOptions()
                launch_options.add_argument("--remote-debugging-port=9222")
                launch_options.add_argument("--no-sandbox")
                launch_options.add_argument("--disable-dev-shm-usage")
                
                profile_path = Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data" / "RPA_Remote_Profile"
                launch_options.add_argument(f"--user-data-dir={profile_path}")
                
                if self.maximize and not self.background:
                    launch_options.add_argument("--start-maximized")
                
                launch_options.add_experimental_option("detach", True)
                self.driver = webdriver.Chrome(options=launch_options)
                print("[INFO v2] Nueva instancia lanzada correctamente.", flush=True)

            self.wait = WebDriverWait(self.driver, 8)
            
            # Solo maximizar si no estamos en modo background
            if self.maximize and not self.background:
                try:
                    self.driver.maximize_window()
                    if maximize_ris_windows:
                        maximize_ris_windows()
                except Exception:
                    pass
            print("[INFO v2] Configuración de navegador completada.", flush=True)

        except Exception as e:
            print(f"[ERROR v2] Error fatal al iniciar el navegador: {e}", flush=True)
            raise

    def find_element(self, xpath: str, css: str = "", timeout: int = 6, clickable: bool = False):
        element = None
        condition = EC.element_to_be_clickable if clickable else EC.presence_of_element_located
        try:
            element = WebDriverWait(self.driver, timeout).until(condition((By.XPATH, xpath)))
        except Exception:
            if css:
                try:
                    element = WebDriverWait(self.driver, timeout).until(condition((By.CSS_SELECTOR, css)))
                except Exception:
                    pass
        return element

    def run(self, start_url: str = None):
        """Main execution flow with fast session-reuse"""
        try:
            self.db_initialize()
            self.setup_browser()

            current_url = ""
            try:
                current_url = self.driver.current_url
            except Exception:
                pass

            # ==============================================================
            # OPTIMIZACIÓN: REUTILIZAR SESIÓN SI YA ESTÁ LOGUEADO
            # ==============================================================
            print(f"[INFO v2] URL actual de Chrome: {current_url}")
            is_already_in_lista = "ris/atencion/lista" in current_url
            
            if not is_already_in_lista:
                # Comprobar si al navegar a lista se mantiene la sesión (evitando logout innecesario)
                try:
                    self.driver.get('https://ris.chile.telemedicina.com/ris/atencion/lista')
                    time.sleep(1)
                    if "ris/atencion/lista" in self.driver.current_url and "login" not in self.driver.current_url.lower():
                        is_already_in_lista = True
                        print("[INFO v2] ⚡ Sesión activa reutilizada directamente en lista de atención (Ahorro ~25s)!")
                except Exception:
                    pass

            if is_already_in_lista:
                # Ya estamos logueados en la lista. Solo asegurar filtros o refrescar
                print("[INFO v2] ⚡ Saltando proceso de logout / login. Validando filtros...")
                btn_buscar = self.find_element(r"//*[@id='buscar']", r"button#buscar", timeout=3)
                if not btn_buscar:
                    mostrar = self.find_element(r"//*[@id='mostrar']", r"a#mostrar", timeout=3, clickable=True)
                    if mostrar:
                        self.driver.execute_script('arguments[0].click();', mostrar)
                        self.find_element(r"//*[@id='buscar']", r"button#buscar", timeout=6)
                
                print("[INFO v2] ✓ Lista RIS preparada y lista.")
                self.db_finish(success=True)
                return

            # ==============================================================
            # FALLBACK: LOGIN COMPLETO SOLO SI NO HAY SESIÓN ACTIVA
            # ==============================================================
            print("[INFO v2] Sesión no detectada. Iniciando login formal...")
            self.driver.get('https://ris.chile.telemedicina.com/usuario/logout')
            time.sleep(1)

            try:
                WebDriverWait(self.driver, 3).until(EC.alert_is_present())
                alert = self.driver.switch_to.alert
                alert.accept()
                time.sleep(0.5)
            except Exception:
                pass

            # Usuario
            user_el = self.find_element(r"//*[@id='user']", r"input#user", timeout=5, clickable=True)
            if user_el:
                user_el.clear()
                user_el.send_keys('rbt.integra')

            # Pass
            pass_el = self.find_element(r"//*[@id='pass']", r"input#pass", timeout=5, clickable=True)
            if pass_el:
                pass_el.clear()
                pass_el.send_keys('Integramedica02!')

            # Click Ingresar
            btn_el = self.find_element(r"//*[@id='button']", r"button#button", timeout=5, clickable=True)
            if btn_el:
                self.driver.execute_script('arguments[0].click();', btn_el)
                time.sleep(1.5)

            # Navegar lista
            self.driver.get('https://ris.chile.telemedicina.com/ris/atencion/lista')
            time.sleep(1.5)

            # Mostrar filtros
            mostrar_el = self.find_element(r"//*[@id='mostrar']", r"a#mostrar", timeout=5, clickable=True)
            if mostrar_el:
                self.driver.execute_script('arguments[0].click();', mostrar_el)
                self.find_element(r"//*[@id='buscar']", r"button#buscar", timeout=10)

            print("[INFO v2] Automation completed successfully")
            self.db_finish(success=True)

        except Exception as e:
            print(f"[ERROR v2] {e}")
            self.db_finish(success=False)
            sys.exit(1)


def main():
    background_mode = os.environ.get("VAR_RIS_BACKGROUND", "0") == "1"
    automation = WebAutomationV2(headless=False, maximize=not background_mode, background=background_mode)
    automation.run()

if __name__ == "__main__":
    main()
