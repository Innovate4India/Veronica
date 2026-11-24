"""Provider-neutral interfaces and errors for local voice components."""

from abc import ABC, abstractmethod


class VoiceError(Exception):
    """Base exception for voice input and output failures."""


class MicrophoneUnavailableError(VoiceError):
    """Raised when a microphone cannot be opened or read."""


class MicrophonePermissionError(MicrophoneUnavailableError):
    """Raised when microphone access is denied."""


class VoiceTimeoutError(VoiceError):
    """Raised when microphone capture exceeds its configured duration."""


class NoSpeechDetectedError(VoiceError):
    """Raised when no usable speech was detected."""


class VoiceModelUnavailableError(VoiceError):
    """Raised when a required local speech model is missing or invalid."""


class SpeechRecognitionError(VoiceError):
    """Raised when local speech recognition fails."""


class TextToSpeechUnavailableError(VoiceError):
    """Raised when the local text-to-speech engine cannot be loaded."""


class AudioPlaybackError(VoiceError):
    """Raised when generated speech cannot be played locally."""


class UnsupportedSpeechLanguageError(VoiceError):
    """Raised when the selected voice cannot synthesize the requested language."""


class SpeechInterruptedError(VoiceError):
    """Raised when local speech playback is interrupted."""


class SpeechToTextProvider(ABC):
    """Interface for explicit, one-shot local microphone transcription."""

    @abstractmethod
    def listen(self) -> str:
        """Record one explicitly requested utterance and return recognized text."""


class TextToSpeechProvider(ABC):
    """Interface for local speech synthesis and playback."""

    @abstractmethod
    def speak(self, text: str, *, language: str | None = None) -> None:
        """Speak text using a local voice and local audio output."""
