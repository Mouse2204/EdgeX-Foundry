# 🚀 Raspberry Pi System Monitor with EdgeX Foundry

Dự án này triển khai hệ thống thu thập dữ liệu hiệu năng hệ thống từ Raspberry Pi (Client) về máy chủ Windows/WSL2 (Server) thông qua framework EdgeX Foundry. Dữ liệu được quản lý tập trung và tự động xuất ra định dạng CSV để phục vụ phân tích.

## 📌 Mục lục
- [Kiến trúc hệ thống](#kiến-trúc-hệ-thống)
- [Yêu cầu hệ thống](#yêu-cầu-hệ-thống)
- [Cài đặt môi trường](#cài-đặt-môi-trường)
- [Cấu hình mạng & Firewall](#cấu-hình-mạng--firewall)
- [Triển khai EdgeX](#triển-khai-edgex)
- [Định nghĩa Metadata (Device & Profile)](#định-nghĩa-metadata-device--profile)
- [Thu thập & Xuất dữ liệu](#thu-thập--xuất-dữ-liệu)

## 🏗 Kiến trúc hệ thống

Dự án sử dụng thiết kế **Metadata-Driven Ingestion**:

- **Edge Side (RPi)**: Chạy Python script thu thập metrics qua `psutil` và đẩy dữ liệu tới REST API của EdgeX.
- **Platform Side (WSL)**: EdgeX Foundry (v4.0 Odessa) tiếp nhận, thẩm định dữ liệu dựa trên Profile JSON và lưu trữ vào Core Data.
- **Export Side**: Script Python tự động lấy dữ liệu từ Core Data và xử lý thành file CSV.

## 💻 Yêu cầu hệ thống

| Thành phần | Chi tiết |
|------------|----------|
| Server | Windows 10/11 + WSL2 (Ubuntu 20.04/22.04) |
| Client | Raspberry Pi 3/4/5 (Raspberry Pi OS) |
| Network | Cùng mạng LAN (WiFi hoặc Ethernet) |
| Phần mềm | Docker, Docker Compose, Python 3.7+ |

## 🛠 Hướng dẫn chi tiết

### 1. Cài đặt môi trường trên Windows (WSL)

#### 1.1. Cài đặt Docker
```bash
# Cài đặt nhanh Docker engine
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```
*(Lưu ý: Bạn cần khởi động lại terminal WSL sau bước này)*

#### 1.2. Tải EdgeX Compose
```bash
git clone https://github.com/edgexfoundry/edgex-compose.git
cd edgex-compose
git checkout odessa
cd compose-builder
make build no-secty
```

### 2. Cấu hình mạng và Firewall

> **Quan trọng**: EdgeX chạy trong Docker/WSL cần được thông tuyến với mạng LAN để Raspberry Pi có thể "nhìn" thấy.

1. **Lấy IP Windows**: Mở CMD và gõ `ipconfig`. (Ví dụ: `192.168.1.6`)
2. **Mở Port 59986**: Chạy PowerShell (Admin):
   ```powershell
   New-NetFirewallRule -DisplayName "EdgeX REST 59986" -Direction Inbound -Protocol TCP -LocalPort 59986 -Action Allow
   ```
3. **Port Forwarding**: (Nếu RPi không kết nối được trực tiếp vào WSL)
   ```powershell
   netsh interface portproxy add v4tov4 listenport=59986 listenaddress=0.0.0.0 connectport=59986 connectaddress=127.0.0.1
   ```

### 3. Chạy EdgeX trên WSL

```bash
# Khởi động dịch vụ
cd /path/to/edgex-compose/compose-files
docker compose -f docker-compose-no-secty.yml up -d

# Kiểm tra trạng thái các container
docker ps --format "table {{.Names}}\t{{.Status}}"
```

### 4. Tạo Profile và Device (Metadata)

Gửi thông tin định nghĩa thiết bị tới EdgeX Core Metadata:

#### 4.1. Đăng ký Profile
```bash
curl -X POST http://localhost:59881/api/v3/deviceprofile \
  -H "Content-Type: application/json" \
  -d @config/rpi-rest-profile-v2.json
```

#### 4.2. Đăng ký Device
```bash
curl -X POST http://localhost:59881/api/v3/device \
  -H "Content-Type: application/json" \
  -d @config/rpi-rest-device-v2.json
```

#### 4.3. Kiểm tra
```bash
curl http://localhost:59881/api/v3/device/name/RPi4-REST-v2 | jq .
```

### 5. Script thu thập trên Raspberry Pi

#### 5.1. Cài đặt thư viện
```bash
pip3 install psutil requests
```

#### 5.2. Tạo file `system_monitor.py`
```python
#!/usr/bin/env python3
import requests
import psutil
import time

DEVICE_NAME = "RPi4-REST-v2"
BASE_URL = "http://192.168.1.6:59986/api/v3/resource"
INTERVAL = 3

dynamic_metrics = [
    'Temperature', 'CPUUsage', 'CPUFreq', 'ContextSwitches',
    'Interrupts', 'SoftInterrupts', 'MemUsed', 'MemFree',
    'LoadAvg1', 'LoadAvg5', 'LoadAvg15', 'ProcessCount', 'Uptime'
]

def read_cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            return float(f.read()) / 1000.0
    except:
        return 0.0

def get_metrics():
    metrics = {}
    metrics['CPUUsage'] = psutil.cpu_percent(interval=0.1)
    freq = psutil.cpu_freq()
    metrics['CPUFreq'] = freq.current if freq else 0.0
    stats = psutil.cpu_stats()
    metrics['ContextSwitches'] = stats.ctx_switches
    metrics['Interrupts'] = stats.interrupts
    metrics['SoftInterrupts'] = stats.soft_interrupts
    mem = psutil.virtual_memory()
    metrics['MemUsed'] = mem.used
    metrics['MemFree'] = mem.free
    load = psutil.getloadavg()
    metrics['LoadAvg1'] = load[0]
    metrics['LoadAvg5'] = load[1]
    metrics['LoadAvg15'] = load[2]
    metrics['ProcessCount'] = len(psutil.pids())
    metrics['Uptime'] = int(time.time() - psutil.boot_time())
    metrics['Temperature'] = read_cpu_temp()
    return metrics

def send_metric(name, value):
    try:
        r = requests.post(f"{BASE_URL}/{DEVICE_NAME}/{name}", json=value, timeout=1)
        return r.status_code == 200
    except:
        return False

print(f"🚀 Bắt đầu thu thập mỗi {INTERVAL}s...")
while True:
    try:
        data = get_metrics()
        ok = 0
        for k, v in data.items():
            if send_metric(k, v):
                ok += 1
        print(f"[{time.strftime('%H:%M:%S')}] Temp:{data['Temperature']:.1f}°C CPU:{data['CPUUsage']:.1f}% | Gửi {ok}/{len(data)}")
        time.sleep(INTERVAL)
    except KeyboardInterrupt:
        break
    except Exception as e:
        print("❌ Lỗi:", e)
        time.sleep(INTERVAL)
```

#### 5.3. Chạy script
```bash
python3 system_monitor.py
```
Để chạy nền, dùng `tmux` hoặc `screen`.

## 📊 Xử lý dữ liệu đầu ra

Hệ thống cung cấp script `auto_update.py` để làm phẳng (flatten) dữ liệu từ dạng key-value của EdgeX sang bảng CSV hoàn chỉnh.

### Script `auto_update.py` (chạy trên WSL)
```python
import requests
import pandas as pd
import time
from datetime import datetime

DEVICE_NAME = "RPi4-REST-v2"
BASE_URL = f"http://localhost:59880/api/v3/reading/device/name/{DEVICE_NAME}"
LIMIT = 1024
OUTPUT_FILE = "pi_dataset_dynamic.csv"
INTERVAL = 60
BIN_SIZE_SEC = 0.5

dynamic_metrics = [
    'Temperature', 'CPUUsage', 'CPUFreq', 'ContextSwitches',
    'Interrupts', 'SoftInterrupts', 'MemUsed', 'MemFree',
    'LoadAvg1', 'LoadAvg5', 'LoadAvg15', 'ProcessCount', 'Uptime'
]

def get_all_readings():
    all_rd = []
    offset = 0
    while True:
        params = {"limit": LIMIT, "offset": offset}
        resp = requests.get(BASE_URL, params=params)
        if resp.status_code != 200:
            return []
        data = resp.json()
        rds = data.get('readings', [])
        if not rds:
            break
        all_rd.extend(rds)
        offset += len(rds)
        if len(rds) < LIMIT:
            break
    return all_rd

def process_and_save(readings):
    if not readings:
        return
    df = pd.DataFrame(readings)
    df = df[df['resourceName'].isin(dynamic_metrics)]
    if df.empty:
        return
    df['value'] = pd.to_numeric(df['value'])
    bin_ns = int(BIN_SIZE_SEC * 1e9)
    df['bin'] = (df['origin'] // bin_ns) * bin_ns
    df_pivot = df.pivot_table(index='bin', columns='resourceName', values='value', aggfunc='first').reset_index()
    df_pivot.columns.name = None
    df_pivot['datetime'] = pd.to_datetime(df_pivot['bin'] / 1_000_000_000, unit='s')
    df_pivot = df_pivot.sort_values('bin').ffill()
    cols = ['bin', 'datetime'] + [c for c in dynamic_metrics if c in df_pivot.columns]
    df_pivot = df_pivot[cols]
    df_pivot.to_csv(OUTPUT_FILE, index=False)
    print(f"[{datetime.now()}] ✅ Đã ghi {len(df_pivot)} dòng vào {OUTPUT_FILE}")

def main():
    print(f"🔄 Tự động cập nhật mỗi {INTERVAL}s...")
    while True:
        readings = get_all_readings()
        if readings:
            process_and_save(readings)
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()
```

### Chạy script cập nhật
```bash
python auto_update.py
```

### Cấu trúc dữ liệu CSV
| bin | datetime | Temperature | CPUUsage | MemUsed | ... |
|:---|:---|:---|:---|:---|:---|
| 1772632762000000000 | 2026-03-04 13:59:22.009 | 49.173 | 0.0 | 318971904 | ... |

## 📁 Cấu trúc thư mục dự án

```
.
├── config/
│   ├── rpi-rest-device-v2.json      # Cấu hình thiết bị
│   └── rpi-rest-profile-v2.json     # Định nghĩa tài nguyên dữ liệu
├── scripts/
│   ├── system_monitor.py            # Chạy trên Raspberry Pi
│   └── auto_update.py               # Chạy trên WSL (Xuất CSV)
├── docker-compose-no-secty.yml      # File chạy EdgeX
├── .gitignore                        # Bỏ qua các file không cần thiết
└── README.md                         # Tài liệu này
```

## 🔒 .gitignore

```gitignore
# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# Virtual environments
venv/
env/
ENV/

# CSV và file dữ liệu
*.csv
*.zip
*.tar
*.gz

# Images
*.png
*.jpg
*.jpeg
*.gif
*.bmp

# EdgeX config (tuỳ chọn)
config/*.json
!config/README.md

# Docker compose override
docker-compose.override.yml

# Logs
*.log
```

## 📝 Giấy phép

Dự án này được phát hành dưới bản quyền **MIT License**. Vui lòng trích dẫn nguồn khi sử dụng cho mục đích học thuật tại **HCMUT**.

---

**Tác giả:** [Tên bạn]  
**Last updated:** 2026-03-06
