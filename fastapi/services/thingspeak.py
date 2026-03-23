"""
services/thingspeak.py — Single-user. Reads from ./data/ directly.
"""
import re
import os
import json
import requests
import matplotlib.pyplot as plt
from datetime import datetime
from config import get_settings
from services.imagekit_client import get_imagekit, upload_file as ik_upload

DATA_DIR = "./data"


def send_ecg() -> None:
    json_path = os.path.join(DATA_DIR, "ecg_data.json")
    with open(json_path, "r") as f:
        data = json.load(f)
    ecg_data = data.get("ecg", [])
    if not ecg_data:
        raise ValueError("No ECG data found.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"ecg_plot_{timestamp}.png"
    full_path = os.path.join(DATA_DIR, filename)

    plt.figure(figsize=(10, 4))
    plt.plot(ecg_data, color="red")
    plt.title("ECG Signal")
    plt.xlabel("Samples")
    plt.ylabel("Amplitude")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(full_path)
    plt.close()

    imagekit = get_imagekit()
    with open(full_path, "rb") as file_data:
        upload_response = ik_upload(
            imagekit, file_data=file_data, file_name=filename,
            folder="/ecg_plots/", tags=["ecg", "medical", "signal"],
        )
    url = getattr(upload_response, "url", None)
    print(f"ECG upload {'successful: ' + url if url else 'failed.'}")


def send_vitals() -> None:
    s = get_settings()
    file_path = os.path.join(DATA_DIR, "firstREC.txt")
    with open(file_path, "r") as f:
        raw = f.read()

    # FIX: assign regex patterns to variables before using in f-strings —
    # backslashes are not allowed inside f-string expressions in Python < 3.12
    def extract(pattern):
        match = re.search(pattern, raw)
        return match.group(1).strip() if match else "N/A"

    pat_body_temp = r"BODY TEMPERATURE:\s*([\d.]+)"
    pat_humidity  = r"HUMIDITY:\s*([\d.]+)"
    pat_room_temp = r"ROOM TEMPERATURE:\s*([\d.]+)"
    pat_spo2      = r"SPO2 LEVEL:\s*([\d.]+)"
    pat_bpm       = r"AVERAGE BEATS PER MINUTE:\s*([\d.]+)"

    body_temp = extract(pat_body_temp)
    humidity  = extract(pat_humidity)
    room_temp = extract(pat_room_temp)
    spo2      = extract(pat_spo2)
    bpm       = extract(pat_bpm)

    params = {
        "api_key": s.thingspeak_write_api_key,
        "field1": f"{body_temp} DEGREE CELSIUS",
        "field2": f"{humidity} %",
        "field3": f"{room_temp} DEGREE CELSIUS",
        "field4": f"{spo2} %",
        "field5": f"{bpm} BPM",
    }

    response = requests.get("https://api.thingspeak.com/update", params=params)
    if response.status_code == 200 and response.text != "0":
        print(f"Vitals uploaded. Entry ID: {response.text}")
    else:
        print(f"ThingSpeak upload failed: {response.status_code} — {response.text}")