"""Data models for persistent user memories."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Memory:
    """A single user-approved persistent memory."""

    id: int
    content: str
    category: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class MemoryIntent:
    """Conservative application-recognized natural-language memory request."""

    kind: Literal["none", "remember", "ambiguous"]
    content: str = ""
