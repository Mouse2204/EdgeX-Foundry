Dưới đây là file `README.md` tổng hợp toàn bộ quá trình từ setup mạng, chạy EdgeX, thu thập dữ liệu từ Raspberry Pi, và xuất dữ liệu. Nội dung được trình bày chi tiết, dễ làm theo.

```markdown
# Dự án thu thập dữ liệu Raspberry Pi với EdgeX Foundry

Dự án này hướng dẫn cách thiết lập EdgeX Foundry trên Windows (WSL) để thu thập các chỉ số hệ thống từ Raspberry Pi (nhiệt độ CPU, tần số, context switches, bộ nhớ, load average, v.v.) qua REST API, lưu trữ vào EdgeX, và xuất ra file CSV để phân tích.

## Yêu cầu

- Máy tính Windows có hỗ trợ WSL2 (cài Ubuntu 20.04/22.04)
- Docker và Docker Compose trên WSL
- Raspberry Pi (chạy Raspberry Pi OS) cùng mạng LAN với máy Windows
- Python 3.7+ trên cả Windows (WSL) và Raspberry Pi

## Các bước thực hiện

### 1. Cài đặt môi trường trên Windows (WSL)

#### 1.1. Cài đặt Docker trên WSL
```bash
# Trong WSL Ubuntu
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
exit
# Mở lại WSL và kiểm tra
docker --version
```

#### 1.2. Tải EdgeX Docker Compose file
```bash
cd ~
git clone https://github.com/edgexfoundry/edgex-compose.git
cd edgex-compose
# Sử dụng phiên bản 4.0 (Odessa)
git checkout odessa
cd compose-builder
make build no-secty
cp docker-compose-no-secty.yml ~/edgex-mqtt/   # tạo thư mục nếu chưa có
```

Hoặc sử dụng file `docker-compose-no-secty.yml` đã được cung cấp trong dự án.

### 2. Cấu hình mạng và firewall

#### 2.1. Lấy địa chỉ IP của Windows trên mạng LAN
```bash
ipconfig
```
Kết quả: `IPv4 Address: 192.168.1.6` (ví dụ). Ghi nhớ IP này.

#### 2.2. Mở port 59986 (cho device-rest) trên Windows Firewall
Chạy PowerShell với quyền Administrator:
```powershell
New-NetFirewallRule -DisplayName "EdgeX REST 59986" -Direction Inbound -Protocol TCP -LocalPort 59986 -Action Allow
```

#### 2.3. Thiết lập port forwarding (nếu device-rest chỉ lắng nghe localhost)
Trong WSL, kiểm tra:
```bash
docker logs edgex-device-rest | grep "Route"
```
Nếu thấy route nhưng từ máy ngoài không kết nối được, tạo port forward:
```powershell
netsh interface portproxy add v4tov4 listenport=59986 listenaddress=192.168.1.6 connectport=59986 connectaddress=127.0.0.1
```

### 3. Chạy EdgeX trên WSL

#### 3.1. Khởi động các container
```bash
cd /mnt/d/EdgeX   # hoặc thư mục chứa file docker-compose
docker compose -f docker-compose-no-secty.yml up -d
```

#### 3.2. Kiểm tra container đã chạy
```bash
docker ps
```
Phải thấy `edgex-core-metadata`, `edgex-core-data`, `edgex-device-rest`, v.v.

### 4. Tạo profile và device trên EdgeX

#### 4.1. Tạo file profile mở rộng (`rpi-rest-profile-v2.json`)
Nội dung file (có thể lấy từ dự án):
```json
[
  {
    "apiVersion": "v3",
    "profile": {
      "name": "RPi-REST-Profile-v2",
      "manufacturer": "Raspberry",
      "model": "Pi4",
      "labels": ["rpi", "rest", "expanded"],
      "description": "Expanded profile for Raspberry Pi system metrics",
      "deviceResources": [
        {"name": "Temperature", "properties": {"valueType": "Float32", "readWrite": "R", "units": "Celsius"}},
        {"name": "CPUUsage", "properties": {"valueType": "Float32", "readWrite": "R", "units": "percent"}},
        {"name": "CPUFreq", "properties": {"valueType": "Float32", "readWrite": "R", "units": "MHz"}},
        {"name": "ContextSwitches", "properties": {"valueType": "Uint64", "readWrite": "R", "units": "switches"}},
        {"name": "Interrupts", "properties": {"valueType": "Uint64", "readWrite": "R", "units": "interrupts"}},
        {"name": "SoftInterrupts", "properties": {"valueType": "Uint64", "readWrite": "R", "units": "interrupts"}},
        {"name": "MemUsed", "properties": {"valueType": "Uint64", "readWrite": "R", "units": "bytes"}},
        {"name": "MemFree", "properties": {"valueType": "Uint64", "readWrite": "R", "units": "bytes"}},
        {"name": "LoadAvg1", "properties": {"valueType": "Float32", "readWrite": "R", "units": "load"}},
        {"name": "LoadAvg5", "properties": {"valueType": "Float32", "readWrite": "R", "units": "load"}},
        {"name": "LoadAvg15", "properties": {"valueType": "Float32", "readWrite": "R", "units": "load"}},
        {"name": "ProcessCount", "properties": {"valueType": "Uint64", "readWrite": "R", "units": "processes"}},
        {"name": "Uptime", "properties": {"valueType": "Uint64", "readWrite": "R", "units": "seconds"}}
      ]
    }
  }
]
```

#### 4.2. Tạo file device (`rpi-rest-device-v2.json`)
```json
[
  {
    "apiVersion": "v3",
    "device": {
      "name": "RPi4-REST-v2",
      "profileName": "RPi-REST-Profile-v2",
      "serviceName": "device-rest",
      "adminState": "UNLOCKED",
      "operatingState": "UP",
      "labels": ["rpi", "rest"],
      "protocols": {
        "rest": {
          "Address": "192.168.1.6",   // IP của Windows
          "Port": "59986"
        }
      }
    }
  }
]
```

#### 4.3. Đăng ký profile và device
```bash
cd /mnt/d/EdgeX/config
curl -X POST http://localhost:59881/api/v3/deviceprofile -H "Content-Type: application/json" -d @rpi-rest-profile-v2.json
curl -X POST http://localhost:59881/api/v3/device -H "Content-Type: application/json" -d @rpi-rest-device-v2.json
curl http://localhost:59881/api/v3/device/name/RPi4-REST-v2 | jq .
```

### 5. Cài đặt script thu thập trên Raspberry Pi

#### 5.1. Cài đặt thư viện Python
```bash
pip3 install psutil requests pandas
```

#### 5.2. Tạo script `system_monitor.py`
```python
#!/usr/bin/env python3
import requests
import psutil
import time

DEVICE_NAME = "RPi4-REST-v2"
BASE_URL = "http://192.168.1.6:59986/api/v3/resource"
INTERVAL = 3  # giây

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

print(f"Bắt đầu thu thập mỗi {INTERVAL}s...")
while True:
    try:
        data = get_metrics()
        ok = 0
        for k, v in data.items():
            if send_metric(k, v):
                ok += 1
        print(f"[{time.strftime('%H:%M:%S')}] Temp:{data['Temperature']:.1f} CPU:{data['CPUUsage']:.1f}% Gửi {ok}/{len(data)}")
        time.sleep(INTERVAL)
    except KeyboardInterrupt:
        break
    except Exception as e:
        print("Lỗi:", e)
        time.sleep(INTERVAL)
```

#### 5.3. Chạy script
```bash
python3 system_monitor.py
```
Để chạy nền, dùng `tmux` hoặc `screen`.

### 6. Xuất dữ liệu từ EdgeX ra CSV (trên WSL)

#### 6.1. Script tự động cập nhật (`auto_update.py`)
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
    print(f"[{datetime.now()}] Đã ghi {len(df_pivot)} dòng.")

def main():
    while True:
        readings = get_all_readings()
        if readings:
            process_and_save(readings)
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()
```

#### 6.2. Chạy script cập nhật
```bash
python auto_update.py
```
Script sẽ chạy nền, mỗi 60 giây cập nhật file CSV.

### 7. Lấy dữ liệu từ máy khác (cùng mạng LAN)
Sử dụng URL:
```
http://192.168.1.6:59880/api/v3/reading/device/name/RPi4-REST-v2?limit=100
```
Hoặc dùng script Python với `requests`.

### 8. Git và .gitignore

#### 8.1. Tạo file `.gitignore`
```
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

#### 8.2. Tạo repository và đẩy lên
```bash
git init
git add .
git commit -m "Initial commit: EdgeX Raspberry Pi monitor"
git branch -M main
git remote add origin https://github.com/yourusername/edgex-rpi-monitor.git
git push -u origin main
```

## Kết luận

Bạn đã thiết lập thành công hệ thống thu thập dữ liệu từ Raspberry Pi vào EdgeX, tự động cập nhật CSV và sẵn sàng cho phân tích. Mọi thông tin cấu hình đều được lưu trong dự án, dễ dàng tái tạo trên máy khác.
```

File này bao gồm tất cả các bước, từ setup mạng, chạy Docker, tạo profile, script thu thập, xuất dữ liệu, và cả .gitignore. Bạn có thể điều chỉnh địa chỉ IP cho phù hợp.
