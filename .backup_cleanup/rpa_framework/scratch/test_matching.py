import sys
import os
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions

def test_matching():
    try:
        options = ChromeOptions()
        options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
        driver = webdriver.Chrome(options=options)
        
        rows = driver.find_elements(By.XPATH, "//tbody/tr")
        print(f"Total rows: {len(rows)}")
        
        # Test original matching logic on all rows
        for i, row in enumerate(rows):
            try:
                txt_to_search = ""
                cells = row.find_elements(By.TAG_NAME, "td")
                
                if len(cells) >= 2:
                    txt_to_search = cells[1].text.strip()
                    method = f"cells[1] (len={len(cells)})"
                else:
                    txt_to_search = row.text.strip()
                    method = "row.text"
                
                if not txt_to_search:
                    continue
                    
                match = re.search(r'(\d{6,})\s*/\s*[^/]+', txt_to_search)
                if match:
                    print(f"Row {i} MATCHED using {method}!")
                    print(f"  Matched text snippet: {repr(txt_to_search[:100])}")
                    print(f"  Regex match: {repr(match.group(0))}")
                    print(f"  Group 2: {repr(match.group(2).strip())}")
            except Exception as e:
                print(f"Row {i} raised error: {e}")
                
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    test_matching()
