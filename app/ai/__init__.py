"""Local language-model provider interfaces and services."""

from importlib import import_module

from app.ai.base import (
    AIProvider,
    AIProviderError,
    AssistantResponse,
    ChatMessage,
    ConversationMessage,
    ProviderCapabilities,
    ProviderCapabilityError,
    ProviderConfigurationError,
    ProviderConnectionError,
    ProviderMetadata,
    ProviderModelUnavailableError,
    ProviderResponseError,
    ProviderTimeoutError,
    ToolCall,
    ToolCallTextParser,
    ToolDefinition,
    ToolErrorPayload,
    ToolResultPayload,
    VisionProvider,
    VisionRequest,
    VisionResponse,
)
from app.ai.provider import create_provider, register_provider
from app.ai.veronica_provider import VeronicaModelProvider
from app.ai.personality import VERONICA_SYSTEM_PROMPT
from app.ai.service import AIService, AIServiceError
from app.ai.tool_calling import ToolCallingService, ToolCallingServiceError
from app.ai.vision import LocalVisionService
from app.ai.roles import (
    RoleDecision,
    TeachingLanguage,
    TeachingSubject,
    VeronicaRole,
)
from app.ai.teaching import TeachingSession

__all__ = [
    "AIProvider",
    "AIProviderError",
    "AssistantResponse",
    "AIService",
    "AIServiceError",
    "ChatMessage",
    "ConversationMessage",
    "ProviderCapabilities",
    "ProviderCapabilityError",
    "ProviderConfigurationError",
    "ProviderConnectionError",
    "ProviderMetadata",
    "ProviderModelUnavailableError",
    "ProviderResponseError",
    "ProviderTimeoutError",
    "ToolCall",
    "ToolCallTextParser",
    "ToolDefinition",
    "ToolErrorPayload",
    "ToolResultPayload",
    "VisionProvider",
    "VisionRequest",
    "VisionResponse",
    "OllamaToolAdapter",
    "OllamaVisionProvider",
    "LegacyOllamaVisionProvider",
    "create_provider",
    "register_provider",
    "VeronicaModelProvider",
    "OllamaClient",
    "OllamaAssistantResponse",
    "OllamaAssistantToolMessage",
    "OllamaChatMessage",
    "OllamaConfigurationError",
    "OllamaConnectionError",
    "OllamaModelUnavailableError",
    "OllamaResponseError",
    "OllamaTimeoutError",
    "OllamaToolCall",
    "OllamaToolCallPayload",
    "OllamaToolDefinition",
    "OllamaToolResultMessage",
    "OllamaToolCallingService",
    "OllamaLegacyToolCallingService",
    "ToolCallingService",
    "LocalVisionService",
    "RoleDecision",
    "TeachingSubject",
    "TeachingSession",
    "TeachingLanguage",
    "VeronicaRole",
    "ToolCallingServiceError",
    "VERONICA_SYSTEM_PROMPT",
]


_OLLAMA_CLIENT_EXPORTS = {
    "OllamaAssistantResponse",
    "OllamaAssistantToolMessage",
    "OllamaChatMessage",
    "OllamaClient",
    "OllamaConfigurationError",
    "OllamaConnectionError",
    "OllamaModelUnavailableError",
    "OllamaResponseError",
    "OllamaTimeoutError",
    "OllamaToolCall",
    "OllamaToolCallPayload",
    "OllamaToolDefinition",
    "OllamaToolResultMessage",
    "OllamaToolAdapter",
    "OllamaVisionProvider",
    "LegacyOllamaVisionProvider",
}


def __getattr__(name: str) -> object:
    if name in _OLLAMA_CLIENT_EXPORTS:
        module = import_module("app.ai.ollama_client")
        return getattr(module, name)
    if name in {"OllamaLegacyToolCallingService", "OllamaToolCallingService"}:
        module = import_module("app.ai.ollama_tool_compat")
        return getattr(module, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
