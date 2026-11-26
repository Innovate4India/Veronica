# Phase 3E: Backend Application Layer and Shared Service Architecture Plan

**Status:** Documentation-only proposal. No application layer, backend, API, server, endpoint, or client integration is implemented or authorized by this document.

## 1. Executive summary

Veronica already has useful provider-neutral AI contracts, a synchronous orchestration service, a local memory service, a validated tool registry, and a working interactive CLI. These provide implementation material to reuse, but they do not yet constitute a shared backend application layer: the CLI currently creates and wires its dependencies itself, `app.main` is only a minimal scaffold, and `app.services` contains no service implementation.

This plan proposes a transport-independent application/use-case boundary that the existing CLI can call directly and that a future, separately approved API can call through authenticated request handlers. The CLI must remain usable without an HTTP listener. Future desktop, web, and authorized external applications may use an approved local facade or authenticated, versioned HTTP API; these integrations are proposals, not existing capabilities.

The application layer should coordinate user intent, conversation context, authorization, memory, knowledge, tools, and the configured answer provider without absorbing transport details or provider-specific wire formats. The current Ollama provider remains operational and the default until a Veronica-owned brain independently passes its gates and a separate provider-switch approval is granted. No framework, package, persistence expansion, API behavior, or service topology is selected here.

## 2. Current architecture assessment

The table distinguishes inspected implementation from target design.

| Area | Existing and verified | Implication for the target |
|---|---|---|
| Entry points | `dev_ai.py` is the interactive CLI and composes provider, memory, optional tools, and optional speech. `run.py` invokes the minimal `app.main` scaffold. | Preserve both behaviors unless a separately approved implementation changes them. Do not make the CLI depend on HTTP. |
| Application orchestration | `app/ai/service.py` defines `AIService`, which handles roles/teaching behavior, memory intent/retrieval, optional tool dispatch, provider calls, and an in-process bounded conversation history. | Reuse the behavior and separate responsibilities carefully. `AIService` is currently stateful and is not an API handler, persistence abstraction, or multi-user boundary. |
| Provider contracts | `app/ai/base.py` defines provider-neutral messages, response/capability metadata, tool-call types, and typed errors. `app/ai/provider.py` registers Ollama and selects it by default. | Keep these contracts behind a provider adapter boundary. The contracts do not themselves implement native inference or API security. |
| Native brain | `VeronicaModelProvider` is an unavailable scaffold without answer-generation capability. | Treat it as an extension point, not a functioning brain or replacement provider. |
| Memory | `MemoryService` uses `MemoryDatabase` and SQLite for local save/list/search/delete/clear operations. The database opens short-lived connections; the schema has no owner or tenant column. | Preserve current local semantics. Add a repository/use-case boundary before future API exposure; do not assume multi-user ownership or migration support. |
| Tools | `ToolRegistry` is instance-scoped, allowlisted, schema-validates parameters, and can require confirmation. `ToolCallingService` bounds the model/tool loop. | Keep server-side policy and validation. A model-generated tool request is never authorization. Client/API permissions and confirmation remain future work. |
| Configuration | `app/config.py` exposes environment-backed provider, memory, voice, file-search, and optional web-search settings. There is no backend lifecycle, API identity, or server configuration. | A future composition root may consume validated settings, but new settings and secrets require separate review. |
| Service package | `app/services/__init__.py` is reserved for future service components; it currently contains no application service implementation. | A shared use-case layer is proposed, not already present. The eventual package layout is illustrative, not a commitment to create these files. |
| Transport/backend | `app/main.py` logs that the Phase 1 scaffold started. No HTTP framework, server, route, API authentication, or listener was found. FastAPI is not in the dependency manifest. | No endpoint, server, framework, or dependency is authorized by this plan. |
| Tests | Inspected tests cover provider contracts and the Ollama adapter, AIService behavior, local memory, tools, CLI startup/commands, configuration, and selected optional integrations. | These are component and CLI/integration tests, not tests of a Veronica HTTP backend. No API/server, authentication, multi-tenant, remote-deployment, shared application/use-case composition, or cross-user conversation-isolation tests were found. AIService history tests cover preservation, trimming, and clearing within one instance; they do not prove isolation between requests or users. Future tests remain proposals. |

### Existing test coverage verified

- **Provider and AI service:** `tests/test_provider_contracts.py` exercises fake-provider compatibility, Ollama-default selection, provider registration/errors, advertised capability accuracy, provider-neutral tool contracts, and adapter serialization. `tests/test_ai.py` covers configuration, mocked Ollama client behavior, and AIService turn/history, trimming, clearing, and error behavior.
- **AI orchestration:** `tests/test_roles.py`, `tests/test_teaching.py`, and `tests/test_teacher_quality.py` cover role/language decisions, tool scoping, session-local teaching state, response validation, bounded retry, and fallback behavior. These tests do not establish multi-user or API request isolation.
- **Memory:** `tests/test_memory.py` covers SQLite setup and CRUD/search, parameterized search, limits, obvious credential rejection, memory-intent handling, and limited matching-memory retrieval. It does not cover API authorization, owner/tenant isolation, migration, backup, or retention services.
- **Tools:** `tests/test_tools.py` covers registry instance isolation, schema validation, confirmation, and structured safe failures. `tests/test_ai_tool_calling.py` covers provider/tool orchestration, malformed, unregistered, or confirmation-required calls, timeouts, failure mapping, and iteration limits.
- **CLI and optional integrations:** `tests/test_dev_ai.py` covers CLI commands, interactive history, startup/provider error reporting, and optional tool setup. `tests/test_web_search.py` covers search configuration and bounded tool behavior; `tests/test_web_search_integration.py` exercises the mocked optional-search path through the CLI. `tests/test_file_search.py` covers bounded file-search behavior, configuration, and tool integration.
- **Gaps:** No inspected test exercises a Veronica HTTP route/server, API authentication/authorization, remote deployment, tenant ownership, shared application-service composition, or context isolation across simultaneous requests/users. `tests/test_ai.py` verifies history within one AIService instance, not cross-instance or cross-principal isolation.

All statements above describe existing test cases by static inspection only; no tests were run for this verification. Future application/use-case, authorization, API contract, and request-isolation tests described elsewhere in this plan remain proposed and require an approved implementation phase.

### Existing strengths to retain

- Provider-neutral interfaces and typed provider failures.
- A provider factory with Ollama as the current default.
- A distinct AI orchestration service, which is a candidate to evolve rather than duplicate.
- Explicit local memory operations and SQLite connection scoping.
- An instance-level tool allowlist, parameter validation, bounded tool dispatch, and optional confirmation.
- A CLI that composes services without requiring a server.

### Missing capabilities

- A shared application composition root and transport-neutral use cases.
- A defined request/principal context for authorization and resource ownership.
- Safe session/context isolation across concurrent requests and users.
- A backend lifecycle, API transport, authentication/authorization implementation, rate/resource limits, and API tests.
- A general governed knowledge store/retrieval service and a Veronica-owned answer brain/inference engine.
- Approved retention, identity, data migration, backup, and multi-user persistence policies.

## 3. Architecture principles and boundaries

1. **One application semantics, multiple adapters:** CLI and future API handlers invoke the same use cases; clients must not reimplement business policy.
2. **Transport independence:** Application inputs/results do not contain HTTP requests, response codes, framework models, or provider-specific payloads.
3. **Provider neutrality:** Application services depend on `AIProvider`-style contracts. Ollama serialization stays in its adapter; native inference remains a future implementation.
4. **Explicit dependency composition:** Construct providers, memory, tools, and repositories in a composition/bootstrap boundary and inject them. Avoid module-global mutable service instances.
5. **Explicit request and owner context:** The authenticated principal comes from trusted server-side identity resolution, not a caller-supplied user ID. Use cases check scopes and resource ownership before data access or side effects.
6. **Session isolation:** Each chat turn receives only its request-scoped context or the explicitly identified, owner-authorized conversation context. No request may inherit another request's or user's in-process history.
7. **Separate state classes:** Keep transient conversation context, durable user-approved memory, governed knowledge, configuration, audit metadata, and model artifacts distinct.
8. **Visible failure:** Preserve typed failures and map them at adapter boundaries. A provider/database/tool failure must not become a success-shaped response or hidden provider fallback.
9. **Consent and least privilege:** Memory writes, consequential tools, and future knowledge operations require their applicable user consent and authorization. Model output cannot grant permission.
10. **Incremental adoption:** Do not change the CLI or current provider behavior as an incidental result of introducing future backend architecture.

## 4. Proposed target architecture

The following is conceptual. The API, facade, shared use-case services, identity layer, and service lifecycle are not implemented.

```text
Existing CLI (dev_ai.py)
    | direct in-process calls; no HTTP requirement
    +---------------------------------------------------+
                                                        |
Future desktop client                                   |
    | approved local API or application facade          |
    +---------------------------------------------------+--> Application/use-case services
                                                        |       |
Future web client                                        |       +--> Policy and authorization
    | authenticated API                                  |       +--> Conversation/context service
    +---------------------------------------------------+       +--> Memory service/repository
                                                        |       +--> Knowledge retrieval (future)
Authorized external applications                        |       +--> Tool policy/registry
    | versioned authenticated HTTP API                   |       |
    +--> Authentication, validation, quotas, request ID +-------+
                                                                |
                                                 Provider-neutral AI orchestration
                                                                |
                                                 Configured answer-provider adapter
                                                  Current default: Ollama
                                                  Future: Veronica-owned brain
```

The API is a future transport adapter, not the application layer itself. The CLI directly invokes in-process services. A future desktop client may use an explicitly approved local API or facade. Web and authorized external clients use an authenticated/versioned API if separately approved. Each client path ultimately uses the same application semantics and provider-neutral service contracts.

## 5. Proposed layers and responsibilities

| Layer | Responsibility | Must not own |
|---|---|---|
| Client adapters | Translate CLI commands or UI actions into application inputs; display results and ask for user confirmation. | Direct database access, provider wire formats, authorization decisions, or unrestricted tool execution. |
| Transport adapter (future API) | HTTP routing, versioning, request/response validation, request IDs, content limits, authentication middleware integration, and conversion of application results/errors to HTTP. | Business rules, SQL, provider orchestration, implicit memory writes, or identity inferred from request bodies. |
| Identity and authorization boundary | Resolve a trusted principal/client; check operation scopes, owner/tenant/resource access, consent, quota, and tool permission. | Treating authentication as blanket authorization, trusting model output, or granting access because a caller knows an ID. |
| Application/use-case layer (proposed) | Coordinate one user operation such as a chat turn, conversation lifecycle action, memory operation, knowledge search, or model/health query. | HTTP status codes, CLI rendering, provider-specific payloads, direct framework types, or hidden persistence choices. |
| Domain/policy contracts | Define transport-neutral request/result types, policies for memory/knowledge/tool use, and typed application errors. | Duplicating the existing provider contract without need or claiming policy is implemented before it is. |
| Service adapters | Wrap existing AI, memory, tool, and future knowledge capabilities for use by application operations. | Widening permissions beyond the principal/consent provided by the application boundary. |
| Infrastructure adapters | Provider factory/client, SQLite memory store, future repositories/indexes, configuration, clock/ID sources, and optional network services. | Becoming the source of user-facing business policy. |
| Composition and lifecycle (proposed) | Validate configuration, construct dependencies, expose a service bundle to CLI/API adapters, and manage startup/shutdown/readiness. | Starting an unauthorized server, silently downloading assets, or creating global cross-user mutable sessions. |

These are logical boundaries. A future implementation may use fewer Python packages if the dependencies remain clear and testable; this plan does not require a particular directory structure.

## 6. Shared application/use-case service design

### Application operations

The initial conceptual use-case surface is:

| Operation | Purpose and boundary |
|---|---|
| `generate_chat_turn` | Validate a user message and request context, authorize any conversation/memory/knowledge/tool use, call provider-neutral orchestration, and return a transport-neutral result. |
| `create_conversation` / `get_conversation` / `delete_conversation` | Manage an explicitly owner-bound conversation resource under the approved ephemeral/persistence policy. |
| `list_memories` / `search_memories` / `save_memory` / `delete_memory` / `clear_memories` | Wrap current memory operations with user/owner authorization, consent, and safe outcomes before any API exposure. |
| `search_knowledge` | Future operation over approved, access-controlled collections with source provenance; no ingestion is implied. |
| `get_model_metadata` / `get_readiness` | Return truthful configured provider capability/readiness information without leaking secrets or internal paths. |

Names are illustrative and do not define Python APIs or authorize route creation. Each operation should accept validated values and a server-constructed actor/request context, then return a typed result or a specific application error. It should not accept a framework `Request`, `Response`, HTTP status, or untrusted `principal_id` as proof of identity.

### Application operation flow

1. Adapter validates the transport/command shape and resolves the caller identity where applicable.
2. Construct a request context containing a correlation ID, authenticated principal/client (for API calls), and trusted permission/consent evidence. CLI identity remains local/operator context until separately designed.
3. Validate operation inputs, limits, and resource ownership before loading private context.
4. Apply explicit policy to memory, knowledge, and tools; only authorized resources are supplied to orchestration.
5. Call the provider-neutral AI service and configured infrastructure adapters.
6. Return typed application results; adapters render CLI output or convert results/errors to the approved API schema.
7. Emit only approved redacted operational/audit metadata. Do not persist prompts or conversations implicitly.

## 7. AI orchestration and provider integration

### Existing service and reuse boundary

`AIService` currently owns more than a narrow provider call: it has mutable message history, selected role, teaching-session state, memory intent/retrieval behavior, tool gating, provider invocation, response validation, and history mutation. Its `respond(user_message)` API has no explicit principal, conversation ID, per-turn memory policy, cancellation token, or request-context object. It is a useful behavior source and candidate orchestration component, but it cannot be assumed safe as one shared mutable service instance for concurrent API users.

Before any future API integration, an approved design must decide how to separate or parameterize:

- Stateless per-turn orchestration from conversation/session state.
- Conversation loading/appending and owner authorization from prompt construction.
- Memory intent/save policy and memory retrieval policy from generic provider invocation.
- Tool request parsing from authorization and confirmation.
- Provider failure handling from CLI-specific error rendering.

Do not silently remove current CLI behavior while factoring these concerns. Retain the current provider default and test parity explicitly.

### Provider boundary

- Use the existing `AIProvider`, provider factory, metadata/capabilities, and typed errors as the provider adapter boundary where they meet the future application's needs.
- Keep provider selection under trusted application/operator configuration; do not allow a chat request to select an arbitrary provider, endpoint, or local model path.
- Ollama remains current/default until a Veronica-owned brain independently passes model, tokenizer, inference, quality, language, security, resource, and offline gates and separate provider-switch approval is granted.
- Do not represent Ollama as Veronica-native and do not silently fall back to external AI in a native-only mode.
- The proposed application result should expose truthful provider/mode metadata without copying provider-specific wire formats.
- No brain, tokenizer, model weights, training process, or provider replacement is designed for implementation in this phase.

## 8. Conversation and request context isolation

Conversation context is a first-class service boundary, not a global property of a shared AI service.

- A one-shot chat operation must be isolated from every other request, conversation, CLI session, and principal. It may use only the current request and explicitly authorized resources selected for that request.
- A continuing turn may load prior messages only from the explicitly identified conversation after verifying the authenticated owner and `conversation:read` permission. Appending the new turn requires `conversation:write`, or a separately approved `conversation:turn` permission explicitly defined to include both read-context and append-turn for that owned conversation. The permission choice remains pending user approval under C3D-12.
- Context objects must be immutable/copy-isolated at adapter boundaries where mutation could cross turns. Session caches, if later introduced, must be keyed by trusted owner and conversation identity and enforce expiry and access checks on every use.
- Never store per-user history in a singleton `AIService`, provider instance, or application-global list. Stateless shared dependencies may be reused only when concurrency-safe.
- Ephemeral versus persistent conversation state, size/TTL limits, transcript reads, restart semantics, and deletion are undecided and require explicit approval.
- These are target requirements. Current `AIService` has instance-held message/role/teaching state; this plan does not claim that cross-request/API-user isolation is already implemented.

Isolation acceptance tests, before future API use:

1. Interleave two one-shot requests and prove neither receives the other's user/assistant messages.
2. Interleave two users' conversations and prove no cross-owner reads, appends, or cache reuse.
3. Prove a one-shot request never reads an implicit conversation history.
4. Prove a continuing turn receives only its owner's selected conversation context.
5. Exercise clear, expiry, failure, cancellation, and retry paths without retaining or replaying another turn's context.

## 9. Memory, knowledge, and tool service boundaries

### Personal memory

- Reuse `MemoryService` for its current local operations only after an application boundary supplies consent and owner policy.
- Keep personal memory separate from transient conversation context, knowledge sources/indexes, and training data.
- Current CLI memory save intent is explicit, but matching memories may be retrieved on ordinary turns when memory service is enabled. The future API's retrieval policy must be separately approved and accurately disclosed.
- `MemoryService` currently accesses SQLite directly through `MemoryDatabase`; there is no repository interface, owner/tenant schema, migration service, or authenticated API. Any future abstraction or schema change requires separate implementation and migration approval.
- Never convert memory writes into automatic transcript saves or training examples.

### Knowledge

- No general knowledge-ingestion/indexing service was found.
- Treat future knowledge search as a distinct, permission-checked use case with approved sources, provenance, source ACLs, bounded excerpts, and deletion rules.
- Search approval does not grant ingestion, web scraping, dataset acquisition, or training rights.

### Tools

- Reuse the instance-scoped `ToolRegistry` and bounded `ToolCallingService` as execution infrastructure where appropriate.
- The application/policy layer must intersect a user's request with configured allowlists, authenticated scopes, tool-specific policy, schema validation, and explicit confirmation.
- A model-generated tool call is untrusted data, not a principal or permission. Avoid allowing transport handlers to call `Tool.execute` directly.
- Tool outcomes should remain typed and safe; logs should omit private arguments/results as current registry behavior intends.

## 10. Composition root and dependency lifecycle

### Existing composition

`dev_ai.main()` currently reads feature configuration, creates and validates the provider, initializes `MemoryService`, optionally creates a `ToolRegistry` and `ToolCallingService`, constructs one `AIService`, and then owns the interactive loop. `app.main()` is separate and minimal. There is no shared application container or service lifecycle abstraction.

### Proposed future composition

After decisions and a separate implementation authorization, a small composition boundary could:

1. Load and validate environment-backed configuration once, without printing secrets.
2. Create the selected provider through the existing registry; preserve Ollama as the default.
3. Create local memory and optional tool adapters only when permitted and configured.
4. Construct request-scoped application services and explicit policies; avoid global user/session state.
5. Expose a service bundle to the CLI directly and to an API adapter only when that API is authorized.
6. Provide lifecycle hooks for startup checks, readiness, bounded shutdown, and resource cleanup if a server is separately approved.

The composition API, service lifetime, dependency scope, and directory structure are unresolved design details. Do not add a framework-specific dependency container without evidence that it is needed. A CLI-only composition must not start a listener as a side effect.

## 11. Client and transport integration

| Client | Proposed path | Status and boundary |
|---|---|---|
| Existing `dev_ai.py` CLI | Direct in-process application/use-case services. | Existing CLI remains usable without HTTP; preserve current command/provider behavior unless separately approved. |
| `run.py` / `app.main` | May become an explicitly chosen application/backend entry point in a future implementation. | Currently only a minimal scaffold; unification with the CLI is not assumed. |
| Future desktop | Approved local API or application facade, as decided in a separate phase. | Not implemented; requires UX, identity, memory consent, tool confirmation, and local security decisions. |
| Future web | Authenticated API with reviewed browser-session, origin, CSRF, and safe-rendering controls. | Not implemented; loopback alone is not authentication. |
| Authorized external applications | Versioned HTTP API, per-client identity/scopes, quotas, revocation, and documented data handling. | Not implemented; LAN/remote/public exposure requires separate approval. |

All clients should use the same application semantics and provider-neutral services, but they do not have to communicate through the same transport. The CLI does not have to communicate through HTTP. Do not expose Ollama-specific API payloads as Veronica's permanent contract.

## 12. Persistence, configuration, and observability boundaries

- Keep current SQLite memory semantics and schema unchanged in this planning phase.
- Keep conversation context ephemeral by default in proposed backend designs unless a future user decision explicitly approves persistence.
- Do not mix account/authorization metadata, memory, conversation records, knowledge documents/indexes, audit events, and model artifacts into one undifferentiated store.
- Do not add database migrations or select a future database. SQLite remains a candidate for the existing local single-user memory scope, not an already-approved multi-user service database.
- Treat configuration as trusted operator input. API clients must not set environment variables, secrets, provider endpoints, filesystem roots, or model paths.
- Use request/correlation IDs and redacted operational outcomes in a future service. Do not log full prompts, memory contents, credentials, or raw tool inputs/results by default.
- Readiness should reflect the configured provider and required dependencies, not merely whether a server process is alive. Health endpoints, if authorized, must not reveal secrets or personal data.
- Backups, retention, recovery, audit access/retention, and user-data export/deletion remain pending decisions.

## 13. Security, concurrency, and operational requirements

Before a future API implementation:

- Approve authentication, principal/client identity, credential provisioning/rotation/revocation, permissions, and ownership checks. Authentication is not authorization.
- Approve local-only versus LAN/remote deployment boundaries; never expose a listener publicly by default. A loopback bind does not authenticate callers or prevent browser-origin attacks.
- Bound request sizes, output tokens, concurrent inference, queues, provider deadlines, tool loops, and memory/knowledge result sizes using measured resource limits.
- Keep blocking provider, SQLite, and tool operations from exhausting an async event loop or worker pool. Choose a sync/worker/process strategy only after framework and hardware decisions; do not assume cancellation stops a running model call.
- Make failure, timeout, cancellation, provider-unavailable, and retry/idempotency behavior explicit. No silent AI provider fallback or success-shaped error.
- Enforce per-operation scopes and resource ownership before reading or mutating memory, conversation, knowledge, or tools.
- Provide browser CSRF/origin/content-security policies if a web client is approved; require TLS and operational controls for any remote access.
- Enforce offline/egress policy at service boundaries. Online search and speech remain optional and separately disclosed.
- Define redacted audit events and privacy-safe logs before external client access.

## 14. Language and answer ownership requirements

- English, Hindi written in Devanagari, and Hinglish written in Roman Hindi/code-switching remain co-equal priorities.
- Mixed-script text is a separate evaluation/reporting group; do not fold it into a single aggregate that conceals differences.
- Preserve Unicode through clients, application inputs/results, memory/knowledge boundaries, provider adapters, and error messages. Do not automatically transliterate or normalize user text.
- Future acceptance reviews must report per-language answer quality, instruction following, tool behavior, Unicode handling, latency, and failure rates separately, with mixed-script reported separately. Thresholds require approval before evaluation.
- The final answer in Veronica's long-term target must be generated by the Veronica-owned brain. Retrieval, memory, tools, and optional online evidence may inform the answer but do not replace the answer generator.
- The current configured Ollama provider remains the working transitional provider until independent native-model and runtime gates pass and separate switch approval is recorded.

## 15. Dependency-aware roadmap and approval gates

Every item below is a proposed future stage, not implementation authorization.

| Stage | Scope and deliverable | Prerequisite/exit gate |
|---|---|---|
| 3E-0: Decisions and threat model | Resolve application/service responsibilities, identity, context/session lifecycle, persistence, framework, deployment audience, and security model. | User decisions recorded; threat/data-flow model; Phase 3C and C3D decisions still pending until explicitly resolved. |
| 3E-1: Application boundary design | Specify transport-neutral use-case inputs/results/errors, dependency lifecycle, state scoping, and CLI parity plan. | Approved bounded implementation scope; preserve CLI/default-provider behavior with a regression baseline. |
| 3E-2: Shared composition/use cases | If authorized, factor or add composition/use cases while keeping the CLI direct/in-process. | Design approved; focused tests prove existing CLI behavior and request/session isolation. No HTTP listener. |
| 3E-3: Local API foundation | Separately select/install a framework and implement only approved local API lifecycle/health/model metadata. | Framework/dependency/security decisions; identity/auth tests; loopback and no-public-bind controls; explicit API authorization. |
| 3E-4: Chat/conversation API | Add authorized chat and ephemeral conversation operations if approved. | API foundation, read/write permission decision, owner isolation, context lifecycle, limits, cancellation/idempotency, and tests. |
| 3E-5: Memory/knowledge operations | Expose explicit memory and governed search use cases only after individual data decisions. | Consent receipts, scopes/ownership, source rights/provenance, retention/deletion, and migration approval if needed. |
| 3E-6: Clients and deployment | Integrate desktop/web/external clients and any LAN/remote operation. | Stable API, client-specific auth, browser/network security, operations/incident ownership, language/accessibility acceptance. |
| Separate native-brain work | Build and validate Veronica-owned weights, tokenizer, and inference runtime; integrate behind provider-neutral boundary and consider replacement. | Independently approved model/data/runtime work, capability and language tests, hardware/security/offline gates, rollback, and a separate provider-switch approval. |

### Required approval gates before implementation

- [ ] Resolve the applicable Phase 3C and Phase 3D decisions; recommendations are not approvals.
- [ ] Approve the application/use-case contracts, composition strategy, dependency scopes, and CLI compatibility requirements.
- [ ] Approve the conversation context ownership and read/write authorization model, including one-shot isolation requirements.
- [ ] Approve identity, data handling, consent, retention, deletion, backup, and migration boundaries for every operation in scope.
- [ ] Approve framework/dependencies and local versus remote exposure separately; public exposure remains off by default.
- [ ] Define measurable resource budgets, concurrency strategy, provider deadlines, cancellation guarantees, and failure behavior.
- [ ] Approve focused tests for service composition, CLI parity, authorization-negative cases, context isolation, Unicode/language reporting, and offline egress as applicable.
- [ ] Obtain explicit user authorization naming the implementation scope and exclusions.

Passing these gates would authorize only the specifically named work. It would not authorize model/data experiments, training, migrations, public deployment, or provider replacement unless those are separately approved.

## 16. Pending decisions

The following remain open; the recommendations in this plan do not resolve or pre-approve them:

1. Whether to create a shared composition root and how much existing CLI setup to factor.
2. Whether `AIService` is refactored, wrapped, or replaced as the orchestration service while preserving CLI behavior.
3. The lifetime and ownership model for application services, provider clients, sessions, and conversation context.
4. The conversation read/write permission pair versus a `conversation:turn` scope; this remains pending under C3D-12.
5. API framework and dependency/version policy; FastAPI is a prior-phase candidate, not selected.
6. Identity, authentication, authorization scopes, local-only versus multi-user operation, and remote access.
7. Ephemeral conversation limits/expiry and any future persistence, export, backup, or deletion behavior.
8. API-specific memory retrieval defaults and consent UX; current CLI retrieval behavior must not be misrepresented.
9. Knowledge store/index technology, source governance, and collection/source access control.
10. Provider/inference worker topology, concurrency/resource limits, cancellation, and operational monitoring.
11. Database evolution, migrations, encryption/key management, backups, retention, and recovery.
12. Desktop/web/external application scope and whether any listener is permitted.
13. Native brain ownership, evaluation thresholds, and provider-switch acceptance gates.

## 17. Explicit exclusions and authorization boundaries

This is a read-only inspection and documentation-only plan. It does **not** authorize:

- Modifying source code, tests, configuration, dependencies, databases, schemas, or existing documentation.
- Creating an application service, composition root, API route, endpoint, server, authentication system, or client integration.
- Installing/selecting packages or changing the Python environment.
- Starting or binding any network listener.
- Changing `dev_ai.py`, `run.py`, `app.main`, provider defaults, Ollama behavior, memory behavior, or tool behavior.
- Database migrations or persistent transcript storage.
- Dataset/model download, corpus processing, tokenizer experiment/fitting, model training, or inference implementation.
- Replacing Ollama or representing its output as native Veronica output.
- Commit, amend, push, or publish.

Phase 2G D-01 remains approval of the tokenizer-comparison objective only. D-02 through D-18 remain pending. No tokenizer experiment, model training, provider integration, or provider replacement is authorized here. Phase 3C and Phase 3D recommendations remain recommendations unless separately approved.

## Final status

**BACKEND APPLICATION LAYER AND SHARED SERVICE ARCHITECTURE PLANNED — NO IMPLEMENTATION PERFORMED — ALL IMPLEMENTATION AND EXPERIMENTS REMAIN UNAUTHORIZED.**

The recommended direction is to preserve Veronica's provider-neutral contracts and useful existing services, introduce an explicitly composed transport-independent use-case boundary only in a future approved phase, and keep `dev_ai.py` as a direct in-process client. A future authenticated API may reuse those use cases without becoming a requirement for CLI operation. The stateful current `AIService` must not be treated as a cross-user singleton; request/conversation isolation must be established and tested before API use. Ollama remains the current working provider until native replacement gates and separate approval are satisfied.

## Inspection record

Read-only inspection for this plan covered:

- `docs/PHASE_3A_COMPLETE_INDEPENDENT_AI_SYSTEM_ARCHITECTURE_PLAN.md`: current architecture, backend/API, memory/storage, dependency flow, roadmap.
- `docs/PHASE_3B_CORE_SYSTEM_REQUIREMENTS_AND_BACKEND_API_CONTRACT_PLAN.md`: verified baseline, backend layers, provider/memory/storage and client requirements, implementation roadmap.
- `docs/PHASE_3C_API_SECURITY_IDENTITY_PERSISTENCE_AND_FRAMEWORK_DECISION_CLOSURE.md`: current-state verification, framework options, authorization, persistence, and approval gates.
- `docs/PHASE_3D_API_CONTRACT_FINALIZATION_AND_CLIENT_INTEGRATION_ARCHITECTURE_PLAN.md`: API contracts, client transport split, context isolation, authorization, pending decisions, and implementation gates.
- `app/ai/base.py`, `app/ai/provider.py`, `app/ai/service.py`, `app/ai/tool_calling.py`, and `app/ai/__init__.py`.
- `app/memory/database.py`, `app/memory/models.py`, and `app/memory/service.py`.
- `app/tools/base.py` and `app/tools/registry.py`.
- `app/config.py`, `app/services/__init__.py`, `app/main.py`, and `dev_ai.py`.
- Repository search for existing HTTP frameworks, API routes, authentication, application service imports, and server entry points.
- The following test files, inspected statically for relevant coverage:
  - `tests/test_provider_contracts.py`
  - `tests/test_ai.py`
  - `tests/test_roles.py`
  - `tests/test_teaching.py`
  - `tests/test_teacher_quality.py`
  - `tests/test_ai_tool_calling.py`
  - `tests/test_memory.py`
  - `tests/test_tools.py`
  - `tests/test_dev_ai.py`
  - `tests/test_web_search.py`
  - `tests/test_web_search_integration.py`
  - `tests/test_file_search.py`

In the current document, Section 13 is titled “Security, concurrency, and operational requirements”; there is no Section 13 titled “Testing architecture.” The coverage correction is recorded in Section 2; the isolation tests in Section 8 and future test gates in Section 15 remain proposals.

No datasets, model artifacts, or user databases were accessed. Test files were inspected only; no tests were run. No source, test, configuration, dependency, database, or documentation file other than this Phase 3E document was modified. No package was installed, no experiment or training was run, and no server was started.
