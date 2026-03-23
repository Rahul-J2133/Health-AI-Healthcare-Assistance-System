"""
services/vector_store.py — Retriever using qdrant-client directly.

Bypasses LangChain's Qdrant vectorstore wrapper entirely to avoid
version compatibility issues (recreate_collection, .search() removal etc).

Implements a simple retriever that:
  1. Embeds the query with Ollama
  2. Searches Qdrant using client.search()  (or query_points() on newer clients)
  3. Returns LangChain Document objects so the rest of the RAG chain works unchanged
"""
from functools import lru_cache
from langchain_core.documents import Document
from qdrant_client import QdrantClient
from config import get_settings

COLLECTION_NAME = "medical_db"


def _get_embeddings():
    try:
        from langchain_ollama import OllamaEmbeddings
    except ImportError:
        from langchain_community.embeddings import OllamaEmbeddings
    s = get_settings()
    return OllamaEmbeddings(model="nomic-embed-text", base_url=s.ollama_url)


class _DirectRetriever:
    """Minimal retriever that queries Qdrant without LangChain's vectorstore layer."""

    def __init__(self, k: int = 3):
        self.k = k
        self._embeddings = _get_embeddings()
        self._client = QdrantClient(url=get_settings().qdrant_url)

    def invoke(self, query: str) -> list[Document]:
        try:
            vector = self._embeddings.embed_query(query)

            # Try new API first (qdrant-client >= 1.7), fall back to legacy
            try:
                results = self._client.query_points(
                    collection_name=COLLECTION_NAME,
                    query=vector,
                    limit=self.k,
                ).points
            except AttributeError:
                results = self._client.search(
                    collection_name=COLLECTION_NAME,
                    query_vector=vector,
                    limit=self.k,
                )

            return [
                Document(
                    page_content=r.payload.get("page_content", ""),
                    metadata=r.payload.get("metadata", {}),
                )
                for r in results
            ]
        except Exception as e:
            print(f"[vector_store] Retrieval error: {e}")
            return []

    # Alias so code that calls .get_relevant_documents() still works
    def get_relevant_documents(self, query: str) -> list[Document]:
        return self.invoke(query)


@lru_cache()
def get_retriever() -> _DirectRetriever:
    return _DirectRetriever(k=3)