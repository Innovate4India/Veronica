"""Standard-library client for Ollama's local HTTP API."""

from __future__ import annotations

import base64
import json
import re
import socket
from io import BytesIO
from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass
from json import JSONDecodeError
from typing import TYPE_CHECKING, Literal, Protocol, TypedDict
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from app.ai.base import (
    AIProvider,
    AIProviderError,
    AssistantResponse,
    ChatMessage,
    ConversationMessage,
    ProviderCapabilities,
    ProviderConfigurationError,
    ProviderConnectionError,
    ProviderModelUnavailableError,
    ProviderMetadata,
    ProviderResponseError,
    ProviderTimeoutError,
    ToolCall,
    ToolDefinition,
    ToolResultPayload,
    VisionProvider,
    VisionRequest,
    VisionResponse,
)
from app.config import (
    OllamaConfig,
    load_ollama_config,
    load_ollama_vision_model,
)

if TYPE_CHECKING:
    from PIL import Image


class _LegacyOllamaVisionClient(Protocol):
    def list_models(self) -> tuple[str, ...]: ...

    def generate_vision_response(
        self,
        model: str,
        question: str,
        image: Image.Image,
    ) -> str: ...


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


class OllamaConfigurationError(ProviderConfigurationError, AIProviderError):
    """Raised when local Ollama settings are invalid or incomplete."""


class OllamaConnectionError(ProviderConnectionError, AIProviderError):
    """Raised when the local Ollama service cannot be reached."""


class OllamaTimeoutError(ProviderTimeoutError, OllamaConnectionError):
    """Raised when an Ollama HTTP request times out."""


class OllamaResponseError(ProviderResponseError, AIProviderError):
    """Raised when Ollama returns an unsuccessful or invalid response."""


class OllamaModelUnavailableError(
    ProviderModelUnavailableError,
    OllamaResponseError,
):
    """Raised when the selected local model is not available to Ollama."""


class OllamaClient(AIProvider):
    """Text-only client for a loopback Ollama server."""

    def __init__(self, config: OllamaConfig | None = None) -> None:
        self.config = config or load_ollama_config()
        self._validate_base_url(self.config.base_url)

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="Ollama",
            kind="ollama-local",
            model=self.config.model,
            capabilities=ProviderCapabilities(
                text=True,
                streaming=False,
                tools=True,
                vision=True,
            ),
        )

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

    @property
    def connection_error_message(self) -> str:
        return (
            "Veronica cannot reach the local AI engine. "
            "Please make sure Ollama is running."
        )

    def validate_startup(self) -> None:
        if not self.config.model:
            raise OllamaConfigurationError(
                "OLLAMA_MODEL is not configured. Choose and install a model "
                "explicitly, then set OLLAMA_MODEL to its name. For example:\n"
                "  ollama pull llama3.2\n"
                '  $env:OLLAMA_MODEL = "llama3.2"'
            )
        if not _model_is_installed(self.config.model, self.list_models()):
            raise OllamaModelUnavailableError(
                f"Configured model {self.config.model!r} is not installed locally. "
                f"Install it explicitly with: ollama pull {self.config.model}"
            )

    def create_vision_provider(self) -> VisionProvider:
        return OllamaVisionProvider(self, load_ollama_vision_model())

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

    def generate_provider_tool_response(
        self,
        messages: Sequence[ConversationMessage],
        tools: Sequence[ToolDefinition],
    ) -> AssistantResponse:
        """Provider-neutral tool entry point implemented by the Ollama adapter."""
        ollama_messages = _to_ollama_messages(messages)
        ollama_tools = tuple(_to_ollama_tool_definition(tool) for tool in tools)
        response = self.generate_tool_response(ollama_messages, ollama_tools)
        return _normalize_ollama_assistant_response(response)

    def parse_tool_call_text(self, content: str) -> ToolCall | None:
        """Parse legacy text-encoded tool requests at the Ollama boundary."""
        return _parse_legacy_tool_call_text(content)


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


class OllamaVisionProvider(VisionProvider):
    """Provider-neutral vision boundary around Ollama's existing vision API."""

    def __init__(
        self,
        client: OllamaClient,
        model: str,
    ) -> None:
        self._client = client
        self._model = model.strip()

    missing_model_message = (
        "Local screen understanding is unavailable because "
        "OLLAMA_VISION_MODEL is not configured."
    )
    connection_error_message = (
        "The local Ollama vision service is unavailable."
    )
    model_unavailable_message = (
        "The configured local vision model is unavailable."
    )
    model_not_installed_message = (
        "The configured local vision model is not installed in Ollama."
    )

    @property
    def model_configured(self) -> bool:
        return bool(self._model)

    def model_available(self) -> bool:
        if not self._model:
            return False
        installed = self._client.list_models()
        return _model_is_installed(self._model, installed)

    def generate_vision(self, request: VisionRequest) -> VisionResponse:
        text = self._client.generate_vision_response(
            self._model,
            request.question,
            request.image,
        )
        return VisionResponse(text=text)


class LegacyOllamaVisionProvider(VisionProvider):
    """Backward-compatible adapter for existing Ollama vision mocks and clients."""

    missing_model_message = (
        "Local screen understanding is unavailable because "
        "OLLAMA_VISION_MODEL is not configured."
    )
    connection_error_message = (
        "The local Ollama vision service is unavailable."
    )
    model_unavailable_message = (
        "The configured local vision model is unavailable."
    )
    model_not_installed_message = (
        "The configured local vision model is not installed in Ollama."
    )

    def __init__(
        self,
        client: _LegacyOllamaVisionClient,
        model: str,
    ) -> None:
        self._client = client
        self._model = model.strip()

    @property
    def model_configured(self) -> bool:
        return bool(self._model)

    def model_available(self) -> bool:
        if not self._model:
            return False
        installed = self._client.list_models()
        return _model_is_installed(self._model, installed)

    def generate_vision(self, request: VisionRequest) -> VisionResponse:
        text = self._client.generate_vision_response(
            self._model,
            request.question,
            request.image,
        )
        return VisionResponse(text=text)


class OllamaToolAdapter:
    """Translate neutral tool contracts to Ollama and back."""

    def __init__(self, provider: object) -> None:
        self._provider = provider

    def generate_provider_tool_response(
        self,
        messages: Sequence[ConversationMessage],
        tools: Sequence[ToolDefinition],
    ) -> AssistantResponse:
        ollama_messages = _to_ollama_messages(messages)
        ollama_tools = tuple(_to_ollama_tool_definition(tool) for tool in tools)
        generate = getattr(self._provider, "generate_tool_response", None)
        if not callable(generate):
            raise OllamaResponseError(
                "The Ollama compatibility provider does not support tool responses."
            )
        response = generate(ollama_messages, ollama_tools)
        if isinstance(response, AssistantResponse):
            return response
        if not isinstance(response, OllamaAssistantResponse):
            raise OllamaResponseError(
                "The Ollama compatibility provider returned an invalid tool response."
            )
        return _normalize_ollama_assistant_response(response)


def _model_is_installed(model: str, installed_models: tuple[str, ...]) -> bool:
    normalized = model.casefold()
    installed = {name.casefold() for name in installed_models}
    if ":" in normalized:
        return normalized in installed
    return normalized in installed or f"{normalized}:latest" in installed


def _to_ollama_messages(
    messages: Sequence[ConversationMessage],
) -> list[OllamaChatMessage]:
    converted: list[OllamaChatMessage] = []
    for message in messages:
        if isinstance(message, dict):
            role = message.get("role")
            content = message.get("content")
            if role not in {"system", "user", "assistant"}:
                raise OllamaResponseError(
                    "The provider-neutral conversation contains an invalid role."
                )
            if not isinstance(content, str):
                raise OllamaResponseError(
                    "The provider-neutral conversation contains invalid content."
                )
            converted.append(OllamaChatMessage(role=role, content=content))
        elif isinstance(message, AssistantResponse):
            item = OllamaChatMessage(
                role="assistant",
                content=message.content,
            )
            if message.tool_calls:
                item["tool_calls"] = [
                    OllamaToolCall(
                        name=call.name,
                        arguments=call.arguments,
                        malformed=call.malformed,
                    ).to_message_payload()
                    for call in message.tool_calls
                ]
            converted.append(item)
        elif isinstance(message, ToolResultPayload):
            payload: dict[str, object] = {"status": message.status}
            if message.error is not None:
                payload["error"] = {
                    "code": message.error.code,
                    "message": message.error.message,
                }
            else:
                payload["data"] = message.data
            converted.append(
                OllamaChatMessage(
                    role="tool",
                    content=json.dumps(
                        payload,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                )
            )
        else:
            raise OllamaResponseError(
                "The provider-neutral conversation contains an unsupported message."
            )
    return converted


def _to_ollama_tool_definition(
    tool: ToolDefinition,
) -> OllamaToolDefinition:
    if not isinstance(tool, dict):
        raise OllamaResponseError("The provider returned an invalid tool definition.")
    name = tool.get("name")
    description = tool.get("description")
    parameters = tool.get("parameters")
    if not isinstance(name, str) or not isinstance(description, str):
        raise OllamaResponseError("The provider returned an invalid tool definition.")
    if not isinstance(parameters, dict):
        raise OllamaResponseError("The provider returned an invalid tool schema.")
    return OllamaToolDefinition(
        type="function",
        function=OllamaFunctionDefinition(
            name=name,
            description=description,
            parameters=parameters,
        ),
    )


def _normalize_ollama_assistant_response(
    response: OllamaAssistantResponse,
) -> AssistantResponse:
    content = response.content
    calls: list[ToolCall] = []
    for call in response.tool_calls:
        name = call.name
        if not isinstance(name, str) or not name.strip():
            calls.append(ToolCall(None, None, malformed=True))
            continue
        if call.malformed:
            calls.append(ToolCall(name, None, malformed=True))
            continue
        try:
            calls.append(ToolCall(name, call.arguments))
        except ValueError:
            calls.append(ToolCall(name, None, malformed=True))

    if not calls:
        text_call = _parse_legacy_tool_call_text(content)
        if text_call is not None:
            calls.append(text_call)
    return AssistantResponse(content="" if calls else content, tool_calls=tuple(calls))


_TOOL_CALL_ENVELOPE = re.compile(
    r'\{\s*"name"\s*:\s*"(?P<name>[^"]+)"\s*,\s*'
    r'"{1,2}(?:parameters|arguments)"{1,2}\s*:',
    re.DOTALL,
)


def _parse_legacy_tool_call_text(content: str) -> ToolCall | None:
    match = _TOOL_CALL_ENVELOPE.search(content)
    if match is None:
        return None

    name = match.group("name")
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return ToolCall(name, None, malformed=True)
    if not isinstance(payload, dict):
        return ToolCall(name, None, malformed=True)

    arguments_key = (
        "parameters" if "parameters" in payload else "arguments"
    )
    arguments = payload.get(arguments_key)
    malformed = (
        set(payload) != {"name", arguments_key}
        or payload.get("name") != name
        or not isinstance(arguments, dict)
    )
    if malformed:
        return ToolCall(name, None, malformed=True)
    try:
        return ToolCall(name, arguments)
    except ValueError:
        return ToolCall(name, None, malformed=True)
