"""Safe, read-only diagnostics for configured local Whisper and audio inputs."""

import importlib.util
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, TextIO, TypedDict, cast

from app.config import WhisperConfig, load_whisper_config


class _AudioDevice(TypedDict):
    name: str
    max_input_channels: int


class _AudioDeviceBackend(Protocol):
    def query_devices(self) -> Sequence[_AudioDevice]: ...


def _missing_model_files(model_path: Path) -> tuple[str, ...]:
    required_files = ("model.bin", "config.json")
    return tuple(
        filename
        for filename in required_files
        if not (model_path / filename).is_file()
    )


def run_diagnostic(
    config: WhisperConfig | None = None,
    *,
    audio_backend: _AudioDeviceBackend | None = None,
    output: TextIO | None = None,
) -> int:
    """Report model availability and input devices without recording audio."""
    selected_config = config or load_whisper_config()
    destination = sys.stdout if output is None else output
    print(f"Whisper model: {selected_config.model}", file=destination)
    print(f"Whisper model path: {selected_config.model_path}", file=destination)
    print(
        f"Inference: device={selected_config.device}, "
        f"compute_type={selected_config.compute_type}",
        file=destination,
    )

    model_missing = _missing_model_files(selected_config.model_path)
    if model_missing:
        print(
            "Model unavailable. Missing local files: "
            + ", ".join(model_missing)
            + ". No model download was attempted.",
            file=destination,
        )
        model_available = False
    else:
        print("Model files found locally.", file=destination)
        model_available = True

    if importlib.util.find_spec("faster_whisper") is None:
        print("faster-whisper package is not installed.", file=destination)
        package_available = False
    else:
        print("faster-whisper package is installed.", file=destination)
        package_available = True

    try:
        if audio_backend is None:
            import sounddevice

            audio_backend = cast(_AudioDeviceBackend, sounddevice)
        devices = audio_backend.query_devices()
    except Exception as error:
        print(f"Could not query audio input devices: {error}", file=destination)
        return 1

    try:
        input_devices = [
            (device["name"], device["max_input_channels"])
            for device in devices
            if device["max_input_channels"] > 0
        ]
    except (KeyError, TypeError) as error:
        print(
            f"Audio backend returned invalid device information: {error}",
            file=destination,
        )
        return 1
    if input_devices:
        print(f"Audio input devices detected: {len(input_devices)}", file=destination)
        for index, (name, input_channels) in enumerate(input_devices):
            print(
                f"  {index + 1}. {name} ({input_channels} input channel(s))",
                file=destination,
            )
    else:
        print("No audio input devices detected.", file=destination)

    print("No recording was started.", file=destination)
    return 0 if model_available and package_available else 1


def main() -> int:
    """CLI entry point, run with ``python -m app.voice.diagnostic``."""
    try:
        config = load_whisper_config()
    except ValueError as error:
        print(f"Whisper configuration error: {error}", file=sys.stderr)
        return 2
    return run_diagnostic(config)


if __name__ == "__main__":
    raise SystemExit(main())
