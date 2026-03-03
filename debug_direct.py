import os
import time
import json
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

def debug_direct_search(hotel_name, check_in, check_out):
    print(f"--- Debugging: {hotel_name} ---")
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(service=webdriver.chrome.service.Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        # 測試 1: Google Search 直接搜尋房價 (Agoda)
        search_url = f"https://www.google.com/search?q={hotel_name}+Agoda+價格"
        print(f"Testing URL: {search_url}")
        driver.get(search_url)
        time.sleep(5)
        
        with open(f"debug_{hotel_name}_search.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        
        # 尋找所有包含金額的內容
        text_content = driver.find_element(By.TAG_NAME, "body").text
        prices = re.findall(r"[\$NT]?\s?\d{1,3}(?:,\d{3})*", text_content)
        print(f"Found price-like strings in body: {prices[:10]}")

        # 嘗試尋找 Agoda 相關區塊
        agoda_elements = driver.find_elements(By.XPATH, "//*[contains(text(), 'Agoda')]")
        print(f"Found {len(agoda_elements)} elements containing 'Agoda'")
        
        for i, elem in enumerate(agoda_elements[:5]):
            try:
                parent = elem.find_element(By.XPATH, "./..")
                print(f"Agoda Elem {i} Parent Text: {parent.text[:100]}")
            except: pass

    finally:
        driver.quit()

if __name__ == "__main__":
    debug_direct_search("卓家小苑", "2026-03-14", "2026-03-15")
