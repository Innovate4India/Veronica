"""Local speech synthesis and playback using a preinstalled Piper voice."""

import importlib
import json
import threading
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from app.config import PiperConfig, load_piper_config
from app.voice.base import (
    AudioPlaybackError,
    SpeechInterruptedError,
    TextToSpeechProvider,
    TextToSpeechUnavailableError,
    UnsupportedSpeechLanguageError,
    VoiceModelUnavailableError,
)


class _AudioChunk(Protocol):
    sample_rate: int
    sample_width: int
    sample_channels: int
    audio_int16_bytes: bytes


class _PiperVoice(Protocol):
    def synthesize(self, text: str) -> Iterable[_AudioChunk]: ...


class _PiperVoiceFactory(Protocol):
    @staticmethod
    def load(model_path: str) -> _PiperVoice: ...


class _AudioBackend(Protocol):
    def play(self, data: object, samplerate: int) -> None: ...

    def wait(self) -> None: ...

    def stop(self) -> None: ...


class _NumpyArray(Protocol):
    def reshape(self, shape: tuple[int, int]) -> _NumpyArray: ...


class _NumpyBackend(Protocol):
    int16: object

    def frombuffer(self, buffer: bytes, *, dtype: object) -> _NumpyArray: ...


@dataclass(frozen=True)
class PiperPlaybackStats:
    """Audio details for a completed local Piper playback."""

    sample_rate: int
    sample_count: int
    duration_seconds: float


class PiperTTS(TextToSpeechProvider):
    """Speak through an existing local Piper voice; never downloads a model."""

    def __init__(
        self,
        model_path: Path | str | None = None,
        *,
        voice_factory: _PiperVoiceFactory | None = None,
        audio_backend: _AudioBackend | None = None,
        numpy_module: _NumpyBackend | None = None,
        config: PiperConfig | None = None,
    ) -> None:
        piper_config = config or (
            load_piper_config()
            if model_path is None
            else PiperConfig("", Path(model_path))
        )
        self._config = piper_config
        self._model_name = piper_config.model
        self._model_path = Path(
            model_path if model_path is not None else piper_config.model_path
        ).expanduser()
        self._voice_factory = voice_factory
        self._audio_backend = audio_backend
        self._numpy_module = numpy_module
        self._voices: dict[Path, _PiperVoice] = {}

    def _configured_voice(
        self,
        language: str | None,
    ) -> tuple[str, Path, str]:
        if language is None:
            return (
                self._model_name or self._model_path.stem,
                self._model_path,
                "PIPER_MODEL_PATH",
            )
        normalized_language = language.casefold()
        if normalized_language == "hi":
            model_name = "hi_IN-pratham-medium"
            model_path = self._config.hindi_model_path
            setting_name = "PIPER_HI_MODEL_PATH"
        elif normalized_language == "en":
            model_name = "en_US-ryan-medium"
            model_path = self._config.english_model_path
            setting_name = "PIPER_EN_MODEL_PATH"
        else:
            raise UnsupportedSpeechLanguageError(
                "Piper language must be 'hi' or 'en'."
            )
        if model_path is None:
            raise VoiceModelUnavailableError(
                f"No local Piper model path is configured for language "
                f"'{normalized_language}'. Set {setting_name}."
            )
        return model_name, model_path, setting_name

    def _load_voice(
        self,
        model_name: str,
        model_path: Path,
        setting_name: str,
    ) -> _PiperVoice:
        config_path = (
            Path(f"{model_path}.json")
            if model_path.suffix.casefold() == ".onnx"
            else None
        )
        if (
            not model_path.is_file()
            or config_path is None
            or not config_path.is_file()
        ):
            config_location = (
                f"'{config_path}'"
                if config_path is not None
                else "the model filename with '.json' appended"
            )
            raise VoiceModelUnavailableError(
                f"The local Piper voice '{model_name}' is missing or incomplete. "
                f"Configure {setting_name}; the .onnx model "
                f"and matching voice config must exist at {config_location}. "
                "Piper voices are not downloaded automatically."
            )
        try:
            with config_path.open(encoding="utf-8") as config_file:
                voice_config = json.load(config_file)
        except (OSError, json.JSONDecodeError) as error:
            raise VoiceModelUnavailableError(
                "The Piper voice config is unreadable or invalid JSON."
            ) from error
        if not isinstance(voice_config, dict):
            raise VoiceModelUnavailableError(
                "The Piper voice config must contain a JSON object."
            )
        if voice_config.get("phoneme_type") == "pinyin":
            raise TextToSpeechUnavailableError(
                "This Piper voice requires an auxiliary Pinyin model that Piper "
                "may download automatically. It is blocked in Veronica's offline "
                "voice path; use a voice that requires no automatic resources."
            )
        resolved_path = model_path.resolve()
        if resolved_path in self._voices:
            return self._voices[resolved_path]
        factory = self._voice_factory
        if factory is None:
            try:
                piper = importlib.import_module("piper")
            except ImportError as error:
                raise TextToSpeechUnavailableError(
                    "The local Piper text-to-speech package is not installed."
                ) from error
            factory = cast(_PiperVoiceFactory, piper.PiperVoice)
        try:
            voice = factory.load(str(resolved_path))
        except ImportError as error:
            raise TextToSpeechUnavailableError(
                "Piper or one of its required local runtime dependencies is unavailable."
            ) from error
        except (OSError, RuntimeError, ValueError) as error:
            raise VoiceModelUnavailableError(
                f"The local Piper voice '{model_name}' "
                "could not be loaded. Check the ONNX model and companion JSON."
            ) from error
        self._voices[resolved_path] = voice
        return voice

    def _load_audio_backend(self) -> _AudioBackend:
        if self._audio_backend is not None:
            return self._audio_backend
        try:
            self._audio_backend = cast(
                _AudioBackend,
                importlib.import_module("sounddevice"),
            )
        except ImportError as error:
            raise AudioPlaybackError(
                "The local audio playback backend is not installed."
            ) from error
        return self._audio_backend

    def _load_numpy(self) -> _NumpyBackend:
        if self._numpy_module is not None:
            return self._numpy_module
        try:
            self._numpy_module = cast(
                _NumpyBackend,
                importlib.import_module("numpy"),
            )
        except ImportError as error:
            raise AudioPlaybackError(
                "NumPy is required by the local audio playback backend."
            ) from error
        return self._numpy_module

    def speak(self, text: str, *, language: str | None = None) -> None:
        """Synthesize one response and play it without writing audio files."""
        self.speak_with_stats(text, language=language)

    def speak_with_stats(
        self,
        text: str,
        *,
        language: str | None = None,
    ) -> PiperPlaybackStats | None:
        """Synthesize, play, and return audio details without writing audio files."""
        if not text.strip():
            return None
        model_name, model_path, setting_name = self._configured_voice(language)
        voice = self._load_voice(model_name, model_path, setting_name)
        audio_backend = self._load_audio_backend()
        numpy_module = self._load_numpy()
        chunks: list[_AudioChunk] = []
        try:
            chunks.extend(voice.synthesize(text))
        except Exception as error:
            raise TextToSpeechUnavailableError(
                "The local Piper voice could not synthesize the response."
            ) from error
        if not chunks:
            raise TextToSpeechUnavailableError(
                "The local Piper voice returned no audio."
            )
        first_chunk = chunks[0]
        if any(
            chunk.sample_rate != first_chunk.sample_rate
            or chunk.sample_width != first_chunk.sample_width
            or chunk.sample_channels != first_chunk.sample_channels
            for chunk in chunks
        ):
            raise TextToSpeechUnavailableError(
                "The Piper voice returned inconsistent audio formats."
            )
        if first_chunk.sample_width != 2:
            raise TextToSpeechUnavailableError(
                "The Piper voice returned an unsupported PCM format."
            )

        pcm_data = b"".join(chunk.audio_int16_bytes for chunk in chunks)
        if not pcm_data or len(pcm_data) % (
            first_chunk.sample_width * first_chunk.sample_channels
        ):
            raise TextToSpeechUnavailableError(
                "The Piper voice returned invalid PCM audio."
            )
        audio = numpy_module.frombuffer(pcm_data, dtype=numpy_module.int16)
        if first_chunk.sample_channels > 1:
            audio = audio.reshape((-1, first_chunk.sample_channels))
        sample_count = len(pcm_data) // (
            first_chunk.sample_width * first_chunk.sample_channels
        )

        try:
            playback_errors: list[BaseException] = []
            playback_complete = threading.Event()

            def play_audio() -> None:
                try:
                    audio_backend.play(audio, first_chunk.sample_rate)
                    audio_backend.wait()
                except BaseException as error:
                    playback_errors.append(error)
                finally:
                    playback_complete.set()

            playback_thread = threading.Thread(target=play_audio, daemon=True)
            playback_thread.start()
            playback_timeout = max(
                5.0,
                (sample_count / first_chunk.sample_rate) + 5.0,
            )
            if not playback_complete.wait(timeout=playback_timeout):
                audio_backend.stop()
                raise AudioPlaybackError(
                    "Local speaker playback did not finish within the expected time."
                )
            if playback_errors:
                if isinstance(playback_errors[0], KeyboardInterrupt):
                    audio_backend.stop()
                    raise SpeechInterruptedError(
                        "Speech playback was interrupted."
                    ) from playback_errors[0]
                raise AudioPlaybackError(
                    "The local speaker playback failed."
                ) from playback_errors[0]
        except KeyboardInterrupt as error:
            audio_backend.stop()
            raise SpeechInterruptedError("Speech playback was interrupted.") from error
        except SpeechInterruptedError:
            raise
        except AudioPlaybackError:
            raise
        except Exception as error:
            raise AudioPlaybackError(
                "The local speaker playback failed."
            ) from error
        return PiperPlaybackStats(
            sample_rate=first_chunk.sample_rate,
            sample_count=sample_count,
            duration_seconds=sample_count / first_chunk.sample_rate,
        )
