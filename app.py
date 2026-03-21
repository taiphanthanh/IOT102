from flask import Flask, jsonify
from flask_cors import CORS
import requests
from collections import deque
from datetime import datetime

app = Flask(__name__)
CORS(app)

BLYNK_AUTH_TOKEN = "Z_y95lYbyK10X8FiNWJvRpAUnHOpx_jG"
BLYNK_BASE_URL = "https://blynk.cloud/external/api/get"

# Lưu lịch sử ngắn trong RAM
# mỗi phần tử: {time, water_level, distance, alert}
history = deque(maxlen=60)  # khoảng 60 mẫu gần nhất

def blynk_get(pin):
    url = f"{BLYNK_BASE_URL}?token={BLYNK_AUTH_TOKEN}&{pin}"
    res = requests.get(url, timeout=5)
    res.raise_for_status()
    txt = res.text.strip()
    return float(txt)

def fetch_current_data():
    try:
        distance_cm = blynk_get("V0")
    except:
        distance_cm = None

    try:
        water_level_cm = blynk_get("V1")
    except:
        water_level_cm = None

    try:
        alert_level = blynk_get("V2")
    except:
        alert_level = None

    item = {
        "time": datetime.now(),
        "distance_cm": distance_cm,
        "water_level_cm": water_level_cm,
        "alert_level": alert_level,
    }

    # chỉ lưu nếu có water level hợp lệ
    if water_level_cm is not None:
        history.append(item)

    return item

def analyze_trend():
    valid = [x for x in history if x["water_level_cm"] is not None]

    if len(valid) < 5:
        return {
            "trend": "not_enough_data",
            "slope_cm_per_sec": 0,
            "message": "Chưa đủ dữ liệu để phân tích xu hướng"
        }

    first = valid[0]
    last = valid[-1]

    dt = (last["time"] - first["time"]).total_seconds()
    if dt <= 0:
        return {
            "trend": "stable",
            "slope_cm_per_sec": 0,
            "message": "Dữ liệu thời gian không hợp lệ"
        }

    dw = last["water_level_cm"] - first["water_level_cm"]
    slope = dw / dt  # cm / giây

    if slope > 0.3:
        trend = "rising_fast"
        message = "Mực nước đang tăng nhanh"
    elif slope > 0.05:
        trend = "rising"
        message = "Mực nước đang tăng"
    elif slope < -0.05:
        trend = "falling"
        message = "Mực nước đang giảm"
    else:
        trend = "stable"
        message = "Mực nước đang ổn định"

    return {
        "trend": trend,
        "slope_cm_per_sec": round(slope, 4),
        "message": message
    }

@app.route("/current-data", methods=["GET"])
def current_data():
    item = fetch_current_data()

    return jsonify({
        "distance_cm": item["distance_cm"],
        "water_level_cm": item["water_level_cm"],
        "alert_level": item["alert_level"],
        "timestamp": item["time"].strftime("%Y-%m-%d %H:%M:%S")
    })

@app.route("/predict-trend", methods=["GET"])
def predict_trend():
    fetch_current_data()
    trend_info = analyze_trend()

    current = history[-1] if len(history) > 0 else None

    return jsonify({
        "current_water_level_cm": current["water_level_cm"] if current else None,
        "samples": len(history),
        "trend": trend_info["trend"],
        "slope_cm_per_sec": trend_info["slope_cm_per_sec"],
        "message": trend_info["message"]
    })

if __name__ == "__main__":
    app.run(debug=True, port=5000)