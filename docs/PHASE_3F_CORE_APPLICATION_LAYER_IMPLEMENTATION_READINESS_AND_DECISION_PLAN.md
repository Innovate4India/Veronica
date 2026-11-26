# Phase 3F: Core Application Layer Implementation Readiness and Decision Plan

**Status:** Documentation-only readiness plan. No implementation, dependency, data, training, inference, or provider-switch work is authorized by this document.

## 1. Purpose and governing boundaries

This plan assesses readiness for a small shared application layer and coordinates that work with Veronica's separately governed native-brain roadmap. It follows Phases 3A–3E and does not supersede their pending decisions or authorization gates.

The target architecture must let Veronica's own model generate every final answer in its eventual native mode. Ollama remains the current working and default provider until a Veronica-owned brain passes independent gates and the user separately approves a provider switch. External AI services must not silently become permanent answer generators.

The plan distinguishes:

- **Existing — verified:** observed in the inspected source or test files. Test claims are based on static inspection; no tests were run for this plan.
- **Proposed:** a design or future acceptance requirement, not existing behavior.
- **Pending:** requires explicit user approval or a future evidence-based decision.
- **Not authorized:** outside this documentation-only task and not approved by this plan.

English, Hindi written in Devanagari, and Hinglish written in Roman Hindi/code-switching remain equal priorities. Mixed-script inputs require a separate evaluation and report group. A pooled score must not conceal a weak result for any group.

Phase 2G D-01 was explicitly approved only for the objective of a controlled tokenizer comparison. It did **not** authorize running an experiment. D-02 through D-18 remain pending; experiment execution, data access, vocabulary fitting, training, inference implementation, and provider integration are not authorized here.

## 2. Verified current state

| Area | Existing — verified | What is not established |
|---|---|---|
| Provider contracts | `app/ai/base.py` defines provider-neutral messages, responses, capabilities, typed provider errors, and tool-call/result types. `app/ai/provider.py` registers providers and reads `VERONICA_AI_PROVIDER`, defaulting to `ollama`. | These are in-process contracts, not an API or application use-case layer. |
| Current and native providers | Ollama is the only complete current text-answer provider. `VeronicaModelProvider` is an unavailable scaffold and advertises no implemented answer-generation capabilities. | No Veronica-owned model, weights, tokenizer integration, or inference engine generates answers. |
| AI orchestration | `AIService` in `app/ai/service.py` calls the configured provider and coordinates role selection, teaching behavior, optional memory and tool use, and response validation. | It is synchronous and holds mutable conversation messages, role, preferred role, and teaching-session state. It has no principal, conversation ID, explicit request context, cancellation input, or ownership boundary. |
| CLI and startup | `dev_ai.py` constructs the provider, memory, optional tools/speech, and one `AIService` for its interactive loop. `run.py` invokes the minimal `app.main` scaffold. | No shared composition root exists; `app/services/__init__.py` is reserved and empty. The CLI does not require HTTP. |
| Memory | `MemoryService` uses a local SQLite `memories` table, with short-lived database connections and save/list/search/delete/clear operations. Saving is explicit in the CLI; matching memories may be retrieved on ordinary turns when memory is enabled. | The schema has no owner/tenant key. There is no API authorization, migration framework, retention/backup service, or comprehensive sensitive-data classifier. |
| Tools | `ToolRegistry` is an instance-scoped allowlist that validates schemas, checks configured confirmation, dispatches tools, and omits raw arguments/results from its outcome logs. `ToolCallingService` bounds orchestration. | Tool validation is not user authentication or authorization. Model-generated tool calls do not establish user permission. |
| Configuration | `app/config.py` supplies environment-backed provider, memory, and optional feature settings, including a bounded CLI history setting. | There is no backend lifecycle, API identity, API request configuration, or server configuration. |
| Backend and clients | No Veronica HTTP API, server, endpoint, authentication system, or desktop/web integration was found. | FastAPI remains a candidate only; no framework or API is selected, installed, or implemented. |
| Existing tests | Static review found provider/adapter, AI orchestration, memory, tool, CLI, configuration, and selected optional-integration tests (listed in the inspection record). | They do not establish shared application composition, API authentication/authorization, tenant ownership, or cross-request/user context isolation. |

### Existing behavior versus target architecture

The usable implementation base is the provider-neutral contract, `AIService`, local memory service, tool registry/orchestration, and `dev_ai.py`. The proposed application/use-case layer would sit between clients and these services. It must not be described as already existing, and it must not turn a future API into a prerequisite for the existing CLI.

## 3. Smallest useful application-layer scope

### Proposed boundary

The smallest useful shared layer is a transport-independent set of application operations plus an explicit composition boundary. It coordinates trusted inputs and existing services; it is not a new model, a database redesign, or an HTTP server.

Candidate operations, names illustrative only:

| Operation | Minimum responsibility |
|---|---|
| `generate_chat_turn` | Validate a user turn, resolve only request-scoped or explicitly owned conversation context, apply approved memory/tool policy, call provider-neutral orchestration, and return a typed result or explicit failure. |
| `create_conversation` / `clear_conversation` | Manage an explicitly identified ephemeral conversation if that lifecycle is approved. |
| Memory operations | Wrap existing memory operations with consent, owner, and permission checks before any new client/API access. |
| `get_model_metadata` / `get_readiness` | Report the configured provider and actual capabilities truthfully; readiness must not imply a native model exists. |
| Knowledge search | Future-only operation over approved, access-controlled sources; no knowledge store or ingestion is implied. |

Inputs and results should be transport-neutral. Application operations should not accept framework request/response objects, HTTP status codes, arbitrary provider settings, untrusted owner IDs as identity proof, or raw provider wire payloads.

### Client paths

| Client | Proposed connection |
|---|---|
| Existing CLI (`dev_ai.py`) | Direct in-process application/use-case calls; no HTTP server required. |
| Future desktop | Separately approved local API or application facade. |
| Future web | Authenticated API with reviewed browser protections. |
| Authorized external applications | Versioned HTTP API with separately approved identity, scopes, quotas, revocation, and deployment. |

All clients should share application semantics and provider-neutral services, not necessarily a transport. Desktop, web, and external API integrations remain proposed, not implemented.

### Explicit initial exclusions

No chat/API routes, server, account system, multi-user persistence, transcript archive, knowledge ingestion, UI, new framework, or dependency is part of the minimum application-layer scope. A future implementation must name any additions separately.

## 4. Composition and dependency lifecycle

There is no current shared composition root. `dev_ai.main()` currently creates the configured provider, memory service, optional tool services, one `AIService`, and then owns the CLI loop. `app.main()` is a minimal Phase 1 scaffold.

### Proposed responsibilities

1. **Configuration boundary:** read and validate trusted operator settings once at process startup; never accept secrets, provider endpoints, or model paths from an ordinary client request.
2. **Provider construction:** use the existing registry and provider-neutral interface. Keep Ollama as the current default. Do not silently substitute another provider if startup or generation fails.
3. **Infrastructure construction:** create the existing memory adapter and only the explicitly configured tool registry. Avoid new persistence or migrations without separate authorization.
4. **Application services:** compose transport-neutral use cases and policy boundaries. Do not retain request-specific user or conversation state in module globals.
5. **Request/session state:** construct a request-scoped context for each one-shot request and an explicitly owner-bound context for a continuing conversation. Session state must not be reused across unrelated requests.
6. **Client lifecycle:** provide the same application semantics to the CLI directly. Create API lifecycle hooks only in a separately authorized server phase.
7. **Shutdown and readiness:** close resources and stop bounded work when applicable; readiness must reflect the configured provider and required dependencies, not merely a running process.

### Proposed lifetime guidance

| Dependency/state | Candidate lifetime | Required constraint |
|---|---|---|
| Validated immutable configuration | Process | Keep secret values out of logs and client responses. |
| Provider adapter/client | Process or bounded worker, after its concurrency safety is verified | Do not assume a shared client is thread-safe. Do not create unbounded model workers or duplicate model loads. |
| Memory service/database | Process-level adapter with short-lived DB connections, matching current design | Any future multi-user use requires ownership enforcement at every repository operation; current SQLite schema does not provide it. |
| Tool registry | Application instance, configured allowlist | Per-operation authorization and confirmation remain mandatory; registration alone is not user permission. |
| Request metadata/context | One request | Contains only server-verified principal and permission evidence for API operations. |
| Conversation state | Explicit owner-bound conversation lifecycle, if approved | Never use a shared `AIService` history as implicit API context. TTL, size, persistence, and concurrency semantics require approval. |

The provider's safe concurrency strategy, service lifetimes, and exact composition API remain pending design decisions. This plan does not choose a DI framework or require a particular package layout.

## 5. AIService evolution

`AIService` contains useful behavior but currently combines orchestration with mutable session state and policy. Three approaches were considered:

| Approach | Benefits | Risks |
|---|---|---|
| Refactor gradually | Can preserve current CLI semantics while separating per-turn execution from conversation/role/teaching state and memory/tool policy. | Requires characterization tests and careful compatibility work; behavior can regress if responsibilities are split prematurely. |
| Wrap unchanged `AIService` | Small short-term change and may isolate CLI construction behind a facade. | Does not by itself make a shared instance safe for concurrent requests or users; wrapper could conceal rather than remove shared mutable state. |
| Replace it | Could produce a clean request-oriented API. | Highest regression risk for CLI commands, role/teaching behavior, memory intent/retrieval, tool limits, provider errors, and response quality. |

**Recommendation — pending approval:** prefer a gradual refactor with a compatibility wrapper where useful. First characterize current behavior and preserve the CLI, then isolate conversation/session state from a request-oriented turn operation. Do not share one mutable `AIService` instance across unrelated API users or one-shot requests. Replacement is not justified before the current behavior and call sites are fully characterized.

Existing CLI behavior requiring parity includes its current provider default, interactive history, role and teaching state, explicit memory commands/confirmation, optional tool setup, error reporting, and exit/clear commands. Any intentional behavior change requires separate scope and approval.

## 6. Request and conversation isolation

Isolation is a prerequisite for any multi-request application/API use; it is **not currently guaranteed** by `AIService`.

### Proposed rules

- **One-shot request:** isolated from every other request, conversation, CLI session, and principal. Use only the current request and explicitly authorized resources selected for that request. Do not read or append shared in-process conversation history.
- **Continuing conversation:** load context only from the explicitly identified conversation after verifying the authenticated owner and access policy; append the turn only after required write authorization.
- **Conversation authorization:** require both `conversation:read` and `conversation:write` for a turn that reads prior context and appends a new turn, or use a dedicated `conversation:turn` permission explicitly defined to grant both semantics for that owner's conversation. The final choice remains pending under C3D-12.
- **Memory and knowledge:** include only when the relevant user policy, consent, request selection, and authorization permit it. They remain distinct from conversation history and from training data.
- **State ownership:** do not keep per-user or per-conversation message history in a singleton `AIService`, provider instance, or application-global list. Any future cache must be scoped by trusted owner and conversation identity and must re-check access and expiry.
- **Concurrency:** define behavior for simultaneous turns in one conversation (serialization, optimistic versioning, or another approved policy) before enabling it. Bound provider work and account for calls that continue after client cancellation.
- **Failures and retries:** do not fabricate success on provider failure. A timeout does not establish that work or a tool side effect did not happen; idempotency/retry behavior must be approved.

### Required future negative tests

1. Interleave one-shot requests and prove neither receives the other's messages.
2. Interleave separate owners' conversations and prove there is no cross-owner context, append, cache, or memory leakage.
3. Prove a one-shot request never reads any implicit history.
4. Prove a continuing turn receives only its authorized conversation and fails without the selected read/write permission model.
5. Exercise concurrent turns, clear/expiry, cancellation, provider failure, and retry without context replay or duplicate consequential effects.

These are proposed acceptance tests; none are established by current tests.

## 7. Identity, security, persistence, and provider decisions

No user/account authentication, API authorization, tenant ownership, or API security system exists. Localhost/loopback alone would not authenticate callers. A future API must separately resolve authenticated principal, operation scope, resource ownership, consent, tool permission, and quota.

The current SQLite memory store is appropriate only within its verified local single-user boundary. Do not infer multi-user readiness. Conversation persistence remains ephemeral by default in prior plans; durable transcripts, retention, export, backup, deletion, and migrations need explicit decisions.

Tool requests remain untrusted. Application policy must validate the allowlist, schema, user/client permission, and confirmation independently. Online egress remains optional and separately disclosed; offline mode must enforce egress limits at the service/network boundary.

The application layer must preserve provider-neutral contracts and current Ollama behavior. No native-only mode may silently fall back to external AI. The Veronica provider scaffold must not be represented as a working model.

## 8. Separate native-brain roadmap

Native-brain work is a separate roadmap, not a dependency that blocks all provider-neutral application design. Conversely, an application-layer authorization does not authorize any native-brain activity.

| Native stage | Scope and deliverables | Dependencies and exit evidence | Authorization status / exclusions |
|---|---|---|---|
| N0 — Architecture and ownership | Define candidate native model architecture, purpose, target hardware, ownership boundaries, and quality/safety goals. | Record architecture choices and constraints; distinguish design from implementation. | Planning only unless separately authorized; no model downloads or training. |
| N1 — Tokenizer decision closure | Reconcile existing byte-level prototype with outstanding tokenizer decisions; define comparison protocol, measurable thresholds, language groups, and artifact/license review. | Resolve applicable D-02–D-18 and tokenizer compatibility questions; D-01 currently approves only the comparison objective. | Experiment execution remains **NOT AUTHORIZED**; no fitting, vocabulary build, or corpus access. |
| N2 — Data governance and licensing | Define permitted source classes, provenance, consent, licenses, privacy, retention, deletion, and contamination controls. | Legal/privacy review and source-by-source authorization before any acquisition or processing. | No dataset collection, scraping, or corpus processing authorized. Conversations and SQLite memory are not automatic training data. |
| N3 — Model/training design | Specify candidate model family/size, training objective, compute budget, reproducibility, safety controls, and evaluation plan. | N0–N2 decisions; approved hardware and dataset plan. | Planning only; no package installation, training, fine-tuning, or checkpoint creation authorized. |
| N4 — Data preparation and training | If later authorized, prepare only approved/licensed data and train a Veronica-owned model under an auditable run plan. | Explicit data access, processing, dependency, compute, and training approvals; governance and tokenizer gates passed. | Not authorized by this plan. No real corpora or private memory. |
| N5 — Evaluation and quality gates | Evaluate factuality, instruction following, safety, robustness, latency, resource use, and reliability. | Independently approved evaluation evidence and thresholds. Report English, Hindi, Hinglish separately and mixed-script separately. | No experiments or evaluation data acquisition authorized here; no aggregate-only pass. |
| N6 — Native inference runtime | Design and implement local inference, model/tokenizer compatibility, resource limits, cancellation, offline behavior, and packaging. | Validated model artifacts, hardware evidence, security/supply-chain review, offline tests, and explicit runtime authorization. | No inference implementation or dependency installation authorized. |
| N7 — Native provider adapter | Add a non-default provider behind existing provider-neutral contracts, with truthful metadata and conformance/failure tests. | N4–N6 completed; adapter authorization; no capability advertised until implemented and tested. | No provider integration authorized here; Ollama remains current/default. |
| N8 — Independent validation and switch gate | Validate quality, safety, privacy, offline operation, hardware, rollback, and failure handling independently of the implementation team. | All previous stages pass; documented rollback and support plan. | Provider switch requires separate explicit user approval; no silent or automatic replacement. |

### Language and offline requirements for every relevant native gate

- Equal priority and separately reported results for English, Hindi (Devanagari), and Hinglish (Roman Hindi/code-switching).
- Mixed-script evaluation reported as an additional independent group.
- No language-based default that downgrades one group; preserve Unicode and report sample counts, errors, quality, latency, and resource use by group.
- Define offline mode, required model/tokenizer assets, dependency availability, device/CPU/GPU/RAM/VRAM constraints, and no-egress behavior using measured evidence.
- Approve thresholds before evaluation; a pooled metric cannot hide a deficient group.

## 9. Parallel development and integration gates

### Work that can proceed independently, if separately authorized

- Application-layer contract design, CLI behavior characterization, and a test plan can proceed without model training.
- Provider-neutral use-case and composition design can proceed while the native architecture and data governance are researched, provided it does not change current provider behavior.
- Native architecture, data-policy, tokenizer-decision, and hardware research can proceed as separately scoped planning work without implementing the application layer.
- Existing Ollama-backed CLI work may continue under its existing scope; it does not grant API, data, training, or provider-switch authorization.

### Work that requires an integration gate

- A native provider adapter requires a working, independently validated inference runtime and model/tokenizer artifacts.
- Any API chat integration requires approved identity, authorization, conversation ownership, request isolation, concurrency, limits, and error semantics.
- Memory or knowledge exposure requires separate consent, ownership, retention/deletion, and source-rights decisions.
- Desktop, web, and external clients require their own client, authentication, browser/network, privacy, and exposure approvals.
- Replacing Ollama requires all native quality/resource/security/offline gates and a separate explicit provider-switch approval.

Parallelism does not waive dependencies or approvals. Application-layer progress must not automatically trigger tokenizer experiments, data acquisition, model training, inference implementation, API exposure, or provider switching.

## 10. Dependency-aware application-layer roadmap

Every phase is proposed future work. Each requires a separate implementation authorization naming its files/components, tests, and exclusions.

| Stage | Scope and deliverables | Prerequisites | Proposed tests and exit criteria | Explicit exclusions unless separately approved |
|---|---|---|---|---|
| A0 — Decision closure | Resolve relevant 3C/3D/3E decisions: app boundary, AIService direction, identity, persistence, concurrency, client scope, framework, and resource limits. | Review this plan and record explicit decisions. | Decision register complete; threat/data-flow and ownership model reviewed. | No code, packages, server, migrations, or provider changes. |
| A1 — CLI characterization and boundary design | Specify transport-neutral inputs/results/errors, composition lifecycle, CLI compatibility matrix, and state ownership. | A0 decisions; inspect existing call sites and behavior. | Baseline current CLI/provider/memory/tool behavior; identify stateful fields and dependencies. | No API, routes, or behavior change. |
| A2 — Minimal shared composition/use cases | If authorized, factor or add the smallest shared application layer and wire `dev_ai.py` through it directly. | A1 contract approved; no HTTP required; dependency lifetime and error behavior decided. | Existing CLI regression tests; provider construction/default; memory/tool behavior; focused application-use-case and one-shot isolation tests. | No listener, authentication system, multi-user persistence, database migration, or provider change. |
| A3 — Isolation and concurrency hardening | Separate request turns from session state; define explicit conversation ownership and concurrent turn behavior. | A2; C3D-12 decision and identity/ownership model approved. | Negative one-shot and cross-owner tests; simultaneous requests; cancellation/failure/retry accounting. | No durable transcript archive or unapproved shared mutable history. |
| A4 — Local API foundation (optional) | Select and review a framework, then implement only the approved local lifecycle and minimal health/model metadata contract. | A0–A3 as applicable; framework/dependency, authentication, browser, deployment, and security approvals. | API schema/auth tests, sanitized errors/readiness, loopback/no-public-bind tests, resource limits. | No public/LAN exposure, transcript persistence, memory writes, knowledge ingestion, or provider switch by default. |
| A5 — Approved chat/conversation API (optional) | Expose versioned chat and ephemeral conversation operations. | A4; explicit API authorization, scopes, ownership, read/write semantics, TTL/limits, idempotency, cancellation, and concurrency decisions. | Contract, negative authorization, isolation, limits, Unicode, provider failure, offline-egress tests. | No persistent transcripts, implicit memory/knowledge context, or silent provider fallback. |
| A6 — Memory/knowledge/client expansion (optional) | Add only individually approved memory, approved-source search, and client integrations. | Separate consent, ownership, source rights, retention/deletion, browser/network and client approvals. | Consent and ownership tests; source provenance/access tests; client security, egress, and language-parity tests. | No automatic training, source ingestion, public exposure, or migrations unless explicitly scoped. |
| A7 — Native provider integration (separate track) | Integrate a non-default native adapter only after native roadmap gates pass. | Native N0–N8 dependencies and separate adapter approval. | Provider conformance, capability accuracy, per-language/mixed-script, offline, resource, safety, rollback tests. | No provider switch without separate release approval. |

## 11. Risks and measurable acceptance criteria

| Risk | Required acceptance evidence before relevant release |
|---|---|
| CLI regression | Existing `dev_ai.py` commands, conversation history, role/teaching behavior, memory consent, tool behavior, provider default, and error handling remain covered by regression tests. No HTTP requirement is introduced for ordinary CLI use. |
| Cross-request or cross-user leakage | Negative tests prove one-shot isolation and owner-bound conversation/memory/knowledge access across interleaved requests, caches, concurrent work, and failures. |
| Provider failure or silent fallback | Provider errors map to explicit failures; no success-shaped answer is returned; native-only operation cannot silently call Ollama or another external answer provider. Ollama remains the current development default until separately replaced. |
| Concurrency and resource exhaustion | Measured bounds for queueing, inference concurrency, timeouts, output, memory, and cancellation; tests cover saturation and work that outlives client cancellation. No unbounded workers or duplicate model loading. |
| Offline operation and egress | Offline tests show optional network capabilities are unavailable and no unauthorized outbound request occurs. User-facing state must accurately disclose any approved egress. |
| Privacy and consent | No automatic transcript persistence or training; explicit memory consent; retention, export, deletion, backup, and logs have approved handling before persistent APIs. |
| Tool authorization | Model-generated tool calls cannot authorize themselves; allowlist, schema, permission, and confirmation are tested independently. |
| Language quality and Unicode | Report correctness and quality separately for English, Hindi, and Hinglish, with mixed-script separate; preserve input/output Unicode; report errors, latency, and resource use per group. No unapproved threshold or dataset is assumed. |
| Native model readiness | Independent validation demonstrates required quality, safety, hardware, security, offline, and rollback gates before any provider-switch request. A working adapter alone is insufficient. |

Acceptance thresholds, hardware targets, retention periods, timeout values, and supported-client lists remain pending and must be approved rather than invented in implementation.

## 12. Decision register

Recommendations are advisory. Each decision below remains **PENDING USER APPROVAL** unless later resolved explicitly in a separate approval. The prior D-01 tokenizer-comparison objective approval is limited as stated in Section 1 and is not an approval to execute work.

| ID | Question | Options | Recommendation, if justified | Dependencies | Approval status |
|---|---|---|---|---|---|
| A-01 | What is the smallest shared application boundary? | Directly retain CLI wiring; introduce transport-neutral use cases/composition; larger service framework. | Start with minimal use cases and explicit composition; keep CLI in-process. | A1 behavior characterization; CLI parity. | PENDING |
| A-02 | How should `AIService` evolve? | Gradual refactor; wrapper only; replacement. | Gradual refactor with a compatibility wrapper where useful. | A1 call-site and state review; regression tests. | PENDING |
| A-03 | What are service and dependency lifetimes? | Per request; process-level; bounded worker; mixed explicit scopes. | Immutable config/process adapters where safe; request-scoped context; owner-bound conversation state. | Provider thread-safety and resource measurements. | PENDING |
| A-04 | What conversation permission is required for a chat turn? | `conversation:read` + `conversation:write`; dedicated `conversation:turn` with explicit read/append semantics. | Require both semantics and least privilege; keep exact form pending. | Identity/scopes; C3D-12. | PENDING |
| A-05 | How are one-shot and continuing requests isolated? | Per-request context; explicit owned conversation; shared service history. | Per-request isolation by default; only explicit, authorized conversations may carry context. | A2/A3; negative isolation tests. | PENDING |
| A-06 | What local identity/authentication applies if an API is built? | No auth; OS identity; local credential; scoped short-lived token; IPC. | Do not rely on loopback alone; use authenticated, least-privilege local access if approved. | C3C identity decisions; deployment model. | PENDING |
| A-07 | Is multi-user support in scope? | Single-user local only; future multi-user; both. | Defer multi-user until identity, ownership, storage, and operations are designed. | Tenant model and storage evidence. | PENDING |
| A-08 | What is the API conversation retention policy? | Ephemeral; opt-in persistence; persistent by default. | Ephemeral by default; no durable transcript without separate decision. | Consent, deletion, export, backup, ownership. | PENDING |
| A-09 | What memory behavior is permitted? | Current CLI behavior only; API opt-in retrieval; preference-based retrieval; explicit operation per use. | Keep writes user-approved; separately decide API retrieval and disclose it. | User consent, scopes, owner-bound storage. | PENDING |
| A-10 | Which backend framework/dependencies should be adopted? | No API yet; FastAPI; Flask; Starlette; another reviewed framework. | Evaluate FastAPI first; select only after compatibility, security, dependency, and concurrency review. | API authorization; packaging/update policy; resource strategy. | PENDING |
| A-11 | Which clients and transport modes are in scope? | CLI only; local desktop; local web; external/remote clients. | Preserve direct CLI; approve each future API client separately. | A0 decisions; client-specific security. | PENDING |
| A-12 | Is any network listener allowed? | No listener; authenticated loopback; LAN; remote. | No listener until explicitly approved; loopback is not authentication. | Identity, browser protection, deployment and operations. | PENDING |
| A-13 | What are concurrency, timeout, cancellation, and retry semantics? | Bounded synchronous; worker/process; streaming/jobs; best-effort cancellation. | Measure first; use bounded work and explicit failure/idempotency behavior. | Hardware/provider capabilities; framework and client needs. | PENDING |
| A-14 | What tool authorization and confirmation model applies to clients? | Current CLI policy only; per-client scopes; per-tool confirmation/approval. | Server-side least privilege plus allowlist, schema, and action confirmation. | Identity, tool risk classification, client UX. | PENDING |
| A-15 | How may persistence evolve beyond current SQLite memory? | Keep current local SQLite only; approved schema extension; server database. | Keep the current schema within its existing single-user use; measure needs before changing storage. | Ownership, backups, migrations, workload, retention. | PENDING |
| N-01 | Which native model architecture/size is appropriate? | Candidate model families/sizes and training approaches. | Decide only from approved capability, hardware, and governance evidence. | Hardware targets, data policy, evaluation goals. | PENDING |
| N-02 | What tokenizer approach and experiment protocol are approved? | Existing byte baseline; controlled comparison; other reviewed options. | Close tokenizer decisions and pre-register measures before any experiment. | Phase 2 decisions; language and licensing review. D-01 authorizes objective only. | PENDING |
| N-03 | Which training/evaluation sources are permitted? | No new data; specific licensed/consented sources; other governed sources. | Approve source-by-source provenance, rights, privacy, retention, and deletion. | Legal/privacy review, licenses, consent. | PENDING |
| N-04 | Is training or fine-tuning authorized, and under what budget? | No training; from-scratch training; fine-tuning; staged pilot. | No training until data, compute, dependency, safety, and reproducibility gates are approved. | N-01–N-03 and compute plan. | PENDING |
| N-05 | What quality and safety thresholds decide model readiness? | Per-group thresholds; aggregate-only threshold; staged benchmark. | Require separate English/Hindi/Hinglish and mixed-script reporting with approved per-group gates. | Approved evaluation plan and lawful data. | PENDING |
| N-06 | Which inference runtime and packaging model are acceptable? | Existing libraries; new runtime/dependencies; CPU/GPU variants. | Select only after license, security, offline, hardware, and reproducibility review. | Trained/approved artifacts and target devices. | PENDING |
| N-07 | How will native provider integration be validated? | No integration; non-default adapter; later default switch. | First add only a non-default adapter after independent conformance and failure tests. | Native model/runtime gates; provider-neutral contract. | PENDING |
| N-08 | What evidence and approval are required to replace Ollama? | Keep Ollama; parallel optional native provider; replace default. | Keep Ollama current/default until all independent gates pass; require separate switch approval. | N-01–N-07, rollback, support plan. | PENDING |

## 13. Implementation authorization checklist

No checklist item in this document is itself authorization. Before implementation begins, the user must issue a separate, explicit scope naming the phase, allowed files/components, validation, and exclusions.

### Application-layer authorization

- [ ] Resolve the applicable A-01–A-15 decisions, including AIService evolution, service lifetimes, isolation, identity, memory behavior, persistence, framework, client scope, and concurrency.
- [ ] Approve the exact first implementation phase and its file/component boundaries.
- [ ] Approve the CLI compatibility requirements and baseline/focused regression suite.
- [ ] Approve one-shot isolation, explicit conversation ownership, read/write permission semantics, and negative-test expectations.
- [ ] Approve provider and dependency lifecycle, failure mapping, cancellation/retry behavior, and measurable resource limits.
- [ ] Approve whether the initial scope is strictly in-process; any API, framework, package, listener, client, or network exposure needs separate explicit authorization.
- [ ] Approve privacy, consent, retention, deletion, backup, audit, and migration policy for every data operation in scope.
- [ ] Confirm Ollama remains the current working/default provider and no provider behavior changes are in scope unless separately authorized.

### Native-brain authorization — separate from application work

- [ ] Approve model architecture and hardware research/targets separately.
- [ ] Resolve tokenizer decisions and explicitly authorize any experiment execution; D-01's objective approval alone is insufficient.
- [ ] Approve each data source, license, privacy/consent boundary, acquisition, and processing plan.
- [ ] Explicitly authorize dependencies, training/fine-tuning, compute budget, and artifact creation before those activities.
- [ ] Approve evaluation datasets/methods and thresholds, with separate English, Hindi, Hinglish, and mixed-script results.
- [ ] Approve inference runtime implementation and offline/resource/security validation separately.
- [ ] Approve native provider integration only after independent evidence; keep it non-default initially unless separately decided.
- [ ] Approve provider replacement in a separate explicit decision after all acceptance and rollback gates pass.

An application-layer approval does not grant native-brain approvals. Native-brain progress does not authorize API exposure or data access. Nothing here authorizes public deployment.

## 14. Explicitly unauthorized work

This plan does not authorize:

- Source, test, configuration, dependency, database, schema, migration, or existing documentation changes.
- Installing/selecting packages, creating application services, changing `AIService`, or altering CLI behavior.
- Creating or starting an API/server, endpoints, authentication, client integrations, or any listener.
- LAN/public exposure, persistent conversation storage, memory API, knowledge ingestion, or multi-user access.
- Dataset acquisition, scraping, corpus processing, tokenizer experiment/fitting, vocabulary creation, model training/fine-tuning, or inference implementation.
- Downloading model/tokenizer artifacts or integrating a native provider.
- Changing Ollama configuration/default, replacing Ollama, or silently falling back to an external answer service in native-only mode.
- Committing, amending, pushing, or publishing.

## 15. Final assessment and recommended next phase

**Implementation readiness is partial, not complete.** The repository has reusable provider-neutral contracts and functional CLI, AI orchestration, memory, and tool components. It lacks a shared application composition/use-case boundary, safe request/owner isolation, API identity/authorization, and API/backend lifecycle.

**Recommended next phase:** a separately authorized, in-process application-boundary design and implementation readiness closure: characterize current CLI behavior, settle A-01–A-05 and relevant security/resource decisions, then scope a minimal composition/use-case layer that the CLI can call directly. Do not begin an API/server phase until its separate identity, framework, exposure, and contract gates are resolved.

Keep the native-brain roadmap separate. Continue treating D-01 as approval of the comparison objective only; no experiment, dataset work, training, inference, or provider integration follows automatically. Ollama remains the current working/default provider until the native model passes independent gates and a separate provider-switch approval is granted.

## Inspection record

Read-only inspection for this plan included the complete Phase 3A, 3B, 3C, 3D, and 3E planning documents. Relevant implementation inspected:

- `app/ai/base.py`, `app/ai/provider.py`, `app/ai/service.py`, `app/ai/tool_calling.py`
- `app/memory/database.py`, `app/memory/service.py`
- `app/tools/registry.py`
- `app/config.py`, `app/main.py`, `app/services/__init__.py`, `dev_ai.py`

Relevant test files inspected statically:

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

The tests cover provider selection/contracts and adapter behavior, AIService history within one service instance, role/teaching/tool behavior, local memory operations and explicit memory intent, tool validation/confirmation/dispatch, CLI behavior, and selected optional integrations. Static inspection did not find coverage establishing shared application composition, HTTP/API behavior, authentication/authorization, multi-tenant ownership, or cross-request/user context isolation. No tests were run for this documentation-only task.

No dataset, model artifact, or user database was accessed. No package was installed, no experiment or training was run, no server was started, and no source, test, configuration, dependency, database, or existing documentation file was changed for this task.
