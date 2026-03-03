import os
import time
import requests
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

def debug_one_hotel(hotel_name, check_in, check_out):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(service=webdriver.chrome.service.Service(ChromeDriverManager().install()), options=chrome_options)
    
    query = f"{hotel_name} {check_in} {check_out}"
    target_url = f"https://www.google.com/travel/search?q={query}"
    print(f"Searching: {target_url}")
    
    try:
        driver.get(target_url)
        time.sleep(5)
        
        print(f"Current URL after load: {driver.current_url}")
        
        # 1. 檢查是否存在列表項
        items = driver.find_elements(By.CSS_SELECTOR, "div[role='listitem']")
        print(f"Found {len(items)} list items.")
        
        for i, item in enumerate(items[:3]):
            try:
                name = item.find_element(By.TAG_NAME, "h2").text
                price_elements = item.find_elements(By.XPATH, ".//*[contains(text(), '$') or contains(text(), '元')]")
                prices = [p.text for p in price_elements if p.text]
                print(f"Item {i} Name: {name}, Prices: {prices}")
            except:
                print(f"Item {i} could not be parsed.")

        # 2. 如果沒找到列表，檢查是否是單一飯店頁面 (通常會有特定的 ID 或較大的標題)
        if not items:
            try:
                # 嘗試抓取頁面主要標題 (h1)
                title = driver.find_element(By.TAG_NAME, "h1").text
                print(f"Found Page Title (H1): {title}")
                # 尋找價格
                price_elements = driver.find_elements(By.XPATH, ".//*[contains(text(), '$') or contains(text(), '元')]")
                prices = [p.text for p in price_elements if p.text]
                print(f"Page Prices: {prices}")
            except:
                print("Could not find H1 title.")

        # 保存截圖 (如果有桌面環境，但我現在是終端機，所以跳過)
        # 但我可以保存 HTML 源碼片段來分析
        html_snippet = driver.page_source[:5000]
        with open("debug_page.html", "w") as f:
            f.write(driver.page_source)
        print("Saved full page source to debug_page.html")

    finally:
        driver.quit()

if __name__ == "__main__":
    debug_one_hotel("卓家小苑", "2026-03-14", "2026-03-15")
