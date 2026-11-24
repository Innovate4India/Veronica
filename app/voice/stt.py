"""Local microphone capture and transcription using faster-whisper."""

import importlib
import math
from collections.abc import Iterable
from pathlib import Path
from typing import Protocol, cast

from app.config import WhisperConfig, load_whisper_config
from app.voice.base import (
    MicrophonePermissionError,
    MicrophoneUnavailableError,
    NoSpeechDetectedError,
    SpeechRecognitionError,
    SpeechToTextProvider,
    VoiceModelUnavailableError,
    VoiceTimeoutError,
)


class _TranscriptionModel(Protocol):
    def transcribe(
        self,
        audio: object,
        *,
        language: str | None = None,
        vad_filter: bool = True,
    ) -> tuple[Iterable[object], object]: ...


class _WhisperModelFactory(Protocol):
    def __call__(
        self,
        model_size_or_path: str,
        *,
        device: str,
        compute_type: str,
        local_files_only: bool,
    ) -> _TranscriptionModel: ...


class _AudioBackend(Protocol):
    def rec(
        self,
        frames: int,
        *,
        samplerate: int,
        channels: int,
        dtype: str,
        device: int | None = None,
    ) -> object: ...

    def wait(self, timeout: float | None = None) -> None: ...


class FasterWhisperSTT(SpeechToTextProvider):
    """Capture a fixed-duration utterance and transcribe a preinstalled model."""

    def __init__(
        self,
        model_path: Path | str | None = None,
        *,
        model_name: str | None = None,
        device: str | None = None,
        compute_type: str | None = None,
        duration_seconds: float = 6.0,
        sample_rate: int = 16_000,
        input_device: int | None = None,
        language: str | None = None,
        model_factory: _WhisperModelFactory | None = None,
        audio_backend: _AudioBackend | None = None,
        config: WhisperConfig | None = None,
    ) -> None:
        if not math.isfinite(duration_seconds) or duration_seconds <= 0:
            raise ValueError("duration_seconds must be a positive finite number.")
        if sample_rate <= 0:
            raise ValueError("sample_rate must be positive.")
        whisper_config = config or load_whisper_config()
        self._model_name = model_name or whisper_config.model
        self._model_path = Path(
            model_path if model_path is not None else whisper_config.model_path
        ).expanduser()
        self._device = device or whisper_config.device
        self._compute_type = compute_type or whisper_config.compute_type
        self._duration_seconds = duration_seconds
        self._sample_rate = sample_rate
        self._input_device = input_device
        self._language = language
        self._model_factory = model_factory
        self._audio_backend = audio_backend
        self._model: _TranscriptionModel | None = None

    def _load_audio_backend(self) -> _AudioBackend:
        if self._audio_backend is not None:
            return self._audio_backend
        try:
            self._audio_backend = cast(
                _AudioBackend,
                importlib.import_module("sounddevice"),
            )
        except ImportError as error:
            raise MicrophoneUnavailableError(
                "The local microphone backend is not installed."
            ) from error
        return self._audio_backend

    def _load_model(self) -> _TranscriptionModel:
        if not self._model_path.is_dir() or not self._has_required_model_files():
            raise VoiceModelUnavailableError(
                f"The configured faster-whisper model '{self._model_name}' is missing "
                f"or incomplete at '{self._model_path}'. Install the model locally; "
                "Veronica will not download it automatically."
            )
        if self._model is not None:
            return self._model
        factory = self._model_factory
        if factory is None:
            try:
                faster_whisper = importlib.import_module("faster_whisper")
            except ImportError as error:
                raise VoiceModelUnavailableError(
                    "The faster-whisper package is not installed."
                ) from error
            factory = cast(_WhisperModelFactory, faster_whisper.WhisperModel)
        try:
            self._model = factory(
                str(self._model_path.resolve()),
                device=self._device,
                compute_type=self._compute_type,
                local_files_only=True,
            )
        except (OSError, RuntimeError, ValueError) as error:
            raise VoiceModelUnavailableError(
                "The local faster-whisper model could not be loaded."
            ) from error
        return self._model

    def _has_required_model_files(self) -> bool:
        return (self._model_path / "model.bin").is_file() and (
            self._model_path / "config.json"
        ).is_file()

    def listen(self) -> str:
        """Record only for the configured duration; never retain audio to disk."""
        frames = round(self._duration_seconds * self._sample_rate)
        model = self._load_model()
        audio_backend = self._load_audio_backend()
        try:
            recording = audio_backend.rec(
                frames,
                samplerate=self._sample_rate,
                channels=1,
                dtype="float32",
                device=self._input_device,
            )
            audio_backend.wait(timeout=self._duration_seconds + 5)
        except PermissionError as error:
            raise MicrophonePermissionError(
                "Microphone permission was denied."
            ) from error
        except TimeoutError as error:
            raise VoiceTimeoutError("Microphone capture timed out.") from error
        except (OSError, RuntimeError) as error:
            raise MicrophoneUnavailableError(
                "The microphone is unavailable."
            ) from error
        except Exception as error:
            raise MicrophoneUnavailableError(
                "The microphone could not capture audio."
            ) from error

        try:
            segments, _ = model.transcribe(
                recording,
                language=self._language,
                vad_filter=True,
            )
            recognized_text = " ".join(
                segment.text.strip()
                for segment in segments
                if isinstance(getattr(segment, "text", None), str)
                and segment.text.strip()
            ).strip()
        except (OSError, RuntimeError, ValueError) as error:
            raise SpeechRecognitionError(
                "Local speech recognition failed."
            ) from error
        except Exception as error:
            raise SpeechRecognitionError(
                "Local speech recognition failed."
            ) from error
        if not recognized_text:
            raise NoSpeechDetectedError("No speech was detected.")
        return recognized_text
