"""
routers/generator.py — Start/stop/status endpoints for the vitals generator.
"""
from fastapi import APIRouter
from pseudo_data_generator import start_generator, stop_generator, is_running

router = APIRouter(prefix="/generator", tags=["Generator"])

@router.post("/start")
def start(interval: float = 5.0):
    start_generator(interval=interval)
    return {"status": "started", "interval": interval}

@router.post("/stop")
def stop():
    stop_generator()
    return {"status": "stopped"}

@router.get("/status")
def status():
    return {"running": is_running()}