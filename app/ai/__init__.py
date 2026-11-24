"""Local language-model provider interfaces and services."""

from app.ai.base import AIProvider, AIProviderError, ChatMessage
from app.ai.personality import VERONICA_SYSTEM_PROMPT
from app.ai.ollama_client import (
    OllamaAssistantResponse,
    OllamaAssistantToolMessage,
    OllamaChatMessage,
    OllamaClient,
    OllamaConfigurationError,
    OllamaConnectionError,
    OllamaModelUnavailableError,
    OllamaResponseError,
    OllamaTimeoutError,
    OllamaToolCall,
    OllamaToolCallPayload,
    OllamaToolDefinition,
    OllamaToolResultMessage,
)
from app.ai.service import AIService, AIServiceError
from app.ai.tool_calling import OllamaToolCallingService, ToolCallingServiceError
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
    "AIService",
    "AIServiceError",
    "ChatMessage",
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
    "LocalVisionService",
    "RoleDecision",
    "TeachingSubject",
    "TeachingSession",
    "TeachingLanguage",
    "VeronicaRole",
    "ToolCallingServiceError",
    "VERONICA_SYSTEM_PROMPT",
]
