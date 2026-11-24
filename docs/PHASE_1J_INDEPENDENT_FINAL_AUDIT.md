# Veronica Phase 1J-Final: Independent Implementation Audit

**Review date:** 2026-11-24
**Review type:** Read-only implementation and test audit
**Scope:** Phase 1J findings I-01 through I-05 and the reported final worktree

## Verdict

# APPROVED WITH CONDITIONS

The five Phase 1H findings were addressed in the inspected implementation, and no Phase 1A provider-neutral architecture regression was found. Two low-severity residual issues remain: cyclic Python containers can escape the new JSON validation as an uncaught recursion error, and the screenshot tool still tells the model that screen understanding is not implemented even when the separate vision tool is registered. Startup error handling is correctly ordered, but the typed startup branches are not individually covered by focused tests.

These conditions do not establish a current Ollama execution bypass. Resolve them before relying on arbitrary third-party providers or treating screenshot and screen-understanding instructions as unambiguous.

## Audit scope and method

Inspected the Phase 1H findings, the Phase 1I resolution plan, the Phase 1J implementation report, the current changes and source for each named finding, the related tests, provider selection, the screenshot and screen-understanding tools, and the confirmed language-priority record.

This audit performed static inspection only. It did not rerun tests, start Veronica, contact Ollama, or perform inference. The test results below are reconciled against the Phase 1J report and the test-run output captured during that implementation phase; they are not new test executions.

`docs/PHASE_1A_PROVIDER_ARCHITECTURE.md` and `tests/test_provider_contracts.py` are untracked in this worktree, so Git cannot provide a tracked-file diff for them. Their current contents were inspected against the source and the Phase 1H/1I evidence. This limits independent verification of their complete edit history, but not of the claims currently present in those files.

## Worktree state and preservation

At audit start, `git status --short` showed **18 modified tracked files** and **20 untracked paths**. `git diff --stat` showed 1,303 insertions and 410 deletions across the tracked changes; those totals include earlier Phase 1A work and are not Phase 1J-only statistics. `git diff --check` reported no tracked-diff whitespace errors.

The status matches the final Phase 1J implementation report: the existing modifications and untracked files remain present, including prior provider, test, and documentation work. No unrelated change was reverted or overwritten. The Phase 1J implementation report and this audit are untracked documentation deliverables. Creating this audit adds one untracked file; the source, tests, configuration, and provider selection were not changed during this audit.

## Finding-by-finding assessment

### I-01 — Phase 1A architecture documentation

**Assessment: Addressed.**

The current [Phase 1A provider architecture note](PHASE_1A_PROVIDER_ARCHITECTURE.md) now identifies `create_provider()` as the selector and `_create_ollama_provider()` as the private Ollama factory; describes the Veronica provider as an unavailable scaffold with all capabilities disabled; and describes provider-factory startup validation and provider-neutral tool transport. These claims match [provider.py](../app/ai/provider.py), [veronica_provider.py](../app/ai/veronica_provider.py), [dev_ai.py](../dev_ai.py), and the Ollama adapter.

The note labels the 343-collected run as historical, retains its counts, and points readers to later run-specific Phase 1A verification records. The Phase 1A approval audit and final verification were not changed. The note does not imply that a native model or provider replacement is approved.

**Evidence limitation:** As noted above, the architecture note is untracked, so its diff against `HEAD` cannot be independently inspected with Git.

### I-02 — Base `ProviderError` during CLI startup

**Assessment: Addressed; typed-branch coverage is incomplete.**

In [dev_ai.py](../dev_ai.py), `main()` catches `ProviderConfigurationError`, `ProviderCapabilityError`, `ProviderModelUnavailableError`, `ProviderTimeoutError`, `ProviderConnectionError`, and `ProviderResponseError` before the final `ProviderError` fallback. The fallback prints a generic message, omits exception details, and returns exit code 1. It does not catch arbitrary `Exception`. This preserves the intended typed exit behavior by inspection.

[test_dev_ai.py](../tests/test_dev_ai.py) includes a direct-base-error startup test that checks the exit code, generic diagnostic, absence of the private exception detail, and absence of a traceback. Existing tests also cover provider connection failures and normal-chat connection handling.

**Coverage limitation:** No focused startup test was found for each of the configuration, capability, model-unavailable, timeout, and response-error branches. Their ordering and messages are source-verifiable, but the plan’s branch-by-branch regression criterion is not fully demonstrated by tests.

### I-03 — `ToolCall` JSON-compatible object arguments

**Assessment: Addressed for ordinary finite JSON structures; one residual robustness condition is recorded below.**

In [base.py](../app/ai/base.py), non-malformed calls require a dictionary with string keys and recursively valid JSON values; tuples, sets, unsupported objects, non-string keys, non-finite floats, and top-level scalars/lists are rejected. Malformed calls require the `None` sentinel. In [ollama_client.py](../app/ai/ollama_client.py), malformed Ollama arguments are normalized to that sentinel. In [tool_calling.py](../app/ai/tool_calling.py), response normalization reconstructs calls to revalidate nested arguments and converts `ValueError` to `ToolCallingServiceError` before dispatch.

[test_provider_contracts.py](../tests/test_provider_contracts.py) covers valid nested objects, empty objects, the listed invalid value categories, malformed sentinels, nested mutation before dispatch, and non-execution of malformed calls. [test_ai_tool_calling.py](../tests/test_ai_tool_calling.py) retains legacy Ollama malformed-call and normal-tool execution coverage. The `ToolRegistry` remains the allowlist and schema-validation boundary.

#### AUD-01 — Recursive JSON validation has no cycle/depth guard

**Severity: Low.**

**Verified facts:** `_is_json_value()` in [base.py](../app/ai/base.py) recursively descends lists and dictionaries without tracking visited ancestors or limiting depth. `_normalize_assistant_response()` in [tool_calling.py](../app/ai/tool_calling.py) converts `ValueError` to a provider-neutral tool error but does not handle `RecursionError`.

**Inferred impact:** A custom in-process provider can construct a cyclic list/dictionary, or an excessively deep nested value. Validation can then raise `RecursionError` rather than rejecting the arguments through the normal error boundary. This aborts before tool execution, but can escape the provider/tool service as an unhandled exception. Ordinary JSON decoding cannot itself create cyclic references; no reproduction was run during this read-only audit.

**Recommendation:** Add ancestor-aware cycle detection and/or an explicit nesting limit, and test cyclic list and dictionary values through both construction and response normalization before accepting arbitrary provider implementations.

### I-04 — Runtime validation of vision responses

**Assessment: Addressed.**

In [vision.py](../app/ai/vision.py), `LocalVisionService` checks that the returned value is a `VisionResponse`, that its `text` is a string, and that the trimmed text is non-empty. Invalid responses raise stable `ProviderResponseError` messages. The capture remains protected by `finally`, so malformed, empty, and successful responses all close the image.

[test_screen_understanding.py](../tests/test_screen_understanding.py) tests a non-response object, non-string response text, empty and whitespace-only text, a valid trimmed response, and image closure. Existing tests cover Ollama timeout, connection, missing-model, model-unavailable, and malformed native response behavior.

### I-05 — Screen-understanding capability filtering

**Assessment: Filtering is implemented; one related prompt inconsistency remains.**

In [dev_ai.py](../dev_ai.py), the registry adds `screen_understanding` only when `provider.metadata.capabilities.vision` is true and `create_vision_provider()` returns an adapter. `ScreenshotTool` remains registered independently. [test_dev_ai.py](../tests/test_dev_ai.py) verifies disabled vision, a missing adapter, an available fake adapter, screenshot-tool retention, and Ollama registration. [test_screen_understanding.py](../tests/test_screen_understanding.py) verifies direct calls without a vision provider return unavailable without capturing the display. Existing tests retain the unconfigured Ollama vision-model response.

#### AUD-02 — Screenshot tool instruction contradicts available screen understanding

**Severity: Low.**

**Verified facts:** [screenshot.py](../app/tools/screenshot.py) says both that the screenshot tool does not interpret images and that the model should tell the user “screen understanding is not implemented yet.” Its description also includes requests such as “look at the current screen.” Separately, [screen_understanding.py](../app/tools/screen_understanding.py) describes an implemented explicit screen-understanding tool, and [dev_ai.py](../dev_ai.py) registers it for vision-capable providers. Ollama advertises vision and returns an adapter; tests verify that it remains registered.

**Why it matters:** For a vision-capable provider, the screenshot instruction can incorrectly suggest that the application has no screen-understanding capability and overlaps with the separate tool’s intended user requests. The metadata-only behavior of `ScreenshotTool` is valid; the global “not implemented yet” instruction is the inconsistent part.

**Recommendation:** Clarify that the screenshot tool itself only returns metadata and does not interpret images, and direct the model to use `screen_understanding` only when that tool is available. Preserve the current fail-closed behavior when vision is unavailable.

## Architecture, defaults, and language priorities

- **Ollama default:** `load_provider_selection_config()` in [config.py](../app/config.py) defaults `VERONICA_AI_PROVIDER` to `"ollama"`. [provider.py](../app/ai/provider.py) registers Ollama and selects it by default. `test_provider_contracts.py` explicitly tests the default and factory result.
- **Provider-neutral boundaries:** Generic `dev_ai.py` and `tool_calling.py` use provider interfaces and neutral response values. Ollama wire conversion remains in `ollama_client.py` and the explicit compatibility adapter. No new fallback to Ollama was introduced for providers that lack vision.
- **Capabilities:** Ollama declares text, tools, and vision; it does not declare streaming. The Veronica scaffold declares no implemented capabilities and remains unavailable. Registry filtering consults vision capability and adapter availability.
- **Language priority:** Phase 1D DEC-01 explicitly records English, Hindi (Devanagari), and Hinglish (Roman Hindi) as equal priorities, with no ranking among them; sampling ratios remain pending. Phase 1J changed no language policy or sampling behavior. Equal priority is not evidence of equal sampling proportions or equal measured quality.
- **Memory/training and model approval:** The reviewed Phase 1J changes do not use private conversations or SQLite memories for training and do not load or integrate a Veronica model. No evidence suggests Ollama was removed or that a pretrained model became a new permanent answer engine.

## Test-result reconciliation

The Phase 1J report’s full-suite figures reconcile arithmetically and with the captured implementation-phase test output: **363 collected = 362 passed + 1 skipped**, with **0 failed**. The skip is `tests/test_file_search.py:187`, where Windows directory-symlink creation fails with `WinError 1314`. The focused test counts in the report correspond to separate, overlapping runs and must not be added together.

These results were not rerun during this audit. The audit’s checks were repository status/diff inspection, `git diff --check`, and static inspection of source, tests, and reports.

## Conditions and final assessment

1. Add cycle/depth protection to the recursive tool-argument validator before relying on arbitrary in-process providers.
2. Reconcile the screenshot tool’s “not implemented yet” instruction with the separately registered screen-understanding capability.
3. Add focused startup tests for the typed error branches to fully satisfy the Phase 1I test-coverage criterion.

**No Phase 1A architectural regression was found.** The five original fixes are substantially implemented and their recorded test results are consistent. The conditions above are low-severity robustness, prompt-consistency, and verification gaps; they are not claims of a current tool-execution bypass. This audit grants no authorization for Phase 2, model training, provider replacement, or changes to Ollama configuration.
