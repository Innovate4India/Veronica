"""Contracts for application chat operations."""

from dataclasses import dataclass
from typing import Protocol


class ApplicationError(Exception):
    """Base class for application-layer failures."""


class InvalidChatRequestError(ApplicationError):
    """Raised when a chat request cannot be executed."""


@dataclass(frozen=True)
class ChatRequest:
    message: str


@dataclass(frozen=True)
class ChatResult:
    response: str


class ChatService(Protocol):
    def respond(self, user_message: str) -> str: ...

    def clear(self) -> None: ...

    @property
    def message_count(self) -> int: ...
