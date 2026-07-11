import sys
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions

def dump_table():
    try:
        options = ChromeOptions()
        options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
        driver = webdriver.Chrome(options=options)
        print("Connected to browser successfully!")
        print("Current URL:", driver.current_url)
        
        # Try both selectors
        print("\n--- Trying table#turbogrid tbody tr ---")
        rows = driver.find_elements(By.CSS_SELECTOR, "table#turbogrid tbody tr")
        print(f"Found {len(rows)} rows with CSS selector")
        for i, row in enumerate(rows):
            print(f"Row {i}: {repr(row.text)}")
            
        print("\n--- Trying //tbody/tr ---")
        rows_xpath = driver.find_elements(By.XPATH, "//tbody/tr")
        print(f"Found {len(rows_xpath)} rows with XPath")
        if len(rows_xpath) > 50:
            print("Showing first 15 and last 15 rows to avoid overflow:")
            for i in range(15):
                print(f"Row {i}: {repr(rows_xpath[i].text)}")
            for i in range(len(rows_xpath)-15, len(rows_xpath)):
                print(f"Row {i}: {repr(rows_xpath[i].text)}")
        else:
            for i, row in enumerate(rows_xpath):
                print(f"Row {i}: {repr(row.text)}")
                
    except Exception as e:
        print("Error connecting or parsing:", e)

if __name__ == "__main__":
    dump_table()
