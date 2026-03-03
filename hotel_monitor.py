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
    default_config = {
        "CHECK_IN": "2026-03-14",
        "CHECK_OUT": "2026-03-15",
        "MAX_PRICE": 3000,
        "MIN_RATING": 3.5,
        "HOTELS_TO_WATCH": [
            "大林成都旅社", "仁義湖岸大酒店", "仁義潭溫馨民宿", "嘉義市 偶然行旅",
            "島宇居行藝文旅", "嘉義 慢漫民宿", "ML Hotel 晨光飯店", "碰碰諸羅山",
            "嘉宮旅社", "永悅商務大飯店", "Summertime Inn 夏天旅宿"
        ],
        "BLACKLIST": [
            "金龍海悅飯店", "仲青行旅嘉義館", "LIGHT HOSTEL", "風箏旅人旅社"
        ],
        "STOP_DATE": "2026-03-12"
    }
    try:
        if os.path.exists("config.json"):
            with open("config.json", "r", encoding="utf-8") as f:
                user_config = json.load(f)
                default_config.update(user_config)
    except Exception as e:
        print(f"載入 config.json 失敗: {e}, 將使用預設配置。")
    return default_config

config = load_config()

# LINE 配置 (從 GitHub Secrets 讀取)
CHANNEL_ACCESS_TOKEN = os.environ.get("CHANNEL_ACCESS_TOKEN", "")
USER_ID = os.environ.get("USER_ID", "")

if not CHANNEL_ACCESS_TOKEN or not USER_ID:
    print("警告：未偵測到 LINE 配置 (CHANNEL_ACCESS_TOKEN 或 USER_ID)，將無法發送通知。")

# 將 config 內容解構成變數
CHECK_IN = config["CHECK_IN"]
CHECK_OUT = config["CHECK_OUT"]
MAX_PRICE = config["MAX_PRICE"]
MIN_RATING = config["MIN_RATING"]
HOTELS_TO_WATCH = config["HOTELS_TO_WATCH"]
BLACKLIST = config["BLACKLIST"]
STOP_DATE = config["STOP_DATE"]

def send_line_push(text):
    """發送 LINE Push Message"""
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

def get_hotel_data():
    """使用 Selenium 爬取 Google Hotels 彙整的價格與連結"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--remote-debugging-port=9222")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(service=webdriver.chrome.service.Service(ChromeDriverManager().install()), options=chrome_options)
    
    found_hotels = []
    current_state_keys = set()
    processed_names = set()

    # 定義要搜尋的所有關鍵字 (一個泛用 + 所有指定名單)
    search_queries = [f"嘉義 雙人房 住宿 {CHECK_IN} {CHECK_OUT}"]
    for hotel in HOTELS_TO_WATCH:
        search_queries.append(f"{hotel} 雙人房 {CHECK_IN} {CHECK_OUT}")

    try:
        for query in search_queries:
            target_url = f"https://www.google.com/travel/search?q={query}"
            driver.get(target_url)
            time.sleep(4) # 等待 JavaScript 載入
            
            items = driver.find_elements(By.CSS_SELECTOR, "div[role='listitem']")
            
            # 針對特定飯店搜尋，可能直接跳轉到該飯店的專屬頁面而非列表
            # 這裡我們只抓取列表呈現的資料，如果 Google 自動跳轉單一飯店頁面，
            # 可以擷取 h1 作為飯店名稱，並找價格。為了簡化與穩定，我們嘗試統一用 listitem 抓取。
            # 大部分情況給定日期還是會出現在列表第一項。
            
            for item in items:
                try:
                    name = item.find_element(By.TAG_NAME, "h2").text
                    if not name or name in processed_names:
                        continue
                        
                    # 0. 黑名單過濾
                    if any(b in name for b in BLACKLIST):
                        continue

                    # 1. 抓取價格
                    price_element = item.find_element(By.CSS_SELECTOR, "span[aria-label*='元']")
                    price_val = int(''.join(filter(str.isdigit, price_element.text)))

                    # 2. 抓取評分
                    try:
                        rating_element = item.find_element(By.CSS_SELECTOR, "span[aria-label*='顆星']")
                        rating_val = float(rating_element.get_attribute("aria-label").split(" ")[0])
                    except:
                        rating_val = 0.0

                    # 3. 抓取跳轉網址
                    try:
                        link_element = item.find_element(By.TAG_NAME, "a")
                        hotel_url = link_element.get_attribute("href")
                    except:
                        hotel_url = target_url 

                    # 判定邏輯
                    is_in_list = any(target in name for target in HOTELS_TO_WATCH)
                    is_recommended = (price_val <= MAX_PRICE and rating_val >= MIN_RATING)
                    
                    if (is_in_list or is_recommended) and price_val > 0:
                        hotel_data = {
                            "name": name,
                            "price": price_val,
                            "rating": rating_val,
                            "url": hotel_url
                        }
                        found_hotels.append(hotel_data)
                        current_state_keys.add(f"{name}-{price_val}")
                        processed_names.add(name)
                except Exception as e:
                    continue
    except Exception as e:
        print(f"爬蟲發生錯誤: {e}")
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
