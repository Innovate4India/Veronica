# Phase 3D: API Contract Finalization and Client Integration Architecture Plan

**Status:** Proposed contract for review. No API/server, client integration, framework, or behavior is implemented or authorized by this document.

## 1. Current-state verification

Phase 3A, Phase 3B, and Phase 3C were read completely before this plan was drafted. Their target diagrams, route examples, decision matrices, and recommendations are proposals unless identified below as existing verified behavior.

### Existing — verified

- `AIProvider`, `ChatMessage`, provider metadata/capabilities, and typed errors provide an in-process provider-neutral contract. Ollama is the only complete text-answer provider in the registry and remains the current default.
- `VeronicaModelProvider` is a scaffold with no answer-generation capability. It does not load a model or generate answers.
- `AIService` accepts a user message, maintains bounded in-process conversation context, and calls the selected provider. It also integrates optional memory and tools. These are synchronous Python services, not HTTP handlers. The current service's history behavior does not establish isolation between API requests or users; the isolation defined below is a proposed requirement, not an implemented guarantee.
- `dev_ai.py` composes provider, memory, optional tools, and optional speech for the CLI. `run.py` invokes the minimal `app.main` scaffold.
- Local SQLite memory is user-approved personal memory with explicit save intent and lexical retrieval. Matching memories may be retrieved during ordinary CLI turns when memory is enabled. No API, user/tenant identity, or persistent transcript store exists.
- `ToolRegistry` is an explicit, schema-validating allowlist. It can require confirmation, but it does not supply a general API authentication or permission system.
- Optional web search and online speech have external network boundaries; neither is a replacement for the answer-generation provider.
- Existing project tests cover provider contracts, CLI, memory, tools, and optional search; they do not establish API, authentication, browser security, or multi-user behavior.

### Proposed, not implemented

- `/api/v1` routes and JSON schemas from Phase 3B.
- FastAPI as a candidate framework; identity and permission scopes; ephemeral conversation resources; memory and knowledge APIs; versioning and error conventions.
- Local-only service operation, desktop/web/external client integration, streaming, cancellation, and API operations.
- Any changes to the CLI, persistence, provider selection, or client behavior.

### Governing boundaries

Ollama remains the current development provider until a native Veronica brain is independently implemented, tested, and separately approved to replace it. The API must not expose Ollama-specific wire formats as Veronica's permanent public contract, label Ollama output as native, or silently fall back to external AI in a mode represented as native-only.

English, Hindi (Devanagari), and Hinglish (Roman Hindi/code-switching) are co-equal priorities. Mixed-script text must be reported separately. D-01 from Phase 2G approves only the tokenizer-comparison objective; no tokenizer experiment, dataset acquisition, model training, provider integration, or provider replacement is authorized.

## 2. API architecture and request lifecycle

The proposed API is a transport adapter over shared application services, not a second implementation of chat logic. All clients should reuse the same application semantics and provider-neutral services, but they need not share one transport: the existing CLI calls in-process application/use-case services directly, while future API-backed clients use the approved API or facade appropriate to that client.

```text
CLI (dev_ai.py)
      | direct in-process calls
      +-------------------------------------+
                                            |
Future desktop client                       |
      | approved local API or facade         |
      +-------------------------------------+--> Shared application/use-case services
                                            |       | auth/policy for API calls
Future web client                            |       | memory / knowledge / tools
      | authenticated API                    |       v
      +-------------------------------------+  Provider-neutral AI service
                                            |       |
Authorized external applications            |       v
      | versioned HTTP API                   |  Configured answer provider
      +-------------------------------------+  Current: Ollama / Future: Veronica
                                                    |
                                      Client-appropriate response
```

The future desktop, web, and external API paths are proposed, not implemented. HTTP authentication and request validation apply to API calls; the CLI remains usable without an HTTP listener.

### Request lifecycle

1. Assign or validate a request ID; reject malformed protocol and oversized bodies before expensive work.
2. Authenticate the client and resolve the principal. Check route scope, resource ownership, consent, and tenant/collection ACL.
3. Validate request fields and server-owned bounds. The client cannot choose an arbitrary provider, model path, endpoint, tool schema, or system prompt.
4. Build the application request from the user message, approved conversation context, and only authorized memory/knowledge/tool capabilities.
5. Invoke the provider-neutral service. Keep Ollama-specific serialization in the Ollama adapter; keep the API response framework-neutral.
6. Validate the returned answer and metadata. Do not convert a timeout/provider failure into a successful-looking answer.
7. Return a versioned response with provider identity, permitted citations/tool summaries, and request ID. Log only approved redacted metadata.
8. Retain conversation content only according to the explicitly approved session policy; never add transcript or memory content to training automatically.

The API service must not access the database directly from route functions. The API layer delegates to application/use-case services, which call repository and provider interfaces.

## 3. Chat request and response contracts

The following is a proposed version-1 contract, not a live endpoint. It uses Veronica-level fields and does not mirror Ollama's native request/response payloads.

### `POST /api/v1/chat`

**Purpose:** generate one answer, optionally appending the turn to an active ephemeral conversation.

**Required scopes:** `chat:generate`. For a supplied `conversation_id`, the proposed rule is to require both `conversation:read` (to load existing context) and `conversation:write` (to append the new turn), in addition to ownership. Whether to use this pair or a dedicated `conversation:turn` scope is pending user approval under C3D-12. A `conversation:turn` scope is acceptable only if its documented semantics explicitly grant both reading the owned conversation context and appending the turn; it must not imply access to other conversations or transcript export.

Request:

```json
{
  "conversation_id": "opaque-id-or-null",
  "message": "A user message in English, Hindi, Hinglish, or mixed script.",
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

Contract rules:

- `message` is required, a string, and non-empty after whitespace validation. Preserve the supplied Unicode text; do not silently transliterate or normalize it.
- If `conversation_id` is absent or `null`, perform an isolated one-shot request without creating durable conversation state; return `conversation_id: null`. The request must not read, append to, or inherit conversation history from any other request, conversation, CLI session, or principal. Build its context only from this request and any separately authorized memory/knowledge resources explicitly selected for this request.
- Context must be scoped to the individual request or to the explicitly identified, owner-authorized conversation. Do not rely on implicit shared `AIService` in-process history for API context. The API implementation must establish and test this isolation; it is not claimed to exist in the current service.
- If an ephemeral conversation is desired, first create it with `POST /api/v1/conversations`, then supply its ID. Expired, unknown, or inaccessible IDs must not disclose another user's resource.
- `generation.max_output_tokens` is optional and nullable. A positive integer may be accepted only within a server-published limit; `null` means server-selected defaults. Do not expose parameters lacking provider-independent semantics.
- `context.memory` is `disabled` by default. `approved` is accepted only when the user's memory policy permits retrieval and the principal has `memory:read`.
- `knowledge_collection_ids` defaults to an empty list. Every selected collection requires caller permission and resource-level access checks.
- `requested_tools` defaults to an empty list. The service intersects user/client requests with scopes, policy, registry availability, and confirmation requirements. A model's tool request never authorizes itself.
- Reject unknown fields and client-supplied system/assistant roles, arbitrary prompts, provider names, endpoints, filesystem paths, or raw tool schemas.
- `Idempotency-Key` behavior for retries must be approved before stateful turn or tool execution is implemented. Duplicate requests must not silently duplicate a consequential operation.
- The initial contract is non-streaming. A request must not imply streaming if the selected provider does not implement it.

Successful response `200`:

```json
{
  "request_id": "opaque-request-id",
  "conversation_id": "opaque-id-or-null",
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
  "finish_reason": "completed"
}
```

The response must not expose hidden reasoning, internal system prompts, secrets, raw tool arguments, unrelated memories, local model paths, or exception messages. Do not invent usage counts, citations, or capabilities. When a provider cannot supply optional metadata, omit it or report it as unavailable using a reviewed schema.

For chat requests with a conversation ID, the authenticated owner receives the same conversation ID. `answer_mode` must distinguish the existing Ollama development provider from a future, explicitly approved native Veronica provider. The API may report provider identity for transparency; it must not expose provider-specific wire data.

## 4. Conversation lifecycle and identifiers

### Proposed routes

| Method and path | Contract |
|---|---|
| `POST /api/v1/conversations` | Create an owner-bound ephemeral conversation. Returns `201` with opaque `conversation_id`, `created_at`, `expires_at`, and `persistence: "ephemeral"`. |
| `GET /api/v1/conversations/{conversation_id}` | Return permitted metadata such as ID, creation/expiry, and message count. Does not expose transcript content by default. |
| `DELETE /api/v1/conversations/{conversation_id}` | Clear and release the caller's ephemeral conversation; returns `204` on success. |
| `GET /api/v1/conversations` | Not included in the initial ephemeral-only contract. Add only after transcript persistence, retention, ownership, export, and deletion are approved. |

Identifiers should be unpredictable, opaque, scoped to the authenticated owner/tenant, and never treated as authorization credentials. Resource lookup must enforce ownership on every operation. Use `404` for inaccessible/unknown IDs where avoiding cross-user enumeration is appropriate.

The current CLI holds bounded history in process memory. API-created sessions must also be bounded by server policy and expire; exact limits/TTL are pending resource measurement and user approval. API conversations must not silently become durable transcripts or share state with the CLI.

Persistent conversation history, transcript read endpoints, list/search APIs, synchronization, and cross-device continuity are future opt-in decisions—not version-1 defaults.

## 5. Memory API boundaries and consent

Personal memory is not conversation history, knowledge content, or training data.

### Proposed routes

| Method and path | Contract |
|---|---|
| `GET /api/v1/memories` | List the authenticated user's memories within a bounded page. Requires `memory:read`. |
| `POST /api/v1/memories/search` | Search using an authenticated request body so private query text is not exposed in URL logs. Requires `memory:read`. |
| `POST /api/v1/memories` | Create one memory after explicit user action, `memory:write`, and a trusted, single-use approval receipt. |
| `PATCH /api/v1/memories/{memory_id}` | Edit an owned memory under `memory:write` and the approved confirmation policy. |
| `DELETE /api/v1/memories/{memory_id}` | Delete one owned memory under `memory:delete` and applicable confirmation. |
| `DELETE /api/v1/memories` | Clear all memories for the authenticated owner only after explicit high-friction confirmation. |

The create request may use the Phase 3B proposed shape:

```json
{
  "content": "A concise user-approved fact.",
  "category": "general",
  "approval_id": "short-lived-single-use-receipt"
}
```

The response must return only the created record's approved fields and opaque ID. An approval receipt must bind to the principal, operation, and content/resource and be single-use. The confirmation UX and receipt issuer remain pending decisions; a client-supplied `confirmed: true` is not sufficient proof.

Existing CLI save intent is explicit, but matching memory can be retrieved during an ordinary turn when memory service is enabled. The API's retrieval mode must therefore be independently specified and disclosed; do not claim the existing CLI is per-turn opt-in. Never write memory from model/tool output alone. Existing credential-pattern rejection is useful but is not comprehensive sensitive-data detection.

No memory operation may trigger transcript retention, online search, knowledge ingestion, or training. Export, retention, and deletion from derived copies/backups need separately approved policies.

## 6. Knowledge search API boundaries

### `POST /api/v1/knowledge/search`

Search only approved and already-ingested collections. This proposal includes no ingestion, upload, crawl, or source-registration endpoint.

Required permission: `knowledge:search` for each requested collection, followed by source-level ownership/ACL checks.

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
      "excerpt": "Bounded evidence excerpt.",
      "citation": "Safe display citation"
    }
  ]
}
```

Apply server-side result and excerpt limits, preserve provenance, and do not return unauthorized content, raw files, or local absolute paths. Search results are untrusted evidence for Veronica's answer provider; they are not final generated answers and may contain prompt injection.

Source rights, provenance, privacy, parser security, retention/deletion, and indexing must be approved independently before any source is ingested. This contract does not authorize dataset access or data acquisition.

## 7. Model metadata and capability contracts

### `GET /api/v1/models`

Return the configured model/provider identity and capabilities visible to the authenticated caller. Do not add a user-facing provider/model selection endpoint in version 1.

Proposed response:

The capability values below are illustrative schema values only; the implementation must report the actual configured provider/model capabilities and must not copy these values as defaults.

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

Capability requirements:

- Derive capabilities from the selected provider's implemented contract, not a client request or marketing label.
- Distinguish provider identity (`ollama`, future `veronica-local`) from answer mode (`development`, future `native`).
- Never label Ollama output as Veronica-native. Do not report `native` unless the native provider is implemented, tested, configured, and separately approved.
- Report `streaming`, `tools`, and `vision` accurately. `false` means unavailable; no capability is implied by a generic provider interface.
- Do not expose model installation paths, environment variables, credentials, internal endpoints, or model-file listings.
- If no provider/model is ready, report a sanitized unavailable state; do not silently substitute another answer service.

This metadata contract does not authorize provider changes or native-model integration.

## 8. Error response format and HTTP status conventions

Use one stable, provider-neutral `application/problem+json`-style envelope:

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

`detail` and field errors must be safe for the authenticated client. Do not return stack traces, raw exceptions, SQLite/provider internals, private prompts, credentials, local paths, or unredacted tool payloads.

| Status | Proposed use |
|---|---|
| `200` | Successful read or chat response. |
| `201` | Conversation or memory resource created. |
| `204` | Resource deleted/cleared with no response body. |
| `400` | Malformed request/protocol. |
| `401` | Missing or invalid authentication. |
| `403` | Authenticated principal lacks scope, consent, or permission. |
| `404` | Unknown, expired, or inaccessible resource. |
| `409` | State conflict, stale/used approval, or idempotency conflict. |
| `413` | Request exceeds the configured payload bound. |
| `422` | Valid protocol but invalid/disallowed fields or options. |
| `429` | Rate, queue, quota, or resource bound reached. |
| `503` | Required configured provider/model/dependency unavailable. |
| `504` | Request exceeded its permitted deadline. |
| `500` | Unexpected failure with generic client text and a request ID. |

Do not return `200` with an error-shaped answer if generation failed. Error mapping, retryability, and idempotency responses must be contract-tested before implementation.

## 9. Synchronous requests, streaming, cancellation, and timeouts

### Version-1 recommendation: synchronous, non-streaming

- Keep `POST /api/v1/chat` a single JSON request/response initially. This matches the current synchronous `AIService` and avoids promising a capability that the current provider may not implement.
- Enforce server-configured provider and request deadlines, output bounds, queue limits, and concurrency limits. Exact values require measurement on supported hardware and explicit approval.
- Return a sanitized `504` when the service deadline expires, or `503` for a provider that is unavailable before generation. Never retry to another AI provider implicitly.
- Use a bounded execution strategy for synchronous provider/inference calls. Do not block an async event loop with model work. Worker/process selection and cancellation support require a separate implementation decision.
- Client disconnect/cancellation must stop queued work where possible. If a running native/provider call cannot be interrupted safely, stop delivering its result, keep resource accounting until it ends, and prevent it from creating hidden side effects.
- Define idempotency for retried chat turns and tools before enabling retries. A timeout does not prove that the model/tool did not execute.

### Streaming — future opt-in, not in version 1

If separately approved, a streaming route may use server-sent events with versioned JSON event data such as `message_start`, `text_delta`, `citation`, `tool_status`, `message_end`, and `error`. It must not expose hidden reasoning, raw tool arguments, or provider-native payloads. Client disconnect should request cancellation; actual cancellation guarantees must match the provider's capability.

Streaming must be disabled/rejected when `capabilities.streaming` is false. It requires separate decisions for event schema, partial-response errors, reconnection, heartbeat, tool events, client support, and resource cleanup. No streaming endpoint is created by this plan.

### Queued jobs and cancellation resources

Queued job IDs, polling endpoints, explicit cancel endpoints, partial-result retention, and background workers are not part of the initial contract. Adopt them only if measured latency and client requirements justify the additional lifecycle/security surface.

## 10. API versioning and backward compatibility

- Use the proposed major-version prefix `/api/v1`; exact route/schema adoption remains pending approval.
- Publish a machine-readable OpenAPI contract after framework selection and keep its generated output reviewable.
- Keep HTTP schemas independent of Python dataclasses and Ollama wire shapes.
- Within a major version, preserve field meaning, authorization semantics, error codes, and resource ownership behavior. Add optional fields only when older clients can ignore them safely.
- Reject unsupported input fields rather than silently accepting a different meaning.
- Breaking changes to routes, required fields, IDs, authorization, retention, or error semantics require a new major version and migration/deprecation plan.
- Document API deprecation periods, client compatibility support, and server/client version negotiation before external clients are supported.
- Add `request_id` to responses and safe error envelopes. Define idempotency-key retention/behavior and pagination before implementing writes or list operations.

## 11. CLI, desktop, web, and external application integration

All clients reuse the same application semantics and provider-neutral services; they do not call Ollama directly or format provider-specific prompts. Transport differs by client: the existing CLI (`dev_ai.py`) calls in-process application/use-case services directly and does not have to communicate through HTTP. The desktop, web, and external API integrations below are future proposals, not implemented functionality.

### Existing CLI

- `dev_ai.py` remains usable without starting an HTTP service and calls the application/use-case services in process.
- Prefer a shared composition/use-case layer so the CLI and future API call the same services without forcing local CLI traffic through HTTP.
- Preserve its current provider default, commands, memory behavior, and error handling unless separately authorized.
- `run.py` and `app.main` currently form a distinct minimal scaffold; unifying entry points is a separate decision.

### Future desktop client

- Use an approved local API or application facade after separately authorized; this integration is proposed, not implemented.
- Use OS-protected credentials, display provider/mode and online state, and provide memory consent/deletion and tool-confirmation UX.
- Do not bundle administrator credentials or expose model files/paths to ordinary clients.

### Future web client

- Use an authenticated API; same-origin hosting for a local web experience may be preferred where feasible, subject to framework and deployment decisions. This integration is proposed, not implemented.
- Require a reviewed browser-session, CSRF, origin allowlist, content-security, safe-rendering, and local-network request policy.
- Do not store long-lived bearer credentials in browser-accessible local storage.
- A loopback server is not trusted merely because it is local; protect it against cross-origin and local-process requests.

### Authorized external applications

- Use a versioned HTTP API with per-client identity, least-privilege scopes, quotas, revocation, and documented data handling, if separately authorized. This integration is proposed, not implemented.
- Never embed shared administrator credentials in client apps.
- Remote clients require a separately approved deployment, TLS, identity, operations, rate/abuse controls, privacy review, and incident-response ownership.
- Do not expose the API publicly by default.

## 12. Online/offline behavior and external network boundaries

| Capability | Offline behavior | Online boundary |
|---|---|---|
| Current development answers | Local Ollama can answer if its local service and model are installed and running. | Ollama remains transitional and local; it is not the final native-answer ownership target. |
| Future native answers | Must use the approved local Veronica model, tokenizer, and inference subsystem. | External AI services must not be permanent answer-generation dependencies. No silent fallback. |
| Memory and ephemeral conversations | Local in-process/SQLite operation under approved policy. | No remote sync or backup by default. |
| Knowledge search | Search only locally available, approved collections. | Online web search is optional, separately authorized, and sends only disclosed/minimized data. |
| Speech | Local speech requires preinstalled local assets and hardware. | Microsoft Neural TTS is online; response text egress must be disclosed and opt-in. |
| API client transport | Local CLI can remain in-process; a future local service may bind loopback after security gates. | LAN/internet exposure is a separate decision and is not enabled by this plan. |

The server must represent remote-only capabilities as unavailable when offline and must not invent results. Offline mode must be enforced at the service/network boundary, not just displayed in the UI. Search evidence may inform the answer but does not generate Veronica's final answer.

## 13. Client authorization and resource ownership

- Resolve each request to an authenticated human principal, local installation, or client application. Authentication does not grant blanket access.
- Use server-side scopes and resource checks: `chat:generate`; conversation read/write/delete (or a separately approved `conversation:turn` scope with explicit read-and-append semantics); memory read/write/delete; per-collection knowledge search; `models:read`; `health:read`; and per-tool invocation. The final conversation permission choice remains pending user approval under C3D-12.
- A chat turn using an existing conversation must be authorized to read that conversation's context and append the new turn. Under the proposed paired-scope option, require both `conversation:read` and `conversation:write`; under the alternative, `conversation:turn` must explicitly mean both operations for that owned conversation. Neither option grants access to unrelated conversations.
- One-shot requests must use request-scoped context only and must be isolated from conversation histories held for any other request or principal. This is a proposed API requirement, not an existing `AIService` guarantee.
- Bind conversation and memory IDs to the authenticated owner/tenant. Do not trust caller-supplied owner IDs or assume an opaque ID is a capability.
- Return non-enumerating failures for inaccessible resources where appropriate.
- For an external application acting for a user, separately record client identity and user identity; check both the client grant and user/resource permission.
- Enforce knowledge collection/source ACLs at retrieval time. Search permission does not imply ingestion or training permission.
- Model and tool output never confer authorization. A tool request must pass allowlist, scope, schema, policy, and confirmation checks.
- Keep administrator/configuration scopes away from ordinary chat and third-party integrations.
- If multi-user mode is later selected, test tenant isolation across storage, caches, indexes, logs, backups, and asynchronous jobs.

## 14. API contract testing strategy

Testing is for a future implementation phase; no tests were created or run for this plan.

### Contract and schema

- Validate every request/response example against the approved OpenAPI/schema.
- Test required/unknown fields, malformed JSON, Unicode, body/output bounds, IDs, pagination, status codes, and content types.
- Verify API responses contain only Veronica-level fields and do not leak Ollama-native formats.
- Verify additive compatibility and major-version rejection/deprecation behavior.

### Identity, authorization, and privacy

- Missing/invalid token, expired/revoked credential, insufficient scope, cross-user IDs, wrong tenant/collection, reused approval receipts, and administrator-scope denial.
- Memory confirmation and user-consent behavior; verify model requests cannot create/delete memories without user authorization.
- Ensure errors, logs, traces, and audit events omit secrets, prompts, memory text, local paths, and raw tool arguments/results.
- Browser-origin/CSRF tests if browser clients are enabled; remote TLS and credential lifecycle tests if remote deployment is approved.

### Provider and lifecycle

- Stub-provider tests for successful answers, provider unavailable, timeout, malformed output, capability reporting, and no silent external fallback.
- Conversation creation, ownership, expiry, clearing/deletion, one-shot chat, duplicate/idempotency behavior, and restart semantics.
- Cancellation/disconnect cleanup, bounded queue saturation, worker resource accounting, and no duplicate side effects on retry.
- Offline network-egress tests and explicit unavailable responses for online-only search/speech.

### Language and Unicode

- Keep reports separate for English, Hindi (Devanagari), and Hinglish (Roman Hindi/code-switching); report mixed-script separately.
- For each group test request/response preservation, validation/error behavior, citations, tool summaries, and generation quality when an approved brain is available.
- Include synthetic inputs with whitespace, punctuation, emoji, combining marks, Devanagari matras/nukta/conjuncts, and mixed scripts. Do not access real datasets as part of this plan.
- Do not set or infer performance/quality thresholds here. Approve measurable thresholds before evaluation, and never let aggregate metrics hide a weak group.

## 15. Decision matrix

All entries below are recommendations for review. **Every status is PENDING USER APPROVAL.** None of the Phase 3B/3C recommendations has been approved by this document.

| Decision ID | Topic | Available options | Recommended option | Risks/trade-offs | User approval required | Status |
|---|---|---|---|---|---|---|
| C3D-01 | API base/version | `/api/v1`; another URI/version scheme; defer versioning. | Use `/api/v1` with a published, framework-neutral schema. | URI versioning is simple but breaking changes still require support/deprecation planning. | Approve base path and version/deprecation policy. | PENDING USER APPROVAL |
| C3D-02 | Primary chat route | `/chat`; `/chat/completions`; resource-based turns only. | Keep one canonical `POST /api/v1/chat`; optional ephemeral conversation ID. | New route semantics must remain stable; no compatibility with provider-native payloads should be promised. | Approve exact route, fields, and response. | PENDING USER APPROVAL |
| C3D-03 | Stateless and conversation behavior | One-shot only; optional ephemeral session; persistent transcript. | One-shot by default; create explicit ephemeral session to continue; no durable transcript initially. | Active context disappears at expiry/restart; persistent history needs separate privacy/storage work. | Approve lifecycle, expiry, message access, and persistence. | PENDING USER APPROVAL |
| C3D-04 | Identifier policy | UUID; random opaque token; caller-selected ID. | Server-generated unpredictable opaque IDs bound to an owner. | Opaque IDs are not authorization; ownership checks remain mandatory. | Approve ID format/ownership and expiry behavior. | PENDING USER APPROVAL |
| C3D-05 | Memory search/write contract | GET query-string search; POST body search; direct writes; confirmation receipt. | POST body for private search; explicit write with scoped single-use user approval receipt. | Receipt issuance UX and storage are additional complexity; GET is more cache/log prone for private queries. | Approve routes, consent UX, receipt issuer, scopes, and retrieval default. | PENDING USER APPROVAL |
| C3D-06 | Knowledge search | GET query; POST query body; expose ingestion endpoints; search-only. | POST body search over approved collections only; no ingestion route in initial contract. | Query bodies are not automatically private from logs; access control/provenance remains necessary. | Approve search schema, source/collection ACL, and separate ingestion gates. | PENDING USER APPROVAL |
| C3D-07 | Model metadata | Provider-specific payload; neutral metadata with provider ID; no metadata. | Neutral metadata, truthful capabilities, explicit development/native mode, no internal paths. | Revealing provider/model identity has small information value; omitting it reduces transparency. | Approve exposed metadata and visibility scopes. | PENDING USER APPROVAL |
| C3D-08 | Errors/statuses | Framework-default errors; stable problem envelope; provider raw errors. | Stable problem-style envelope with safe details and request ID. | Mapping needs consistent implementations and client compatibility; raw errors aid debugging but risk disclosure. | Approve status mapping, error codes, retryable semantics. | PENDING USER APPROVAL |
| C3D-09 | Streaming | Non-streaming only; SSE; WebSocket; queued jobs. | Non-streaming JSON for initial contract; revisit after provider/runtime measurements. | Longer waits; stream/job options add lifecycle and cancellation complexity. | Approve supported modes and event/job semantics. | PENDING USER APPROVAL |
| C3D-10 | Timeout/cancellation | Disconnect-only best effort; explicit request/job cancellation; no deadline. | Bounded deadlines and cancellation cleanup; do not promise hard cancellation if provider cannot stop. | A timed-out worker may continue consuming resources; job IDs add persistence and auth complexity. | Approve deadlines, cancel guarantees, cleanup, and retry behavior. | PENDING USER APPROVAL |
| C3D-11 | Idempotency | No retry handling; idempotency key; client-only deduplication. | Require defined idempotency for stateful chat/tool/memory writes before retries are supported. | Key storage/expiry and pending-request semantics add state; no idempotency can duplicate actions. | Approve header/key scope, expiry, conflict, and response behavior. | PENDING USER APPROVAL |
| C3D-12 | Authorization and ownership | Coarse user/admin; scopes; scopes plus resource ACL; local trust; paired conversation read/write scopes or a dedicated `conversation:turn` scope. | Least-privilege scopes plus owner/tenant/resource checks; model requests never authorize. | Increased policy/testing surface; requires identity design first. A dedicated turn scope must clearly grant both read-context and append-turn only for the owned conversation. | Approve principal, scope, resource ownership, admin matrix, and the conversation read/write permission form. | PENDING USER APPROVAL |
| C3D-13 | Client connectivity | CLI direct service; all clients HTTP; optional API client mode. | CLI remains in-process; desktop/web/external clients use approved API contracts. | Shared application composition is required; multiple deployment modes need test coverage. | Approve client topology and whether CLI gets an API mode. | PENDING USER APPROVAL |
| C3D-14 | Browser and external clients | Shared static key; per-client scopes; browser session plus CSRF; unauthenticated local. | Per-client scopes and reviewed browser-session policy; never unauthenticated solely because local. | Provisioning and revocation complexity; remote use also requires transport and operations decisions. | Approve auth flows and permitted client categories. | PENDING USER APPROVAL |
| C3D-15 | Online/offline contract | Always online; per-feature opt-in; strict offline mode. | Offline/local default; explicit online feature opt-in and egress disclosure. | Remote tools unavailable offline; egress policy and network tests required. | Approve destinations, data sent, and offline enforcement. | PENDING USER APPROVAL |
| C3D-16 | Language/evaluation contract | Pooled metrics; three language reports; separate mixed-script reports. | Equal English/Hindi/Hinglish reports plus separate mixed-script results. | Requires adequate approved evaluation evidence; thresholds remain undecided. | Approve thresholds and evaluation data only in a separate authorized phase. | PENDING USER APPROVAL |

## 16. Implementation approval gates

The contract may be treated as approved for implementation only after the user separately resolves applicable C3D decision IDs and approves a named, bounded implementation scope. A recommendation, a completed design document, or a blank approval field is not authorization.

### Gate A — Contract freeze

- [ ] Approve the API base/version, routes, required/optional fields, response metadata, error codes, and deprecation policy.
- [ ] Approve conversation semantics: one-shot behavior, ephemeral ID ownership/expiry, deletion, and whether transcript access exists.
- [ ] Approve the non-streaming baseline or a fully specified streaming/job/cancellation contract.
- [ ] Approve output limits, timeouts, idempotency and retry behavior using measured resource evidence.

### Gate B — Identity, authorization, and data

- [ ] Approve local identity, authentication, credential provisioning/storage/rotation/revocation, and future multi-user identity if in scope.
- [ ] Approve route scopes, resource ownership, per-collection knowledge ACLs, tool permissions, and confirmation policy.
- [ ] Approve memory retrieval defaults and trusted write/delete consent flow.
- [ ] Approve conversation retention, memory/knowledge deletion, backup, export, and audit retention policies.
- [ ] Confirm no conversation, memory, credentials, logs, or personal data flow automatically to model training.

### Gate C — Security and deployment

- [ ] Complete threat model and privacy/data-flow review for the chosen clients and deployment mode.
- [ ] Approve loopback/LAN/remote boundary explicitly; public exposure remains off by default.
- [ ] Approve browser-origin/CSRF protections, rate/size/resource bounds, redaction, audit fields, and incident handling.
- [ ] Review framework/dependencies, licensing, updates, packaging, secret handling, and synchronous inference/cancellation strategy.
- [ ] Define offline egress controls and test destinations; disclose any permitted online search or speech traffic.

### Gate D — Provider, clients, and verification

- [ ] Preserve current Ollama operation/default until separate native replacement gates pass.
- [ ] Keep provider-specific formats behind adapters and accurately report capabilities and answer mode.
- [ ] Define CLI, desktop, web, and external-app responsibilities without forcing the CLI through an HTTP listener.
- [ ] Approve contract, authorization-negative, ownership, memory-consent, Unicode, egress, cancellation, and error-redaction tests.
- [ ] Report English, Hindi, and Hinglish independently and mixed-script separately; approve thresholds before evaluation.
- [ ] Obtain explicit user authorization naming the implementation phase, files/components, dependencies, and exclusions.

Passing these gates would authorize only the specifically named implementation scope. It would not authorize dataset acquisition, tokenizer experiments, model training, public deployment, or provider replacement unless those are separately and explicitly approved.

## Final status

**PROPOSED API CONTRACT DOCUMENTED — NO ENDPOINTS EXIST — ALL C3D DECISIONS PENDING USER APPROVAL — IMPLEMENTATION NOT AUTHORIZED.**

The recommended review baseline is a neutral `/api/v1` contract, non-streaming requests first, one-shot chat plus owner-bound ephemeral conversations, explicit/authorized memory operations, search-only access to approved knowledge, truthful model capabilities, and per-client authorization. These are recommendations only. Ollama remains the current development provider; the public contract must not make Ollama's wire format permanent or silently substitute external AI for a future native answer path.

## Inspection record

The complete Phase 3A, Phase 3B, and Phase 3C documents were read before drafting. Their existing/proposed/pending distinctions and authorization boundaries were retained. Existing interfaces and services were not reinspected because the directly relevant capabilities and test coverage are documented in Phase 3B and the current-state verification in Phase 3C; no new code-level claim in this plan requires a different conclusion.
