# fastapi/Dockerfile — Dev image with live reload via bind mount
FROM python:3.11-slim

WORKDIR /app

# System libs for OpenCV, ReportLab
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgomp1 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (cached layer — only re-runs if requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir langchain-core langchain-ollama

# Source is bind-mounted at runtime — no COPY needed
# Directories created here are overridden by named volumes in compose
RUN mkdir -p ./data ./temp ./generated_pdfs

EXPOSE 8000

# --reload watches for file changes in the bind-mounted source
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]