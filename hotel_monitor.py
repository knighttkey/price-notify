import os
import sys

# 強制抑制所有警告，包含 urllib3 的 SSL 警告
os.environ['PYTHONWARNINGS'] = 'ignore'
import warnings
warnings.filterwarnings("ignore")

import time
import requests
import json
import re
from datetime import datetime, timezone, timedelta
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
        search_queries = [
            f"嘉義 飯店 住宿 {CHECK_IN} {CHECK_OUT}",
            f"嘉義 民宿 住宿 {CHECK_IN} {CHECK_OUT}"
        ]
        for hotel in HOTELS_TO_WATCH:
            search_queries.append(f"{hotel} {CHECK_IN} {CHECK_OUT}")

        for query in search_queries:
            target_url = f"https://www.google.com/travel/search?q={query}"
            driver.get(target_url)
            time.sleep(6) # 穩定載入
            
            # --- 策略 A: 標準 DOM 解析 ---
            items = driver.find_elements(By.CSS_SELECTOR, "div[role='listitem']")
            if not items:
                try:
                    # 處理單一飯店導覽頁
                    name_elem = driver.find_element(By.CSS_SELECTOR, "h1, h2")
                    if name_elem: items = [driver.find_element(By.TAG_NAME, "body")]
                except: pass

            for item in items:
                try:
                    name = ""
                    for s in ["h2", "h3", "[role='heading']", ".W8db6c", ".P83p7e"]:
                        try:
                            name = item.find_element(By.CSS_SELECTOR, s).text
                            if name: break
                        except: continue
                    
                    if not name or name in processed_names: continue
                    if any(b in name for b in BLACKLIST): continue

                    # 抓取價格與來源
                    price_elements = item.find_elements(By.CSS_SELECTOR, "span[aria-label*='元'], span[aria-label*='NT$'], .MJ69ic, .U986S")
                    
                    # 抓取評分
                    rating_val = 0.0
                    try:
                        rating_elem = item.find_element(By.CSS_SELECTOR, "[aria-label*='星'], [aria-label*='star']")
                        r_match = re.search(r"(\d+\.?\d*)", rating_elem.get_attribute("aria-label"))
                        rating_val = float(r_match.group(1)) if r_match else 0.0
                    except: pass

                    found_any_for_this = False
                    for pe in price_elements:
                        label = pe.get_attribute("aria-label") or ""
                        try:
                            digits = ''.join(filter(str.isdigit, pe.text))
                            if not digits: continue
                            val = int(digits)
                            src = "Google"
                            if "Agoda" in label: src = "Agoda"
                            elif "Booking" in label or "繽客" in label: src = "Booking.com"
                            elif "Trip.com" in label: src = "Trip.com"
                            
                            is_watch = any(t in name for t in HOTELS_TO_WATCH)
                            is_rec = (val <= MAX_PRICE and rating_val >= MIN_RATING)
                            
                            if is_watch or is_rec:
                                found_hotels.append({
                                    "name": name, "price": val, "rating": rating_val,
                                    "source": src, "url": target_url
                                })
                                current_state_keys.add(f"{name}-{src}-{val}")
                                found_any_for_this = True
                        except: continue
                    
                    if found_any_for_this: processed_names.add(name)
                except: continue

            # --- 策略 B: 深度源碼 Regex 解析 (二次保險) ---
            page_content = driver.page_source
            for target in HOTELS_TO_WATCH:
                if target not in processed_names and target in page_content:
                    try:
                        # 尋找 飯店名稱 ... $2,267 這種結構 (排除 HTML 標籤)
                        # 改進 Regex 偵測，允許更多字元並正確處理逗號
                        match = re.search(re.escape(target) + r".{0,3000}?(?:\$|NT\$|元)\s?(\d{1,3}(?:,\d{3})*)", page_content, re.DOTALL)
                        if match:
                            price_str = match.group(2).replace(",", "")
                            price_val = int(price_str)
                            if 500 < price_val < 10000: # 合理價格區間過濾，防止抓到編號
                                rating = get_google_rating(driver, target)
                                found_hotels.append({
                                    "name": target, "price": price_val, "rating": rating,
                                    "source": "Agoda/Booking", "url": target_url
                                })
                                current_state_keys.add(f"{target}-Auto-{price_val}")
                                processed_names.add(target)
                    except Exception as re_e:
                        pass

    except Exception as e:
        print(f"資料抓取發生錯誤: {e}")

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
