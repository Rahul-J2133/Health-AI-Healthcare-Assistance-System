"""
services/cleanup.py — Full data cleanup across all storage layers.

Clears:
  1. Local ./data/ files (vitals, ECG, X-rays, notes)
  2. Local ./temp/ (conversation history)
  3. Local ./generated_pdfs/
  4. ImageKit CDN — /ecg_plots/ and /xray_plots/ folders
  5. ThingSpeak — clears the channel by writing zeroed fields

Called on:
  - POST /reset_user_data (manual reset button)
  - POST /new_session     (auto-cleanup when a new user logs in)
"""
import os
import shutil
import requests
from config import get_settings

DATA_DIR    = "./data"
TEMP_DIR    = "./temp"


# ── Local cleanup ──────────────────────────────────────────────────────────

def _clear_local() -> list[str]:
    """Wipe local data files. Cannot rmtree volume mount points."""
    cleared = []

    # ./data/ contents
    if os.path.exists(DATA_DIR):
        for fname in os.listdir(DATA_DIR):
            fpath = os.path.join(DATA_DIR, fname)
            try:
                if os.path.isfile(fpath):
                    os.remove(fpath)
                elif os.path.isdir(fpath):
                    shutil.rmtree(fpath)
            except Exception as e:
                print(f"[cleanup] Could not delete {fpath}: {e}")
        cleared.append("local data files")

    # conversation history
    history = os.path.join(TEMP_DIR, "conversation.json")
    if os.path.exists(history):
        os.remove(history)
        cleared.append("conversation history")

    # generated PDFs
    s = get_settings()
    if os.path.exists(s.pdf_output_dir):
        for fname in os.listdir(s.pdf_output_dir):
            fpath = os.path.join(s.pdf_output_dir, fname)
            try:
                if os.path.isfile(fpath):
                    os.remove(fpath)
            except Exception as e:
                print(f"[cleanup] Could not delete {fpath}: {e}")
        cleared.append("generated PDFs")

    return cleared


# ── ImageKit cleanup ───────────────────────────────────────────────────────

def _clear_imagekit() -> str:
    """Delete all files in /ecg_plots/ and /xray_plots/ on ImageKit."""
    try:
        from services.imagekit_client import get_imagekit
        ik = get_imagekit()
        deleted_count = 0

        for folder in ["/ecg_plots/", "/xray_plots/"]:
            # List files in folder
            try:
                if hasattr(ik, "list_files"):
                    response = ik.list_files({"path": folder})
                    files = getattr(response, "list", response) or []
                else:
                    files = []
            except Exception:
                files = []

            for file in files:
                file_id = getattr(file, "file_id", None) or getattr(file, "fileId", None)
                if not file_id and isinstance(file, dict):
                    file_id = file.get("fileId") or file.get("file_id")
                if not file_id:
                    continue
                try:
                    if hasattr(ik, "delete_file"):
                        ik.delete_file(file_id)
                    elif hasattr(ik, "files"):
                        ik.files.delete(file_id)
                    deleted_count += 1
                except Exception as e:
                    print(f"[cleanup] ImageKit delete error for {file_id}: {e}")

        msg = f"ImageKit: deleted {deleted_count} file(s)"
        print(f"[cleanup] {msg}")
        return msg

    except Exception as e:
        msg = f"ImageKit cleanup failed: {e}"
        print(f"[cleanup] {msg}")
        return msg


# ── ThingSpeak cleanup ─────────────────────────────────────────────────────

def _clear_thingspeak() -> str:
    """
    ThingSpeak has no delete API for individual entries.
    We write a zeroed entry to mark the channel as reset,
    and clear the channel feed via the clear API if available.
    """
    try:
        s = get_settings()
        if not s.thingspeak_write_api_key:
            return "ThingSpeak: no API key configured"

        # Clear the entire channel feed (ThingSpeak bulk delete)
        clear_url = f"https://api.thingspeak.com/channels/{s.thingspeak_channel_id}/feeds.json"
        resp = requests.delete(
            clear_url,
            params={"api_key": s.thingspeak_write_api_key},
            timeout=10,
        )

        if resp.status_code in (200, 204):
            msg = "ThingSpeak: channel feed cleared"
        else:
            # Fallback — write zeroed entry to mark reset
            params = {
                "api_key": s.thingspeak_write_api_key,
                "field1": "0",
                "field2": "0",
                "field3": "0",
                "field4": "0",
                "field5": "0",
            }
            requests.get("https://api.thingspeak.com/update", params=params, timeout=10)
            msg = f"ThingSpeak: wrote reset entry (clear returned {resp.status_code})"

        print(f"[cleanup] {msg}")
        return msg

    except Exception as e:
        msg = f"ThingSpeak cleanup failed: {e}"
        print(f"[cleanup] {msg}")
        return msg


# ── Public API ─────────────────────────────────────────────────────────────

def full_cleanup() -> dict:
    """
    Run complete cleanup across all storage layers.
    Returns a summary of what was cleared.
    """
    print("[cleanup] Starting full cleanup...")
    results = {}
    results["local"]      = _clear_local()
    results["imagekit"]   = _clear_imagekit()
    results["thingspeak"] = _clear_thingspeak()
    print("[cleanup] Full cleanup complete.")
    return results