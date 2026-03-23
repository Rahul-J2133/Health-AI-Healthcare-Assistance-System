"""
ingest/watcher.py — Lightweight file watcher using only stdlib os.stat().
No watchdog dependency. Polls ./data/ every 3 seconds for .txt changes.

- File modified  → delete old chunks, upsert new ones
- File created   → upsert new chunks
- File deleted   → delete its chunks; wipe collection if none remain
- First startup  → full rebuild via update_vector_store()
"""
import os
import time
import uuid
import threading
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams, PointStruct,
    Filter, FieldCondition, MatchValue,
)
from langchain_community.document_loaders import TextLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import get_settings

COLLECTION_NAME = "medical_db"
POLL_INTERVAL   = 3.0   # seconds between scans
_rebuild_lock   = threading.Lock()


# ── Helpers ────────────────────────────────────────────────────────────────

def _get_client() -> QdrantClient:
    return QdrantClient(url=get_settings().qdrant_url)


def _get_embeddings():
    try:
        from langchain_ollama import OllamaEmbeddings
    except ImportError:
        from langchain_community.embeddings import OllamaEmbeddings
    return OllamaEmbeddings(model="nomic-embed-text", base_url=get_settings().ollama_url)


def _ensure_collection(client: QdrantClient, vector_size: int = 768) -> None:
    try:
        client.get_collection(COLLECTION_NAME)
    except Exception:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )


def _embed_and_upsert(client: QdrantClient, embeddings, chunks: list, source: str) -> None:
    texts   = [c.page_content for c in chunks]
    vectors = embeddings.embed_documents(texts)
    _ensure_collection(client, vector_size=len(vectors[0]))
    points  = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=vec,
            payload={"page_content": text, "metadata": {"source": source}},
        )
        for text, vec in zip(texts, vectors)
    ]
    client.upsert(collection_name=COLLECTION_NAME, points=points)


def _delete_file_chunks(client: QdrantClient, file_path: str) -> None:
    for variant in [file_path, str(Path(file_path).as_posix())]:
        try:
            client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=Filter(must=[
                    FieldCondition(key="metadata.source", match=MatchValue(value=variant))
                ]),
            )
        except Exception:
            pass
    print(f"[watcher] Removed chunks for: {file_path}")


def _upsert_file(file_path: str) -> None:
    client     = _get_client()
    embeddings = _get_embeddings()
    _delete_file_chunks(client, file_path)
    try:
        docs = TextLoader(file_path, encoding="utf-8").load()
    except Exception as e:
        print(f"[watcher] Failed to load {file_path}: {e}")
        return
    if not docs:
        return
    chunks = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100).split_documents(docs)
    if not chunks:
        return
    print(f"[watcher] Upserting {len(chunks)} chunks from: {file_path}")
    _embed_and_upsert(client, embeddings, chunks, file_path)
    print(f"[watcher] Done: {file_path}")


def _handle_deletion(file_path: str, watch_dir: str) -> None:
    client = _get_client()
    _delete_file_chunks(client, file_path)
    remaining = [f for f in os.listdir(watch_dir) if f.endswith(".txt")] if os.path.exists(watch_dir) else []
    if not remaining:
        try:
            client.delete_collection(COLLECTION_NAME)
            print("[watcher] No .txt files remaining — collection wiped.")
        except Exception:
            pass


# ── Full rebuild (startup only) ────────────────────────────────────────────

def update_vector_store(path: str) -> None:
    with _rebuild_lock:
        client     = _get_client()
        embeddings = _get_embeddings()
        print(f"[watcher] Full rebuild from: {path}")

        loader = DirectoryLoader(path, glob="**/*.txt", show_progress=False)
        docs   = loader.load()
        if not docs:
            print("[watcher] No .txt documents found — skipping.")
            return

        chunks = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100).split_documents(docs)
        if not chunks:
            print("[watcher] No chunks produced — skipping.")
            return

        print(f"[watcher] Indexing {len(chunks)} chunks...")
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass

        texts      = [c.page_content for c in chunks]
        vectors    = embeddings.embed_documents(texts)
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=len(vectors[0]), distance=Distance.COSINE),
        )
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=[
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vec,
                    payload={"page_content": text, "metadata": {"source": c.metadata.get("source", "")}},
                )
                for text, vec, c in zip(texts, vectors, chunks)
            ],
        )
        print(f"[watcher] Full rebuild complete. {len(chunks)} points indexed.")


# ── Polling watcher (replaces watchdog) ───────────────────────────────────

def _scan(watch_dir: str) -> dict[str, float]:
    """Return {filepath: mtime} for all .txt files in watch_dir."""
    result = {}
    if not os.path.exists(watch_dir):
        return result
    for fname in os.listdir(watch_dir):
        if fname.endswith(".txt"):
            full = os.path.join(watch_dir, fname)
            try:
                result[full] = os.stat(full).st_mtime
            except FileNotFoundError:
                pass
    return result


def _poll_loop(watch_dir: str, stop: threading.Event) -> None:
    print(f"[watcher] Polling '{watch_dir}' every {POLL_INTERVAL}s for .txt changes...")
    known = _scan(watch_dir)   # baseline snapshot

    while not stop.is_set():
        stop.wait(POLL_INTERVAL)
        if stop.is_set():
            break

        current = _scan(watch_dir)

        # Created or modified
        for path, mtime in current.items():
            if path not in known:
                print(f"[watcher] Created: {path}")
                threading.Thread(target=_safe_upsert, args=(path,), daemon=True).start()
            elif mtime != known[path]:
                print(f"[watcher] Modified: {path}")
                threading.Thread(target=_safe_upsert, args=(path,), daemon=True).start()

        # Deleted
        for path in known:
            if path not in current:
                print(f"[watcher] Deleted: {path}")
                threading.Thread(target=_safe_delete, args=(path, watch_dir), daemon=True).start()

        known = current

    print("[watcher] Stopped.")


def _safe_upsert(file_path: str) -> None:
    with _rebuild_lock:
        try:
            _upsert_file(file_path)
        except Exception as e:
            print(f"[watcher] Upsert error: {e}")


def _safe_delete(file_path: str, watch_dir: str) -> None:
    with _rebuild_lock:
        try:
            _handle_deletion(file_path, watch_dir)
        except Exception as e:
            print(f"[watcher] Delete error: {e}")


# ── Public API ─────────────────────────────────────────────────────────────

def start_watcher() -> None:
    s = get_settings()
    watch_dir = s.data_dir
    os.makedirs(watch_dir, exist_ok=True)
    stop = threading.Event()
    _poll_loop(watch_dir, stop)   # blocks the thread (called from daemon thread in main.py)


if __name__ == "__main__":
    start_watcher()