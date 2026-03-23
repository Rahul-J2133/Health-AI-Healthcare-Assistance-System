"""
routers/rag.py — RAG query with conversation history.
History persisted at ./temp/conversation.json.
"""
import json
import os
from datetime import datetime

from fastapi import APIRouter, Form
from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response

from services.vector_store import get_retriever
from services.llm import query_ollama

router = APIRouter()

HISTORY_FILE = "./temp/conversation.json"

SYSTEM_PROMPT = (
    "You are a friendly and caring medical AI assistant. "
    "You answer health-related questions clearly and compassionately. "
    "You remember the conversation and can answer follow-up questions. "
    "Use the provided medical context when relevant. "
    "If the context is not relevant, answer from general medical knowledge and say so."
)


def _load_history() -> list[dict]:
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_history(history: list[dict]) -> None:
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def _build_prompt(history: list[dict], context: str, question: str) -> str:
    lines = [SYSTEM_PROMPT, ""]
    if context.strip():
        lines += ["--- Relevant medical context ---", context, "--- End of context ---", ""]
    if history:
        lines.append("--- Conversation so far ---")
        for turn in history:
            lines.append(f"User: {turn['user']}")
            lines.append(f"Assistant: {turn['assistant']}")
        lines += ["--- End of conversation ---", ""]
    lines += [f"User: {question}", "Assistant:"]
    return "\n".join(lines)


@router.post("/get_response")
async def get_response(query: str = Form(...)):
    history = _load_history()
    retrieved_docs = get_retriever().invoke(query)
    context = "\n".join([doc.page_content for doc in retrieved_docs])
    prompt = _build_prompt(history, context, query)
    print("[RAG] Prompt:\n" + "-" * 60 + "\n" + prompt + "\n" + "-" * 60)
    answer = await query_ollama(prompt)
    history.append({"timestamp": datetime.now().isoformat(), "user": query, "assistant": answer})
    _save_history(history)
    source = retrieved_docs[0].page_content if retrieved_docs else "No source available."
    return Response(jsonable_encoder(json.dumps({"answer": answer, "source_document": source})))