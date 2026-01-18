"""
Auto-generated Web Automation Script
Generated: 2025-12-30T09:27:43.927192
Total Actions: 11
Clicks: 5
Inputs: 2
Selects: 0
Duration: 00:57

Description:
This script executes the actions recorded via the RPA Web Recorder.
It is standalone and only requires 'selenium' and 'pillow'.
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
    print("Warning: Missing 'pillow' library. Screenshots will not be saved. (pip install pillow)")


class WebAutomation:
    """Auto-generated Web Automation Class"""
    
    def __init__(self, headless=False, maximize=True):
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None
        self.headless = headless
        self.maximize = maximize
        self.screenshots_dir = None
        # Database config
        self.db_config = {
            'host': 'localhost',
            'user': 'root',
            'password': '',
            'database': 'ris'
        }
        self.current_action_id = None

    def _get_db_connection(self):
        """Helper to get a database connection"""
        if not HAS_MYSQL:
            return None
        try:
            return mysql.connector.connect(**self.db_config)
        except Exception as e:
            print(f"[ERROR] Could not connect to database: {e}")
            return None

    def db_initialize(self):
        """Initializes database state for the current run"""
        conn = self._get_db_connection()
        if not conn:
            return

        try:
            cursor = conn.cursor()
            
            # 1. Update existing 'En Proceso' records to 'error'
            print("[DB] Cleaning up previous 'En Proceso' records...")
            update_query = "UPDATE registro_acciones SET estado = 'error', `update` = NOW() WHERE estado = 'En Proceso'"
            cursor.execute(update_query)
            
            # 2. Insert new record for current run
            print("[DB] Inserting new run record...")
            insert_query = """
            INSERT INTO registro_acciones (inicio, `update`, ultimo_nodo, estado) 
            VALUES (NOW(), NOW(), 'inicio', 'En Proceso')
            """
            cursor.execute(insert_query)
            self.current_action_id = cursor.lastrowid
            
            conn.commit()
            print(f"[DB] New run record created with ID: {self.current_action_id}")
            
        except Exception as e:
            print(f"[ERROR] Database initialization failed: {e}")
        finally:
            if conn and conn.is_connected():
                conn.close()

    def db_finish(self, success=True):
        """Updates database state on script completion or error"""
        if self.current_action_id is None:
            return
            
        conn = self._get_db_connection()
        if not conn:
            return

        try:
            cursor = conn.cursor()
            
            if success:
                # Success case: Update timestamp and node (keep status as En Proceso for next node)
                print("[DB] Updating record for success...")
                query = "UPDATE registro_acciones SET `update` = NOW(), ultimo_nodo = 'inicio' WHERE id = %s"
                cursor.execute(query, (self.current_action_id,))
            else:
                # Error case: Update timestamp, node, and set status to error
                print("[DB] Updating record for error...")
                query = "UPDATE registro_acciones SET `update` = NOW(), ultimo_nodo = 'inicio', estado = 'error' WHERE id = %s"
                cursor.execute(query, (self.current_action_id,))
            
            conn.commit()
            
        except Exception as e:
            print(f"[ERROR] Database finish update failed: {e}")
        finally:
            if conn and conn.is_connected():
                conn.close()
    
    def setup_browser(self):
        """Configures and starts the browser with fast port detection"""
        print("[INFO] Configurando opciones del navegador...", flush=True)
        try:
            # --- FAST PORT CHECK ---
            is_port_open = False
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.5) # Very fast check
                    if s.connect_ex(('127.0.0.1', 9222)) == 0:
                        is_port_open = True
            except:
                pass

            # --- STRATEGY 1: ATTACH TO EXISTING ---
            if is_port_open:
                try:
                    print("[INFO] Puerto 9222 detectado. Intentando conectar...", flush=True)
                    attach_options = ChromeOptions()
                    attach_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
                    self.driver = webdriver.Chrome(options=attach_options)
                    print("[INFO] Conexión exitosa al navegador existente.", flush=True)
                except Exception as e:
                    print(f"[WARNING] Puerto abierto pero no respondió como Chrome: {e}", flush=True)

            if not self.driver:
                # --- STRATEGY 2: LAUNCH NEW WITH REMOTE DEBUGGING ---
                print("[INFO] Iniciando nueva instancia de Chrome con puerto 9222...", flush=True)
                
                launch_options = ChromeOptions()
                launch_options.add_argument("--remote-debugging-port=9222")
                launch_options.add_argument("--no-sandbox")
                launch_options.add_argument("--disable-dev-shm-usage")
                
                # Use a dedicated profile
                profile_path = Path.home() / "AppData" / "Local" / "Google" / "Chrome" / "User Data" / "RPA_Remote_Profile"
                launch_options.add_argument(f"--user-data-dir={profile_path}")
                
                if self.maximize:
                    launch_options.add_argument("--start-maximized")
                
                launch_options.add_experimental_option("detach", True)
                
                try:
                    self.driver = webdriver.Chrome(options=launch_options)
                    print("[INFO] Nueva instancia lanzada correctamente.", flush=True)
                except Exception as e2:
                    print(f"[ERROR] Error al lanzar con puerto 9222: {e2}", flush=True)
                    # --- STRATEGY 3: STANDALONE FALLBACK ---
                    print("[INFO] Intentando lanzamiento estándar (sin depuración remota)...", flush=True)
                    fallback_options = ChromeOptions()
                    if self.maximize:
                        fallback_options.add_argument("--start-maximized")
                    fallback_options.add_experimental_option("detach", True)
                    self.driver = webdriver.Chrome(options=fallback_options)
                    print("[INFO] Lanzamiento estándar exitoso.", flush=True)

            self.wait = WebDriverWait(self.driver, 10)
            self.screenshots_dir = Path.cwd() / "screenshots_results"
            self.screenshots_dir.mkdir(exist_ok=True)
            print("[INFO] Configuración de navegador completada.", flush=True)
            
        except Exception as e:
            print(f"[ERROR] Error fatal al iniciar el navegador: {e}", flush=True)
            raise
    
    def find_element(self, xpath: str, css: str = "", timeout: int = 10, clickable: bool = False):
        """Finds an element by XPath with CSS fallback"""
        element = None
        condition = EC.element_to_be_clickable if clickable else EC.presence_of_element_located
        
        # 1. Try XPath
        try:
            element = self.wait.until(
                condition((By.XPATH, xpath)),
                f"Timeout waiting for: {xpath}"
            )
        except Exception:
            pass
            
        # 2. Try CSS if XPath failed
        if not element and css:
            try:
                element = self.wait.until(
                    condition((By.CSS_SELECTOR, css)),
                    f"Timeout waiting for CSS: {css}"
                )
            except Exception:
                pass
                
        if not element:
             print(f"[WARNING] Element not found by XPath or CSS: {xpath} | {css}")
             
        return element
    
    def save_screenshot(self, base64_data: str, filename: str):
        """Saves a screenshot from base64"""
        if not base64_data or not HAS_PIL:
            return
        
        try:
            # Check if it was truncated/placeholder
            if len(base64_data) < 100:
                return
            
            img_data = base64.b64decode(base64_data)
            img = Image.open(io.BytesIO(img_data))
            filepath = self.screenshots_dir / filename
            img.save(filepath)
            # print(f"[INFO] Screenshot saved: {filepath}")
        except Exception as e:
            print(f"[WARNING] Error saving screenshot: {e}")
    
    def run(self, start_url: str = None):
        """Main execution flow"""
        try:
            # Initialize database tracking
            self.db_initialize()
            
            self.setup_browser()
            
            if start_url and start_url != "about:blank":
                print(f"[INFO] Navigating to: {start_url}")
                self.driver.get(start_url)
            else:
                print(f"[INFO] Using current page: {self.driver.current_url}")
                
            # Recorded actions start here
            print("[INFO] Starting recorded actions...")


            # Action 1: PAGE_LOAD
            print('[ACTION] Loading page: https://ris.chile.telemedicina.com/usuario/logout')
            self.driver.get('https://ris.chile.telemedicina.com/usuario/logout')
            time.sleep(2)

            # Action 2: HANDLE_ALERT
            print('[ACTION] Handling Alert')
            try:
                WebDriverWait(self.driver, 5).until(EC.alert_is_present())
                alert = self.driver.switch_to.alert
                print(f'[INFO] Alert text: {alert.text}')
                alert.accept()
                time.sleep(1)
            except Exception as e:
                print(f'[WARNING] No alert found to handle: {e}')

            # Action 3: CLICK
            print('[ACTION] CLICK on: ')
            element = self.find_element(r"""//*[@id='user']""", r"""input#user""", clickable=True)
            if element:
                self.driver.execute_script('arguments[0].scrollIntoView(true);', element)
                time.sleep(1.0)
                element.click()
                time.sleep(1.0)

            # Action 4: INPUT
            print('[ACTION] Typing text')
            element = self.find_element(r"""//*[@id='user']""", r"""input#user""", clickable=True)
            if element:
                element.clear()
                element.send_keys(r'rbt.integra')
                time.sleep(1.0)

            # Action 5: CLICK
            print('[ACTION] CLICK on: ')
            element = self.find_element(r"""//*[@id='pass']""", r"""input#pass""", clickable=True)
            if element:
                self.driver.execute_script('arguments[0].scrollIntoView(true);', element)
                time.sleep(1.0)
                element.click()
                time.sleep(1.0)

       

            # Action 7: INPUT
            print('[ACTION] Typing text')
            element = self.find_element(r"""//*[@id='pass']""", r"""input#pass""", clickable=True)
            if element:
                element.clear()
                element.send_keys(r'Integramedica02!')
                time.sleep(1.0)

            # Action 8: CLICK
            print('[ACTION] CLICK on: Ingresar')
            element = self.find_element(r"""//*[@id='button']""", r"""button#button""", clickable=True)
            if element:
                self.driver.execute_script('arguments[0].scrollIntoView(true);', element)
                time.sleep(1.0)
                element.click()
                time.sleep(1.0)

            # Action 9: PAGE_LOAD
            print('[ACTION] Loading page: https://ris.chile.telemedicina.com/ris/atencion/lista')
            self.driver.get('https://ris.chile.telemedicina.com/ris/atencion/lista')
            time.sleep(2)

        

            # Action 11: CLICK
            print('[ACTION] CLICK on: Mostrar Filtros')
            element = self.find_element(r"""//*[@id='mostrar']""", r"""a#mostrar""", clickable=True)
            if element:
                # Se utiliza click via JS para evitar que Selenium haga scroll automático al elemento
                self.driver.execute_script('arguments[0].click();', element)
                # Esperar a que el botón de búsqueda sea visible (máximo 15 segundos)
                # Esto es más eficiente que un sleep fijo de 10 segundos
                print('[INFO] Esperando a que carguen los filtros del sistema...', flush=True)
                self.find_element(r"//*[@id='buscar']", r"button#buscar", timeout=15)



            print("[INFO] Automation completed successfully")
            
            # Update database for success
            self.db_finish(success=True)
            
        except Exception as e:
            print(f"[ERROR] Error during execution: {e}")
            # Update database for error
            self.db_finish(success=False)
            # traceback.print_exc()
        finally:
            self._cleanup()
    
    def _cleanup(self):
        """Cleans up resources"""
        if self.driver:
            try:
                # self.driver.quit() # Commented out to keep browser open as requested
                print("[INFO] Automation finished. Keeping browser open.")
            except:
                pass


def main():
    """Main execution entry point"""
    # Start the automation. 
    # If you want to force a specific URL, pass it to run(start_url="...")
    automation = WebAutomation(headless=False, maximize=True)
    automation.run()


if __name__ == "__main__":
    main()
