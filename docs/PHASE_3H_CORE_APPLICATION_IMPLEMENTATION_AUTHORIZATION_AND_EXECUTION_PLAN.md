# Phase 3H: Core Application Implementation Authorization and Execution Plan

**Status:** Planning and execution-preparation only. This document is not implementation approval.

## 1. Purpose and authorization boundary

This document converts the reviewed Phase 3A–3G architecture and decisions into a future implementation sequence. It does not implement an application component, install or select dependencies, change source or tests, create a server or API, alter Ollama behavior, ingest knowledge, train or download models, migrate a database, expose a network listener, or authorize provider replacement.

The approved Phase 3G architectural directions are retained in this plan. Separate implementation approval is still required for every execution stage. Planning approval and implementation authorization are deliberately distinct:

- **Approved architecture:** a recorded Phase 3G user decision or preserved architectural direction.
- **Proposed implementation:** work, files, tests, and acceptance criteria described below for future approval.
- **Work completed:** no implementation work is completed by this document.

No C3C or C3D recommendation becomes implementation approval merely by appearing in this plan.

## 2. Cross-document conclusions

### 2.1 Current baseline

The repository has provider-neutral contracts, `AIService`, local SQLite memory, a tool registry, bounded tool orchestration, and a working CLI. It does not have a shared application composition root, API authentication/authorization, cross-request owner isolation, a backend lifecycle, or a production knowledge system.

Ollama remains the only complete current text-answer provider and remains the development default. `VeronicaModelProvider` is a nonfunctional scaffold. External AI providers must not become permanent Veronica answer-generation engines.

### 2.2 Long-term target

Veronica's long-term architecture is an independently controlled system with:

- Veronica-owned model weights and tokenizer.
- Veronica-controlled local inference.
- A shared application/backend boundary.
- A versioned API.
- Governed knowledge and explicit personal memory.
- CLI, desktop, and web clients.
- Authorized external-app access.
- Separate online and offline operation.

No native model, weight, tokenizer, training pipeline, inference runtime, backend, knowledge store, desktop client, or web client is assumed implemented by this plan.

### 2.3 Language and offline constraints

English, Hindi in Devanagari, and Hinglish in Roman Hindi/code-switching remain equal priorities. Mixed-script text is a separate evaluation group. Unicode text must be preserved and must not be silently normalized or transliterated.

Offline operation and online/remote features remain distinct. Strict offline behavior must be enforced at the network boundary. Optional search and speech must be disclosed and opt-in.

## 3. Preserved Phase 3G approved directions

| A-ID | Preserved approved direction | Implementation relevance |
|---|---|---|
| A-01 | Small shared application layer, transport-neutral use cases, explicit composition, existing CLI retained, future clients supported. | First implementation stage and all later adapters. |
| A-02 | Gradually refactor existing `AIService`; no wrapper-only or replacement shortcut. | Characterize behavior, isolate state incrementally, retain compatibility tests. |
| A-03 | Explicitly mixed process, request, conversation, and worker dependency scopes. | Compose immutable process dependencies, request contexts, owner-bound conversation state, and bounded workers separately. |
| A-04 | Dedicated `conversation:turn` permission, with ownership verification. | Turn use cases and API policy must read context and append only within the owner's conversation. |
| A-05 | Request-scoped context for one-shot requests. | Never inherit another request or conversation context. |
| A-06 | Per-install credential for local API authentication. | Credential issuance, secure storage, no-secret logging, and revocation are required; exact storage remains under C3C closure. |
| A-07 | Both single-user local operation and future multi-user support. | Design owner boundaries now without prematurely adding a multi-user implementation. |
| A-08 | Ephemeral conversations by default; persistence requires explicit approval. | Use bounded in-memory or explicitly approved ephemeral state only. |
| A-09 | Explicit user approval before saving persistent memory. | Memory writes require a trusted user action and no model-only consent. |
| A-10 | FastAPI selected as the future backend/API framework. | A later API stage may proceed with FastAPI; compatibility and security reviews determine package versions and integration safeguards, not whether FastAPI is selected. |
| A-11 | Existing CLI, future desktop, future web, and authorized external applications using Veronica's API. | The client scope is approved. Transport, integration, authentication, accessibility, and security details remain pending. |
| A-12 | Configurable deployment modes with localhost-only default; mapping clarification required. | No listener initially; loopback requires authentication; LAN/public requires separate approval. |
| A-13 | In-process background workers with failure handling, cancellation, and resource limits; mapping clarification required. | Bounded execution and explicit cancellation are mandatory; exact limits and retry semantics need evidence. |
| A-14 | Risk-based tool confirmation and application-side authorization. | Server policy, least privilege, schema validation, and sensitive-action confirmation. |
| A-15 | Database abstraction, SQLite default, PostgreSQL future option; mapping clarification required. | Introduce abstractions cautiously; retain SQLite; no PostgreSQL migration is approved. |

Additional preserved directions:

- Knowledge ingestion is limited to reviewed and approved sources.
- API keys use secure storage and never appear in logs or ordinary diagnostics.
- Structured, privacy-safe logging and observability require request/correlation IDs and secret/sensitive-data exclusion.
- Testing includes unit, integration, API contract, and end-to-end coverage.

## 4. Recommended implementation order

The implementation sequence is a proposal only:

1. Characterize and baseline the existing CLI and component behavior.
2. Define transport-neutral application contracts and explicit composition.
3. Refactor `AIService` gradually while preserving the existing CLI.
4. Add request, owner, conversation, and dependency isolation.
5. Add privacy-safe observability and bounded worker infrastructure.
6. Resolve the applicable C3C/C3D decisions needed for a local API.
7. Add a FastAPI foundation and loopback-only local lifecycle only if explicitly approved.
8. Add authenticated chat and ephemeral conversations.
9. Add memory operations and explicitly approved knowledge search separately.
10. Add desktop, web, or external clients only after separate client approvals.
11. Add database growth, PostgreSQL, or migration work only when measured requirements justify it.
12. Integrate a separately approved native provider and inference runtime, but preserve Ollama until a separate provider replacement gate passes.

### Rationale

This order minimizes simultaneous change and keeps the CLI usable throughout. `AIService` and provider behavior are characterized before state is separated. Security, identity, and resource policy precede an API listener. Persistence and knowledge work wait for separate consent and source governance. Database migration and provider replacement remain isolated late gates.

## 5. Dependency map

```text
Phase H0 Baseline and authorization
  -> H1 Application contracts and composition
  -> H2 AIService compatibility refactor
  -> H3 Request/conversation isolation
  -> H4 Observability and bounded workers
  -> H5 C3C/C3D implementation closure
  -> H6 Local FastAPI foundation
  -> H7 Chat and ephemeral conversations
  -> H8 Memory operations
  -> H9 Approved knowledge search
  -> H10 Client integrations
  -> H11 Storage growth and migration
  -> H12 Native provider integration and replacement
```

Dependencies:

- H2 depends on H1 and a CLI behavior baseline.
- H1–H2 may produce application/composition and AIService compatibility design; H3 may perform only H3 design and baseline work that does not depend on unresolved authorization decisions.
- H5 closes the applicable C3C/C3D decisions using H1–H2 design evidence and does not require completed H3 implementation.
- H3 implementation depends on H5/authorization closure for principal definitions, the scope matrix, resource ACL boundaries, ownership verification, and enforcement failures.
- H4 design depends on H1/H2 and may proceed without unresolved authorization decisions; implementation requiring those decisions waits for H5.
- H5 must close the applicable C3C/C3D decisions before H3 implementation and before H6.
- H6 depends on H5 and the framework/dependency review.
- H7 depends on H3 implementation, H4 implementation, and H6.
- H8 depends on H6/H7 and a separate memory consent/migration decision.
- H9 depends on H6/H7 and separately approved sources.
- H10 depends on H6/H7 plus client-specific security decisions.
- H11 depends on H8/H9 workload evidence and migration approval.
- H12 depends on separate native-model, tokenizer, data, inference, evaluation, and replacement approvals.

## 6. Implementation phases

### Phase H0: Baseline and approval preconditions

**Objective and scope**

Record a measured baseline of existing CLI behavior, provider selection, memory operations, tools, configuration, test coverage, and worktree state. Define the first named implementation scope and explicit exclusions.

**Expected proposed files/modules**

- No required source change is assumed.
- Proposed additions may include a future session state or application package, but exact paths are not approved here.
- Existing files likely relevant include `dev_ai.py`, `app/ai/service.py`, `app/ai/provider.py`, `app/memory/service.py`, `app/tools/registry.py`, and `app/config.py`.

**Prerequisites**

- Read and retain the Phase 3A–3G decisions.
- Record the approved architecture and unresolved C3C/C3D items.
- Confirm no pre-existing worktree change is overwritten.

**Required tests and acceptance**

- Existing provider, AI, memory, tool, CLI, and integration tests are identified, not executed or modified by this plan.
- A future baseline report must state commands and results rather than infer success.
- English, Hindi, Hinglish, and mixed-script behavior must remain covered as applicable.

**Security, privacy, compatibility risks**

- Baseline snapshots may be incomplete or stale.
- Test-only assumptions must not be mistaken for API, authorization, or multi-user evidence.
- Avoid collecting prompt content or sensitive output in baseline records.

**Rollback/recovery**

- No implementation change occurs in this phase.
- Preserve the worktree and create reviewable diffs only after explicit implementation approval.

**User approval gate**

Separate explicit approval of the baseline scope, exact files to inspect, and no-change boundary.

### Phase H1: Shared application contracts and composition

**Objective and scope**

Introduce the smallest transport-neutral application use cases and an explicit composition boundary. The CLI should invoke shared application operations directly and remain usable without HTTP.

**Expected proposed files/modules**

- A future `app/services` implementation package.
- Future transport-neutral request/result and application-error types.
- A composition/bootstrap module.
- Reviewed call-site changes in `dev_ai.py` and selected existing AI/memory/tool adapters.

**Prerequisites**

- H0 baseline.
- A-01 approval retained.
- Preserve provider-neutral contracts and CLI behavior.
- The approved `conversation:turn` permission form means reading relevant context and appending a turn for the owned conversation.
- H1 may define the future conversation-turn interface only; principal definitions, the scope matrix, resource ACL boundaries, ownership verification, and enforcement remain unresolved C3D-12 work.
- No conversation authorization implementation is authorized in H1. H3 owns later conversation-isolation implementation, subject to H5/C3D-12 closure and separate authorization.

**Required tests and acceptance**

- CLI parity for commands, provider defaults, memory intent, tool behavior, history, role/teaching behavior, and errors.
- Unit tests for use-case inputs, typed failures, and dependency composition.
- One-shot isolation tests.
- No HTTP listener or public bind.

**Security, privacy, compatibility risks**

- Incorrect extraction can duplicate AI behavior or change CLI semantics.
- Transport-neutral types must not accept untrusted user identity.
- A shared singleton must not retain cross-request state.

**Rollback/recovery**

- Keep a compatibility wrapper and reversible call-site changes.
- Stop the rollout if CLI parity or provider construction fails.
- Retain Ollama configuration and provider behavior unchanged.

**User approval gate**

Explicit approval naming the composition package, exact affected files, CLI parity suite, and exclusions.

### Phase H2: Gradual AIService compatibility refactor

**Objective and scope**

Separate stateless turn operations from mutable conversation, role, teaching, memory intent, and tool policy state while preserving current behavior.

**Expected proposed files/modules**

- Reviewed modifications to `app/ai/service.py`, provider/orchestration adapters, and future application use cases.
- Future tests for state separation and compatibility.

**Prerequisites**

- H1 transport-neutral contracts.
- A-02 gradual-refactor approval.
- A characterization matrix for mutable AIService fields.

**Required tests and acceptance**

- Existing AI, role, teaching, tool, provider, memory, and CLI tests.
- New tests proving that separate requests do not share mutable history.
- Provider unavailable, malformed output, timeout, and no-silent-fallback tests.
- English, Hindi, Hinglish, and mixed-script preservation cases.

**Security, privacy, compatibility risks**

- Shared mutable state can leak between users or turns.
- Refactoring memory/tool behavior may change consent or confirmation semantics.
- Replacing provider behavior accidentally is a high-risk regression.

**Rollback/recovery**

- Retain the existing implementation behind a compatibility adapter until parity is demonstrated.
- No provider switch or native integration.
- Revert only the named refactor changes if a gate fails.

**User approval gate**

Separate approval for affected classes/files, compatibility scope, test baseline, and provider exclusions.

### Phase H3: Request, conversation, and ownership isolation

**Objective and scope**

Add request-scoped context and owner-bound conversation state. Implement the approved `conversation:turn` semantics for future chat operations.

**Expected proposed files/modules**

- Future application context types.
- Future conversation repository/context service.
- Future authorization-policy components.
- Future tests for ownership and isolation.

**Prerequisites**

- H2.
- A-04/A-05 retained.
- The dedicated `conversation:turn` permission form is already established in substance: it grants read-context and append-turn semantics only for the owned conversation.
- H3 may produce design, repository interfaces, and isolation tests that do not depend on unresolved authorization decisions.
- Before H3 implementation begins, H5 must resolve the remaining broader C3D-12 details: principal types, complete scope matrix, resource ACL boundaries, and ownership enforcement failures.
- Principal/owner resolution design remains subject to H5/C3D-12 closure.

**Required tests and acceptance**

- Interleaved one-shot requests prove no context reuse.
- Cross-owner conversation reads/appends fail.
- Owned conversation turns read context and append once.
- Clear, expiry, cancellation, failure, retry, and concurrency cases leave no cross-turn state.

**Security, privacy, compatibility risks**

- Opaque IDs must not be treated as credentials.
- Missing ownership checks can expose transcripts or memory.
- Shared caches can leak data across principals.

**Rollback/recovery**

- Disable continuing-conversation support and retain one-shot request isolation.
- No persistent transcript is introduced.
- Preserve in-process CLI state until explicit parity is proven.

**User approval gate**

Explicit approval of context types, owner policy, permission representation, and isolation test suite.

### Phase H4: Structured observability and bounded workers

**Objective and scope**

Create privacy-safe logging and bounded in-process worker behavior with failure handling, cancellation, and resource limits.

**Expected proposed files/modules**

- Future structured logging configuration/helper.
- Future worker/executor abstraction.
- Future request/correlation context propagation.
- Future operational metrics or audit metadata.

**Prerequisites**

- H1/H2/H3.
- A-13 retained.
- Resource measurements and limits approved.
- C3C-14/C3C-15 and C3D-10/C3D-11 resolved where applicable.

**Required tests and acceptance**

- Queue saturation, timeout, cancellation, disconnect, provider failure, and retry behavior.
- Secret, prompt, memory, and raw-tool-data redaction tests.
- Structured fields do not include sensitive content.
- Worker count and resource accounting stay within approved bounds.

**Security, privacy, compatibility risks**

- Logs can become sensitive transcript stores.
- Cancellation may not stop an active provider call.
- Retry can duplicate stateful tool effects.

**Rollback/recovery**

- Disable background execution and return to bounded synchronous behavior.
- Disable sensitive telemetry fields and retain request IDs only.
- Preserve the provider adapter and CLI path.

**User approval gate**

Measured limits, logging fields, retention, worker strategy, retry policy, and cancellation guarantees require separate approval.

### Phase H5: Security, deployment, and contract closure

**Objective and scope**

Close the implementation prerequisites from C3C/C3D rather than changing source. Produce a threat model, permission matrix, data-flow review, deployment mode, API contract freeze, and dependency review.

**Expected proposed files/modules**

- Documentation and future configuration templates only unless implementation approval explicitly follows.
- No source, test, server, key, or database change is performed by this planning phase.

**Prerequisites**

- H0–H2 design evidence, as applicable; H5 does not require completed H3 implementation.
- Applicable C3C-02 through C3C-18 and C3D-01 through C3D-16 decisions.
- C3C-01 framework selection is resolved for FastAPI; only package versions, compatibility, security, lifecycle, and integration review remain.
- C3D-12 retains the approved dedicated `conversation:turn` form; resolve its remaining principals, scope matrix, resource ACL, and ownership-enforcement details before implementation.
- A-06/A-12/A-14/A-10 clarifications resolved.

**Required tests and acceptance**

- Authorization-negative review.
- Threat-model and data-flow review.
- API schema and error examples.
- Secret and sensitive-data redaction review.
- Language and mixed-script contract cases.

**Security, privacy, compatibility risks**

- Closing individual records without end-to-end consistency can create incompatible authentication or resource policies.
- Loopback and per-install credentials do not replace resource authorization.

**Rollback/recovery**

- No implementation change, so no migration or runtime rollback is required.
- If decisions conflict, preserve prior pending statuses and stop.

**User approval gate**

Explicit resolution of all applicable C3C/C3D decisions and exact implementation scope.

### Phase H6: Local FastAPI foundation

**Objective and scope**

Implement only a separately approved local API foundation using the selected FastAPI framework. Compatibility and security reviews determine package versions and integration safeguards, not the framework selection. Preserve CLI direct/in-process operation.

**Expected proposed files/modules**

- Future FastAPI application/composition module.
- Future versioned router package.
- Future health/readiness and model-info routes.
- Future authentication middleware and per-install credential provisioning.
- Future API contract/OpenAPI artifact.

**Prerequisites**

- H5 complete.
- A-10 framework direction retained.
- A-12 configurable deployment, localhost-only default.
- A-06 per-install credential and secure key handling.
- Framework dependencies and exact versions separately approved.

**Required tests and acceptance**

- Route/schema tests.
- Authentication and authorization-negative tests.
- Loopback/no-public-bind tests.
- Readiness truthful provider/dependency reporting.
- Secret and error-redaction tests.
- No-network fallback tests if offline.

**Security, privacy, compatibility risks**

- FastAPI does not implement authentication or authorization policy.
- Synchronous provider/SQLite work must not block the server loop or duplicate model loads.
- A listener expands local-process and browser threat surfaces.

**Rollback/recovery**

- Do not start or expose the listener until all gates pass.
- Disable API entry point and retain the CLI-only composition.
- Remove no existing provider or memory behavior.

**User approval gate**

Explicit named server/API scope, dependency versions, bind mode, credential mechanism, files, tests, and exclusions.

### Phase H7: Chat and ephemeral conversations

**Objective and scope**

Implement approved chat and ephemeral conversation operations with owner-bound IDs, request isolation, `conversation:turn`, cancellation, and resource limits.

**Expected proposed files/modules**

- Future chat and conversation routes/use cases.
- Future ephemeral conversation store.
- Future model metadata response adapters.
- Future idempotency and cancellation components if separately approved.

**Prerequisites**

- H6.
- H3 ownership isolation.
- A-04/A-05/A-08 retained.
- C3D chat, retention, timeout, cancellation, and idempotency decisions resolved.

**Required tests and acceptance**

- One-shot isolation.
- Owner-only read/append/delete.
- Ephemeral expiry/restart behavior.
- Cancellation and timeout.
- Provider unavailable/malformed response.
- Unicode and mixed-script cases.
- No persisted transcript by default.

**Security, privacy, compatibility risks**

- Conversation IDs can be misused without ownership checks.
- Persistent state or shared caches can cross users.
- A timeout or disconnect can hide active work or side effects.

**Rollback/recovery**

- If continuing-conversation isolation fails, disable continuing-conversation functionality.
- Retain or restore one-shot chat only if its own verified request isolation and safety requirements pass.
- Stop accepting chat routes and retain health/model metadata only if approved.
- Preserve Ollama default and no silent fallback behavior.

**User approval gate**

Separate chat/API implementation approval, exact routes, limits, retention, permissions, and provider behavior.

### Phase H8: Explicit memory operations

**Objective and scope**

Expose local memory operations only through explicit user consent and owner-bound application policy.

**Expected proposed files/modules**

- Future memory repository/use-case adapters.
- Future memory routes.
- Future trusted approval receipt mechanism.
- Future export/delete/clear behavior.

**Prerequisites**

- H6/H7.
- A-09 explicit-save approval.
- C3C-09/C3C-10/C3C-11/C3C-13 resolved.
- Existing SQLite file and schema preserved unless migration is separately approved.

**Required tests and acceptance**

- Explicit write/clear consent.
- Cross-owner read/write/delete denial.
- Reused or stale approval rejection.
- Credential and sensitive-data handling.
- No memory-to-training or transcript-to-memory flow.
- Backup/export/delete behavior if in scope.

**Security, privacy, compatibility risks**

- Model output must not write memory by itself.
- Existing SQLite has no owner/tenant schema.
- Existing retrieval behavior differs from explicit save consent.

**Rollback/recovery**

- Disable memory API routes.
- Preserve current CLI memory behavior and database unchanged.
- No schema migration or database deletion.

**User approval gate**

Separate memory API scope, consent UX, storage semantics, migration decision, and retention policy.

### Phase H9: Approved knowledge-source search

**Objective and scope**

Add search over explicitly reviewed and approved local collections, with no ingestion endpoint until separately authorized.

**Expected proposed files/modules**

- Future source/collection/provenance models.
- Future access-controlled knowledge repository/search adapter.
- Future search route/use case.
- Future source manifests and indexes.

**Prerequisites**

- H6/H7.
- Reviewed source licenses/rights/privacy approval.
- C3C-11/C3C-12/C3C-13 and C3D-06 decisions resolved.
- Per-collection access policy approved.

**Required tests and acceptance**

- Source provenance and citation.
- Unauthorized collection denial.
- Prompt-injection and malicious-document handling.
- Bounded excerpts and deletion/re-index behavior.
- No ingestion, scraping, or training from memory/conversations.

**Security, privacy, compatibility risks**

- Retrieved content is untrusted.
- Source approval is not training approval.
- Indexes can outlive source deletion.

**Rollback/recovery**

- Disable search ingestion and routes.
- Remove only newly added derived indexes according to the approved deletion procedure.
- Preserve existing web-search behavior unless explicitly changed.

**User approval gate**

Explicit approval for each source or collection, index scope, parser scope, and search API.

### Phase H10: Desktop, web, and external-client integrations

**Objective and scope**

Add approved clients over the shared application/API contracts. Keep the CLI direct and in-process.

**Expected proposed files/modules**

- Future desktop, web, or external-client projects/modules.
- Future browser session/CSRF/origin policy.
- Future per-client credential/quota/revocation management.
- Future accessibility and localization assets.

**Prerequisites**

- H6/H7, with H8/H9 where needed.
- A-11 client scope retained.
- C3D-13/C3D-14/C3D-15 resolved.
- A-12 LAN/public exposure decision.

**Required tests and acceptance**

- Authentication, CSRF, origin, tenant/owner isolation, revocation, and quotas.
- English, Hindi, Hinglish, and mixed-script UI/API behavior.
- Offline/online disclosures.
- Safe memory/tool confirmation UX.
- External-app scope is limited by the approved grant.

**Security, privacy, compatibility risks**

- Browser-origin and local-network request abuse.
- A desktop/web client can expose secrets or overprivileged admin credentials.
- Multiple clients can drift if business logic is duplicated.

**Rollback/recovery**

- Disable the client and preserve direct CLI operation.
- Revoke new client credentials and close only the approved listener.
- Preserve provider and server behavior until a separate release gate.

**User approval gate**

Separate approval for every client, transport, network exposure, identity, and deployment scope.

### Phase H11: Storage growth and future PostgreSQL

**Objective and scope**

Evaluate or implement database growth only after a workload, multi-user, backup, and migration decision justifies it.

**Expected proposed files/modules**

- Future repository interfaces and implementations.
- Future migration framework/artifacts.
- Future backup/restore configuration.
- Future PostgreSQL adapter only if separately approved.

**Prerequisites**

- A-15 database-abstraction direction retained.
- H8/H9/H10 workload evidence.
- C3C-11/C3C-12/C3C-13/C3D data decisions resolved.
- SQLite remains unchanged until a migration gate passes.

**Required tests and acceptance**

- Repository compatibility and tenant isolation.
- Migration backup, restore, rollback, integrity, and deletion/export behavior.
- Concurrency and resource measurements.
- No cross-tenant cache or log leakage.

**Security, privacy, compatibility risks**

- SQLite migration can lose or expose user data.
- PostgreSQL adds operations and network dependencies.
- Backup keys and deletion propagation require separate custody design.

**Rollback/recovery**

- Restore verified SQLite backup and keep the application on the old repository.
- No migration is run until backup/restore and rollback tests pass.
- Future PostgreSQL remains optional.

**User approval gate**

Explicit database, migration, backup, and multi-user scope with exact files and data handling.

### Phase H12: Native provider and future replacement

**Objective and scope**

Add a non-default, independently validated Veronica-native provider only after model, tokenizer, runtime, source, evaluation, and resource gates pass.

**Expected proposed files/modules**

- Future native provider adapter and inference runtime integration.
- Future model/tokenizer artifact compatibility and readiness checks.
- Future native provider tests and rollback behavior.
- No change to Ollama default until separate replacement approval.

**Prerequisites**

- Separate native-brain approvals.
- Working model weights, tokenizer, and inference runtime.
- Independent English, Hindi, Hinglish, and mixed-script evidence.
- Hardware, offline, security, resource, and rollback acceptance.

**Required tests and acceptance**

- Provider conformance and capability reporting.
- No silent fallback in native-only mode.
- Ollama remains operational until release acceptance.
- Independent quality, safety, resource, offline, and rollback gates.

**Security, privacy, compatibility risks**

- External AI fallback or early provider switch can violate Veronica ownership goals.
- Model/tokenizer incompatibility can break generation or tool behavior.
- Artifact supply-chain or resource exhaustion can compromise operation.

**Rollback/recovery**

- Keep Ollama as the current/default provider throughout native-provider development and validation.
- Ollama remains available during native-provider development and validation.
- Switching away from Ollama requires a successful independent acceptance review and explicit user approval.
- No automatic provider switch or silent fallback is permitted; on rollback or validation failure, retain Ollama and disable native mode under the approved rollback plan.

**User approval gate**

Separate native integration approval and separate provider-replacement/release approval.

## 7. Cross-phase safety rules

Do not change multiple independent subsystems simultaneously. In particular:

- Do not combine an AIService refactor with a database migration.
- Do not combine framework adoption with native-provider work.
- Do not add API authentication and persistent conversations in the same unbounded change.
- Do not alter memory, tools, provider defaults, and listener behavior in one phase.
- Do not add desktop or web clients before API behavior and ownership are stable.
- Do not interpret an application-layer approval as a native-brain, data, or training approval.

At every stage, preserve:

- Existing CLI commands and provider behavior unless a separate change is approved.
- Ollama as the current development/default provider.
- SQLite memory semantics and data files.
- Existing tool allowlist and confirmation behavior.
- English, Hindi, Hinglish, and mixed-script equal priority.
- Existing online/offline boundaries.
- Existing untracked files and unrelated worktree changes.

## 8. Blockers and unresolved prerequisites

Implementation is blocked until the applicable items are resolved:

- C3C-01 package/version/dependency review remains open; the FastAPI framework-selection decision is resolved.
- C3C-02 through C3C-18.
- C3D-01 through C3D-16.
- A-11 client scope is approved; transport, integration, authentication, and security details remain pending.
- Exact A-12 listener/deployment mode and security model.
- Exact A-13 resource limits, cancellation guarantees, retry, and idempotency semantics.
- Exact A-15 repository/migration plan and future PostgreSQL trigger.
- Per-install credential design and secure storage.
- Conversation retention, TTL, deletion, export, and persistence policy.
- Memory retrieval default and trusted write confirmation UX.
- Knowledge source approval, provenance, licensing, parser, and deletion policy.
- Framework and dependency compatibility/security review.
- Measured hardware/resource acceptance criteria.
- Desktop/web/external-client scope and authentication.
- Native model, tokenizer, dataset, training, runtime, and provider replacement approvals.

## 9. Approval and execution record

For each future execution stage, the approving record must include:

- The exact Phase H number and objective.
- Approved files/modules and explicit exclusions.
- Approved tests and acceptance thresholds.
- Identity, authorization, privacy, persistence, and network scope.
- Dependency package and version scope, if applicable.
- Ollama/provider behavior and fallback exclusions.
- Rollback/recovery steps.
- Independent reviewer or verification evidence where required.

Execution is complete only after the stage's tests and acceptance review pass. A completed plan or passing design review does not pass the execution gate.

## 10. Work-status matrix

| Area | Phase 3G status | Phase 3H status | Work completed |
|---|---|---|---|
| A-01–A-15 architectural directions | Approved or approved with mapping clarification | Proposed implementation sequence | None |
| C3C/C3D decisions | Pending unless separately approved | Prerequisites for implementation stages | None |
| Shared application layer | Approved architecture direction | Proposed H1/H2 | Not implemented |
| AIService | Approved gradual-refactor direction | Proposed H2 | Not implemented |
| Conversation isolation | Approved architecture direction | Proposed H3/H7 | Not implemented |
| Memory | Approved explicit-save direction | Proposed H8 | Not implemented |
| Knowledge | Approved source-governance direction | Proposed H9 | Not implemented |
| FastAPI/API | Approved framework direction; contracts pending | Proposed H6 | Not implemented |
| Authentication | Per-install credential approved; storage details pending | Proposed H6 | Not implemented |
| Deployment | Localhost-default direction approved; exposure details pending | Proposed H6/H10 | Not implemented |
| Database | SQLite/default and PostgreSQL/future direction | Proposed H11 | Not implemented |
| Workers/observability/testing | Approved directions | Proposed H4 and each phase test plan | Not implemented |
| Native brain/provider replacement | Separate future gates | Proposed H12 and native-roadmap dependency | Not implemented |

## 11. Final planning verdict

**PHASE 3H DOCUMENTED — IMPLEMENTATION NOT AUTHORIZED — NO WORK COMPLETED.**

The future implementation should begin only with H0 and a separately approved named scope. H1 or later work may proceed only after the required decision closure, security review, exact file list, tests, exclusions, rollback plan, and user approval gate are satisfied.
