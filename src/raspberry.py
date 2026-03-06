import requests
import pandas as pd
import time
import os
from datetime import datetime

DEVICE_NAME = "RPi4-REST-v2"
BASE_URL = f"http://localhost:59880/api/v3/reading/device/name/{DEVICE_NAME}"
LIMIT = 1024  # tăng limit lên tối đa cho phép
OUTPUT_FILE = "pi_dataset_dynamic.csv"
INTERVAL = 60  # giây, mỗi 60s lấy dữ liệu mới

# Các metric động
dynamic_metrics = [
    'Temperature', 'CPUUsage', 'CPUFreq', 'ContextSwitches',
    'Interrupts', 'SoftInterrupts', 'MemUsed', 'MemFree',
    'LoadAvg1', 'LoadAvg5', 'LoadAvg15', 'ProcessCount', 'Uptime'
]

# Kích thước bin tính bằng giây (ví dụ 0.5 giây)
BIN_SIZE_SEC = 0.5

def get_all_readings():
    """Lấy tất cả readings từ API (dùng phân trang)"""
    all_readings = []
    offset = 0
    while True:
        params = {"limit": LIMIT, "offset": offset}
        try:
            resp = requests.get(BASE_URL, params=params)
            if resp.status_code != 200:
                print(f"Lỗi API: {resp.status_code}")
                return []
            data = resp.json()
            readings = data.get('readings', [])
            if not readings:
                break
            all_readings.extend(readings)
            offset += len(readings)
            if len(readings) < LIMIT:
                break
        except Exception as e:
            print(f"Lỗi khi gọi API: {e}")
            return []
    return all_readings

def process_readings_to_csv(readings):
    """Xử lý readings: pivot, forward fill và ghi file"""
    if not readings:
        return
    df = pd.DataFrame(readings)
    df = df[df['resourceName'].isin(dynamic_metrics)]
    if df.empty:
        return
    df['value'] = pd.to_numeric(df['value'])
    
    # Tạo time bin
    bin_ns = int(BIN_SIZE_SEC * 1e9)
    df['bin'] = (df['origin'] // bin_ns) * bin_ns
    
    # Pivot theo bin, lấy giá trị đầu tiên trong bin (có thể dùng mean nhưng first hợp lý hơn)
    df_pivot = df.pivot_table(index='bin', columns='resourceName', values='value', aggfunc='first').reset_index()
    df_pivot.columns.name = None
    df_pivot['datetime'] = pd.to_datetime(df_pivot['bin'] / 1_000_000_000, unit='s')
    
    # Sắp xếp theo bin
    df_pivot = df_pivot.sort_values('bin')
    
    # Forward fill để điền các ô thiếu (lấy giá trị từ dòng trước)
    df_pivot = df_pivot.ffill()
    
    # Sắp xếp lại cột
    cols = ['bin', 'datetime'] + [c for c in dynamic_metrics if c in df_pivot.columns]
    df_pivot = df_pivot[cols]
    
    # Ghi file (ghi đè)
    df_pivot.to_csv(OUTPUT_FILE, index=False)
    print(f"Đã ghi {len(df_pivot)} dòng vào {OUTPUT_FILE} (đã forward fill)")

def main():
    print(f"Bắt đầu tự động cập nhật dữ liệu mỗi {INTERVAL}s, lưu vào {OUTPUT_FILE} (bin size={BIN_SIZE_SEC}s)")
    while True:
        try:
            readings = get_all_readings()
            if readings:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Đã tải {len(readings)} readings.")
                process_readings_to_csv(readings)
            else:
                print("Không có dữ liệu.")
            time.sleep(INTERVAL)
        except KeyboardInterrupt:
            print("\nDừng theo yêu cầu.")
            break
        except Exception as e:
            print(f"Lỗi: {e}")
            time.sleep(INTERVAL)

if __name__ == "__main__":
    main()