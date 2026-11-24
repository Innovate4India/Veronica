# Veronica - Phase 1A Corrective Implementation Report

**Date:** 2026-11-24
**Scope:** Correct the architectural weaknesses identified in [PHASE_1A_CODE_REVIEW.md](PHASE_1A_CODE_REVIEW.md). No Ollama removal, model training, cloud infrastructure, or external AI provider was added.

## 1. Issues Found in the Independent Review

The independent review identified these correction areas:

1. `create_provider()` was not used by the real application startup.
2. The generic tool loop still exposed Ollama/OpenAI-shaped tool definitions and tool-call payload assumptions.
3. Legacy web-search text-envelope parsing remained in generic tool orchestration.
4. `VeronicaModelProvider` declared text, streaming, tool, and vision capabilities that it could not perform.
5. Vision had only a partial protocol and still contained Ollama-specific model and message handling.
6. Tool response normalization silently normalized unknown objects and lacked complete provider-neutral validation.
7. Generic provider code still had provider-specific names and error messages.
8. Provider capabilities did not distinguish implemented functionality truthfully.

## 2. Files Modified and Why

### Provider contracts

- [app/ai/base.py](../app/ai/base.py)
  - Defaulted provider capabilities to false instead of text=true.
  - Added neutral `ToolCall`, `AssistantResponse`, `ToolDefinition`, `ToolResultPayload`, and `ToolErrorPayload` contracts.
  - Added `VisionProvider`, `VisionRequest`, and `VisionResponse`.
  - Kept text, streaming, tool, and provider metadata contracts in the provider-neutral module.

### Provider factory

- [app/ai/provider.py](../app/ai/provider.py)
  - Added an optional Ollama provider factory injection for compatibility testing.
  - Kept Ollama as the default registered provider.
  - Unknown providers remain rejected.

### Veronica scaffold

- [app/ai/veronica_provider.py](../app/ai/veronica_provider.py)
  - Set text, streaming, tools, and vision capabilities to false.
  - Preserved an explicit unavailable error boundary.
  - Did not add model loading or inference.

### Ollama adapter

- [app/ai/ollama_client.py](../app/ai/ollama_client.py)
  - Added `generate_provider_tool_response()` for provider-neutral tool output.
  - Added `OllamaToolAdapter` to translate neutral tool definitions and conversation payloads to Ollama.
  - Added `OllamaVisionProvider` for the formal vision contract.
  - Added `LegacyOllamaVisionProvider` for existing Ollama vision clients and mocks.
  - Moved legacy web-search text-envelope parsing into the Ollama compatibility adapter.
  - Preserved existing Ollama classes, names, methods, and exception exports.

### Tool orchestration

- [app/ai/tool_calling.py](../app/ai/tool_calling.py)
  - Uses neutral `ToolDefinition`, `ToolCall`, and `AssistantResponse` values.
  - Uses a compatibility adapter for legacy providers that expose only `generate_tool_response()`.
  - Removed Ollama-shaped tool definitions from generic orchestration.
  - Removed generic web-search text-envelope parsing.
  - Normalizes only explicit neutral responses or responses translated by the compatibility adapter.
  - Rejects unknown provider response types and malformed call sequences.
  - Preserves the four-call limit and registry validation/execution behavior.

### Vision orchestration

- [app/ai/vision.py](../app/ai/vision.py)
  - Accepts the formal `VisionProvider` contract.
  - Adapts existing legacy vision clients through the Ollama adapter.
  - Uses provider-neutral `VisionRequest` and `VisionResponse`.
  - Uses generic provider-neutral errors except in the explicit Ollama legacy compatibility boundary.

### Application startup

- [dev_ai.py](../dev_ai.py)
  - Added `_create_provider()` and integrated `create_provider()` into startup.
  - Uses provider-neutral `list_models()` and provider-neutral error categories.
  - Keeps Ollama as the default provider.
  - Keeps existing Ollama model validation and CLI startup messages.
  - Passes an Ollama vision adapter into the vision tool.

### Public exports

- [app/ai/__init__.py](../app/ai/__init__.py)
  - Exported neutral provider, tool, and vision contracts.
  - Retained existing Ollama compatibility exports.

### Tests

- [tests/test_provider_contracts.py](../tests/test_provider_contracts.py)
  - Added fake text-provider coverage.
  - Added list and tuple tool-call coverage.
  - Added invalid unknown-provider tool-response rejection.
  - Added provider-neutral vision contract coverage.
  - Added truthful Veronica capability assertions.

No unrelated production module was changed.

## 3. Architecture Changes

### Provider-neutral text

`AIProvider.generate_response()` remains the text boundary with neutral `ChatMessage` values.

Streaming remains a future-ready fallback on `AIProvider.generate_stream()`. Ollama reports streaming as unavailable. The future Veronica provider reports all capabilities false.

### Provider-neutral tools

Generic tool definitions now contain:

- `name`
- `description`
- `parameters`

Generic tool calls contain:

- `name`
- `arguments`
- `malformed`

Generic tool results now have neutral result/error payload types in `app/ai/base.py`.

The generic loop:

1. Builds neutral tool definitions.
2. Requests a neutral `AssistantResponse`.
3. Validates list or tuple tool calls.
4. Executes calls through `ToolRegistry`.
5. Returns provider-neutral final text or typed tool-loop errors.

Ollama is translated at the adapter:

- Neutral tool definitions become Ollama function definitions.
- Neutral conversation tool calls become Ollama function payloads.
- Ollama native tool calls become neutral `ToolCall` values.
- Legacy web-search text envelopes are parsed only in `OllamaToolAdapter` and `OllamaClient.generate_provider_tool_response()`.

Existing providers that expose only `generate_tool_response()` are wrapped by `OllamaToolAdapter` for backward compatibility.

### Provider-neutral vision

The formal contract is `VisionProvider`:

- `model_available(model)`
- `generate_vision(VisionRequest) -> VisionResponse`

Ollama image encoding and model-name normalization remain in `OllamaVisionProvider` and `LegacyOllamaVisionProvider`.

Generic `LocalVisionService`:

- Uses a formal vision provider where available.
- Keeps existing direct Ollama/mock clients working through the legacy adapter.
- Uses provider-neutral request/response values.
- Removes Ollama model-name handling from generic vision orchestration.

### Provider capabilities

Provider capability defaults are false.

The Ollama provider accurately declares:

- text=true
- streaming=false
- tools=true
- vision=true

`VeronicaModelProvider` accurately declares:

- text=false
- streaming=false
- tools=false
- vision=false

### Factory integration

`dev_ai.py` now calls `create_provider("ollama", ...)` through `_create_provider()`.

Ollama remains the compatibility-default provider and model startup behavior remains unchanged.

## 4. Backward Compatibility Verification

Preserved compatibility includes:

- Existing `OllamaClient` text and vision methods.
- Existing `OllamaAssistantResponse`, `OllamaToolCall`, `OllamaToolDefinition`, and Ollama message payload exports.
- Existing `OllamaToolCallingService` name and constructor.
- Existing native Ollama tool-calling behavior.
- Existing legacy web-search text-envelope compatibility.
- Existing CLI Ollama configuration, model checks, and error messages.
- Existing memory, role, teaching, tool, voice, and vision behavior.

The complete suite confirms existing Ollama tool and vision tests continue to pass.

## 5. Tests Executed and Exact Results

### Provider, startup, tool, and vision focused run

Command:

```powershell
.\\.venv\\Scripts\\python.exe -m pytest -q tests/test_provider_contracts.py tests/test_ai_tool_calling.py tests/test_dev_ai.py tests/test_screen_understanding.py tests/test_ai.py
```

Result:

- **69 passed**
- **48 subtests passed**
- **0 failed**

### Complete suite

Command:

```powershell
.\\.venv\\Scripts\\python.exe -m pytest -ra
```

Result:

- **346 collected**
- **345 passed**
- **1 skipped**
- **0 failed**

Skip:

- [tests/test_file_search.py](../tests/test_file_search.py:187)
- Windows `[WinError 1314]` prevented directory-symlink creation.

The skip is unchanged from the existing test suite and is an environment privilege limitation, not a hidden or weakened test.

### CLI startup verification

Command:

```powershell
.\\.venv\\Scripts\\python.exe dev_ai.py
```

Result:

- Exit code: **2**
- Existing behavior was preserved because `OLLAMA_MODEL` is unset.
- The CLI printed the existing Ollama model setup guidance.
- No environment or configuration was changed.

## 6. Remaining Limitations

- Ollama remains the only runtime provider.
- Provider-neutral tool transport exists, but [app/ai/tool_calling.py](../app/ai/tool_calling.py) intentionally retains `OllamaToolCallingService` as the backward-compatible public name.
- Ollama native payload conversion is implemented; providers need their own adapter methods for real provider neutrality.
- Streaming has an interface/fallback but no application streaming consumer.
- Vision is provider-neutral for orchestration, but only the Ollama adapter is implemented.
- The Ollama vision and tool adapters still contain compatibility serialization and parsing, as designed.
- [app/config.py](../app/config.py) still owns Ollama-specific environment configuration.
- No provider-selection environment variable or API was added.
- The provider-neutral factory supports Ollama only in this phase.
- No knowledge store, RAG pipeline, independent API, or cloud deployment was added.

## 7. Actual Veronica Model Status

No actual Veronica language model was implemented or trained.

`VeronicaModelProvider` is only an integration scaffold and reports every capability as false.

It raises `ProviderModelUnavailableError` for text generation and does not perform tool or vision operations.
