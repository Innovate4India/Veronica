# Veronica - Phase 1 Existing Project Audit

**Audit date:** 2026-11-24
**Repository:** Innovate4India/Veronica
**Scope:** Existing repository only. No production code or configuration was changed.

## 1. Project Overview

Veronica is an in-repository local-first Python assistant scaffold. The real interactive application is [dev_ai.py](../dev_ai.py); [app/main.py](../app/main.py) and [run.py](../run.py) are a separate, incomplete Phase 1 scaffold. The repository currently has no web server, desktop UI, public API, cloud LLM integration, or standalone inference engine.

### Major structure

| Area | Responsibility | Status |
|---|---|---|
| `dev_ai.py` | Interactive CLI, startup checks, command handling, TTS setup, tool and memory assembly | Primary application entry point |
| `app/main.py`, `run.py` | Minimal startup scaffold; writes only an application log message | Scaffold |
| `app/ai/` | Ollama provider, prompt construction, conversation context, role classification, teaching state, tool loop, and vision | Implemented core |
| `app/memory/` | SQLite schema and explicit memory operations | Implemented and tested |
| `app/tools/` | Allowlisted calculator, file search, web search, system information, URL opening, app launch, screenshot, and screen understanding | Most implemented and tested |
| `app/voice/` | Whisper STT, Piper TTS, Microsoft Edge TTS, provider interfaces, diagnostics | Implemented components, with orchestration not fully wired |
| `app/config.py` | Environment parsing and path/model configuration | Implemented |
| `app/core/logger.py` | File and console logging helper | Implemented helper, limited integration |
| `app/security/` | Package marker only | Empty scaffold |
| `app/services/` | Package marker only | Empty scaffold |
| `tests/` | Unit and integration-style unittest/pytest coverage | Extensive |
| `data/` | Whisper/Piper model files and SQLite memory database | Present local assets |
| `logs/` | Runtime/application log output | Present when configured |

### Entry points

- **Interactive application:** `python dev_ai.py`
- **Documented scaffold:** `python run.py`
- **Voice/STT diagnostics:** modules in [app/voice/](../app/voice/)
- **Library entry packages:** [app/ai/__init__.py](../app/ai/__init__.py), [app/voice/__init__.py](../app/voice/__init__.py), [app/tools/__init__.py](../app/tools/__init__.py)

### Unused, duplicate or incomplete components

- [app/main.py](../app/main.py) is not used by `dev_ai.py` and does not start Veronica.
- [app/security/](../app/security/) and [app/services/](../app/services/) contain only package markers.
- [app/voice/service.py](../app/voice/service.py) provides `VoiceService`, but `dev_ai.py` does not call it.
- Piper TTS is implemented, has local models, and has diagnostics, but the conversational CLI does not use it.
- Faster-Whisper STT is implemented and has a tested/diagnosed microphone path, but it is not wired into `dev_ai.py`.
- [app/tools/screenshot.py](../app/tools/screenshot.py) is a metadata-only capture tool. It explicitly reports screen understanding as not implemented, while [app/tools/screen_understanding.py](../app/tools/screen_understanding.py) provides the separate implemented vision path.
- No `pyproject.toml`, `setup.py`, `pytest.ini`, or `tox.ini` exists.

## 2. Existing AI Architecture

### Provider architecture

- `app/ai/base.py`:
  - `AIProvider` is a small abstract interface.
  - `generate_response(messages)` is the provider-neutral text boundary.
- [app/ai/ollama_client.py](../app/ai/ollama_client.py):
  - `OllamaClient` implements `AIProvider`.
  - Calls Ollama `/api/tags` and `/api/chat`.
  - Uses only the Python standard library for HTTP.
  - Enforces loopback HTTP endpoints.
- [app/ai/service.py](../app/ai/service.py):
  - `AIService` owns conversation state, role selection, memory retrieval, prompt assembly, tool selection, retries, and answer validation.
- [app/ai/tool_calling.py](../app/ai/tool_calling.py):
  - `OllamaToolCallingService` orchestrates Ollama-native tool calls and `ToolRegistry`.
- [app/ai/vision.py](../app/ai/vision.py):
  - `LocalVisionService` captures the primary display once and sends it to a separate local Ollama vision model.

### Complete text flow

`User input (`dev_ai.main`)`
→ `_handle_command()` or `AIService.respond()`
→ explicit memory/role/tool intent detection
→ memory retrieval through `MemoryService.search_memories()`
→ system prompt assembly in `AIService.respond()`
→ role classifier in `classify_role()` (for ambiguous turns)
→ either `OllamaClient.generate_response()` or `OllamaToolCallingService.respond()`
→ bounded Ollama HTTP chat request
→ optional `ToolRegistry.execute()` round trips
→ final text validation
→ in-memory conversation history update
→ optional Microsoft Edge TTS
→ CLI output

### Prompt construction

- Base identity: `VERONICA_SYSTEM_PROMPT` in [app/ai/personality.py](../app/ai/personality.py).
- Role instructions: `role_instructions()` in [app/ai/roles.py](../app/ai/roles.py).
- Tool instructions: `_WEB_SEARCH_INSTRUCTIONS` in [app/ai/service.py](../app/ai/service.py).
- Teaching state: `TeachingSession.prompt_context()` in [app/ai/teaching.py](../app/ai/teaching.py).
- Retrieved memories are appended as clearly labeled untrusted facts.
- The current date is dynamically inserted for tool-enabled turns.
- Role classification sends the most recent 10 conversation messages and a separate role-classifier system prompt to Ollama.

### Conversation context

- `AIService._messages` holds a system message plus bounded session messages.
- Default limit: 20 non-system messages, configurable by `MAX_CONVERSATION_MESSAGES`.
- `_record_exchange()` appends user/assistant pairs and removes oldest pairs when over limit.
- `/clear` resets chat and teaching state while retaining the base system prompt.
- Teaching state is process-local and not persisted to SQLite.
- Screen-understanding exchanges are intentionally omitted from retained chat history.

### Ollama dependency and replaceability

There is a reusable provider interface, `AIProvider`, but replacement is **not entirely Ollama-neutral**:

- `OllamaToolCallingService` and tool protocol types are Ollama-specific.
- Vision is coupled to `OllamaClient.generate_vision_response()`.
- Role classification is provider-neutral in method shape but reuses text providers.
- The CLI startup directly validates Ollama endpoints and models.

Thus Ollama can be replaced for ordinary text generation with moderate work, but native tools and vision require an interface redesign rather than a single implementation swap.

## 3. Existing Feature Status

| Feature | Status | Evidence |
|---|---|---|
| AI conversation | **Fully implemented** for local Ollama | AI/tool/CLI test coverage; startup, response, history, and error paths implemented |
| Personality | **Fully implemented** | `VERONICA_SYSTEM_PROMPT` and tests |
| Friend mode | **Fully implemented** | `VeronicaRole.FRIEND`, explicit/guarded classification, tests |
| Teacher mode | **Fully implemented** | Teacher instructions, session state, quality retry, tests |
| Assistant mode | **Fully implemented** | Role instructions and tool routing, tests |
| Persistent memory | **Fully implemented** | Parameterized SQLite service, explicit commands, sensitive-data refusal |
| SQLite database | **Fully implemented** locally | Tables created lazily; database has zero memories on audit |
| ToolRegistry | **Fully implemented** | Schema validation, status types, confirmation support, bounded dispatch |
| Calculator | **Fully implemented** | Safe AST/Decimal implementation, 8 tests |
| File search | **Fully implemented** with Windows/test limits | Read-only bounded search, 11 pass/1 skip |
| System information | **Fully implemented** | Read-only OS/CPU/RAM/Python/disk data, tests |
| Application launcher | **Fully implemented** for allowlisted apps | Fixed and discovered targets, `Popen(..., shell=False)`, tests |
| Web search | **Implemented but opt-in** | Tavily adapter, missing-key and network failure handling; no live key configured |
| Open URL | **Fully implemented** | HTTP/HTTPS validation and default browser, tests |
| Screen awareness | **Partially implemented** | Captures primary display and sends it to a configured local Ollama vision model; live model is not configured |
| Screenshot metadata | **Implemented, interpretation not implemented** | Captures once in memory and reports dimensions |
| Voice recognition | **Partially implemented** | Faster-Whisper implementation exists and model files are present; not wired into `dev_ai.py` |
| Text-to-speech | **Partially implemented** | Microsoft Edge TTS wired into CLI; Piper is implemented but not selected by CLI |
| Configuration | **Fully implemented** | Environment loaders validate values |
| Logging | **Partially implemented** | Standard logger helper exists; registry logs through module logger, but `dev_ai.py` does not initialize `get_logger()` |
| Error handling | **Fully implemented for tested paths** | Typed provider/voice/tool/memory errors and CLI messages |
| Public API / backend server | **Not implemented** | No HTTP server or API framework |
| Desktop/web UI | **Not implemented** | CLI only |

## 4. Dependencies and Environment

### Dependency manifests

The only dependency manifest is [requirements.txt](../requirements.txt). It contains:

- `faster-whisper==1.2.1`
- `numpy==2.5.3`
- `piper-tts==1.8.0`
- `sounddevice==0.5.6`
- `av==19.0.0`
- `edge-tts==7.2.8`
- `Pillow>=11.0.0`

No Ollama Python package is required; Ollama is an external process/API.

### Environment

[.env.example](../.env.example) documents variables but is not loaded automatically. `app/config.py` loads process environment variables only.

No secret values are stored in `.env.example`. Audit-time process-variable presence checks found all of `OLLAMA_MODEL`, `OLLAMA_VISION_MODEL`, `TAVILY_API_KEY`, `MEMORY_DATABASE_PATH`, `WHISPER_DEVICE`, `VOICE_RESPONSES_ENABLED`, and `WEB_SEARCH_ENABLED` unset.

### Runtime and internet needs

| Component | Internet | Ollama | GPU | API key |
|---|---:|---:|---:|---:|
| Text chat | No | Required | CPU/GPU choice belongs to Ollama | No |
| Ollama model startup/list | No | Required | Optional, model/runtime dependent | No |
| Tavily web search | Yes | Text model still required | No direct dependency | Tavily key required |
| Microsoft Edge TTS | Yes | No | No | No Azure key; Edge endpoint |
| Piper TTS | No | No | CPU | No |
| Faster-Whisper STT | No | No | Optional CUDA, CPU default | No |
| Local vision | No | Required | Optional, vision model dependent | No |
| File/system/app/URL tools | No | Required for model-mediated invocation | No | No |

## 5. Database and Memory

- Database implementation: [app/memory/database.py](../app/memory/database.py), `MemoryDatabase`.
- Operations: [app/memory/service.py](../app/memory/service.py), `MemoryService`.
- Default path: `data/veronica_memory.db`.
- Schema: `id`, `content`, `category`, `created_at`, `updated_at`.
- Audit inspection found 0 memories.
- Writes and deletes use parameterized SQL.
- Search is bounded, newest-first, and uses escaped `LIKE` patterns.
- Obvious credentials/private keys are refused.
- SQLite file is not encrypted; it is protected only by operating-system/user permissions.
- Conversation history is process-memory-only and is bounded.
- Teaching progress is process-memory-only and reset by `/clear`.
- Screen-understanding images and results are not saved or retained.

## 6. Test Audit

### Command

```powershell
.\\.venv\\Scripts\\python.exe -m pytest -ra
```

### Results

- **Collected:** 336
- **Passed:** 335
- **Failed:** 0
- **Skipped:** 1
- **Could not run:** None

The skipped test attempts a directory symlink in `tests/test_file_search.py:187`. Windows denied privilege `[WinError 1314]`; it is an environment/permission limitation, not a code failure.

Tests cover AI, tool calling, CLI commands, memory, calculator, file search, app launch, Open URL, role classification, teacher quality, teaching state, screenshots, system information, voice, web search, and Windows app discovery. Most external dependencies are mocked. The integration suite exercises an end-to-end CLI/tool loop but does not call real Ollama, Tavily, or Microsoft TTS.

## 7. Security Findings

### Verified controls

- Ollama URL is restricted to `http://localhost`, `127.0.0.1`, or `::1`; credentials/query/fragment URLs are rejected.
- Calculator uses an AST allowlist and Decimal evaluation; it does not execute arbitrary Python.
- Tool dispatch validates JSON object shape and supported schema keywords.
- Tool loop limits tool calls to four per turn.
- Tool registry records outcome and elapsed time, not parameters/results/exception messages.
- File search is bounded by roots, 10,000 visited entries, 50 results, 2 seconds, sensitive names, and reparse-point checks.
- Web search sends only query/count to fixed Tavily endpoint and ignores body content fetches.
- Application launch uses `shell=False`, fixed system targets, or validated `.exe` discovery.
- SQLite memory operations use parameterized statements.
- Obvious secrets are refused before memory persistence.
- Web search and Microsoft TTS are opt-in.

### Findings

#### Critical

- None identified in the audited code.

#### High

1. **No authentication or authorization boundary.** The CLI is local and intended for one owner, but a future API/UI would currently have no account, session, or authorization mechanism.
2. **Tool allowlisting is opt-in per turn but still model-mediated.** The local model can select tools within a bounded set. This is not a malicious-command execution surface, but prompt injection in web/search or memory content could influence tool selection.

#### Medium

1. **SQLite memory is plaintext.** Anyone with OS-file read access can read stored personal facts.
2. **Database path is unrestricted by the environment.** Relative paths resolve under the project, but a process with modified environment variables can point it elsewhere.
3. **Microsoft TTS sends response text to Microsoft via `edge-tts`.** This is documented and opt-in, but private text can leave the machine.
4. **Tavily receives search queries.** Conversation history is not sent, but search terms may contain personal context.
5. **Screen images are sent to the local Ollama vision model.** They leave application memory but remain on loopback. Future remote providers would change privacy boundaries.
6. **App discovery reads Windows registry and Start Menu metadata.** Reads are limited and targets are validated, but it is a larger local attack surface.
7. **OpenURL can accept IP literals.** It does not fetch or interact, but could ask the browser to open a private/local address.
8. **Logging integration is incomplete.** The logger helper exists, but `dev_ai.py` does not initialize it. Tool logs may not be consistently persisted.

#### Low

1. The current database file is not protected by an application-level permission model.
2. Voice and tool failures return generic exceptions but can vary by platform.
3. No rate limit or resource accounting exists outside individual tool bounds.

## 8. Hardware Assessment

Verified with NVIDIA-SMI:

- Windows 11 Home Single Language 64-bit
- Intel Core i5-13420H
- 8 physical / 12 logical CPUs
- 16 GB RAM
- NVIDIA RTX 3050 Laptop GPU
- 6 GB VRAM
- NVIDIA driver 576.93
- CUDA reported by NVIDIA-SMI 12.9
- Ollama is reachable and currently lists `gemma3:4b` and `llama3.2:latest`

`OLLAMA_MODEL` was not set, so `dev_ai.py` cannot start with a conversational model until it is explicitly configured.

### Suitable workloads

- **Suitable:** 3B-4B quantized Ollama chat models; CPU or GPU Ollama fallback; small vision models with tight quantization; Whisper base or small CPU/local CUDA; TTS; bounded tools.
- **Boundary:** 7B-8B models may fit with 4-5 bit quantization, but KV context and OS/GPU memory sharing reduce usable margin.
- **Not suitable as primary training:** 6 GB VRAM is too constrained for serious full fine-tuning or most large LoRA training stacks.
- **Conservative development:** quantized, parameter-efficient experiments, model adapters, RAG, inference benchmarking, CPU/GPU baseline comparisons.

`CUDA 12.9` is a CUDA compatibility report from NVIDIA-SMI, not proof that every installed Python package has a compatible CUDA runtime. No CUDA-required package is currently assumed active.

## 9. Technical Debt

1. Two entry-point concepts (`run.py` vs `dev_ai.py`) without a coherent application bootstrap.
2. `app/main.py` is a dead scaffold.
3. Ollama is strongly coupled into tool and vision implementations.
4. Native tool parsing and legacy text-envelope parsing live in separate paths.
5. Role classification consumes another model request and therefore can fail ambiguously on provider constraints.
6. Teaching quality is implemented partly as prompt instructions plus post-generation validation/retry.
7. Voice components are extensive but not unified behind the interactive CLI.
8. No API/authentication/server framework.
9. No `pyproject.toml` packaging or declared Python support range.
10. Requirements use a mixture of exact and range pins.
11. No persistent knowledge store or retrieval beyond simple SQLite memory matching.
12. No usage telemetry, model metrics, or provider latency abstraction.
13. Logging helper is underused by startup code.
14. Empty `app/security` and `app/services` folders represent future architecture rather than implemented architecture.
15. Test suite is strong for unit behavior but depends heavily on mocks for external services and real devices.

## 10. Independent AI Readiness

### Reusable

- `AIProvider`/`AIProviderError` interface
- `ChatMessage` shape
- `AIService` conversation and memory orchestration
- Personality and role behavior
- Teaching session state
- Tool base contracts and `ToolRegistry`
- Memory database and CRUD operations
- CLI commands
- Voice provider interfaces
- Configuration loaders
- Guarded tool implementations
- Test suite patterns

### Needs modification

- Replace `OllamaClient` while preserving `AIProvider.generate_response()`.
- Redesign `OllamaToolCallingService` into a provider-neutral tool-execution orchestrator.
- Replace Ollama-specific `OllamaChatMessage` and native tool-call payload types.
- Separate vision input and provider/model selection from Ollama.
- Move Ollama model availability checks out of `dev_ai.py`.
- Abstract provider streaming, retries, cancellation, tokens, latency, and health.
- Add a model-independent answer-generation contract that supports streaming and tools.

### What should be isolated

- Model serving/runtime
- Tokenization and context construction
- Provider adapters
- Knowledge retrieval
- Persistent memory
- Tool execution
- Voice input/output
- Local/cloud deployment
- Desktop/web transport

### Safest migration strategy

1. Introduce a provider-neutral `ModelProvider` interface with chat, streamed chat, tool-call, and optional vision capabilities.
2. Keep `OllamaProvider` as the compatibility adapter.
3. Move provider/tool loops behind `AIService`; do not embed provider payloads in application features.
4. Add capability declarations (`chat`, `tools`, `vision`, `streaming`) instead of provider-specific branches.
5. Add an integration test harness with a fake provider.
6. Implement Veronica model provider as a second adapter with feature flags.
7. Run Ollama and Veronica providers side by side; shadow mode before replacement.
8. Preserve memory, personality, roles, tools, and voice contracts.
9. Remove Ollama only after parity tests and migration fallback criteria are met.

## 11. Recommended Migration Roadmap

### Phase 1A: Stabilize provider boundary

- Create provider-neutral chat/tool/vision contracts.
- Move startup model discovery behind a provider factory.
- Add structured provider metadata and health checks.
- Add a single configuration-driven provider selection.

### Phase 1B: Knowledge and memory separation

- Separate memory storage from semantic retrieval.
- Introduce embedding/retrieval interfaces.
- Encrypt secrets and sensitive database fields if they are expanded in scope.
- Add retention and deletion policies.

### Phase 1C: API and backend

- Add a local API server boundary.
- Add authentication for any non-loopback deployment.
- Move CLI into a thin transport/client layer.
- Add request limits and cancellation.

### Phase 1D: Independent model integration

- Define model serving formats and runtime adapters.
- Add quantized local inference.
- Add fallback routing: Veronica local -> Ollama compatibility -> cloud provider.
- Add shadow and canary evaluation.

### Phase 1E: Platforms

- Add desktop packaging only after API/process separation.
- Add web UI only after authentication and remote security.

## 12. Prioritized Issues

### Critical

- None found.

### High

1. No authentication/authorization for future API or remote use.
2. Ollama and native tool/vision APIs are too tightly coupled for a safe independent-model migration.
3. No complete API/backend or deployment boundary exists for desktop/web/cloud goals.

### Medium

1. Persistent memory database is plaintext.
2. Speech/STT orchestration is not wired into the primary CLI.
3. `OLLAMA_MODEL` is not configured in the process environment.
4. Screen awareness is constrained to Ollama vision and not live-configured.
5. Microsoft TTS can send text externally when enabled.
6. Tavily can receive search queries when enabled.
7. Logger initialization and persistent tool/CLI logs are incomplete.
8. The repository lacks packaging metadata and a Python support declaration.

### Low

1. Duplicate entry-point concepts need consolidation.
2. Empty `app/security` and `app/services` packages should be removed or given concrete implementations during future phases.
3. Requirements and model assets should be documented with version/size/hardware guidance.
4. Add end-to-end tests with real Ollama, Whisper, Piper, and TTS in opt-in test environments.
