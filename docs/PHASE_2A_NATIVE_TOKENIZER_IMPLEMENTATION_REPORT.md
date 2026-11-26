# Veronica Phase 2A: Native Tokenizer Implementation Report

## Implementation summary

Added a small, independent UTF-8 byte-level tokenizer at `app/tokenizer.py`.
It uses Python's standard library only and is not connected to the live
assistant, an AI provider, or a training pipeline. The implementation is a
deterministic baseline, not a learned BPE tokenizer.

## Module and API design

The module exposes two functions:

- `encode(text: str) -> list[int]`
- `decode(token_ids: Iterable[int]) -> str`

`encode` accepts strings and encodes them as UTF-8. Non-string inputs raise
`TypeError`; strings containing surrogate code points that cannot be encoded
as UTF-8 raise `UnicodeEncodeError`.

`decode` accepts an iterable of integer token IDs. It rejects strings and
non-iterables with `TypeError`, rejects booleans and non-integer elements with
`TypeError`, and rejects values outside the byte range with `ValueError`.
Malformed UTF-8 sequences raise `UnicodeDecodeError` rather than being
silently replaced.

## Token-ID mapping

Every UTF-8 byte maps directly to its unchanged integer value, from `0` through
`255`. There are no added special tokens, vocabulary tables, or alternate
token-ID mappings.

## Unicode and multilingual behavior

English, Hindi in Devanagari, and Hinglish in Roman Hindi follow the same UTF-8
byte path; the tokenizer does not detect, rank, or prioritize languages.
Spaces, tabs, line endings, punctuation, symbols, and emoji are preserved by
the exact encode-decode round trip for valid UTF-8 text.

Because each byte is represented separately, this baseline may produce longer
sequences than a learned subword tokenizer.

## Tests and verification

Validation used the repository's existing `.venv` (Python 3.14.5 and pytest
9.1.1); no packages were installed.

| Check | Result |
|---|---|
| Focused tokenizer tests (`tests/test_tokenizer.py`) | 15 passed; 17 subtests passed; 0 failed |
| Complete suite (`.venv\Scripts\python.exe -m pytest -ra`) | 382 collected; 381 passed, 1 skipped, 0 failed |
| Import and multilingual UTF-8 round-trip check | Passed |
| `git diff --check` | Passed |

The complete suite's one skip is
`tests/test_file_search.py:187`: Windows denied directory-symlink creation
with `WinError 1314` because the required privilege is unavailable.

## Known limitations

This is a lossless byte encoding for valid UTF-8 strings, not a learned
subword tokenizer. It has no vocabulary training, merge rules, language model,
or model inference capability, and byte-level sequences can be longer than
subword-token sequences.

## Scope and worktree preservation

No real corpus was acquired or processed, no vocabulary was fitted, no model
was trained or fine-tuned, no package was installed, and no provider was
replaced or reconfigured. Ollama and the existing assistant behavior were not
modified. No later phase was started, and nothing was committed, pushed, or
published.

The pre-implementation Git status showed no tracked modifications or
untracked files. After implementation, the only status-visible additions are
`app/tokenizer.py`, `tests/test_tokenizer.py`, and this report; no existing
files were modified.

## Work remaining before a learned tokenizer

A learned tokenizer would require a separately authorized design and
evaluation phase: define data governance and representative training inputs,
specify normalization and segmentation policies, fit and version a
subword vocabulary, measure multilingual and sequence-length behavior, and
validate compatibility with any model that would consume its IDs. None of
that work is part of this byte-level prototype.
