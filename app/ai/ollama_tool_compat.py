"""Explicit backward-compatibility entry point for legacy Ollama tool clients."""

from app.ai.ollama_client import OllamaToolAdapter
from app.ai.tool_calling import ToolCallingService
from app.tools import ToolRegistry


class OllamaLegacyToolCallingService(ToolCallingService):
    """Adapt an explicitly selected legacy Ollama client to neutral orchestration."""

    def __init__(
        self,
        provider: object,
        registry: ToolRegistry,
        *,
        max_tool_iterations: int = 4,
    ) -> None:
        super().__init__(
            OllamaToolAdapter(provider),
            registry,
            max_tool_iterations=max_tool_iterations,
        )


OllamaToolCallingService = OllamaLegacyToolCallingService
