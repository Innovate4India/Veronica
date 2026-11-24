"""Microsoft Edge online Neural TTS using an explicitly female voice."""

import asyncio
import importlib
import io
import threading
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol, cast

import numpy

from app.config import (
    SpokenResponseConfig,
    FEMALE_ENGLISH_NEURAL_VOICES,
    FEMALE_HINDI_NEURAL_VOICES,
)
from app.voice.base import (
    AudioPlaybackError,
    SpeechInterruptedError,
    TextToSpeechProvider,
    TextToSpeechUnavailableError,
    UnsupportedSpeechLanguageError,
)

_SYNTHESIS_TIMEOUT_SECONDS = 45
_OUTPUT_SAMPLE_RATE = 24_000
_PLAYBACK_TIMEOUT_MIN_SECONDS = 5.0


class _AudioStream(Protocol):
    def start(self) -> None: ...

    def abort(self) -> None: ...

    def close(self) -> None: ...


class _AudioBackend(Protocol):
    CallbackAbort: type[BaseException]
    CallbackStop: type[BaseException]

    def OutputStream(
        self,
        *,
        samplerate: int,
        channels: int,
        dtype: str,
        callback: Callable[[numpy.ndarray, int, object, object], None],
        finished_callback: Callable[[], None],
    ) -> _AudioStream: ...


@dataclass(frozen=True)
class NeuralPlaybackStats:
    """Audio details for one successfully played online Neural TTS response."""

    voice: str
    sample_rate: int
    sample_count: int
    duration_seconds: float


async def _request_audio(
    text: str,
    voice: str,
    rate: str,
    pitch: str,
    volume: str,
) -> bytes:
    try:
        edge_tts = importlib.import_module("edge_tts")
    except ImportError as error:
        raise TextToSpeechUnavailableError(
            "Microsoft Neural TTS requires the edge-tts package."
        ) from error
    communicate = edge_tts.Communicate(
        text,
        voice,
        rate=rate,
        pitch=pitch,
        volume=volume,
    )
    audio_parts: list[bytes] = []
    async for packet in communicate.stream():
        if packet.get("type") == "audio":
            data = packet.get("data")
            if isinstance(data, bytes):
                audio_parts.append(data)
    audio = b"".join(audio_parts)
    if not audio:
        raise TextToSpeechUnavailableError(
            "Microsoft Neural TTS returned no audio data."
        )
    return audio


def _decode_mp3(audio_bytes: bytes) -> numpy.ndarray:
    try:
        av = importlib.import_module("av")
        with av.open(io.BytesIO(audio_bytes), mode="r", format="mp3") as container:
            audio_stream = container.streams.audio[0]
            resampler = av.AudioResampler(
                format="s16",
                layout="mono",
                rate=_OUTPUT_SAMPLE_RATE,
            )
            pcm_frames: list[numpy.ndarray] = []
            for frame in container.decode(audio_stream):
                pcm_frames.extend(
                    output.to_ndarray().reshape(-1)
                    for output in resampler.resample(frame)
                )
            pcm_frames.extend(
                output.to_ndarray().reshape(-1)
                for output in resampler.resample(None)
            )
    except Exception as error:
        raise TextToSpeechUnavailableError(
            "Microsoft Neural TTS audio could not be decoded locally."
        ) from error
    if not pcm_frames:
        raise TextToSpeechUnavailableError(
            "Microsoft Neural TTS produced an empty audio stream."
        )
    return numpy.concatenate(pcm_frames).astype(numpy.int16, copy=False)


class MicrosoftNeuralTTS(TextToSpeechProvider):
    """Speak through Microsoft Edge's online TTS using female-only voice choices."""

    def __init__(
        self,
        config: SpokenResponseConfig,
        *,
        audio_backend: _AudioBackend | None = None,
        synthesizer: Callable[[str, str, str, str, str], Awaitable[bytes]] | None = None,
        decoder: Callable[[bytes], numpy.ndarray] | None = None,
    ) -> None:
        self._config = config
        self._audio_backend = audio_backend
        self._synthesizer = synthesizer or _request_audio
        self._decoder = decoder or _decode_mp3

    def _voice_for_language(self, language: str | None) -> str:
        if language == "hi":
            voice = self._config.hindi_voice
            allowed_voices = FEMALE_HINDI_NEURAL_VOICES
        elif language == "en":
            voice = self._config.english_voice
            allowed_voices = FEMALE_ENGLISH_NEURAL_VOICES | {
                "hi-IN-SwaraNeural",
            }
        else:
            raise UnsupportedSpeechLanguageError(
                "Microsoft Neural TTS requires explicit language='hi' or language='en'."
            )
        if voice not in allowed_voices:
            raise UnsupportedSpeechLanguageError(
                "The selected Microsoft Neural TTS voice is not on the female-only "
                "voice allowlist."
            )
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

    async def _synthesize(
        self,
        text: str,
        voice: str,
    ) -> bytes:
        return await self._synthesizer(
            text,
            voice,
            self._config.rate,
            self._config.pitch,
            self._config.volume,
        )

    def speak(
        self,
        text: str,
        *,
        language: str | None = None,
    ) -> None:
        """Request online speech, decode in memory, and play with a time bound."""
        if not text.strip():
            return
        if language is None:
            raise UnsupportedSpeechLanguageError(
                "Microsoft Neural TTS requires explicit language='hi' or language='en'."
            )
        self.speak_with_stats(text, language=language)

    def speak_with_stats(
        self,
        text: str,
        *,
        language: str,
    ) -> NeuralPlaybackStats | None:
        """Speak once and return format details useful for voice auditions."""
        if not text.strip():
            return None
        voice = self._voice_for_language(language)
        try:
            audio_bytes = asyncio.run(
                asyncio.wait_for(
                    self._synthesize(text, voice),
                    timeout=_SYNTHESIS_TIMEOUT_SECONDS,
                )
            )
        except TextToSpeechUnavailableError:
            raise
        except Exception as error:
            raise TextToSpeechUnavailableError(
                "Microsoft Neural TTS could not synthesize the response. "
                "Check internet access and the selected voice."
            ) from error
        audio = self._decoder(audio_bytes)
        if audio.ndim != 1 or audio.dtype != numpy.int16 or audio.size == 0:
            raise TextToSpeechUnavailableError(
                "Microsoft Neural TTS returned audio in an unsupported format."
            )
        self._play(audio)
        return NeuralPlaybackStats(
            voice=voice,
            sample_rate=_OUTPUT_SAMPLE_RATE,
            sample_count=int(audio.size),
            duration_seconds=audio.size / _OUTPUT_SAMPLE_RATE,
        )

    def _play(self, audio: numpy.ndarray) -> None:
        backend = self._load_audio_backend()
        playback_complete = threading.Event()
        playback_errors: list[BaseException] = []
        position = 0

        def play_audio(
            output: numpy.ndarray,
            frames: int,
            time_info: object,
            status: object,
        ) -> None:
            nonlocal position
            del time_info, status
            try:
                output.fill(0)
                end = min(position + frames, audio.size)
                frame_count = end - position
                if frame_count:
                    output[:frame_count, 0] = audio[position:end]
                position = end
                if position >= audio.size:
                    raise backend.CallbackStop
            except backend.CallbackStop:
                raise
            except BaseException as error:
                playback_errors.append(error)
                playback_complete.set()
                raise backend.CallbackAbort

        timeout = max(
            _PLAYBACK_TIMEOUT_MIN_SECONDS,
            (audio.size / _OUTPUT_SAMPLE_RATE) + _PLAYBACK_TIMEOUT_MIN_SECONDS,
        )
        try:
            stream = backend.OutputStream(
                samplerate=_OUTPUT_SAMPLE_RATE,
                channels=1,
                dtype="int16",
                callback=play_audio,
                finished_callback=playback_complete.set,
            )
        except Exception as error:
            raise AudioPlaybackError(
                "Microsoft Neural TTS audio playback could not be started."
            ) from error

        try:
            stream.start()
            if not playback_complete.wait(timeout=timeout):
                cleanup_error = self._close_stream(stream, abort=True)
                if cleanup_error is not None:
                    raise AudioPlaybackError(
                        "Microsoft Neural TTS playback timed out and cleanup failed."
                    ) from cleanup_error
                raise AudioPlaybackError(
                    "Microsoft Neural TTS playback did not finish in time."
                )
            if playback_errors:
                cleanup_error = self._close_stream(stream, abort=True)
                error = AudioPlaybackError(
                    "Microsoft Neural TTS audio playback failed."
                )
                raise error from (cleanup_error or playback_errors[0])
            cleanup_error = self._close_stream(stream)
            if cleanup_error is not None:
                raise AudioPlaybackError(
                    "Microsoft Neural TTS audio playback could not be closed."
                ) from cleanup_error
        except KeyboardInterrupt as error:
            self._close_stream(stream, abort=True)
            raise SpeechInterruptedError(
                "Speech playback was interrupted."
            ) from error
        except AudioPlaybackError:
            raise
        except Exception as error:
            cleanup_error = self._close_stream(stream, abort=True)
            raise AudioPlaybackError(
                "Microsoft Neural TTS audio playback failed."
            ) from (cleanup_error or error)

    @staticmethod
    def _close_stream(
        stream: _AudioStream,
        *,
        abort: bool = False,
    ) -> BaseException | None:
        cleanup_error: BaseException | None = None
        if abort:
            try:
                stream.abort()
            except BaseException as error:
                cleanup_error = error
        try:
            stream.close()
        except BaseException as error:
            if cleanup_error is None:
                cleanup_error = error
        return cleanup_error
