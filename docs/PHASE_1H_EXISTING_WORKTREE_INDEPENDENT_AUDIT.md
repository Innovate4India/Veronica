# Veronica Phase 1H: Existing Worktree Independent Audit

**Review type:** Independent, read-only worktree and architecture audit
**Review date:** 2026-11-24
**Scope:** Current tracked modifications and untracked files, compared with the Phase 1A provider architecture approval and its stated boundaries.
**Restrictions observed:** No implementation, test execution, downloads, installations, inference, training, benchmarks, configuration changes, staging, commits, pushes, resets, stashes, or cleanup operations were performed.

## 1. Executive summary

**Verdict: APPROVED WITH CONDITIONS.**

Static inspection found that the current implementation preserves the principal Phase 1A provider-neutral boundaries: startup uses the provider factory, generic AI and tool orchestration do not serialize Ollama wire messages, Ollama conversion is in the Ollama adapter, and the built-in provider capability declarations match their implemented feature paths. The current Veronica provider remains an unavailable scaffold. No Phase 1A architectural regression was identified in the inspected implementation.

This is not a new approval of the modified worktree. The earlier Phase 1A approval applied to the exact state it reviewed; the current worktree is dirty and was not dynamically tested in this audit. Conditions are: reconcile stale Phase 1A architecture documentation, address or explicitly accept the validation and extensibility caveats below, and run the relevant suite against the intended worktree before relying on runtime compatibility.

The main verified issue is documentation drift: the untracked Phase 1A architecture note contains claims that do not match the current code or later approval record. The main potential risks concern unhandled base provider errors at startup, runtime validation of vision responses, and exposing a screen-understanding tool to a future tool-capable provider that does not advertise vision.

## 2. Current Git/worktree state

The required initial inspection recorded:

- `git status --short`: **18 modified tracked files** and **17 untracked files**.
- `git diff --stat`: **1,046 insertions and 405 deletions** across the 18 tracked modifications. Untracked files are not included in this statistic.
- `git diff --check`: completed with no reported whitespace errors in the tracked diff.
- No staged changes were listed.
- The Phase 1H report target was absent before this report was created.

### Tracked modified files

- `app/ai/__init__.py`
- `app/ai/base.py`
- `app/ai/ollama_client.py`
- `app/ai/roles.py`
- `app/ai/service.py`
- `app/ai/tool_calling.py`
- `app/ai/vision.py`
- `app/config.py`
- `app/tools/screen_understanding.py`
- `app/tools/screenshot.py`
- `dev_ai.py`
- `tests/test_ai.py`
- `tests/test_dev_ai.py`
- `tests/test_roles.py`
- `tests/test_screen_understanding.py`
- `tests/test_screenshot.py`
- `tests/test_teacher_quality.py`
- `tests/test_web_search_integration.py`

### Untracked files

Untracked implementation/test files:

- `app/ai/ollama_tool_compat.py`
- `app/ai/provider.py`
- `app/ai/veronica_provider.py`
- `tests/test_provider_contracts.py`

The other 13 untracked files are the Phase 1 audit and Phase 1A-1G documents, including the three historical records named in the task. The audit report itself is the only file created by this Phase 1H task.

## 3. Files inspected

Inspected the full tracked diff for all 18 modified files listed above, the current contents of the three untracked provider/compatibility modules, and `tests/test_provider_contracts.py`. Inspected the existing `ToolRegistry` validation boundary used by the changed orchestration.

Historical and related documentation inspected:

- [Phase 1A independent approval audit](PHASE_1A_INDEPENDENT_APPROVAL_AUDIT.md)
- [Phase 1A final verification](PHASE_1A_FINAL_VERIFICATION.md)
- [Phase 1A provider architecture note](PHASE_1A_PROVIDER_ARCHITECTURE.md)
- [Phase 1G final pre-implementation readiness review](PHASE_1G_FINAL_PRE_IMPLEMENTATION_READINESS_REVIEW.md)

The remaining untracked Phase 1B-1F planning documents were inventoried but not re-audited for their planning content; they are outside this implementation-boundary review.

## 4. Architecture compliance assessment

| Area | Assessment |
|---|---|
| Generic application/provider boundary | **Compliant by static inspection.** `dev_ai.py` calls `create_provider()` and passes the resulting `AIProvider` to `AIService`; generic service code does not import Ollama classes/configuration. |
| Ollama serialization | **Compliant.** `role="tool"`, Ollama tool payloads, and tool-result JSON serialization are in `app/ai/ollama_client.py`. Generic orchestration exchanges `AssistantResponse`, `ToolCall`, and `ToolResultPayload`. |
| Registration and factory | **Compliant for the current scope.** Ollama is lazily constructed and remains the only registered/default provider. Registration supports additional `AIProvider` factories. `VeronicaModelProvider` is intentionally not registered and is not operational. |
| Capability declarations | **Truthful for the two built-in providers.** Ollama reports text/tools/vision and no streaming; Veronica reports no implemented capabilities and unavailable health/generation. Capability gating for individual application tools has a future-provider caveat in finding I-05. |
| Vision request boundary | **Compliant for request input.** `VisionRequest` requires a non-empty question and a PIL image. `LocalVisionService` accepts the runtime-checkable `VisionProvider` protocol, and closes the captured image in a `finally` block. Runtime validation of provider responses is incomplete (I-04). |
| Tool-call and response validation | **Mostly compliant.** Generic orchestration accepts only `AssistantResponse` and `ToolCall` values, rejects malformed/unknown response shapes, and invokes tools only through `ToolRegistry`, which validates object arguments against registered schemas. `ToolCall`'s own JSON-compatibility check is less strict than its contract and downstream validation (I-03). |
| Startup validation and errors | **Compliant for current built-in providers and their typed failures.** The factory creates the selected provider and startup calls `validate_startup()`. Known configuration, capability, model, timeout, connection, and response errors are handled. A provider raising the public base `ProviderError` directly would not be handled by the CLI startup block (I-02). |
| Legacy compatibility | **Explicit and isolated.** `OllamaLegacyToolCallingService`, `OllamaToolAdapter`, and `LegacyOllamaVisionProvider` are explicit compatibility paths. Generic `ToolCallingService` does not silently wrap arbitrary providers in an Ollama adapter. Lazy legacy exports remain available. |
| Test coverage | **Relevant contract tests are present, but not executed here.** The new provider contract tests cover factory selection, capability declarations, neutral tool transport, malformed responses, vision input/injection, and compatibility exports. Historical test results are recorded separately below. |
| Regression against Phase 1A | **No architectural regression found by source comparison.** Current code reflects the boundaries described in the latest Phase 1A approval audit; this static finding is not a runtime test or a new approval. |

## 5. Findings by severity

### Verified defects and inconsistencies

#### I-01 — Phase 1A architecture note contains stale or inaccurate implementation claims

- **Severity:** Medium
- **Files/lines:** `docs/PHASE_1A_PROVIDER_ARCHITECTURE.md:38,53,157,212`; current implementation at `app/ai/provider.py:24-35`, `app/ai/veronica_provider.py:23-34`, and `dev_ai.py:58-60,221-223`.
- **Evidence:** The architecture note says the factory provides `create_ollama_provider()`, while the implementation defines private `_create_ollama_provider()` and public `create_provider()`. It says `VeronicaModelProvider` advertises text, streaming, tools, and vision, while the implementation truthfully sets all four flags to `False`. It also says the CLI still constructs `OllamaClient` directly and that startup/model validation is unchanged, while current startup calls the provider factory and delegates validation to the provider.
- **Why it matters:** The note is a historical artifact but can mislead readers about current capabilities, supported entry points, and the approved integration seam. The historical test totals also differ across the Phase 1A architecture, final verification, and later independent approval records; do not treat them as one current result.
- **Regression from approved Phase 1A state:** **No implementation regression.** This is a documentation inconsistency; the later independent approval audit describes the current provider-neutral boundary more accurately.
- **Recommended next action:** Reconcile the historical architecture note with the later verified state in a separately authorized documentation task. Preserve the historical verdicts and clearly identify which test run each count describes.

#### I-03 — `ToolCall` argument validation does not match its JSON-compatible contract

- **Severity:** Low
- **Files/lines:** `app/ai/base.py:21-36`; downstream checks at `app/ai/tool_calling.py:196-233`; execution validation at `app/tools/registry.py:72-92`.
- **Evidence:** The constructor accepts a tuple as `arguments`, although tuples are not JSON values. Its container check is shallow, so a dictionary containing a non-JSON object also passes construction. The generic normalizer later rejects tuples, while `ToolRegistry` rejects non-JSON nested values and non-object tool arguments before execution.
- **Why it matters:** Provider implementations see inconsistent validation at contract construction versus orchestration. Current downstream validation prevents malformed arguments from reaching a tool, so no unsafe tool execution was observed.
- **Regression from approved Phase 1A state:** **No demonstrated regression.** This is a validation inconsistency in the current neutral contract.
- **Recommended next action:** Align construction-time validation with the accepted JSON value/object contract, or document that validation is intentionally deferred to the registry; add focused cases if the contract is changed.

### Potential risks and missing evidence

#### I-02 — CLI startup does not catch the provider-error base class

- **Severity:** Medium
- **Files/lines:** `app/ai/base.py:100-123`; `dev_ai.py:221-240`.
- **Evidence:** `ProviderError` is the public base for provider failures, but startup catches its specific subclasses rather than `ProviderError` itself. The current Ollama and Veronica implementations raise typed subclasses, so this path was not observed with built-in providers.
- **Why it matters:** A future registered provider that raises `ProviderError` directly from `validate_startup()` can escape the startup error handling and print a traceback instead of the CLI's normal error message.
- **Regression from approved Phase 1A state:** **Not demonstrated for current providers;** this is an extension-path risk in the generic boundary.
- **Recommended next action:** Decide whether arbitrary provider failures should be normalized at the factory or handled at the CLI boundary, then add a startup test for the chosen contract.

#### I-04 — Vision responses are trusted without runtime shape/content validation

- **Severity:** Low
- **Files/lines:** `app/ai/base.py:189-191`; `app/ai/vision.py:82-107`.
- **Evidence:** `VisionResponse` has a `text: str` annotation but no runtime validation. `LocalVisionService` reads `response.text` and calls `.strip()` without verifying that the provider returned a `VisionResponse` containing a string.
- **Why it matters:** A buggy or nonconforming structural provider can raise an untyped `AttributeError` or `TypeError`. The normal registered-tool path converts such exceptions into a generic execution failure, but the provider contract does not produce a clear response-validation error.
- **Regression from approved Phase 1A state:** **No observed Ollama regression.** This is a gap for malformed responses from future providers.
- **Recommended next action:** Validate provider response type and text before using it, with a focused fake-provider test.

#### I-05 — Screen-understanding tool availability is not filtered by provider vision capability

- **Severity:** Low
- **Files/lines:** `dev_ai.py:62-77`; `app/ai/base.py:83-89,158-160`; `app/ai/tool_calling.py:53-61`.
- **Evidence:** When the tool registry is built, it always registers `ScreenUnderstandingTool`, even if `provider.create_vision_provider()` returns `None`. The tool loop then builds definitions from all registered tools. The built-in Ollama provider supports vision, so this is not triggered by the current registered provider; the Veronica scaffold is not registered and reports no tool capability.
- **Why it matters:** A future provider that supports tools but not vision may still receive a screen-understanding tool definition, then receive an unavailable result if it requests it. This is a capability/availability mismatch, not a current disclosure or execution bypass.
- **Regression from approved Phase 1A state:** **No current-provider regression found.** This is a future-provider integration risk.
- **Recommended next action:** Filter or mark tool definitions using provider and tool-specific availability before exposing them to a model; test a tool-capable, vision-disabled provider.

## 6. Tests and checks

### Checks actually performed during this audit

- `git status --short`, `git diff --stat`, `git diff --check`, `git diff --name-only`, and `git ls-files --others --exclude-standard`.
- Static review of all 18 tracked diffs, the untracked provider/compatibility modules and contract-test file, the tool registry validation boundary, and the specified Phase 1A/1G documents.
- Cross-reference search for Ollama-specific imports, message roles, and serialization in generic service/orchestration files.
- **No test suite or individual test was run.** No inference, network request, training, benchmark, or installation was performed.

`git diff --check` reported no whitespace errors for the tracked diff. That command does not check untracked files, including this report.

### Previously recorded results (not rerun)

- The latest [Phase 1A independent approval audit](PHASE_1A_INDEPENDENT_APPROVAL_AUDIT.md) records **356 collected, 355 passed, 1 skipped, 0 failed**. The skip was `tests/test_file_search.py:187`, a Windows symlink privilege failure (`WinError 1314`).
- The earlier [Phase 1A final verification](PHASE_1A_FINAL_VERIFICATION.md) records **346 collected, 345 passed, 1 skipped, 0 failed**. It predates the later audit and is not a current result.
- The Phase 1A architecture note records other test totals, which are historical and contribute to documentation drift noted in I-01.

These are historical records only. No claim is made that the current worktree passes tests.

## 7. Approval-boundary assessment

- The latest Phase 1A audit approved provider-neutral application/orchestration boundaries, not multiple implemented providers, native model generation, or a switch away from Ollama.
- Ollama remains the only registered and complete provider and remains the default. The current factory does not register `VeronicaModelProvider`; its unavailable scaffold accurately declares no capabilities.
- The current source was compared with the approved architecture rather than presumed approved. No current source change inspected here was found to reintroduce generic Ollama wire serialization, implicit legacy adapter fallback, or a false Veronica capability claim.
- This report does not authorize implementation, integration, or provider selection. It does not update or supersede the Phase 1A approval for any later code state.

## 8. Final verdict

**APPROVED WITH CONDITIONS** for architectural-boundary consistency only:

1. Reconcile the stale Phase 1A architecture note and keep historical test results clearly attributed to their runs.
2. Resolve or explicitly accept findings I-02 through I-05 before relying on the generic boundary for additional providers.
3. Run the relevant test suite against the exact worktree intended for approval; this audit did not run tests.

**Architectural regression:** None found by static inspection.
**Runtime verification of current worktree:** Not performed.
