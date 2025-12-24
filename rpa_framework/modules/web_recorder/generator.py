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
from pathlib import Path
from typing import Optional

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
    
    def setup_browser(self):
        """Configures and starts the browser"""
        try:
            chrome_options = ChromeOptions()
            
            if self.headless:
                chrome_options.add_argument("--headless")
            
            if self.maximize:
                chrome_options.add_argument("--start-maximized")
            
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            # chrome_options.add_argument("--disable-gpu") # Optional
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.wait = WebDriverWait(self.driver, 10)
            
            self.screenshots_dir = Path.cwd() / "screenshots_results"
            self.screenshots_dir.mkdir(exist_ok=True)
            
            print("[INFO] Browser started")
        except Exception as e:
            print(f"[ERROR] Could not start browser: {e}")
            raise
    
    def find_element(self, xpath: str, timeout: int = 10):
        """Finds an element by XPath"""
        try:
            element = self.wait.until(
                EC.presence_of_element_located((By.XPATH, xpath)),
                f"Timeout waiting for: {xpath}"
            )
            return element
        except Exception as e:
            print(f"[WARNING] Element not found: {xpath}")
            return None
    
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
    
    def execute_actions(self):
        """Executes all recorded actions"""
        try:
            self.setup_browser()
'''
    
    def _get_main_logic(self) -> str:
        """Generates the action code"""
        actions_code = ""
        
        for i, action in enumerate(self.recorder.actions):
            actions_code += self._action_to_code(action, i)
        
        return f'''{actions_code}
            
            print("[INFO] Automation completed successfully")
            
        except Exception as e:
            print(f"[ERROR] Error during execution: {{e}}")
            # traceback.print_exc()
        finally:
            self._cleanup()
    
    def _cleanup(self):
        """Cleans up resources"""
        if self.driver:
            try:
                self.driver.quit()
                print("[INFO] Browser closed")
            except:
                pass


def main():
    """Main execution entry point"""
    automation = WebAutomation(headless=False, maximize=True)
    automation.execute_actions()


if __name__ == "__main__":
    main()
'''
    
    def _action_to_code(self, action: WebAction, index: int) -> str:
        """Converts an action to Python code"""
        code = f"\n            # Action {index + 1}: {action.action_type.upper()}\n"
        
        try:
            timestamp = datetime.fromtimestamp(action.timestamp).strftime("%H%M%S")
            
            if action.action_type == 'page_load':
                code += f"            print('[ACTION] Loading page: {action.url}')\n"
                code += f"            self.driver.get('{action.url}')\n"
                code += "            time.sleep(2)\n"
            
            elif action.action_type == 'click':
                xpath = action.element_info.xpath
                text = action.element_info.text[:30] if action.element_info.text else ""
                
                # Check for screenshot
                if action.screenshot_base64:
                    img_name = f"step_{index+1}_click_{timestamp}.png"
                    code += f"            # Reference Screenshot: {img_name}\n"
                
                if xpath:
                    code += f"            print('[ACTION] Click on: {text}')\n"
                    # Use triple quotes for safety against internal quotes
                    code += f'            element = self.find_element(r"""{xpath}""")\n'
                    code += "            if element:\n"
                    code += "                self.driver.execute_script('arguments[0].scrollIntoView(true);', element)\n"
                    code += "                time.sleep(0.5)\n"
                    code += "                element.click()\n"
                    code += "                time.sleep(0.5)\n"
            
            elif action.action_type == 'input':
                xpath = action.element_info.xpath
                value = (action.value or "")
                if xpath:
                    code += f"            print('[ACTION] Typing text')\n"
                    code += f'            element = self.find_element(r"""{xpath}""")\n'
                    code += "            if element:\n"
                    code += "                element.clear()\n"
                    code += f"                element.send_keys(r'{value}')\n"
                    code += "                time.sleep(0.3)\n"
            
            elif action.action_type == 'select':
                xpath = action.element_info.xpath
                value = action.value or ""
                if xpath:
                    code += f"            print('[ACTION] Selecting option')\n"
                    code += f'            element = self.find_element(r"""{xpath}""")\n'
                    code += "            if element:\n"
                    code += f"                Select(element).select_by_value(r'{value}')\n"
                    code += "                time.sleep(0.3)\n"
        
        except Exception as e:
            code += f"            # [ERROR] Generating code for action {index}: {e}\n"
        
        return code
