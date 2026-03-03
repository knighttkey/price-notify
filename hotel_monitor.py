import os
import sys
import time
import requests
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# ===================== [配置讀取區] =====================
def load_config():
    """載入本地 config.json 或使用預設值"""
def load_config():
    default_config = {
        "CHECK_IN": "2026-03-14",
        "CHECK_OUT": "2026-03-15",
        "MAX_PRICE": 3000,
        "MIN_RATING": 3.5,
        "HOTELS_TO_WATCH": [
            "大林成都旅社", "仁義湖岸大酒店", "仁義潭溫馨民宿", "嘉義市 偶然行旅",
            "島宇居行藝文旅", "嘉義 慢漫民宿", "ML Hotel 晨光飯店", "碰碰諸羅山",
            "嘉宮旅社", "永悅商務大飯店", "Summertime Inn 夏天旅宿", "卓家小苑"
        ],
        "BLACKLIST": [
            "金龍海悅飯店", "仲青行旅嘉義館", "LIGHT HOSTEL", "風箏旅人旅社"
        ],
        "STOP_DATE": "2026-03-12",
        "LINE_TOKEN": "",
        "LINE_USER_ID": ""
    }
    try:
        if os.path.exists("config.json"):
            with open("config.json", "r", encoding="utf-8") as f:
                user_config = json.load(f)
                default_config.update(user_config)
        
        # 本地端可選擇從 secrets.json 讀取 (不建議上傳到 Git)
        if os.path.exists("secrets.json"):
            with open("secrets.json", "r", encoding="utf-8") as f:
                secrets = json.load(f)
                if "CHANNEL_ACCESS_TOKEN" in secrets:
                    default_config["LINE_TOKEN"] = secrets["CHANNEL_ACCESS_TOKEN"]
                if "USER_ID" in secrets:
                    default_config["LINE_USER_ID"] = secrets["USER_ID"]
    except Exception as e:
        print(f"載入配置失敗: {e}, 將使用預設配置。")
    return default_config

config = load_config()

# LINE 配置 (優先讀取 GitHub Secrets 環境變數，次之讀取本地配置)
CHANNEL_ACCESS_TOKEN = os.environ.get("CHANNEL_ACCESS_TOKEN") or config.get("LINE_TOKEN", "")
USER_ID = os.environ.get("USER_ID") or config.get("LINE_USER_ID", "")

if not CHANNEL_ACCESS_TOKEN or not USER_ID:
    print("通知：未偵測到 LINE 配置 (預期為環境變數或 secrets.json)，發送通知功能將受限。")

# 將 config 內容解構成變數
CHECK_IN = config["CHECK_IN"]
CHECK_OUT = config["CHECK_OUT"]
MAX_PRICE = config["MAX_PRICE"]
MIN_RATING = config["MIN_RATING"]
HOTELS_TO_WATCH = config["HOTELS_TO_WATCH"]
BLACKLIST = config["BLACKLIST"]
STOP_DATE = config["STOP_DATE"]

def send_line_push(text):
    """發送 LINE Push Message (移除表情符號以符合規範)"""
    if not CHANNEL_ACCESS_TOKEN or not USER_ID:
        return
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"
    }
    payload = {
        "to": USER_ID,
        "messages": [
            {
                "type": "text",
                "text": text
            }
        ]
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
    except Exception as e:
        print(f"發送 LINE 訊息失敗: {e}")

def get_google_rating(driver, hotel_name):
    """回頭向 Google Maps 驗證評分"""
    try:
        search_url = f"https://www.google.com/search?q={hotel_name}+評分"
        driver.get(search_url)
        time.sleep(2)
        # 尋找包含星等的元素
        rating_elem = driver.find_element(By.CSS_SELECTOR, "[aria-label*='星'], [aria-label*='star']")
        rating_text = rating_elem.get_attribute("aria-label")
        import re
        match = re.search(r"(\d+\.?\d*)", rating_text)
        return float(match.group(1)) if match else 0.0
    except:
        return 0.0

def get_hotel_data():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(service=webdriver.chrome.service.Service(ChromeDriverManager().install()), options=chrome_options)
    
    found_hotels = []
    current_state_keys = set()
    processed_names = set()

    try:
        # 1. 來源甲：Google Travel (廣度與指定搜尋)
        search_queries = [
            f"嘉義 飯店 住宿 {CHECK_IN} {CHECK_OUT}",
            f"嘉義 民宿 住宿 {CHECK_IN} {CHECK_OUT}"
        ]
        for hotel in HOTELS_TO_WATCH:
            search_queries.append(f"{hotel} {CHECK_IN} {CHECK_OUT}")

        for query in search_queries:
            target_url = f"https://www.google.com/travel/search?q={query}"
            driver.get(target_url)
            time.sleep(4)
            
            items = driver.find_elements(By.CSS_SELECTOR, "div[role='listitem']")
            if not items:
                try:
                    single_name_elem = driver.find_element(By.CSS_SELECTOR, "h1, h2, [role='heading'][aria-level='1']")
                    if any(target in single_name_elem.text for target in HOTELS_TO_WATCH):
                        items = [driver.find_element(By.TAG_NAME, "body")]
                except: pass

            for item in items:
                try:
                    name = ""
                    for selector in ["h2", "h3", "[role='heading']", ".W8db6c"]:
                        try:
                            name = item.find_element(By.CSS_SELECTOR, selector).text
                            if name: break
                        except: continue
                    
                    if not name or name in processed_names: continue
                    if any(b in name for b in BLACKLIST): continue

                    # 抓取價格與來源
                    price_val = 0
                    source = "Google"
                    price_candidates = item.find_elements(By.CSS_SELECTOR, "span[aria-label*='元'], span[aria-label*='NT$'], .MJ69ic")
                    if not price_candidates:
                        price_candidates = item.find_elements(By.XPATH, ".//*[contains(text(), '$') or contains(text(), '元')]")

                    for pc in price_candidates:
                        label = pc.get_attribute("aria-label") or pc.text or ""
                        try:
                            digits = ''.join(filter(str.isdigit, pc.text))
                            if not digits: continue
                            price_val = int(digits)
                            if "Agoda" in label: source = "Agoda"
                            elif "Booking" in label or "繽客" in label: source = "Booking.com"
                            elif "Trip.com" in label: source = "Trip.com"
                            if price_val > 0: break
                        except: continue

                    if price_val == 0: continue

                    # 抓取評分
                    rating_val = 0.0
                    try:
                        rating_elem = item.find_element(By.CSS_SELECTOR, "[aria-label*='星'], [aria-label*='star']")
                        import re
                        match = re.search(r"(\d+\.?\d*)", rating_elem.get_attribute("aria-label"))
                        rating_val = float(match.group(1)) if match else 0.0
                    except:
                        pass # If not found, will be verified below

                    # 評分驗證
                    if rating_val < MIN_RATING: # If rating is low or missing, verify with Google Maps
                        verified_rating = get_google_rating(driver, name)
                        if verified_rating > rating_val: # Use the higher rating if verified
                            rating_val = verified_rating

                    is_in_list = any(target in name for target in HOTELS_TO_WATCH)
                    is_recommended = (price_val <= MAX_PRICE and rating_val >= MIN_RATING)
                    
                    if (is_in_list or is_recommended) and price_val > 0:
                        found_hotels.append({
                            "name": name, "price": price_val, "rating": rating_val,
                            "source": source, "url": target_url
                        })
                        current_state_keys.add(f"{name}-{price_val}")
                        processed_names.add(name)
                except Exception as item_e:
                    print(f"處理 Google Travel 項目時發生錯誤: {item_e}")
                    continue
    except Exception as e:
        print(f"Google Travel 抓取發生錯誤: {e}")

    # 2. 來源乙：Agoda 直接搜尋 (透過 Google Search 快速摘要抓取)
    try:
        for hotel in HOTELS_TO_WATCH: # 針對所有關注的飯店
            search_url = f"https://www.google.com/search?q={hotel}+Agoda+價格"
            driver.get(search_url)
            time.sleep(3)
            try:
                # 尋找搜尋結果中的 Agoda 價格標籤
                # 嘗試尋找包含 "Agoda" 和價格的元素
                price_box = driver.find_element(By.XPATH, "//*[contains(text(), 'Agoda')]/ancestor::div[contains(@class, 'g')]//span[contains(text(), '$') or contains(text(), '元')]")
                price_text = price_box.text
                digits = ''.join(filter(str.isdigit, price_text))
                if digits:
                    price_val = int(digits)
                    if price_val > 0 and hotel not in processed_names:
                        rating_val = get_google_rating(driver, hotel)
                        if rating_val >= MIN_RATING or hotel in HOTELS_TO_WATCH:
                            found_hotels.append({
                                "name": hotel, "price": price_val, "rating": rating_val,
                                "source": "Agoda", "url": search_url # URL to Google search result
                            })
                            current_state_keys.add(f"{hotel}-{price_val}")
                            processed_names.add(hotel)
            except: 
                # print(f"未在 Google Search 中找到 {hotel} 的 Agoda 價格。")
                pass
    except Exception as e:
        print(f"Agoda 抓取發生錯誤: {e}")

    # 3. 來源丙：Booking.com 直接搜尋 (透過 Google Search 快速摘要抓取)
    try:
        for hotel in HOTELS_TO_WATCH: # 針對所有關注的飯店
            search_url = f"https://www.google.com/search?q={hotel}+Booking.com+價格"
            driver.get(search_url)
            time.sleep(3)
            try:
                # 尋找搜尋結果中的 Booking.com 價格標籤
                # 嘗試尋找包含 "Booking.com" 和價格的元素
                price_box = driver.find_element(By.XPATH, "//*[contains(text(), 'Booking.com') or contains(text(), '繽客')]/ancestor::div[contains(@class, 'g')]//span[contains(text(), '$') or contains(text(), '元')]")
                price_text = price_box.text
                digits = ''.join(filter(str.isdigit, price_text))
                if digits:
                    price_val = int(digits)
                    if price_val > 0 and hotel not in processed_names:
                        rating_val = get_google_rating(driver, hotel)
                        if rating_val >= MIN_RATING or hotel in HOTELS_TO_WATCH:
                            found_hotels.append({
                                "name": hotel, "price": price_val, "rating": rating_val,
                                "source": "Booking.com", "url": search_url # URL to Google search result
                            })
                            current_state_keys.add(f"{hotel}-{price_val}")
                            processed_names.add(hotel)
            except: 
                # print(f"未在 Google Search 中找到 {hotel} 的 Booking.com 價格。")
                pass
    except Exception as e:
        print(f"Booking.com 抓取發生錯誤: {e}")

    finally:
        driver.quit()
    
    return found_hotels, current_state_keys

def load_state():
    if os.path.exists("last_state.txt"):
        with open("last_state.txt", "r", encoding="utf-8") as f:
            return set(f.read().splitlines())
    return set()

def save_state(keys):
    with open("last_state.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(keys))

from datetime import datetime, timezone, timedelta

def save_results_to_json(hotels):
    """將掃描結果存入 results.json 供網頁前端讀取"""
    # GitHub Actions 伺服器預設為 UTC 時間，在此強制轉換為台灣時間 (UTC+8)
    tz_tw = timezone(timedelta(hours=8))
    tw_time_str = datetime.now(tz_tw).strftime("%Y-%m-%d %H:%M:%S")

    data = {
        "last_updated": tw_time_str,
        "hotels": hotels
    }
    with open("results.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def main():
    current_date = time.strftime("%Y-%m-%d")
    if current_date >= STOP_DATE:
        print(f"目前日期 {current_date} 已達到終止日期 {STOP_DATE}，停止運作。")
        return

    print(f"開始執行巡邏 (日期: {CHECK_IN}, 預算上限: ${MAX_PRICE})...")
    
    hotels, current_keys = get_hotel_data()
    last_state = load_state()
    
    # 儲存到 JSON (供網頁顯示)
    save_results_to_json(hotels)
    
    new_items = current_keys - last_state
    
    if new_items:
        # 組合 LINE 訊息
        msg_list = []
        for h in hotels:
            msg_list.append(f"{h['name']}\n價格: ${h['price']}\n評分: {h['rating']}\n連結: {h['url']}")
        
        content = "\n\n".join(msg_list)
        msg = f"[發現房源更新]\n日期：{CHECK_IN}\n\n{content}"
        send_line_push(msg)
        save_state(current_keys)
        print("偵測到變動，已發送 LINE 通知。")
    else:
        print("狀態無變化，不發送通知。")

if __name__ == "__main__":
    main()
