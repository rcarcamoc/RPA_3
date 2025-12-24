"""
Auto-generated Web Automation Script
Generated: 2025-12-24T18:40:16.938215
Total Actions: 15
Clicks: 3
Inputs: 8
Selects: 0
Duration: 00:34

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
            print('[ACTION] Loading page: https://www.google.com/?zx=1766612351302&no_sw_cr=1')
            self.driver.get('https://www.google.com/?zx=1766612351302&no_sw_cr=1')
            time.sleep(2)

            # Action 3: CLICK
            print('[ACTION] Click on: ')
            element = self.find_element(r"""//*[@id='APjFqb']""")
            if element:
                self.driver.execute_script('arguments[0].scrollIntoView(true);', element)
                time.sleep(0.5)
                element.click()
                time.sleep(0.5)

            # Action 4: INPUT
            print('[ACTION] Typing text')
            element = self.find_element(r"""//*[@id='APjFqb']""")
            if element:
                element.clear()
                element.send_keys(r'g')
                time.sleep(0.3)

            # Action 5: INPUT
            print('[ACTION] Typing text')
            element = self.find_element(r"""//*[@id='APjFqb']""")
            if element:
                element.clear()
                element.send_keys(r'ga')
                time.sleep(0.3)

            # Action 6: INPUT
            print('[ACTION] Typing text')
            element = self.find_element(r"""//*[@id='APjFqb']""")
            if element:
                element.clear()
                element.send_keys(r'gat')
                time.sleep(0.3)

            # Action 7: INPUT
            print('[ACTION] Typing text')
            element = self.find_element(r"""//*[@id='APjFqb']""")
            if element:
                element.clear()
                element.send_keys(r'gato')
                time.sleep(0.3)

            # Action 8: INPUT
            print('[ACTION] Typing text')
            element = self.find_element(r"""//*[@id='APjFqb']""")
            if element:
                element.clear()
                element.send_keys(r'gato ')
                time.sleep(0.3)

            # Action 9: INPUT
            print('[ACTION] Typing text')
            element = self.find_element(r"""//*[@id='APjFqb']""")
            if element:
                element.clear()
                element.send_keys(r'gato u')
                time.sleep(0.3)

            # Action 10: INPUT
            print('[ACTION] Typing text')
            element = self.find_element(r"""//*[@id='APjFqb']""")
            if element:
                element.clear()
                element.send_keys(r'gato ui')
                time.sleep(0.3)

            # Action 11: INPUT
            print('[ACTION] Typing text')
            element = self.find_element(r"""//*[@id='APjFqb']""")
            if element:
                element.clear()
                element.send_keys(r'gato uia')
                time.sleep(0.3)

            # Action 12: PAGE_LOAD
            print('[ACTION] Loading page: https://www.google.com/search?q=gato+uia&sca_esv=f34f7d9e35b45ae5&source=hp&ei=f11MaeA88drWxA_Ah7fADg&iflsig=AOw8s4IAAAAAaUxrj5MQ1YEqCefkssu_6j1h41jFL1vB&ved=0ahUKEwig-Iztl9eRAxVxrZUCHcDDDegQ4dUDCBQ&uact=5&oq=gato+uia&gs_lp=Egdnd3Mtd2l6IghnYXRvIHVpYTIFEAAYgAQyCRAAGIAEGAoYCzIJEAAYgAQYChgLMgkQABiABBgKGAsyCRAAGIAEGAoYCzIFEAAYgAQyBRAAGIAEMgUQABiABDIJEAAYgAQYChgLMgkQABiABBgKGAtI0SFQmwlYjBtwAXgAkAEAmAEqoAGbAqoBATi4AQPIAQD4AQGYAgmgAsMCqAIKwgIKEAAYAxjqAhiPAcICChAuGAMY6gIYjwHCAgsQABiABBixAxiDAcICERAuGIAEGLEDGNEDGIMBGMcBwgIIEAAYgAQYsQPCAg4QLhiABBixAxiDARiKBcICCBAuGIAEGLEDwgILEC4YgAQYsQMYgwHCAg4QLhiABBixAxjRAxjHAcICBBAAGAPCAg4QABiABBixAxiDARiKBcICCxAuGIAEGNEDGMcBwgIFEC4YgASYAwnxBUfhMIp8RAEVkgcBOaAH5mOyBwE4uAe5AsIHBzAuNi4yLjHIBxyACAA&sclient=gws-wiz&sei=nl1Mafkg98_WxA-t0e_4DA')
            self.driver.get('https://www.google.com/search?q=gato+uia&sca_esv=f34f7d9e35b45ae5&source=hp&ei=f11MaeA88drWxA_Ah7fADg&iflsig=AOw8s4IAAAAAaUxrj5MQ1YEqCefkssu_6j1h41jFL1vB&ved=0ahUKEwig-Iztl9eRAxVxrZUCHcDDDegQ4dUDCBQ&uact=5&oq=gato+uia&gs_lp=Egdnd3Mtd2l6IghnYXRvIHVpYTIFEAAYgAQyCRAAGIAEGAoYCzIJEAAYgAQYChgLMgkQABiABBgKGAsyCRAAGIAEGAoYCzIFEAAYgAQyBRAAGIAEMgUQABiABDIJEAAYgAQYChgLMgkQABiABBgKGAtI0SFQmwlYjBtwAXgAkAEAmAEqoAGbAqoBATi4AQPIAQD4AQGYAgmgAsMCqAIKwgIKEAAYAxjqAhiPAcICChAuGAMY6gIYjwHCAgsQABiABBixAxiDAcICERAuGIAEGLEDGNEDGIMBGMcBwgIIEAAYgAQYsQPCAg4QLhiABBixAxiDARiKBcICCBAuGIAEGLEDwgILEC4YgAQYsQMYgwHCAg4QLhiABBixAxjRAxjHAcICBBAAGAPCAg4QABiABBixAxiDARiKBcICCxAuGIAEGNEDGMcBwgIFEC4YgASYAwnxBUfhMIp8RAEVkgcBOaAH5mOyBwE4uAe5AsIHBzAuNi4yLjHIBxyACAA&sclient=gws-wiz&sei=nl1Mafkg98_WxA-t0e_4DA')
            time.sleep(2)

            # Action 13: PAGE_LOAD
            print('[ACTION] Loading page: https://www.youtube.com/watch?v=IxX_QHay02M')
            self.driver.get('https://www.youtube.com/watch?v=IxX_QHay02M')
            time.sleep(2)

            # Action 14: CLICK
            print('[ACTION] Click on: Omitir')
            element = self.find_element(r"""//*[@id='skip-button:2']""")
            if element:
                self.driver.execute_script('arguments[0].scrollIntoView(true);', element)
                time.sleep(0.5)
                element.click()
                time.sleep(0.5)

            # Action 15: CLICK
            print('[ACTION] Click on: ')
            element = self.find_element(r"""//*[@id='movie_player']/div[1]/video[1]""")
            if element:
                self.driver.execute_script('arguments[0].scrollIntoView(true);', element)
                time.sleep(0.5)
                element.click()
                time.sleep(0.5)

            
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
