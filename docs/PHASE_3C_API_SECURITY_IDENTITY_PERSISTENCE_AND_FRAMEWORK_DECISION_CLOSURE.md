# Phase 3C: API Security, Identity, Persistence, and Framework Decision Closure

**Status:** Planning and decision support only. No framework, identity mechanism, network exposure, persistence policy, or implementation is approved by this document.

## 1. Current-state verification

This plan follows the complete Phase 3A architecture plan and Phase 3B requirements/API contract plan. Their diagrams, routes, security controls, FastAPI discussion, and roadmaps are proposals unless separately identified below as existing verified functionality.

### Already implemented and verified

| Area | Verified current capability | Boundary |
|---|---|---|
| Provider-neutral contracts | `AIProvider`, typed provider errors, capability metadata, neutral tool-call/result types, and provider registration exist. | These are in-process Python interfaces, not API authentication or an HTTP contract. |
| Current answer provider | The provider registry defaults to Ollama; `OllamaClient` is the current complete answer provider and restricts its configured URL to loopback HTTP. | Keep the current provider operational. Ollama is not the eventual independently owned answer brain. |
| Native provider | `VeronicaModelProvider` is a scaffold; it advertises no implemented text, streaming, tool, or vision capabilities and cannot generate answers. | It is not production-ready or a replacement. |
| Application service and CLI | `AIService` handles text, bounded in-process conversation history, role logic, optional tools, and memory integration. `dev_ai.py` composes services and runs the interactive loop. `run.py` invokes the minimal `app.main` scaffold. | No shared HTTP backend, server lifecycle, multi-client authentication, or persistent transcript store exists. |
| Memory and SQLite | `MemoryDatabase` and `MemoryService` store user-approved local memories and support search/list/delete/clear. Obvious credential patterns are rejected. | There is no user/tenant key, encryption/key management, migration framework, retention/backup service, or authenticated API. |
| Memory consent nuance | The CLI requires an explicit remember request before saving; the service recognizes that intent. For ordinary turns, `AIService` can retrieve matching stored memories automatically when memory service is enabled. | Explicit save consent does not mean retrieval is always per-turn opt-in. Any future API default and user control must be decided without misrepresenting existing CLI behavior. |
| Tool security | Tools are instance-registered, schema-validated and dispatched through an allowlist; tools can require explicit confirmation. Tool logs omit arguments/results. | This is useful infrastructure, not a complete authorization, identity, or network security system. |
| Configuration and dependencies | Environment-backed settings exist. `requirements.txt` does not include FastAPI, an ASGI server, or an authentication package. | Framework and dependency selection remain open; no package is installed or chosen here. |
| Network features | Ollama is local loopback. Web search is optional and disabled by default; online Microsoft Neural TTS is opt-in. | No Veronica API listener exists. These optional features have their own outbound-data boundaries. |

### Proposed architecture from Phases 3A and 3B

- Shared application/use-case services behind a versioned API.
- FastAPI as a candidate framework; typed request validation and OpenAPI documentation.
- Proposed `/api/v1` chat, ephemeral conversation, memory, knowledge search, health/readiness, and model metadata routes.
- Authenticated principals, least-privilege scopes, per-resource ownership, bounded requests/queues, structured safe errors, and redacted audit events.
- Local-only service as the initial network boundary; LAN/remote operation only after a separate security decision.
- SQLite reuse for current local single-user memory, with future storage changes based on measured needs.

These are not implemented or approved settings.

### Recommendations in this document

Recommendations are advisory: start with an authenticated, single-user, loopback-only API if and when implementation is authorized; keep conversational transcripts ephemeral by default; reuse SQLite only within its present local memory boundary; use explicit least-privilege scopes; and evaluate FastAPI before alternatives because of its Python typing, validation, and OpenAPI fit.

### Decisions requiring explicit user approval

Framework/dependencies, local identity and credential provisioning, future multi-user identity, token/session form and lifetime, permission scopes, network reachability, conversation persistence, memory retrieval/consent policy, database growth, retention/backups, operational limits, and audit policy remain pending in the decision matrix (Section 7). None are marked approved.

### Not implemented

There is no FastAPI/Flask/Starlette server, API route, API schema, user/account system, authentication or authorization implementation, token store, public/LAN listener, persistent conversation system, multi-user database, knowledge database, API rate limiter, or API audit pipeline. No migration or database modification was made.

## 2. Backend framework decision

No framework is selected. FastAPI is a reasonable leading candidate, but its adoption and dependency versions require user approval and compatibility/security review.

| Criterion | FastAPI | Flask | Starlette | Django REST Framework |
|---|---|---|---|---|
| Existing Python architecture | Good fit with the current typed Python services and adapter approach. | Fits Python and can wrap the services, with a mostly synchronous mental model. | Fits ASGI and can provide a lightweight transport layer. | Fits Python but introduces a larger application and ORM/auth ecosystem than the current project. |
| API documentation | Schema-driven OpenAPI is a strong built-in benefit. | Usually needs an extension or separately maintained schema. | Core is intentionally lower-level; schema/documentation needs additional choices. | Schema support is available through the ecosystem, but adds configuration/dependencies. |
| Validation | Typed request/response models and validation are central strengths. | Validation/schema behavior needs extensions or explicit code. | Validation is not a full contract layer by itself; add and maintain a schema library. | Serializers provide established validation but require adopting its conventions. |
| Authentication integration | Security dependencies and middleware are composable, but FastAPI does not supply a complete product identity, consent, or authorization policy. | Mature extension options exist; the project must select and integrate them. | Authentication middleware is possible but more assembly is required. | Strong built-in user/auth/permission conventions, at the cost of broader framework adoption. |
| Async and inference | ASGI supports async I/O and network concurrency. | Straightforward synchronous routes; async support is not the primary differentiator. | Native ASGI foundation. | ASGI support exists, but framework choice does not make model inference nonblocking. |
| Synchronous calls | Existing `AIService`, SQLite, and Ollama calls are synchronous; FastAPI can run synchronous handlers in its execution model. | Naturally compatible with synchronous service calls. | Requires an explicit sync/worker strategy for blocking inference. | Synchronous application code is familiar, but expensive inference still needs bounded execution. |
| Maintenance/dependency cost | Additional FastAPI/Starlette/Pydantic/server dependencies and their upgrade/security lifecycle. | Core is relatively small; extensions can create their own dependency surface. | Smaller core, but assembling validation/auth/docs increases project-owned integration work. | Broad feature set and conventions, with higher initial integration and operational cost. |

### Recommendation — not an approval

Evaluate **FastAPI** first for a future local API because it aligns with Python type annotations and offers request validation and OpenAPI generation. Keep the application services and public contract independent of framework-specific models so the framework remains replaceable.

Before deciding:

- Verify supported Python versions, transitive dependency compatibility, license, security update cadence, packaging, and testability in Veronica's chosen environment.
- Decide how synchronous inference, SQLite I/O, cancellation, and timeouts execute without blocking the server or spawning duplicate model instances.
- Measure model memory before selecting web-worker count. Multiple workers may each load a model and exhaust limited RAM/VRAM.
- Confirm authentication, authorization, CSRF/origin policy, rate limiting, and secret handling are designed separately; FastAPI does not provide these policies automatically.
- Approve exact dependencies and versions in a future implementation task. Do not install anything as part of this phase.

No framework choice should force `dev_ai.py` to become an HTTP client. The CLI can call shared application services directly and remain usable without a server.

## 3. Identity and authentication

Authentication establishes *who or what is calling*. Authorization determines *which action and resource that principal may access*. Neither exists as a complete system in the repository.

### Single-user local mode

| Option | Advantages | Risks/trade-offs |
|---|---|---|
| No authentication; rely on loopback | Simple for a throwaway local prototype. | Not a safe default: other local processes and browser-origin attacks may reach the listener; it does not identify a user or client. |
| Current OS-user identity plus an installation-specific credential | Can align access with the logged-in user and separate local applications. | Requires secure provisioning, storage, revocation, and browser/native-client handling; same-user malware remains in scope. |
| Static API key in a config/environment file | Simple to prototype and easy to pass to clients. | Long-lived secrets can leak through process environments, config backups, logs, crash reports, or client storage; weak revocation/rotation if shared. |
| Short-lived bearer access token issued to an authenticated local client | Allows scopes, expiry, and revocation without credentials in URLs. | Requires a secure issuance/exchange mechanism and protected storage; does not itself establish a trustworthy user confirmation UX. |
| OS-specific IPC with OS access controls | Avoids an HTTP listener for some local clients. | Platform-specific, more difficult for web and external clients; not a universal API boundary. |

**Recommended safe initial default (pending approval):** do not expose an unauthenticated API. If a local API is later authorized, bind only to loopback and require authenticated, least-privilege access tied to the local user/client. Prefer short-lived credentials protected by the operating system or an equivalent approved secret store. Keep the CLI in-process where practical rather than forcing it through a local HTTP listener. Loopback is a network boundary, not authentication.

### Future multi-user mode

| Option | Advantages | Risks/trade-offs |
|---|---|---|
| Self-managed username/password accounts | Full product control; can work without a third-party identity service. | Veronica would own password hashing, reset, MFA, abuse prevention, breach response, session security, and lifecycle. High security/operations cost. |
| Established identity provider using OIDC/OAuth-based flows | Delegates mature identity lifecycle and can support external clients and revocation. | Adds a provider dependency, network/availability considerations, configuration complexity, and user-data processing; provider selection and privacy review required. |
| Organization-managed identity federation | Fits a controlled organizational deployment. | Not appropriate as an assumed consumer default; requires tenant administration and federation policy. |
| Shared static API key | Low setup friction. | Poor user attribution, broad privileges, difficult revocation, and unsafe multi-user isolation. Not recommended for multi-user access. |

**Recommendation — not an approval:** use an established identity provider or organization-managed federation for any future network-accessible multi-user service rather than inventing password handling. Retain a clearly defined single-user local mode. If an offline multi-user mode is required, treat that as a separate security and operations design, not an extension of the current SQLite assumptions.

### Sessions, tokens, permissions, and credentials

- Do not put credentials in query strings, URLs, prompts, ordinary logs, or source control.
- Compare opaque server-side sessions with signed self-contained tokens. A short-lived, revocable opaque token is the safer initial local-service recommendation because it can be invalidated centrally; JWT-like tokens require careful signing-key rotation, audience, issuer, expiry, and revocation policy.
- Native desktop clients should use an OS-protected credential store if selected. Browser clients should not store long-lived bearer secrets in JavaScript-accessible local storage; use an approved secure session strategy with CSRF and origin protections.
- Define token audience, scopes, expiry, refresh/rotation, revocation, issuance, logout, and incident response before implementation. Never reuse one administrator token across desktop, web, and external applications.
- Keep secrets out of `.env.example`. Environment variables may be used for deployment configuration only after the secret-management policy is decided; they are not automatically a secure vault.
- For remote operation, require encrypted transport and approved identity federation. No credential method makes a public listener safe by itself.

## 4. Authorization and API security

### Authentication versus authorization

- **Authentication:** validate a credential and resolve a principal (human user, local installation, or client application).
- **Authorization:** check operation scope, resource ownership/tenant, consent, policy, and any tool-specific approval on every request.
- Authentication does not imply access to every user's conversations, memories, knowledge collections, models, or tools.
- Client-supplied user IDs, collection IDs, memory IDs, or tool choices are untrusted until resolved and authorized server-side.

### Proposed permission boundaries

Use least-privilege scopes, with resource/tenant checks in addition to the scope:

| Operation | Proposed permission | Additional enforcement |
|---|---|---|
| Generate a chat answer | `chat:generate` | Per-principal quotas, request limits, selected provider policy, and approved context settings. |
| Read/write/delete a conversation | `conversation:read`, `conversation:write`, `conversation:delete` | Same authenticated owner/tenant; ephemeral by default; durable history disabled until approved. |
| Read/search personal memory | `memory:read` | Only the owner's memories; retrieval policy/consent must be explicit and visible. |
| Create/edit personal memory | `memory:write` | Explicit user action and trusted confirmation receipt; model intent alone is insufficient. |
| Delete one/all memories | `memory:delete` | Ownership, explicit confirmation proportional to scope, safe audit outcome; no content in logs. |
| Search knowledge | `knowledge:search:<collection>` | Collection ACL, source policy, bounded excerpts, provenance, and per-result access check. |
| Invoke a tool | `tools:invoke:<tool>` | Allowlist, schema validation, per-tool policy, explicit user request, confirmation for consequential action. |
| Read model metadata | `models:read` | Return truthful provider/capabilities only; no local paths/secrets. |
| Read readiness | `health:read` or local operator access | Minimal sanitized dependency state. Liveness remains minimal. |
| Change configuration/administer | Separate owner/admin scope | Not granted to ordinary chat or third-party clients; no such API is approved. |

### Required controls

- **Conversation ownership:** use unpredictable opaque IDs and bind each resource to the authenticated owner/tenant. Deny cross-owner access without revealing whether another user's resource exists.
- **Memory:** require operation-specific scopes and user confirmation for writes/deletes. The future API's retrieval defaults need an explicit decision; do not assume the CLI's current implicit matching-memory retrieval is equivalent to API consent.
- **Knowledge:** authorize each collection and each retrieved source. Ingestion permissions are separate from search permissions; no ingestion is authorized here.
- **Tools:** model-generated tool requests are untrusted. Intersect requested tools with client scopes and policy, validate again server-side, bound loops/timeouts, and require separate confirmation where appropriate.
- **Validation:** validate JSON encoding, types, nested structures, allowed fields, IDs, pagination, and provider-independent generation parameters. Reject unsupported fields rather than silently ignoring them.
- **Sensitive search input:** place memory, knowledge, and other private search queries in authenticated request bodies (for example, `POST` search operations), not URL query strings that may be retained by browser history, proxies, or access logs.
- **Size limits:** impose body, text, output, collection, and result limits before expensive processing. The numbers must be selected through resource measurement and approval, not invented in this plan.
- **Rate/resource limiting:** apply principal- and route-specific quotas, bounded concurrent inference, queue limits, deadlines, cancellation, and backpressure. Rate limits alone do not control GPU/memory exhaustion.
- **Error handling:** use a stable, sanitized error envelope and documented status codes. Never expose stack traces, raw exception/SQLite messages, local paths, private prompts, credentials, or tool arguments. A provider outage must not produce a success-shaped answer.
- **Audit logging:** record security-relevant metadata such as request ID, principal/client ID, action, resource category, outcome, and timestamp. Do not record full prompts, memory text, credentials, full query contents, or raw tool inputs/results by default. Define audit access and retention before implementation.
- **Secret redaction:** redact authorization headers, API keys, passwords, tokens, credential-like values, and secret-bearing provider errors in logs, traces, API responses, and crash reports. Existing memory credential patterns are not a complete secret detector.
- **Browser protection:** if a web UI is served, define allowed origins, CSRF defense for cookie sessions, content security policy, safe content rendering, and local-network request protections.

## 5. Persistence and data protection

### Existing SQLite usage

SQLite is appropriate for the currently implemented local single-user memory use case. The existing code creates a `memories` table, opens short-lived connections, uses parameterized search operations, and exposes explicit save/list/search/delete/clear operations through `MemoryService`.

It is not a multi-user persistence solution as currently designed: the schema has no owner/tenant identity; the code has no migrations, encryption/key management, backup, export, retention, or recovery service; and no API authorization guards the database. Do not modify the existing database or schema as part of this phase.

### Conversation persistence

**Recommended initial policy (pending approval):** keep API conversations ephemeral in memory with a bounded lifetime and size; do not write transcripts to SQLite or ordinary logs. Process restart may discard active conversations. If durable history is later requested, require a separate user opt-in, per-user ownership, retention/expiry, export, deletion, backup, and access-audit design.

The CLI currently holds a bounded conversation history in process only. Do not silently turn it into persistent history when adding a server.

### Memory consent, retrieval, deletion, and retention

- Keep personal memory separate from transient conversation state and knowledge documents.
- Preserve the current explicit save intent in the CLI. Its existing matching-memory retrieval during ordinary turns is a separate behavior; API retrieval mode and per-user settings must be explicitly decided.
- API write/delete operations require an authenticated principal, operation scope, and user action/confirmation mechanism. A body flag such as `confirmed: true` is not sufficient proof by itself.
- Provide owner-only read/edit/delete/export and an explicit clear-all confirmation if those APIs are implemented.
- Set retention and deletion semantics before persisting sessions or audit details. Deletion policy must say how indexes, caches, backups, and replicas are handled.
- Do not automatically train on conversations, memory, credentials, logs, or personal data.

### Backups, future multi-user storage, migration, and recovery

- **Recommendation (pending approval):** keep the initial local memory store in SQLite without changing its schema; protect the database and backups using an approved OS-level or equivalent encryption/key strategy. Do not upload backups by default.
- Maintain a documented backup schedule/scope, key custody and recovery process, retention, secure deletion, and restore-test procedure before production use.
- If measured concurrency, multi-user isolation, or availability requirements exceed SQLite's suitable scope, evaluate a client/server relational database. Require per-user/tenant ownership in repository operations and test isolation at every read/write path.
- Choose storage only after recording workload, transaction/concurrency needs, offline support, operations, data portability, cost, and security evidence. PostgreSQL or a vector database is not preselected.
- Any future migration requires an explicit scope, verified backup, versioned schema plan, transactional/idempotent migration, integrity checks, rollback/recovery test, export/deletion plan, and user authorization. No migration is run here.

## 6. Network exposure

| Mode | Advantages | Risks and requirements | Recommendation |
|---|---|---|---|
| No API listener / in-process calls | Smallest attack surface; appropriate for current CLI and early shared-service refactoring. | Does not serve separate desktop/web/external processes. | Safest until API security and framework decisions are approved. |
| Loopback-only local API | Enables local desktop/web clients while keeping the listener off LAN interfaces. | Other local processes can connect; a browser can be induced to make local requests; local malware may run as the user; port/origin handling can be abused. Loopback does not authenticate or authorize. | Recommended first network boundary only after authentication, browser protections, and request limits are implemented and tested. |
| LAN access | Supports trusted-network devices. | Network peers, weak Wi-Fi, routing, firewall errors, credential interception, and device identity expand the threat model. Requires TLS, authentication, authorization, revocation, rate limits, monitoring, and explicit firewall/deployment configuration. | Not enabled by default; separate approval and security review. |
| Remote/internet access | Supports external applications and users anywhere. | Highest exposure: credential attacks, abuse, availability, privacy/legal obligations, incident response, TLS/identity operations, tenant isolation, and service maintenance. | Not recommended as an initial deployment. Separate architecture, operational ownership, review, and explicit user approval required. |

Binding to `localhost` or `127.0.0.1` is not authentication: it restricts network interfaces, but does not prove which local process/user made a request, prevent other processes from connecting, or protect against browser-origin/local-network request attacks. A future local API still requires authenticated principals, authorization, origin controls, and safe request handling.

No network service was created, started, or exposed in this phase.

## 7. Decision matrix

All recommendations below are advisory. Each row remains **PENDING USER APPROVAL**; no decision is approved by inclusion in this plan.

| Decision ID | Topic | Available options | Recommended option | Reason | Risks and trade-offs | User approval required | Current status |
|---|---|---|---|---|---|---|---|
| C3C-01 | Backend framework | FastAPI; Flask; Starlette plus selected schema/auth components; Django REST Framework. | Evaluate FastAPI first; select only after compatibility, security, and dependency review. | Good fit for typed Python services, validation, and OpenAPI. | Adds dependencies; async does not make synchronous inference nonblocking; no framework supplies the complete auth policy. | Choose framework and approved dependency/update policy. | PENDING USER APPROVAL |
| C3C-02 | Initial service topology | In-process only; one local API process; multiple web workers; separate inference worker/process. | In-process CLI first; when API is separately approved, begin with a single local service/worker and measure before splitting. | Minimizes attack surface and duplicate model memory. | Single process may limit availability/concurrency; process isolation adds IPC/operations complexity. | Approve initial topology and evidence required to scale. | PENDING USER APPROVAL |
| C3C-03 | Local user identity | No identity; current OS user; local account; per-install identity plus OS user. | Require an authenticated local principal tied to the OS user/installation; do not rely on loopback alone. | Provides attribution and a basis for resource ownership with limited initial scope. | Same-user malware remains a threat; OS integration/provisioning choices vary by platform. | Approve local identity model and supported platforms. | PENDING USER APPROVAL |
| C3C-04 | Local API authentication | No auth; static API key; OS-protected install credential; short-lived scoped bearer token; OS IPC. | No unauthenticated API; if a listener is approved, use scoped, revocable credentials protected by OS/equivalent secret storage. | Reduces exposure from local processes and avoids shared permanent secrets. | Secure provisioning, key storage, rotation, browser handling, and recovery need design. | Select auth mechanism and credential issuance. | PENDING USER APPROVAL |
| C3C-05 | Multi-user identity | Self-managed passwords; OIDC/OAuth identity provider; organization federation; shared API key. | Use established identity federation for future remote/multi-user mode; avoid hand-rolled password security and shared keys. | Delegates mature identity lifecycle and improves user attribution. | Adds provider availability, integration, privacy, and deployment dependency; offline mode may be constrained. | Decide whether multi-user is in scope and select identity approach. | PENDING USER APPROVAL |
| C3C-06 | Session/token lifecycle | Long-lived API key; opaque short-lived revocable token; signed self-contained token; browser session cookie. | Prefer short-lived revocable credentials; browser sessions need secure cookie/CSRF controls; no long-lived browser token in local storage. | Easier revocation and reduced impact of token theft. | Requires secure issuance, rotation, logout/revocation storage, and clock/lifecycle handling. | Approve token/session format, expiry, refresh, revocation, and logout behavior. | PENDING USER APPROVAL |
| C3C-07 | Permission model | Coarse admin/user roles; endpoint scopes; role-based plus resource ACL; unrestricted local trust. | Least-privilege scopes plus per-user/resource ownership and tool-specific permissions. | Supports separated chat, memory, knowledge, model metadata, and tool rights. | More policy code and test surface; role/scope vocabulary must remain consistent across clients. | Approve principals, roles, scopes, resource ownership, and admin boundaries. | PENDING USER APPROVAL |
| C3C-08 | Network exposure | No listener; loopback; LAN; remote/internet. | No listener until implementation is approved; first API deployment should be authenticated loopback only. | Smallest practical surface for local clients; avoids premature remote operations. | Loopback is not authentication; still requires browser-origin and local-process controls. | Explicitly approve any listener and each later exposure expansion. | PENDING USER APPROVAL |
| C3C-09 | Conversation persistence | Ephemeral only; user-opt-in transcript storage; always persist. | Ephemeral by default; no durable transcript in initial API. | Minimizes sensitive data and avoids changing CLI behavior. | Loses history after expiry/restart; later persistence requires UX, retention, export/deletion, and storage design. | Approve persistence, opt-in, retention, and deletion policy. | PENDING USER APPROVAL |
| C3C-10 | Memory write/retrieval consent | Existing CLI semantics; per-turn opt-in; remembered user preference; automatic retrieval; model-triggered writes. | Keep explicit user-approved writes; require scoped user consent for API writes; make API retrieval opt-in/configurable until separately decided. | Distinguishes save consent from the current CLI's automatic matching-memory retrieval. | Extra interaction and preference state; consent receipt workflow needs trusted UI and server validation. | Approve write confirmation, retrieval default, edit/delete, and clear-all flow. | PENDING USER APPROVAL |
| C3C-11 | Initial database | Existing SQLite; separate SQLite databases; server relational database; other store. | Reuse current SQLite for existing single-user memory only; do not expand schema before approval. | Lowest migration risk and consistent with current offline usage. | No tenant isolation/migration service today; SQLite concurrency and backup limits need measurement. | Approve data boundaries and future database evaluation criteria. | PENDING USER APPROVAL |
| C3C-12 | Multi-user persistence | Continue SQLite with enforced ownership; PostgreSQL/other relational store; managed database. | Defer until multi-user demand and workload are established; require explicit tenant isolation and migration plan. | Avoids premature operational complexity while preventing unsafe reuse of current schema. | Delaying may require later migration; selecting a server database adds operations and network dependencies. | Decide whether multi-user is a requirement and approve any migration. | PENDING USER APPROVAL |
| C3C-13 | Retention and backups | No durable content; local encrypted backups; cloud backups; configurable retention. | Ephemeral conversations; local protected backups only if explicitly required; no cloud sync by default. | Minimizes data movement and keeps offline/privacy boundaries clear. | Data loss risk without backups; encryption/key recovery and deletion across backups are nontrivial. | Approve retention, backup scope/location, encryption/key custody, and restore/deletion policy. | PENDING USER APPROVAL |
| C3C-14 | Request limits and concurrency | Fixed universal limits; config limits; measured per-route/principal limits; unbounded requests. | Measured server-configured body/output/queue/rate limits with bounded concurrency; no unbounded mode. | Protects constrained hardware and prevents trivial resource exhaustion. | Limits can reject legitimate workloads; performance/headroom must be measured and published. | Approve thresholds, quotas, timeout, cancellation, and streaming/job behavior. | PENDING USER APPROVAL |
| C3C-15 | Audit and error detail | Verbose request logs; content-free security metadata; no audit; configurable policy. | Minimal metadata-only audit with request IDs and safe categories; redact prompts, memory, credentials, and raw tool data. | Supports incident review without creating a secondary sensitive transcript store. | Less content can complicate debugging; retention/access and user disclosure must be decided. | Approve event fields, access, retention, redaction, and incident process. | PENDING USER APPROVAL |
| C3C-16 | Secret storage/rotation | Environment variables; config file; OS credential store; external secret manager. | OS-protected store for local credentials; managed secret service only for an approved remote deployment. | Reduces accidental disclosure in source, logs, and client files. | Platform support, recovery, rotation, and deployment complexity vary. | Approve storage, key ownership, rotation/revocation, and recovery approach. | PENDING USER APPROVAL |
| C3C-17 | API contract details | Phase 3B proposal unchanged; amend schemas; defer routes; streaming now/later. | Review and freeze a minimal non-streaming v1 only after decisions on ownership, retention, auth, limits, and errors. | Avoids cementing unresolved policy in endpoint behavior. | A synchronous call may need longer client deadlines; future streaming may require compatibility changes. | Approve exact routes, schemas, statuses, idempotency, pagination, and deprecation policy. | PENDING USER APPROVAL |
| C3C-18 | Online egress | Always enabled; per-feature opt-in; disabled/offline-only; policy-controlled allowlist. | Disabled by default; explicit per-feature opt-in and destination policy; offline mode blocks egress. | Search and online TTS transmit data externally; they are not required for local API operation. | Reduced functionality offline; egress monitoring and user disclosure required. | Approve destinations, data sent, consent, and offline enforcement. | PENDING USER APPROVAL |

## 8. Approval gates before implementation

Implementation remains **NOT AUTHORIZED** until all applicable gates below are completed and a separate, explicit implementation scope is approved. A recommendation, blank response, or partial approval does not pass a gate.

### Gate A — Decisions and scope

- [ ] User has reviewed and explicitly resolved each applicable C3C decision ID.
- [ ] The user has approved the first bounded implementation phase, exact files/components, intended clients, and explicit exclusions.
- [ ] FastAPI or another framework and exact dependency review are decided; no inference from this plan counts as selection.
- [ ] Local-only versus LAN/remote deployment is explicitly selected. Any change from loopback requires a new exposure/security approval.
- [ ] The first phase excludes persistence, memory APIs, knowledge ingestion, provider changes, or other unapproved features.

### Gate B — Identity and authorization

- [ ] Principal types and local identity binding are defined.
- [ ] Authentication credential issuance, protected storage, expiry, rotation, revocation, recovery, and logout are documented.
- [ ] A permission matrix maps every route/resource/tool to scopes and ownership checks.
- [ ] Cross-user/cross-client resource isolation and non-enumerating failure behavior are specified and tested.
- [ ] Memory write/delete confirmation is based on a trusted user action, not an AI request or client-supplied boolean.
- [ ] Browser session, origin, CSRF, and local-network request protections are defined if a browser client is in scope.

### Gate C — Privacy and persistence

- [ ] Conversation retention is explicitly ephemeral or has a user-approved retention/consent/deletion design.
- [ ] Memory write and retrieval policies distinguish existing CLI behavior from any new API defaults.
- [ ] User export, deletion, backup scope, key custody, restore, retention expiry, and deletion from derived copies are defined for all persistent data.
- [ ] Memory, conversations, credentials, logs, and personal data are explicitly excluded from automatic training.
- [ ] Any database/schema change has a separate migration plan, verified backup, rollback, and explicit approval.

### Gate D — Security and network

- [ ] Threat model and data-flow diagram cover local processes, browser-origin requests, credential theft, API abuse, prompt injection, tool abuse, resource exhaustion, tenant leakage, and logs/backups.
- [ ] Request/response validation, payload/result limits, timeouts, cancellation, queue and rate policies are decided from evidence.
- [ ] Error mapping and audit fields are reviewed to ensure secrets, prompts, private memory, local paths, and raw tool content are not exposed.
- [ ] Secret storage and dependency supply-chain/update policy are reviewed.
- [ ] Offline mode and online egress destinations/data are specified and testable.
- [ ] If any network exposure beyond loopback is proposed, transport security, identity operations, firewall/deployment, monitoring, abuse response, and incident ownership have separate approval.

### Gate E — Framework, provider, and verification

- [ ] Framework compatibility, dependencies, licenses, security updates, and runtime packaging are verified without weakening the existing environment.
- [ ] Synchronous inference and SQLite behavior have a bounded execution/cancellation strategy; worker count respects measured RAM/VRAM.
- [ ] The API continues to use provider-neutral contracts and does not expose Ollama-specific wire formats.
- [ ] Ollama remains the current development default and operational provider unless a separate native replacement gate is passed.
- [ ] No silent external-AI fallback is permitted in a mode represented as native-only.
- [ ] Test plan covers route/schema contracts, negative authorization, memory ownership/consent, error redaction, rate/size limits, egress, concurrency, and recovery.
- [ ] Any brain quality evaluation reports English, Hindi, Hinglish, and mixed-script results separately with approved thresholds.

Only after all applicable gates are checked and the user explicitly authorizes a named implementation phase may implementation begin. A checked design gate does not authorize tokenizer experiments, dataset acquisition, model training, provider replacement, or public deployment unless the separate authorization explicitly says so.

## Final status

**DECISION PLAN CREATED — RECOMMENDATIONS ARE ADVISORY — ALL C3C DECISIONS REMAIN PENDING USER APPROVAL — NO IMPLEMENTATION AUTHORIZED.**

FastAPI is the leading framework candidate, and authenticated loopback-only operation with ephemeral conversations is the recommended initial direction. These are recommendations only. Identity, credentials, scopes, memory/API consent, persistence, backup, limits, audit retention, framework, and any network exposure remain undecided. Ollama remains the current development provider; external AI services are not approved as permanent answer-generation dependencies.

## Inspection record

The complete Phase 3A architecture plan and Phase 3B requirements/API contract plan were read before drafting. Their distinctions between existing capability, proposed design, pending decisions, and unauthorized work were preserved.

Relevant existing repository facts used from those inspections include the provider-neutral AI interfaces and default Ollama registry, `AIService` and the distinct CLI entry points, SQLite memory schema/service, the allowlisted `ToolRegistry`, environment-backed configuration, and the reviewed provider, memory, tool, CLI, and web-search tests. No additional code, database, test, or configuration file was changed or inspected for this Phase 3C planning task.
