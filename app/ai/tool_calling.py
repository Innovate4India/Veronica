"""Provider-neutral bounded tool orchestration through ToolRegistry."""

import re
from collections.abc import Sequence
from copy import deepcopy
from typing import Protocol, cast

from app.ai.base import (
    AIProviderError,
    AssistantResponse,
    ChatMessage,
    ConversationMessage,
    ProviderCapabilityError,
    ToolCall,
    ToolDefinition,
    ToolErrorPayload,
    ToolResultPayload,
)
from app.tools import JSONValue, Tool, ToolRegistry, ToolResult, ToolStatus

_DEFAULT_MAX_TOOL_ITERATIONS = 4
_WEB_SEARCH_RESULT_COUNT = re.compile(r"[0-9]{1,3}\Z")


class ToolProvider(Protocol):
    """Provider-neutral tool loop protocol."""

    def generate_provider_tool_response(
        self,
        messages: Sequence[ConversationMessage],
        tools: Sequence[ToolDefinition],
    ) -> AssistantResponse: ...


class ToolCallingServiceError(AIProviderError):
    """Raised when the tool loop cannot safely produce a final answer."""


class ToolCallingService:
    """Run a bounded provider→registry→provider exchange."""

    def __init__(
        self,
        provider: ToolProvider,
        registry: ToolRegistry,
        *,
        max_tool_iterations: int = _DEFAULT_MAX_TOOL_ITERATIONS,
    ) -> None:
        if max_tool_iterations < 1:
            raise ValueError("max_tool_iterations must be at least 1.")
        if not callable(getattr(provider, "generate_provider_tool_response", None)):
            raise ProviderCapabilityError(
                "The selected provider does not support provider-neutral tool calling."
            )
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
            list[ConversationMessage],
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
            response = self._provider.generate_provider_tool_response(
                conversation,
                definitions,
            )
            response = _normalize_assistant_response(response)
            if not response.requests_tools:
                return _require_final_text(response)
            screen_call_in_batch = any(
                call.name == "screen_understanding"
                for call in response.tool_calls
            )
            conversation.append(response)
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
                conversation.append(_tool_result_payload(call, result))
            if screen_call_in_batch:
                final_response = self._provider.generate_provider_tool_response(
                    conversation,
                    (),
                )
                final_response = _normalize_assistant_response(final_response)
                if final_response.requests_tools:
                    raise ToolCallingServiceError(
                        "The provider returned a tool request after screen understanding."
                    )
                return _require_final_text(final_response)

        final_response = self._provider.generate_provider_tool_response(
            conversation,
            (),
        )
        final_response = _normalize_assistant_response(final_response)
        if final_response.requests_tools:
            raise ToolCallingServiceError(
                "The provider returned a tool request after the tool-call limit."
            )
        return _require_final_text(final_response)


def _tool_definition(
    tool: Tool,
    parameters_schema: dict[str, JSONValue] | None,
) -> ToolDefinition:
    if parameters_schema is None:
        raise ToolCallingServiceError(
            "A registered tool has no parameter schema."
        )
    schema = cast(dict[str, object], parameters_schema)
    return {
        "name": tool.name,
        "description": tool.description,
        "parameters": schema,
    }


def _execute_call(registry: ToolRegistry, call: ToolCall) -> ToolResult:
    if call.malformed or call.name is None:
        return ToolResult.failure(
            ToolStatus.VALIDATION_FAILURE,
            "The provider returned a malformed tool call.",
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


def _normalize_assistant_response(response: object) -> AssistantResponse:
    """Accept only explicit provider-neutral responses or pre-adapted values."""
    if not isinstance(response, AssistantResponse):
        raise ToolCallingServiceError(
            "The provider returned an unknown tool-response type."
        )
    if not isinstance(response.content, str):
        raise ToolCallingServiceError(
            "The provider returned invalid assistant text."
        )
    if not isinstance(response.tool_calls, (tuple, list)):
        raise ToolCallingServiceError(
            "The provider returned invalid tool calls."
        )
    calls: list[ToolCall] = []
    for call in response.tool_calls:
        if not isinstance(call, ToolCall):
            raise ToolCallingServiceError(
                "The provider returned a malformed tool call."
            )
        if call.malformed:
            calls.append(ToolCall(call.name, None, malformed=True))
            continue
        if call.name is None or not isinstance(call.name, str) or not call.name.strip():
            raise ToolCallingServiceError(
                "The provider returned a malformed tool call."
            )
        try:
            validated_call = ToolCall(call.name, call.arguments)
        except ValueError as error:
            raise ToolCallingServiceError(
                "The provider returned invalid tool-call arguments."
            ) from error
        calls.append(validated_call)
    return AssistantResponse(
        content=response.content,
        tool_calls=tuple(calls),
    )


def _tool_result_payload(
    call: ToolCall,
    result: ToolResult,
) -> ToolResultPayload:
    error = None
    if result.error is not None:
        error = ToolErrorPayload(
            code=result.error.code.value,
            message=result.error.message,
        )
    return ToolResultPayload(
        tool_name=call.name or "",
        status=result.status.value,
        data=result.data if error is None else None,
        error=error,
    )


def _require_final_text(response: AssistantResponse) -> str:
    if not response.content.strip():
        raise ToolCallingServiceError(
            "The provider did not return a final assistant text response."
        )
    return response.content.strip()


def __getattr__(name: str) -> object:
    if name == "OllamaToolCallingService":
        from app.ai.ollama_tool_compat import OllamaToolCallingService

        return OllamaToolCallingService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
