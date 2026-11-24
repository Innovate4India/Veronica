# Veronica - Phase 1A Independent Code Review

**Review date:** 2026-11-24
**Scope:** Read-only review of the Phase 1A provider-independent architecture. No source or test files were modified.

## Review Result
# NEEDS FIXES
Phase 1A establishes useful provider-neutral text and error contracts, preserves the Ollama implementation, and passes the full suite. However, it is not yet sufficient to claim provider-independent architecture:

- Ollama remains the direct runtime dependency in `dev_ai.py`.
- The provider factory is not used by the application.
- The future Veronica provider advertises capabilities it cannot perform.
- Vision and tool contracts still contain provider-specific/Ollama-shaped behavior.
- The generic tool loop retains Ollama-specific names, error text, and legacy response parsing.

## Verified Strengths

1. **Useful neutral text contract**
   - [app/ai/base.py](../app/ai/base.py) defines `AIProvider.generate_response()` using neutral `ChatMessage` values.
   - `ChatMessage` contains only role and content fields and does not import Ollama types.

2. **Provider-neutral metadata and capabilities**
   - [app/ai/base.py](../app/ai/base.py) defines `ProviderMetadata`, `ProviderCapabilities`, and provider-neutral typed errors.
   - Ollama implements those properties in [app/ai/ollama_client.py](../app/ai/ollama_client.py).

3. **Typed provider error hierarchy**
   - `ProviderConfigurationError`, `ProviderConnectionError`, `ProviderTimeoutError`, `ProviderResponseError`, and `ProviderModelUnavailableError` form a usable provider-neutral hierarchy.
   - Existing Ollama exception names remain subclasses of both their legacy/neutral categories where appropriate.
   - The focused suite and full suite confirmed no MRO or inheritance failures.

4. **No circular import found**
   - [app/ai/provider.py](../app/ai/provider.py) imports Ollama lazily from `create_ollama_provider()`.
   - [app/ai/ollama_client.py](../app/ai/ollama_client.py) depends on `app.ai.base` and `app.config`, not on `app.ai.service` or `app.ai.tool_calling`.
   - [app/ai/service.py](../app/ai/service.py) does not import Ollama implementation classes.
   - [app/ai/roles.py](../app/ai/roles.py) uses provider-neutral interfaces and catches both neutral and legacy provider errors.

5. **Ollama compatibility has been preserved**
   - Existing `OllamaClient`, `OllamaAssistantResponse`, `OllamaToolCall`, and tool payload types remain exported.
   - Existing Ollama HTTP, loopback validation, `/api/tags`, `/api/chat`, vision, and native tool methods remain.
   - Existing AI, tool, CLI, memory, role, voice, and vision tests pass.

6. **ToolRegistry boundaries remain intact**
   - Tool definitions, parameter schema validation, confirmation checks, execution limits, and structured outcomes remain in [app/tools/registry.py](../app/tools/registry.py).
   - Provider-neutral orchestration delegates execution to the existing allowlist.

7. **Conversation responsibilities remain separated**
   - [app/ai/service.py](../app/ai/service.py) owns conversation history, prompt assembly, roles, memory retrieval, and tool routing.
   - Memory remains in [app/memory/](../app/memory/) and tool execution remains in [app/tools/](../app/tools/).

## Bugs and Architectural Weaknesses

### High: Provider-neutral tool transport is not genuinely provider-neutral

`ToolDefinition` in [app/ai/base.py](../app/ai/base.py) uses the shape:

- `type: "function"`
- `function: {name, description, parameters}`

This shape is effectively provider-native/OpenAI-compatible and is likely usable by Ollama, but it is not a provider-independent abstract tool contract.

The orchestration in [app/ai/tool_calling.py](../app/ai/tool_calling.py) also still:

- Names `OllamaToolCallingService`
- Emits assistant/tool payloads shaped as `{"function": {...}}`
- Uses `"role": "tool"` message entries
- Parses a legacy Ollama-style text envelope for `web_search`
- Returns Ollama-specific error text for malformed/tool-limit conditions

This reduces provider independence because a future provider must mimic Ollama/OpenAI wire semantics instead of receiving only an abstract tool call API.

### High: Ollama remains directly wired into the real application

[dev_ai.py](../dev_ai.py) directly:

- Imports `OllamaClient`
- Loads `load_ollama_config()`
- Calls `OllamaClient(config)`
- Calls `client.list_models()`
- Constructs `OllamaToolCallingService`
- Passes Ollama `client` into vision

Provider selection is not used by startup. A future Veronica provider cannot replace Ollama through configuration or a factory call.

### Medium: Factory is unused

[app/ai/provider.py](../app/ai/provider.py) provides `create_provider()` and `create_ollama_provider()`, but no application code calls either function.

The factory currently supports only Ollama, so it does not reduce direct Ollama coupling yet.

### Medium: VeronicaModelProvider incorrectly advertises capabilities

[app/ai/veronica_provider.py](../app/ai/veronica_provider.py) advertises:

- `text=True`
- `streaming=True`
- `tools=True`
- `vision=True`

But the implementation:

- Raises `ProviderModelUnavailableError` for text
- Raises `ProviderModelUnavailableError` for streaming
- Has no tool-call generation method
- Has no vision generation method
- Reports `health_check() == False`

The test in [tests/test_provider_contracts.py](../tests/test_provider_contracts.py) incorrectly asserts streaming, tools, and vision are available even though they are not implemented.

### Medium: Vision is only structurally provider-neutral

[app/ai/vision.py](../app/ai/vision.py) accepts a local `_VisionClient` protocol and catches provider-neutral errors, which is a useful boundary.

Remaining issues:

- The base `AIProvider` interface has no vision method or vision response contract.
- Vision availability is represented as `ProviderCapabilities.vision`, but providers are not required to implement a vision method.
- `_model_is_installed()` is Ollama-style name normalization.
- User-facing messages still name Ollama configuration and Ollama model installation.
- `dev_ai.py` passes `OllamaClient`, not a provider abstraction.
- The `PIL.Image` dependency remains in the Ollama and vision implementation path.

As currently written, a provider can advertise vision while having no usable vision contract.

### Medium: Streaming is an interface but not an extensible application path

`AIProvider.generate_stream()` exists in [app/ai/base.py](../app/ai/base.py), and providers can inherit a one-chunk fallback.

Remaining limitations:

- Ollama metadata reports `streaming=False`, matching the current implementation.
- `AIService` does not expose or consume streaming.
- CLI output does not consume streaming chunks.
- There is no async/iterator error-state contract or cancellation/finish metadata.
- The method is future-ready only; it is not yet an application-facing streaming architecture.

### Medium: Tool-call normalization contains a provider-neutrality gap

[app/ai/tool_calling.py](../app/ai/tool_calling.py) `_normalize_assistant_response()` only iterates `raw_calls` when it is a tuple:

```python
for call in raw_calls if isinstance(raw_calls, tuple) else ()
```

A provider-neutral `AssistantResponse` can contain a list or another sequence if constructed directly, but the normalizer does not preserve that call type. It is also duck-typed rather than using a formal provider adapter contract.

Additionally, `_normalize_assistant_response()` silently converts a dict or unknown object into an empty text response and an empty call tuple instead of rejecting an invalid provider result.

### Medium: Legacy text-tool parsing remains in the generic core

`_parse_web_search_content_call()` in [app/ai/tool_calling.py](../app/ai/tool_calling.py) remains provider-neutral core logic for an Ollama compatibility behavior. It recognizes web-search JSON text and converts malformed envelopes to tool calls.

This introduces a provider-specific model compatibility rule into generic tool orchestration and couples the core loop to `web_search` legacy behavior.

### Low: Ollama-specific language remains in generic tool errors

Examples include:

- `"Ollama returned a malformed tool call."`
- `"Ollama returned a tool request after screen understanding."`
- `"Ollama did not return a final assistant text response."`

These strings can be misleading if the tool loop is exercised with a future provider.

### Low: Ollama-specific configuration remains outside the adapter

[app/config.py](../app/config.py) still owns only Ollama environment/config data for text and vision. Provider-neutral configuration is not modeled, and provider selection cannot yet be expressed independently of the Ollama module.

## Incorrect or Misleading Capability Declarations

| Provider | Declared Capability | Actual Status |
|---|---|---|
| Ollama text | `text=True` | Implemented |
| Ollama streaming | `streaming=False` | Accurate for current implementation |
| Ollama tools | `tools=True` | Implemented native tool round trips |
| Ollama vision | `vision=True` | Implemented when model/configured files are available |
| Veronica text | `text=True` | Misleading: generation raises unavailable |
| Veronica streaming | `streaming=True` | Misleading: generation raises unavailable |
| Veronica tools | `tools=True` | Misleading: no tool method or transport |
| Veronica vision | `vision=True` | Misleading: no vision method or transport |

The default `AIProvider` metadata also reports text as enabled through `ProviderCapabilities(text=True)`, even though a subclass only receives the default text capability if it does not override metadata. This can hide whether a provider actually implemented text generation.

## Remaining Ollama Coupling

### Direct application coupling

- [dev_ai.py](../dev_ai.py): direct `OllamaClient`, Ollama config, Ollama model checks, and Ollama tool calling.
- [app/config.py](../app/config.py): Ollama base URL/model/timeout/vision environment variables.
- [app/ai/vision.py](../app/ai/vision.py): Ollama-specific configuration and installation messages.
- [app/ai/tool_calling.py](../app/ai/tool_calling.py): Ollama names and legacy compatibility text.
- [app/ai/__init__.py](../app/ai/__init__.py): Ollama types remain exported in the public package.

### Adapter-contained coupling

The following coupling is appropriately isolated inside the Ollama implementation:

- Ollama HTTP endpoint and `/api/chat`
- Ollama native tool payload types
- Ollama tool-call parsing
- Ollama vision image encoding
- Ollama model discovery

### Remaining feature-level coupling

- [app/ai/service.py](../app/ai/service.py) is provider-neutral for ordinary text generation.
- Tool results and registered tools are provider-neutral after execution.
- Role classification is provider-neutral and currently can use any provider implementing text generation.
- Conversation history uses provider-neutral `ChatMessage`.

## Tool-Call Normalization Review

Verified behavior:

- Neutral `AssistantResponse` with a tuple of `ToolCall` values is recognized.
- Legacy Ollama `OllamaAssistantResponse`/`OllamaToolCall` objects are recognized through duck typing.
- Tool calls are converted to the registry-neutral `ToolCall` shape.
- Malformed calls become validation failures instead of execution.
- Tool call count remains bounded at four.
- Legacy web-search text envelopes remain rejected or converted safely.
- Tool payload results are serialized without logging parameters or exceptions.

Weaknesses:

- Normalization depends on Ollama-shaped `function` payload structures.
- Sequence handling is narrower than the provider-neutral dataclass contract.
- Invalid provider response objects are silently normalized to empty text.
- Generic tool loop error text and class naming are Ollama-specific.

## Backward Compatibility Findings

### Verified compatible

- Existing `OllamaClient` behavior remains covered by existing tests.
- Existing `OllamaAssistantResponse`, `OllamaToolCall`, and Ollama message types remain exported.
- Existing `OllamaToolCallingService` name and constructor behavior remain available.
- Existing Ollama exception imports remain available.
- Existing CLI startup and Ollama model-validation behavior remain present.
- The complete suite passes.

### Compatibility weaknesses

- The new provider-neutral package exports Ollama types at the top level, making it easy for core code to continue importing them.
- The provider factory does not expose or configure Veronica-owned providers.
- Ollama-specific startup exceptions are inherited by provider-neutral errors, but generic `AIService` callers still need to handle or inspect the provider-neutral hierarchy.
- The neutral tool protocol is not fully documented as a formal adapter; Ollama response types are normalized retrospectively rather than converted by an explicit adapter boundary.

## Test Results

Command:

```powershell
.\\.venv\\Scripts\\python.exe -m pytest -ra
```

- **Collected:** 343
- **Passed:** 342
- **Failed:** 0
- **Skipped:** 1

Skip:

- [tests/test_file_search.py](../tests/test_file_search.py:187)
- Windows returned `[WinError 1314]` while creating a directory symlink.

The provider contract tests provide useful fake-provider coverage:

- A fake text provider works through `AIService`.
- Streaming fallback yields one chunk.
- The Ollama factory path creates Ollama metadata.
- Unknown providers are rejected.
- The Veronica scaffold raises unavailable for text.
- A fake provider-neutral tool call executes through `ToolRegistry`.

Coverage gaps:

- No test verifies that Ollama and Veronica providers share a formally neutral tool/vision interface.
- No test verifies neutral tool response handling for list sequences.
- No test verifies invalid provider response objects are rejected rather than normalized silently.
- No test verifies that provider-neutral vision errors do not expose Ollama names.
- No test asserts that `VeronicaModelProvider` should advertise capabilities as false.

## Recommendations

### Critical

No critical runtime vulnerability or data-loss bug was identified.

### High

1. **Route `dev_ai.py` through the provider factory**
   - Select Ollama only as the current default.
   - Stop direct Ollama construction in the application startup path.
   - Move Ollama model/configuration checks behind the provider adapter.

2. **Create a formal provider-neutral tool interface**
   - Replace Ollama/OpenAI-shaped tool definitions and tool payload types with generic tool-call/tool-result types.
   - Make Ollama translate neutral types to native Ollama payloads.
   - Move legacy web-search text-envelope parsing into the Ollama adapter.

3. **Correct capabilities for the Veronica scaffold**
   - Advertise text, streaming, tools, and vision as false until implemented.
   - Add tests that prevent future capability declarations from claiming unsupported operations.

### Medium

1. **Add a neutral vision interface**
   - Add vision methods or capabilities to `AIProvider` or a separate `VisionProvider` base.
   - Return a provider-neutral result and expose provider-neutral errors.
   - Keep Ollama-specific model-name normalization in its adapter.

2. **Move Ollama names out of generic code**
   - Replace generic tool and vision error text with provider-neutral wording.
   - Keep Ollama-specific diagnostics in Ollama adapter methods.

3. **Strengthen tool response normalization**
   - Accept only explicit `AssistantResponse` or formal adapter responses.
   - Reject unknown objects and malformed tool-call sequences.
   - Support and validate list/tuple sequences consistently.

4. **Make provider capabilities authoritative**
   - Make capability claims required or opt-in rather than defaulting every provider to text.
   - Include vision/tool capability interfaces rather than metadata-only declarations.

### Low

1. Split Ollama compatibility exports from the primary provider-neutral exports.
2. Add a provider-neutral streaming consumer test in `AIService`.
3. Document the exact migration order for replacing Ollama.
4. Add provider metadata tests for health and model discovery.

## Final Verdict

# NEEDS FIXES

The Phase 1A implementation is a valid compatibility bridge and improves provider abstraction for text generation and typed errors. It should not yet be considered provider-independent because the runtime application, tool transport, factory usage, vision boundary, and future scaffold remain coupled to or misleading about Ollama capabilities.
