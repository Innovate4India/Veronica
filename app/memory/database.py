"""SQLite database setup and local connection management."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from collections.abc import Generator


class MemoryDatabase:
    """Create the local memory schema and provide short-lived connections."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL CHECK (length(trim(content)) > 0),
                    category TEXT NOT NULL DEFAULT 'general',
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Yield a connection that commits on success and always closes."""
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()
