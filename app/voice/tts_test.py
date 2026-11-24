"""Explicit local Piper synthesis and speaker playback diagnostic."""

import argparse
import sys
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import TextIO

from app.config import PiperConfig, load_piper_config
from app.voice.base import VoiceError
from app.voice.tts import PiperTTS

_DEFAULT_TEST_TEXT = "Hello, I am Veronica. This is a local voice test."
_LANGUAGE_TEST_TEXT = {
    "hi": "नमस्ते, मैं वेरोनिका हूँ। मैं आपकी स्थानीय AI सहायक हूँ।",
    "en": "Hello, I am Veronica. I am your private local AI assistant.",
}


def run_tts_test(
    config: PiperConfig,
    *,
    text: str | None = None,
    language: str | None = None,
    output: TextIO | None = None,
) -> int:
    """Speak one test sentence through a configured, preinstalled local voice."""
    destination = sys.stdout if output is None else output
    if language == "hi":
        model_name = "hi_IN-pratham-medium"
        model_path = config.hindi_model_path
        selected_language = "Hindi (hi)"
    elif language == "en":
        model_name = "en_US-ryan-medium"
        model_path = config.english_model_path
        selected_language = "English (en)"
    else:
        model_name = config.model or "(not named)"
        model_path = config.model_path
        selected_language = "configured default"
    if model_path is None:
        print(
            f"No local Piper model path is configured for {selected_language}.",
            file=destination,
        )
        return 1
    selected_text = text or (
        _LANGUAGE_TEST_TEXT[language]
        if language in _LANGUAGE_TEST_TEXT
        else _DEFAULT_TEST_TEXT
    )
    print(f"Selected language: {selected_language}", file=destination)
    print(f"Piper model: {model_name}", file=destination)
    print(f"Piper model path: {model_path}", file=destination)
    if model_path.suffix.casefold() == ".onnx":
        companion_path = Path(f"{model_path}.json")
        print(f"Piper voice config path: {companion_path}", file=destination)
        files_available = model_path.is_file() and companion_path.is_file()
    else:
        print(
            "Piper voice config path: matching .onnx filename with '.json' appended",
            file=destination,
        )
        files_available = False
    if not files_available:
        print(
            "Piper voice unavailable. Install the voice files manually: the "
            "configured .onnx model and its matching .onnx.json file. "
            "No download was attempted.",
            file=destination,
        )
        return 1

    print(f"Speaking: {selected_text}", file=destination)
    try:
        stats = PiperTTS(config=config).speak_with_stats(
            selected_text,
            language=language,
        )
    except VoiceError as error:
        print(f"Local Piper test failed: {error}", file=destination)
        return 1
    if stats is None:
        print("No audio was generated for empty text.", file=destination)
        return 1
    print(f"Synthesized sample rate: {stats.sample_rate} Hz", file=destination)
    print(f"Generated audio samples: {stats.sample_count}", file=destination)
    print(
        f"Generated audio duration: {stats.duration_seconds:.2f} seconds",
        file=destination,
    )
    print("Local Piper playback completed.", file=destination)
    return 0


def _parse_args(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Synthesize and play one sentence using an already-installed local "
            "Piper voice."
        )
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        help="local Piper .onnx voice path; companion <model>.onnx.json is required",
    )
    parser.add_argument(
        "--text",
        help="text to synthesize (defaults to the selected language's test sentence)",
    )
    parser.add_argument(
        "--language",
        choices=("hi", "en"),
        help="select configured Hindi or English voice; default uses PIPER_MODEL_PATH",
    )
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    """CLI entry point for the independent local Piper test."""
    reconfigure_stdout = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure_stdout):
        reconfigure_stdout(encoding="utf-8")
    args = _parse_args(arguments)
    try:
        config = load_piper_config()
    except ValueError as error:
        print(f"Piper configuration error: {error}", file=sys.stderr)
        return 2
    if args.model_path is not None:
        model_path = args.model_path.expanduser()
        if not model_path.is_absolute():
            model_path = Path.cwd() / model_path
        if args.language == "hi":
            config = replace(config, hindi_model_path=model_path)
        elif args.language == "en":
            config = replace(config, english_model_path=model_path)
        else:
            config = replace(config, model_path=model_path)
    return run_tts_test(config, text=args.text, language=args.language)


if __name__ == "__main__":
    raise SystemExit(main())
