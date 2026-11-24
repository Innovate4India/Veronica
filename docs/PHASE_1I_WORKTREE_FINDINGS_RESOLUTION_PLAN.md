# Veronica Phase 1I: Worktree Findings Resolution Plan

**Task type:** Planning and documentation only
**Status:** Not authorized for implementation
**Review date:** 2026-11-24

> **Planning approval is not implementation authorization.**

This plan describes how the five findings in the [Phase 1H Existing Worktree Independent Audit](PHASE_1H_EXISTING_WORKTREE_INDEPENDENT_AUDIT.md) could be addressed in a future, explicitly authorized phase. No finding is marked fixed or resolved. No implementation or tests were performed for this plan.

## 1. Repository state recorded before inspection

The required initial inspection recorded:

- `git status --short` and `git ls-files --others --exclude-standard`: 18 modified tracked files and 18 untracked files before this plan was created.
- `git diff --stat`: 1,046 insertions and 405 deletions across tracked modifications; untracked files are not included.
- `git diff --check`: no reported whitespace errors in the tracked diff.
- No staged changes were listed.
- The Phase 1I target did not exist before this plan was created.

The existing worktree changes are not part of this plan's proposed edits and must be preserved. In particular, future implementation work must not reset, stash, clean, stage, or overwrite them without separate user authorization.

## 2. Scope and cross-cutting constraints

The future resolution must preserve all of the following:

1. English, Hindi (Devanagari), and Hinglish (Roman Hindi) remain equal language priorities. No language-specific policy or implementation in this plan ranks one above another.
2. Ollama remains the only complete registered/default provider until a separately approved replacement passes applicable gates.
3. `VeronicaModelProvider` remains an unavailable scaffold unless a separate task authorizes a native-model implementation.
4. Generic application and orchestration code must not construct Ollama wire messages or serialize Ollama tool-result payloads.
5. Provider capability declarations must match implemented behavior; model availability/configuration remains distinct from implementation capability.
6. Private conversations and SQLite memories are not automatically used for training.
7. No pretrained model may silently become Veronica's permanent answer engine.
8. Each source/test correction below needs explicit implementation authorization. This plan alone authorizes none of them.

## 3. Finding I-01 — Stale Phase 1A architecture documentation

**Severity:** Medium
**Status:** Open; verified documentation inconsistency
**Historical reference:** [Phase 1A provider architecture note](PHASE_1A_PROVIDER_ARCHITECTURE.md)

### Verified evidence and affected files

- `docs/PHASE_1A_PROVIDER_ARCHITECTURE.md:38` says the factory provides public `create_provider()` and `create_ollama_provider()`. The current `app/ai/provider.py` provides public `create_provider()` and private `_create_ollama_provider()`.
- `docs/PHASE_1A_PROVIDER_ARCHITECTURE.md:53` says the Veronica scaffold advertises text, streaming, tools, and vision. `app/ai/veronica_provider.py` sets all four capabilities to `False`, returns unhealthy, and raises `ProviderModelUnavailableError` for generation.
- The note's compatibility summary and remaining limitations (`:157`, `:212`) say CLI startup/model validation is unchanged and that the CLI still constructs `OllamaClient` directly. Current `dev_ai.py` uses `_create_provider()`/`create_provider()` and calls `provider.validate_startup()`.
- The note records a 343-collected full test run; [Phase 1A final verification](PHASE_1A_FINAL_VERIFICATION.md) records 346 collected; the later [Phase 1A independent approval audit](PHASE_1A_INDEPENDENT_APPROVAL_AUDIT.md) records 356 collected. These are historical runs, not a current worktree result.
- The final verification's **NEEDS FIXES** verdict and the later independent audit's **APPROVED** verdict are chronological and have different review outcomes. The later approval is limited to provider-neutral application/orchestration boundaries.

### Proposed correction

Correct the architecture note in a separately authorized documentation-only change:

1. State that `create_provider()` is the public selector and `_create_ollama_provider()` is the private Ollama factory; the registry currently contains only Ollama.
2. State that the Veronica scaffold advertises no implemented capabilities and remains unavailable.
3. Replace the stale startup/validation statements with the current provider-factory startup flow, while clarifying that Ollama remains the default and only complete provider.
4. Preserve every historical verdict and test count in place or in a clearly labeled chronology. Add an as-of/current-state note rather than rewriting old results as current.
5. Identify the latest approval's narrow scope; do not imply that it approves model training, provider replacement, or a future code revision.

### Future files that may need modification

- `docs/PHASE_1A_PROVIDER_ARCHITECTURE.md` only.
- Do not modify the Phase 1A approval audit, final verification, Phase 1H audit, or any other existing document as part of this correction unless separately authorized.

### Regression tests, acceptance, and verification

- **Tests:** None required for a documentation-only correction.
- **Acceptance criteria:** Every listed claim matches the inspected source; old verdicts and test counts remain explicitly historical; no claim says the worktree has passed tests unless a dated run supports it.
- **Independent verification:** A reviewer checks the corrected statements against `app/ai/provider.py`, `app/ai/veronica_provider.py`, and `dev_ai.py`, and confirms the historical records remain unchanged.
- **Compatibility risks:** Rephrasing old statements could accidentally make the historical note appear to have been written after later changes. Keep chronology and status labels explicit.
- **Dependencies:** None. This documentation correction can precede the code-related findings.
- **Mandatory or optional:** **Mandatory** for maintaining accurate Phase 1A reference documentation; it does not change application behavior.

## 4. Finding I-02 — ProviderError startup handling

**Severity:** Medium
**Status:** Open; future-provider error-handling risk
**Evidence:** `ProviderError` is the public provider-failure base in `app/ai/base.py`; `dev_ai.main()` catches specific subclasses around provider creation/startup but has no final `except ProviderError` fallback (`dev_ai.py:221-240`).

### Proposed correction and handling boundary

Keep CLI exit behavior at the CLI startup boundary, because `main()` owns user-facing diagnostics and exit codes. Preserve the existing typed branches and add a final `ProviderError` fallback after all specific provider exceptions. Do not catch broad `Exception` as a substitute.

Suggested behavior for a provider that raises the base class directly during `validate_startup()`:

- Print a clear, provider-neutral startup failure message without a traceback or sensitive exception details.
- Return a nonzero startup status (recommended: `1`, consistent with connection/response failures).
- Keep current specific handling unchanged: configuration/capability/model-selection errors remain configuration exits; timeout/connection and response failures retain their existing sanitized messages and exit codes.

### Future files that may need modification

- `dev_ai.py` for the base-class fallback.
- `tests/test_dev_ai.py` for CLI startup coverage.
- `tests/test_provider_contracts.py` only if a shared provider error contract test is preferred.
- Do not change Ollama error inheritance or provider selection as part of this finding.

### Required regression tests and acceptance criteria

1. A fake selected provider whose `validate_startup()` raises `ProviderError` directly returns the agreed nonzero code, prints the generic startup diagnostic, and emits no traceback.
2. Existing tests for `ProviderConfigurationError`, `ProviderCapabilityError`, `ProviderModelUnavailableError`, `ProviderTimeoutError`, `ProviderConnectionError`, and `ProviderResponseError` retain their specific messages and exit behavior.
3. No broad catch hides unrelated programming errors.
4. Provider errors during normal chat continue to be handled through the existing `AIService` boundary.

### Risks, verification, dependencies, and status

- **Compatibility risks:** A broad fallback could accidentally swallow defects or override the more specific exit codes. Keep it after typed catches and catch only `ProviderError`.
- **Independent verification:** Review exception inheritance and branch ordering; run the focused startup tests, then the full existing test suite in the explicitly authorized phase.
- **Dependencies:** Independent of I-01 and I-03 through I-05.
- **Mandatory or optional:** **Mandatory** before relying on arbitrary registered providers that may use the base error directly; not currently reproduced by the built-in providers.

## 5. Finding I-03 — ToolCall JSON-compatible validation

**Severity:** Low
**Status:** Open; verified contract inconsistency
**Evidence:** `ToolCall.__post_init__` in `app/ai/base.py:21-36` accepts tuples and only checks the outer container. The generic normalizer in `app/ai/tool_calling.py:196-233` later rejects tuples, and `ToolRegistry` performs recursive JSON/schema/object validation before execution (`app/tools/registry.py:72-92`).

### Proposed correction

Define the contract for a well-formed tool call as **an object of string keys to recursively valid JSON values**. JSON-compatible values are `null`, booleans, integers, finite floats, strings, lists of JSON values, and dictionaries with string keys and JSON-value contents. Reject tuples, sets, non-finite floats, unsupported objects, and non-string object keys.

At construction/normalization time, require an object for a non-malformed call. Keep malformed-provider-response representation explicit and non-executable; normalize invalid raw arguments to a safe malformed sentinel rather than allowing unsupported objects to reach a registry or serializer. The existing registry remains authoritative for registered-tool allowlists, confirmation requirements, and tool-specific schema constraints.

### Future files that may need modification

- `app/ai/base.py` for the contract and construction-time checks.
- `app/ai/tool_calling.py` if malformed normalization needs to align with the chosen contract.
- `tests/test_provider_contracts.py` for focused contract cases.
- Existing `ToolRegistry` code should remain unchanged unless future implementation evidence identifies a separate defect.

### Required regression tests

**Positive cases**

- Empty and populated string-keyed dictionaries containing nested JSON scalars, lists, and dictionaries.
- `None`, if used only as the documented malformed-call sentinel, remains non-executable.

**Negative cases**

- Tuple at the top level and nested in a dictionary/list.
- Scalar/list arguments for a well-formed tool call when the contract requires an object.
- Nested arbitrary objects, sets, non-string dictionary keys, NaN, and infinity.
- Malformed calls are rejected by the normalizer/registry path and never invoke a tool.

### Acceptance, risks, verification, and status

- **Acceptance criteria:** Construction, generic normalization, and tool dispatch agree on accepted shapes; valid object arguments still reach `ToolRegistry`; schema validation and allowlist/confirmation checks remain intact; invalid input never executes a tool.
- **Compatibility risks:** Existing providers or tests might rely on non-object arguments or tuples. Preserve support only if a documented provider contract requires it; do not loosen validation for convenience.
- **Independent verification:** Inspect the JSON type checks and registry boundary; run focused positive/negative tests and existing tool-calling tests; verify invalid cases cannot call a registered fake tool.
- **Dependencies:** No implementation dependency on I-02 or I-04; complete before broad final regression testing.
- **Mandatory or optional:** **Mandatory** to make the declared JSON-compatible/object contract reliable.

## 6. Finding I-04 — VisionResponse runtime validation

**Severity:** Low
**Status:** Open; missing runtime validation for structural providers
**Evidence:** `VisionResponse` in `app/ai/base.py:189-191` only annotates `text: str`; `LocalVisionService` reads `response.text` and calls `.strip()` without checking the runtime type (`app/ai/vision.py:82-107`).

### Proposed correction

Validate the provider result immediately after `generate_vision()` returns and before using `.text`:

1. Require a `VisionResponse` instance.
2. Require `text` to be a string.
3. Treat empty or whitespace-only text as an invalid/unavailable vision result; do not return it as a successful answer.
4. Convert malformed provider output into a clear, stable provider/tool error without exposing provider internals or private screen content.
5. Preserve the `finally` cleanup so every captured image is closed after success or failure.

The exact error class/message should follow the repository's existing provider and `ToolUnavailableError` conventions. Do not add a success-shaped fallback.

### Future files that may need modification

- `app/ai/vision.py` for response validation and stable error conversion.
- `app/ai/base.py` only if a constructor-level invariant is selected; service-boundary validation is still required for nonconforming structural implementations.
- `tests/test_provider_contracts.py` and/or `tests/test_screen_understanding.py` for malformed-response coverage.

### Required regression tests

- A structural fake returning a non-`VisionResponse` object is rejected clearly.
- A fake returning `VisionResponse` with a non-string `text` is rejected clearly.
- Empty and whitespace-only strings produce the agreed failure, not an empty success.
- A valid non-empty response is returned unchanged after trimming according to existing behavior.
- The captured image is closed for every malformed and empty response path.
- Existing timeout, connection, missing-model, and model-unavailable behavior remains unchanged.

### Acceptance, risks, verification, and status

- **Acceptance criteria:** Only a valid, non-empty string response succeeds; all invalid result cases use a clear error path; captured-image cleanup is guaranteed.
- **Compatibility risks:** Custom providers that currently return duck-typed objects or non-string text will be rejected. This is intentional contract enforcement; keep structural provider injection itself intact.
- **Independent verification:** Review the returned-object guards and error mapping; run focused fake-provider tests through both `LocalVisionService` and the registered screen tool.
- **Dependencies:** Independent of I-02 and I-03. Resolve before I-05 tests that exercise vision-enabled providers.
- **Mandatory or optional:** **Mandatory** before treating vision as a trustworthy provider-neutral contract.

## 7. Finding I-05 — Screen-understanding capability filtering

**Severity:** Low
**Status:** Open; future-provider capability mismatch
**Evidence:** `dev_ai._create_tool_registry()` always registers `ScreenUnderstandingTool` (`dev_ai.py:62-77`). `ToolCallingService` derives definitions from all registered tools (`app/ai/tool_calling.py:53-61`). A future provider can support tool calls while `create_vision_provider()` returns `None` and `metadata.capabilities.vision` is false.

### Proposed correction and availability policy

Recommended policy: **exclude screen understanding from the model's available tool definitions when the provider does not implement vision or returns no vision adapter.** Do not advertise a capability the provider cannot carry out. Keep the tool's execution path fail-closed if a request is nevertheless received through a stale or direct call.

When vision is implemented and an adapter is returned, include the screen-understanding tool as today. Preserve current Ollama behavior: Ollama advertises the implemented vision capability and returns its adapter. If its optional vision model is not configured, retain the current clear unavailable response rather than silently switching providers or removing Ollama's existing behavior.

The screenshot metadata-only tool is distinct from image interpretation and should not be removed solely because vision is unsupported.

### Future files that may need modification

- `dev_ai.py` or a narrowly scoped tool-registry builder to conditionally register/expose `ScreenUnderstandingTool`.
- `app/ai/tool_calling.py` only if tool-definition filtering belongs at the generic registry boundary; keep provider-specific logic out of generic serialization.
- `tests/test_provider_contracts.py`, `tests/test_dev_ai.py`, and/or `tests/test_screen_understanding.py`.
- Avoid changing `OllamaClient` capabilities or Ollama model behavior unless separately justified by verification.

### Required regression tests

1. A fake provider with tool support but `vision=False`/no vision adapter does not receive a `screen_understanding` tool definition; a direct attempt remains unavailable and does not capture the screen.
2. A fake vision-capable provider with an adapter receives the screen-understanding definition and can complete a valid fake vision response.
3. Ollama continues to receive the same screen-understanding behavior when its vision adapter is present.
4. An unconfigured Ollama vision model continues to fail with the existing clear unavailable behavior; no fallback to another provider occurs.
5. Screenshot-only behavior remains available and does not imply image interpretation.

### Acceptance, risks, verification, and status

- **Acceptance criteria:** Tool definitions reflect provider implementation capability; vision-disabled providers do not receive screen-understanding instructions; vision-capable providers retain the existing flow; direct unsupported calls fail closed.
- **Compatibility risks:** Filtering changes which tool definitions a non-vision provider receives. Avoid changing the current Ollama behavior, tool allowlist semantics, screen-capture privacy controls, or screenshot metadata tool.
- **Independent verification:** Use a fake tool-capable/vision-disabled provider and inspect the exact definitions passed to it; use a vision-enabled fake and the Ollama adapter to confirm inclusion and behavior. Review generic modules for Ollama payload construction.
- **Dependencies:** Depends on a stable vision-response contract from I-04 and should follow it. Independent of I-02 and I-03.
- **Mandatory or optional:** **Conditionally mandatory** before enabling any tool-capable provider without vision. It is not a behavior change required for the current Ollama-only registration if no such provider is introduced.

## 8. Safest future implementation order

This order isolates documentation from behavior changes, then resolves the core contracts before connecting capability decisions. It is a recommendation, not authorization:

1. **Establish the exact authorized baseline.** Record the worktree state and scope in the future task. Preserve every existing modification and untracked file; do not clean, reset, stash, or overwrite them.
2. **Resolve I-01 first (documentation only).** Correct the stale architecture note while preserving historical findings, verdicts, and run-specific test totals. This establishes accurate reference claims without touching code.
3. **Resolve I-03 (tool-call value contract).** Agree the accepted JSON/object contract, update construction/normalization as authorized, and run focused safety/compatibility tests before changing other provider behavior.
4. **Resolve I-02 (startup error fallback).** Add the base-error catch after specific typed branches and test the user-facing exit behavior; retain all specific branches.
5. **Resolve I-04 (vision response validation).** Validate provider output and cleanup behavior, then run focused vision tests.
6. **Resolve I-05 (tool capability filtering).** After I-04 is stable, filter only unsupported vision tools and test both vision-disabled and vision-enabled providers, including Ollama compatibility.
7. **Perform independent verification.** In a separately authorized verification phase, inspect the final diff and run the focused tests followed by the agreed full suite. Record exact commands, results, skips, and any unverified behavior. Do not infer success from this plan or from historical test totals.

I-02 and I-03 are independent in code, but this order keeps each behavioral change separately reviewable. I-04 precedes I-05 because capability filtering depends on a dependable vision boundary. I-01 is isolated so historical documentation can be corrected without being rewritten by implementation changes.

## 9. Cross-cutting acceptance gates

Any future implementation/verification request should confirm all of the following before considering these findings addressed:

- English, Hindi (Devanagari), and Hinglish (Roman Hindi) remain equal priorities; no change here implies equal sampling proportions.
- Ollama remains the only complete registered/default provider unless a separate, explicit replacement approval is granted.
- `VeronicaModelProvider` remains unavailable and advertises no implemented capabilities until separately authorized implementation exists.
- Ollama wire formats and serialization remain confined to the Ollama adapter and explicitly named compatibility modules.
- Provider capabilities, tool definitions, and runtime availability agree; unsupported operations fail closed.
- Tool calls remain subject to `ToolRegistry` allowlisting, confirmation, and schema validation.
- Personal conversations and SQLite memories are never automatically included in training data.
- A pretrained model does not become Veronica's permanent answer engine by implication or fallback.
- No tests, benchmarks, model execution, installation, or training are claimed as completed unless actually authorized and run.

## 10. Files and authorization record

This task creates only `docs/PHASE_1I_WORKTREE_FINDINGS_RESOLUTION_PLAN.md`. No source code, tests, configuration, Phase 1A approval record, or Phase 1H audit is modified by this plan.

**Planning approval is not implementation authorization.** Each proposed correction requires a future, explicit implementation scope. No finding is fixed or resolved by this document.
