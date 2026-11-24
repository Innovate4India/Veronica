"""Local voice provider interfaces and orchestration."""

from app.voice.base import (
    AudioPlaybackError,
    MicrophonePermissionError,
    MicrophoneUnavailableError,
    NoSpeechDetectedError,
    SpeechInterruptedError,
    SpeechRecognitionError,
    SpeechToTextProvider,
    TextToSpeechProvider,
    TextToSpeechUnavailableError,
    UnsupportedSpeechLanguageError,
    VoiceError,
    VoiceModelUnavailableError,
    VoiceTimeoutError,
)
from app.voice.service import VoiceService
from app.voice.stt import FasterWhisperSTT
from app.voice.microsoft_tts import MicrosoftNeuralTTS
from app.voice.tts import PiperTTS

__all__ = [
    "AudioPlaybackError",
    "FasterWhisperSTT",
    "MicrophonePermissionError",
    "MicrophoneUnavailableError",
    "MicrosoftNeuralTTS",
    "NoSpeechDetectedError",
    "PiperTTS",
    "SpeechInterruptedError",
    "SpeechRecognitionError",
    "SpeechToTextProvider",
    "TextToSpeechProvider",
    "TextToSpeechUnavailableError",
    "UnsupportedSpeechLanguageError",
    "VoiceError",
    "VoiceModelUnavailableError",
    "VoiceService",
    "VoiceTimeoutError",
]
