"""Standard-library client for Ollama's local HTTP API."""

from __future__ import annotations

import base64
import json
import socket
from io import BytesIO
from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass
from json import JSONDecodeError
from typing import TYPE_CHECKING, Literal, TypedDict
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from app.ai.base import AIProvider, AIProviderError, ChatMessage
from app.config import OllamaConfig, load_ollama_config

if TYPE_CHECKING:
    from PIL import Image


class OllamaFunctionDefinition(TypedDict):
    """Function signature in Ollama's native chat tools request format."""

    name: str
    description: str
    parameters: dict[str, object]


class OllamaToolDefinition(TypedDict):
    """Function tool definition accepted in /api/chat requests."""

    type: Literal["function"]
    function: OllamaFunctionDefinition


class OllamaToolCallFunction(TypedDict):
    """Function selected by the assistant, with its JSON arguments."""

    name: str
    arguments: object


class OllamaToolCallPayload(TypedDict):
    """Native tool-call item carried on an assistant chat message."""

    function: OllamaToolCallFunction


class OllamaChatMessage(TypedDict, total=False):
    """Message shapes used by the native Ollama tool-calling loop."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_calls: list[OllamaToolCallPayload]


class OllamaAssistantToolMessage(TypedDict):
    """Assistant call entry appended to the following model request."""

    role: Literal["assistant"]
    content: str
    tool_calls: list[OllamaToolCallPayload]


class OllamaToolResultMessage(TypedDict):
    """Structured tool outcome encoded as content for Ollama's tool role."""

    role: Literal["tool"]
    content: str


@dataclass(frozen=True)
class OllamaToolCall:
    """Parsed tool call; fields remain untrusted until registry validation."""

    name: str | None
    arguments: object
    malformed: bool = False

    def to_message_payload(self) -> OllamaToolCallPayload:
        """Return a safe, canonical tool-call shape for conversation context."""
        return {
            "function": {
                "name": self.name or "__malformed_tool_call__",
                "arguments": (
                    self.arguments if isinstance(self.arguments, dict) else {}
                ),
            }
        }


@dataclass(frozen=True)
class OllamaAssistantResponse:
    """Parsed assistant text and any native tool calls."""

    content: str
    tool_calls: tuple[OllamaToolCall, ...] = ()

    @property
    def requests_tools(self) -> bool:
        """Whether the assistant returned at least one tool-call item."""
        return bool(self.tool_calls)


class OllamaConfigurationError(AIProviderError):
    """Raised when local Ollama settings are invalid or incomplete."""


class OllamaConnectionError(AIProviderError):
    """Raised when the local Ollama service cannot be reached."""


class OllamaTimeoutError(OllamaConnectionError):
    """Raised when an Ollama HTTP request times out."""


class OllamaResponseError(AIProviderError):
    """Raised when Ollama returns an unsuccessful or invalid response."""


class OllamaModelUnavailableError(OllamaResponseError):
    """Raised when the selected local model is not available to Ollama."""


class OllamaClient(AIProvider):
    """Text-only client for a loopback Ollama server."""

    def __init__(self, config: OllamaConfig | None = None) -> None:
        self.config = config or load_ollama_config()
        self._validate_base_url(self.config.base_url)

    @staticmethod
    def _validate_base_url(base_url: str) -> None:
        try:
            parsed = urlsplit(base_url)
            hostname = parsed.hostname
        except ValueError as error:
            raise OllamaConfigurationError(
                "OLLAMA_BASE_URL must be a valid loopback HTTP URL."
            ) from error

        if (
            parsed.scheme != "http"
            or hostname not in {"localhost", "127.0.0.1", "::1"}
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise OllamaConfigurationError(
                "OLLAMA_BASE_URL must point to a local loopback HTTP service."
            )
        try:
            parsed.port
        except ValueError as error:
            raise OllamaConfigurationError(
                "OLLAMA_BASE_URL contains an invalid port."
            ) from error

    def _request_json(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: dict[str, object] | None = None,
    ) -> object:
        url = f"{self.config.base_url}/{path.lstrip('/')}"
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"} if data is not None else {},
            method=method,
        )
        try:
            with urlopen(request, timeout=self.config.timeout) as response:
                response_data = response.read()
        except HTTPError as error:
            raise OllamaResponseError(
                f"Ollama returned HTTP status {error.code}."
            ) from error
        except (TimeoutError, socket.timeout) as error:
            raise OllamaTimeoutError("The Ollama request timed out.") from error
        except URLError as error:
            if isinstance(error.reason, (TimeoutError, socket.timeout)):
                raise OllamaTimeoutError("The Ollama request timed out.") from error
            raise OllamaConnectionError(
                "Could not connect to the local Ollama service."
            ) from error
        except OSError as error:
            raise OllamaConnectionError(
                "Could not connect to the local Ollama service."
            ) from error

        try:
            return json.loads(response_data.decode("utf-8"))
        except (UnicodeDecodeError, JSONDecodeError) as error:
            raise OllamaResponseError(
                "Ollama returned a response that was not valid JSON."
            ) from error

    def list_models(self) -> tuple[str, ...]:
        """Return model names advertised by the local Ollama service."""
        response = self._request_json("/api/tags")
        if not isinstance(response, dict) or not isinstance(
            response.get("models"), list
        ):
            raise OllamaResponseError(
                "Ollama returned an invalid model-list response."
            )

        names: list[str] = []
        for model in response["models"]:
            if not isinstance(model, dict) or not isinstance(model.get("name"), str):
                raise OllamaResponseError(
                    "Ollama returned an invalid model-list response."
                )
            names.append(model["name"])
        return tuple(names)

    def health_check(self) -> bool:
        """Check the Ollama API and validate its model-list response."""
        self.list_models()
        return True

    def generate_response(self, messages: Sequence[ChatMessage]) -> str:
        """Ask the configured local model for a text-only chat response."""
        if not self.config.model:
            raise OllamaConfigurationError(
                "OLLAMA_MODEL is not configured. Select a local model first."
            )
        if not messages:
            raise ValueError("At least one chat message is required.")
        for message in messages:
            if (
                message.get("role") not in {"system", "user", "assistant"}
                or not isinstance(message.get("content"), str)
            ):
                raise ValueError("Each message needs a supported role and text content.")

        response = self._request_json(
            "/api/chat",
            method="POST",
            payload={
                "model": self.config.model,
                "messages": [dict(message) for message in messages],
                "stream": False,
            },
        )
        if not isinstance(response, dict):
            raise OllamaResponseError("Ollama returned an invalid chat response.")
        if response.get("error"):
            raise OllamaResponseError("Ollama reported an error for the chat request.")

        assistant_message = response.get("message")
        if (
            not isinstance(assistant_message, dict)
            or not isinstance(assistant_message.get("content"), str)
        ):
            raise OllamaResponseError(
                "Ollama returned a chat response without assistant text."
            )
        return assistant_message["content"]

    def generate_vision_response(
        self,
        model: str,
        question: str,
        image: Image.Image,
    ) -> str:
        """Send one in-memory image to the configured loopback Ollama server."""
        if not model.strip():
            raise OllamaConfigurationError(
                "OLLAMA_VISION_MODEL is not configured."
            )
        if not question.strip():
            raise ValueError("A non-empty vision question is required.")
        image_buffer = BytesIO()
        try:
            image.save(image_buffer, format="PNG")
            encoded_image = base64.b64encode(image_buffer.getvalue()).decode("ascii")
        finally:
            image_buffer.close()

        try:
            response = self._request_json(
                "/api/chat",
                method="POST",
                payload={
                    "model": model,
                    "messages": [
                        {
                            "role": "user",
                            "content": question,
                            "images": [encoded_image],
                        }
                    ],
                    "stream": False,
                },
            )
        except OllamaResponseError as error:
            if "HTTP status 404." in str(error):
                raise OllamaModelUnavailableError(
                    "The configured local vision model is unavailable."
                ) from None
            raise
        if isinstance(response, dict) and isinstance(response.get("error"), str):
            if "model" in response["error"].casefold() and "not found" in response["error"].casefold():
                raise OllamaModelUnavailableError(
                    "The configured local vision model is unavailable."
                )
        if not isinstance(response, dict) or response.get("error"):
            raise OllamaResponseError(
                "Ollama returned an invalid local vision response."
            )
        assistant_message = response.get("message")
        if (
            not isinstance(assistant_message, dict)
            or assistant_message.get("role") != "assistant"
            or not isinstance(assistant_message.get("content"), str)
            or not assistant_message["content"].strip()
        ):
            raise OllamaResponseError(
                "Ollama returned no valid text for the vision request."
            )
        return assistant_message["content"].strip()

    def generate_tool_response(
        self,
        messages: Sequence[OllamaChatMessage],
        tools: Sequence[OllamaToolDefinition],
    ) -> OllamaAssistantResponse:
        """Request one native tool-capable chat turn and parse its assistant message."""
        if not self.config.model:
            raise OllamaConfigurationError(
                "OLLAMA_MODEL is not configured. Select a local model first."
            )
        if not messages:
            raise ValueError("At least one chat message is required.")
        for message in messages:
            if (
                message.get("role") not in {"system", "user", "assistant", "tool"}
                or not isinstance(message.get("content", ""), str)
            ):
                raise ValueError("Each Ollama chat message needs a supported role.")
            calls = message.get("tool_calls")
            if calls is not None and (
                not isinstance(calls, list)
                or message.get("role") != "assistant"
            ):
                raise ValueError("Only assistant messages may contain tool calls.")
        payload: dict[str, object] = {
            "model": self.config.model,
            "messages": [dict(message) for message in messages],
            "stream": False,
        }
        if tools:
            payload["tools"] = [deepcopy(tool) for tool in tools]
        response = self._request_json(
            "/api/chat",
            method="POST",
            payload=payload,
        )
        if not isinstance(response, dict):
            raise OllamaResponseError("Ollama returned an invalid chat response.")
        if response.get("error"):
            raise OllamaResponseError("Ollama reported an error for the chat request.")
        assistant_message = response.get("message")
        if (
            not isinstance(assistant_message, dict)
            or assistant_message.get("role") != "assistant"
        ):
            raise OllamaResponseError(
                "Ollama returned a response without an assistant message."
            )
        content = assistant_message.get("content", "")
        if not isinstance(content, str):
            raise OllamaResponseError(
                "Ollama returned assistant content in an invalid format."
            )
        raw_calls = assistant_message.get("tool_calls")
        if raw_calls is None:
            return OllamaAssistantResponse(content=content)
        if not isinstance(raw_calls, list):
            return OllamaAssistantResponse(
                content=content,
                tool_calls=(OllamaToolCall(None, None, malformed=True),),
            )
        parsed_calls = tuple(_parse_tool_call(call) for call in raw_calls)
        return OllamaAssistantResponse(
            content=content,
            tool_calls=parsed_calls,
        )


def _parse_tool_call(value: object) -> OllamaToolCall:
    if not isinstance(value, dict):
        return OllamaToolCall(None, None, malformed=True)
    function = value.get("function")
    if not isinstance(function, dict):
        return OllamaToolCall(None, None, malformed=True)
    name = function.get("name")
    arguments = function.get("arguments")
    malformed = (
        not isinstance(name, str)
        or not name.strip()
        or not isinstance(arguments, dict)
    )
    return OllamaToolCall(
        name=name if isinstance(name, str) and name.strip() else None,
        arguments=arguments,
        malformed=malformed,
    )
