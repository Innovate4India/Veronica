"""Deterministic UTF-8 byte-level tokenization for Veronica.

Each UTF-8 byte is represented by its unchanged integer value (0 through 255).
This baseline is not a learned BPE tokenizer and may produce longer sequences
than a learned subword tokenizer.
"""

from collections.abc import Iterable


def encode(text: str) -> list[int]:
    """Encode text as UTF-8 byte values without language-specific rules."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    return list(text.encode("utf-8"))


def decode(token_ids: Iterable[int]) -> str:
    """Decode byte-valued token IDs as strict UTF-8 text."""
    if isinstance(token_ids, str) or not isinstance(token_ids, Iterable):
        raise TypeError("token_ids must be an iterable of integers")

    encoded = bytearray()
    for index, token_id in enumerate(token_ids):
        if isinstance(token_id, bool) or not isinstance(token_id, int):
            raise TypeError(f"token ID at index {index} must be an integer")
        if not 0 <= token_id <= 255:
            raise ValueError(f"token ID at index {index} must be between 0 and 255")
        encoded.append(token_id)

    return encoded.decode("utf-8")
