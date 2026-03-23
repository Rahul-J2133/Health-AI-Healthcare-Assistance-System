# Docker Setup

## Folder structure required

```
your-project/
├── docker-compose.yml        ← place here
├── fastapi/                  ← your backend source
│   ├── main.py
│   ├── routers/
│   ├── services/
│   ├── ingest/
│   ├── models/
│   │   └── pneumonia_pred_self.h5   ← place your model here
│   ├── pdf/
│   ├── requirements.txt
│   ├── .env                  ← copy from .env.example and fill in
│   ├── Dockerfile            ← copy here
│   └── .dockerignore         ← copy here
└── frontend/                 ← your Next.js source
    ├── src/
    ├── package.json
    ├── Dockerfile.dev        ← copy here (rename from Dockerfile.frontend)
    └── .dockerignore         ← copy from .dockerignore.frontend
```

## First time setup

```bash
# 1. Place docker-compose.yml at the project root
# 2. Copy Dockerfile into fastapi/
# 3. Copy Dockerfile.frontend into frontend/ and rename to Dockerfile.dev
# 4. Copy .dockerignore into fastapi/.dockerignore
# 5. Copy .dockerignore.frontend into frontend/.dockerignore
# 6. Fill in fastapi/.env (copy from .env.example)

# Start everything
docker compose up --build
```

First boot pulls ~2GB of Ollama models (llama3.2:1b + nomic-embed-text).
Subsequent boots use the cached ollama_data volume — fast startup.

## Daily use

```bash
docker compose up          # start all services
docker compose down        # stop all services
docker compose down -v     # stop + wipe all volumes (fresh start)

docker compose logs -f backend    # tail backend logs
docker compose logs -f ollama     # watch model downloads
```

## How bind mounts work

| What changes | Effect |
|---|---|
| Edit any `.py` file in `fastapi/` | uvicorn auto-reloads the backend |
| Edit any `.tsx` file in `frontend/` | Next.js hot-reloads the page |
| Add `.txt` to `fastapi/data/` | Watcher re-indexes Qdrant automatically |

`node_modules` and `.next` are excluded from the bind mount via
anonymous volumes so the container's own install is used, not your
host machine's.

## Ports

| Service  | Port |
|---|---|
| Frontend | http://localhost:3000 |
| Backend  | http://localhost:8000 |
| Qdrant   | http://localhost:6333 |
| Ollama   | http://localhost:11434 |

## GPU support (optional)

If you have an NVIDIA GPU, add this to the ollama service in docker-compose.yml:

```yaml
  ollama:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
```