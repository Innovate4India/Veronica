"""Explicit, privacy-conscious operations for local persistent memories."""

import re
import sqlite3
from pathlib import Path

from app.config import (
    MAX_RELEVANT_MEMORIES,
    MEMORY_DATABASE_PATH,
)
from app.memory.database import MemoryDatabase
from app.memory.models import Memory, MemoryIntent

_SENSITIVE_PATTERNS = (
    re.compile(
        r"\b(?:password|passwd|passphrase|api[\s_-]*key|access[\s_-]*token|"
        r"auth[\s_-]*token|refresh[\s_-]*token|token|secret|private[\s_-]*key)\b"
        r"\s*(?:is\s+|[:=]\s*)\S+",
        re.IGNORECASE,
    ),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", re.IGNORECASE),
    re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
)
_MEMORY_REQUESTS = (
    re.compile(r"^\s*remember\s+that\s+(.+?)\s*[.!?]?\s*$", re.IGNORECASE),
    re.compile(
        r"^\s*i\s+want\s+you\s+to\s+remember\s+that\s+(.+?)\s*[.!?]?\s*$",
        re.IGNORECASE,
    ),
    re.compile(r"^\s*please\s+remember\s+(.+?)\s*[.!?]?\s*$", re.IGNORECASE),
)
_AMBIGUOUS_REMEMBER = re.compile(
    r"^\s*(?:please\s+)?remember\b|^\s*i\s+want\s+you\s+to\s+remember\b",
    re.IGNORECASE,
)
_SEARCH_STOP_WORDS = {
    "a", "about", "am", "an", "are", "do", "does", "for", "i", "is",
    "me", "my", "of", "please", "the", "that", "to", "what", "which",
    "who", "you",
}
_SEARCH_WORD = re.compile(r"[^\W_]+", re.UNICODE)


class MemoryServiceError(Exception):
    """Raised when local memory storage cannot complete an operation."""


class SensitiveMemoryError(MemoryServiceError):
    """Raised when content appears to contain a credential or private secret."""


def contains_sensitive_credential(content: str) -> bool:
    """Detect obvious credentials without attempting broad secret classification."""
    return any(pattern.search(content) for pattern in _SENSITIVE_PATTERNS)


def detect_memory_intent(message: str) -> MemoryIntent:
    """Recognize only clear, explicit remember requests; never executes SQL."""
    for pattern in _MEMORY_REQUESTS:
        match = pattern.fullmatch(message)
        if match and match.group(1).strip().casefold() != "that":
            return MemoryIntent("remember", match.group(1).strip())
    if _AMBIGUOUS_REMEMBER.search(message):
        return MemoryIntent("ambiguous")
    return MemoryIntent("none")


def _memory_from_row(row: sqlite3.Row) -> Memory:
    return Memory(
        id=row["id"],
        content=row["content"],
        category=row["category"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class MemoryService:
    """Store and retrieve only user-approved memories on the local machine."""

    def __init__(
        self,
        database_path: Path | str = MEMORY_DATABASE_PATH,
        max_relevant_memories: int = MAX_RELEVANT_MEMORIES,
        *,
        database: MemoryDatabase | None = None,
    ) -> None:
        if max_relevant_memories < 1:
            raise ValueError("max_relevant_memories must be at least 1.")
        self.database = database or MemoryDatabase(database_path)
        self.max_relevant_memories = max_relevant_memories

    def save_memory(self, content: str, category: str = "general") -> Memory:
        """Persist one explicitly approved memory and return the stored record."""
        normalized_content = content.strip()
        normalized_category = category.strip()
        if not normalized_content:
            raise ValueError("Memory content must not be empty.")
        if not normalized_category:
            raise ValueError("Memory category must not be empty.")
        if contains_sensitive_credential(normalized_content):
            raise SensitiveMemoryError(
                "Credentials and secrets cannot be stored as assistant memories."
            )
        try:
            with self.database.connection() as connection:
                cursor = connection.execute(
                    "INSERT INTO memories (content, category) VALUES (?, ?)",
                    (normalized_content, normalized_category),
                )
                row = connection.execute(
                    "SELECT id, content, category, created_at, updated_at "
                    "FROM memories WHERE id = ?",
                    (cursor.lastrowid,),
                ).fetchone()
        except sqlite3.Error as error:
            raise MemoryServiceError("Could not save local memory.") from error
        if row is None:
            raise MemoryServiceError("The saved local memory could not be retrieved.")
        return _memory_from_row(row)

    def list_memories(self) -> list[Memory]:
        """Return all stored memories, newest first."""
        try:
            with self.database.connection() as connection:
                rows = connection.execute(
                    "SELECT id, content, category, created_at, updated_at "
                    "FROM memories ORDER BY id DESC"
                ).fetchall()
        except sqlite3.Error as error:
            raise MemoryServiceError("Could not list local memories.") from error
        return [_memory_from_row(row) for row in rows]

    def search_memories(
        self,
        query: str,
        limit: int | None = None,
    ) -> list[Memory]:
        """Find a limited set of memories matching meaningful query words."""
        maximum = self.max_relevant_memories if limit is None else limit
        if maximum < 1:
            raise ValueError("limit must be at least 1.")
        terms = [
            word.lower()
            for word in _SEARCH_WORD.findall(query)
            if word.lower() not in _SEARCH_STOP_WORDS
        ][:8]
        if not terms:
            return []

        conditions: list[str] = []
        parameters: list[object] = []
        for term in terms:
            escaped_term = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{escaped_term}%"
            conditions.append("(content LIKE ? ESCAPE '\\' OR category LIKE ? ESCAPE '\\')")
            parameters.extend((pattern, pattern))
        parameters.append(maximum)
        statement = (
            "SELECT id, content, category, created_at, updated_at FROM memories "
            f"WHERE {' OR '.join(conditions)} ORDER BY id DESC LIMIT ?"
        )
        try:
            with self.database.connection() as connection:
                rows = connection.execute(statement, parameters).fetchall()
        except sqlite3.Error as error:
            raise MemoryServiceError("Could not search local memories.") from error
        return [_memory_from_row(row) for row in rows]

    def delete_memory(self, memory_id: int) -> bool:
        """Delete one memory by ID; return whether a record was removed."""
        if memory_id < 1:
            raise ValueError("memory_id must be a positive integer.")
        try:
            with self.database.connection() as connection:
                cursor = connection.execute(
                    "DELETE FROM memories WHERE id = ?",
                    (memory_id,),
                )
        except sqlite3.Error as error:
            raise MemoryServiceError("Could not delete local memory.") from error
        return cursor.rowcount > 0

    def clear_all_memories(self) -> int:
        """Delete all stored memories and return the number removed."""
        try:
            with self.database.connection() as connection:
                cursor = connection.execute("DELETE FROM memories")
        except sqlite3.Error as error:
            raise MemoryServiceError("Could not clear local memories.") from error
        return cursor.rowcount
