"""Direct, bounded sounddevice capture diagnostic without Whisper."""

import argparse
import importlib
import math
import sys
from collections.abc import Callable, Sequence
from typing import Protocol, TextIO, TypedDict, cast


class _DeviceInfo(TypedDict):
    name: str
    max_input_channels: int
    default_samplerate: float
    hostapi: int


class _HostApiInfo(TypedDict):
    name: str


class _SoundDeviceBackend(Protocol):
    default: object

    def query_devices(self) -> Sequence[_DeviceInfo]: ...

    def query_hostapis(self, index: int) -> _HostApiInfo: ...

    def check_input_settings(
        self,
        *,
        device: int,
        channels: int,
        samplerate: float,
        dtype: str,
    ) -> None: ...

    def rec(
        self,
        frames: int,
        *,
        samplerate: float,
        channels: int,
        dtype: str,
        device: int,
    ) -> object: ...

    def wait(self) -> None: ...


def _format_exception_details(error: Exception) -> str:
    """Preserve concrete backend exception type, message, and available codes."""
    details = [f"{type(error).__name__}: {error}", f"repr={error!r}"]
    errno = getattr(error, "errno", None)
    if errno is not None:
        details.append(f"errno={errno!r}")
    hosterror_info = getattr(error, "hosterror_info", None)
    if hosterror_info is not None:
        details.append(f"hosterror_info={hosterror_info!r}")
    return "; ".join(details)


def _print_devices(
    devices: Sequence[_DeviceInfo],
    audio_backend: _SoundDeviceBackend,
    output: TextIO,
) -> None:
    print("Sounddevice input devices:", file=output)
    for index, device in enumerate(devices):
        if device["max_input_channels"] <= 0:
            continue
        try:
            host_api = audio_backend.query_hostapis(device["hostapi"])["name"]
        except (IndexError, KeyError, TypeError):
            host_api = f"unknown (host API index {device['hostapi']})"
        print(
            f"  [{index}] {device['name']} | "
            f"max_input_channels={device['max_input_channels']} | "
            f"default_samplerate={device['default_samplerate']:g} | "
            f"host_api={host_api}",
            file=output,
        )


def _default_input_index(
    audio_backend: _SoundDeviceBackend,
    devices: Sequence[_DeviceInfo],
    output: TextIO,
) -> int | None:
    default_devices = getattr(audio_backend.default, "device", None)
    if not isinstance(default_devices, (tuple, list)) or not default_devices:
        print(f"Current sounddevice default input device: {default_devices!r}", file=output)
        return None
    default_input = default_devices[0]
    if not isinstance(default_input, int) or default_input < 0:
        print(f"Current sounddevice default input device: {default_input!r}", file=output)
        return None
    if default_input >= len(devices):
        print(f"Current sounddevice default input device: invalid index {default_input}", file=output)
        return None
    print(
        f"Current sounddevice default input device: "
        f"[{default_input}] {devices[default_input]['name']}",
        file=output,
    )
    return default_input


def _signal_stats(audio: object) -> tuple[int, float, float, float, float, bool]:
    import numpy

    samples = numpy.asarray(audio, dtype=numpy.float64).reshape(-1)
    if samples.size == 0:
        raise ValueError("The audio backend returned an empty capture.")
    minimum = float(samples.min())
    maximum = float(samples.max())
    mean_absolute = float(numpy.mean(numpy.abs(samples)))
    rms = float(numpy.sqrt(numpy.mean(numpy.square(samples))))
    contains_signal = bool(numpy.any(samples != 0))
    return int(samples.size), minimum, maximum, rms, mean_absolute, contains_signal


def run_capture_diagnostic(
    *,
    device_index: int | None = None,
    duration_seconds: float = 2.0,
    audio_backend: _SoundDeviceBackend | None = None,
    input_fn: Callable[[str], str] = input,
    output: TextIO | None = None,
) -> int:
    """Inspect sounddevice configuration and optionally capture two seconds."""
    destination = sys.stdout if output is None else output
    if not math.isfinite(duration_seconds) or not 1 <= duration_seconds <= 3:
        print("Capture duration must be between 1 and 3 seconds.", file=destination)
        return 2
    try:
        if audio_backend is None:
            audio_backend = cast(
                _SoundDeviceBackend,
                importlib.import_module("sounddevice"),
            )
        devices = audio_backend.query_devices()
    except Exception as error:
        print(
            "Could not enumerate sounddevice devices: "
            + _format_exception_details(error),
            file=destination,
        )
        return 1

    _print_devices(devices, audio_backend, destination)
    default_input = _default_input_index(audio_backend, devices, destination)
    selected_index = default_input if device_index is None else device_index
    if selected_index is None:
        print(
            "No default input device is configured; specify --device-index.",
            file=destination,
        )
        return 1
    if selected_index < 0 or selected_index >= len(devices):
        print(f"Selected device index {selected_index} does not exist.", file=destination)
        return 1

    selected_device = devices[selected_index]
    print(
        f"Selected device [{selected_index}]: {selected_device['name']}",
        file=destination,
    )
    try:
        host_api_name = audio_backend.query_hostapis(selected_device["hostapi"])["name"]
    except Exception as error:
        print(
            "Could not query selected device host API: "
            + _format_exception_details(error),
            file=destination,
        )
        return 1
    print(
        f"Device info: max_input_channels={selected_device['max_input_channels']}, "
        f"default_samplerate={selected_device['default_samplerate']:g}, "
        f"host_api={host_api_name}",
        file=destination,
    )
    if selected_device["max_input_channels"] < 1:
        print("Selected device has no input channels.", file=destination)
        return 1

    sample_rate = float(selected_device["default_samplerate"])
    if not math.isfinite(sample_rate) or sample_rate <= 0:
        print(f"Invalid device default samplerate: {sample_rate!r}", file=destination)
        return 1
    print(
        f"Checking mono float32 input at device default samplerate {sample_rate:g} Hz.",
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
        print(
            "Input configuration is not supported: "
            + _format_exception_details(error),
            file=destination,
        )
        return 1
    print("Input configuration check passed.", file=destination)

    try:
        input_fn(
            f"Press Enter to capture once for {duration_seconds:g} seconds "
            "(Ctrl+C to cancel): "
        )
    except (EOFError, KeyboardInterrupt):
        print("Capture cancelled; no audio was recorded.", file=destination)
        return 0

    frames = round(duration_seconds * sample_rate)
    try:
        audio = audio_backend.rec(
            frames,
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
            device=selected_index,
        )
        audio_backend.wait()
    except PermissionError as error:
        print(
            "Microphone permission error: " + _format_exception_details(error),
            file=destination,
        )
        return 1
    except Exception as error:
        print(
            "sounddevice capture error: " + _format_exception_details(error),
            file=destination,
        )
        return 1

    try:
        count, minimum, maximum, rms, mean_absolute, has_signal = _signal_stats(audio)
    except Exception as error:
        print(
            "Could not analyze captured samples: "
            + _format_exception_details(error),
            file=destination,
        )
        return 1
    print("Capture succeeded; audio was kept in memory only.", file=destination)
    print(f"Samples: {count}", file=destination)
    print(f"Minimum: {minimum:.8f}", file=destination)
    print(f"Maximum: {maximum:.8f}", file=destination)
    print(f"RMS amplitude: {rms:.8f}", file=destination)
    print(f"Average absolute amplitude: {mean_absolute:.8f}", file=destination)
    print(f"Contains non-zero samples: {'yes' if has_signal else 'no'}", file=destination)
    return 0


def _parse_args(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Perform one bounded sounddevice microphone capture without Whisper."
    )
    parser.add_argument(
        "--device-index",
        type=int,
        help="sounddevice input device index (defaults to the current input device).",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=2.0,
        help="Capture duration in seconds (1-3; default: 2).",
    )
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    args = _parse_args(arguments)
    return run_capture_diagnostic(
        device_index=args.device_index,
        duration_seconds=args.duration,
    )


if __name__ == "__main__":
    raise SystemExit(main())
