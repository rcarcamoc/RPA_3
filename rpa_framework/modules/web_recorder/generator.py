#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web Recorder - Script Generator
Generates a standalone Python script from recorded actions.
"""

from datetime import datetime
from .web_recorder import WebRecorder, WebAction

class PythonScriptGenerator:
    """Generates Python scripts from captured actions"""
    
    def __init__(self, recorder: WebRecorder):
        self.recorder = recorder
    
    def generate(self) -> str:
        """Generates the complete script"""
        header = self._get_header()
        imports = self._get_imports()
        web_automation_class = self._get_web_automation_class()
        main_logic = self._get_main_logic()
        
        return f"{header}\n{imports}\n{web_automation_class}\n{main_logic}"
    
    def _get_header(self) -> str:
        """Script header"""
        return f'''"""
Auto-generated Web Automation Script
Generated: {datetime.now().isoformat()}
Total Actions: {len(self.recorder.actions)}
Clicks: {self.recorder.stats.clicks}
Inputs: {self.recorder.stats.inputs}
Selects: {self.recorder.stats.selects}
Duration: {self.recorder.stats.elapsed_formatted}

Description:
This script executes the actions recorded via the RPA Web Recorder.
It is standalone and only requires 'selenium' and 'pillow'.
"""'''
    
    def _get_imports(self) -> str:
        """Necessary imports"""
        return '''
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
'''
    
    def _get_web_automation_class(self) -> str:
        """Main automation class"""
        return '''
class WebAutomation:
    """Auto-generated Web Automation Class"""
    
    def __init__(self, headless=False, maximize=True):
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None
        self.headless = headless
        self.maximize = maximize
        self.screenshots_dir = None
        # Identity for database tracking
        self.script_name = Path(sys.argv[0]).stem
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

    def db_update_status(self, status='En Proceso'):
        """Updates the current execution record in the database"""
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
            print(f"[DB] Tracking updated: {self.script_name} ({status})")
        except Exception as e:
            print(f"[ERROR] Database tracking failed: {e}")
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
            # DB Tracking: Start
            self.db_update_status(status='En Proceso')
            
            self.setup_browser()
            
            if start_url and start_url != "about:blank":
                print(f"[INFO] Navigating to: {start_url}")
                self.driver.get(start_url)
            else:
                print(f"[INFO] Using current page: {self.driver.current_url}")
                
            # Recorded actions start here
            print("[INFO] Starting recorded actions...")
'''
    
    def _get_main_logic(self) -> str:
        """Generates the action code with smart optimization"""
        actions_code = ""
        i = 0
        n = len(self.recorder.actions)
        
        while i < n:
            action = self.recorder.actions[i]
            
            # --- OPTIMIZATION: Detect Select2 Pattern ---
            # Pattern: Click Opener -> [Click Input] -> Input Text -> Keypress Enter
            if action.action_type == 'click':
                # Look ahead
                next_idx = i + 1
                if next_idx < n:
                    next_act = self.recorder.actions[next_idx]
                    
                    # Skip intermediate click on the input itself if present
                    if next_act.action_type == 'click' and self._is_select2_input(next_act):
                        next_idx += 1
                        if next_idx < n:
                            next_act = self.recorder.actions[next_idx]
                    
                    # Check for Input on Select2
                    if next_act.action_type == 'input' and self._is_select2_input(next_act):
                        input_act = next_act
                        
                        # Check for subsequent Enter
                        enter_act = None
                        after_input_idx = next_idx + 1
                        if after_input_idx < n:
                            candi = self.recorder.actions[after_input_idx]
                            if candi.action_type == 'keypress' and (candi.value == 'Enter' or (isinstance(candi.value, dict) and candi.value.get('key') == 'Enter')):
                                enter_act = candi
                                next_idx = after_input_idx 
                        
                        # Detected Sequence!
                        actions_code += self._generate_select2_block(i, action, input_act, enter_act)
                        
                        # Check for spurious empty input after Enter (common artifact)
                        if next_idx + 1 < n:
                            cleanup_act = self.recorder.actions[next_idx + 1]
                            if cleanup_act.action_type == 'input' and not cleanup_act.value:
                                next_idx += 1
                                
                        i = next_idx + 1
                        continue

            # Standard Generation
            actions_code += self._action_to_code(action, i)
            i += 1
        
        return f'''{actions_code}
            
            print("[INFO] Automation completed successfully")
            # DB Tracking: Success
            self.db_update_status(status='En Proceso')
            
        except Exception as e:
            print(f"[ERROR] Error during execution: {{e}}")
            # DB Tracking: Error
            self.db_update_status(status='error')
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
'''

    def _is_select2_input(self, action: WebAction) -> bool:
        """Checks if action functionality targets a Select2 search input"""
        info = action.element_info
        # Check specific Select2 classes or IDs
        if 'select2-input' in info.class_name or 'select2-focused' in info.class_name:
            return True
        if 'select2-drop' in info.xpath or 'select2-drop' in info.css_selector:
            return True
        return False

    def _generate_select2_block(self, idx, open_act, input_act, enter_act):
        """Generates robust code for Select2 interaction"""
        opener_xpath = open_act.element_info.xpath
        opener_css = open_act.element_info.css_selector
        value = input_act.value or ""
        
        code = f"\n            # Action {idx+1}-{idx+3}: Smart Select2 Interaction ({value})\n"
        code += f"            print('[ACTION] Searching and Selecting: {value}')\n"
        
        # 1. Open Dropdown
        code += f"            # 1. Open Dropdown\n"
        code += f'            element = self.find_element(r"""{opener_xpath}""", r"""{opener_css}""", clickable=True)\n'
        code += "            if element:\n"
        code += "                element.click()\n"
        code += "                time.sleep(1.0)\n"
        code += "            else:\n"
        code += "                print('[WARNING] Could not find dropdown opener')\n"

        # 2. Wait for Container
        code += "\n            # 2. Wait for Dropdown Container\n"
        code += "            try:\n"
        code += "                self.wait.until(EC.visibility_of_element_located((By.ID, 'select2-drop')))\n"
        code += "            except:\n"
        code += "                print('[WARNING] Dropdown container #select2-drop did not explicitly appear.')\n"
        
        # 3. Find Input & Type
        code += "\n            # 3. Search & Enter\n"
        code += '            element = self.find_element(r"""//div[@id=\'select2-drop\']//input[contains(@class,\'select2-input\')]""", r"""#select2-drop input.select2-input""", clickable=True)\n'
        code += "            if element:\n"
        code += "                element.clear()\n"
        code += f"                element.send_keys(r'{value}')\n"
        code += "                time.sleep(1.5) # Wait for filtering\n"
        if enter_act:
             # Only add Arrow Down if user wants it (commenting it out by default as per user latest pref)
            code += "                # element.send_keys(Keys.ARROW_DOWN)\n"
            code += "                time.sleep(0.5)\n"
            code += "                element.send_keys(Keys.ENTER)\n"
        code += "                time.sleep(1.0)\n"
        code += "            else:\n"
        code += "                print('[ERROR] Could not find Select2 search input!')\n"
            
        return code
    
    def _action_to_code(self, action: WebAction, index: int) -> str:
        """Converts an action to Python code"""
        code = f"\n            # Action {index + 1}: {action.action_type.upper()}\n"
        
        try:
            timestamp = datetime.fromtimestamp(action.timestamp).strftime("%H%M%S")
            
            if action.action_type == 'page_load':
                code += f"            print('[ACTION] Loading page: {action.url}')\n"
                code += f"            self.driver.get('{action.url}')\n"
                code += "            time.sleep(2)\n"
            
            elif action.action_type in ['click', 'dblclick', 'contextmenu']:
                xpath = action.element_info.xpath
                css = action.element_info.css_selector or ""
                text = action.element_info.text[:30] if action.element_info.text else ""
                
                # Check for screenshot
                if action.screenshot_base64:
                    img_name = f"step_{index+1}_{action.action_type}_{timestamp}.png"
                    code += f"            # Reference Screenshot: {img_name}\n"
                
                if xpath:
                    code += f"            print('[ACTION] {action.action_type.upper()} on: {text}')\n"
                    # Pass both xpath and css for fallback, and ensure clickable
                    code += f'            element = self.find_element(r"""{xpath}""", r"""{css}""", clickable=True)\n'
                    code += "            if element:\n"
                    # code += "                self.driver.execute_script('arguments[0].scrollIntoView(true);', element)\n"
                    # code += "                time.sleep(1.0)\n"
                    
                    if action.action_type == 'click':
                        # Prefer standard click for better event triggering, fallback to JS if needed?
                        # Standard click is better for dropdowns openers usually.
                        code += "                element.click()\n"
                    elif action.action_type == 'dblclick':
                        code += "                ActionChains(self.driver).double_click(element).perform()\n"
                    elif action.action_type == 'contextmenu':
                        code += "                ActionChains(self.driver).context_click(element).perform()\n"
                        
                    code += "                time.sleep(1.0)\n"
            
            elif action.action_type == 'input':
                xpath = action.element_info.xpath
                css = action.element_info.css_selector or ""
                value = (action.value or "")
                if xpath:
                    code += f"            print('[ACTION] Typing text')\n"
                    code += f'            element = self.find_element(r"""{xpath}""", r"""{css}""", clickable=True)\n'
                    code += "            if element:\n"
                    code += "                element.clear()\n"
                    code += f"                element.send_keys(r'{value}')\n"
                    code += "                time.sleep(1.0)\n"
            
            elif action.action_type == 'select':
                xpath = action.element_info.xpath
                css = action.element_info.css_selector or ""
                value = action.value or ""
                if xpath:
                    code += f"            print('[ACTION] Selecting option')\n"
                    code += f'            element = self.find_element(r"""{xpath}""", r"""{css}""", clickable=True)\n'
                    code += "            if element:\n"
                    code += f"                Select(element).select_by_value(r'{value}')\n"
                    code += "                time.sleep(1.0)\n"

            elif action.action_type == 'keypress':
                xpath = action.element_info.xpath
                css = action.element_info.css_selector or ""
                # We currently only support Enter explicitly, but structure allows expansion
                if getattr(action, 'key', '') == 'Enter' or (isinstance(action.value, dict) and action.value.get('key') == 'Enter'):
                     if xpath:
                        code += f"            print('[ACTION] Pressing Key: Enter')\n"
                        code += f'            element = self.find_element(r"""{xpath}""", r"""{css}""", clickable=True)\n'
                        code += "            if element:\n"
                        code += "                element.send_keys(Keys.ENTER)\n"
                        code += "                time.sleep(1)\n"

            elif action.action_type == 'handle_alert':
                code += f"            print('[ACTION] Handling Alert')\n"
                code += "            try:\n"
                code += "                WebDriverWait(self.driver, 5).until(EC.alert_is_present())\n"
                code += "                alert = self.driver.switch_to.alert\n"
                code += f"                print(f'[INFO] Alert text: {{alert.text}}')\n"
                code += "                alert.accept()\n"
                code += "                time.sleep(1)\n"
                code += "            except Exception as e:\n"
                code += "                print(f'[WARNING] No alert found to handle: {e}')\n"
        
        except Exception as e:
            code += f"            # [ERROR] Generating code for action {index}: {e}\n"
        
        return code
