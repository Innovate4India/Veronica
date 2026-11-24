"""Provider-neutral interface for text-only AI providers."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Literal, TypedDict


class ChatMessage(TypedDict):
    """A role-tagged text message in a conversation."""

    role: Literal["system", "user", "assistant"]
    content: str


class AIProviderError(Exception):
    """Base exception for AI provider failures."""


class AIProvider(ABC):
    """Abstract interface implemented by local AI providers."""

    @abstractmethod
    def generate_response(self, messages: Sequence[ChatMessage]) -> str:
        """Generate assistant text from a sequence of conversation messages."""
