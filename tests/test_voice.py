"""Mocked tests for local voice provider interfaces and orchestration."""

import tempfile
import unittest
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from unittest.mock import Mock, patch

import numpy

from app.ai import AIProvider, AIService
from app.config import PiperConfig, SpokenResponseConfig, WhisperConfig
from app.voice import (
    AudioPlaybackError,
    FasterWhisperSTT,
    MicrophonePermissionError,
    MicrophoneUnavailableError,
    MicrosoftNeuralTTS,
    NoSpeechDetectedError,
    PiperTTS,
    SpeechInterruptedError,
    SpeechRecognitionError,
    SpeechToTextProvider,
    TextToSpeechProvider,
    TextToSpeechUnavailableError,
    UnsupportedSpeechLanguageError,
    VoiceModelUnavailableError,
    VoiceService,
    VoiceTimeoutError,
)
from app.voice.diagnostic import run_diagnostic
from app.voice.microphone_capture_diagnostic import run_capture_diagnostic
from app.voice.microphone_test import (
    _AudioDevice,
    _DeviceRateAudioBackend,
    _parse_args,
    run_microphone_test,
)
from app.voice.stt import _TranscriptionModel
from app.voice.tts import (
    _AudioChunk,
    _NumpyArray,
    _PiperVoice,
)
from app.voice.microsoft_tts import NeuralPlaybackStats
from app.voice.microsoft_tts_test import _parse_args as _parse_neural_tts_args
from app.voice.microsoft_tts_test import run_neural_tts_test
from app.voice.tts_test import (
    _LANGUAGE_TEST_TEXT,
    _parse_args as _parse_tts_args,
    main as run_tts_main,
    run_tts_test,
)


@dataclass
class _FakeChunk:
    sample_rate: int = 22_050
    sample_width: int = 2
    sample_channels: int = 1
    audio_int16_bytes: bytes = b"\x01\x00\x02\x00"


class _FakeWhisperModel:
    def __init__(self, text: str = "recognized speech") -> None:
        self.text = text
        self.audio: object | None = None

    def transcribe(
        self,
        audio: object,
        *,
        language: str | None = None,
        vad_filter: bool = True,
    ) -> tuple[list[object], object]:
        self.audio = audio
        del language, vad_filter
        segments = [] if not self.text else [type("Segment", (), {"text": self.text})()]
        return segments, object()


class _FakeWhisperFactory:
    def __init__(self, model: _TranscriptionModel) -> None:
        self.model = model
        self.model_path: str | None = None

    def __call__(
        self,
        model_size_or_path: str,
        *,
        device: str,
        compute_type: str,
        local_files_only: bool,
    ) -> _TranscriptionModel:
        self.model_path = model_size_or_path
        if device != "cpu" or compute_type != "int8" or not local_files_only:
            raise AssertionError("STT should use CPU int8 and local-only files.")
        return self.model


class _FakeAudioInput:
    def __init__(self) -> None:
        self.recording: numpy.ndarray = numpy.zeros((1, 1), dtype=numpy.float32)
        self.record_arguments: tuple[int, float, int, str] | None = None
        self.record_device: int | None = None
        self.capture_sample_rate: float | None = None
        self.capture_blocking: bool | None = None
        self.wait_timeout: float | None = None
        self.record_error: Exception | None = None
        self.wait_error: Exception | None = None

    def rec(
        self,
        frames: int,
        *,
        samplerate: float,
        channels: int,
        dtype: str,
        device: int | None = None,
        blocking: bool = False,
    ) -> object:
        if self.record_error:
            raise self.record_error
        self.record_arguments = (frames, samplerate, channels, dtype)
        self.record_device = device
        self.capture_sample_rate = samplerate
        self.capture_blocking = blocking
        return self.recording

    def wait(self, timeout: float | None = None) -> None:
        self.wait_timeout = timeout
        if self.wait_error:
            raise self.wait_error


class _FakePiperVoice:
    def __init__(
        self,
        chunks: list[_AudioChunk] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.chunks = chunks if chunks is not None else [_FakeChunk()]
        self.error = error
        self.text: str | None = None

    def synthesize(self, text: str) -> object:
        self.text = text
        if self.error:
            raise self.error
        return iter(self.chunks)


class _FakePiperFactory:
    def __init__(self, voice: _PiperVoice) -> None:
        self.voice = voice
        self.model_path: str | None = None

    def load(self, model_path: str) -> _PiperVoice:
        self.model_path = model_path
        return self.voice


class _FakeAudioArray:
    def __init__(self) -> None:
        self.shape: tuple[int, int] | None = None

    def reshape(self, shape: tuple[int, int]) -> _NumpyArray:
        self.shape = shape
        return self


class _FakeNumpy:
    int16 = object()

    def __init__(self) -> None:
        self.buffer: bytes | None = None
        self.array = _FakeAudioArray()

    def frombuffer(self, buffer: bytes, *, dtype: object) -> _NumpyArray:
        self.buffer = buffer
        if dtype is not self.int16:
            raise AssertionError("Piper playback must use int16 PCM.")
        return self.array


class _FakeCallbackStop(Exception):
    pass


class _FakeCallbackAbort(Exception):
    pass


class _FakeAudioOutput:
    CallbackAbort = _FakeCallbackAbort
    CallbackStop = _FakeCallbackStop

    def __init__(self) -> None:
        self.data: object | None = None
        self.sample_rate: int | None = None
        self.wait_error: Exception | None = None
        self.play_error: Exception | None = None
        self.stopped = False
        self.closed = False
        self.auto_complete = True
        self.callback_error = False
        self.stream: _FakeMicrosoftAudioStream | None = None

    def play(self, data: object, samplerate: int) -> None:
        self.data = data
        self.sample_rate = samplerate
        if self.play_error:
            raise self.play_error

    def wait(self, timeout: float | None = None) -> None:
        del timeout
        if self.wait_error:
            raise self.wait_error

    def stop(self) -> None:
        self.stopped = True

    def OutputStream(
        self,
        *,
        samplerate: int,
        channels: int,
        dtype: str,
        callback: Callable[[numpy.ndarray, int, object, object], None],
        finished_callback: Callable[[], None],
    ) -> _FakeMicrosoftAudioStream:
        del channels, dtype
        self.sample_rate = samplerate
        self.stream = _FakeMicrosoftAudioStream(
            self,
            callback,
            finished_callback,
        )
        return self.stream


class _FakeCallbackOutput:
    def fill(self, value: int) -> None:
        del value
        raise RuntimeError("callback failed")


class _FakeMicrosoftAudioStream:
    CallbackAbort = _FakeCallbackAbort
    CallbackStop = _FakeCallbackStop

    def __init__(
        self,
        backend: _FakeAudioOutput,
        callback: Callable[[numpy.ndarray, int, object, object], None],
        finished_callback: Callable[[], None],
    ) -> None:
        self.backend = backend
        self.callback = callback
        self.finished_callback = finished_callback

    def start(self) -> None:
        if not self.backend.auto_complete:
            return
        output = (
            _FakeCallbackOutput()
            if self.backend.callback_error
            else numpy.zeros((4, 1), dtype=numpy.int16)
        )
        try:
            self.callback(output, 4, None, None)
        except (_FakeCallbackAbort, _FakeCallbackStop):
            pass
        finally:
            self.finished_callback()

    def abort(self) -> None:
        self.backend.stopped = True

    def close(self) -> None:
        self.backend.closed = True


class VoiceInterfaceTests(unittest.TestCase):
    def test_provider_interfaces_are_abstract(self) -> None:
        with self.assertRaises(TypeError):
            SpeechToTextProvider()  # type: ignore[abstract]
        with self.assertRaises(TypeError):
            TextToSpeechProvider()  # type: ignore[abstract]


class FasterWhisperProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.model_path = Path(self.temporary_directory.name) / "local-model"
        self.model_path.mkdir()
        (self.model_path / "model.bin").touch()
        (self.model_path / "config.json").touch()
        self.model = _FakeWhisperModel()
        self.factory = _FakeWhisperFactory(self.model)
        self.audio = _FakeAudioInput()
        self.provider = FasterWhisperSTT(
            self.model_path,
            duration_seconds=2,
            sample_rate=16_000,
            input_device=9,
            language="en",
            model_factory=self.factory,
            audio_backend=self.audio,
        )

    def test_captures_one_explicit_utterance_and_transcribes_in_memory(self) -> None:
        result = self.provider.listen()

        self.assertEqual(result, "recognized speech")
        self.assertEqual(self.audio.record_arguments, (32_000, 16_000, 1, "float32"))
        self.assertEqual(self.audio.wait_timeout, 7)
        self.assertEqual(self.audio.record_device, 9)
        self.assertIs(self.model.audio, self.audio.recording)
        self.assertEqual(self.factory.model_path, str(self.model_path.resolve()))

    def test_microphone_permission_failure_is_reported(self) -> None:
        self.audio.record_error = PermissionError("denied")

        with self.assertRaises(MicrophonePermissionError):
            self.provider.listen()

    def test_microphone_device_failure_is_reported(self) -> None:
        self.audio.record_error = OSError("device missing")

        with self.assertRaises(MicrophoneUnavailableError):
            self.provider.listen()

    def test_microphone_timeout_is_reported(self) -> None:
        self.audio.wait_error = TimeoutError("timed out")

        with self.assertRaises(VoiceTimeoutError):
            self.provider.listen()

    def test_missing_model_fails_before_opening_microphone(self) -> None:
        provider = FasterWhisperSTT(
            Path(self.temporary_directory.name) / "not-installed",
            model_factory=self.factory,
            audio_backend=self.audio,
        )

        with self.assertRaises(VoiceModelUnavailableError):
            provider.listen()
        self.assertIsNone(self.audio.record_arguments)
        self.assertIsNone(self.factory.model_path)

    def test_empty_transcription_is_reported(self) -> None:
        self.model.text = ""

        with self.assertRaises(NoSpeechDetectedError):
            self.provider.listen()

    def test_recognition_failure_is_reported(self) -> None:
        class FailedModel:
            def transcribe(
                self,
                audio: object,
                *,
                language: str | None = None,
                vad_filter: bool = True,
            ) -> tuple[list[object], object]:
                del audio, language, vad_filter
                raise RuntimeError("decode error")

        provider = FasterWhisperSTT(
            self.model_path,
            model_factory=_FakeWhisperFactory(FailedModel()),
            audio_backend=self.audio,
        )

        with self.assertRaises(SpeechRecognitionError):
            provider.listen()


class PiperProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.model_path = Path(self.temporary_directory.name) / "voice.onnx"
        self.model_path.touch()
        Path(f"{self.model_path}.json").write_text(
            '{"phoneme_type": "espeak"}',
            encoding="utf-8",
        )
        self.voice = _FakePiperVoice()
        self.factory = _FakePiperFactory(self.voice)
        self.audio = _FakeAudioOutput()
        self.numpy = _FakeNumpy()
        self.provider = PiperTTS(
            self.model_path,
            voice_factory=self.factory,
            audio_backend=self.audio,
            numpy_module=self.numpy,
        )

    def test_synthesizes_and_plays_local_pcm_without_saving_audio(self) -> None:
        self.provider.speak("Hello")

        self.assertEqual(self.voice.text, "Hello")
        self.assertEqual(self.factory.model_path, str(self.model_path.resolve()))
        self.assertEqual(self.numpy.buffer, b"\x01\x00\x02\x00")
        self.assertIs(self.audio.data, self.numpy.array)
        self.assertEqual(self.audio.sample_rate, 22_050)

    def test_returns_sample_rate_count_and_duration_after_playback(self) -> None:
        stats = self.provider.speak_with_stats("Hello")

        self.assertIsNotNone(stats)
        self.assertEqual(stats.sample_rate, 22_050)
        self.assertEqual(stats.sample_count, 2)
        self.assertAlmostEqual(stats.duration_seconds, 2 / 22_050)
        self.assertIs(self.audio.data, self.numpy.array)

    def test_missing_local_voice_is_reported(self) -> None:
        provider = PiperTTS(
            Path(self.temporary_directory.name) / "missing.onnx",
            voice_factory=self.factory,
            audio_backend=self.audio,
            numpy_module=self.numpy,
        )

        with self.assertRaises(VoiceModelUnavailableError):
            provider.speak("Hello")

    def test_missing_companion_voice_config_is_reported(self) -> None:
        Path(f"{self.model_path}.json").unlink()

        with self.assertRaisesRegex(
            VoiceModelUnavailableError,
            r"matching voice config must exist",
        ):
            self.provider.speak("Hello")

    def test_voice_with_auto_downloading_pinyin_resource_is_rejected_offline(self) -> None:
        Path(f"{self.model_path}.json").write_text(
            '{"phoneme_type": "pinyin"}',
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            TextToSpeechUnavailableError,
            "blocked in Veronica's offline voice path",
        ):
            self.provider.speak("Hello")
        self.assertIsNone(self.factory.model_path)

    def test_speaks_with_configured_hindi_voice(self) -> None:
        config = PiperConfig(
            "",
            self.model_path,
            hindi_model_path=self.model_path,
            english_model_path=None,
        )
        provider = PiperTTS(
            config=config,
            voice_factory=self.factory,
            audio_backend=self.audio,
            numpy_module=self.numpy,
        )

        provider.speak("नमस्ते", language="hi")

        self.assertEqual(self.voice.text, "नमस्ते")
        self.assertEqual(self.factory.model_path, str(self.model_path.resolve()))

    def test_speaks_with_configured_english_voice(self) -> None:
        config = PiperConfig(
            "",
            self.model_path,
            hindi_model_path=None,
            english_model_path=self.model_path,
        )
        provider = PiperTTS(
            config=config,
            voice_factory=self.factory,
            audio_backend=self.audio,
            numpy_module=self.numpy,
        )

        provider.speak("Hello", language="en")

        self.assertEqual(self.voice.text, "Hello")
        self.assertEqual(self.factory.model_path, str(self.model_path.resolve()))

    def test_missing_requested_english_voice_has_actionable_error(self) -> None:
        config = PiperConfig(
            "",
            self.model_path,
            hindi_model_path=self.model_path,
            english_model_path=None,
        )
        provider = PiperTTS(
            config=config,
            voice_factory=self.factory,
            audio_backend=self.audio,
            numpy_module=self.numpy,
        )

        with self.assertRaisesRegex(
            VoiceModelUnavailableError,
            "PIPER_EN_MODEL_PATH",
        ):
            provider.speak("Hello", language="en")

    def test_unsupported_language_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            UnsupportedSpeechLanguageError,
            "must be 'hi' or 'en'",
        ):
            self.provider.speak("Hello", language="fr")

    def test_synthesis_failure_is_reported(self) -> None:
        self.voice.error = RuntimeError("synthesis failed")

        with self.assertRaises(TextToSpeechUnavailableError):
            self.provider.speak("Hello")

    def test_missing_piper_runtime_is_reported(self) -> None:
        provider = PiperTTS(self.model_path, audio_backend=self.audio)
        with patch(
            "app.voice.tts.importlib.import_module",
            side_effect=ImportError("piper runtime unavailable"),
        ), self.assertRaises(TextToSpeechUnavailableError):
            provider.speak("Hello")

    def test_playback_failure_is_reported(self) -> None:
        self.audio.play_error = OSError("speaker unavailable")

        with self.assertRaises(AudioPlaybackError):
            self.provider.speak("Hello")

    @patch("app.voice.tts.threading.Thread")
    def test_playback_timeout_stops_audio_and_returns_error(
        self,
        thread_class: Mock,
    ) -> None:
        thread_class.return_value.start.return_value = None

        with self.assertRaisesRegex(AudioPlaybackError, "did not finish"):
            self.provider.speak("Hello")

        self.assertTrue(self.audio.stopped)

    def test_interrupted_playback_stops_audio(self) -> None:
        self.audio.wait_error = KeyboardInterrupt()

        with self.assertRaises(SpeechInterruptedError):
            self.provider.speak("Hello")
        self.assertTrue(self.audio.stopped)

    def test_empty_text_does_nothing_without_loading_voice_or_audio(self) -> None:
        provider = PiperTTS(
            Path(self.temporary_directory.name) / "not-installed.onnx",
            voice_factory=self.factory,
            audio_backend=self.audio,
            numpy_module=self.numpy,
        )

        provider.speak(" \t\n ")

        self.assertIsNone(self.factory.model_path)
        self.assertIsNone(self.audio.data)


class MicrosoftNeuralProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = SpokenResponseConfig(
            enabled=True,
            language="en",
            hindi_voice="hi-IN-SwaraNeural",
            english_voice="hi-IN-SwaraNeural",
            rate="-10%",
            pitch="+0Hz",
            volume="+0%",
        )
        self.audio = _FakeAudioOutput()
        self.samples = numpy.array([0, 120, -120], dtype=numpy.int16)
        self.synthesis_args: list[tuple[str, str, str, str, str]] = []

        def decode_audio(audio_bytes: bytes) -> numpy.ndarray:
            self.assertEqual(audio_bytes, b"encoded-audio")
            return self.samples

        self.decode_audio = decode_audio

        async def synthesize(
            text: str,
            voice: str,
            rate: str,
            pitch: str,
            volume: str,
        ) -> bytes:
            self.synthesis_args.append((text, voice, rate, pitch, volume))
            return b"encoded-audio"

        self.provider = MicrosoftNeuralTTS(
            self.config,
            audio_backend=self.audio,
            synthesizer=synthesize,
            decoder=self.decode_audio,
        )

    def test_uses_same_female_swara_voice_for_hindi_and_english(self) -> None:
        self.provider.speak("Namaste Veronica", language="hi")
        self.provider.speak("Hello, Python and GitHub", language="en")

        self.assertEqual(
            [args[1] for args in self.synthesis_args],
            ["hi-IN-SwaraNeural", "hi-IN-SwaraNeural"],
        )
        self.assertEqual(
            [(args[2], args[3], args[4]) for args in self.synthesis_args],
            [("-10%", "+0Hz", "+0%"), ("-10%", "+0Hz", "+0%")],
        )
        self.assertEqual(self.audio.sample_rate, 24_000)

    def test_can_select_an_official_female_english_voice_explicitly(self) -> None:
        alternate_config = SpokenResponseConfig(
            enabled=True,
            language="en",
            hindi_voice="hi-IN-SwaraNeural",
            english_voice="en-IN-NeerjaNeural",
            rate="-10%",
            pitch="+0Hz",
            volume="+0%",
        )
        provider = MicrosoftNeuralTTS(
            alternate_config,
            audio_backend=self.audio,
            synthesizer=self.provider._synthesizer,
            decoder=self.decode_audio,
        )

        provider.speak("English audition", language="en")

        self.assertEqual(self.synthesis_args[-1][1], "en-IN-NeerjaNeural")

    def test_rejects_male_voice_even_if_constructed_directly(self) -> None:
        male_config = SpokenResponseConfig(
            enabled=True,
            language="en",
            hindi_voice="hi-IN-SwaraNeural",
            english_voice="en-IN-PrabhatNeural",
            rate="-10%",
            pitch="+0Hz",
            volume="+0%",
        )
        provider = MicrosoftNeuralTTS(
            male_config,
            audio_backend=self.audio,
            synthesizer=self.provider._synthesizer,
            decoder=self.decode_audio,
        )

        with self.assertRaises(UnsupportedSpeechLanguageError):
            provider.speak("No male fallback", language="en")

        self.assertEqual(self.synthesis_args, [])

    def test_requires_explicit_language(self) -> None:
        with self.assertRaises(UnsupportedSpeechLanguageError):
            self.provider.speak("Hello")

    def test_empty_text_does_not_call_network_or_audio(self) -> None:
        self.provider.speak(" \t\n ", language="en")

        self.assertEqual(self.synthesis_args, [])
        self.assertIsNone(self.audio.data)

    def test_reports_network_synthesis_failure_as_voice_error(self) -> None:
        async def fail_synthesis(
            text: str,
            voice: str,
            rate: str,
            pitch: str,
            volume: str,
        ) -> bytes:
            del text, voice, rate, pitch, volume
            raise OSError("network unavailable")

        provider = MicrosoftNeuralTTS(
            self.config,
            audio_backend=self.audio,
            synthesizer=fail_synthesis,
            decoder=self.decode_audio,
        )

        with self.assertRaises(TextToSpeechUnavailableError):
            provider.speak("Hello", language="en")

    def test_reports_playback_failure(self) -> None:
        self.audio.callback_error = True

        with self.assertRaises(AudioPlaybackError):
            self.provider.speak("Hello", language="en")

        self.assertTrue(self.audio.stopped)
        self.assertTrue(self.audio.closed)

    def test_playback_completes_and_closes_the_stream(self) -> None:
        stats = self.provider.speak_with_stats("Hello", language="en")

        self.assertIsNotNone(stats)
        self.assertEqual(self.audio.sample_rate, 24_000)
        self.assertTrue(self.audio.closed)
        self.assertFalse(self.audio.stopped)

    def test_playback_timeout_aborts_and_closes_the_stream(self) -> None:
        self.audio.auto_complete = False
        with patch(
            "app.voice.microsoft_tts._PLAYBACK_TIMEOUT_MIN_SECONDS",
            0.001,
        ), self.assertRaisesRegex(AudioPlaybackError, "did not finish"):
            self.provider.speak("Hello", language="en")

        self.assertTrue(self.audio.stopped)
        self.assertTrue(self.audio.closed)

    def test_main_thread_interruption_aborts_and_closes_the_stream(self) -> None:
        with patch(
            "app.voice.microsoft_tts.threading.Event.wait",
            side_effect=KeyboardInterrupt,
        ), self.assertRaises(SpeechInterruptedError):
            self.provider.speak("Hello", language="en")

        self.assertTrue(self.audio.stopped)
        self.assertTrue(self.audio.closed)

    def test_audition_uses_exact_test_text_and_female_voice(self) -> None:
        output = StringIO()
        with patch("app.voice.microsoft_tts_test.MicrosoftNeuralTTS") as tts_class:
            tts_class.return_value.speak_with_stats.return_value = NeuralPlaybackStats(
                voice="hi-IN-SwaraNeural",
                sample_rate=24_000,
                sample_count=24_000,
                duration_seconds=1,
            )
            exit_code = run_neural_tts_test(
                self.config,
                language="en",
                output=output,
            )

        self.assertEqual(exit_code, 0)
        tts_class.assert_called_once()
        self.assertEqual(
            tts_class.return_value.speak_with_stats.call_args.args[0],
            "Hello! I am Veronica. I can help you with Python, web development, "
            "DSA, GitHub, APIs, and artificial intelligence.",
        )
        self.assertIn("hi-IN-SwaraNeural", output.getvalue())
        self.assertIn("playback completed", output.getvalue())

    def test_voice_audition_cli_allows_only_female_language_voice_choices(self) -> None:
        self.assertEqual(
            _parse_neural_tts_args(["--language", "en", "--voice", "en-IN-NeerjaNeural"]).voice,
            "en-IN-NeerjaNeural",
        )
        output = StringIO()
        result = run_neural_tts_test(
            self.config,
            language="en",
            voice="en-IN-PrabhatNeural",
            output=output,
        )

        self.assertEqual(result, 2)
        self.assertIn("female-only allowlist", output.getvalue())


class PiperDiagnosticTests(unittest.TestCase):
    def test_model_path_override_is_available(self) -> None:
        args = _parse_tts_args(["--model-path", "voices/test.onnx"])
        self.assertEqual(args.model_path, Path("voices/test.onnx"))

    def test_language_selection_is_available(self) -> None:
        self.assertEqual(_parse_tts_args(["--language", "hi"]).language, "hi")
        self.assertEqual(_parse_tts_args(["--language", "en"]).language, "en")

    def test_model_path_override_targets_selected_language(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            override_path = Path(temporary_directory) / "voice.onnx"
            default_config = PiperConfig(
                "single",
                Path("single.onnx"),
                hindi_model_path=Path("default-hi.onnx"),
                english_model_path=Path("default-en.onnx"),
            )
            with patch(
                "app.voice.tts_test.load_piper_config",
                return_value=default_config,
            ), patch(
                "app.voice.tts_test.run_tts_test",
                return_value=0,
            ) as run_test, patch(
                "app.voice.tts_test.sys.stdout",
                StringIO(),
            ):
                result = run_tts_main(
                    [
                        "--language",
                        "hi",
                        "--model-path",
                        str(override_path),
                    ]
                )

        self.assertEqual(result, 0)
        selected_config = run_test.call_args.args[0]
        self.assertEqual(selected_config.hindi_model_path, override_path)
        self.assertEqual(selected_config.english_model_path, Path("default-en.onnx"))
        self.assertEqual(run_test.call_args.kwargs["language"], "hi")

    def test_missing_voice_reports_required_files_without_download(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            model_path = Path(temporary_directory) / "voice.onnx"
            output = StringIO()

            result = run_tts_test(
                PiperConfig("test voice", model_path),
                output=output,
            )

        self.assertEqual(result, 1)
        self.assertIn("voice.onnx", output.getvalue())
        self.assertIn("voice.onnx.json", output.getvalue())
        self.assertIn("No download was attempted", output.getvalue())

    def test_plays_sample_text_with_piper_when_model_files_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            model_path = Path(temporary_directory) / "voice.onnx"
            model_path.touch()
            Path(f"{model_path}.json").write_text(
                '{"phoneme_type": "espeak"}',
                encoding="utf-8",
            )
            config = PiperConfig(
                "test voice",
                model_path,
                hindi_model_path=model_path,
                english_model_path=model_path,
            )
            output = StringIO()
            with patch("app.voice.tts_test.PiperTTS") as piper_tts:
                piper_tts.return_value.speak_with_stats.return_value = Mock(
                    sample_rate=22_050,
                    sample_count=44_100,
                    duration_seconds=2.0,
                )
                result = run_tts_test(config, language="en", output=output)

        self.assertEqual(result, 0)
        piper_tts.assert_called_once_with(config=config)
        piper_tts.return_value.speak_with_stats.assert_called_once_with(
            _LANGUAGE_TEST_TEXT["en"],
            language="en",
        )
        self.assertIn("Selected language: English (en)", output.getvalue())
        self.assertIn(f"Piper model path: {model_path}", output.getvalue())
        self.assertIn("Synthesized sample rate: 22050 Hz", output.getvalue())
        self.assertIn("Generated audio samples: 44100", output.getvalue())
        self.assertIn("Generated audio duration: 2.00 seconds", output.getvalue())
        self.assertIn("Local Piper playback completed.", output.getvalue())

    def test_hindi_uses_hindi_path_and_default_hindi_text(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            hindi_model = Path(temporary_directory) / "hindi.onnx"
            english_model = Path(temporary_directory) / "english.onnx"
            for model_path in (hindi_model, english_model):
                model_path.touch()
                Path(f"{model_path}.json").write_text(
                    '{"phoneme_type": "espeak"}',
                    encoding="utf-8",
                )
            config = PiperConfig(
                "single",
                english_model,
                hindi_model_path=hindi_model,
                english_model_path=english_model,
            )
            output = StringIO()
            with patch("app.voice.tts_test.PiperTTS") as piper_tts:
                piper_tts.return_value.speak_with_stats.return_value = Mock(
                    sample_rate=22_050,
                    sample_count=22_050,
                    duration_seconds=1.0,
                )
                result = run_tts_test(config, language="hi", output=output)

        self.assertEqual(result, 0)
        piper_tts.return_value.speak_with_stats.assert_called_once_with(
            _LANGUAGE_TEST_TEXT["hi"],
            language="hi",
        )
        self.assertIn(f"Piper model path: {hindi_model}", output.getvalue())
        self.assertIn("Selected language: Hindi (hi)", output.getvalue())

    def test_reports_local_voice_or_playback_errors(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            model_path = Path(temporary_directory) / "voice.onnx"
            model_path.touch()
            Path(f"{model_path}.json").touch()
            output = StringIO()
            with patch(
                "app.voice.tts_test.PiperTTS",
            ) as piper_tts:
                piper_tts.return_value.speak_with_stats.side_effect = AudioPlaybackError(
                    "default speaker unavailable"
                )
                result = run_tts_test(
                    PiperConfig("test voice", model_path),
                    output=output,
                )

        self.assertEqual(result, 1)
        self.assertIn(
            "Local Piper test failed: default speaker unavailable",
            output.getvalue(),
        )


class VoiceServiceTests(unittest.TestCase):
    def test_orchestrates_stt_ai_and_tts_in_order(self) -> None:
        events: list[str] = []

        class STT(SpeechToTextProvider):
            def listen(self) -> str:
                events.append("listen")
                return "Hello Veronica"

        class TTS(TextToSpeechProvider):
            def speak(self, text: str, *, language: str | None = None) -> None:
                del language
                events.append(f"speak:{text}")

        provider = Mock(spec=AIProvider)
        def generate_response(messages: list[dict[str, str]]) -> str:
            if "Classify the user's current conversational intent" in messages[0]["content"]:
                events.append("classify")
                return '{"role":"assistant"}'
            events.append("respond")
            return "Hello!"

        provider.generate_response.side_effect = generate_response
        ai_service = AIService(provider)
        result = VoiceService(STT(), ai_service, TTS()).interact()

        self.assertEqual(result, "Hello!")
        self.assertEqual(events, ["listen", "respond", "speak:Hello!"])

    def test_microphone_failure_prevents_ai_and_speech(self) -> None:
        stt = Mock(spec=SpeechToTextProvider)
        stt.listen.side_effect = MicrophoneUnavailableError("no mic")
        ai_service = Mock(spec=AIService)
        tts = Mock(spec=TextToSpeechProvider)

        with self.assertRaises(MicrophoneUnavailableError):
            VoiceService(stt, ai_service, tts).interact()

        ai_service.respond.assert_not_called()
        tts.speak.assert_not_called()

    def test_tts_failure_is_reported_after_ai_response(self) -> None:
        stt = Mock(spec=SpeechToTextProvider)
        stt.listen.return_value = "Hello"
        ai_service = Mock(spec=AIService)
        ai_service.respond.return_value = "Hi!"
        tts = Mock(spec=TextToSpeechProvider)
        tts.speak.side_effect = AudioPlaybackError("no output")

        with self.assertRaises(AudioPlaybackError):
            VoiceService(stt, ai_service, tts).interact()

        ai_service.respond.assert_called_once_with("Hello")
        tts.speak.assert_called_once_with("Hi!")


class WhisperDiagnosticTests(unittest.TestCase):
    def test_reports_model_and_input_devices_without_recording(self) -> None:
        class AudioBackend:
            def query_devices(self) -> list[dict[str, str | int]]:
                return [
                    {"name": "Microphone A", "max_input_channels": 1},
                    {"name": "Speakers", "max_input_channels": 0},
                ]

        with tempfile.TemporaryDirectory() as temporary_directory:
            model_path = Path(temporary_directory) / "base"
            model_path.mkdir()
            (model_path / "model.bin").touch()
            (model_path / "config.json").touch()
            config = WhisperConfig(
                model="base",
                model_path=model_path,
                device="cpu",
                compute_type="int8",
            )
            output = StringIO()

            result = run_diagnostic(
                config,
                audio_backend=AudioBackend(),
                output=output,
            )

        self.assertEqual(result, 0)
        self.assertIn("Model files found locally.", output.getvalue())
        self.assertIn("Microphone A", output.getvalue())
        self.assertIn("No recording was started.", output.getvalue())

    def test_reports_missing_model_without_attempting_download(self) -> None:
        class AudioBackend:
            def query_devices(self) -> list[object]:
                return []

        with tempfile.TemporaryDirectory() as temporary_directory:
            config = WhisperConfig(
                model="base",
                model_path=Path(temporary_directory) / "missing",
                device="cpu",
                compute_type="int8",
            )
            output = StringIO()
            result = run_diagnostic(
                config,
                audio_backend=AudioBackend(),
                output=output,
            )

        self.assertEqual(result, 1)
        self.assertIn("No model download was attempted.", output.getvalue())
        self.assertIn("No recording was started.", output.getvalue())


class OneShotMicrophoneTestTests(unittest.TestCase):
    def test_audio_adapter_keeps_one_dimensional_input_and_returns_float(self) -> None:
        backend = _FakeAudioInput()
        backend.recording = numpy.array([0.25, -0.5, 1], dtype=numpy.float64)
        adapter = _DeviceRateAudioBackend(
            backend,
            device_index=11,
            device_sample_rate=16_000,
        )

        result = adapter.rec(
            3,
            samplerate=16_000,
            channels=1,
            dtype="float32",
        )

        result_array = numpy.asarray(result)
        self.assertEqual(result_array.shape, (3,))
        self.assertEqual(result_array.dtype, numpy.float32)
        numpy.testing.assert_allclose(result_array, [0.25, -0.5, 1])

    def test_audio_adapter_flattens_single_channel_2d_input(self) -> None:
        backend = _FakeAudioInput()
        backend.recording = numpy.array([[0.25], [-0.5], [1]], dtype=numpy.float32)
        adapter = _DeviceRateAudioBackend(
            backend,
            device_index=11,
            device_sample_rate=16_000,
        )

        result = adapter.rec(
            3,
            samplerate=16_000,
            channels=1,
            dtype="float32",
        )

        result_array = numpy.asarray(result)
        self.assertEqual(result_array.shape, (3,))
        numpy.testing.assert_allclose(result_array, [0.25, -0.5, 1])

    def test_audio_adapter_averages_multichannel_input_not_interleaves(self) -> None:
        backend = _FakeAudioInput()
        backend.recording = numpy.array(
            [[1, 9], [2, 6], [-2, 4]],
            dtype=numpy.float32,
        )
        adapter = _DeviceRateAudioBackend(
            backend,
            device_index=11,
            device_sample_rate=16_000,
        )

        result = adapter.rec(
            3,
            samplerate=16_000,
            channels=1,
            dtype="float32",
        )

        result_array = numpy.asarray(result)
        self.assertEqual(result_array.shape, (3,))
        self.assertEqual(result_array.dtype, numpy.float32)
        numpy.testing.assert_allclose(result_array, [5, 4, 1])
        self.assertNotEqual(result_array.size, 6)

    def test_audio_adapter_keeps_48khz_to_16khz_resampling_mono(self) -> None:
        backend = _FakeAudioInput()
        backend.recording = numpy.array(
            [
                [0.0, 0.6],
                [0.3, 0.9],
                [0.6, 1.2],
                [0.9, 1.5],
                [1.2, 1.8],
                [1.5, 2.1],
            ],
            dtype=numpy.float32,
        )
        adapter = _DeviceRateAudioBackend(
            backend,
            device_index=11,
            device_sample_rate=48_000,
        )

        result = adapter.rec(
            2,
            samplerate=16_000,
            channels=1,
            dtype="float32",
        )

        result_array = numpy.asarray(result)
        self.assertEqual(result_array.shape, (2,))
        self.assertEqual(result_array.dtype, numpy.float32)
        numpy.testing.assert_allclose(result_array, [0.6, 1.5])

    def test_selects_and_records_once_from_realtek_microphone(self) -> None:
        devices: list[_AudioDevice] = [
            {
                "name": "DroidCam Virtual Audio",
                "max_input_channels": 1,
                "default_samplerate": 44_100.0,
                "hostapi": 0,
            },
            {
                "name": "Microphone (Realtek(R) Audio)",
                "max_input_channels": 2,
                "default_samplerate": 44_100.0,
                "hostapi": 0,
            },
            {
                "name": "Microphone (Realtek(R) Audio)",
                "max_input_channels": 2,
                "default_samplerate": 48_000.0,
                "hostapi": 1,
            },
            {
                "name": "Realtek Stereo Mix",
                "max_input_channels": 2,
                "default_samplerate": 48_000.0,
                "hostapi": 1,
            },
        ]

        class TestAudioBackend(_FakeAudioInput):
            def __init__(self) -> None:
                super().__init__()
                self.input_settings: tuple[int, int, float, str] | None = None

            def query_devices(self) -> Sequence[_AudioDevice]:
                return devices

            def query_hostapis(self, index: int) -> dict[str, str]:
                return {"name": ("MME", "Windows WASAPI")[index]}

            def check_input_settings(
                self,
                *,
                device: int,
                channels: int,
                samplerate: float,
                dtype: str,
            ) -> None:
                self.input_settings = (device, channels, samplerate, dtype)

        with tempfile.TemporaryDirectory() as temporary_directory:
            model_path = Path(temporary_directory) / "base"
            model_path.mkdir()
            (model_path / "model.bin").touch()
            (model_path / "config.json").touch()
            backend = TestAudioBackend()
            whisper_model = _FakeWhisperModel("Veronica test transcription")
            factory = _FakeWhisperFactory(whisper_model)
            config = WhisperConfig(
                "base",
                model_path,
                "cpu",
                "int8",
            )
            backend.recording = numpy.zeros((240_000, 1), dtype=numpy.float32)
            output = StringIO()
            with patch(
                "app.voice.microphone_test.load_whisper_config",
                return_value=config,
            ), patch("app.voice.stt.load_whisper_config", return_value=config), patch(
                "app.voice.stt.importlib.import_module",
                return_value=Mock(WhisperModel=factory),
            ):
                result = run_microphone_test(
                    audio_backend=backend,
                    input_fn=lambda _: "",
                    output=output,
                )

        self.assertEqual(result, 0)
        self.assertEqual(backend.record_device, 2)
        self.assertEqual(backend.record_arguments, (240_000, 48_000.0, 1, "float32"))
        self.assertEqual(backend.capture_sample_rate, 48_000.0)
        self.assertTrue(backend.capture_blocking)
        self.assertEqual(backend.input_settings, (2, 1, 48_000.0, "float32"))
        self.assertEqual(numpy.asarray(whisper_model.audio).shape, (80_000,))
        self.assertEqual(numpy.asarray(whisper_model.audio).dtype, numpy.float32)
        self.assertIn("Realtek input devices:", output.getvalue())
        self.assertIn("Selected device [2]", output.getvalue())
        self.assertIn("48000 Hz", output.getvalue())
        self.assertIn("Veronica test transcription", output.getvalue())

    def test_debug_reports_underlying_recognition_error_and_configuration(self) -> None:
        class FailedModel:
            def transcribe(
                self,
                audio: object,
                *,
                language: str | None = None,
                vad_filter: bool = True,
            ) -> tuple[list[object], object]:
                del audio, language, vad_filter
                raise RuntimeError("CTranslate2 decoder initialization failed")

        devices: list[_AudioDevice] = [
            {
                "name": "Microphone (Realtek(R) Audio)",
                "max_input_channels": 2,
                "default_samplerate": 48_000.0,
                "hostapi": 0,
            }
        ]

        class AudioBackend(_FakeAudioInput):
            def __init__(self) -> None:
                super().__init__()
                self.recording = numpy.zeros((240_000, 1), dtype=numpy.float32)

            def query_devices(self) -> Sequence[_AudioDevice]:
                return devices

            def query_hostapis(self, index: int) -> dict[str, str]:
                del index
                return {"name": "Windows WASAPI"}

            def check_input_settings(self, **_: object) -> None:
                pass

        with tempfile.TemporaryDirectory() as temporary_directory:
            model_path = Path(temporary_directory) / "base"
            model_path.mkdir()
            (model_path / "model.bin").touch()
            (model_path / "config.json").touch()
            config = WhisperConfig("base", model_path, "cpu", "int8")
            factory = _FakeWhisperFactory(FailedModel())
            output = StringIO()
            with patch(
                "app.voice.microphone_test.load_whisper_config",
                return_value=config,
            ), patch(
                "app.voice.stt.importlib.import_module",
                return_value=Mock(WhisperModel=factory),
            ):
                result = run_microphone_test(
                    device_index=0,
                    audio_backend=AudioBackend(),
                    input_fn=lambda _: "",
                    output=output,
                    debug=True,
                )

        transcript = output.getvalue()
        self.assertEqual(result, 1)
        self.assertIn(
            "Microphone transcription failed: Local speech recognition failed.",
            transcript,
        )
        self.assertIn("Whisper model: base", transcript)
        self.assertIn(f"Model path: {model_path}", transcript)
        self.assertIn("Device: cpu", transcript)
        self.assertIn("Compute type: int8", transcript)
        self.assertIn("Audio sample rate: 16000 Hz", transcript)
        self.assertIn("Captured device sample rate: 48000 Hz", transcript)
        self.assertIn("Captured device sample count: 240000", transcript)
        self.assertIn("Whisper audio sample count: 80000", transcript)
        self.assertIn(
            "Underlying exception: RuntimeError: "
            "CTranslate2 decoder initialization failed",
            transcript,
        )

    def test_debug_flag_is_available_on_command_line(self) -> None:
        self.assertTrue(_parse_args(["--debug"]).debug)

    def test_invalid_duration_does_not_prompt_or_record(self) -> None:
        backend = _FakeAudioInput()
        output = StringIO()
        result = run_microphone_test(
            duration_seconds=30,
            audio_backend=backend,
            input_fn=Mock(),
            output=output,
        )

        self.assertEqual(result, 2)
        self.assertIsNone(backend.record_arguments)

    def test_missing_realtek_requires_explicit_device_index(self) -> None:
        class NonRealtekAudio(_FakeAudioInput):
            def query_devices(self) -> list[dict[str, str | int | float]]:
                return [
                    {
                        "name": "DroidCam Virtual Audio",
                        "max_input_channels": 1,
                        "default_samplerate": 48_000.0,
                        "hostapi": 0,
                    }
                ]

            def query_hostapis(self, index: int) -> dict[str, str]:
                del index
                return {"name": "MME"}

            def check_input_settings(self, **_: object) -> None:
                pass

        backend = NonRealtekAudio()
        output = StringIO()
        result = run_microphone_test(
            audio_backend=backend,
            input_fn=Mock(),
            output=output,
        )

        self.assertEqual(result, 1)
        self.assertIn("No Realtek microphone input", output.getvalue())
        self.assertIsNone(backend.record_arguments)

    def test_selected_input_device_can_be_specified(self) -> None:
        class AudioBackend(_FakeAudioInput):
            def query_devices(self) -> list[dict[str, str | int | float]]:
                return [
                    {
                        "name": "DroidCam Virtual Audio",
                        "max_input_channels": 1,
                        "default_samplerate": 48_000.0,
                        "hostapi": 0,
                    },
                ]

            def query_hostapis(self, index: int) -> dict[str, str]:
                del index
                return {"name": "MME"}

            def check_input_settings(self, **_: object) -> None:
                pass

        backend = AudioBackend()
        output = StringIO()
        with patch(
            "app.voice.microphone_test.FasterWhisperSTT",
            side_effect=MicrophoneUnavailableError("model missing"),
        ):
            result = run_microphone_test(
                device_index=0,
                audio_backend=backend,
                input_fn=lambda _: "",
                output=output,
            )

        self.assertEqual(result, 1)
        self.assertIn("Microphone transcription failed: model missing", output.getvalue())
        self.assertIsNone(backend.record_arguments)

    def test_cancelled_activation_does_not_record(self) -> None:
        class AudioBackend(_FakeAudioInput):
            def query_devices(self) -> list[dict[str, str | int | float]]:
                return [
                    {
                        "name": "Microphone (Realtek)",
                        "max_input_channels": 1,
                        "default_samplerate": 48_000.0,
                        "hostapi": 0,
                    }
                ]

            def query_hostapis(self, index: int) -> dict[str, str]:
                del index
                return {"name": "Windows WASAPI"}

            def check_input_settings(self, **_: object) -> None:
                pass

        backend = AudioBackend()
        output = StringIO()
        result = run_microphone_test(
            audio_backend=backend,
            input_fn=lambda _: (_ for _ in ()).throw(KeyboardInterrupt()),
            output=output,
        )

        self.assertEqual(result, 0)
        self.assertIsNone(backend.record_arguments)
        self.assertIn("cancelled", output.getvalue())


class MicrophoneCaptureDiagnosticTests(unittest.TestCase):
    def setUp(self) -> None:
        self.devices = [
            {
                "name": "DroidCam Virtual Audio",
                "max_input_channels": 1,
                "default_samplerate": 44_100.0,
                "hostapi": 0,
            },
            {
                "name": "Microphone (Realtek(R) Audio)",
                "max_input_channels": 2,
                "default_samplerate": 48_000.0,
                "hostapi": 1,
            },
            {
                "name": "Speakers",
                "max_input_channels": 0,
                "default_samplerate": 48_000.0,
                "hostapi": 1,
            },
        ]
        self.backend = Mock()
        self.backend.query_devices.return_value = self.devices
        self.backend.query_hostapis.side_effect = [
            {"name": "MME"},
            {"name": "Windows WASAPI"},
            {"name": "Windows WASAPI"},
        ]
        self.backend.default.device = (1, 2)
        self.backend.rec.return_value = numpy.zeros((96_000, 1), dtype=numpy.float32)
        self.output = StringIO()

    def test_lists_devices_and_captures_two_seconds_in_mono(self) -> None:
        self.backend.rec.return_value = numpy.array(
            [[-0.5], [0.0], [0.5], [0.25]],
            dtype=numpy.float32,
        )

        result = run_capture_diagnostic(
            audio_backend=self.backend,
            input_fn=lambda _: "",
            output=self.output,
        )

        self.assertEqual(result, 0)
        self.backend.check_input_settings.assert_called_once_with(
            device=1,
            channels=1,
            samplerate=48_000.0,
            dtype="float32",
        )
        self.backend.rec.assert_called_once_with(
            96_000,
            samplerate=48_000.0,
            channels=1,
            dtype="float32",
            device=1,
        )
        self.backend.wait.assert_called_once_with()
        transcript = self.output.getvalue()
        self.assertIn("[1] Microphone (Realtek(R) Audio)", transcript)
        self.assertIn("max_input_channels=2", transcript)
        self.assertIn("default_samplerate=48000", transcript)
        self.assertIn("host_api=Windows WASAPI", transcript)
        self.assertIn("Current sounddevice default input device: [1]", transcript)
        self.assertIn("Samples: 4", transcript)
        self.assertIn("RMS amplitude: 0.37500000", transcript)
        self.assertIn("Contains non-zero samples: yes", transcript)

    def test_explicit_device_index_is_used(self) -> None:
        self.backend.rec.return_value = numpy.ones((4, 1), dtype=numpy.float32)

        result = run_capture_diagnostic(
            device_index=0,
            duration_seconds=1,
            audio_backend=self.backend,
            input_fn=lambda _: "",
            output=self.output,
        )

        self.assertEqual(result, 0)
        self.backend.check_input_settings.assert_called_once_with(
            device=0,
            channels=1,
            samplerate=44_100.0,
            dtype="float32",
        )
        self.backend.rec.assert_called_once_with(
            44_100,
            samplerate=44_100.0,
            channels=1,
            dtype="float32",
            device=0,
        )

    def test_zero_signal_is_reported(self) -> None:
        result = run_capture_diagnostic(
            audio_backend=self.backend,
            input_fn=lambda _: "",
            output=self.output,
        )

        self.assertEqual(result, 0)
        self.assertIn("Contains non-zero samples: no", self.output.getvalue())
        self.assertIn("RMS amplitude: 0.00000000", self.output.getvalue())

    def test_capture_error_preserves_sounddevice_exception_details(self) -> None:
        self.backend.rec.side_effect = RuntimeError(
            "PortAudioError: Invalid device (no default output device)"
        )

        result = run_capture_diagnostic(
            audio_backend=self.backend,
            input_fn=lambda _: "",
            output=self.output,
        )

        self.assertEqual(result, 1)
        self.assertIn("RuntimeError:", self.output.getvalue())
        self.assertIn("Invalid device (no default output device)", self.output.getvalue())
        self.assertIn("repr=", self.output.getvalue())

    def test_permission_error_is_reported_explicitly(self) -> None:
        self.backend.rec.side_effect = PermissionError("access denied")

        result = run_capture_diagnostic(
            audio_backend=self.backend,
            input_fn=lambda _: "",
            output=self.output,
        )

        self.assertEqual(result, 1)
        self.assertIn("Microphone permission error", self.output.getvalue())
        self.assertIn("PermissionError: access denied", self.output.getvalue())

    def test_unsupported_input_configuration_stops_before_recording(self) -> None:
        self.backend.check_input_settings.side_effect = RuntimeError(
            "Invalid sample rate"
        )

        result = run_capture_diagnostic(
            audio_backend=self.backend,
            input_fn=lambda _: "",
            output=self.output,
        )

        self.assertEqual(result, 1)
        self.backend.rec.assert_not_called()
        self.assertIn("Input configuration is not supported", self.output.getvalue())
        self.assertIn("Invalid sample rate", self.output.getvalue())

    def test_cancel_does_not_record(self) -> None:
        result = run_capture_diagnostic(
            audio_backend=self.backend,
            input_fn=lambda _: (_ for _ in ()).throw(KeyboardInterrupt()),
            output=self.output,
        )

        self.assertEqual(result, 0)
        self.backend.rec.assert_not_called()
        self.assertIn("Capture cancelled", self.output.getvalue())


if __name__ == "__main__":
    unittest.main()
