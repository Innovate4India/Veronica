"""Explicit one-shot microphone transcription test; never stores recorded audio."""

import argparse
import importlib
import math
import sys
from collections.abc import Callable, Sequence
from typing import NotRequired, Protocol, TextIO, TypedDict, cast

from app.config import WhisperConfig, load_whisper_config
from app.voice.base import (
    MicrophonePermissionError,
    MicrophoneUnavailableError,
    SpeechRecognitionError,
    VoiceError,
)
from app.voice.stt import FasterWhisperSTT


class _AudioDevice(TypedDict):
    name: str
    max_input_channels: int
    default_samplerate: float
    hostapi: int
    host_api: NotRequired[str]


class _AudioRecorder(Protocol):
    def rec(
        self,
        frames: int,
        *,
        samplerate: float,
        channels: int,
        dtype: str,
        device: int | None = None,
        blocking: bool = False,
    ) -> object: ...


class _AudioBackend(_AudioRecorder, Protocol):
    def query_devices(self) -> Sequence[_AudioDevice]: ...

    def query_hostapis(self, index: int) -> dict[str, str]: ...

    def check_input_settings(
        self,
        *,
        device: int,
        channels: int,
        samplerate: float,
        dtype: str,
    ) -> None: ...

    def wait(self, timeout: float | None = None) -> None: ...


class _DeviceRateAudioBackend:
    """Capture at the device's native rate, then adapt audio for Whisper."""

    def __init__(
        self,
        audio_backend: _AudioRecorder,
        *,
        device_index: int,
        device_sample_rate: float,
    ) -> None:
        self._audio_backend = audio_backend
        self._device_index = device_index
        self._device_sample_rate = device_sample_rate

    def rec(
        self,
        frames: int,
        *,
        samplerate: float,
        channels: int,
        dtype: str,
        device: int | None = None,
    ) -> object:
        import numpy

        del device
        device_frames = round(frames * self._device_sample_rate / samplerate)
        audio = self._audio_backend.rec(
            device_frames,
            samplerate=self._device_sample_rate,
            channels=channels,
            dtype=dtype,
            device=self._device_index,
            blocking=True,
        )
        captured = numpy.asarray(audio)
        if captured.ndim == 1:
            mono_audio = captured
        elif captured.ndim == 2 and captured.shape[1] > 0:
            if captured.shape[1] == 1:
                mono_audio = captured[:, 0]
            else:
                mono_audio = captured.mean(axis=1)
        else:
            raise ValueError(
                "The microphone must return audio with shape (samples,) or "
                "(samples, channels)."
            )
        if not numpy.issubdtype(mono_audio.dtype, numpy.number) or numpy.issubdtype(
            mono_audio.dtype,
            numpy.complexfloating,
        ):
            raise ValueError("The microphone audio must contain real numeric samples.")
        mono_audio = mono_audio.astype(numpy.float32, copy=False)

        rate_ratio = self._device_sample_rate / samplerate
        rounded_ratio = round(rate_ratio)
        if (
            rate_ratio > 1
            and math.isclose(rate_ratio, rounded_ratio)
            and mono_audio.shape[0] >= frames * rounded_ratio
        ):
            resampled = mono_audio[: frames * rounded_ratio].reshape(
                frames,
                rounded_ratio,
            ).mean(axis=1)
        else:
            old_positions = numpy.arange(mono_audio.shape[0], dtype=numpy.float64)
            new_positions = numpy.linspace(
                0,
                max(0, mono_audio.shape[0] - 1),
                frames,
            )
            resampled = numpy.interp(
                new_positions,
                old_positions,
                mono_audio,
            )
        return resampled.astype(numpy.float32, copy=False)

    def wait(self, timeout: float | None = None) -> None:
        del timeout


def _realtek_input_devices(
    devices: Sequence[_AudioDevice],
) -> list[tuple[int, _AudioDevice]]:
    return [
        (index, device)
        for index, device in enumerate(devices)
        if device["max_input_channels"] > 0
        and "realtek" in device["name"].casefold()
    ]


def _select_input_device(
    devices: Sequence[_AudioDevice],
    requested_index: int | None,
    output: TextIO,
) -> int:
    if requested_index is not None:
        if requested_index < 0 or requested_index >= len(devices):
            raise MicrophoneUnavailableError(
                f"Audio input device index {requested_index} does not exist."
            )
        requested = devices[requested_index]
        if requested["max_input_channels"] < 1:
            raise MicrophoneUnavailableError(
                f"Audio device {requested_index} is not an input device."
            )
        return requested_index

    matching_devices = _realtek_input_devices(devices)
    if not matching_devices:
        raise MicrophoneUnavailableError(
            "No Realtek microphone input was found. Specify a valid input "
            "device index with --device-index."
        )

    print("Realtek input devices:", file=output)
    for index, device in matching_devices:
        print(
            f"  [{index}] {device['name']} "
            f"({device['max_input_channels']} input channel(s))",
            file=output,
        )
    microphone_matches = [
        (index, device)
        for index, device in matching_devices
        if "microphone" in device["name"].casefold()
    ]
    preferred_wasapi = [
        (index, device)
        for index, device in microphone_matches
        if "wasapi" in device.get("host_api", "").casefold()
    ]
    selected_index, selected_device = (
        preferred_wasapi or microphone_matches or matching_devices
    )[0]
    print(
        f"Selected device [{selected_index}]: {selected_device['name']}",
        file=output,
    )
    return selected_index


def run_microphone_test(
    *,
    duration_seconds: float = 5.0,
    device_index: int | None = None,
    audio_backend: _AudioBackend | None = None,
    input_fn: Callable[[str], str] = input,
    output: TextIO | None = None,
    debug: bool = False,
) -> int:
    """Prompt once, record a bounded utterance, and print local transcription."""
    destination = sys.stdout if output is None else output
    if not 5 <= duration_seconds <= 10:
        print("Recording duration must be between 5 and 10 seconds.", file=destination)
        return 2
    try:
        whisper_config = load_whisper_config()
    except ValueError as error:
        print(f"Whisper configuration error: {error}", file=destination)
        return 2
    try:
        if audio_backend is None:
            audio_backend = cast(
                _AudioBackend,
                importlib.import_module("sounddevice"),
            )
        devices = audio_backend.query_devices()
        host_apis = [
            audio_backend.query_hostapis(index)["name"]
            for index in range(
                max((device["hostapi"] for device in devices), default=-1) + 1
            )
        ]
        devices_with_host_api: list[_AudioDevice] = [
            cast(
                _AudioDevice,
                {
                    **device,
                    "host_api": host_apis[device["hostapi"]],
                },
            )
            for device in devices
        ]
        selected_index = _select_input_device(
            devices_with_host_api,
            device_index,
            destination,
        )
    except (ImportError, MicrophoneUnavailableError, OSError, RuntimeError) as error:
        print(f"Microphone setup failed: {error}", file=destination)
        return 1
    selected_device = devices[selected_index]
    sample_rate = float(selected_device["default_samplerate"])
    print(
        f"Using device default sample rate: {sample_rate:g} Hz "
        "(Whisper input: 16000 Hz).",
        file=destination,
    )
    try:
        audio_backend.check_input_settings(
            device=selected_index,
            channels=1,
            samplerate=sample_rate,
            dtype="float32",
        )
    except Exception as error:
        print(f"Microphone input configuration failed: {error}", file=destination)
        return 1

    try:
        input_fn(
            f"Press Enter to record once for {duration_seconds:g} seconds "
            "(Ctrl+C to cancel): "
        )
    except (EOFError, KeyboardInterrupt):
        print("Microphone test cancelled; no recording was started.", file=destination)
        return 0

    try:
        stt = FasterWhisperSTT(
            duration_seconds=duration_seconds,
            sample_rate=16_000,
            input_device=selected_index,
            config=whisper_config,
            audio_backend=_DeviceRateAudioBackend(
                audio_backend,
                device_index=selected_index,
                device_sample_rate=sample_rate,
            ),
        )
        transcription = stt.listen()
    except MicrophonePermissionError as error:
        print(f"Microphone permission denied: {error}", file=destination)
        return 1
    except SpeechRecognitionError as error:
        print(f"Microphone transcription failed: {error}", file=destination)
        if debug:
            _print_recognition_diagnostics(
                error,
                whisper_config=whisper_config,
                duration_seconds=duration_seconds,
                source_sample_rate=sample_rate,
                output=destination,
            )
        return 1
    except VoiceError as error:
        print(f"Microphone transcription failed: {error}", file=destination)
        return 1

    print("\nRecognized speech:", file=destination)
    print(transcription, file=destination)
    return 0


def _print_recognition_diagnostics(
    error: SpeechRecognitionError,
    *,
    whisper_config: WhisperConfig,
    duration_seconds: float,
    source_sample_rate: float,
    output: TextIO,
) -> None:
    cause = error.__cause__
    if cause is None:
        cause = error
    print("Recognition diagnostics:", file=output)
    print(f"  Whisper model: {whisper_config.model}", file=output)
    print(f"  Model path: {whisper_config.model_path}", file=output)
    print(f"  Device: {whisper_config.device}", file=output)
    print(f"  Compute type: {whisper_config.compute_type}", file=output)
    print(f"  Audio sample rate: 16000 Hz", file=output)
    print(
        f"  Captured device sample rate: {source_sample_rate:g} Hz",
        file=output,
    )
    print(
        f"  Captured device sample count: "
        f"{round(duration_seconds * source_sample_rate)}",
        file=output,
    )
    print(
        f"  Whisper audio sample count: {round(duration_seconds * 16_000)}",
        file=output,
    )
    print(
        f"  Underlying exception: {type(cause).__name__}: {cause}",
        file=output,
    )


def _parse_args(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Record one explicit 5-10 second utterance using a local Whisper model."
        )
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=5.0,
        help="Recording duration in seconds (5-10; default: 5).",
    )
    parser.add_argument(
        "--device-index",
        type=int,
        help="sounddevice input-device index; default selects a Realtek microphone.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="show local Whisper configuration and the underlying recognition error.",
    )
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    """CLI entry point for the one-shot microphone test."""
    args = _parse_args(arguments)
    return run_microphone_test(
        duration_seconds=args.duration,
        device_index=args.device_index,
        debug=args.debug,
    )


if __name__ == "__main__":
    raise SystemExit(main())
