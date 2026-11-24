# Veronica - Phase 1A Final Correction Report

## Result

The findings in `PHASE_1A_FINAL_VERIFICATION.md` have been addressed at the
generic application and orchestration boundaries. Ollama remains the default
working provider, but its request formats, model discovery, image encoding, and
legacy text-tool parsing are handled by its adapter. Generic startup and tool
orchestration use provider-neutral contracts.

No Veronica model, inference engine, API, cloud provider, or cloud service was
implemented. No model was downloaded or trained.

## Findings and Disposition

### High: Startup was hard-wired to Ollama

**Status: Addressed.**

- `dev_ai.py` calls `create_provider()` and validates the selected provider
  through `validate_startup()`. It no longer imports or constructs
  `OllamaClient`, selects a provider by a literal name, discovers models, or
  matches Ollama model tags.
- `VERONICA_AI_PROVIDER` selects the provider; its default remains `ollama`.
- `app/ai/provider.py` owns provider construction and registration. The default
  Ollama factory loads existing Ollama settings and imports the implementation
  lazily. Unknown or unregistered names raise `ProviderConfigurationError`.
- `OllamaClient.validate_startup()` owns Ollama model discovery and validation.
  Existing `OLLAMA_MODEL`, `OLLAMA_BASE_URL`, `OLLAMA_TIMEOUT`, and
  `OLLAMA_VISION_MODEL` behavior is preserved.
- Ollama package exports are lazy, preserving legacy imports without loading
  `ollama_client` when generic application startup imports `app.ai`.

### High: Generic tool orchestration implicitly used the Ollama adapter

**Status: Addressed.**

- `ToolCallingService` requires the neutral
  `generate_provider_tool_response()` contract. It raises
  `ProviderCapabilityError` for unsupported providers and never wraps an
  arbitrary object in an Ollama adapter.
- `OllamaLegacyToolCallingService` is the explicit compatibility path for
  legacy Ollama clients. `OllamaToolCallingService` remains available as a
  backward-compatible alias from both `app.ai` and
  `app.ai.tool_calling`.
- Startup reports a clear configuration error if tools are enabled for a
  provider that lacks the tool capability.

### High: Generic orchestration built provider-shaped messages and JSON text

**Status: Addressed.**

- The neutral conversation consists of `ChatMessage`, `AssistantResponse`,
  `ToolCall`, and `ToolResultPayload` values, including typed tool errors.
- The generic tool loop passes these values to the provider and does not
  construct Ollama `"assistant"`/`"tool"` wire messages or JSON-encode results.
- `OllamaClient` performs neutral-to-Ollama conversion and serializes tool
  results only at its adapter boundary.
- Provider-specific legacy text tool requests are parsed in the Ollama adapter
  into neutral `ToolCall` values through the optional `ToolCallTextParser`
  protocol. Generic conversation code does not parse Ollama payloads.
- Tool limits, allowlist checks, registry validation, and safe execution remain
  in `ToolCallingService` and `ToolRegistry`.

### Medium: Vision interface and image validation were insufficient

**Status: Addressed.**

- `VisionRequest.image` is a `PIL.Image.Image` and rejects invalid inputs.
- `VisionProvider` is a structural protocol, so providers need not inherit
  from an Ollama class.
- `LocalVisionService` accepts an explicitly supplied provider and does not
  infer that arbitrary objects are legacy Ollama clients.
- `OllamaClient.create_vision_provider()` supplies the Ollama adapter;
  `LegacyOllamaVisionProvider` remains available for explicit compatibility.
- Ollama image encoding and vision-model configuration remain in the adapter.

### Medium: Model discovery and validation were in CLI startup

**Status: Addressed.** The CLI now calls the provider-neutral
`validate_startup()` method; Ollama owns its model list and model-name matching.

### Low: Base health checks reported success by default

**Status: Addressed.** `AIProvider.health_check()` raises
`ProviderCapabilityError` unless implemented. Ollama performs its model-list
health check; the unimplemented Veronica provider reports unavailable.

### Low: Trailing whitespace at end of `ollama_client.py`

**Status: Addressed.** `git diff --check` passes.

## Architecture and Remaining Boundaries

- Provider selection is configured independently from provider implementation.
  A future provider can register a factory with `register_provider()` without
  changing `dev_ai.py`.
- The future provider must implement the neutral interfaces for each capability
  it actually supports. `VeronicaModelProvider` remains an unregistered
  scaffold and advertises no implemented capabilities.
- Ollama-specific code remains in `app/ai/ollama_client.py`, its explicit
  compatibility module, provider-factory registration/default configuration,
  and legacy exports. This is intentional compatibility coupling; generic
  startup, `AIService`, `ToolCallingService`, and vision orchestration do not
  depend on Ollama payload types or classes.
- `VERONICA_AI_PROVIDER` currently supports registered providers only; there is
  no automatic plugin discovery. A future implementation needs to register its
  factory during its own integration setup.
- Compatibility was verified with the existing automated tests and import
  checks. No live Ollama-server session was used for this correction.

## Files Modified or Created

### Production

- `app/ai/__init__.py` - retained public compatibility exports with lazy Ollama
  imports; exposed neutral interfaces.
- `app/ai/base.py` - provider, tool, conversation, health, and vision contracts.
- `app/ai/ollama_client.py` - Ollama startup/model validation, neutral tool
  serialization, legacy tool parsing, and vision adapter.
- `app/ai/ollama_tool_compat.py` - explicit Ollama legacy tool adapter and alias.
- `app/ai/provider.py` - provider registry, selection, and default Ollama factory.
- `app/ai/veronica_provider.py` - truthful, unimplemented future-provider
  scaffold.
- `app/ai/roles.py` - provider-neutral error handling.
- `app/ai/service.py` - neutral text-tool parser integration and generic
  conversation handling.
- `app/ai/tool_calling.py` - typed provider-neutral tool orchestration.
- `app/ai/vision.py` - structural provider injection and generic vision handling.
- `app/config.py` - independent provider-selection setting and lazy legacy
  Ollama settings.
- `app/tools/screen_understanding.py` - provider-neutral screen-awareness
  descriptions and integration.
- `app/tools/screenshot.py` - provider-neutral screen feature description.
- `dev_ai.py` - provider-factory startup and capability-aware tool setup.

### Tests

- `tests/test_ai.py` - preserve rejection of a disabled legacy web-search call.
- `tests/test_dev_ai.py` - factory-based startup and unsupported-tool capability
  reporting.
- `tests/test_provider_contracts.py` - provider selection/registration,
  capabilities, neutral tool exchange, response validation, vision, and health.
- `tests/test_roles.py` - neutral tool-call handling in role flows.
- `tests/test_screen_understanding.py` - explicit vision compatibility and
  structural-provider behavior.
- `tests/test_screenshot.py` - preserved screen-tool behavior.
- `tests/test_teacher_quality.py` - neutral tool-call handling in teacher
  responses.
- `tests/test_web_search_integration.py` - real Ollama adapter boundary with
  mocked transport, rather than patching removed CLI Ollama imports.

Earlier Phase 1 audit/review documents present as untracked files were not
modified by this correction.

## Verification

Focused command:

```powershell
.\.venv\Scripts\python.exe -m pytest -ra tests\test_ai.py tests\test_roles.py tests\test_teacher_quality.py tests\test_provider_contracts.py tests\test_ai_tool_calling.py tests\test_dev_ai.py
```

Result: **122 passed, 0 failed**.

Full command:

```powershell
.\.venv\Scripts\python.exe -m pytest -ra
```

Result: **356 collected, 355 passed, 1 skipped, 0 failed**.

The skipped test is `tests/test_file_search.py:187`: Windows denied directory
symlink creation with `WinError 1314` because the required privilege is not
available.

Additional checks:

- Fresh-process import check confirmed importing `dev_ai` does not load
  `app.ai.ollama_client`; legacy `from app.ai import OllamaClient` and
  `OllamaToolCallingService` imports, including the prior
  `app.ai.tool_calling` path, still resolve.
- `git diff --check` passed.

## Limitations

- Ollama remains the only provider registered by default and the only complete
  provider implementation.
- No live-server connectivity test was run; Ollama request and compatibility
  behavior remain covered by automated tests.
- Veronica's model, inference, streaming, tools, and vision are not implemented.
