"""
main.py — FastAPI application entry point.
Run with: uvicorn main:app --reload
"""
import os
import time
import threading
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from qdrant_client import QdrantClient

from config import get_settings
from routers import rag, patient, imaging, ehr, generator

COLLECTION_NAME = "medical_db"


# ── Startup ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    _setup_dirs()
    _wait_for_qdrant()
    _wait_for_ollama()
    _sync_collection()
    _start_watcher()
    _start_generator()
    yield


def _setup_dirs() -> None:
    s = get_settings()
    os.makedirs("./temp", exist_ok=True)
    os.makedirs(s.data_dir, exist_ok=True)
    os.makedirs(s.pdf_output_dir, exist_ok=True)
    from routers.patient import _seed_files
    _seed_files()
    print("[startup] Directories ready, data files seeded.")


def _poll(url: str, name: str, retries: int, delay: float) -> None:
    for i in range(1, retries + 1):
        try:
            if httpx.get(url, timeout=5.0).status_code == 200:
                print(f"[startup] {name} ready ({i} attempt(s)).")
                return
        except Exception:
            pass
        print(f"[startup] Waiting for {name}... ({i}/{retries})")
        time.sleep(delay)
    print(f"[startup] WARNING: {name} not responding — continuing.")


def _wait_for_qdrant() -> None:
    s = get_settings()
    _poll(s.qdrant_url + "/collections", "Qdrant", retries=20, delay=3.0)


def _wait_for_ollama() -> None:
    s = get_settings()
    _poll(s.ollama_url + "/api/tags", "Ollama", retries=20, delay=3.0)
    # Wait for nomic-embed-text model specifically
    for i in range(1, 61):
        try:
            r = httpx.post(
                s.ollama_url + "/api/embeddings",
                json={"model": "nomic-embed-text", "prompt": "test"},
                timeout=10.0,
            )
            if r.status_code == 200:
                print(f"[startup] nomic-embed-text ready ({i} attempt(s)).")
                return
        except Exception:
            pass
        print(f"[startup] Waiting for nomic-embed-text... ({i}/60)")
        time.sleep(5)
    print("[startup] WARNING: nomic-embed-text not ready — continuing.")


def _sync_collection() -> None:
    s = get_settings()
    client = QdrantClient(url=s.qdrant_url)
    txt_files = [f for f in os.listdir(s.data_dir) if f.endswith(".txt")] if os.path.exists(s.data_dir) else []

    try:
        client.get_collection(COLLECTION_NAME)
        exists = True
    except Exception:
        exists = False

    if not txt_files and exists:
        client.delete_collection(COLLECTION_NAME)
        print("[startup] No .txt files — deleted stale collection.")
    elif txt_files and not exists:
        print(f"[startup] Building collection from {len(txt_files)} file(s)...")
        from ingest.watcher import update_vector_store
        update_vector_store(s.data_dir)
    elif txt_files and exists:
        print(f"[startup] Collection ready ({len(txt_files)} source file(s)).")
    else:
        print(f"[startup] No .txt files in '{s.data_dir}'. Add knowledge files and restart.")


def _start_watcher() -> None:
    from ingest.watcher import start_watcher
    threading.Thread(target=start_watcher, daemon=True, name="watcher").start()
    print("[startup] File watcher running.")


def _start_generator() -> None:
    from pseudo_data_generator import start_generator
    start_generator(interval=5.0)
    print("[startup] Vitals generator running.")


# ── App ────────────────────────────────────────────────────────────────────

app = FastAPI(title="Medical RAG API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rag.router)
app.include_router(patient.router)
app.include_router(imaging.router)
app.include_router(ehr.router)
app.include_router(generator.router)


@app.get("/")
async def root():
    return {"status": "Medical RAG API is running"}


@app.post("/reset-knowledge")
async def reset_knowledge():
    """Wipe and rebuild the Qdrant collection from ./data/*.txt."""
    s = get_settings()
    client = QdrantClient(url=s.qdrant_url)
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    txt_files = [f for f in os.listdir(s.data_dir) if f.endswith(".txt")] if os.path.exists(s.data_dir) else []
    if not txt_files:
        return {"status": "cleared", "message": "No .txt files to rebuild from."}
    from ingest.watcher import update_vector_store
    update_vector_store(s.data_dir)
    return {"status": "rebuilt", "message": f"Rebuilt from {len(txt_files)} file(s)."}