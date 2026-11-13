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

# Importar para alertas de telegram
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from utils.telegram_manager import enviar_alerta_todos
try:
    from utils.chrome_session import connect_or_launch_rpa_chrome
except ImportError:
    from rpa_framework.utils.chrome_session import connect_or_launch_rpa_chrome

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
        """Connects to the existing RPA browser on port 9222 and validates the RIS tab"""
        print("[INFO] Configurando opciones del navegador...", flush=True)
        try:
            self.driver = connect_or_launch_rpa_chrome(
                port=9222,
                maximize=self.maximize,
                headless=self.headless,
                allow_launch=False,
                expected_url_substr="ris.chile.telemedicina.com",
            )
            self.wait = WebDriverWait(self.driver, 10)
            try:
                self.driver.maximize_window()
            except Exception:
                pass
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
    

    def _visual_highlight(self, element):
        """Intenta resaltar visualmente el elemento usando VisualFeedback"""
        try:
             # Lazy import
            try:
                sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
                from rpa_framework.utils.visual_feedback import VisualFeedback
                vf = VisualFeedback()
            except ImportError:
                return

            # Calcular coordenadas de pantalla usando JS
            screen_rect = self.driver.execute_script("""
                var rect = arguments[0].getBoundingClientRect();
                var borderLeft = (window.outerWidth - window.innerWidth) / 2;
                var navHeight = window.outerHeight - window.innerHeight - borderLeft;
                
                return {
                    x: rect.left + window.screenX + borderLeft,
                    y: rect.top + window.screenY + navHeight,
                    width: rect.width,
                    height: rect.height
                };
            """, element)
            
            final_x = screen_rect['x'] + screen_rect['width']/2
            final_y = screen_rect['y'] + screen_rect['height']/2
             
            vf.highlight_click(final_x, final_y)
        except Exception as e:
            pass

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



            # Action 1: Selección directa de cliente Integramédica (INT-000) vía jQuery/DOM
            print('[ACTION] Selecting client: Integramédica (INT-000)')
            cliente_sel = self.find_element(r"""//*[@id='filtro_cliente']""", r"""select#filtro_cliente""", clickable=False)
            if not cliente_sel:
                raise RuntimeError("No se encontró el selector de cliente '#filtro_cliente' en RIS.")

            selected_val = self.driver.execute_script("""
                var sel = document.getElementById('filtro_cliente');
                if (!sel) return null;
                if (window.jQuery && jQuery(sel).length) {
                    jQuery(sel).val('INT-000').trigger('change');
                } else {
                    sel.value = 'INT-000';
                    sel.dispatchEvent(new Event('change', { bubbles: true }));
                }
                return sel.value;
            """)
            if selected_val != 'INT-000':
                raise RuntimeError(f"No se pudo seleccionar cliente INT-000 (valor actual: {selected_val}).")

            # Action 2: Selecciona checkbox Examen Validado (name="estados[]", value="7")
            print('[ACTION] CLICK on: Examen Validado')
            element = self.find_element(
                r"""//form[@id='frm_buscar']//input[@name='estados[]' and @value='7']""",
                r"""#frm_buscar input[name="estados[]"][value="7"]""",
                clickable=True,
            )
            if element:
                if not element.is_selected():
                    self._visual_highlight(element)
                    element.click()
                    time.sleep(0.1)

            # Action 3: CLICK en Buscar estudios
            print('[ACTION] CLICK on: Buscar estudios')
            element = self.find_element(r"""//*[@id='buscar']""", r"""button#buscar""", clickable=True)
            if element:
                self._visual_highlight(element)
                element.click()
                time.sleep(0.3)
            else:
                raise RuntimeError("No se encontró el botón 'Buscar estudios' (#buscar) en RIS.")


            print("[INFO] Automation completed successfully")
            # Inform success
            self.db_update_node(status='En Proceso')
            
        except Exception as e:
            try:
                from rpa_framework.utils.error_handler import handle_error_and_exit
                handle_error_and_exit("seleccion int 2.py", str(e))
            except ImportError:
                print(f"[ERROR] {e}")
                sys.exit(1)
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
