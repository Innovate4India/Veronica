# Veronica Phase 2B: Tokenizer Testing and Multilingual Validation

## Scope and method

This is a read-only evaluation of the existing Phase 2A tokenizer
(`app/tokenizer.py`) using deterministic, synthetic strings. No source,
existing tests, or provider code was changed. No datasets, conversations,
pretrained tokenizers, or external models were used. No packages were
installed or updated.

The evaluation ran with the existing `.venv` on Python 3.14.5. Inputs were
encoded using `encode`, decoded using `decode`, and checked against
`list(text.encode("utf-8"))`. Determinism was checked by repeating each
encoding. Character counts below mean Python Unicode code points (`len(text)`),
not grapheme clusters or bytes.

English, Devanagari Hindi, and Roman Hindi (Hinglish) each have three primary
synthetic samples and receive the same checks. A mixed-language sample is
reported separately.

## Reproducible primary inputs

The exact three-string evaluation groups were:

**English**

1. `Hello, world!`
2. `The quick brown fox jumps over the lazy dog.`
3. `Spaces stay; punctuation stays: !? #$%&*`

**Hindi (Devanagari)**

1. `नमस्ते दुनिया!`
2. `किताबें अच्छी हैं।`
3. `स्वर, व्यंजन और भाषा।`

**Hinglish (Roman Hindi)**

1. `Namaste, aap kaise hain?`
2. `Main Hindi aur English dono bolta hoon.`
3. `Aaj hum tokenizer test karenge!`

**Mixed**

- `Hello, नमस्ते! Aap kaise hain? 🙂`

## Correctness and multilingual results

Every primary and robustness input passed all of these checks:

- Encoded IDs exactly equal the UTF-8 bytes as integer values.
- Token count equals UTF-8 byte count.
- Decoding reproduces the exact original Python string.
- Repeated encoding produces the same IDs.

| Group | Samples | Characters (code points) | UTF-8 bytes | Tokens | Tokens / character | Tokens / UTF-8 byte |
|---|---:|---:|---:|---:|---:|---:|
| English | 3 | 97 | 97 | 97 | 1.0000 | 1.0000 |
| Hindi (Devanagari) | 3 | 53 | 143 | 143 | 2.6981 | 1.0000 |
| Hinglish (Roman Hindi) | 3 | 94 | 94 | 94 | 1.0000 | 1.0000 |
| Mixed English/Hindi/Hinglish | 1 | 32 | 47 | 47 | 1.4688 | 1.0000 |

These are byte counts and expansion-per-code-point measurements for a
byte-level tokenizer, not a learned-tokenizer compression benchmark.

## Unicode, whitespace, and length robustness

These additional exact inputs were evaluated independently:

| Case | Exact synthetic input | Characters | UTF-8 bytes / tokens |
|---|---|---:|---:|
| Devanagari letters | `अ आ इ ई उ ऊ ऋ ए ऐ ओ औ` | 21 | 43 |
| Matras and conjuncts | `क का कि की कु कू कृ के कै को कौ क्ष ज्ञ` | 39 | 93 |
| Nukta forms | `क़ / क़` | 6 | 12 |
| Combining and precomposed Latin | `e\u0301 / é` (`\u0301` is combining acute) | 6 | 8 |
| Emoji and ZWJ sequences | `🙂 👩🏽‍💻 🧑‍🚀` | 10 | 32 |
| Non-Latin symbols | `₹ € © ✓ Ω 漢字` | 12 | 24 |
| Whitespace | `" \t\n\r\n\v\f\u00a0"` | 8 | 9 |
| Punctuation and symbols | ``!?.,;: @#$%^&*()[]{}<>/\\|+=-_`~`` | 31 | 31 |
| Empty input | `""` | 0 | 0 |

Every row round-tripped exactly, including empty and whitespace-only content.
The combining and precomposed forms remain distinct: `e\u0301` and `é` each
decode back to the exact input and produce different byte sequences.
Likewise, `क़` and `क़` round-trip exactly as supplied and are not normalized
into one another.

Long inputs used fixed repetition counts, without random generation:

| Group | Reproducible generation | Characters | UTF-8 bytes | Tokens | Tokens / character | Tokens / UTF-8 byte |
|---|---|---:|---:|---:|---:|---:|
| English | `"English test line. " * 1000` | 19,000 | 19,000 | 19,000 | 1.0000 | 1.0000 |
| Hindi (Devanagari) | `"नमस्ते दुनिया। " * 1000` | 15,000 | 41,000 | 41,000 | 2.7333 | 1.0000 |
| Hinglish (Roman Hindi) | `"Namaste duniya, kaise ho? " * 1000` | 26,000 | 26,000 | 26,000 | 1.0000 | 1.0000 |

All long strings also passed exact round-trip, direct-byte-mapping, and
determinism checks. In all tested inputs, token count equaled UTF-8 byte
count.

## Invalid-input behavior

The following expected exception types were observed:

| Input | Expected exception | Actual exception |
|---|---|---|
| `encode(None)` | `TypeError` | `TypeError` |
| `encode(b"text")` | `TypeError` | `TypeError` |
| `encode(42)` (also covered by the focused unit tests) | `TypeError` | `TypeError` |
| `decode([True])` | `TypeError` | `TypeError` |
| `decode([-1])` | `ValueError` | `ValueError` |
| `decode([256])` | `ValueError` | `ValueError` |
| `decode([0x80])` | `UnicodeDecodeError` | `UnicodeDecodeError` |
| `decode([0xC3, 0x28])` | `UnicodeDecodeError` | `UnicodeDecodeError` |
| `decode(None)` | `TypeError` | `TypeError` |

The focused unit tests additionally check false booleans, other non-integer
IDs, malformed/truncated UTF-8 sequences, and surrogate-containing input.

## Test-suite verification

Commands used the existing virtual environment:

| Check | Result |
|---|---|
| `.venv\Scripts\python.exe -m pytest -q tests\test_tokenizer.py` | 15 passed; 17 subtests passed; 0 failed |
| `.venv\Scripts\python.exe -m pytest -ra` | 382 collected; 381 passed, 1 skipped, 0 failed |
| `git diff --check` | Passed |

The single full-suite skip is `tests/test_file_search.py:187`, where Windows
denied directory-symlink creation with `WinError 1314` because the required
privilege is unavailable. Counts match the Phase 2A implementation and audit
reports.

## Evaluation-run discrepancy

An initial ad hoc metrics attempt supplied literal non-ASCII source through a
PowerShell-to-Python pipe. The observed Hindi byte counts were inconsistent
with UTF-8, so those exploratory metrics were discarded. The final evaluation
used ASCII-only Python `\u`/`\U` escapes for all non-ASCII test inputs and
ASCII-safe output, then verified IDs against each string's UTF-8 encoding.
The tables in this report contain only the corrected run's results.

## Worktree preservation and scope

At the start of Phase 2B, the branch was `main` tracking `origin/main`, with
these four existing status-visible untracked Phase 2A files:

- `app/tokenizer.py`
- `tests/test_tokenizer.py`
- `docs/PHASE_2A_NATIVE_TOKENIZER_IMPLEMENTATION_REPORT.md`
- `docs/PHASE_2A_INDEPENDENT_CODE_AUDIT.md`

No tracked modifications were present. After evaluation, those files remain
unchanged; this report is the only new file. No source, tests, configuration,
or provider behavior was modified. Nothing was committed or pushed.

## Conclusion

The tested implementation behaves as a deterministic UTF-8 byte tokenizer
for all three language groups, with equal byte-count behavior and exact
round trips for the synthetic inputs. Devanagari uses more tokens per Unicode
code point because its UTF-8 representation uses multiple bytes per
code point. This evaluation makes no claim of learned subword tokenization,
compression quality, or language-model capability.
