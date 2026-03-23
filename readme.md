# HealthAI — AI-Driven, IoT-Enabled Personalized Healthcare Assistance System

A full-stack medical monitoring and assistance platform that combines a simulated patient vitals layer, a RAG-based medical chatbot, chest X-ray AI analysis, and automated Electronic Health Record (EHR) generation — all running locally with Docker.

---

## What This System Does

HealthAI is built around the idea that a patient's health data — vitals, ECG, imaging, clinical notes — should be immediately accessible to an AI assistant that can answer medical questions in context. The system has four distinct capabilities that work together:

**1. Real-Time Vitals Monitoring**
A background simulator continuously generates realistic patient vitals (body temperature, heart rate, SpO₂, humidity, room temperature) and writes them to the data store every 5 seconds. This simulates what an IoT sensor layer would do in a physical deployment. The dashboard reads these values live and displays them as gauge charts that update continuously.

**2. RAG Medical Chat**
The chatbot is powered by `llama3.2:1b` running locally through Ollama. When a user asks a health question, the system retrieves the most relevant chunks from a medical knowledge base using `nomic-embed-text` embeddings stored in Qdrant, builds a prompt that includes that context along with the full conversation history, and sends it to the LLM. Answers are grounded in actual medical literature, and follow-up questions work correctly because the conversation is remembered.

**3. Chest X-Ray Analysis**
Users can upload or capture a chest X-ray from their device camera. A pre-trained CNN model classifies the image as NORMAL or INFECTED (pneumonia). If infected, the model highlights the affected region. The result can be approved for inclusion in the patient's EHR.

**4. EHR PDF Generation**
When the user clicks Generate EHR, the system reads all stored patient data — latest vitals, ECG waveform, approved X-rays, clinical notes — and renders a professional multi-section medical PDF with normal reference ranges, abnormal value flagging, and a clinical disclaimer.

---

## Architecture

```
your-project/
├── docker-compose.yml
│
├── fastapi/                        ← Python backend (FastAPI)
│   ├── main.py                     ← App entry point, startup orchestration
│   ├── config.py                   ← Settings from .env
│   ├── pseudo_data_generator.py    ← Simulated vitals (replaces physical IoT sensors)
│   │
│   ├── routers/
│   │   ├── rag.py                  ← /get_response — RAG chat with history
│   │   ├── patient.py              ← /health-data, /reset_user_data, /new_session
│   │   ├── imaging.py              ← /predict, /approveForEHR, /unlabelled-stream
│   │   ├── ehr.py                  ← /generate-pdf
│   │   └── generator.py            ← /generator/start|stop|status
│   │
│   ├── services/
│   │   ├── llm.py                  ← Ollama query wrapper
│   │   ├── vector_store.py         ← Qdrant retriever (direct client)
│   │   ├── imagekit_client.py      ← ImageKit CDN upload
│   │   ├── thingspeak.py           ← ThingSpeak telemetry push
│   │   └── cleanup.py              ← Full wipe: local + cloud
│   │
│   ├── ingest/
│   │   ├── watcher.py              ← os.stat() polling → incremental Qdrant updates
│   │   └── ecg_default.py          ← Default ECG waveform seed data
│   │
│   ├── models/
│   │   └── pneumonia.py            ← CNN inference (TensorFlow CPU)
│   │
│   ├── pdf/
│   │   └── ehr_pdf_generator.py    ← Professional EHR PDF (ReportLab + matplotlib)
│   │
│   ├── data/                       ← Runtime patient data (Docker named volume)
│   ├── temp/                       ← Conversation history
│   └── generated_pdfs/             ← Output EHR PDFs
│
└── frontend/                       ← Next.js 14 frontend
    └── src/app/
        ├── page.tsx                ← / → profile setup + dashboard
        ├── RAG/page.tsx            ← /RAG → medical chat
        ├── XRAY/page.tsx           ← /XRAY → X-ray analysis
        └── components/
            └── Header.tsx          ← Navigation + EHR + Reset (present on all pages)
```

**Infrastructure:**

| Service  | Role                              | Image                |
|----------|-----------------------------------|----------------------|
| qdrant   | Vector database for RAG retrieval | qdrant/qdrant:latest |
| ollama   | Local LLM + embedding model       | ollama/ollama:latest |
| backend  | FastAPI application               | python:3.11-slim     |
| frontend | Next.js dashboard                 | node:20-alpine       |

---

## How Data Flows Through the System

```
pseudo_data_generator.py (background thread, every 5s)
  → writes firstREC.txt (body temp, HR, SpO2, humidity, room temp)

User (via RAG page)
  → POST /update_patient_info → appended to secondREC.txt

User (via XRAY page, after approving a result)
  → POST /approveForEHR → approved_xray_*.jpg saved locally
                        → uploaded to ImageKit CDN

ingest/watcher.py (background thread, polls every 3s)
  → detects .txt file changes via os.stat()
  → re-embeds only the changed file → upserts chunks into Qdrant
  → removes old chunks for that file before upserting new ones

GET /health-data       → reads firstREC.txt → JSON for dashboard gauges
GET /unlabelled-stream → reads ecg_data.json → array for ECG chart
POST /get_response     → embeds query → retrieves from Qdrant
                       → builds prompt with history + context
                       → queries llama3.2:1b via Ollama
GET /generate-pdf      → reads all of ./data/ → renders EHR PDF
```

The knowledge base and patient sensor data live in the same `./data/` directory. Any `.txt` file added there is automatically indexed into Qdrant within 3 seconds. The RAG chatbot then has that content available as context when answering questions.

---

## The Vitals Simulator

`pseudo_data_generator.py` starts automatically as a daemon thread when the server boots. It generates realistic vitals by applying small random variation around base values:

```python
BASE = {
    "body_temp": 36.8,   # °C  — normal resting temperature
    "humidity":  55.0,   # %   — comfortable indoor humidity
    "room_temp": 24.0,   # °C  — room temperature
    "spo2":      97.5,   # %   — healthy blood oxygen saturation
    "bpm":       72,     # BPM — normal resting heart rate
}
```

Each tick overwrites `firstREC.txt` with slightly varied values. The dashboard polls `/health-data` every 5 seconds and updates the gauges. This gives a live monitoring experience without physical hardware.

To change the tick speed or pause generation:

```
POST /generator/start?interval=2   ← faster updates
POST /generator/stop               ← pause
GET  /generator/status             ← check running state
```

This simulator is designed to be replaced by real IoT sensor data. Any device that can send HTTP POST requests to `/update_patient_info_esp` and `/update_ECG` with the correct JSON body will integrate seamlessly — the rest of the system is agnostic to whether the data came from a sensor or the simulator.

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) with Compose
- 8 GB RAM minimum (Ollama models use ~2.5 GB)
- ~5 GB free disk space (models + Docker images)
- [ImageKit](https://imagekit.io) account — free tier is sufficient
- [ThingSpeak](https://thingspeak.com) account — free tier is sufficient
- Trained pneumonia CNN model file (`.h5`)

---

## Quick Start

### 1. Project layout

```
your-project/
├── docker-compose.yml
├── fastapi/
│   ├── .env              ← fill in from step 2
│   ├── Dockerfile
│   └── models/
│       └── pneumonia_pred_self.h5   ← place your model here
└── frontend/
    └── Dockerfile.dev
```

### 2. Configure environment

Copy `.env.example` to `fastapi/.env`:

```env
# ImageKit — from imagekit.io → Developer Options → API Keys
IMAGEKIT_PUBLIC_KEY=public_xxxxxxxxxxxx
IMAGEKIT_PRIVATE_KEY=private_xxxxxxxxxxxx
IMAGEKIT_URL_ENDPOINT=https://ik.imagekit.io/your_id

# ThingSpeak — from thingspeak.com → My Channels → API Keys
THINGSPEAK_CHANNEL_ID=0000000
THINGSPEAK_WRITE_API_KEY=XXXXXXXXXXXXXXXX

# Path to your .h5 model inside the container
PNEUMONIA_MODEL_PATH=/app/models/pneumonia_pred_self.h5

# Your local timezone (for accurate timestamps)
TZ=Asia/Kolkata
```

### 3. Add medical knowledge files

Place `.txt` files in `fastapi/data/` before starting:

```
fastapi/data/
├── general_medicine.txt
├── respiratory_diseases.txt
└── cardiac_conditions.txt
```

Files added or edited while the server is already running are re-indexed automatically within 3 seconds.

### 4. Start everything

```bash
docker compose up --build
```

First boot pulls Ollama models (~1.6 GB total) and takes 5–10 minutes. Every boot after that starts in under 30 seconds because models are cached in the `ollama_data` volume.

| URL                             | What it is             |
|---------------------------------|------------------------|
| http://localhost:3000           | Frontend dashboard     |
| http://localhost:8000           | Backend API            |
| http://localhost:8000/docs      | Swagger API docs       |
| http://localhost:6333/dashboard | Qdrant collection UI   |

---

## Features

### Profile Setup

On first visit, the user enters their name, age, and gender. The profile is saved in browser localStorage. The moment a new profile is created, `POST /new_session` automatically wipes all data from the previous session — locally, on ImageKit, and on ThingSpeak — so sessions are fully isolated.

### Dashboard

- Live vitals gauges (body temperature, heart rate, SpO₂, humidity, room temperature) updated every 5 seconds
- ECG waveform chart from `ecg_data.json`
- Approve Vitals for EHR — uploads the current ECG plot and vitals to cloud storage
- Generate EHR — builds and downloads the PDF
- Reset Data — full wipe across all storage layers with confirmation dialog

### Medical Chat (`/RAG`)

- Conversational AI grounded in your `.txt` knowledge base
- Full conversation memory — follow-up questions work correctly
- Patient context panel to add personal notes that are stored and indexed automatically

### X-Ray Analysis (`/XRAY`)

- Upload an image file or capture from device camera
- CNN classifies as NORMAL or INFECTED with probability score
- Infected results show highlighted region
- Approve to include in next EHR generation

### EHR PDF

- Patient banner with auto-generated record ID
- Vitals cards with normal reference ranges; abnormal values flagged in red
- ECG waveform chart rendered from live data
- Up to 3 most recent approved X-rays with timestamps
- Full clinical notes history
- Abnormal values summary
- Professional medical disclaimer

---

## Session Isolation

When Reset Data is clicked or a new user logs in:

| Storage      | What gets cleared                                      |
|--------------|--------------------------------------------------------|
| Local        | All files in `./data/`, conversation history, generated PDFs |
| ImageKit     | All files in `/ecg_plots/` and `/xray_plots/` folders  |
| ThingSpeak   | Channel feed cleared via bulk delete API               |

After wiping, default seed files are written immediately so the dashboard renders with zeroed gauges rather than blank state.

---

## RAG Pipeline Detail

The RAG implementation bypasses LangChain's Qdrant vectorstore wrappers and uses `qdrant-client` directly. This avoids the version compatibility issues between LangChain and the Qdrant client that affected earlier versions.

**Indexing (watcher.py):**
```
.txt file modified
  → TextLoader reads file
  → RecursiveCharacterTextSplitter (chunk_size=1000, overlap=100)
  → OllamaEmbeddings.embed_documents() via nomic-embed-text
  → qdrant_client.delete() removes old chunks (keyed on metadata.source)
  → qdrant_client.upsert() writes new points
```

**Query (rag.py):**
```
User message
  → OllamaEmbeddings.embed_query()
  → qdrant_client.query_points() — top 3 by cosine similarity
  → prompt = system instructions + retrieved context + conversation history + question
  → httpx POST to Ollama /api/generate
  → answer saved to conversation.json
  → response returned
```

---

## API Reference

| Method | Endpoint                    | Description                                 |
|--------|-----------------------------|---------------------------------------------|
| GET    | `/health-data`              | Latest vitals as JSON                       |
| POST   | `/update_patient_info`      | Append clinical note to secondREC.txt       |
| POST   | `/update_patient_info_esp`  | Receive vitals (ESP32 or any HTTP client)   |
| POST   | `/update_ECG`               | Receive ECG waveform array                  |
| GET    | `/unlabelled-stream`        | Latest ECG array for chart                  |
| POST   | `/get_response`             | RAG chat — returns answer + source          |
| POST   | `/predict`                  | Pneumonia detection on uploaded X-ray       |
| GET    | `/approveForEHR`            | Upload ECG + vitals to cloud services       |
| POST   | `/approveForEHR`            | Upload approved X-ray to ImageKit           |
| GET    | `/generate-pdf`             | Build and download EHR PDF                  |
| POST   | `/new_session`              | Full cleanup on new user login              |
| POST   | `/reset_user_data`          | Full cleanup triggered by Reset button      |
| POST   | `/reset-knowledge`          | Rebuild Qdrant collection from scratch      |
| POST   | `/generator/start`          | Start vitals simulator                      |
| POST   | `/generator/stop`           | Stop vitals simulator                       |
| GET    | `/generator/status`         | Check if simulator is running               |

---

## Running Without Docker

```bash
# Qdrant
docker run -p 6333:6333 qdrant/qdrant

# Ollama
ollama pull llama3.2:1b
ollama pull nomic-embed-text
ollama serve

# Backend
cd fastapi
pip install -r requirements.txt
uvicorn main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

Add to `fastapi/.env`:
```env
QDRANT_URL=http://localhost:6333
OLLAMA_URL=http://localhost:11434
```

---

## Tech Stack

| Layer       | Technology                                   |
|-------------|----------------------------------------------|
| Frontend    | Next.js 14, TypeScript, Chart.js             |
| Backend     | FastAPI, Python 3.11                         |
| LLM         | Ollama — llama3.2:1b (local)                 |
| Embeddings  | Ollama — nomic-embed-text (local)            |
| Vector DB   | Qdrant (direct client, no wrapper)           |
| ML Model    | TensorFlow CPU — pre-trained CNN (.h5)       |
| PDF         | ReportLab + matplotlib                       |
| Cloud CDN   | ImageKit                                     |
| Telemetry   | ThingSpeak                                   |
| Containers  | Docker + Docker Compose                      |

---

## Troubleshooting

**Backend waits forever for nomic-embed-text**
Ollama is still pulling the model on first boot. Run `docker compose logs -f ollama` to watch progress. Once you see `[ollama] models ready.` the backend will proceed automatically.

**Gauges show 0.0 and never change**
The simulator starts with the server. Check `docker compose logs -f backend` for `[generator]` lines. If absent, look for startup errors earlier in the log.

**RAG returns "No source available"**
No `.txt` files are indexed. Add knowledge files to `fastapi/data/`. Confirm indexing at http://localhost:6333/dashboard — the `medical_db` collection point count should increase.

**X-ray prediction fails**
Ensure `pneumonia_pred_self.h5` is at `fastapi/models/` and `PNEUMONIA_MODEL_PATH=/app/models/pneumonia_pred_self.h5` is in `.env`.

**Timestamps show wrong time**
Set `TZ=Asia/Kolkata` (or your timezone) in `docker-compose.yml` under the backend `environment` block and restart.

**Reset returns 500 (Device or resource busy)**
The `./data/` directory is a Docker named volume mount point and cannot be deleted with `rmtree`. The reset endpoint correctly deletes file contents individually rather than the directory itself — if you see this error, ensure you are running the latest version of `routers/patient.py`.