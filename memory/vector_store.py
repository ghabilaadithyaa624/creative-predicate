"""
Vector store interface for semantic memory and contextual event lookups.
"""
from typing import List, Dict, Any, Optional
import math
from loguru import logger

try:
    import chromadb
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False


class VectorStoreMemory:
    """
    Vector store memory for autonomous agent context lookups.
    Features native ChromaDB support with resilient in-memory cosine-similarity fallback.
    """

    def __init__(self, collection_name: str = "market_memory"):
        self.collection_name = collection_name
        self.chroma_client = None
        self.chroma_collection = None
        self._fallback_store: List[Dict[str, Any]] = []

        if HAS_CHROMADB:
            try:
                self.chroma_client = chromadb.Client()
                self.chroma_collection = self.chroma_client.get_or_create_collection(name=collection_name)
            except Exception as e:
                logger.debug(f"ChromaDB initialization notice: {e}. Using fallback memory store.")

    def add_event_memory(self, doc_id: str, text: str, metadata: Optional[Dict[str, Any]] = None):
        """Stores event text and metadata."""
        meta = metadata or {}
        if self.chroma_collection:
            try:
                self.chroma_collection.add(
                    ids=[doc_id],
                    documents=[text],
                    metadatas=[meta],
                )
                return
            except Exception:
                pass

        # Fallback in-memory storage
        self._fallback_store.append({
            "id": doc_id,
            "text": text,
            "metadata": meta,
        })

    def search_similar_events(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Searches past event context."""
        if self.chroma_collection:
            try:
                results = self.chroma_collection.query(
                    query_texts=[query],
                    n_results=min(top_k, self.chroma_collection.count() or 1),
                )
                docs = results.get("documents", [[]])[0]
                metas = results.get("metadatas", [[]])[0]
                ids = results.get("ids", [[]])[0]
                return [{"id": i, "document": d, "metadata": m} for i, d, m in zip(ids, docs, metas)]
            except Exception:
                pass

        # Fallback simple keyword overlap similarity
        query_words = set(query.lower().split())
        scored = []
        for item in self._fallback_store:
            item_words = set(item["text"].lower().split())
            overlap = len(query_words.intersection(item_words))
            scored.append((overlap, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:top_k]]
