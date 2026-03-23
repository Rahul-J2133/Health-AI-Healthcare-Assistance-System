"""
routers/patient.py — Patient vitals, notes, session management.

/reset_user_data — full cleanup (local + ImageKit + ThingSpeak) + re-seed
/new_session     — same cleanup, called automatically when a new user logs in
/health-data     — latest vitals from firstREC.txt
/update_patient_info     — append manual notes
/update_patient_info_esp — receive ESP32 sensor data
"""
import json
import os
from datetime import datetime

from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse

router = APIRouter()

DATA_DIR = "./data"
TEMP_DIR = "./temp"


# ── File seeding ───────────────────────────────────────────────────────────

def _seed_files() -> None:
    """Create default data files so dashboard renders on first load."""
    os.makedirs(DATA_DIR, exist_ok=True)

    first_rec = os.path.join(DATA_DIR, "firstREC.txt")
    if not os.path.exists(first_rec):
        with open(first_rec, "w") as f:
            f.write(
                f"DATE: {datetime.now().date()}\n"
                f"TIME: {datetime.now().strftime('%H:%M:%S')}\n"
                f"BODY TEMPERATURE: 0.0 DEGREE CELSIUS\n"
                f"HUMIDITY: 0.0 %\n"
                f"ROOM TEMPERATURE: 0.0 DEGREE CELSIUS\n"
                f"SPO2 LEVEL: 0.0 %\n"
                f"AVERAGE BEATS PER MINUTE: 0.0\n"
            )

    ecg_file = os.path.join(DATA_DIR, "ecg_data.json")
    if not os.path.exists(ecg_file):
        from ingest.ecg_default import DEFAULT_ECG
        with open(ecg_file, "w") as f:
            json.dump({"ecg": DEFAULT_ECG}, f)

    second_rec = os.path.join(DATA_DIR, "secondREC.txt")
    if not os.path.exists(second_rec):
        with open(second_rec, "w") as f:
            f.write(
                f"DATE: {datetime.now().date()}\n"
                f"TIME: {datetime.now().strftime('%H:%M:%S')}\n"
                f"ADDED INFORMATION: Profile initialised.\n"
            )


# ── Vitals endpoints ───────────────────────────────────────────────────────

@router.post("/update_patient_info")
async def update_patient_info(patient_info: str = Form(...)):
    """Append manually entered notes to secondREC.txt."""
    path = os.path.join(DATA_DIR, "secondREC.txt")
    with open(path, "a") as f:
        f.write(
            f"\nDATE: {datetime.now().date()}\n"
            f"TIME: {datetime.now().strftime('%H:%M:%S')}\n"
            f"ADDED INFORMATION: {patient_info}\n"
        )
    return {"message": "Patient information saved."}


@router.post("/update_patient_info_esp")
async def update_patient_info_esp(request: Request):
    """Receive sensor telemetry from ESP32."""
    try:
        data = await request.json()
        with open(os.path.join(DATA_DIR, "firstREC.txt"), "w") as f:
            f.write(
                f"\nDATE: {datetime.now().date()}\n"
                f"TIME: {datetime.now().strftime('%H:%M:%S')}\n"
                f"BODY TEMPERATURE: {data.get('bodyTemp')} DEGREE CELSIUS\n"
                f"HUMIDITY: {data.get('humidity')} %\n"
                f"ROOM TEMPERATURE: {data.get('roomTemp')} DEGREE CELSIUS\n"
                f"SPO2 LEVEL: {data.get('spo2')} %\n"
                f"AVERAGE BEATS PER MINUTE: {data.get('avgBpm')}\n"
            )
        return {"message": "Sensor data written."}
    except Exception as e:
        return {"error": str(e)}


@router.get("/health-data")
def read_health_data():
    """Return latest vitals as JSON."""
    _seed_files()
    result = {}
    with open(os.path.join(DATA_DIR, "firstREC.txt"), "r") as f:
        for line in f:
            if ":" in line:
                key, _, value = line.strip().partition(":")
                key = key.strip().lower().replace(" ", "_")
                numeric = value.strip().split(" ")[0]
                try:
                    result[key] = float(numeric)
                except ValueError:
                    result[key] = value.strip()
    return result


# ── Session & reset endpoints ──────────────────────────────────────────────

@router.post("/new_session")
async def new_session():
    """
    Called automatically by the frontend when a new user profile is created.
    Wipes all data across every storage layer so no previous user's data
    remains — locally, on ImageKit, or on ThingSpeak.
    Then re-seeds empty files so the dashboard renders immediately.
    """
    from services.cleanup import full_cleanup
    results = full_cleanup()
    _seed_files()
    return JSONResponse(content={
        "message": "New session started. All previous data cleared.",
        "cleared": results,
    })


@router.post("/reset_user_data")
async def reset_user_data():
    """
    Manual reset triggered by the Reset Data button in the header.
    Same as new_session — full cleanup across all layers + re-seed.
    """
    from services.cleanup import full_cleanup
    results = full_cleanup()
    _seed_files()
    return JSONResponse(content={
        "message": "All data reset.",
        "cleared": results,
    })