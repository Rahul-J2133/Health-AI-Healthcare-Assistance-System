"""
pseudo_data_generator.py — Simple hardcoded vitals generator.
Writes slightly varied values to firstREC.txt every N seconds in a background thread.
"""
import os
import random
import threading
import time
from datetime import datetime

DATA_DIR = "./data"
REC_FILE = os.path.join(DATA_DIR, "firstREC.txt")

# ── Hardcoded base values ──────────────────────────────────────────────────
BASE = {
    "body_temp": 36.8,   # °C
    "humidity":  55.0,   # %
    "room_temp": 24.0,   # °C
    "spo2":      97.5,   # %
    "bpm":       72,     # beats per minute
}

# Small random variation applied each tick (±range)
VARIATION = {
    "body_temp": 0.2,
    "humidity":  2.0,
    "room_temp": 0.5,
    "spo2":      0.5,
    "bpm":       4,
}

_stop_event: threading.Event | None = None


def _write():
    os.makedirs(DATA_DIR, exist_ok=True)

    body_temp = round(BASE["body_temp"] + random.uniform(-VARIATION["body_temp"], VARIATION["body_temp"]), 1)
    humidity  = round(BASE["humidity"]  + random.uniform(-VARIATION["humidity"],  VARIATION["humidity"]),  1)
    room_temp = round(BASE["room_temp"] + random.uniform(-VARIATION["room_temp"], VARIATION["room_temp"]), 1)
    spo2      = round(BASE["spo2"]      + random.uniform(-VARIATION["spo2"],      VARIATION["spo2"]),      1)
    bpm       = int(BASE["bpm"]         + random.randint(-VARIATION["bpm"],       VARIATION["bpm"]))

    with open(REC_FILE, "w") as f:
        f.write(
            f"\nDATE: {datetime.now().date()}\n"
            f"TIME: {datetime.now().strftime('%H:%M:%S')}\n"
            f"BODY TEMPERATURE: {body_temp} DEGREE CELSIUS\n"
            f"HUMIDITY: {humidity} %\n"
            f"ROOM TEMPERATURE: {room_temp} DEGREE CELSIUS\n"
            f"SPO2 LEVEL: {spo2} %\n"
            f"AVERAGE BEATS PER MINUTE: {bpm}\n"
        )
    print(f"[generator] Temp={body_temp}°C  HR={bpm}bpm  SpO2={spo2}%  Hum={humidity}%  Room={room_temp}°C")


def _run(interval: float, stop: threading.Event):
    print(f"[generator] Started — writing every {interval}s")
    while not stop.is_set():
        try:
            _write()
        except Exception as e:
            print(f"[generator] Error: {e}")
        stop.wait(interval)
    print("[generator] Stopped.")


def start_generator(interval: float = 5.0) -> None:
    global _stop_event
    if _stop_event and not _stop_event.is_set():
        _stop_event.set()
    _stop_event = threading.Event()
    threading.Thread(target=_run, args=(interval, _stop_event), daemon=True, name="vitals-gen").start()


def stop_generator() -> None:
    global _stop_event
    if _stop_event:
        _stop_event.set()


def is_running() -> bool:
    return _stop_event is not None and not _stop_event.is_set()


if __name__ == "__main__":
    stop = threading.Event()
    try:
        _run(5.0, stop)
    except KeyboardInterrupt:
        pass