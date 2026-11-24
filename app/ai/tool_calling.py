"""Bounded orchestration between Ollama native tool calls and ToolRegistry."""

import json
import re
from collections.abc import Sequence
from copy import deepcopy
from typing import Protocol, cast

from app.ai.base import AIProviderError, ChatMessage
from app.ai.ollama_client import (
    OllamaAssistantResponse,
    OllamaAssistantToolMessage,
    OllamaChatMessage,
    OllamaToolCall,
    OllamaToolDefinition,
    OllamaToolResultMessage,
)
from app.tools import JSONValue, Tool, ToolRegistry, ToolResult, ToolStatus

_DEFAULT_MAX_TOOL_ITERATIONS = 4
_WEB_SEARCH_CONTENT_MARKER = re.compile(r'"name"\s*:\s*"web_search"')
_WEB_SEARCH_CONTENT_PREFIX = re.compile(
    r'^\s*\{\s*"name"\s*:\s*"web_search"\s*,'
)
_WEB_SEARCH_RESULT_COUNT = re.compile(r"[0-9]{1,3}\Z")
_TOOL_CALL_ENVELOPE = re.compile(
    r'\{\s*"name"\s*:\s*"[^"]+"\s*,\s*'
    r'"(?:parameters|arguments)"\s*:',
    re.DOTALL,
)


class OllamaToolProvider(Protocol):
    """The minimal Ollama API needed by the native tool loop."""

    def generate_tool_response(
        self,
        messages: Sequence[OllamaChatMessage],
        tools: Sequence[OllamaToolDefinition],
    ) -> OllamaAssistantResponse: ...


class ToolCallingServiceError(AIProviderError):
    """Raised when the tool loop cannot safely produce a final answer."""


class OllamaToolCallingService:
    """Run a bounded Ollama→registry→Ollama exchange without CLI integration."""

    def __init__(
        self,
        provider: OllamaToolProvider,
        registry: ToolRegistry,
        *,
        max_tool_iterations: int = _DEFAULT_MAX_TOOL_ITERATIONS,
    ) -> None:
        if max_tool_iterations < 1:
            raise ValueError("max_tool_iterations must be at least 1.")
        self._provider = provider
        self._registry = registry
        self._max_tool_iterations = max_tool_iterations
        self._last_turn_used_screen_understanding = False

    @property
    def last_turn_used_screen_understanding(self) -> bool:
        """Whether the latest tool turn included screen-derived output."""
        return self._last_turn_used_screen_understanding

    def respond(
        self,
        messages: Sequence[ChatMessage],
        *,
        allowed_tool_names: frozenset[str] | None = None,
    ) -> str:
        """Return a final assistant response after any registered tool round trips."""
        if not messages:
            raise ValueError("At least one chat message is required.")
        self._last_turn_used_screen_understanding = False
        conversation = cast(
            list[OllamaChatMessage],
            [deepcopy(dict(message)) for message in messages],
        )
        definitions = tuple(
            _tool_definition(
                tool,
                self._registry.parameters_schema_for(tool.name),
            )
            for tool in self._registry.list_tools()
            if allowed_tool_names is None or tool.name in allowed_tool_names
        )
        processed_tool_calls = 0
        while processed_tool_calls < self._max_tool_iterations:
            response = self._provider.generate_tool_response(
                conversation,
                definitions,
            )
            response = _parse_web_search_content_call(response)
            if not response.requests_tools:
                return _require_final_text(response)
            screen_call_in_batch = any(
                call.name == "screen_understanding"
                for call in response.tool_calls
            )
            conversation.extend(_assistant_tool_message(response))
            for call in response.tool_calls:
                if processed_tool_calls >= self._max_tool_iterations:
                    result = ToolResult.failure(
                        ToolStatus.LIMIT_REACHED,
                        "The maximum number of tool calls was reached.",
                    )
                elif (
                    self._last_turn_used_screen_understanding
                    or (
                        screen_call_in_batch
                        and call.name != "screen_understanding"
                    )
                ):
                    result = ToolResult.failure(
                        ToolStatus.UNAVAILABLE,
                        "Additional tools are not run after a screen request.",
                    )
                    processed_tool_calls += 1
                elif (
                    allowed_tool_names is not None
                    and call.name not in allowed_tool_names
                ):
                    result = ToolResult.failure(
                        ToolStatus.UNAVAILABLE,
                        "This tool was not explicitly requested for this turn.",
                    )
                    processed_tool_calls += 1
                else:
                    if call.name == "screen_understanding":
                        self._last_turn_used_screen_understanding = True
                    result = _execute_call(self._registry, call)
                    processed_tool_calls += 1
                conversation.append(
                    cast(
                        OllamaChatMessage,
                        OllamaToolResultMessage(
                            role="tool",
                            content=_serialize_tool_result(result),
                        ),
                    )
                )
            if screen_call_in_batch:
                final_response = self._provider.generate_tool_response(
                    conversation,
                    (),
                )
                final_response = _parse_web_search_content_call(final_response)
                if final_response.requests_tools:
                    raise ToolCallingServiceError(
                        "Ollama returned a tool request after screen understanding."
                    )
                return _require_final_text(final_response)

        final_response = self._provider.generate_tool_response(conversation, ())
        final_response = _parse_web_search_content_call(final_response)
        if final_response.requests_tools:
            raise ToolCallingServiceError(
                "Ollama returned a tool request after the tool-call limit."
            )
        return _require_final_text(final_response)


def _tool_definition(
    tool: Tool,
    parameters_schema: dict[str, JSONValue] | None,
) -> OllamaToolDefinition:
    if parameters_schema is None:
        raise ToolCallingServiceError(
            "A registered tool has no parameter schema."
        )
    schema = cast(dict[str, object], parameters_schema)
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": schema,
        },
    }


def _assistant_tool_message(
    response: OllamaAssistantResponse,
) -> list[OllamaChatMessage]:
    calls = [call.to_message_payload() for call in response.tool_calls]
    return [
        cast(
            OllamaChatMessage,
            OllamaAssistantToolMessage(
                role="assistant",
                content=response.content,
                tool_calls=calls,
            ),
        )
    ]


def _execute_call(registry: ToolRegistry, call: OllamaToolCall) -> ToolResult:
    if call.malformed or call.name is None:
        return ToolResult.failure(
            ToolStatus.VALIDATION_FAILURE,
            "Ollama returned a malformed tool call.",
        )
    arguments = call.arguments
    if call.name == "web_search" and isinstance(arguments, dict):
        result_count = arguments.get("max_results")
        if (
            isinstance(result_count, str)
            and _WEB_SEARCH_RESULT_COUNT.fullmatch(result_count) is not None
        ):
            arguments = dict(arguments)
            arguments["max_results"] = int(result_count)
    elif (
        call.name == "file_search"
        and isinstance(arguments, dict)
        and arguments.get("path") == ""
    ):
        arguments = {
            key: value
            for key, value in arguments.items()
            if key != "path"
        }
    return registry.execute(call.name, arguments)


def _parse_web_search_content_call(
    response: OllamaAssistantResponse,
) -> OllamaAssistantResponse:
    """Recognize only the exact legacy web_search JSON envelope in assistant text.

    This compatibility path does not repair malformed JSON. A malformed
    web_search-shaped envelope is converted to a rejected call so it cannot
    escape as user-facing text or be executed with guessed arguments.
    """
    content = response.content
    if response.requests_tools or not contains_web_search_tool_marker(content):
        return response
    if not _WEB_SEARCH_CONTENT_PREFIX.match(content):
        return _malformed_web_search_content_call()

    try:
        payload: object = json.loads(content)
    except json.JSONDecodeError:
        return _malformed_web_search_content_call()
    if not isinstance(payload, dict) or set(payload) != {"name", "parameters"}:
        return _malformed_web_search_content_call()
    if payload.get("name") != "web_search":
        return response

    arguments = payload.get("parameters")
    if not isinstance(arguments, dict):
        return OllamaAssistantResponse(
            content="",
            tool_calls=(OllamaToolCall("web_search", arguments, malformed=True),),
        )
    return OllamaAssistantResponse(
        content="",
        tool_calls=(OllamaToolCall("web_search", arguments),),
    )


def contains_web_search_tool_marker(content: str) -> bool:
    """Identify only output naming the registered web_search function."""
    return _WEB_SEARCH_CONTENT_MARKER.search(content) is not None


def contains_tool_call_envelope(content: str) -> bool:
    """Identify a raw JSON function-call envelope that must not be shown as prose."""
    return _TOOL_CALL_ENVELOPE.search(content) is not None


def _malformed_web_search_content_call() -> OllamaAssistantResponse:
    return OllamaAssistantResponse(
        content="",
        tool_calls=(OllamaToolCall("web_search", None, malformed=True),),
    )


def _serialize_tool_result(result: ToolResult) -> str:
    payload: dict[str, JSONValue] = {"status": result.status.value}
    if result.error is not None:
        payload["error"] = {
            "code": result.error.code.value,
            "message": result.error.message,
        }
    else:
        payload["data"] = result.data
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _require_final_text(response: OllamaAssistantResponse) -> str:
    if not response.content.strip():
        raise ToolCallingServiceError(
            "Ollama did not return a final assistant text response."
        )
    if contains_tool_call_envelope(response.content):
        raise ToolCallingServiceError(
            "Ollama returned a tool-call envelope as text; no tool was executed."
        )
    return response.content.strip()
