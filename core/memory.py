"""Utility classes for managing conversational memory.

This module contains implementations for short-term memory that keeps track of
recent dialogue turns and optional long-term memory backends.  The
``MemoryManager`` orchestrates the interaction between these memories and is
used by the dialogue orchestrator.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
import json
import sqlite3


@dataclass
class MemoryRecord:
    """Represents a single conversational message."""

    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Return a serialisable representation of the record."""
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class ShortTermMemory:
    """Keeps track of the latest dialogue turns in chronological order."""

    def __init__(self, max_length: int = 20) -> None:
        self.max_length = max_length
        self._messages: List[MemoryRecord] = []

    def add_message(self, record: MemoryRecord) -> None:
        """Add a message to the short-term buffer and trim the overflow."""
        self._messages.append(record)
        if len(self._messages) > self.max_length:
            overflow = len(self._messages) - self.max_length
            del self._messages[0:overflow]

    def get_recent(self, limit: Optional[int] = None) -> List[MemoryRecord]:
        """Return the most recent ``limit`` messages (all if ``None``)."""
        if limit is None or limit >= len(self._messages):
            return list(self._messages)
        return self._messages[-limit:]

    def clear(self) -> None:
        """Remove all stored messages."""
        self._messages.clear()

    def __iter__(self) -> Iterable[MemoryRecord]:
        return iter(self._messages)


class BaseLongTermMemory(ABC):
    """Abstract interface for pluggable long-term memory backends."""

    @abstractmethod
    def store_interaction(self, record: MemoryRecord) -> None:
        """Persist an interaction for later retrieval."""

    @abstractmethod
    def search(self, query: str, limit: int = 5) -> List[MemoryRecord]:
        """Return a list of relevant interactions based on ``query``."""


class SQLiteLongTermMemory(BaseLongTermMemory):
    """SQLite-based implementation of :class:`BaseLongTermMemory`.

    The database schema is intentionally simple and keeps the full JSON
    representation of the metadata column.  The class is small enough to be
    replaced with a vector store or a more advanced backend without changing
    the consumer interface.
    """

    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self._connection = sqlite3.connect(self.db_path)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        cursor = self._connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                metadata TEXT,
                timestamp TEXT NOT NULL
            )
            """
        )
        self._connection.commit()

    def store_interaction(self, record: MemoryRecord) -> None:
        cursor = self._connection.cursor()
        cursor.execute(
            """
            INSERT INTO interactions (role, content, metadata, timestamp)
            VALUES (?, ?, ?, ?)
            """,
            (
                record.role,
                record.content,
                json.dumps(record.metadata, ensure_ascii=False),
                record.timestamp.isoformat(),
            ),
        )
        self._connection.commit()

    def search(self, query: str, limit: int = 5) -> List[MemoryRecord]:
        cursor = self._connection.cursor()
        cursor.execute(
            """
            SELECT role, content, metadata, timestamp
            FROM interactions
            WHERE content LIKE ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (f"%{query}%", limit),
        )
        rows = cursor.fetchall()
        results: List[MemoryRecord] = []
        for role, content, metadata, timestamp in rows:
            metadata_dict = json.loads(metadata) if metadata else {}
            results.append(
                MemoryRecord(
                    role=role,
                    content=content,
                    metadata=metadata_dict,
                    timestamp=datetime.fromisoformat(timestamp),
                )
            )
        return results

    def close(self) -> None:
        self._connection.close()


class MemoryManager:
    """Aggregates short-term and optional long-term memories."""

    def __init__(
        self,
        short_term: Optional[ShortTermMemory] = None,
        long_term: Optional[BaseLongTermMemory] = None,
    ) -> None:
        self.short_term = short_term or ShortTermMemory()
        self.long_term = long_term

    def add_message(
        self,
        role: str,
        content: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        persist_long_term: bool = False,
    ) -> MemoryRecord:
        """Add a message to the short-term buffer and optionally persist it."""
        record = MemoryRecord(role=role, content=content, metadata=metadata or {})
        self.short_term.add_message(record)
        if persist_long_term and self.long_term is not None:
            self.long_term.store_interaction(record)
        return record

    def get_recent(self, limit: Optional[int] = None) -> List[MemoryRecord]:
        return self.short_term.get_recent(limit)

    def search_long_term(self, query: str, limit: int = 5) -> List[MemoryRecord]:
        if self.long_term is None:
            return []
        return self.long_term.search(query, limit)

    def clear(self) -> None:
        self.short_term.clear()

    def close(self) -> None:
        if hasattr(self.long_term, "close"):
            self.long_term.close()  # type: ignore[attr-defined]
