"""
config.py — Centralised settings from environment / .env file.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ImageKit
    imagekit_public_key: str = ""
    imagekit_private_key: str = ""
    imagekit_url_endpoint: str = ""

    # ThingSpeak
    thingspeak_channel_id: str = ""
    thingspeak_read_api_key: str = ""
    thingspeak_write_api_key: str = ""

    # Qdrant
    qdrant_url: str = "http://localhost:6333"

    # Ollama
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:1b"

    # Pneumonia model
    pneumonia_model_path: str = "./models/pneumonia_pred_self.h5"

    # Directories
    data_dir: str = "./data"
    pdf_output_dir: str = "./generated_pdfs"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # silently ignore unknown env vars like WATCH_DIR


@lru_cache()
def get_settings() -> Settings:
    return Settings()