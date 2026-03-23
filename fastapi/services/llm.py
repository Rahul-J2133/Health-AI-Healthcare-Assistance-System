"""
services/llm.py — Ollama LLM query logic, isolated from routing code.
"""
import httpx
from config import get_settings


async def query_ollama(prompt: str) -> str:
    """Send a prompt to the local Ollama instance and return the response text."""
    s = get_settings()
    payload = {
        "model": s.ollama_model,
        "prompt": prompt,
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(f"{s.ollama_url}/api/generate", json=payload)
        response.raise_for_status()
        return response.json()["response"]
