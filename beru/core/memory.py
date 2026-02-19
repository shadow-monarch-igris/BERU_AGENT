from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from beru.utils.config import get_config
from beru.utils.logger import get_logger

logger = get_logger("beru.memory")

try:
    import chromadb
    from chromadb.config import Settings

    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    chromadb = None  # type: ignore
    Settings = None  # type: ignore
    logger.warning("ChromaDB not available. Install with: pip install chromadb")

try:
    from sentence_transformers import SentenceTransformer

    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    SentenceTransformer = None  # type: ignore
    logger.warning(
        "sentence-transformers not available. Install with: pip install sentence-transformers"
    )


@dataclass
class MemoryEntry:
    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    embedding: Optional[List[float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }


class BaseMemory(ABC):
    @abstractmethod
    async def add(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        pass

    @abstractmethod
    async def search(self, query: str, n_results: int = 5) -> List[MemoryEntry]:
        pass

    @abstractmethod
    async def get(self, entry_id: str) -> Optional[MemoryEntry]:
        pass

    @abstractmethod
    async def delete(self, entry_id: str) -> bool:
        pass

    @abstractmethod
    async def clear(self) -> None:
        pass


class InMemoryStorage(BaseMemory):
    def __init__(self):
        self._entries: Dict[str, MemoryEntry] = {}
        self._counter = 0

    def _generate_id(self) -> str:
        self._counter += 1
        return f"mem_{self._counter:06d}"

    async def add(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        entry_id = self._generate_id()
        entry = MemoryEntry(
            id=entry_id,
            content=content,
            metadata=metadata or {},
        )
        self._entries[entry_id] = entry
        return entry_id

    async def search(self, query: str, n_results: int = 5) -> List[MemoryEntry]:
        results = []
        query_lower = query.lower()

        for entry in self._entries.values():
            if query_lower in entry.content.lower():
                results.append(entry)

        results.sort(key=lambda x: x.timestamp, reverse=True)
        return results[:n_results]

    async def get(self, entry_id: str) -> Optional[MemoryEntry]:
        return self._entries.get(entry_id)

    async def delete(self, entry_id: str) -> bool:
        if entry_id in self._entries:
            del self._entries[entry_id]
            return True
        return False

    async def clear(self) -> None:
        self._entries.clear()


class ChromaDBMemory(BaseMemory):
    def __init__(
        self,
        persist_directory: str = "./data/chromadb",
        collection_name: str = "beru_memory",
        embedding_model: str = "all-MiniLM-L6-v2",
    ):
        if not CHROMADB_AVAILABLE:
            raise ImportError("ChromaDB is not installed")

        self.persist_directory = Path(persist_directory)
        self.persist_directory.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.Client(  # type: ignore
            Settings(  # type: ignore
                chroma_db_impl="duckdb+parquet",
                persist_directory=str(self.persist_directory),
            )
        )

        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

        self.embedder = None
        if EMBEDDINGS_AVAILABLE:
            try:
                self.embedder = SentenceTransformer(embedding_model)  # type: ignore
                logger.info(f"Loaded embedding model: {embedding_model}")
            except Exception as e:
                logger.warning(f"Failed to load embedding model: {e}")

        self._counter = 0

    def _generate_id(self) -> str:
        self._counter += 1
        return f"mem_{self._counter:06d}"

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        if self.embedder:
            return self.embedder.encode(text).tolist()
        return None

    async def add(self, content: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        entry_id = self._generate_id()
        embedding = self._get_embedding(content)

        self.collection.add(
            ids=[entry_id],
            documents=[content],
            metadatas=[metadata or {}],
            embeddings=[embedding] if embedding else None,
        )

        return entry_id

    async def search(self, query: str, n_results: int = 5) -> List[MemoryEntry]:
        query_embedding = self._get_embedding(query)

        results = self.collection.query(
            query_texts=[query] if not query_embedding else None,
            query_embeddings=[query_embedding] if query_embedding else None,
            n_results=n_results,
        )

        entries = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                metadata_raw = (
                    results["metadatas"][0][i] if results["metadatas"] else {}
                )
                embedding_raw = results.get("embeddings")
                entry = MemoryEntry(
                    id=doc_id,
                    content=results["documents"][0][i] if results["documents"] else "",
                    metadata=dict(metadata_raw) if metadata_raw else {},  # type: ignore
                    embedding=list(embedding_raw[0][i]) if embedding_raw else None,  # type: ignore
                )
                entries.append(entry)

        return entries

    async def get(self, entry_id: str) -> Optional[MemoryEntry]:
        results = self.collection.get(ids=[entry_id])

        if results["ids"]:
            metadata_raw = results["metadatas"][0] if results["metadatas"] else {}
            return MemoryEntry(
                id=results["ids"][0],
                content=results["documents"][0] if results["documents"] else "",
                metadata=dict(metadata_raw) if metadata_raw else {},  # type: ignore
            )
        return None

    async def delete(self, entry_id: str) -> bool:
        try:
            self.collection.delete(ids=[entry_id])
            return True
        except Exception:
            return False

    async def clear(self) -> None:
        all_ids = self.collection.get()["ids"]
        if all_ids:
            self.collection.delete(ids=all_ids)


class ConversationMemory:
    def __init__(
        self,
        storage: Optional[BaseMemory] = None,
        max_history: int = 20,
    ):
        self.storage = storage or InMemoryStorage()
        self.max_history = max_history
        self._conversation_id: Optional[str] = None
        self._short_term: List[Dict[str, Any]] = []

    async def start_conversation(self, topic: str = "") -> str:
        self._conversation_id = await self.storage.add(
            content=f"Conversation started: {topic}",
            metadata={"type": "conversation_start", "topic": topic},
        )
        return self._conversation_id

    async def add_message(
        self,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        message = {
            "role": role,
            "content": content,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
        }
        self._short_term.append(message)

        if len(self._short_term) > self.max_history:
            self._short_term.pop(0)

        return await self.storage.add(
            content=content,
            metadata={
                "conversation_id": self._conversation_id,
                "role": role,
                **(metadata or {}),
            },
        )

    async def recall(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        entries = await self.storage.search(query, n_results)
        return [e.to_dict() for e in entries]

    def get_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        return self._short_term[-limit:]

    async def summarize(self) -> str:
        if not self._short_term:
            return "No conversation history"

        summary_parts = []
        for msg in self._short_term[-5:]:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")[:200]
            summary_parts.append(f"{role}: {content}")

        return "\n".join(summary_parts)

    async def clear(self) -> None:
        self._short_term.clear()
        await self.storage.clear()


def create_memory(
    memory_type: Optional[str] = None,
    **kwargs,
) -> BaseMemory:
    config = get_config()
    memory_type = memory_type or config.memory.type

    if memory_type == "chromadb":
        if not CHROMADB_AVAILABLE:
            logger.warning("ChromaDB not available, falling back to in-memory storage")
            return InMemoryStorage()
        return ChromaDBMemory(
            persist_directory=kwargs.get(
                "persist_directory", config.memory.persist_directory
            ),
            collection_name=kwargs.get(
                "collection_name", config.memory.collection_name
            ),
            embedding_model=kwargs.get(
                "embedding_model", config.memory.embedding_model
            ),
        )

    return InMemoryStorage()


_memory: Optional[BaseMemory] = None
_conversation_memory: Optional[ConversationMemory] = None


def get_memory() -> BaseMemory:
    global _memory
    if _memory is None:
        _memory = create_memory()
    return _memory


def get_conversation_memory() -> ConversationMemory:
    global _conversation_memory
    if _conversation_memory is None:
        _conversation_memory = ConversationMemory(storage=get_memory())
    return _conversation_memory
