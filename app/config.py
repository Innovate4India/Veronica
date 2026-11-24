"""Application paths and environment-based settings."""

import math
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

APP_NAME = "Veronica"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_FILE = LOG_DIR / "veronica.log"


@dataclass(frozen=True)
class OllamaConfig:
    """Connection settings for the local Ollama service."""

    base_url: str
    model: str
    timeout: float


@dataclass(frozen=True)
class ProviderSelectionConfig:
    """Implementation-independent selection of the active AI provider."""

    provider_name: str


@dataclass(frozen=True)
class WhisperConfig:
    """Settings for local-only faster-whisper inference."""

    model: str
    model_path: Path
    device: str
    compute_type: str


@dataclass(frozen=True)
class PiperConfig:
    """Settings for a preinstalled local Piper voice."""

    model: str
    model_path: Path
    hindi_model_path: Path | None = None
    english_model_path: Path | None = None


@dataclass(frozen=True)
class SpokenResponseConfig:
    """Opt-in cloud Neural TTS settings for spoken CLI replies."""

    enabled: bool
    language: str
    hindi_voice: str
    english_voice: str
    rate: str
    pitch: str
    volume: str


@dataclass(frozen=True)
class WebSearchConfig:
    """Optional Tavily public web search configuration."""

    provider: str
    api_key: str = field(repr=False)
    timeout_seconds: float = 8.0


def load_web_search_enabled(
    environ: Mapping[str, str] | None = None,
) -> bool:
    """Read the opt-in application switch without loading provider settings."""
    values = os.environ if environ is None else environ
    enabled = values.get("WEB_SEARCH_ENABLED", "false").strip().casefold()
    if enabled not in {"true", "false"}:
        raise ValueError("WEB_SEARCH_ENABLED must be true or false.")
    return enabled == "true"


def load_file_search_roots(
    environ: Mapping[str, str] | None = None,
) -> tuple[Path, ...]:
    """Load absolute local file-search roots; default to the project directory."""
    values = os.environ if environ is None else environ
    configured_roots = values.get("VERONICA_FILE_SEARCH_ROOTS", "").strip()
    root_texts = (
        configured_roots.split(";")
        if configured_roots
        else [str(PROJECT_ROOT)]
    )
    if len(root_texts) > 16:
        raise ValueError("VERONICA_FILE_SEARCH_ROOTS may contain at most 16 paths.")

    roots: list[Path] = []
    seen: set[str] = set()
    for root_text in root_texts:
        text = root_text.strip()
        if not text:
            continue
        if len(text) > 1024:
            raise ValueError(
                "VERONICA_FILE_SEARCH_ROOTS entries must be at most 1024 characters."
            )
        root = Path(text).expanduser()
        if not root.is_absolute():
            raise ValueError(
                "Every VERONICA_FILE_SEARCH_ROOTS entry must be an absolute path."
            )
        try:
            normalized = root.resolve(strict=False)
        except (OSError, RuntimeError):
            raise ValueError(
                "A VERONICA_FILE_SEARCH_ROOTS path could not be resolved."
            ) from None
        identity = os.path.normcase(str(normalized))
        if identity not in seen:
            roots.append(normalized)
            seen.add(identity)
    if not roots:
        raise ValueError("VERONICA_FILE_SEARCH_ROOTS must contain a path.")
    return tuple(roots)


FEMALE_HINDI_NEURAL_VOICES = {
    "hi-IN-SwaraNeural",
    "hi-IN-KavyaNeural",
    "hi-IN-AnanyaNeural",
}
FEMALE_ENGLISH_NEURAL_VOICES = {
    "en-IN-NeerjaNeural",
    "en-IN-KavyaNeural",
    "en-IN-AnanyaNeural",
}
_ALLOWED_HINDI_VOICES = FEMALE_HINDI_NEURAL_VOICES
_ALLOWED_ENGLISH_VOICES = FEMALE_ENGLISH_NEURAL_VOICES | {
    "hi-IN-SwaraNeural",
}


def load_ollama_config(
    environ: Mapping[str, str] | None = None,
) -> OllamaConfig:
    """Load Ollama settings from the process environment."""
    values = os.environ if environ is None else environ
    base_url = values.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip()
    model = values.get("OLLAMA_MODEL", "").strip()
    timeout_text = values.get("OLLAMA_TIMEOUT", "120").strip()

    if not base_url:
        raise ValueError("OLLAMA_BASE_URL must not be empty.")
    try:
        timeout = float(timeout_text)
    except ValueError as error:
        raise ValueError("OLLAMA_TIMEOUT must be a positive number of seconds.") from error
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("OLLAMA_TIMEOUT must be a positive number of seconds.")

    return OllamaConfig(base_url=base_url.rstrip("/"), model=model, timeout=timeout)


def load_provider_selection_config(
    environ: Mapping[str, str] | None = None,
) -> ProviderSelectionConfig:
    """Load the selected registered provider; Ollama remains the default."""
    values = os.environ if environ is None else environ
    provider_name = values.get("VERONICA_AI_PROVIDER", "ollama").strip().casefold()
    if not provider_name:
        raise ValueError("VERONICA_AI_PROVIDER must not be empty.")
    return ProviderSelectionConfig(provider_name=provider_name)


def load_ollama_vision_model(
    environ: Mapping[str, str] | None = None,
) -> str:
    """Load the independent optional local vision model selection."""
    values = os.environ if environ is None else environ
    return values.get("OLLAMA_VISION_MODEL", "").strip()


def load_max_conversation_messages(
    environ: Mapping[str, str] | None = None,
) -> int:
    """Load the maximum number of retained non-system conversation messages."""
    values = os.environ if environ is None else environ
    value = values.get("MAX_CONVERSATION_MESSAGES", "20").strip()
    try:
        maximum = int(value)
    except ValueError as error:
        raise ValueError(
            "MAX_CONVERSATION_MESSAGES must be an integer of at least 2."
        ) from error
    if maximum < 2:
        raise ValueError("MAX_CONVERSATION_MESSAGES must be at least 2.")
    return maximum


def load_memory_database_path(
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Load the local SQLite memory path, resolving relative paths in the project."""
    values = os.environ if environ is None else environ
    configured_path = values.get(
        "MEMORY_DATABASE_PATH",
        "data/veronica_memory.db",
    ).strip()
    if not configured_path:
        raise ValueError("MEMORY_DATABASE_PATH must not be empty.")
    path = Path(configured_path).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def load_max_relevant_memories(
    environ: Mapping[str, str] | None = None,
) -> int:
    """Load the maximum number of local memories included in one model request."""
    values = os.environ if environ is None else environ
    value = values.get("MAX_RELEVANT_MEMORIES", "5").strip()
    try:
        maximum = int(value)
    except ValueError as error:
        raise ValueError(
            "MAX_RELEVANT_MEMORIES must be a positive integer."
        ) from error
    if maximum < 1:
        raise ValueError("MAX_RELEVANT_MEMORIES must be a positive integer.")
    return maximum


def load_whisper_config(
    environ: Mapping[str, str] | None = None,
) -> WhisperConfig:
    """Load Whisper selection and local storage settings."""
    values = os.environ if environ is None else environ
    model = values.get("WHISPER_MODEL", "base").strip()
    configured_path = values.get("WHISPER_MODEL_PATH", "").strip()
    if not model:
        raise ValueError("WHISPER_MODEL must not be empty.")
    if configured_path:
        model_path_text = configured_path.format(model=model)
    else:
        model_path_text = f"data/models/whisper/{model}"
    model_path = Path(model_path_text).expanduser()
    if not model_path.is_absolute():
        model_path = PROJECT_ROOT / model_path

    device = values.get("WHISPER_DEVICE", "cpu").strip().lower()
    if device not in {"cpu", "cuda", "auto"}:
        raise ValueError("WHISPER_DEVICE must be cpu, cuda, or auto.")
    compute_type = values.get("WHISPER_COMPUTE_TYPE", "int8").strip().lower()
    if not compute_type:
        raise ValueError("WHISPER_COMPUTE_TYPE must not be empty.")

    return WhisperConfig(
        model=model,
        model_path=model_path,
        device=device,
        compute_type=compute_type,
    )


def load_piper_config(
    environ: Mapping[str, str] | None = None,
) -> PiperConfig:
    """Load local Piper voice settings without choosing or downloading a voice."""
    values = os.environ if environ is None else environ
    model = values.get("PIPER_MODEL", "").strip()
    configured_path = values.get("PIPER_MODEL_PATH", "").strip()
    if configured_path:
        if "{model}" in configured_path and not model:
            raise ValueError(
                "PIPER_MODEL is required when PIPER_MODEL_PATH uses {model}."
            )
        model_path_text = configured_path.format(model=model)
    else:
        model_path_text = "data/models/piper"
    model_path = Path(model_path_text).expanduser()
    if not model_path.is_absolute():
        model_path = PROJECT_ROOT / model_path

    hindi_model_path = _load_optional_model_path(
        values.get(
            "PIPER_HI_MODEL_PATH",
            "data/models/piper/hi/hi_IN/pratham/medium/hi_IN-pratham-medium.onnx",
        )
    )
    english_model_path = _load_optional_model_path(
        values.get(
            "PIPER_EN_MODEL_PATH",
            "data/models/piper/en/en_US/ryan/medium/en_US-ryan-medium.onnx",
        )
    )

    return PiperConfig(
        model=model,
        model_path=model_path,
        hindi_model_path=hindi_model_path,
        english_model_path=english_model_path,
    )


def load_spoken_response_config(
    environ: Mapping[str, str] | None = None,
) -> SpokenResponseConfig:
    """Load explicit Neural TTS voice choices, rejecting non-female voices."""
    values = os.environ if environ is None else environ
    enabled_value = values.get("VOICE_RESPONSES_ENABLED", "false").strip().casefold()
    if enabled_value not in {"true", "false"}:
        raise ValueError("VOICE_RESPONSES_ENABLED must be true or false.")
    language = values.get("VOICE_RESPONSE_LANGUAGE", "en").strip().casefold()
    if language not in {"hi", "en"}:
        raise ValueError("VOICE_RESPONSE_LANGUAGE must be hi or en.")
    hindi_voice = values.get(
        "MICROSOFT_TTS_HINDI_VOICE", "hi-IN-SwaraNeural"
    ).strip()
    if hindi_voice not in _ALLOWED_HINDI_VOICES:
        raise ValueError(
            "MICROSOFT_TTS_HINDI_VOICE must select a supported female Hindi voice."
        )
    english_voice = values.get(
        "MICROSOFT_TTS_ENGLISH_VOICE", "hi-IN-SwaraNeural"
    ).strip()
    if english_voice not in _ALLOWED_ENGLISH_VOICES:
        raise ValueError(
            "MICROSOFT_TTS_ENGLISH_VOICE must select a supported female voice."
        )
    rate = values.get("MICROSOFT_TTS_RATE", "-10%").strip()
    pitch = values.get("MICROSOFT_TTS_PITCH", "+0Hz").strip()
    volume = values.get("MICROSOFT_TTS_VOLUME", "+0%").strip()
    if not re.fullmatch(r"[+-]?\d+%", rate):
        raise ValueError("MICROSOFT_TTS_RATE must be a percentage such as -10%.")
    if not re.fullmatch(r"[+-]?\d+Hz", pitch):
        raise ValueError("MICROSOFT_TTS_PITCH must be in Hz, such as +0Hz.")
    if not re.fullmatch(r"[+-]?\d+%", volume):
        raise ValueError("MICROSOFT_TTS_VOLUME must be a percentage such as +0%.")
    return SpokenResponseConfig(
        enabled=enabled_value == "true",
        language=language,
        hindi_voice=hindi_voice,
        english_voice=english_voice,
        rate=rate,
        pitch=pitch,
        volume=volume,
    )


def load_web_search_config(
    environ: Mapping[str, str] | None = None,
) -> WebSearchConfig:
    """Load Tavily selection and key without requiring online search to be set up."""
    values = os.environ if environ is None else environ
    provider = values.get("WEB_SEARCH_PROVIDER", "tavily").strip().casefold()
    if provider not in {"tavily", ""}:
        raise ValueError("WEB_SEARCH_PROVIDER must be 'tavily' or empty.")
    timeout_text = values.get("WEB_SEARCH_TIMEOUT_SECONDS", "8").strip()
    try:
        timeout_seconds = float(timeout_text)
    except ValueError as error:
        raise ValueError(
            "WEB_SEARCH_TIMEOUT_SECONDS must be between 1 and 20 seconds."
        ) from error
    if not math.isfinite(timeout_seconds) or not 1 <= timeout_seconds <= 20:
        raise ValueError(
            "WEB_SEARCH_TIMEOUT_SECONDS must be between 1 and 20 seconds."
        )
    return WebSearchConfig(
        provider=provider,
        api_key=values.get("TAVILY_API_KEY", "").strip(),
        timeout_seconds=timeout_seconds,
    )


def _load_optional_model_path(configured_path: str) -> Path | None:
    path_text = configured_path.strip()
    if not path_text:
        return None
    path = Path(path_text).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


MAX_CONVERSATION_MESSAGES = load_max_conversation_messages()
MEMORY_DATABASE_PATH = load_memory_database_path()
MAX_RELEVANT_MEMORIES = load_max_relevant_memories()
_WHISPER_CONFIG = load_whisper_config()
WHISPER_MODEL = _WHISPER_CONFIG.model
WHISPER_MODEL_PATH = _WHISPER_CONFIG.model_path
WHISPER_DEVICE = _WHISPER_CONFIG.device
WHISPER_COMPUTE_TYPE = _WHISPER_CONFIG.compute_type
_PIPER_CONFIG = load_piper_config()
PIPER_MODEL = _PIPER_CONFIG.model
PIPER_MODEL_PATH = _PIPER_CONFIG.model_path


def __getattr__(name: str) -> object:
    if name in {"OLLAMA_BASE_URL", "OLLAMA_MODEL", "OLLAMA_TIMEOUT"}:
        config = load_ollama_config()
        return {
            "OLLAMA_BASE_URL": config.base_url,
            "OLLAMA_MODEL": config.model,
            "OLLAMA_TIMEOUT": config.timeout,
        }[name]
    if name == "OLLAMA_VISION_MODEL":
        return load_ollama_vision_model()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
