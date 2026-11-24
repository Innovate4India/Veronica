# Veronica - Phase 1A Independent Approval Audit

**Review type:** Read-only independent audit
**Verdict:** **APPROVED**
**Scope:** Current provider selection, application/orchestration boundaries,
Ollama compatibility, vision, capabilities, tests, and the two supplied reports.

## 1. Verdict

All three High-priority findings in
`PHASE_1A_FINAL_VERIFICATION.md` are resolved in source:

1. Generic startup selects and validates a provider through the factory and
   contains no Ollama imports, construction, or model-name parsing.
2. Generic tool orchestration rejects providers without the neutral tool
   contract; only the explicitly selected Ollama compatibility adapter uses
   Ollama serialization.
3. Generic tool orchestration exchanges typed neutral conversation and result
   objects; Ollama wire conversion and JSON serialization are in the Ollama
   adapter.

The approval is for the provider-independent application and orchestration
boundaries, not for having multiple implemented providers. Ollama remains the
only complete provider and the default. Ollama-specific implementation,
configuration, default registration, and explicitly requested compatibility
exports remain intentionally present.

## 2. Provider-Independent Startup

### Verified

- `dev_ai.py` imports `create_provider` and generic contracts, not
  `OllamaClient` or an Ollama config loader. `_create_provider()` delegates to
  `create_provider()` and `main()` calls `provider.validate_startup()`
  ([`dev_ai.py:8-22,58-59,222-223`](../dev_ai.py)).
- `load_provider_selection_config()` reads `VERONICA_AI_PROVIDER` and defaults
  it to `ollama` ([`app/config.py:167-174`](../app/config.py)).
- The factory registers Ollama as the default implementation, imports its
  implementation inside `_create_ollama_provider()`, supports other registered
  factories, and raises a clear `ProviderConfigurationError` for unknown names
  ([`app/ai/provider.py:12-55`](../app/ai/provider.py)).
- Ollama model discovery and name matching are owned by the adapter:
  `OllamaClient.list_models()`, `validate_startup()`, and
  `_model_is_installed()` ([`app/ai/ollama_client.py:258-274,289-301,627-632`](../app/ai/ollama_client.py)).
  Generic startup does not parse model tags or load Ollama-specific setup
  instructions.
- `app.ai` uses lazy attribute resolution for legacy Ollama exports; importing
  generic application startup does not itself import `ollama_client`
  ([`app/ai/__init__.py:99-126`](../app/ai/__init__.py)).
- `register_provider()` was exercised in a fresh process with a fake
  non-Ollama `AIProvider`; the fake was created through `create_provider()`
  without loading `app.ai.ollama_client`.

### Import-boundary result

A fresh process verified, in order:

1. Importing `dev_ai` leaves `app.ai.ollama_client` absent from
   `sys.modules`.
2. Registering and creating a fake non-Ollama provider succeeds and still
   leaves that module absent.
3. Importing `OllamaClient` and `OllamaToolCallingService` from `app.ai` loads
   the legacy exports successfully.
4. Importing `OllamaToolCallingService` from `app.ai.tool_calling` also resolves
   to the compatibility service.

**Result: PASS.**

## 3. Tool Orchestration and Conversation Transport

### Verified

- `ToolCallingService` checks for
  `generate_provider_tool_response()` and raises
  `ProviderCapabilityError` if it is missing; there is no automatic
  `OllamaToolAdapter` fallback ([`app/ai/tool_calling.py:39-56`](../app/ai/tool_calling.py)).
- The Ollama legacy path is explicit in
  `OllamaLegacyToolCallingService`; the historical
  `OllamaToolCallingService` alias remains available ([`app/ai/ollama_tool_compat.py:1-25`](../app/ai/ollama_tool_compat.py)).
  The package-level and old module-level exports are lazy compatibility paths
  ([`app/ai/__init__.py:119-126`](../app/ai/__init__.py),
  [`app/ai/tool_calling.py:266-270`](../app/ai/tool_calling.py)).
- Generic conversation values are `ChatMessage`, `AssistantResponse`,
  `ToolCall`, and `ToolResultPayload`; tool failures use
  `ToolErrorPayload` ([`app/ai/base.py:12-79`](../app/ai/base.py)).
- The generic loop passes these values to the neutral provider method and
  appends typed assistant and tool-result objects
  ([`app/ai/tool_calling.py:71-153,230-255`](../app/ai/tool_calling.py)).
  It does not construct provider `"assistant"`/`"tool"` wire messages or
  JSON-encode tool results.
- Ollama performs conversion at the adapter boundary:
  `generate_provider_tool_response()`, `_to_ollama_messages()`,
  `_to_ollama_tool_definition()`, and
  `_normalize_ollama_assistant_response()`
  ([`app/ai/ollama_client.py:475-484,635-713,715-733`](../app/ai/ollama_client.py)).
  The adapter serializes tool-result payloads there
  ([`app/ai/ollama_client.py:667-683`](../app/ai/ollama_client.py)).
- The optional `ToolCallTextParser` protocol is provider-neutral;
  `OllamaClient` implements it and contains legacy envelope parsing
  ([`app/ai/base.py:40-45`](../app/ai/base.py),
  [`app/ai/ollama_client.py:486-488,743-770`](../app/ai/ollama_client.py)).
- The maximum tool-call count remains enforced in
  `ToolCallingService.respond()`; calls still go through `ToolRegistry.execute()`
  ([`app/ai/tool_calling.py:38-40,102-153`](../app/ai/tool_calling.py);
  [`app/tools/registry.py:66-128`](../app/tools/registry.py)). This preserves
  registration, confirmation, JSON/schema validation, and execution outcome
  handling.
- Invalid provider response types and malformed tool calls are rejected by the
  generic normalizer ([`app/ai/tool_calling.py:195-228`](../app/ai/tool_calling.py)).

### Hidden-coupling search

The generic application/orchestration search covered `dev_ai.py`, `app/ai/`,
and `app/tools/` for Ollama classes/configuration, Ollama wire roles, JSON
serialization, and response-shape names.

- `dev_ai.py`, `AIService`, `ToolCallingService`, `LocalVisionService`, and
  screen-awareness tools contain no direct Ollama implementation or payload
  dependency.
- `AIService` constructs ordinary `ChatMessage` role/content values
  ([`app/ai/service.py:310-322`](../app/ai/service.py)); these are the declared
  neutral text contract, not Ollama wire messages.
- Provider-specific `role="tool"` and tool-result JSON serialization occur only
  in `app/ai/ollama_client.py`.
- `roles.py` uses JSON parsing for Veronica role-classifier output; this is not
  Ollama tool transport.

## 4. Vision Independence

- `VisionRequest.image` is typed as `PIL.Image.Image` and runtime-validated;
  invalid image objects raise `TypeError` ([`app/ai/base.py:175-188`](../app/ai/base.py)).
- `VisionProvider` is a runtime-checkable structural protocol
  ([`app/ai/base.py:196-210`](../app/ai/base.py)).
- `LocalVisionService` accepts an injected structural provider and rejects an
  arbitrary object; it does not wrap non-providers as Ollama clients
  ([`app/ai/vision.py:15-24`](../app/ai/vision.py)).
- Ollama vision model selection, image encoding, and Ollama request construction
  are in the Ollama adapter ([`app/ai/ollama_client.py:303-304,345-405,511-600`](../app/ai/ollama_client.py)).
- Screen-understanding uses the configured local vision provider and retains
  its explicit-capture and input-validation behavior
  ([`app/tools/screen_understanding.py:30-78`](../app/tools/screen_understanding.py)).
  Existing screen-understanding and screenshot tests passed.

**Result: PASS.**

## 5. Health and Capability Contracts

- The base `AIProvider.health_check()` raises
  `ProviderCapabilityError`, rather than returning success by default
  ([`app/ai/base.py:152-156`](../app/ai/base.py)).
- `VeronicaModelProvider` reports false for text, streaming, tools, and vision;
  health returns unavailable and text/stream generation raises
  `ProviderModelUnavailableError`
  ([`app/ai/veronica_provider.py:14-50`](../app/ai/veronica_provider.py)).
- `OllamaClient` advertises text/tools/vision and not streaming, matching its
  implemented entry points ([`app/ai/ollama_client.py:167-184,277-304,475-489`](../app/ai/ollama_client.py)).
- Unsupported tool support is reported with the provider-neutral
  `ProviderCapabilityError`; the CLI translates this into a clear startup
  error ([`app/ai/tool_calling.py:49-55`](../app/ai/tool_calling.py);
  [`dev_ai.py:262-273`](../dev_ai.py)).
- Contract tests cover Ollama and Veronica capability declarations and the
  base health-check default ([`tests/test_provider_contracts.py:155-183,306-321`](../tests/test_provider_contracts.py)).

**Result: PASS.**

## 6. Backward Compatibility and Test Integrity

- `OllamaClient`, Ollama response/error names, vision adapters, and tool adapter
  remain accessible through lazy public exports
  ([`app/ai/__init__.py:58-126`](../app/ai/__init__.py)).
- `OllamaToolCallingService` remains available from both historical import
  locations. The explicit legacy adapter test verifies the old tool response
  flow ([`tests/test_provider_contracts.py:201-221`](../tests/test_provider_contracts.py)).
- Ollama request generation and tool/vision conversion remain implemented in
  the adapter; web-search integration tests now patch the provider factory and
  use an `OllamaClient` with mocked transport
  ([`tests/test_web_search_integration.py:79-112`](../tests/test_web_search_integration.py)).
- No existing test function was deleted, and the test diff introduces no new
  skip or xfail markers. Test edits adapt startup/vision tests to the neutral
  boundaries; the screen-image cleanup assertions remain present using a real
  PIL image and a wrapped close method. The suite's one skip is the existing
  Windows symlink-privilege case.

## 7. Test and Independent Check Results

Command run:

```powershell
.\.venv\Scripts\python.exe -m pytest -ra
```

Result: **356 collected, 355 passed, 1 skipped, 0 failed**.

The skipped test is `tests/test_file_search.py:187`, where Windows denied
directory symlink creation with `WinError 1314`; this is an environment
privilege limitation, not a Phase 1A test skip.

`git diff --check`: **passed**.

Fresh-process import and fake-registration test: **passed** (details in §2).

## 8. Correction Report Accuracy and Remaining Ollama References

The correction report's architectural claims were confirmed against source,
except that statements about whether a model was downloaded or trained before
this read-only audit cannot be retrospectively established from source code.
No training/download mechanism was found or run as part of this audit. Its
reported test result matches the independent run.

Remaining Ollama references are classified as follows:

| Location | Reference | Classification |
|---|---|---|
| `app/ai/provider.py:24-35` | Lazy `OllamaClient` construction and default `"ollama"` registration | Factory registration/default, intentional |
| `app/config.py:17-20,145-182,398-407` | Ollama config loaders and legacy environment exports; `VERONICA_AI_PROVIDER` selection | Provider configuration and backward compatibility |
| `app/ai/ollama_client.py:1-770` | Ollama API payloads, roles, JSON wire serialization, model validation, vision encoding, and response parsing | Intentional adapter implementation |
| `app/ai/ollama_tool_compat.py:1-25` | Explicit wrapper around `OllamaToolAdapter` | Explicit backward compatibility |
| `app/ai/__init__.py:58-126` | Lazy names for historical Ollama public exports | Explicit backward compatibility |
| `app/ai/tool_calling.py:266-270` | Lazy old module-level `OllamaToolCallingService` export | Explicit backward compatibility |

No genuine Ollama-specific coupling was found in generic startup, generic
conversation/tool orchestration, vision orchestration, or screen-awareness
tools. The remaining factory default and compatibility paths are explicit and
do not make a future provider pass through Ollama serialization.

## 9. Future Provider Integration and Limitations

A future Veronica-native provider can register a factory through
`register_provider()` and implement the provider-neutral contracts without
modifying `dev_ai.py`, `AIService`, or `ToolCallingService`. It must implement
only capabilities it can actually perform. The Veronica scaffold is not
registered and does not claim unsupported capabilities.

Limitations:

- Ollama is still the only complete provider and the configured default.
- Provider registration is explicit; automatic plugin discovery is not
  implemented.
- No live Ollama server was contacted in this audit. Existing compatibility is
  verified by unit and integration tests using mocked transport.
- No actual Veronica inference engine, model, streaming implementation, or
  vision implementation exists.
