"""Provider-neutral interfaces for AI providers and tool conversations."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Iterator, Literal, Protocol, TypedDict, runtime_checkable

from PIL import Image

_MAX_JSON_NESTING_DEPTH = 100


class ChatMessage(TypedDict):
    """A role-tagged text message in a conversation."""

    role: Literal["system", "user", "assistant"]
    content: str


def _is_json_value(value: object) -> bool:
    pending: list[tuple[object, int, bool]] = [(value, 0, False)]
    active_containers: set[int] = set()
    while pending:
        current, depth, is_exit = pending.pop()
        if is_exit:
            active_containers.remove(id(current))
            continue
        if current is None or isinstance(current, (bool, int, str)):
            continue
        if isinstance(current, float):
            if not math.isfinite(current):
                return False
            continue
        if isinstance(current, list):
            children = current
        elif isinstance(current, dict):
            if not all(isinstance(key, str) for key in current):
                return False
            children = list(current.values())
        else:
            return False

        child_depth = depth + 1
        if child_depth > _MAX_JSON_NESTING_DEPTH:
            return False
        identity = id(current)
        if identity in active_containers:
            return False
        active_containers.add(identity)
        pending.append((current, depth, True))
        pending.extend((child, child_depth, False) for child in children)
    return True


def _is_json_object(value: object) -> bool:
    return isinstance(value, dict) and _is_json_value(value)


@dataclass(frozen=True)
class ToolCall:
    """A provider-neutral tool call before registry validation."""

    name: str | None
    arguments: object
    malformed: bool = False

    def __post_init__(self) -> None:
        if self.name is not None and (
            not isinstance(self.name, str) or not self.name.strip()
        ):
            raise ValueError("Tool call names must be non-empty strings.")
        if self.malformed:
            if self.arguments is not None:
                raise ValueError("Malformed tool calls must not include arguments.")
            return
        if not _is_json_object(self.arguments):
            raise ValueError("Tool call arguments must be a JSON object.")


@runtime_checkable
class ToolCallTextParser(Protocol):
    """Optional adapter for provider-specific tool requests returned as text."""

    def parse_tool_call_text(self, content: str) -> ToolCall | None:
        ...


@dataclass(frozen=True)
class AssistantResponse:
    """Provider-neutral assistant text plus optional tool calls."""

    content: str
    tool_calls: tuple[ToolCall, ...] | list[ToolCall] = ()

    @property
    def requests_tools(self) -> bool:
        return bool(self.tool_calls)


class ToolDefinition(TypedDict):
    name: str
    description: str
    parameters: dict[str, object]


@dataclass(frozen=True)
class ToolErrorPayload:
    code: str
    message: str


@dataclass(frozen=True)
class ToolResultPayload:
    tool_name: str
    status: str
    data: object | None = None
    error: ToolErrorPayload | None = None


ConversationMessage = ChatMessage | AssistantResponse | ToolResultPayload


@dataclass(frozen=True)
class ProviderCapabilities:
    text: bool = False
    streaming: bool = False
    tools: bool = False
    vision: bool = False


@dataclass(frozen=True)
class ProviderMetadata:
    name: str
    kind: str
    model: str
    capabilities: ProviderCapabilities = field(
        default_factory=ProviderCapabilities
    )


class ProviderError(Exception):
    """Base provider-neutral AI provider failure."""


class ProviderConfigurationError(ProviderError):
    """Invalid provider configuration."""


class ProviderCapabilityError(ProviderError):
    """The selected provider does not implement a requested capability."""


class ProviderConnectionError(ProviderError):
    """The provider or local runtime cannot be reached."""


class ProviderTimeoutError(ProviderConnectionError):
    """A provider request exceeded its timeout."""


class ProviderResponseError(ProviderError):
    """The provider returned an invalid or unsuccessful response."""


class ProviderModelUnavailableError(ProviderResponseError):
    """A requested model is not available."""


class AIProviderError(ProviderError):
    """Base exception for AI provider failures."""


class AIProvider(ABC):
    """Abstract interface implemented by local AI providers."""

    @property
    def metadata(self) -> ProviderMetadata:
        """Stable provider identity and advertised capabilities."""
        return ProviderMetadata(
            name="unknown",
            kind="unknown",
            model="",
            capabilities=ProviderCapabilities(),
        )

    def list_models(self) -> tuple[str, ...]:
        """Return models available to the provider, if supported."""
        return ()

    def validate_startup(self) -> None:
        """Validate provider-owned startup configuration and model availability."""

    def health_check(self) -> bool:
        """Return whether the provider is ready to serve requests."""
        raise ProviderCapabilityError(
            "The provider does not implement a health check."
        )

    def create_vision_provider(self) -> VisionProvider | None:
        """Return this provider's vision adapter when vision is supported."""
        return None

    def generate_stream(
        self,
        messages: Sequence[ChatMessage],
    ) -> Iterator[str]:
        """Future-ready streaming interface; providers may fallback to one chunk."""
        yield self.generate_response(messages)

    @abstractmethod
    def generate_response(self, messages: Sequence[ChatMessage]) -> str:
        """Generate assistant text from a sequence of conversation messages."""


@dataclass(frozen=True)
class VisionRequest:
    """Provider-neutral request for one vision operation."""

    question: str
    image: Image.Image

    def __post_init__(self) -> None:
        if not isinstance(self.question, str) or not self.question.strip():
            raise ValueError("A non-empty vision question is required.")
        if not isinstance(self.image, Image.Image):
            raise TypeError("Vision requests require a PIL image.")


@dataclass(frozen=True)
class VisionResponse:
    """Provider-neutral text response from a vision operation."""

    text: str


@runtime_checkable
class VisionProvider(Protocol):
    """Structural boundary for provider-specific vision implementations."""

    @property
    def model_configured(self) -> bool:
        """Whether the provider has a vision model configured."""
        ...

    def model_available(self) -> bool:
        """Return whether the requested vision model is available."""
        ...

    def generate_vision(self, request: VisionRequest) -> VisionResponse:
        """Generate a text response for one image and question."""
        ...
