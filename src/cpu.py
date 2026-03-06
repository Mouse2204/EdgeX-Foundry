import paho.mqtt.client as mqtt
import psutil
import time
import json

# ===== CẤU HÌNH =====
BROKER_IP = "10.128.21.214"   # Địa chỉ IP của máy tính chạy EdgeX
BROKER_PORT = 1883
DEVICE_NAME = "RPi4-MQTT"      # Tên device đã tạo trên EdgeX
TOPIC = f"edgex/device-mqtt/{DEVICE_NAME}/ReadSensor"
INTERVAL = 5                    # giây

# ===== HÀM ĐỌC DỮ LIỆU =====
def read_cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            return float(f.read()) / 1000.0
    except:
        return 0.0

# ===== KẾT NỐI MQTT =====
client = mqtt.Client()
try:
    client.connect(BROKER_IP, BROKER_PORT, 60)
    print(f"✅ Đã kết nối tới MQTT broker {BROKER_IP}:{BROKER_PORT}")
except Exception as e:
    print(f"❌ Lỗi kết nối MQTT: {e}")
    exit(1)

client.loop_start()
print(f"🚀 Bắt đầu gửi dữ liệu mỗi {INTERVAL} giây...")

# ===== VÒNG LẶP CHÍNH =====
while True:
    cpu_usage = psutil.cpu_percent(interval=1)
    cpu_temp = read_cpu_temp()
    payload = {
        "CPU_Usage": cpu_usage,
        "CPU_Temperature": cpu_temp
    }
    client.publish(TOPIC, json.dumps(payload))
    print(f"📤 Published: {payload}")
    time.sleep(INTERVAL)