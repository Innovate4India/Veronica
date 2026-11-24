# Veronica Phase 1J-Correction Report

**Date:** 2026-11-24
**Scope:** AUD-01, AUD-02, and AUD-03 only

## Initial worktree state

Before implementation, `git status --short` showed 18 modified tracked files and five displayed untracked entries; `git ls-files --others --exclude-standard` showed 21 existing untracked paths. The untracked work included provider architecture files, Phase 1A–1J documentation, and `tests/test_provider_contracts.py`.

The existing tracked modifications included:

- `app/ai/__init__.py`, `app/ai/base.py`, `app/ai/ollama_client.py`, `app/ai/roles.py`, `app/ai/service.py`, `app/ai/tool_calling.py`, `app/ai/vision.py`
- `app/config.py`, `app/tools/screen_understanding.py`, `app/tools/screenshot.py`, `dev_ai.py`
- `tests/test_ai.py`, `tests/test_dev_ai.py`, `tests/test_roles.py`, `tests/test_screen_understanding.py`, `tests/test_screenshot.py`, `tests/test_teacher_quality.py`, `tests/test_web_search_integration.py`

The pre-change `git diff --check` passed. The affected implementation and test files already contained earlier Phase 1J modifications; these were inspected and preserved.

## AUD-01 — Recursive JSON validation

Changed `app/ai/base.py` to validate nested JSON iteratively, track active container identities to reject cycles, and reject container nesting beyond 100 levels. The non-malformed `ToolCall` contract remains a string-keyed JSON object. No broad exception handler was added; validation failures continue through the existing `ValueError` and `ToolCallingServiceError` boundary.

Added coverage in `tests/test_provider_contracts.py` for cyclic lists and dictionaries, over-depth lists and dictionaries, valid nested JSON, construction-time rejection, and rejection during response normalization before registry execution. Existing tool-calling tests continue to cover malformed-call handling and registry behavior.

Focused result: **48 passed**, with **17 subtests passed**, using the repository `.venv`.

## AUD-02 — Screenshot instructions

Updated `app/tools/screenshot.py` to keep `ScreenshotTool` metadata-only and direct image interpretation to the separate `screen_understanding` tool only when available. When it is unavailable, the instruction explicitly prohibits claiming or inferring screen contents. The returned metadata fields are unchanged; the message now accurately says the tool returns metadata only.

Updated `tests/test_screenshot.py` and `tests/test_dev_ai.py` to verify the revised instruction and availability behavior for vision-capable and non-vision providers. Provider capability filtering was not changed.

Focused result: **44 passed**, with **39 subtests passed**.

## AUD-03 — Typed provider startup errors

Kept the specific startup exception handlers in their existing order and retained their exit codes. Replaced exception-detail output for configuration, capability, model-unavailable, and response errors with stable user-facing messages. Timeout and connection errors continue to use the provider-unavailable message; the final generic `ProviderError` fallback remains unchanged.

Added startup tests in `tests/test_dev_ai.py` for all five requested exception classes. They assert exact messages, exit codes, no private exception detail, and no traceback. Existing connection-error and normal startup tests were retained.

Focused result: **16 passed**, with **17 subtests passed**.

## Complete verification

| Check | Result |
|---|---|
| Complete pytest suite | **366 collected; 365 passed; 0 failed; 1 skipped** |
| Skip | `tests/test_file_search.py:187` — Windows could not create a directory symlink (`WinError 1314`, required privilege unavailable) |
| Application import check | Passed (`app.ai`, `app.ai.tool_calling`, `app.tools.screenshot`, `dev_ai`) |
| `git diff --check` | Passed |

No dependencies were installed. No provider startup against a live service, inference, training, benchmark, or external request was performed.

The global Python interpreter initially could not run pytest because pytest was unavailable, and its unittest attempts could not import Pillow. Validation was rerun successfully with the repository's existing `.venv`; these initial runner/environment errors were not test failures in the project environment.

## Final Git status and preservation

The final status retained the same 18 modified tracked paths listed above. The original 21 untracked paths remain; creating this report adds one untracked file, for **22 untracked paths total**. No unrelated existing work was overwritten, removed, staged, or reverted. No commit or push was made.

## Remaining limitations

The single skipped test requires a Windows directory-symlink privilege not available in this environment. Provider-specific startup behavior was verified with unit tests and import checks; no live provider was contacted. The JSON nesting ceiling is 100 container levels.
