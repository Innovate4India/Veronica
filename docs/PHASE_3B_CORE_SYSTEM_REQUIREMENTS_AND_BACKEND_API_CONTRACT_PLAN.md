# Phase 3B: Core System Requirements and Backend/API Contract Plan

**Status:** Planning only. This document does not authorize implementation, dependency changes, API exposure, data access, or provider changes.

## 1. Purpose, status labels, and governing constraints

This plan turns the Phase 3A target architecture into requirements and a proposed backend/API contract. It is not a description of a running backend: the repository has no HTTP API server, account/authentication system, or native text-answer engine.

The long-term target is for Veronica to own and control its backend, API, intelligence, knowledge, memory, storage, and desktop/web interfaces. In native target mode, Veronica's own model generates every final AI answer; external AI services are not permanent answer-generation dependencies.

The following labels are used throughout:

- **Existing — verified:** observed in the inspected source, configuration, or tests.
- **Proposed:** a design requirement or contract for possible future implementation.
- **Pending:** requires a user, legal/privacy, security, or technical decision.
- **Unauthorized:** expressly outside the scope of this planning task.

The current Ollama provider remains operational and the development default until Veronica's native model passes independent implementation, testing, and explicit replacement approval gates. Phase 2G D-01 approves only the objective of a controlled tokenizer comparison; it does not authorize an experiment. D-02 through D-18 remain pending, and the tokenizer experiment gate remains **NOT AUTHORIZED**.

English, Hindi (Devanagari), and Hinglish (Roman Hindi and code-switching) are co-equal priorities. Mixed-script text has a separate evaluation group. No single aggregate metric may hide a weak result for any group.

## 2. Verified project baseline

### Existing architecture and behavior

| Component | Existing — verified | Reuse boundary and limitation |
|---|---|---|
| Provider contracts | `app/ai/base.py` defines `AIProvider`, `ChatMessage`, `AssistantResponse`, provider capabilities/metadata, typed errors, and neutral tool/vision contracts. | Reuse the contract and adapter pattern. It is not an HTTP API or an implemented native brain. |
| Provider selection | `app/ai/provider.py` registers Ollama and defaults to it through `VERONICA_AI_PROVIDER`. | Do not change the default or remove Ollama in this plan. Provider selection is currently configuration-based, not an authenticated user-facing API. |
| Ollama | `OllamaClient` is the complete current text-answer provider; it validates a loopback HTTP base URL and talks to a local Ollama service. | Keep it working as the current development provider. Do not make an external answer service a silent fallback in native mode. |
| Veronica model provider | `VeronicaModelProvider` is a scaffold, reports no text/streaming/tools/vision capability, returns unhealthy, and raises a model-unavailable error. | Never describe it as a working model. Any future capability must be implemented and tested before it is advertised. |
| Application service | `AIService.respond()` accepts user text, maintains a bounded in-process message history, handles explicit natural-language memory requests, retrieves matching memories, and invokes a provider and optional tool service. | Reuse this application behavior through a composition/use-case boundary. It is currently a synchronous service and is not a request handler, persistent conversation store, or multi-user service. |
| CLI | `dev_ai.py` constructs the provider, memory service, optional tools and speech component, then owns the interactive loop. `run.py` calls the minimal `app.main` scaffold instead. | Preserve `dev_ai.py` as a local client. A future backend must not silently change its interaction or require a running HTTP server for ordinary local use. |
| Memory | `MemoryDatabase` creates a local SQLite `memories` table and opens short-lived connections. `MemoryService` supports add/list/search/delete/clear and rejects obvious credential patterns. | Reuse for the current single-user local memory scope. It has no identity/tenant isolation, migration framework, retention policy, authenticated API, or comprehensive sensitive-data classifier. |
| Tool system | `ToolRegistry` is instance-scoped, allowlisted, schema-validates parameters, bounds tool-call loops elsewhere, requires confirmation for tools configured to require it, and avoids logging arguments/results. | Keep authorization and execution server-side. An AI tool request is never an authorization decision. |
| Configuration | `app/config.py` reads environment-backed provider, memory, and optional feature settings. `.env.example` documents local paths and defaults; the example is not automatically loaded. | Extend only after deployment and secret-handling decisions. Do not put credentials in the future API schema or prompts. |
| Knowledge | Optional web search is disabled by default; local file search returns names/metadata only. There is no general knowledge-ingestion/indexing service. | A knowledge API must not be confused with memory or with permission to ingest sources. |
| Speech/network | Local Whisper/Piper paths use preinstalled local assets; Microsoft Neural TTS is online and opt-in. Tavily search is an optional remote search tool. | Report and gate egress separately. These speech/search paths do not replace the answer-generating brain. |
| Dependencies | `requirements.txt` has speech/media dependencies and Pillow, but no FastAPI/ASGI server or authentication library. | FastAPI would be a dependency addition requiring separate review and approval; no package is installed or selected here. |

### Existing tests reviewed

- `tests/test_provider_contracts.py` verifies fake providers, Ollama as the default, provider registration/errors, advertised capability accuracy, and the nonfunctional native-provider scaffold.
- `tests/test_memory.py` verifies SQLite memory operations, parameterized search, credential-pattern rejection, explicit memory intent, limited retrieval, and no provider call for explicit memory handling.
- `tests/test_tools.py` and `tests/test_ai_tool_calling.py` verify allowlisting, schemas, confirmation, bounded tool dispatch, and safe outcomes.
- `tests/test_dev_ai.py` verifies CLI commands, provider startup/error reporting, and preservation of local memory interactions.
- `tests/test_web_search_integration.py` exercises optional search in the normal CLI path.

These are not API/server, authentication, multi-tenant, remote deployment, or API-contract tests. No tests were run for this documentation-only task.

## 3. Backend architecture requirements

The future backend is the shared application boundary for approved clients. It must not place business logic, persistence, tool execution, or provider-specific wire formats directly in HTTP route functions.

### Proposed layers

1. **Client adapters:** CLI, desktop, web, and authorized external applications. Clients submit user intent and render validated responses; they do not hold privileged database or provider access.
2. **Transport/API layer:** routing, versioning, request/response schema validation, status codes, request IDs, content limits, and OpenAPI documentation if FastAPI is selected.
3. **Authentication and authorization:** resolve a principal, verify permissions/scopes for each operation and resource, apply quotas, and produce auditable decisions. This is not present today.
4. **Application/use-case layer:** orchestrate one chat turn, conversation lifecycle, memory operations, knowledge search, model metadata, and health queries. It reuses existing services through explicit dependencies.
5. **Policy layer:** decide whether approved memory/knowledge may be included, which tools can run, whether confirmation is required, and whether online egress is permitted. Model output cannot grant itself access.
6. **Domain contracts:** provider-neutral AI, memory, knowledge, identity, permission, and repository interfaces. Provider-specific formats stay in adapters.
7. **Infrastructure adapters:** current SQLite memory adapter, local Ollama adapter, future local Veronica inference adapter, approved retrieval index, secret provider, and optional online search adapter.
8. **Operational boundary:** startup/readiness, shutdown, bounded queues, cancellation/timeouts, structured redacted logs, resource limits, backup and recovery. No general operational service currently exists.

### Process and request handling

- Start with one local service process and one configured model worker unless measured resource and fault-isolation needs justify a separate inference process.
- Use bounded request sizes, output limits, timeouts, cancellation, and concurrency controls. Limits must be measured and approved; this plan invents no numeric thresholds.
- Avoid multiple web workers that each load a full model into limited RAM/VRAM without an explicit resource plan.
- Treat provider, database, online search, and tool failures as explicit errors. Do not report a successful answer when generation failed.
- Startup must report readiness truthfully: a live HTTP process is not proof that the selected model is ready.
- Do not write full prompts, memory contents, secrets, or raw tool arguments/results to ordinary logs.

## 4. FastAPI evaluation

**Recommendation:** FastAPI is a strong candidate for a future Python HTTP API, subject to a separate framework/dependency decision. This recommendation is advisory, not approval to add or install it.

| Consideration | FastAPI fit | Requirement or trade-off |
|---|---|---|
| Existing language/runtime | Fits the Python application and type-annotated service boundary. | Verify supported Python versions, transitive dependency compatibility, license, security posture, and packaging in the actual deployment environment before selection. |
| Request contracts | Typed request/response models can validate JSON and produce an OpenAPI description. | Keep schemas stable and client-neutral; do not make Python type names the only API contract. Reject unknown or invalid fields where appropriate. |
| Async server model | ASGI supports concurrent network I/O and standard middleware patterns. | Existing `AIService`, SQLite access, Ollama client, and inference calls are synchronous. Never block the event loop with long generation or blocking I/O; choose sync route execution or a bounded worker/thread/process strategy and test cancellation. |
| Documentation/testing | Automatic schema generation and a test client can support contract tests. | OpenAPI output does not provide authentication, authorization, privacy, rate limiting, or secure deployment automatically. |
| Runtime resources | A single ASGI process can host a local API. | Model memory, CPU/GPU concurrency, worker count, and process lifetime need measurement. Avoid multiplying model memory by launching unbounded workers. |
| Dependency/security | It is not currently in `requirements.txt`. | Any addition needs reviewed versions, lock/reproducibility policy, vulnerability/update process, and explicit implementation approval. No install or version selection occurs in this phase. |

Starlette or Flask could also be evaluated; a minimal standard-library HTTP server is not recommended as the long-term public contract boundary because it would require Veronica to build more validation, documentation, middleware, and operational behavior itself. No framework is approved or installed.

## 5. Proposed API contract

The routes and JSON below are a planning contract. They do not exist. Paths are proposed under `/api/v1`; the actual transport, server, OpenAPI file, and compatibility policy require approval.

### 5.1 Common protocol rules

- JSON request/response bodies use UTF-8. Preserve user text as supplied; reject empty/whitespace-only chat input but do not silently normalize Unicode or transliterate scripts.
- Use opaque resource IDs and UTC timestamps in a documented ISO-8601 form. Do not place prompts, memory text, credentials, or search queries in URL paths or query strings when they can be in a protected request body.
- Use `Authorization: Bearer <credential>` for authenticated routes once a credential mechanism is approved. Never accept credentials in query parameters.
- Apply server-configured body, message, result, and generation limits. Publish applicable capabilities/limits; never trust a client-supplied limit to exceed server policy.
- Request fields are validated by schema and by application policy. Model/provider-specific settings are not exposed unless supported and bounded across the selected provider.
- The default conversation retention is **ephemeral**. The baseline contract does not create a durable transcript archive. Persistent conversation history requires a separate privacy/retention decision.
- Memory and knowledge context are off unless the user has explicitly enabled the corresponding approved behavior and the caller has the required scope.
- Tools are disabled unless explicitly requested for that turn, authorized by the backend, and permitted by policy. Tool arguments are never trusted merely because they passed model generation.
- No request causes data acquisition, source ingestion, tokenizer fitting, training, or provider replacement.

### 5.2 Chat and answer generation

**`POST /api/v1/chat`** — generate one answer, optionally continuing an active ephemeral conversation.

Required scope: `chat:generate`; if a conversation ID is supplied, the caller must also own it and have `conversation:write`.

Request:

```json
{
  "conversation_id": "opaque-id-or-null",
  "message": "User text in English, Hindi, Hinglish, or mixed script.",
  "generation": {
    "max_output_tokens": null
  },
  "context": {
    "memory": "disabled",
    "knowledge_collection_ids": []
  },
  "requested_tools": []
}
```

Rules:

- `conversation_id` is optional; when absent the service performs a single-turn request and returns an ephemeral conversation ID only if a session is needed.
- `message` is required, non-empty text. The server applies approved size limits.
- `generation.max_output_tokens` is optional; if supplied it must be a positive integer no greater than the server's published configured bound. `null` means use server defaults.
- `context.memory` is `disabled` or `approved`. `approved` is accepted only if the authenticated user's memory preference/consent and `memory:read` permission permit retrieval; otherwise return a permission error. The default is disabled.
- Knowledge collection IDs must be accessible to the principal and require `knowledge:search` for each selected collection.
- `requested_tools` is a list of tool identifiers explicitly requested by the client/user. The backend intersects this list with the caller's scopes, application policy, and per-tool confirmation rules; unauthorized tools do not execute.
- No assistant/system role, arbitrary prompt template, provider name, endpoint URL, model file path, or raw tool schema is accepted from an untrusted client.

Response `200`:

```json
{
  "request_id": "opaque-request-id",
  "conversation_id": "opaque-id",
  "answer": {
    "role": "assistant",
    "content": "Generated answer."
  },
  "model": {
    "provider_id": "ollama",
    "model_id": "configured-local-model",
    "answer_mode": "development"
  },
  "context_used": {
    "memory": false,
    "knowledge_source_ids": []
  },
  "citations": [],
  "tool_summaries": [],
  "finish_reason": "stop"
}
```

The service must truthfully identify the selected answer provider/mode; it must not label Ollama output as Veronica-native. Do not return hidden reasoning, system prompts, credentials, raw tool arguments, or unrelated memory. Citation and usage fields may be omitted when unsupported; do not fabricate them.

The initial contract is non-streaming. Streaming, queued jobs, retry semantics, idempotency behavior, and cancellation transport are pending decisions; long-running generation still needs a bounded timeout/cancellation design before implementation.

### 5.3 Conversation management

| Method and path | Purpose | Authorization and default behavior |
|---|---|---|
| `POST /api/v1/conversations` | Create an ephemeral conversation and return an opaque ID plus creation time. | `conversation:write`; owner-bound. No transcript is persisted by default. |
| `GET /api/v1/conversations/{conversation_id}` | Read active conversation metadata and, only if explicitly enabled, permitted transcript content. | `conversation:read`; same owner/tenant only. Returns `404` for unknown, expired, or inaccessible IDs to avoid confirming another user's resource. |
| `DELETE /api/v1/conversations/{conversation_id}` | Clear and release the caller's conversation state. | `conversation:delete`; same owner/tenant only. |
| `GET /api/v1/conversations` | List durable conversations. | **Not part of the initial ephemeral-only contract.** Add only after transcript persistence, retention, export/deletion, and consent decisions are approved. |

The existing CLI keeps history only in process memory and bounds it by `MAX_CONVERSATION_MESSAGES`; a server must apply its own per-conversation bound and lifecycle. No API is authorized to archive CLI transcripts.

### 5.4 Memory management

Personal memory is separate from conversations and knowledge. Every write/delete requires the user's explicit intent, proper authorization, and a trusted confirmation mechanism where the action warrants confirmation. A model-generated tool request is not sufficient consent.

| Method and path | Purpose | Authorization |
|---|---|---|
| `GET /api/v1/memories?query=...&limit=...` | List or search only the caller's memories; omit `query` to list within an approved page bound. | `memory:read`; no cross-user IDs. |
| `POST /api/v1/memories` | Create a user-approved memory. | `memory:write` plus a short-lived, single-use confirmation receipt bound to the authenticated user, action, and content. |
| `PATCH /api/v1/memories/{memory_id}` | Edit one owned memory. | `memory:write` and confirmation policy; return no-op/validation errors explicitly. |
| `DELETE /api/v1/memories/{memory_id}` | Delete one owned memory. | `memory:delete` and confirmation policy. |
| `DELETE /api/v1/memories` | Clear all memories for the authenticated user. | Owner-level `memory:delete`, explicit high-friction confirmation, and auditable result count without logging content. |

Create request:

```json
{
  "content": "A concise user-approved fact.",
  "category": "general",
  "approval_id": "short-lived-single-use-receipt"
}
```

Response `201`:

```json
{
  "id": "opaque-memory-id",
  "category": "general",
  "created_at": "UTC timestamp",
  "content": "A concise user-approved fact."
}
```

The approval receipt issuance/confirmation UX and authentication mechanism are pending design decisions. A client-supplied `confirmed: true` boolean alone is not adequate proof. Credentials/secrets must remain rejected; existing pattern checks are useful but do not establish comprehensive sensitive-data detection. Memory APIs must never train on content or transfer it to online search.

### 5.5 Knowledge retrieval

**`POST /api/v1/knowledge/search`** — search only already-ingested, explicitly approved collections. No ingestion or upload endpoint is proposed in this phase.

Required scope: `knowledge:search` for each requested collection.

Request:

```json
{
  "query": "Question or terms to search.",
  "collection_ids": ["approved-collection-id"],
  "limit": 5
}
```

Response `200`:

```json
{
  "request_id": "opaque-request-id",
  "results": [
    {
      "source_id": "opaque-source-id",
      "title": "Approved source title",
      "excerpt": "Bounded, access-checked evidence excerpt.",
      "citation": "Safe display citation"
    }
  ]
}
```

The service must preserve provenance and apply user/tenant access checks at retrieval time. Do not return local absolute paths, unbounded source contents, or content from an unauthorized collection. Search results are untrusted evidence, not generated answers. Source ingestion, licenses, privacy, parser security, retention, deletion, and indexing require separate approval.

### 5.6 Health and readiness

| Method and path | Purpose | Response and exposure |
|---|---|---|
| `GET /health/live` | Report that the API process is responsive. | Minimal `{"status":"alive"}`; local listener only by default; no model, user, path, or secret details. |
| `GET /health/ready` | Report whether configured required dependencies are ready. | `200` when ready, `503` otherwise; report sanitized dependency states, not exception messages or internal addresses. Restrict to local operator/health monitoring or an approved `health:read` principal. |

Liveness must not call the model. Readiness must not claim model availability based only on the HTTP process. Health routes do not permit configuration changes or reveal prompts, memory, host paths, or credentials.

### 5.7 Model information

**`GET /api/v1/models`** — return the configured provider/model identity and truthful capabilities visible to the authenticated caller.

Response `200`:

```json
{
  "active": {
    "provider_id": "ollama",
    "model_id": "configured-local-model",
    "answer_mode": "development",
    "capabilities": {
      "text": true,
      "streaming": false,
      "tools": true,
      "vision": true
    }
  }
}
```

Do not expose installation paths, environment variables, API keys, or arbitrary local model files. A separate model-select endpoint is not proposed; provider/model changes remain operator configuration and require their own approval. Native mode must be clearly distinguishable from the current Ollama development mode.

### 5.8 Authentication and permission model

No authentication or account system exists today. The following is a proposed authorization contract, not a credential implementation:

- No public bind address by default. A future local service binds loopback and still authenticates app/API operations; loopback alone is not authorization.
- Resolve every request to an authenticated principal and enforce resource ownership and scope server-side.
- Proposed least-privilege scopes: `chat:generate`, `conversation:read`, `conversation:write`, `conversation:delete`, `memory:read`, `memory:write`, `memory:delete`, per-collection `knowledge:search`, `models:read`, `health:read`, and separately scoped `tools:invoke:<tool>`. Administrative/configuration scopes are not granted to ordinary clients.
- Separate human-user authorization from application/client credentials. External applications receive only individually approved, revocable scopes and quotas.
- Secret storage, local login/token provisioning, token lifetime/rotation, OS integration, web session strategy, and remote identity federation are pending decisions.
- Future LAN/internet operation requires a separate exposure decision, encrypted transport, robust identity, revocation, rate/abuse controls, deployment hardening, monitoring, and incident-response plan. Do not expose the API publicly by default.

## 6. API versioning and error contract

### Versioning

- Use the URI major version prefix `/api/v1`.
- Preserve existing field meaning within a major version. Additive optional fields may be introduced only when old clients safely ignore them.
- A breaking change to paths, required fields, authorization meaning, or response semantics requires a new major version and migration/deprecation plan.
- Publish and test an OpenAPI contract if a framework is selected. Keep provider-specific payloads behind adapters; do not expose Ollama wire messages as the public API.
- Define request IDs, idempotency behavior for retried state-changing operations, pagination, timeout/cancellation, and deprecation windows before implementation.

### Error format

Use a stable `application/problem+json`-style envelope:

```json
{
  "type": "about:blank",
  "title": "Request validation failed",
  "status": 422,
  "code": "validation_error",
  "detail": "A required field is invalid.",
  "request_id": "opaque-request-id",
  "field_errors": [
    {
      "field": "message",
      "code": "required"
    }
  ],
  "retryable": false
}
```

Proposed status mapping:

| HTTP status | Use |
|---|---|
| `400` | Malformed request or invalid protocol shape. |
| `401` | Missing/invalid authentication. |
| `403` | Authenticated principal lacks a required scope or consent. |
| `404` | Unknown, expired, or inaccessible resource. |
| `409` | State conflict, stale approval, or idempotency conflict. |
| `413` | Request exceeds the configured payload bound. |
| `422` | Valid JSON with invalid field values or disallowed options. |
| `429` | Rate, quota, queue, or resource limit reached; include a safe retry hint if known. |
| `503` | Required provider/model or service dependency is unavailable. |
| `504` | Request exceeded its permitted deadline. |
| `500` | Unexpected internal error with a generic client detail. |

Never return stack traces, raw exception messages, prompts, secrets, local filesystem paths, SQLite details, or private tool arguments. Log a correlation/request ID and safe error category instead. The exact mapping and retry semantics remain pending contract approval.

## 7. AI brain and provider integration

- Route API chat operations through the same provider-neutral application contract used by the CLI; keep Ollama wire serialization within the Ollama adapter.
- Preserve `AIProvider`, capability metadata, typed errors, and `ToolCall`/`ToolResultPayload` boundaries unless a reviewed compatibility change is required.
- Make API provider identity visible in model metadata and generated-response metadata. Never claim an Ollama response is native Veronica output.
- The existing provider default remains Ollama. A future native provider must report only capabilities actually implemented and independently tested.
- Do not implement silent fallback from a native-only answer request to Ollama or another external AI service. If the selected brain fails, return a sanitized unavailable/timeout error. Any transitional fallback requires a separate, visible, user-approved policy and may not be represented as native-only.
- Keep provider selection out of ordinary client-controlled chat payloads. Runtime selection remains server/operator configuration with audit and explicit approval.
- Do not duplicate private prompts to providers for shadow testing. Any comparison needs a separately approved data flow and experiment scope.
- Native replacement requires working Veronica-owned weights, matching tokenizer, inference subsystem, provider conformance, per-language and mixed-script results, resource/security/offline tests, rollback plan, and explicit user approval. This plan does not satisfy those gates.

## 8. Memory and knowledge boundaries

| Property | Conversational memory/session | Personal memory | Knowledge database |
|---|---|---|---|
| Purpose | Current-turn context and optionally an explicitly approved transcript feature. | User-approved facts for personalization. | Governed external/local documents or other approved reference sources. |
| Current state | `AIService` keeps bounded messages in process only. | Local SQLite store and lexical matching. | No general knowledge store found. |
| Ownership | Authenticated user/session; ephemeral by default. | Authenticated user; only explicitly approved writes. | Source owner/license and collection access policy plus user authorization. |
| Retrieval | Only within the active conversation. | Off unless approved by user preference/request and caller scope. | Explicit selected/authorized collections; provenance retained. |
| Persistence/deletion | No durable transcript by default; any persistent history is a pending decision. | Individual edit/delete/export/clear must be available before exposing a broad API. | Source/index deletion and re-index policy must be defined before ingestion. |
| Training | Never automatically used. | Never automatically used. | Retrieval approval is not training approval; separate, source-specific authorization required. |

Do not conflate any of these with model weights or a training corpus. Private conversations, SQLite memory, credentials, logs, and personal data remain excluded from automatic knowledge ingestion and training. Deletion behavior must include relevant indexes, caches, backups, and replicas according to an approved retention policy.

## 9. Database and storage plan

### Existing SQLite evaluation

SQLite is appropriate to retain for the current local, single-user memory use case and can support a first local-only backend stage. Verified strengths include parameterized queries, short-lived connections, nested-directory creation, explicit memory operations, and focused tests.

It is not currently a multi-user database service. There is no account/tenant key in the memory schema, no migrations framework, no encryption/key-management layer, and no defined backup/retention/export service. The current schema and database files must not be modified in this task.

### Gradual target

1. **Initial local stage:** adapt existing `MemoryService` behind an application/repository interface; keep its SQLite file and semantics unchanged. Add no new persisted data until the API's consent and retention rules are approved.
2. **Metadata and knowledge stage:** decide whether local metadata/knowledge indexes use separate SQLite databases/tables or another store. Keep source files, provenance, personal memory, conversation state, and training manifests logically separated.
3. **Growth stage:** benchmark concurrency, workload, backup/restore, access control, and operational needs. Consider a server database such as PostgreSQL only if measured multi-user/service requirements justify it; no migration is assumed.
4. **Artifact storage:** manage model/tokenizer packages as versioned files or an approved artifact store with checksums and compatibility manifests, separate from user databases and never downloaded automatically by this plan.
5. **Migration gate:** future migrations require an approved schema, backup and restore test, transactional/idempotent migration, integrity checks, rollback plan, user-data export/deletion policy, and independent verification. Never run a migration against existing user databases without explicit authorization.

Vector storage, full-text indexing, encryption, key custody, backup destination, retention, replication, and data portability are pending decisions.

## 10. Client architecture

- **Existing CLI (`dev_ai.py`):** keep as a direct local client of shared application/use-case services. It should not require an HTTP server for normal local chat. The existing commands and provider defaults remain unchanged until separately implemented and approved.
- **`run.py` / `app.main`:** currently a minimal scaffold distinct from the actual developer CLI. Unifying entry points is a future decision, not an assumed change.
- **Future desktop client:** use the same local API or shared application facade; expose model status, privacy/online state, explicit memory controls, tool confirmations, accessibility, and language choices.
- **Future web client:** call the API with a reviewed browser session/CSRF/origin policy. A web UI served on loopback is not automatically safe; block untrusted origins and local-network abuse.
- **Authorized external applications:** use documented versioned routes, per-client identity/scopes, revocation, quotas, and audit metadata. External access is not enabled by this plan.
- **Common behavior:** preserve Unicode text, report errors consistently, disclose provider/online mode and memory use, and never represent external model output as native Veronica output.

## 11. Online/offline requirements

| Capability | Offline availability | Online boundary |
|---|---|---|
| Current answer generation | Local Ollama can answer if its local service and selected model are installed and running. | Current generation need not call a cloud LLM; this is a development transition, not the final ownership target. |
| Future native answers | Must use locally available Veronica-owned model/tokenizer/runtime in offline target mode. | External AI answer services are not allowed as permanent native-mode dependencies. |
| SQLite memory | Local operation. | No sync or remote memory transfer by default. |
| Approved local knowledge | Local source/index access, subject to authorization. | Online source retrieval is optional and separately disclosed. |
| Web search | Unavailable when offline; fail clearly without fabricated results. | Existing Tavily search is disabled by default and sends a query to a remote service when enabled. |
| Speech | Local Whisper/Piper require preinstalled models and suitable devices. | Microsoft Neural TTS sends response text to an online service when explicitly enabled. |
| API | Future local API may bind loopback only. | LAN or internet binding requires separate security and deployment approval; never public by default. |

An offline mode must be enforced at the server/egress boundary, not by a UI indicator alone. Tests must verify no unintended outbound connections and must report remote-only tools as unavailable. Search results can supply evidence but do not become the answer generator. The API contract must not auto-enable online search or speech.

## 12. Security, privacy, and operational requirements

### Authentication and authorization

- Authenticate every non-public operation; health liveness may expose only minimal process state to a local listener.
- Apply least privilege per principal, resource owner, collection, and tool. Never trust a client-supplied user ID without a verified principal binding.
- Use short-lived/revocable credentials or an approved OS/browser identity mechanism; protect secrets at rest and in transit. Exact mechanism is pending.
- Keep local-only and remote modes distinct. Remote mode requires encrypted transport, identity federation or another approved authentication design, revocation, abuse protections, and operations ownership.
- Do not log bearer tokens, API keys, passwords, memory contents, prompts, full search queries, or unredacted tool data.

### Input, abuse, and data protection

- Validate type, encoding, length, nesting, enumerations, IDs, pagination, and provider-independent generation bounds.
- Enforce body/result limits, rate/concurrency quotas, timeouts, cancellation, queue limits, and safe error mapping.
- Use an allowlisted tool registry; require server-side scope checks and action-specific confirmation. Keep external documents and model output untrusted.
- Use parameterized database operations and resource ownership checks; test for path traversal, cross-user access, injection, and sensitive response leakage.
- Define data minimization, memory consent, conversation retention, access, export, deletion, backup, and incident response before persistent API behavior.
- Keep online egress disabled by default; allow only reviewed destinations and feature scopes. An API request cannot silently turn on online search or cloud speech.

### Threat model to complete before implementation

Include local malicious processes and browser-origin attacks, credential theft, API abuse, prompt injection, confused-deputy tool execution, cross-user memory/knowledge leakage, model/dependency supply chain, parser attacks, resource exhaustion, and sensitive data in logs/backups. Loopback binding is defense-in-depth, not a complete authentication boundary.

## 13. Language and evaluation requirements

API correctness and brain quality are different evaluation concerns. Transport must preserve Unicode; answer quality must be measured by language group.

- Provide separate test sets/reports for English, Hindi (Devanagari), and Hinglish (Roman Hindi/code-switching), with equal priority and no language-specific provider defaults.
- Report mixed-script text as its own group, not only folded into the three primary groups.
- For every group report request/response correctness, Unicode preservation, task quality, refusal/safety behavior, latency/resource measurements, error rates, and tool-use behavior where supported.
- Keep scores and sample counts disaggregated. Do not use a single aggregate to hide group-level weakness; thresholds require separate approval.
- Include synthetic API contract cases for combining marks, Devanagari matras/nukta/conjuncts, Roman Hindi variation, punctuation, whitespace, emoji, and mixed-script content. Do not access real datasets as part of this phase.
- Do not silently normalize, transliterate, or route text by language. The exact tokenizer normalization/fallback policy remains subject to Phase 2 decisions.
- Test error messages, validation, and UI/API status for all groups; do not assume English-only schemas or examples are sufficient.

## 14. Dependency-aware implementation roadmap

Every phase below is a proposal only. Completion of this document does not authorize any phase.

| Phase | Scope | Prerequisites | Deliverables | Required tests | Approval gate | Explicit exclusions |
|---|---|---|---|---|---|---|
| 3C — API/security decision closure | Resolve framework, local/remote audience, identity/scopes, confirmation receipts, retention, request limits, streaming/idempotency, and threat model. | Review this contract and Phase 3A; decide deployment audience and data policy. | Approved decision register, threat model, API schema freeze, and dependency review plan. | Review consistency, authorization matrix, error/status examples, and language/Unicode cases; no code tests. | Explicit user approval of decisions; legal/privacy/security review where applicable. | No packages, API/server, data access, or provider changes. |
| 3D — Local backend composition boundary | If authorized, factor or add a shared composition/use-case boundary while retaining the existing CLI behavior and provider default. | 3C decisions; service dependency/concurrency design; test baseline. | Explicit app composition, provider/memory/tool dependency injection, configuration/readiness design. | Existing CLI/provider/memory/tool tests; new unit tests for composition and unchanged CLI behavior. | Separate implementation authorization; review diff and test results. | No public bind, remote auth, migrations, training, or native provider replacement. |
| 3E — Local-only API foundation | If authorized, select/install the framework and add local-only health/readiness and model-info routes. | 3C framework/auth decision; 3D composition; dependency/security review. | Versioned schemas, error envelope, loopback-only server lifecycle and OpenAPI contract if FastAPI is selected. | Route/schema tests, auth tests, sanitized errors, readiness semantics, no-network/public-bind tests. | Explicit server/API and dependency authorization. | No transcript persistence, memory writes, knowledge ingestion, or provider change. |
| 3F — Chat and ephemeral conversations | Expose chat/turn routes and bounded in-process conversation state. | 3E; approved auth/scopes, message/output limits, cancellation and retention policy. | Chat API, opaque IDs, response/provider metadata, deletion and expiry behavior. | Provider contract/error tests, idempotency/timeout tests, isolation, limit cases, per-language Unicode contract tests. | Explicit chat API approval; confirm current Ollama operation remains the default. | No persistent transcript archive, model training, provider switch, or silent fallback. |
| 3G — Explicit memory API | Add scoped memory read/write/edit/delete with user confirmation and ownership enforcement. | 3C consent design; 3E auth; reviewed migration and retention policy. | Memory endpoints and audit-safe confirmation behavior over an approved repository boundary. | Consent-required writes/deletes, scope/ownership isolation, credential rejection, backup/export/delete tests. | Explicit memory API and data-handling approval. | No memory-to-training flow, existing DB migration, or automatic transcript storage. |
| 3H — Knowledge search API | Add search over a bounded, approved local collection. | Source-specific rights/privacy approval; provenance/access/deletion design; 3E auth. | Search endpoint with citations and access-checked result limits; no implicit ingestion. | Provenance, tenant isolation, prompt-injection handling, deletion/index consistency, language-disaggregated reports. | Explicit approval for each source and ingestion/index scope. | No dataset collection, web scraping, tokenizer experiment, or training. |
| 3I — Client and external-app access | Connect desktop/web/external applications; decide local versus remote operation. | Stable API; identity/revocation/transport decisions; security review and operations plan. | Client integration, scopes/quotas, safe browser behavior, operator documentation. | CSRF/origin, authn/authz, revocation, rate-limit, privacy/egress, accessibility and language-parity tests. | Separate approval for each client and any network exposure. | No public exposure by default; no provider/model behavior changes. |
| 3J — Native brain integration and replacement | Integrate a separately approved Veronica-owned model and inference subsystem behind provider-neutral interfaces. | Model, tokenizer, runtime, privacy, evaluation, resource, and security gates; independent implementation/testing. | Non-default native provider first, truthful capabilities, validated rollback; replacement only after separate release approval. | Provider conformance, English/Hindi/Hinglish/mixed-script reports, resource/offline/security tests, failure and rollback. | Explicit native integration and separate provider-replacement approval. | No external answer fallback in native-only mode; no automatic tokenizer or model experiment approval. |

Phases 3G and 3H depend on identity and policy decisions. Phase 3J depends on the separately governed Phase 2 tokenizer decisions and all model/data authorizations; it must not be inferred from Phase 3B.

## 15. Pending decisions

The following remain **PENDING**; recommendations above do not resolve them:

1. Whether to adopt FastAPI and which dependency/version/runtime policy to use.
2. Local deployment identity, token issuance/storage/rotation, owner roles, and the server-side scope model.
3. Whether and how the API may be accessed from LAN or internet; remote identity, TLS termination, operations, and incident ownership.
4. Whether conversational history is ever persisted, its default retention, expiry, export, and deletion semantics.
5. Memory retrieval defaults, consent UX/receipt issuance, and confirmation requirements for create/edit/delete/clear.
6. API rate/body/output/concurrency limits, streaming, idempotency, queue/job behavior, and pagination.
7. Database evolution beyond the existing local SQLite memory service; encryption, backups, migrations, and future multi-user storage.
8. Knowledge-store/index technology, source governance, ingestion authorization, and per-collection access control.
9. Tool exposure per client, action-specific confirmation, and online egress policy.
10. Native model/runtime ownership and provider replacement acceptance gates; Phase 2 D-02–D-18 remain pending.

## 16. Explicitly unauthorized work

This is a documentation-only planning task. It does **not** authorize:

- Source, test, configuration, dependency, database, schema, or migration changes.
- Installing FastAPI, an ASGI server, authentication packages, or any dependency.
- Creating or starting a server, routes, endpoints, API keys, accounts, or client integrations.
- Binding a listener to loopback, LAN, or a public address.
- Downloading models, datasets, or other artifacts; accessing or processing corpora; tokenizer fitting or experiments; model training.
- Creating a knowledge index or ingesting sources.
- Changing Ollama configuration/default, modifying AI inference behavior, or integrating/replacing the provider.
- Changing existing CLI, memory, tool, or online/offline behavior.
- Committing, pushing, publishing, or releasing.

Any future implementation requires a new, explicit scope and applicable approval gates. Nothing in this plan automatically authorizes the roadmap.

## 17. Final assessment and recommended next phase

**Requirements and proposed contracts are documented; implementation is not authorized.**

The best reuse path is the existing provider-neutral `AIProvider` boundary and `AIService` orchestration, with a new API adapter kept separate from provider wire formats. The CLI should remain a direct local client of shared application services rather than depend on an HTTP server. SQLite remains suitable for the existing local single-user memory scope, but not a ready-made multi-user persistence/authentication solution.

FastAPI is the leading proposed Python framework because of typed validation and OpenAPI support, with synchronous inference, worker count, dependencies, and security handled explicitly. Adoption remains pending review and user approval.

Recommended next phase: **Phase 3C — API Security, Identity, Persistence, and Framework Decision Closure**, still planning-only. Resolve the pending decisions, threat model, confirmation model, local/remote deployment boundaries, and contract limits before any implementation request. Keep the current Ollama development provider operational until a separately approved native-model replacement passes its independent gates.

## Inspection record

The following files and materials were directly reviewed or queried to ground this plan. Inspection was read-only.

### Repository files

- `README.md`, `requirements.txt`
- `run.py`, `dev_ai.py`
- `app/main.py`, `app/config.py`
- `app/ai/base.py`, `app/ai/provider.py`, `app/ai/service.py`, `app/ai/veronica_provider.py`, `app/ai/tool_calling.py`
- `app/memory/database.py`, `app/memory/models.py`, `app/memory/service.py`
- `app/tools/base.py`, `app/tools/registry.py`
- `tests/test_provider_contracts.py`, `tests/test_memory.py`, `tests/test_dev_ai.py`, `tests/test_ai_tool_calling.py`, `tests/test_tools.py`, `tests/test_ai.py`, `tests/test_web_search_integration.py`
- Test inventory from `tests/` to identify relevant existing coverage.

### Architecture source

- `docs/PHASE_3A_COMPLETE_INDEPENDENT_AI_SYSTEM_ARCHITECTURE_PLAN.md`

The initial Git status for this task contained pre-existing untracked Phase 2A–2G/tokenizer artifacts and the Phase 3A plan. No existing file was modified by this planning document.
