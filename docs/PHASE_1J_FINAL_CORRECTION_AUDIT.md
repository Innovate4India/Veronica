# Veronica Phase 1J Final Correction Audit

**Review date:** 2026-11-24
**Review type:** Independent, read-only audit
**Scope:** Phase 1J corrections AUD-01, AUD-02, and AUD-03

## Verdict

# APPROVED WITH CONDITIONS

The three authorized corrections are substantially implemented and pass the independent checks recorded below. No cycle/depth bypass was found; screenshot instructions and vision-tool filtering are consistent; and the requested typed provider startup branches are ordered, tested, and sanitized. One low-severity residual risk remains: a separate enabled-tools startup handler still interpolates a `ProviderCapabilityError` message. The built-in failure path uses a fixed, non-sensitive message, but a future provider could raise that error with private details.

This verdict covers only the Phase 1J corrections. It does not authorize or approve Phase 2, native-model implementation, data acquisition, or training.

## Audit method and worktree state

Inspected the correction and previous audit reports; the provider-neutral JSON validation and tool-call flow; screenshot and screen-understanding registration; startup exception types and handlers; relevant tests; the provider factory and Veronica scaffold; Phase 1D language/privacy decisions; and current Git status/diff.

Before the audit, `git status --short` showed 18 modified tracked files and the existing untracked provider, test, and documentation work. `git diff --stat` reported 18 tracked files changed, 1,407 insertions, and 417 deletions. The initial `git diff --check` passed. No existing file was edited, reverted, staged, or overwritten during this audit.

## AUD-01 — Recursive JSON validation

**Assessment: Implemented; no bypass or execution regression found.**

- `app/ai/base.py:13,23-59` sets `_MAX_JSON_NESTING_DEPTH` to 100 and validates with an explicit work stack. Container IDs remain active until their descendants are processed, so back-edges in lists and dictionaries are rejected without Python recursion. Repeated non-cyclic references remain valid.
- `ToolCall.__post_init__` at `app/ai/base.py:70-80` requires non-malformed arguments to be a JSON object with string keys. `tests/test_provider_contracts.py:192-248` covers valid nested JSON, cyclic lists/dictionaries, and over-depth lists/dictionaries at construction.
- `app/ai/tool_calling.py:202-238` normalizes provider responses before dispatch. It reconstructs each `ToolCall`; `ValueError` from validation becomes `ToolCallingServiceError`. `tests/test_provider_contracts.py:250-296` confirms mutated invalid arguments and cyclic list/dictionary arguments fail before `ToolRegistry.execute()` is called.
- Independent runtime boundary probe using the existing `.venv`: a 100-container object was accepted; 101 containers and a 5,000-container object were rejected. No `RecursionError` escaped.
- Existing registry protections remain in `app/tools/registry.py:66-119`: tool-name allowlisting, confirmation checks, JSON-object validation, and schema validation precede execution. `tests/test_ai_tool_calling.py:128-176,487-506` cover unknown tools, schema failures, and required confirmation; malformed-call behavior also remains covered.

**Coverage note (Informational):** The committed depth test covers over-limit rejection, not exact-limit acceptance. The independent boundary probe confirmed acceptance at exactly 100 levels.

## AUD-02 — Screenshot and screen-understanding instructions

**Assessment: Implemented; no misleading capability claim found.**

- `app/tools/screenshot.py:34-47` says the screenshot tool does not send image bytes or interpret the image. It directs interpretation to the separate `screen_understanding` tool only when available and prohibits claims or inference when unavailable.
- `app/tools/screenshot.py:59-80` returns metadata (`status`, dimensions, format, duration, and message) only and closes the captured image in `finally`; it does not persist or return image data. The message now accurately says the tool returns metadata only.
- `dev_ai.py:63-83` always registers the metadata-only screenshot tool but registers `screen_understanding` only when vision is advertised and a vision adapter exists.
- `tests/test_dev_ai.py:407-510` exercises vision-disabled, vision-enabled-without-adapter, and vision-enabled-with-adapter cases. It checks which definitions reach the provider and verifies the unavailable-vision instruction. `tests/test_screen_understanding.py:127-140` confirms direct execution without a vision provider fails closed without capture. Screenshot metadata and wording are covered in `tests/test_screenshot.py:47-67,150-164`.

No provider capability filtering change or behavior regression was found.

## AUD-03 — Provider startup errors

**Assessment: Requested branches are correctly handled and tested; one separate low-risk detail-echo path remains.**

- Error inheritance in `app/ai/base.py:144-168` makes timeout a connection error and model-unavailable a response error.
- The provider validation/startup handlers in `dev_ai.py:225-248` retain specific-before-base ordering: configuration, capability, model unavailable, timeout, connection, response, then generic `ProviderError`. No broad `Exception` handler was added.
- `tests/test_dev_ai.py:210-267` covers the base `ProviderError` fallback and all five requested typed errors. It asserts stable exact messages, expected exit codes, no private exception detail, and no traceback. `tests/test_dev_ai.py:188-208,540-600` retain connection-error and interactive normal-startup coverage.
- The independently rerun suite passed, supporting the current branches and existing behavior.

### AUD-03-R1 — Separate tool-setup capability diagnostic

**Severity: Low; potential risk, not a demonstrated disclosure or regression.**

`dev_ai.py:278` has a second `ProviderCapabilityError` handler during enabled-tool initialization that includes `{error}` in its diagnostic. The built-in `ToolCallingService` capability error is a fixed generic message, and the current registered provider is Ollama; no sensitive disclosure was reproduced. However, an extension provider could raise `ProviderCapabilityError` from metadata or vision-adapter initialization with private details. The current startup tests exercise the earlier `validate_startup()` handler, not this separate branch.

**Recommendation:** Before enabling third-party provider extensions, consider replacing this interpolation with a stable diagnostic or add a test proving the allowed details are safe. This does not invalidate the sanitized typed branches audited above.

## Cross-project regression review

- **Ollama remains the default:** `app/config.py:166-174` defaults `VERONICA_AI_PROVIDER` to `"ollama"`; `app/ai/provider.py:35` registers Ollama, and `tests/test_provider_contracts.py:110-128` checks the default factory result.
- **Veronica remains an unavailable scaffold:** `app/ai/veronica_provider.py:14-50` advertises no implemented capabilities and raises `ProviderModelUnavailableError`; it is not registered as a production provider.
- **Provider boundary:** Generic `app/ai/tool_calling.py` uses neutral `AssistantResponse`, `ToolCall`, and registry values. It retains a lazy compatibility export for `OllamaToolCallingService` at lines 269-272, but no Ollama wire serialization. Wire conversion remains in the Ollama adapter/compatibility implementation.
- **No silent model switch:** No new provider or model answer engine was introduced. Ollama remains the current default; native Veronica final-answer generation is still unimplemented.
- **Language priorities:** Phase 1D DEC-01 confirms English, Hindi (Devanagari), and Hinglish (Roman Hindi) remain equal-priority goals. Sampling ratios remain pending; no language policy changed in these corrections.
- **Private-memory training:** Phase 1D DEC-06 states personal conversations and SQLite memories are not to be used automatically for training. Inspection found no training/data-pipeline change in the audited files, and no such behavior was introduced by these corrections.

## Test evidence

I independently reran the complete suite using the existing `.venv`:

- **366 collected**
- **365 passed**
- **0 failed**
- **1 skipped**

The skip was `tests/test_file_search.py:187`: Windows directory-symlink creation failed with `WinError 1314` because the required privilege is unavailable. The correction report’s totals reconcile with this run. The independent 100/101/5,000-level depth probe also passed as described above. No dependencies were installed.

## Worktree preservation

After the audit, `git status --short` retained the same 18 modified tracked files and pre-existing untracked work, with this authorized report as the only new file. `git diff --stat` was unchanged because the report is untracked. `git diff --check` passed before and after the audit. No source, test, configuration, or existing documentation file was changed; nothing was staged, committed, pushed, reverted, or cleaned.

## Approval boundary

This approval applies only to Phase 1J corrections AUD-01, AUD-02, and AUD-03, subject to the low-severity residual noted in AUD-03-R1. It is not approval for Phase 2 implementation, tokenizer or model work, data operations, provider replacement, or training.
