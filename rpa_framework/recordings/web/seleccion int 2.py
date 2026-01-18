"""
Auto-generated Web Automation Script
Generated: 2026-01-01T18:05:43.911047
Total Actions: 6
Clicks: 2
Inputs: 2
Selects: 0
Duration: 00:21

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
        self.script_name = "seleccion int 2"
        # Database config
        self.db_config = {
            'host': 'localhost',
            'user': 'root',
            'password': '',
            'database': 'ris'
        }

    def _get_db_connection(self):
        """Helper to get a database connection"""
        if not HAS_MYSQL:
            return None
        try:
            return mysql.connector.connect(**self.db_config)
        except Exception as e:
            print(f"[ERROR] Could not connect to database: {e}")
            return None

    def db_update_node(self, status='En Proceso'):
        """Updates the current 'En Proceso' record with current node and timestamp"""
        conn = self._get_db_connection()
        if not conn:
            return

        try:
            cursor = conn.cursor()
            
            # Update the record that is 'En Proceso'
            query = """
            UPDATE registro_acciones 
            SET `update` = NOW(), ultimo_nodo = %s, estado = %s 
            WHERE estado = 'En Proceso'
            """
            cursor.execute(query, (self.script_name, status))
            conn.commit()
            print(f"[DB] Updated node to '{self.script_name}' (Status: {status})")
            
        except Exception as e:
            print(f"[ERROR] Database update failed: {e}")
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
            # Inform start of node
            self.db_update_node(status='En Proceso')
            
            self.setup_browser()
            
            if start_url and start_url != "about:blank":
                print(f"[INFO] Navigating to: {start_url}")
                self.driver.get(start_url)
            else:
                print(f"[INFO] Using current page: {self.driver.current_url}")
                
            # Recorded actions start here
            print("[INFO] Starting recorded actions...")



            # Action 2: Click to Open Dropdown
            print('[ACTION] Opening Dropdown (Seleccionar)')
            # Primary: CSS selector for the Select2 container link/button
            element = self.find_element(r"""//div[@id='s2id_filtro_cliente']/a""", r"""div#s2id_filtro_cliente > a""", clickable=True)
            if element:
                element.click() 
                time.sleep(1.0)
            else:
                print("[WARNING] Could not find the dropdown opener 'div#s2id_filtro_cliente > a'")

            # Action 3, 4, 5: Search and Select
            print('[ACTION] Searching and Selecting: integramedica')
            
            # Wait specifically for the dropdown container to appear
            try:
                self.wait.until(EC.visibility_of_element_located((By.ID, "select2-drop")))
            except:
                print("[WARNING] Dropdown container #select2-drop did not explicitly appear.")

            # Find the input field within the now-open dropdown
            # Using the specific class 'select2-input' which is standard for Select2
            element = self.find_element(r"""//div[@id='select2-drop']//input[contains(@class,'select2-input')]""", r"""#select2-drop input.select2-input""", clickable=True)
            
            if element:
                element.clear()
                element.send_keys('integramedica')
                time.sleep(1.5) # Wait for filtering
             #   element.send_keys(Keys.ARROW_DOWN)
                time.sleep(0.5)
                element.send_keys(Keys.ENTER)
                time.sleep(1.0)
            else:
                print("[ERROR] Could not find the Select2 search input!")

            
     # Action 2: selecciona examen validado
            print('[ACTION] CLICK on: ')
            element = self.find_element(r"""//input[contains(@class, '__rpa-highlight')]""", r"""form#frm_buscar > table > tbody > tr:nth-of-type(2) > td > input:nth-of-type(4)""", clickable=True)
            if element:
                element.click()
                time.sleep(0.1)


            # Action 5: CLICK en buscar
            print('[ACTION] CLICK on:  Buscar estudios')
            element = self.find_element(r"""//*[@id='buscar']""", r"""button#buscar""", clickable=True)
            if element:
                element.click()
                time.sleep(0.5)


            print("[INFO] Automation completed successfully")
            # Inform success
            self.db_update_node(status='En Proceso')
            
        except Exception as e:
            print(f"[ERROR] Error during execution: {e}")
            # Inform error
            self.db_update_node(status='error')
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
