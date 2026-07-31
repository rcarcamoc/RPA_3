import sys
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions

def inspect_cells():
    try:
        options = ChromeOptions()
        options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
        driver = webdriver.Chrome(options=options)
        
        rows = driver.find_elements(By.XPATH, "//tbody/tr")
        print(f"Total rows: {len(rows)}")
        
        for i, row in enumerate(rows):
            cells = row.find_elements(By.TAG_NAME, "td")
            # If it's a real data row, it will have cells containing numbers/folios
            if len(cells) > 0:
                text = row.text.strip()
                if "Validado" in text and "/" in text:
                    print(f"\n--- Row {i} (contains data) ---")
                    print(f"Row text: {repr(text)}")
                    print(f"Number of cells: {len(cells)}")
                    for j, cell in enumerate(cells):
                        print(f"  Cell {j}: {repr(cell.text)}")
                        
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    inspect_cells()
