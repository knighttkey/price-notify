import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

def debug_travel_page(hotel_name, check_in, check_out):
    print(f"--- Debugging Google Travel: {hotel_name} ---")
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(service=webdriver.chrome.service.Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        query = f"{hotel_name} {check_in} {check_out}"
        url = f"https://www.google.com/travel/search?q={query}"
        print(f"URL: {url}")
        driver.get(url)
        time.sleep(8) # 加長等待時間
        
        # 1. 儲存 HTML
        filename = f"debug_travel_{hotel_name}.html"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print(f"Saved {filename}")

        # 2. 尋找列表項
        items = driver.find_elements(By.CSS_SELECTOR, "div[role='listitem']")
        print(f"Found {len(items)} list items.")
        
        # 如果沒找到，嘗試尋找飯店標題
        if not items:
            headings = driver.find_elements(By.CSS_SELECTOR, "h1, h2, h3")
            print(f"Found {len(headings)} headings.")
            for h in headings[:10]:
                print(f"Heading: {h.text}")

        # 3. 尋找所有包含金額的元素
        prices = driver.find_elements(By.XPATH, "//*[contains(text(), '$') or contains(text(), '元')]")
        print(f"Found {len(prices)} price-like elements.")
        for p in prices[:10]:
            print(f"Price Element Text: {p.text}, Class: {p.get_attribute('class')}, Label: {p.get_attribute('aria-label')}")

    finally:
        driver.quit()

if __name__ == "__main__":
    debug_travel_page("卓家小苑", "2026-03-14", "2026-03-15")
