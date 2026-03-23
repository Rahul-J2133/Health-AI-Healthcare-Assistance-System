"""
routers/imaging.py — ECG ingestion, X-ray upload, pneumonia prediction.
"""
import base64
import io
import json
import os
import traceback
from datetime import datetime

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image

from services.thingspeak import send_ecg, send_vitals
from services.imagekit_client import get_imagekit, upload_file as ik_upload
import models.pneumonia as pneumonia_model

router = APIRouter()
DATA_DIR = "./data"


@router.post("/update_ECG")
async def update_ecg(request: Request):
    """Receive ECG values from ESP32 and save to ecg_data.json."""
    try:
        data = await request.json()
        ecg_raw = data.get("ecg", "")
        if not isinstance(ecg_raw, str):
            return {"error": "'ecg' must be a comma-separated string."}
        ecg_values = [float(x.strip()) for x in ecg_raw.split(",") if x.strip()]
        with open(os.path.join(DATA_DIR, "ecg_data.json"), "w") as f:
            json.dump({"ecg": ecg_values}, f)
        return {"message": "ECG data saved."}
    except Exception as e:
        return {"error": str(e)}


@router.get("/unlabelled-stream")
def get_ecg_stream():
    """Return latest ECG array for the dashboard chart."""
    path = os.path.join(DATA_DIR, "ecg_data.json")
    if not os.path.exists(path):
        return []
    with open(path, "r") as f:
        return json.load(f).get("ecg", [])


@router.get("/approveForEHR")
async def approve_ehr_vitals():
    """Upload ECG plot and vitals to external services."""
    try:
        send_ecg()
        send_vitals()
        return JSONResponse(content={"status": "success", "message": "ECG and vitals uploaded."})
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@router.post("/approveForEHR")
async def approve_ehr_xray(request: Request):
    """Receive base64-encoded X-ray, save locally, upload to ImageKit."""
    try:
        data = await request.json()
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=400)

    b64 = data.get("image")
    if not b64:
        return JSONResponse(content={"error": "'image' field missing."}, status_code=400)

    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"approved_xray_{timestamp}.jpg"
        save_path = os.path.join(DATA_DIR, filename)
        with open(save_path, "wb") as f:
            f.write(base64.b64decode(b64))
    except Exception as e:
        return JSONResponse(content={"error": f"Failed to save image: {e}"}, status_code=500)

    try:
        with open(save_path, "rb") as f:
            resp = ik_upload(get_imagekit(), f, filename, "/xray_plots/", ["xray", "medical"])
        url = resp.get("url") if isinstance(resp, dict) else getattr(resp, "url", None)
        if not url:
            return JSONResponse(content={"error": "No URL returned.", "raw": str(resp)}, status_code=500)
        return JSONResponse(content={"message": "Uploaded.", "filename": filename, "url": url})
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(content={"error": f"Upload failed: {e}"}, status_code=500)


def _format_result(result: dict) -> dict:
    out = {"result": result["result"], "probability": result["probability"]}
    if result.get("CombinedImg") is not None:
        out["combined_img_base64"] = pneumonia_model.encode_image_to_base64(result["CombinedImg"])
    return out


@router.post("/predict")
async def predict(file: UploadFile = File(...)):
    """Run pneumonia detection on an uploaded X-ray image."""
    try:
        img = Image.open(io.BytesIO(await file.read()))
        return JSONResponse(content=_format_result(pneumonia_model.handler(img)))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/invokePython")
async def invoke_camera(camera_ip: str, camera_port: str):
    """Capture a frame from an IP camera and run pneumonia detection."""
    import cv2
    cap = cv2.VideoCapture(f"http://{camera_ip}:{camera_port}/video")
    if not cap.isOpened():
        raise HTTPException(status_code=500, detail="Could not open camera.")
    frame = None
    while True:
        ret, f = cap.read()
        if not ret:
            cap.release()
            raise HTTPException(status_code=500, detail="Could not read frame.")
        cv2.imshow("Camera", f)
        if cv2.waitKey(1) & 0xFF == ord("s"):
            frame = f
            break
    cap.release()
    cv2.destroyAllWindows()
    img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    return JSONResponse(content=_format_result(pneumonia_model.handler(img)))