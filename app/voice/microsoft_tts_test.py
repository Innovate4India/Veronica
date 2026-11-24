"""One-shot Microsoft Neural TTS voice audition; audio remains in memory."""

import argparse
import sys
from collections.abc import Sequence
from dataclasses import replace
from typing import TextIO

from app.config import (
    SpokenResponseConfig,
    FEMALE_ENGLISH_NEURAL_VOICES,
    FEMALE_HINDI_NEURAL_VOICES,
    load_spoken_response_config,
)
from app.voice.base import VoiceError
from app.voice.microsoft_tts import MicrosoftNeuralTTS

_AUDITION_TEXT = {
    "hi": (
        "Namaste! Main Veronica AI hoon. Aapko kis cheez mein madad chahiye? "
        "Aap apni problem bataiye, main aapki help karne ki poori koshish karungi."
    ),
    "en": (
        "Hello! I am Veronica. I can help you with Python, web development, "
        "DSA, GitHub, APIs, and artificial intelligence."
    ),
}


def run_neural_tts_test(
    config: SpokenResponseConfig,
    *,
    language: str,
    voice: str | None = None,
    output: TextIO | None = None,
) -> int:
    """Speak one requested audition sentence using a female Neural voice."""
    destination = sys.stdout if output is None else output
    allowed_voices = (
        FEMALE_HINDI_NEURAL_VOICES
        if language == "hi"
        else FEMALE_ENGLISH_NEURAL_VOICES | {"hi-IN-SwaraNeural"}
    )
    if language not in _AUDITION_TEXT:
        print("Language must be 'hi' or 'en'.", file=destination)
        return 2
    selected_voice = voice or (
        config.hindi_voice if language == "hi" else config.english_voice
    )
    if selected_voice not in allowed_voices:
        print(
            "The selected voice is not on the female-only allowlist for this "
            "language.",
            file=destination,
        )
        return 2
    test_config = (
        replace(config, hindi_voice=selected_voice)
        if language == "hi"
        else replace(config, english_voice=selected_voice)
    )
    text = _AUDITION_TEXT[language]
    print(f"Selected language: {language}", file=destination)
    print(f"Selected female voice: {selected_voice}", file=destination)
    print(
        f"Speech rate: {test_config.rate}; pitch: {test_config.pitch}; "
        f"volume: {test_config.volume}",
        file=destination,
    )
    print(f"Sending audition text to Microsoft Neural TTS: {text}", file=destination)
    try:
        stats = MicrosoftNeuralTTS(test_config).speak_with_stats(
            text,
            language=language,
        )
    except VoiceError as error:
        print(f"Microsoft Neural TTS audition failed: {error}", file=destination)
        return 1
    if stats is None:
        print("No audio was generated.", file=destination)
        return 1
    print(f"Synthesized sample rate: {stats.sample_rate} Hz", file=destination)
    print(f"Generated audio samples: {stats.sample_count}", file=destination)
    print(
        f"Generated audio duration: {stats.duration_seconds:.2f} seconds",
        file=destination,
    )
    print("Microsoft Neural TTS playback completed.", file=destination)
    return 0


def _parse_args(arguments: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Synthesize and play a one-shot Microsoft Neural TTS voice audition. "
            "The supplied text is sent online; no audio file is saved."
        )
    )
    parser.add_argument("--language", required=True, choices=("hi", "en"))
    parser.add_argument(
        "--voice",
        help=(
            "female-only voice override; defaults to the configured voice "
            "(hi-IN-SwaraNeural for both languages)"
        ),
    )
    return parser.parse_args(arguments)


def main(arguments: Sequence[str] | None = None) -> int:
    reconfigure_stdout = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure_stdout):
        reconfigure_stdout(encoding="utf-8")
    args = _parse_args(arguments)
    try:
        config = load_spoken_response_config()
    except ValueError as error:
        print(f"Neural TTS configuration error: {error}", file=sys.stderr)
        return 2
    return run_neural_tts_test(
        config,
        language=args.language,
        voice=args.voice,
    )


if __name__ == "__main__":
    raise SystemExit(main())
