"""Provider registry and implementation-independent provider selection."""

from collections.abc import Callable

from app.ai.base import AIProvider, ProviderConfigurationError
from app.config import load_provider_selection_config

ProviderFactory = Callable[[], AIProvider]
_PROVIDER_FACTORIES: dict[str, ProviderFactory] = {}


def register_provider(name: str, factory: ProviderFactory) -> None:
    """Register one provider implementation without changing application startup."""
    normalized = name.strip().casefold()
    if not normalized:
        raise ProviderConfigurationError("Provider names must not be empty.")
    if normalized in _PROVIDER_FACTORIES:
        raise ProviderConfigurationError(
            f"AI provider {normalized!r} is already registered."
        )
    _PROVIDER_FACTORIES[normalized] = factory


def _create_ollama_provider() -> AIProvider:
    from app.ai.ollama_client import OllamaClient
    from app.config import load_ollama_config

    try:
        config = load_ollama_config()
    except ValueError as error:
        raise ProviderConfigurationError(str(error)) from error
    return OllamaClient(config)


register_provider("ollama", _create_ollama_provider)


def create_provider(provider_name: str | None = None) -> AIProvider:
    """Create the selected registered provider, defaulting to Ollama."""
    if provider_name is None:
        try:
            provider_name = load_provider_selection_config().provider_name
        except ValueError as error:
            raise ProviderConfigurationError(str(error)) from error
    if not isinstance(provider_name, str) or not provider_name.strip():
        raise ProviderConfigurationError("An AI provider name is required.")

    normalized = provider_name.strip().casefold()
    factory = _PROVIDER_FACTORIES.get(normalized)
    if factory is None:
        raise ProviderConfigurationError(
            f"AI provider {normalized!r} is not registered."
        )
    provider = factory()
    if not isinstance(provider, AIProvider):
        raise ProviderConfigurationError(
            f"Registered AI provider {normalized!r} did not create an AIProvider."
        )
    return provider
