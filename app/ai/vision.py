"""Local Ollama vision orchestration for one explicitly requested screen capture."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.ai.ollama_client import (
    OllamaClient,
    OllamaConnectionError,
    OllamaModelUnavailableError,
    OllamaTimeoutError,
)
from app.tools.base import ToolUnavailableError
from app.tools.screenshot import capture_primary_screen

if TYPE_CHECKING:
    from PIL import Image


class _VisionClient(Protocol):
    def list_models(self) -> tuple[str, ...]: ...

    def generate_vision_response(
        self,
        model: str,
        question: str,
        image: Image.Image,
    ) -> str: ...


class LocalVisionService:
    """Use only the configured local Ollama model for a transient screen image."""

    def __init__(
        self,
        client: _VisionClient | OllamaClient,
        model: str,
    ) -> None:
        self._client = client
        self._model = model.strip()

    @property
    def model_configured(self) -> bool:
        return bool(self._model)

    def understand_primary_screen(self, question: str) -> str:
        """Capture, ask the preinstalled local model, then close the image."""
        if not self._model:
            raise ToolUnavailableError(
                "Local screen understanding is unavailable because "
                "OLLAMA_VISION_MODEL is not configured."
            )

        try:
            installed_models = self._client.list_models()
        except OllamaTimeoutError:
            raise TimeoutError("The local vision request timed out.") from None
        except OllamaModelUnavailableError:
            raise ToolUnavailableError(
                "The configured local vision model is unavailable."
            ) from None
        except OllamaConnectionError:
            raise ToolUnavailableError(
                "The local Ollama vision service is unavailable."
            ) from None
        if not _model_is_installed(self._model, installed_models):
            raise ToolUnavailableError(
                "The configured local vision model is not installed in Ollama."
            )

        image = capture_primary_screen()
        try:
            try:
                answer = self._client.generate_vision_response(
                    self._model,
                    question,
                    image,
                )
            except OllamaTimeoutError:
                raise TimeoutError("The local vision request timed out.") from None
            except OllamaModelUnavailableError:
                raise ToolUnavailableError(
                    "The configured local vision model is unavailable."
                ) from None
            except OllamaConnectionError:
                raise ToolUnavailableError(
                    "The local Ollama vision service is unavailable."
                ) from None
            if not answer.strip():
                raise ValueError("The local vision model returned no description.")
            return answer.strip()
        finally:
            image.close()


def _model_is_installed(model: str, installed_models: tuple[str, ...]) -> bool:
    normalized = model.casefold()
    installed = {name.casefold() for name in installed_models}
    if ":" in normalized:
        return normalized in installed
    return normalized in installed or f"{normalized}:latest" in installed
