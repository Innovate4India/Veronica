"""Provider-neutral vision orchestration for explicitly requested screen captures."""

from __future__ import annotations

from app.ai.base import (
    ProviderConnectionError,
    ProviderModelUnavailableError,
    ProviderResponseError,
    ProviderTimeoutError,
    VisionProvider,
    VisionRequest,
    VisionResponse,
)
from app.tools.base import ToolUnavailableError
from app.tools.screenshot import capture_primary_screen

class LocalVisionService:
    """Use a provider-neutral vision adapter for one transient screen image."""

    def __init__(
        self,
        provider: VisionProvider | None,
    ) -> None:
        if provider is not None and not isinstance(provider, VisionProvider):
            raise TypeError("Vision service requires a VisionProvider.")
        self._provider = provider

    @property
    def model_configured(self) -> bool:
        return (
            self._provider is not None
            and self._provider.model_configured
        )

    def understand_primary_screen(self, question: str) -> str:
        """Capture, ask the preinstalled local model, then close the image."""
        if self._provider is None:
            raise ToolUnavailableError(
                "Local screen understanding is unavailable because "
                "the selected AI provider does not support vision."
            )
        if not self._provider.model_configured:
            raise ToolUnavailableError(
                getattr(
                    self._provider,
                    "missing_model_message",
                    "Local screen understanding is unavailable because no "
                    "vision model is configured.",
                )
            )

        try:
            available = self._provider.model_available()
        except ProviderTimeoutError:
            raise TimeoutError("The local vision request timed out.") from None
        except ProviderModelUnavailableError:
            raise ToolUnavailableError(
                getattr(
                    self._provider,
                    "model_unavailable_message",
                    "The configured local vision model is unavailable.",
                )
            ) from None
        except ProviderConnectionError:
            raise ToolUnavailableError(
                getattr(
                    self._provider,
                    "connection_error_message",
                    "The local vision service is unavailable.",
                )
            ) from None
        if not available:
            raise ToolUnavailableError(
                getattr(
                    self._provider,
                    "model_not_installed_message",
                    "The configured local vision model is not installed.",
                )
            )

        image = capture_primary_screen()
        try:
            try:
                response = self._provider.generate_vision(
                    VisionRequest(
                        question=question,
                        image=image,
                    )
                )
                if not isinstance(response, VisionResponse):
                    raise ProviderResponseError(
                        "The vision provider returned an invalid response."
                    )
                if not isinstance(response.text, str):
                    raise ProviderResponseError(
                        "The vision provider returned invalid response text."
                    )
                answer = response.text
            except ProviderTimeoutError:
                raise TimeoutError("The local vision request timed out.") from None
            except ProviderModelUnavailableError:
                raise ToolUnavailableError(
                    getattr(
                        self._provider,
                        "model_unavailable_message",
                        "The configured local vision model is unavailable.",
                    )
                ) from None
            except ProviderConnectionError:
                raise ToolUnavailableError(
                    getattr(
                        self._provider,
                        "connection_error_message",
                        "The local vision service is unavailable.",
                    )
                ) from None
            if not answer.strip():
                raise ProviderResponseError(
                    "The vision provider returned an empty response."
                )
            return answer.strip()
        finally:
            image.close()
