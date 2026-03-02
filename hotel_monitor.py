import time
import requests
import sys
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

import os

# ===================== [配置設定區] =====================
# 1. 填入你的 LINE Messaging API Token (雲端環境會優先讀取 Secrets)
CHANNEL_ACCESS_TOKEN = os.environ.get("CHANNEL_ACCESS_TOKEN", "Z7b6eHG+MkPJoltJzYTSzecXQF+BtY2P+m4A2e+t+gyeTd8zg0gx3mGgS9zVyyCi9fAgZ1qsD6Tu4wRSwnotOJUpMBqdUFYFprCnpjp/cOkHuYVwKlXPqscCS3Zzy7jxjDD8Zx4+wNR0pSMkbqf9dAdB04t89/1O/w1cDnyilFU=")

# 2. 你的 User ID (雲端環境會優先讀取 Secrets)
USER_ID = os.environ.get("USER_ID", "Ub8fb29414d2f8e05b6a79ffbd872384c")

# 3. 搜尋條件 (符合以下條件即推薦)
CHECK_IN = "2026-03-14"
CHECK_OUT = "2026-03-15"
MAX_PRICE = 2800    # 預算
MIN_RATING = 3.5    # 最低評分門檻 (調整為 3.5)

# 4. 指定監控飯店清單 (只要有房就通知，不受上面評分限制)
HOTELS_TO_WATCH = [
    "嘉義智選假日酒店", "耐斯王子大飯店", "兆品酒店嘉義", "嘉義亮點旅店",
    "承億文旅嘉義商旅", "承億文旅桃城茶樣子", "蘭桂坊花園酒店", "天成文旅-繪日之丘",
    "嘉義大雅旅店", "嘉義皇品國際酒店", "嘉義觀止飯店",
    "葉綠宿・漫漫回嘉 Home Way Hotel 嘉義館"
]

# 5. 黑名單 (永久過濾，不論條件都不會出現在通知中)
BLACKLIST = [
    "金龍海悅飯店", "仲青行旅嘉義館", "LIGHT HOSTEL", "風箏旅人旅社"
]

# 6. 自動結束時間
STOP_DATE = "2026-03-12"

# 狀態追蹤
last_seen_state = set()
# =======================================================

def send_line_push(text):
    """透過 LINE Messaging API 發送推播訊息"""
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"
    }
    payload = {
        "to": USER_ID,
        "messages": [{"type": "text", "text": text}]
    }
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            print(f"LINE 通知發送失敗: {response.text}")
    except Exception as e:
        print(f"發送 LINE 時發生異常: {e}")

def get_hotel_data():
    """使用 Selenium 爬取 Google Hotels 彙整的價格資訊"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # 背景執行
    chrome_options.add_argument("--disable-dev-shm-usage") # 雲端環境必備
    chrome_options.add_argument("--remote-debugging-port=9222")

    # 偽裝 User-Agent 避免被擋
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    found_hotels = []
    current_state_keys = set()

    try:
        # 加入「雙人房」關鍵字以確保搜尋結果符合需求
        search_query = f"嘉義 雙人房 住宿 {CHECK_IN} {CHECK_OUT}"
        target_url = f"https://www.google.com/travel/search?q={search_query}"
        
        driver.get(target_url)
        time.sleep(12)  # 等待動態價格載入完成

        # 抓取飯店列表項目
        items = driver.find_elements(By.CSS_SELECTOR, "div[role='listitem']")
        
        for item in items:
            try:
                name = item.find_element(By.TAG_NAME, "h2").text
                
                # 抓取價格
                price_element = item.find_element(By.CSS_SELECTOR, "span[aria-label*='元']")
                price_val = int(''.join(filter(str.isdigit, price_element.text)))

                # 抓取評分 (通常在包含「顆星」的標籤中)
                try:
                    rating_element = item.find_element(By.CSS_SELECTOR, "span[aria-label*='顆星']")
                    rating_text = rating_element.get_attribute("aria-label")
                    rating_val = float(rating_text.split(" ")[0])
                except:
                    rating_val = 0.0 # 若抓不到評分則預設為 0

                # 判定邏輯：
                # 0. 先檢查是否在黑名單
                if any(b in name for b in BLACKLIST):
                    continue

                # 1. 在監控清單內 (不管評分)
                # 2. 符合預算且評分達標
                is_in_list = any(target in name for target in HOTELS_TO_WATCH)
                is_recommended = (price_val <= MAX_PRICE and rating_val >= MIN_RATING)
                
                if (is_in_list or is_recommended) and price_val > 0:
                    status_text = f"{name}\n價格: ${price_val}\n評分: {rating_val}"
                    found_hotels.append(status_text)
                    current_state_keys.add(f"{name}-{price_val}")
            except:
                continue

    except Exception as e:
        print(f"爬取過程發生錯誤: {e}")
    finally:
        driver.quit()
    
    return found_hotels, current_state_keys

def load_state():
    """從檔案讀取上次掃描的狀態"""
    if os.path.exists("last_state.txt"):
        with open("last_state.txt", "r", encoding="utf-8") as f:
            return set(f.read().splitlines())
    return set()

def save_state(keys):
    """將目前狀態存入檔案"""
    with open("last_state.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(keys))

def main():
    # 檢查是否已過終止日期
    current_date = time.strftime("%Y-%m-%d")
    if current_date >= STOP_DATE:
        print(f"目前日期 {current_date} 已達到終止日期 {STOP_DATE}，停止運作。")
        return

    print(f"開始掃描空房狀態 (日期: {CHECK_IN}, 預算: ${MAX_PRICE})...")
    
    hotels, current_keys = get_hotel_data()
    last_state = load_state()
    
    # 流量檢查：比對是否有「新」的變動
    new_items = current_keys - last_state
    
    if new_items:
        content = "\n\n".join(hotels)
        msg = f"【發現空房變動！】\n日期：{CHECK_IN}\n\n{content}\n\n請前往 Google Hotels 確認！"
        send_line_push(msg)
        save_state(current_keys)
        print("偵測到變動，已發送 LINE 通知並更新狀態。")
    else:
        print("目前狀態無變化，不發送通知 (節省 LINE 額度)。")

if __name__ == "__main__":
    main()
