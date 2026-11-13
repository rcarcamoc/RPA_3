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
    
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
    from utils.telegram_manager import enviar_alerta_todos
    try:
        from utils.chrome_session import connect_or_launch_rpa_chrome
    except ImportError:
        from rpa_framework.utils.chrome_session import connect_or_launch_rpa_chrome
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
        """Updates database state to indicate this node is starting"""
        conn = self._get_db_connection()
        if not conn:
            return

        try:
            cursor = conn.cursor()
            
            # En lugar de INSERT, actualizamos el registro que ya debe existir (creado por el nodo inicial)
            print("[DB] Actualizando registro 'En Proceso' para Inicio RIS...")
            update_query = "UPDATE registro_acciones SET `update` = NOW(), ultimo_nodo = 'Inicia RIS' WHERE estado = 'En Proceso'"
            cursor.execute(update_query)
            
            # Recuperamos el ID para seguimiento interno del script
            cursor.execute("SELECT id FROM registro_acciones WHERE estado = 'En Proceso' ORDER BY id DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                self.current_action_id = row[0]
            
            conn.commit()
            if self.current_action_id:
                print(f"[DB] Seguimiento activo para ID: {self.current_action_id}")
            
        except Exception as e:
            print(f"[ERROR] Error al actualizar estado en BD: {e}")
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
                print("[DB] Actualización exitosa para Inicio RIS...")
                query = "UPDATE registro_acciones SET `update` = NOW(), ultimo_nodo = 'Inicia RIS' WHERE id = %s"
                cursor.execute(query, (self.current_action_id,))
            else:
                # Error case: Update timestamp, node, and set status to error
                print("[DB] Marcando error para Inicio RIS...")
                query = "UPDATE registro_acciones SET `update` = NOW(), ultimo_nodo = 'Inicia RIS', estado = 'error' WHERE id = %s"
                cursor.execute(query, (self.current_action_id,))
            
            conn.commit()
            
        except Exception as e:
            print(f"[ERROR] Database finish update failed: {e}")
        finally:
            if conn and conn.is_connected():
                conn.close()
    
    def setup_browser(self):
        """Configures and starts the browser with fast port detection and auto-repair"""
        print("[INFO] Configurando opciones del navegador...", flush=True)
        try:
            self.driver = connect_or_launch_rpa_chrome(
                port=9222,
                maximize=self.maximize,
                headless=self.headless,
                allow_launch=True,
            )
            self.wait = WebDriverWait(self.driver, 10)
            try:
                self.driver.maximize_window()
            except Exception:
                pass
            if maximize_ris_windows:
                try:
                    maximize_ris_windows()
                except Exception:
                    pass
            self.screenshots_dir = Path.cwd() / "screenshots_results"
            self.screenshots_dir.mkdir(exist_ok=True)
            print("[INFO] Configuración de navegador completada (maximizado).", flush=True)
            
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
            # Asumimos Chrome/Edge
            screen_rect = self.driver.execute_script("""
                var rect = arguments[0].getBoundingClientRect();
                var borderLeft = (window.outerWidth - window.innerWidth) / 2; // Estimado
                var navHeight = window.outerHeight - window.innerHeight - borderLeft; // Estimado
                
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
            # print(f"[WARNING] Visual Highlight failed: {e}")
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

            # Action 2: HANDLE_ALERT (verificación inmediata sin espera de 5s)
            try:
                alert = self.driver.switch_to.alert
                print(f'[INFO] Alert text: {alert.text}')
                alert.accept()
            except Exception:
                pass

            # Action 3-4: INPUT Usuario
            print('[ACTION] Typing text (user)')
            element = self.find_element(r"""//*[@id='user']""", r"""input#user""", clickable=True)
            if element:
                element.clear()
                element.send_keys(r'rbt.integra')

            # Action 5-7: INPUT Password
            print('[ACTION] Typing text (pass)')
            element = self.find_element(r"""//*[@id='pass']""", r"""input#pass""", clickable=True)
            if element:
                element.clear()
                element.send_keys(r'Integramedica02!')

            # Action 8: CLICK Ingresar y esperar redirección post-login
            print('[ACTION] CLICK on: Ingresar')
            element = self.find_element(r"""//*[@id='button']""", r"""button#button""", clickable=True)
            if element:
                element.click()
                try:
                    self.wait.until(lambda d: '/usuario/logout' not in d.current_url)
                except Exception:
                    time.sleep(1.0)

            # Action 9: PAGE_LOAD
            print('[ACTION] Loading page: https://ris.chile.telemedicina.com/ris/atencion/lista')
            self.driver.get('https://ris.chile.telemedicina.com/ris/atencion/lista')

            # Action 11: CLICK Mostrar Filtros
            print('[ACTION] CLICK on: Mostrar Filtros')
            element = self.find_element(r"""//*[@id='mostrar']""", r"""a#mostrar""", clickable=True)
            if element:
                self._visual_highlight(element)
                self.driver.execute_script('arguments[0].click();', element)
                print('[INFO] Esperando a que carguen los filtros del sistema...', flush=True)
                self.find_element(r"//*[@id='buscar']", r"button#buscar", timeout=15)



            try:
                self.driver.maximize_window()
            except Exception:
                pass
            if maximize_ris_windows:
                try:
                    maximize_ris_windows()
                except Exception:
                    pass

            print("[INFO] Automation completed successfully (RIS Maximizado)")
            
            # Update database for success
            self.db_finish(success=True)
            
        except Exception as e:
            try:
                from rpa_framework.utils.error_handler import handle_error_and_exit
                handle_error_and_exit("Inicio_ris.py", str(e))
            except ImportError:
                print(f"[ERROR] {e}")
                sys.exit(1)
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
