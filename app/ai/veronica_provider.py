"""Future integration boundary for a Veronica-owned local model."""

from collections.abc import Iterator, Sequence

from app.ai.base import (
    AIProvider,
    ChatMessage,
    ProviderCapabilities,
    ProviderMetadata,
    ProviderModelUnavailableError,
)


class VeronicaModelProvider(AIProvider):
    """Safe scaffold for a future locally hosted or embedded Veronica model.

    This class intentionally performs no Ollama calls and loads no model.
    A later implementation should supply tokenization, inference, context
    construction, and provider-owned health/model discovery.
    """

    @property
    def metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            name="Veronica",
            kind="veronica-local",
            model="not-implemented",
            capabilities=ProviderCapabilities(
                text=False,
                streaming=False,
                tools=False,
                vision=False,
            ),
        )

    def health_check(self) -> bool:
        return False

    def generate_response(self, messages: Sequence[ChatMessage]) -> str:
        raise ProviderModelUnavailableError(
            "The Veronica-owned model provider is not implemented yet."
        )

    def generate_stream(
        self,
        messages: Sequence[ChatMessage],
    ) -> Iterator[str]:
        raise ProviderModelUnavailableError(
            "The Veronica-owned model provider is not implemented yet."
        )
