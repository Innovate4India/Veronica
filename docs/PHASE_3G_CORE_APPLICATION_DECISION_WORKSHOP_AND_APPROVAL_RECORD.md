# Phase 3G: Core Application Decision Workshop and Approval Record

**Status:** Decision workshop and reconciled approval record. The approved A decisions are documented in Section 8. C3C and C3D decisions remain pending. No implementation is authorized.

## 1. Purpose, scope, and approval boundaries

This workshop consolidates open core-application decisions from Phases 3A–3F so the user can explicitly decide what, if anything, should precede application-layer implementation. It is not an implementation plan approval and does not resolve prior pending decisions by recommendation or repetition.

The target architecture retains the existing CLI as an in-process client of shared application services. HTTP must remain optional for CLI operation. Existing provider-neutral contracts should be reused. Ollama remains the current/default provider until a native Veronica model passes independent gates and the user separately approves a provider switch. `VeronicaModelProvider` is not a working answer model.

English, Hindi (Devanagari), and Hinglish (Roman Hindi/code-switching) are equal priorities. Mixed-script text requires a separate evaluation group. Native-brain development, data governance, tokenizer decisions, experiments, training, inference, and provider replacement remain separate from application-layer authorization.

Approved Phase 3G A-decisions are recorded in Section 8 from the user's explicit decisions. Recommendations are advisory and do not replace an original user decision. C3C and C3D decisions remain in their prior pending status unless separately approved. Recording an architectural decision does not authorize implementation.

This task authorizes only this document. It does not authorize source, test, configuration, dependency, database, schema, documentation-from-prior-phases, API, server, client, tokenizer, data, training, inference, or provider changes.

## 2. Verified current architecture and implementation limitations

| Area | Verified current state | Limitation relevant to decisions |
|---|---|---|
| Provider contracts and selection | Provider-neutral message, response, capability, error, and tool contracts exist. The provider registry selects Ollama by default. | They are in-process interfaces, not an API or application use-case layer. |
| Current/native provider | Ollama is the current complete text-answer provider. `VeronicaModelProvider` is an unavailable scaffold with no answer-generation capability. | There is no Veronica-owned answer-generating model or native inference runtime. |
| AI orchestration | `AIService` handles provider calls, role/teaching behavior, optional memory and tools, response validation, and bounded in-process message history. | It is synchronous and mutable: conversation messages, role, preferred role, and teaching state live on the instance. It has no authenticated principal, conversation ID, explicit request context, or ownership boundary. |
| CLI and startup | `dev_ai.py` composes provider, memory, optional tools/speech, and one `AIService` for its interactive loop. `run.py` invokes the minimal `app.main` scaffold. | No shared composition root or implemented application service exists. The CLI works without HTTP and must remain so. |
| Memory and persistence | `MemoryService` uses local SQLite for explicit save/list/search/delete/clear operations. CLI saves require explicit user intent; matching memories may be retrieved during normal turns when memory is enabled. | The schema has no owner/tenant key, and there is no API authorization, migration framework, retention/backup service, or comprehensive sensitive-data classifier. |
| Tools | `ToolRegistry` is an instance-scoped allowlist with schema checks and configured confirmation; tool orchestration is bounded. | Allowlisting and confirmation are not general user authentication/authorization. Model-generated tool calls do not authorize themselves. |
| Backend and clients | No Veronica HTTP API, server, endpoint, API authentication, desktop client, or web client is implemented. FastAPI is the selected future framework. | Package versions, identity, network exposure, clients, and API contracts remain pending implementation details or decisions. |
| Existing tests | Static review in Phase 3E/3F covered provider, AI/orchestration, memory, tools, CLI, configuration, and selected integrations. | Tests do not establish shared application composition, API authentication/authorization, tenant ownership, or cross-request/user context isolation. No tests were run for this workshop. |

These are verified implementation observations, not approval of any proposed design. For example, the CLI's in-process history does not prove that a shared `AIService` is safe for independent requests or multiple users.

## 3. Application-layer decisions A-01 through A-15

These decision IDs are retained from Phase 3F. The reconciled approvals and mapping clarifications are recorded in Section 8. Recommendations remain advisory unless explicitly superseded by a documented approval.

| ID | Decision question | Decision scope |
|---|---|---|
| A-01 | What is the smallest shared application boundary? | Retain CLI wiring, add transport-neutral use cases/composition, or adopt a larger service framework. |
| A-02 | How should `AIService` evolve? | Gradual refactor, wrapper, or replacement while preserving CLI behavior. |
| A-03 | What are service and dependency lifetimes? | Per-request, process-level, bounded-worker, or explicitly mixed scopes. |
| A-04 | What conversation permission is required for a chat turn? | `conversation:read` plus `conversation:write`, or a dedicated `conversation:turn` with explicit read-and-append semantics. |
| A-05 | How are one-shot and continuing requests isolated? | Request-scoped context, explicit owner-bound conversation, or shared service history. |
| A-06 | What local identity/authentication applies if an API is built? | No auth, OS identity, local credential, short-lived scoped token, or IPC. |
| A-07 | Is multi-user support in scope? | Single-user local only, future multi-user, or both. |
| A-08 | What is the API conversation retention policy? | Ephemeral, opt-in persistence, or persistent by default. |
| A-09 | What memory behavior is permitted? | Current CLI behavior only, API opt-in retrieval, preference-based retrieval, or explicit operation per use. |
| A-10 | Which framework/dependencies should be adopted? | No API yet, FastAPI, Flask, Starlette, or another reviewed option. |
| A-11 | Which clients and transport modes are in scope? | CLI only, future desktop, future web, or external/remote clients. |
| A-12 | Is any network listener allowed? | No listener, authenticated loopback, LAN, or remote. |
| A-13 | What are concurrency, timeout, cancellation, and retry semantics? | Bounded synchronous work, worker/process, streaming/jobs, and cancellation/retry guarantees. |
| A-14 | What tool authorization and confirmation model applies to clients? | CLI policy only, per-client scopes, per-tool permission and confirmation. |
| A-15 | How may persistence evolve beyond current SQLite memory? | Keep existing local scope, approve schema extension, or consider a server database. |

## 4. Relevant unresolved Phase 3C and 3D decisions

C3C-01 framework selection is resolved in favor of FastAPI; its package/version/dependency review remains a separate implementation detail. C3C decisions C3C-02–C3C-18 and C3D decisions C3D-01–C3D-16 remain pending from their respective plans. The workshop retains them because they affect application boundaries, security, identity, persistence, API contracts, client behavior, or implementation readiness. A decision in one family does not automatically resolve an overlapping decision in another family.

| Decision family | Included open topics |
|---|---|
| C3C framework/deployment | Framework, topology, local identity/authentication, multi-user identity, token lifecycle, permissions, network exposure. |
| C3C data/security | Conversation persistence, memory consent/retrieval, initial and future database, retention/backups, resource limits, audit/error detail, secret storage, API contract, online egress. |
| C3D API contract | Versioning, chat route, stateless/conversation behavior, identifiers, memory and knowledge contracts, model metadata, errors/statuses, streaming, timeout/cancellation, idempotency, authorization/ownership, client connectivity, browser/external auth, online/offline behavior, language evaluation. |

Detailed decision records with options and technical implications are in Section 8. No prior status is changed by including a decision in this workshop.

## 5. Recommendation comparison — advisory, not selection

The comparisons below are intended to help evaluate choices. None constitutes user approval.

| Topic | Available choices | Benefits and trade-offs | Dependencies | Compatibility risks | Clearly marked recommendation |
|---|---|---|---|---|---|
| Application boundary and composition (A-01, A-03) | Keep direct CLI construction; introduce a minimal transport-neutral use-case/composition layer; adopt a broader service framework. | Direct construction has no migration cost but duplicates wiring. A small boundary enables reuse and focused testing but requires a careful refactor. A larger framework adds lifecycle/dependency complexity. | Characterize current CLI behavior; define request and dependency lifetimes. | Changing CLI construction can alter defaults, startup errors, memory/tool behavior, or interactive history. | **Recommendation:** evaluate the smallest explicit composition/use-case boundary, keeping `dev_ai.py` a direct in-process caller. |
| AIService evolution (A-02, A-05) | Refactor gradually; wrap unchanged; replace. | Wrapping is initially small but preserves shared mutable state. Replacement is clean in theory but has the highest behavior-regression risk. Gradual refactoring supports parity checks but needs careful separation. | Identify stateful behavior and all call sites; add isolation tests before multi-request use. | Role/teaching session, history, memory retrieval, tool limits, and error behavior may change. | **Recommendation:** gradual, compatibility-preserving refactor; do not treat a wrapper as an isolation solution. |
| Request/conversation authorization (A-04, A-05; C3D-12) | Paired read/write scopes; dedicated `conversation:turn`; implicit shared history. | Paired scopes are explicit but require both grants. The approved dedicated turn scope means reading context and appending a turn only for an owned conversation. Shared history is unsafe for request isolation. | Identity, ownership, scope matrix, concurrency policy. | Existing CLI history is session-local and cannot be equated with API principal ownership. | **Recommendation:** use the approved dedicated `conversation:turn` form. Separately resolve principal definitions, the complete scope matrix, resource ACL boundaries, ownership verification, and enforcement failures. One-shot requests should be strictly request-scoped. |
| Framework and API topology (A-10–A-12; C3C-01/02/08; C3D-13) | In-process only; one local API; FastAPI or alternatives; LAN/remote later. | In-process minimizes dependencies and attack surface. A local API enables separate clients but adds authentication, browser, lifecycle, and dependency burdens. Remote operation adds substantial operations/security cost. | Application boundary, identity, deployment audience, resource strategy, framework review. | Making HTTP mandatory would break the required CLI usage model; multiple model workers may duplicate memory use. | **Recommendation:** keep first application work in-process; evaluate a future authenticated loopback API separately. FastAPI is selected for the future framework. |
| Identity and authorization (A-06/07/14; C3C-03–07; C3D-12/14) | No auth/local trust; OS identity; local credential/token; OS IPC; future federation. | Simplicity trades off attribution and local process/browser protection. Scoped, revocable identity enables least privilege but requires secure issuance, storage, rotation, and recovery. Multi-user federation adds operational dependencies. | Supported clients, principal model, resource ownership, secret storage, browser policy. | Static shared secrets or loopback trust may not safely support desktop/web or multiple users. | **Recommendation:** no unauthenticated API; if separately approved, use authenticated, least-privilege local access and defer multi-user until designed. |
| Persistence and consent (A-08/09/15; C3C-09–13; C3D-03/05/06) | Ephemeral context; explicit opt-in persistence; persistent by default; current SQLite or future store. | Ephemeral minimizes data risk but loses history. Persistence enables continuity but adds ownership, retention, export/deletion, backup, and migration requirements. Current SQLite fits the existing local memory use only. | Identity/ownership, consent UX, deletion, backup, migration/recovery. | Persisting chats would change current CLI semantics; current memory schema cannot isolate tenants. | **Recommendation:** no durable conversation persistence in an initial application boundary; retain existing SQLite semantics without schema changes. |
| Runtime limits, cancellation, and idempotency (A-13; C3C-14; C3D-09–11) | Bounded synchronous; worker/process; stream/job model; best-effort or explicit cancellation; retries with/without idempotency. | Bounded synchronous work is simpler but may wait longer. Workers and streaming increase lifecycle complexity. Unspecified retries risk duplicate tool effects; cancellation may not stop an active model call. | Hardware/provider measurements, client deadlines, tool side-effect analysis. | Existing provider and service calls are synchronous; falsely promising cancellation or retries could change outcomes. | **Recommendation:** measure before setting limits; use bounded work and explicit failure semantics, and do not enable retries for side effects without idempotency rules. |
| Native brain and provider transition | Keep Ollama; add a non-default native provider later; switch default. | Keeping Ollama preserves working behavior. A non-default native adapter allows validation. Switching before evidence risks quality, safety, offline, and hardware failures. | Model/data/tokenizer/runtime gates, independent validation, rollback, separate switch approval. | Replacing Ollama now would break the current answer path; native scaffold is not functional. | **Recommendation:** retain Ollama as current/default; do not integrate or switch a native provider until separate gates pass. |

## 6. Minimum safe first implementation scope

The following is a **candidate scope for discussion only**, not a selected or authorized implementation:

- Introduce only the smallest transport-neutral application operation(s) and composition boundary necessary for the existing CLI to call shared services directly.
- Preserve `dev_ai.py` as an in-process client; do not require HTTP or a running server.
- Preserve provider-neutral contracts and current Ollama default/behavior.
- Avoid shared cross-request session state. One-shot work must use request-scoped context; explicit conversation ownership and permission semantics must be decided before supporting continuing multi-user requests.
- Keep current memory behavior and database schema unchanged unless the user explicitly scopes a change.
- Maintain the current tool allowlist/confirmation boundaries; do not expose tools through a new client without separate authorization.
- Add focused tests only for newly changed application composition, CLI parity, provider failures, and request isolation as applicable.

Before any code begins, the user must approve the exact scope, files, behavior, tests, dependencies (if any), and exclusions. A user may choose a narrower scope or no implementation.

## 7. Explicit exclusions from the candidate first implementation

Unless separately and explicitly authorized, the first application-layer implementation must exclude:

- HTTP routes, API/server lifecycle, framework or dependency installation, and any network listener.
- Making HTTP mandatory for CLI, desktop/web client integration, external applications, LAN/remote/public access.
- Authentication/account systems, multi-user support, or claims that loopback alone authenticates callers.
- Durable conversation transcripts, database/schema changes, migrations, backups, retention services, or multi-tenant persistence.
- Memory API, knowledge database/indexing/ingestion, web scraping, or source acquisition.
- Automatic training on conversations, SQLite memory, prompts, logs, or personal data.
- Changes to provider behavior/default, removal of Ollama, native provider integration, or provider switching.
- Tokenizer experiments/fitting, data acquisition, model training/fine-tuning, model downloads, or inference implementation.
- Any change to English, Hindi, or Hinglish priority; mixed-script evaluation remains separate.
- Commits, pushes, releases, or publication.

## 8. Decision approval record

The A-01 through A-15 architectural decisions below reflect the reconciled, previously communicated approvals. Approval of an architecture or direction is separate from authorization to implement it. FastAPI framework selection is resolved under A-10/C3C-01; C3C-02 through C3C-18 and C3D-01 through C3D-16 remain pending and are not changed by this record.

### 8.1 Phase 3F application-layer decisions

#### A-01 — Shared application boundary

- **Question:** What is the smallest shared application boundary?
- **Available options:** Keep direct CLI wiring; introduce transport-neutral use cases and explicit composition; adopt a broader service framework.
- **Technical implications:** A boundary can centralize semantics and improve testability; it must not add HTTP or global mutable request state.
- **Recommendation:** Evaluate a minimal use-case/composition layer; keep CLI calls direct and in-process.
- **Approved architectural decision:** Small shared application layer with transport-neutral use cases and explicit composition; preserve the existing CLI and support future clients.
- **Mapping:** **Exact match** — Option 2 is equivalent to the approved small shared application layer.
- **User decision:** APPROVED.
- **Approval status:** APPROVED.

#### A-02 — AIService evolution

- **Question:** Should `AIService` be refactored, wrapped, or replaced?
- **Available options:** Gradual refactor; wrapper around current service; replacement.
- **Technical implications:** The service holds history, role, preferred role, teaching state, and orchestration behavior. Wrapping alone does not isolate those fields.
- **Recommendation:** Gradual compatibility-preserving refactor, only after characterizing CLI behavior.
- **Approved architectural decision:** Gradually refactor the existing `AIService`.
- **Mapping:** **Exact match** — Option 1, gradual refactor.
- **User decision:** APPROVED.
- **Approval status:** APPROVED.

#### A-03 — Dependency and service lifetimes

- **Question:** Which dependencies are process-, request-, conversation-, or worker-scoped?
- **Available options:** Per-request construction; process-level services; bounded worker; explicitly mixed scopes.
- **Technical implications:** Shared provider clients require concurrency-safety evidence; conversation state must not be global; multiple workers may duplicate model resources.
- **Recommendation:** Immutable validated configuration at process scope, request-scoped context, and owner-bound conversation state; verify provider lifetime empirically.
- **Approved architectural decision:** Use mixed explicit process, request, conversation, and worker dependency scopes.
- **Mapping:** **Exact match** — Option 4, explicitly mixed scopes.
- **User decision:** APPROVED.
- **Approval status:** APPROVED.

#### A-04 — Conversation turn permissions

- **Question:** What permission authorizes a turn that reads existing context and appends a turn?
- **Available options:** Require `conversation:read` and `conversation:write`; use `conversation:turn` explicitly granting both operations for an owned conversation.
- **Technical implications:** Both models require server-side ownership checks; a turn permission must not grant unrelated conversation access or transcript export.
- **Recommendation:** Require both read and append semantics; leave the scope representation to the user.
- **Approved architectural decision:** Use a dedicated `conversation:turn` permission that reads context and appends a turn only for an owned conversation, with server-side ownership verification.
- **Mapping:** **Exact match** — Option 2.
- **User decision:** APPROVED.
- **Approval status:** APPROVED.

#### A-05 — One-shot and continuing request isolation

- **Question:** How should request context be isolated?
- **Available options:** Request-scoped context; explicitly owner-bound conversation context; shared service history.
- **Technical implications:** `AIService` history is mutable and cannot safely serve as implicit context for unrelated API requests or users.
- **Recommendation:** Isolate one-shot requests completely; use only explicitly selected and authorized conversation context for continuing turns.
- **Approved architectural decision:** Isolate one-shot requests with request-scoped context.
- **Mapping:** **Exact match** — Option 1.
- **User decision:** APPROVED.
- **Approval status:** APPROVED.

#### A-06 — Local identity and authentication

- **Question:** What identity/authentication applies if a local API is later approved?
- **Available options:** No authentication; OS identity; per-install credential; short-lived scoped bearer token; OS IPC.
- **Technical implications:** Loopback does not establish caller identity; credential issuance, storage, expiry, revocation, and browser handling are needed.
- **Recommendation:** Do not expose an unauthenticated API; choose a mechanism only after client/platform review.
- **Approved architectural decision:** Use a per-install credential for local API authentication.
- **Mapping:** **Exact match** — Option 3.
- **Preserved security direction:** Store credentials securely and never expose API keys or secrets in logs.
- **User decision:** APPROVED.
- **Approval status:** APPROVED.

#### A-07 — Multi-user scope

- **Question:** Is multi-user operation in scope?
- **Available options:** Single-user local only; future multi-user; both.
- **Technical implications:** Multi-user support requires identity, per-resource ownership, tenant isolation in storage/cache/logs/jobs, and operational controls.
- **Recommendation:** Defer multi-user support until those requirements are defined.
- **Approved architectural decision:** Support both single-user local operation and future multi-user operation.
- **Mapping:** **Exact match** — Option 3.
- **User decision:** APPROVED.
- **Approval status:** APPROVED.

#### A-08 — Conversation retention

- **Question:** What is the API conversation retention policy?
- **Available options:** Ephemeral only; user-opt-in persistence; persistent by default.
- **Technical implications:** Persistence changes privacy, deletion, export, backup, and storage requirements; ephemeral context may be lost on expiry/restart.
- **Recommendation:** Keep conversations ephemeral by default and do not add transcript storage without separate approval.
- **Approved architectural decision:** Conversations are ephemeral by default; persistence requires explicit approval.
- **Mapping:** **Exact match** — Option 1, ephemeral only.
- **User decision:** APPROVED.
- **Approval status:** APPROVED.

#### A-09 — Memory behavior

- **Question:** What memory retrieval and write behavior is permitted?
- **Available options:** Current CLI behavior only; API opt-in retrieval; preference-based retrieval; explicit operation per use.
- **Technical implications:** CLI writes are explicit, while matching memories may be retrieved during normal turns. API policy must not misstate this or treat save consent as retrieval consent.
- **Recommendation:** Keep writes user-approved and decide API retrieval separately.
- **Approved architectural decision:** Require explicit user approval before saving persistent memory.
- **Mapping:** **Exact match** — Option 4, explicit operation per use.
- **Clarification:** This approval governs memory writes; API retrieval behavior remains a separate policy.
- **User decision:** APPROVED.
- **Approval status:** APPROVED.

#### A-10 — Framework and dependencies

- **Question:** Which framework/dependencies should be adopted for any future API?
- **Available options:** No API; FastAPI; Flask; Starlette; another reviewed framework.
- **Technical implications:** Selection affects validation, schema/docs, dependency surface, synchronous inference strategy, packaging, security updates, and lifecycle.
- **Recommendation:** Use FastAPI and review package versions, compatibility, security, and integration details before implementation.
- **Approved architectural decision:** Use FastAPI as the selected future backend/API framework.
- **Mapping:** **Exact match** — Option 2.
- **Clarification:** This is a framework direction, not approval to install dependencies or implement a server.
- **User decision:** APPROVED.
- **Approval status:** APPROVED.

#### A-11 — Client and transport scope

- **Question:** Which clients and transport modes are in scope?
- **Available options:** Existing CLI only; future desktop; future web; authorized external clients.
- **Technical implications:** Each separate client adds identity, UX, compatibility, and security needs; CLI can call use cases directly.
- **Recommendation:** Preserve CLI in-process and approve each additional client separately.
- **Approved architectural direction:** The established client scope includes the existing CLI, a future desktop client, a future web client, and Veronica's own API for authorized external applications.
- **Mapping clarification:** The original options list each client category but do not provide a combined-all option. This direction preserves the four approved categories without inventing a missing option.
- **User decision:** APPROVED AS ARCHITECTURAL DIRECTION.
- **Approval status:** APPROVED; ORIGINAL-OPTION MAPPING CLARIFICATION REQUIRED.

#### A-12 — Network listener and exposure

- **Question:** Is any network listener allowed?
- **Available options:** No listener; authenticated loopback; LAN; remote/internet.
- **Technical implications:** Every listener expands attack surface; loopback is not authentication; LAN/remote require TLS, identity, operations, abuse response, and monitoring.
- **Recommendation:** No listener until explicitly approved; if later approved, evaluate authenticated loopback before broader exposure.
- **Approved architectural direction:** Deployment is configurable, but localhost-only is the default. LAN/public access remains disabled until separately configured and secured.
- **Mapping clarification:** The original options do not include configurable deployment modes. This direction means no listener initially and authenticated loopback for the initial local mode; later LAN or remote/internet exposure requires separate approval.
- **User decision:** APPROVED AS ARCHITECTURAL DIRECTION.
- **Approval status:** APPROVED; ORIGINAL-OPTION MAPPING CLARIFICATION REQUIRED.

#### A-13 — Concurrency, timeout, cancellation, and retry

- **Question:** What execution and retry semantics should be supported?
- **Available options:** Bounded synchronous calls; worker/process; streaming/jobs; best-effort or explicit cancellation; retries with or without idempotency.
- **Technical implications:** Current service/provider calls are synchronous; cancellation may not stop active inference; retries may duplicate tool side effects.
- **Recommendation:** Measure resource needs, bound work, and define idempotency before enabling stateful retries.
- **Approved architectural direction:** Use in-process background workers with failure handling, cancellation, and resource limits.
- **Mapping clarification:** `worker/process` is the closest original option, but the original choices do not combine in-process operation with explicit cancellation and resource-limit requirements. The approved direction remains preserved.
- **User decision:** APPROVED AS ARCHITECTURAL DIRECTION.
- **Approval status:** APPROVED; ORIGINAL-OPTION MAPPING CLARIFICATION REQUIRED.

#### A-14 — Tool authorization and confirmation

- **Question:** What permission and confirmation model applies to tools invoked through future clients?
- **Available options:** Existing CLI policy only; client scopes; per-tool scopes plus action confirmation.
- **Technical implications:** Registry allowlisting/schema checks do not establish user permission; model output is untrusted.
- **Recommendation:** Require backend policy, least privilege, schema validation, and confirmation for consequential tools.
- **Approved architectural decision:** Use risk-based tool confirmation with application-side authorization.
- **Mapping:** **Exact match** — Option 3, per-tool scopes plus action confirmation.
- **Clarification:** Application-side policy must decide authorization independently of model output and require confirmation for sensitive or consequential actions.
- **User decision:** APPROVED.
- **Approval status:** APPROVED.

#### A-15 — Persistence beyond existing SQLite memory

- **Question:** How may persistence evolve beyond the current local memory database?
- **Available options:** Keep current local SQLite scope; approve schema extensions; adopt a server database.
- **Technical implications:** Current schema has no owner/tenant field or migration service; changing storage requires ownership, backup, recovery, retention, and migration planning.
- **Recommendation:** Preserve current schema and scope; measure needs before considering expansion.
- **Approved architectural direction:** Use database abstraction, with SQLite as the default and PostgreSQL as a future option.
- **Mapping clarification:** The original options do not contain a database-abstraction/future-PostgreSQL option. SQLite is preserved as the initial default implementation; PostgreSQL remains a future option, not a current migration or server-database approval.
- **User decision:** APPROVED AS ARCHITECTURAL DIRECTION.
- **Approval status:** APPROVED; ORIGINAL-OPTION MAPPING CLARIFICATION REQUIRED.

### 8.2 Phase 3C security, identity, persistence, and framework decisions

#### C3C-01 — Backend framework

- **Question:** Which backend framework and dependency policy should be selected?
- **Available options:** FastAPI; Flask; Starlette plus selected components; Django REST Framework; no framework/API yet.
- **Technical implications:** Framework choice affects validation, OpenAPI, auth integration, sync/async behavior, dependencies, packaging, and maintenance.
- **Recommendation:** Preserve FastAPI as the selected framework; review only package versions, compatibility, security, lifecycle, and integration details.
- **Framework selection decision:** APPROVED — FastAPI.
- **Remaining dependency review:** PENDING IMPLEMENTATION DETAIL.
- **User decision:** APPROVED FOR FRAMEWORK SELECTION.
- **Approval status:** APPROVED FOR FRAMEWORK SELECTION; PACKAGE/DEPENDENCY REVIEW REMAINS OPEN.

#### C3C-02 — Initial service topology

- **Question:** What process topology should an initial service use?
- **Available options:** In-process only; one local API process; multiple web workers; separate inference worker/process.
- **Technical implications:** Workers can duplicate model memory; process separation adds IPC and operations; in-process has the smallest attack surface.
- **Recommendation:** Keep current CLI in-process; if a service is later approved, begin with a measured single-process design.
- **User decision:** PENDING.
- **Approval status:** NOT APPROVED.

#### C3C-03 — Local user identity

- **Question:** How should a local service identify its user?
- **Available options:** No identity; current OS user; local account; per-install identity plus OS user.
- **Technical implications:** OS binding supports attribution but needs provisioning/platform behavior; same-user malicious processes remain a threat.
- **Recommendation:** Require authenticated local identity if an API is approved; do not rely on loopback.
- **User decision:** PENDING.
- **Approval status:** NOT APPROVED.

#### C3C-04 — Local API authentication

- **Question:** What credential mechanism should protect a future local API?
- **Available options:** No auth; static API key; OS-protected install credential; short-lived scoped token; OS IPC.
- **Technical implications:** Credentials require secure issuance, storage, rotation, revocation, browser handling, and recovery.
- **Recommendation:** No unauthenticated API; evaluate scoped/revocable credentials protected by an OS or equivalent store.
- **User decision:** PENDING.
- **Approval status:** NOT APPROVED.

#### C3C-05 — Multi-user identity

- **Question:** How should future multi-user identity be handled?
- **Available options:** Self-managed passwords; OIDC/OAuth identity provider; organization federation; shared API key.
- **Technical implications:** Self-managed accounts impose password/security operations; federation adds provider/network/privacy dependencies; shared keys do not provide safe attribution.
- **Recommendation:** Defer multi-user; if needed, evaluate established identity federation rather than hand-rolling password security.
- **User decision:** PENDING.
- **Approval status:** NOT APPROVED.

#### C3C-06 — Session/token lifecycle

- **Question:** What session/token form and lifecycle should be used?
- **Available options:** Long-lived API key; opaque short-lived token; signed self-contained token; secure browser session.
- **Technical implications:** Expiry, refresh, rotation, logout, revocation, CSRF, audience, issuer, and storage policy must be defined.
- **Recommendation:** Prefer revocable short-lived credentials for a local service; choose browser handling separately.
- **User decision:** PENDING.
- **Approval status:** NOT APPROVED.

#### C3C-07 — Permission model

- **Question:** How are operations and resources authorized?
- **Available options:** Coarse roles; endpoint scopes; roles plus resource ACLs; unrestricted local trust.
- **Technical implications:** Scope checks alone do not ensure resource ownership; fine-grained policy increases implementation and test surface.
- **Recommendation:** Least-privilege scopes plus owner/resource checks; never rely on local trust alone.
- **User decision:** PENDING.
- **Approval status:** NOT APPROVED.

#### C3C-08 — Network exposure

- **Question:** What network boundary may a future API use?
- **Available options:** No listener; loopback; LAN; remote/internet.
- **Technical implications:** Exposure increases security and operations requirements; localhost does not authenticate callers or prevent browser-origin requests.
- **Recommendation:** No listener until approved; initially evaluate authenticated loopback only.
- **User decision:** PENDING.
- **Approval status:** NOT APPROVED.

#### C3C-09 — Conversation persistence

- **Question:** Should API conversations be persisted?
- **Available options:** Ephemeral only; user-opt-in transcript storage; persistent by default.
- **Technical implications:** Persistence creates ownership, retention, deletion, export, backup, and security obligations.
- **Recommendation:** Ephemeral by default; no durable transcript in an initial API.
- **User decision:** PENDING.
- **Approval status:** NOT APPROVED.

#### C3C-10 — Memory write and retrieval consent

- **Question:** What consent applies to memory writes and retrieval?
- **Available options:** Existing CLI semantics; per-turn opt-in; remembered preference; automatic retrieval; model-triggered writes.
- **Technical implications:** Existing explicit save intent is distinct from ordinary-turn matching retrieval; model requests cannot establish consent.
- **Recommendation:** Explicit user-approved writes and an independently decided API retrieval default.
- **User decision:** PENDING.
- **Approval status:** NOT APPROVED.

#### C3C-11 — Initial database

- **Question:** What database is appropriate for the initial application stage?
- **Available options:** Existing SQLite; separate SQLite stores; server relational database; other store.
- **Technical implications:** SQLite matches current local single-user use but lacks tenant isolation/migration services; server stores add operations and network dependencies.
- **Recommendation:** Reuse only the existing SQLite scope without schema expansion.
- **User decision:** PENDING.
- **Approval status:** NOT APPROVED.

#### C3C-12 — Multi-user persistence

- **Question:** What persistence is required if multi-user operation is selected?
- **Available options:** SQLite with enforced ownership; PostgreSQL/other relational store; managed database.
- **Technical implications:** Requires tenant isolation, migration, backup, operational, and recovery design.
- **Recommendation:** Defer until multi-user demand and workload are established.
- **User decision:** PENDING.
- **Approval status:** NOT APPROVED.

#### C3C-13 — Retention and backups

- **Question:** What data retention, backup, and recovery policy is required?
- **Available options:** No durable content; local protected backups; cloud backups; configurable retention.
- **Technical implications:** Backups introduce key custody, restore, deletion-from-copies, and retention requirements; no backups raise data-loss risk.
- **Recommendation:** Keep conversations ephemeral and do not add backups or cloud sync without explicit data policy approval.
- **User decision:** PENDING.
- **Approval status:** NOT APPROVED.

#### C3C-14 — Request limits and concurrency

- **Question:** What request limits and concurrency controls should apply?
- **Available options:** Fixed limits; config limits; measured per-route/principal limits; unbounded requests.
- **Technical implications:** Limits protect constrained hardware but require measurement; unbounded work risks resource exhaustion.
- **Recommendation:** Use measured, bounded limits; do not support unbounded requests.
- **User decision:** PENDING.
- **Approval status:** NOT APPROVED.

#### C3C-15 — Audit and error detail

- **Question:** What audit fields and error detail are appropriate?
- **Available options:** Verbose content logs; metadata-only audit; no audit; configurable policy.
- **Technical implications:** Content logs aid debugging but can create a sensitive transcript; minimal logs reduce data exposure but may limit diagnosis.
- **Recommendation:** Minimal redacted security metadata with request IDs; decide access and retention before implementation.
- **User decision:** PENDING.
- **Approval status:** NOT APPROVED.

#### C3C-16 — Secret storage and rotation

- **Question:** Where should credentials and secrets be stored and rotated?
- **Available options:** Environment variables; config file; OS credential store; external secret manager.
- **Technical implications:** Storage affects platform support, backup leakage, rotation, recovery, and deployment complexity.
- **Recommendation:** Evaluate OS-protected storage for local credentials; select only after platform review.
- **User decision:** PENDING.
- **Approval status:** NOT APPROVED.

#### C3C-17 — API contract details

- **Question:** Which exact API routes, schemas, statuses, and compatibility rules should be adopted?
- **Available options:** Adopt Phase 3B proposal; amend schemas; defer routes; add streaming now or later.
- **Technical implications:** Contract changes affect client compatibility, authorization semantics, idempotency, pagination, and deprecation.
- **Recommendation:** Freeze a minimal non-streaming v1 only after identity, retention, limits, and error decisions.
- **User decision:** PENDING.
- **Approval status:** NOT APPROVED.

#### C3C-18 — Online egress

- **Question:** Which features may send data outside the local machine?
- **Available options:** Always online; per-feature opt-in; disabled/offline-only; policy-controlled allowlist.
- **Technical implications:** Search/speech can transmit user data; offline enforcement needs service/network controls and tests.
- **Recommendation:** Disabled by default with explicit per-feature opt-in and destination policy.
- **User decision:** PENDING.
- **Approval status:** NOT APPROVED.

### 8.3 Phase 3D API contract and client decisions

#### C3D-01 — API base/version

- **Question:** Which API base path and versioning scheme should be used?
- **Available options:** `/api/v1`; another URI/version scheme; defer versioning.
- **Technical implications:** Versioning affects compatibility, schema publication, and deprecation commitments.
- **Recommendation:** Consider `/api/v1` with a framework-neutral published schema.
- **User decision:** PENDING.
- **Approval status:** NOT APPROVED.

#### C3D-02 — Primary chat route

- **Question:** What is the canonical chat route and request shape?
- **Available options:** `/chat`; `/chat/completions`; resource-based turns only.
- **Technical implications:** Route semantics must be stable and must not expose Ollama-specific payloads as the permanent contract.
- **Recommendation:** Consider one canonical `POST /api/v1/chat` with optional explicit ephemeral conversation ID.
- **User decision:** PENDING.
- **Approval status:** NOT APPROVED.

#### C3D-03 — Stateless/conversation behavior

- **Question:** How should one-shot and continuing chat behave?
- **Available options:** One-shot only; optional ephemeral session; persistent transcript.
- **Technical implications:** Context scope, expiry/restart behavior, retention, and authorization differ materially by choice.
- **Recommendation:** One-shot by default; explicit ephemeral session to continue; no durable transcript initially.
- **User decision:** PENDING.
- **Approval status:** NOT APPROVED.

#### C3D-04 — Identifier policy

- **Question:** How are conversation/resource identifiers created and authorized?
- **Available options:** UUID; random opaque token; caller-selected ID.
- **Technical implications:** IDs must not act as credentials; every use needs owner checks and expiry behavior.
- **Recommendation:** Server-generated unpredictable opaque IDs bound to an owner.
- **User decision:** PENDING.
- **Approval status:** NOT APPROVED.

#### C3D-05 — Memory search/write contract

- **Question:** How should memory search and write operations be represented?
- **Available options:** GET query search; POST body search; direct writes; confirmation receipt.
- **Technical implications:** URL queries may leak through logs/history; writes need trusted consent, ownership, and deletion policy.
- **Recommendation:** POST body for private search; explicit write with scoped single-use user approval if an API is authorized.
- **User decision:** PENDING.
- **Approval status:** NOT APPROVED.

#### C3D-06 — Knowledge search contract

- **Question:** Should the contract provide search only or also ingestion?
- **Available options:** GET query; POST query body; expose ingestion; search approved sources only.
- **Technical implications:** Ingestion needs source rights, provenance, parser security, retention/deletion, and separate authorization.
- **Recommendation:** Search-only over approved collections; no ingestion route in an initial contract.
- **User decision:** PENDING.
- **Approval status:** NOT APPROVED.

#### C3D-07 — Model metadata

- **Question:** What provider/model metadata may clients see?
- **Available options:** Provider-specific payload; neutral metadata with provider ID; no metadata.
- **Technical implications:** Metadata must be truthful without exposing paths, credentials, or unsupported capabilities.
- **Recommendation:** Neutral metadata with truthful capabilities and clear development/native mode.
- **User decision:** PENDING.
- **Approval status:** NOT APPROVED.

#### C3D-08 — Error/status convention

- **Question:** What error envelope and HTTP status mapping should be used?
- **Available options:** Framework defaults; stable problem-style envelope; provider raw errors.
- **Technical implications:** Stable errors improve clients; raw exceptions may expose sensitive internals.
- **Recommendation:** Stable sanitized problem-style envelope with request ID.
- **User decision:** PENDING.
- **Approval status:** NOT APPROVED.

#### C3D-09 — Streaming

- **Question:** Should initial chat support streaming?
- **Available options:** Non-streaming JSON; SSE; WebSocket; queued jobs.
- **Technical implications:** Streaming requires event schema, cancellation, partial-response, reconnection, capability, and resource lifecycle semantics.
- **Recommendation:** Non-streaming initially; revisit using provider/runtime evidence.
- **User decision:** PENDING.
- **Approval status:** NOT APPROVED.

#### C3D-10 — Timeout and cancellation

- **Question:** What timeout and cancellation guarantees are required?
- **Available options:** Best-effort disconnect cancellation; explicit request/job cancellation; no deadline.
- **Technical implications:** A running provider may not stop immediately; timed-out work may continue consuming resources or have side effects.
- **Recommendation:** Bounded deadlines and cleanup; do not promise hard cancellation without provider evidence.
- **User decision:** PENDING.
- **Approval status:** NOT APPROVED.

#### C3D-11 — Idempotency

- **Question:** How should retried chat, tool, and memory operations behave?
- **Available options:** No retry handling; idempotency key; client-only deduplication.
- **Technical implications:** Retries can duplicate stateful turns or consequential tool actions; idempotency adds key storage and expiry policy.
- **Recommendation:** Define idempotency before enabling retries for stateful operations.
- **User decision:** PENDING.
- **Approval status:** NOT APPROVED.

#### C3D-12 — Authorization and ownership

- **Question:** What principals, scopes, ownership rules, and conversation-turn permission form are required?
- **Available options:** Coarse roles; scopes; scopes plus resource ACL; local trust; paired conversation read/write or dedicated `conversation:turn`.
- **Technical implications:** Every resource needs server-side owner checks. A turn permission must include both read-context and append semantics only for the authorized conversation.
- **Recommendation:** Least-privilege scopes plus ownership checks.
- **Approved conversation-turn form:** Dedicated `conversation:turn` permission with read-context and append semantics for an owned conversation.
- **Remaining C3D-12 details:** Principals, complete scope matrix, resource ACL boundaries, and remaining ownership/enforcement details require separate decision closure.
- **User decision:** PARTIALLY APPROVED — CONVERSATION-TURN FORM ONLY; BROADER AUTHORIZATION DETAILS PENDING.
- **Approval status:** PARTIALLY APPROVED; REMAINING C3D-12 DETAILS NOT APPROVED.

#### C3D-13 — Client connectivity

- **Question:** How should CLI, desktop, web, and external clients connect?
- **Available options:** CLI direct services; all clients HTTP; optional API client mode.
- **Technical implications:** Shared application semantics are required, but a common transport is not. Forcing CLI through HTTP changes startup and availability requirements.
- **Recommendation:** CLI remains direct/in-process; approve API transport separately for other clients.
- **User decision:** PENDING.
- **Approval status:** NOT APPROVED.

#### C3D-14 — Browser and external authentication

- **Question:** What authentication and protections are required for browser and external clients?
- **Available options:** Shared static key; per-client scopes; browser session plus CSRF/origin policy; unauthenticated local access.
- **Technical implications:** Browser storage, CSRF, origin controls, revocation, remote TLS, and per-client attribution must be handled.
- **Recommendation:** Per-client scopes and reviewed browser-session policy; never treat local access as sufficient authentication.
- **User decision:** PENDING.
- **Approval status:** NOT APPROVED.

#### C3D-15 — Online/offline contract

- **Question:** How should optional network features behave online and offline?
- **Available options:** Always online; per-feature opt-in; strict offline mode.
- **Technical implications:** Online tools may transmit data; offline state must be enforced at the service/network boundary and reported truthfully.
- **Recommendation:** Local/offline default with explicit egress disclosure and per-feature opt-in.
- **User decision:** PENDING.
- **Approval status:** NOT APPROVED.

#### C3D-16 — Language/evaluation contract

- **Question:** How should language and mixed-script performance be evaluated?
- **Available options:** Pooled metrics; three language reports; separate mixed-script reports.
- **Technical implications:** Aggregate scores can hide per-language weakness; thresholds and lawful evaluation data must be approved.
- **Recommendation:** Equal English/Hindi/Hinglish reporting plus a separate mixed-script report.
- **User decision:** PENDING.
- **Approval status:** NOT APPROVED.

## 9. Native-brain boundary and preserved approvals

Native-brain decisions are not application-layer decisions. Model architecture, tokenizer decision closure, experiment authorization, data governance/licensing, training, evaluation thresholds, inference runtime, native provider integration, offline/hardware constraints, and provider replacement each require their own explicit scope and gates.

Phase 2G D-01 remains approval of the objective of a controlled tokenizer comparison only. It does not authorize experiment execution, dataset acquisition, vocabulary fitting, training, or provider integration. D-02 through D-18 remain pending.

Ollama remains the current/default provider. A future native provider must first be implemented and independently validated behind provider-neutral contracts; provider replacement requires a separate user approval after quality, safety, language, security, hardware, offline, and rollback gates pass.

### Additional preserved architectural approvals

The following approved directions are recorded separately because they are cross-cutting requirements rather than exact A-01 through A-15 original options:

- **Knowledge-source governance:** Only reviewed and approved knowledge sources may be ingested. Source rights, provenance, privacy, parser security, retention, deletion, and re-indexing remain controlled prerequisites.
- **API-key security:** API-key authentication must use secure storage and must not expose keys or secrets in logs, prompts, responses, source control, or ordinary diagnostics.
- **Structured logging and observability:** Use structured request, service, and security telemetry with request/correlation IDs while excluding secrets and sensitive user data, including prompts, memory contents, and raw tool payloads.
- **Layered testing:** Testing must include layered unit, integration, API contract, and end-to-end coverage appropriate to each later implementation scope.

These approved architectural directions do not authorize implementation, dependency installation, deployment, data ingestion, training, or provider changes.

## 10. Readiness outcome and next step

The repository has reusable provider-neutral contracts and working CLI, AI orchestration, local memory, and tool components. It does not have the shared application composition/use-case layer, API identity/authorization, or request/owner isolation needed for multi-request API use.

**Workshop outcome:** A-01 through A-10 and A-14 have verified original-option mappings; A-11, A-12, A-13, and A-15 preserve approved architectural directions that require mapping clarification. C3C-01 framework selection is resolved in favor of FastAPI; C3C-02 through C3C-18 and C3D-01 through C3D-16 remain pending or, for C3D-12, retain unresolved details beyond the approved conversation-turn form.

Recording these approvals does not authorize implementation. Source/test/configuration/dependency changes, server or API creation, database changes, data acquisition, training, deployment, model/provider work, commits, and pushes remain unauthorized unless separately approved in a later implementation scope.

If the user later approves implementation, the safest candidate to discuss first is a narrowly scoped, in-process application boundary that preserves the CLI and current provider behavior. HTTP/API, framework dependencies, multi-user access, persistence expansion, native-brain work, and provider switching remain separate approvals.

## Inspection record

The complete planning documents reviewed for this workshop:

- `docs/PHASE_3A_COMPLETE_INDEPENDENT_AI_SYSTEM_ARCHITECTURE_PLAN.md`
- `docs/PHASE_3B_CORE_SYSTEM_REQUIREMENTS_AND_BACKEND_API_CONTRACT_PLAN.md`
- `docs/PHASE_3C_API_SECURITY_IDENTITY_PERSISTENCE_AND_FRAMEWORK_DECISION_CLOSURE.md`
- `docs/PHASE_3D_API_CONTRACT_FINALIZATION_AND_CLIENT_INTEGRATION_ARCHITECTURE_PLAN.md`
- `docs/PHASE_3E_BACKEND_APPLICATION_LAYER_AND_SERVICE_ARCHITECTURE_PLAN.md`
- `docs/PHASE_3F_CORE_APPLICATION_LAYER_IMPLEMENTATION_READINESS_AND_DECISION_PLAN.md`

Relevant source/test facts are summarized from the completed Phase 3E/3F inspections. No additional source or test inspection was needed to resolve a new technical question for this documentation-only workshop. No tests were run.

No source, test, configuration, dependency, database, or previous-phase document was changed. Only this Phase 3G document was updated. No package was installed, no server was created or started, no tokenizer experiment/data acquisition/training/inference work was performed, and no provider behavior was changed.
