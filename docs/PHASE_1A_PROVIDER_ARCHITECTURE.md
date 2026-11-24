# Veronica - Phase 1A Provider-Independent Architecture

**Date:** 2026-11-24
**Scope:** Prepare the existing application for a future Veronica-owned model while preserving Ollama compatibility.

## Architecture Changes

### Provider-neutral contracts

[app/ai/base.py](../app/ai/base.py) now contains the application-facing provider contracts:

- `ChatMessage` for text conversations
- `ToolCall` and `AssistantResponse` for provider-neutral tool responses
- `ToolDefinition` for provider-neutral function/tool schemas
- `ProviderCapabilities` for text, streaming, tools, and vision support
- `ProviderMetadata` for provider name, provider kind, model, and capabilities
- `ProviderError` and typed provider configuration, connection, timeout, response, and model-unavailable failures
- `AIProvider` with text generation, streaming fallback, health checks, model listing, and metadata

`AIProvider.generate_stream()` has a compatibility fallback that yields one complete text response. Providers can override it with real streaming later.

### Ollama compatibility

[app/ai/ollama_client.py](../app/ai/ollama_client.py) remains the Ollama implementation and is now also an adapter with:

- Ollama metadata
- Ollama capabilities
- Existing `/api/tags` and `/api/chat` behavior
- Existing loopback URL validation
- Existing model configuration behavior
- Legacy exception names as Ollama compatibility classes
- Provider-neutral typed error inheritance

Ollama-specific wire formats remain in the Ollama client. Core tool orchestration no longer imports Ollama chat/tool classes.

### Provider factory

[app/ai/provider.py](../app/ai/provider.py) provides the public `create_provider()` selector and a private `_create_ollama_provider()` factory.

The factory currently registers only:

- `ollama`

Unknown providers are rejected, avoiding accidental external-provider integration.

### Future Veronica-owned model boundary

[app/ai/veronica_provider.py](../app/ai/veronica_provider.py) provides `VeronicaModelProvider`.

It:

- Implements the provider-neutral `AIProvider` interface
- Advertises no implemented capabilities; text, streaming, tools, and vision are all disabled in its metadata
- Does not call Ollama
- Does not call external APIs
- Does not load or train a model
- Reports unavailable status and raises `ProviderModelUnavailableError` if generation is attempted

This establishes the integration boundary for a later local inference engine.

### Tool orchestration

[app/ai/tool_calling.py](../app/ai/tool_calling.py) now internally normalizes provider responses into neutral `AssistantResponse` and `ToolCall` values.

It also:

- Retains `OllamaToolCallingService` as the compatibility name
- Keeps native Ollama payload translation in the Ollama adapter
- Keeps four-call tool limits
- Keeps allowlist and schema enforcement in `ToolRegistry`
- Keeps legacy web-search envelope rejection
- Works with fake provider-neutral tool responses

### Vision

[app/ai/vision.py](../app/ai/vision.py) no longer imports Ollama-specific provider classes.

It now catches provider-neutral connection, timeout, and model-unavailable errors. `OllamaClient` remains the actual vision implementation adapter, while a future provider can implement the same client capability without Ollama imports in vision orchestration.

### Conversation and role handling

[app/ai/service.py](../app/ai/service.py) continues to own:

- Conversation history
- Memory retrieval
- Role selection
- Prompt assembly
- Teaching state
- Tool routing
- Response validation

Provider-neutral and Ollama-specific exceptions are both handled as provider failures.

[app/ai/roles.py](../app/ai/roles.py) now accepts provider-neutral or legacy provider failures and safely falls back to Assistant role classification.

## Files Created

- [app/ai/provider.py](../app/ai/provider.py)
- [app/ai/veronica_provider.py](../app/ai/veronica_provider.py)
- [tests/test_provider_contracts.py](../tests/test_provider_contracts.py)
- [docs/PHASE_1A_PROVIDER_ARCHITECTURE.md](PHASE_1A_PROVIDER_ARCHITECTURE.md)

## Files Modified

- [app/ai/base.py](../app/ai/base.py)
- [app/ai/__init__.py](../app/ai/__init__.py)
- [app/ai/ollama_client.py](../app/ai/ollama_client.py)
- [app/ai/service.py](../app/ai/service.py)
- [app/ai/tool_calling.py](../app/ai/tool_calling.py)
- [app/ai/vision.py](../app/ai/vision.py)
- [app/ai/roles.py](../app/ai/roles.py)

## Provider Interface Design

### Required text path

```python
provider.generate_response(messages)
```

### Future streaming path

```python
for chunk in provider.generate_stream(messages):
    ...
```

Providers that do not implement streaming inherit a one-chunk fallback.

### Health and model discovery

```python
provider.health_check()
provider.list_models()
provider.metadata
```

### Tool path

```python
provider.generate_provider_tool_response(neutral_messages, tool_definitions)
```

The generic tool orchestration uses provider-neutral conversation and response values. `OllamaClient.generate_provider_tool_response()` translates those values through Ollama-specific `generate_tool_response()` serialization inside the Ollama adapter.

### Vision path

Future providers implement vision through a provider-owned vision method and are invoked through `LocalVisionService`. The application should continue to capture and close the transient image at the orchestration boundary.

## Ollama Compatibility Status

The following compatibility observations describe the original Phase 1A work and its test runs; they are not verification of the current worktree.

- Existing Ollama client exceptions remain available.
- Existing `OllamaAssistantResponse`, `OllamaToolCall`, and Ollama tool definitions remain available.
- Existing native Ollama tool-call payload behavior remains unchanged.
- CLI startup now selects the configured provider through `create_provider()` and delegates startup/model validation to that provider. Ollama remains the default, and its model checks remain inside the Ollama adapter.
- The original Phase 1A focused and complete runs reported passing conversation, role, memory, tool, voice, and vision tests; their run-specific totals are retained below.
- Ollama remains the only complete registered provider; provider selection does not imply that another provider is implemented.

During the original Phase 1A check, `OLLAMA_MODEL` was unset in the process environment; `python dev_ai.py` exited with code 2 and printed the then-current model-configuration guidance. No configuration was changed.

## Future Veronica Model Integration Process

1. Implement `VeronicaModelProvider` with tokenization and model loading.
2. Implement text generation and `generate_stream()`.
3. Implement provider-owned context-window construction.
4. Implement provider-specific tool-call parsing and transport behind the provider contract; keep wire serialization out of generic orchestration.
5. Implement vision if the selected model supports image input.
6. Implement real `health_check()` and `list_models()`.
7. Use the existing provider selection and factory for a future provider only after that provider is separately implemented and approved; keep Ollama as the default until explicit release approval.
8. Add shadow/canary tests comparing Ollama and Veronica responses.
9. Preserve memory, role, tool, voice, and CLI contracts.
10. Remove Ollama dependencies only after independent-provider parity is demonstrated.

The future provider can run without Ollama or any external AI API if its inference and tool implementation remain local.

## Test Results

Later reviews recorded different totals for separate runs; see the [Phase 1A final verification](PHASE_1A_FINAL_VERIFICATION.md) and [Phase 1A independent approval audit](PHASE_1A_INDEPENDENT_APPROVAL_AUDIT.md). Do not combine these run-specific counts or present any as current verification.

### New focused tests

Targeted provider/AI/tool/CLI/vision run:

- **89 passed**
- **48 subtests passed**
- **0 failed**

### Complete suite

Command:

```powershell
.\\.venv\\Scripts\\python.exe -m pytest -ra
```

- **343 collected**
- **342 passed**
- **1 skipped**
- **0 failed**

The skip is the existing Windows symlink test:

- `tests/test_file_search.py:187`
- `[WinError 1314]` because symlink creation privilege is unavailable

No test or production behavior was modified to force the result.

The original Phase 1A CLI verification exited with code 2 because `OLLAMA_MODEL` was unset at that time. It preserved the then-current configuration guidance and did not alter environment or configuration.

## Remaining Limitations

- The application CLI uses the provider factory and provider-owned startup validation. Ollama remains the only complete registered/default provider.
- Generic tool orchestration uses neutral contracts; Ollama wire conversion remains in the Ollama adapter and explicit legacy compatibility path.
- Ollama vision remains the only implemented vision provider.
- Streaming is future-ready but Ollama currently reports streaming disabled.
- `VeronicaModelProvider` is an unimplemented integration scaffold, not an inference engine.
- Knowledge retrieval, embeddings, RAG, and a knowledge store are not implemented.
- No web/API, desktop UI, cloud server, authentication, or independent model runtime was added.
- No model was downloaded, trained, or installed.
