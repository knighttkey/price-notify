import time
import subprocess
import schedule
from datetime import datetime

def run_monitor():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 啟動本地定時巡邏...")
    try:
        # 使用本地虛擬環境執行
        result = subprocess.run(["/Users/kexy/MyLab/python-scripts/.venv/bin/python", "hotel_monitor.py"], 
                              capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print(f"錯誤輸出: {result.stderr}")
    except Exception as e:
        print(f"執行失敗: {e}")

# 設定在每小時的第 30 分鐘執行 (例如 09:30, 10:30...)
schedule.every().hour.at(":30").do(run_monitor)

print("本地監控服務已啟動。")
print("目前設定：每小時的 30 分執行一次 (與雲端整點錯開)。")
print("按下 Ctrl+C 可停止服務。")

# 啟動時先執行一次，確保存放初始資料
run_monitor()

while True:
    schedule.run_pending()
    time.sleep(60)
