"""
Auto-generated Web Automation Script
Generated: 2025-12-24T18:41:51.370133
Total Actions: 6
Clicks: 1
Inputs: 0
Selects: 0
Duration: 00:23

Description:
This script executes the actions recorded via the RPA Web Recorder.
It is standalone and only requires 'selenium' and 'pillow'.
"""

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


            # Action 1: PAGE_LOAD
            print('[ACTION] Loading page: https://www.google.com')
            self.driver.get('https://www.google.com')
            time.sleep(2)

            # Action 2: PAGE_LOAD
            print('[ACTION] Loading page: https://www.google.com/?zx=1766612482207&no_sw_cr=1')
            self.driver.get('https://www.google.com/?zx=1766612482207&no_sw_cr=1')
            time.sleep(2)

            # Action 3: PAGE_LOAD
            print('[ACTION] Loading page: https://www.emol.com/')
            self.driver.get('https://www.emol.com/')
            time.sleep(2)

            # Action 4: CLICK
            print('[ACTION] Click on: CERRAR [X]')
            element = self.find_element(r"""//*[@id='div_itt']/div[1]/div[1]""")
            if element:
                self.driver.execute_script('arguments[0].scrollIntoView(true);', element)
                time.sleep(0.5)
                element.click()
                time.sleep(0.5)

            # Action 5: PAGE_LOAD
            print('[ACTION] Loading page: https://www.emol.com/noticias/Economia/2025/12/24/1186777/empresarios-rechazan-negociacion-ramal.html')
            self.driver.get('https://www.emol.com/noticias/Economia/2025/12/24/1186777/empresarios-rechazan-negociacion-ramal.html')
            time.sleep(2)

            # Action 6: PAGE_LOAD
            print('[ACTION] Loading page: https://www.emol.com/noticias/Nacional/2025/12/14/1185707/nuevo-senado-congreso-miembros-partidos.html')
            self.driver.get('https://www.emol.com/noticias/Nacional/2025/12/14/1185707/nuevo-senado-congreso-miembros-partidos.html')
            time.sleep(2)

            
            print("[INFO] Automation completed successfully")
            
        except Exception as e:
            print(f"[ERROR] Error during execution: {e}")
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
