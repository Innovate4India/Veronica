# Veronica Phase 2G: User Decision Workshop and Approval Record

## 1. Project baseline

### Verified completed work

- **Phase 2A:** `app/tokenizer.py` implements `encode(text)` and
  `decode(token_ids)` as deterministic UTF-8 byte mapping. IDs 0–255 are the
  unchanged byte values; decoding validates IDs and uses strict UTF-8. It
  does not add special tokens, use a learned vocabulary, or integrate with
  an AI provider. The Phase 2A report records 15 focused tests passed (17
  subtests passed) and a full suite of 382 collected, 381 passed, 1 skipped,
  0 failed. The skip is a Windows symlink-privilege limitation.
- **Phase 2A independent audit:** The available audit records an APPROVED
  verdict for the byte-level prototype and its scope. It does not approve a
  learned tokenizer.
- **Phase 2B:** The available validation records synthetic round trips,
  byte mapping, Unicode behavior, and length counts for English, Hindi
  (Devanagari), Hinglish (Roman Hindi), and mixed text. Token count equals
  UTF-8 byte count. These results are not a learned-tokenizer benchmark.
- **Phase 2C:** The available design document compares BPE, Unigram, and
  WordPiece conceptually and leaves algorithm, vocabulary, text policy, and
  data choices unresolved.
- **Phase 2E:** The available readiness plan identifies decisions D-01
  through D-18 and reports experiment readiness as NOT READY.
- **Phase 2F:** The available decision review supplies advisory options and
  recommendations for D-01 through D-18. Recommendations are not approvals.

English, Hindi (Devanagari), and Hinglish (Roman Hindi/code-switching) remain
co-equal priorities. Mixed-script text remains a separate evaluation group.
Veronica's eventual language model must generate its own final answers.

### Phase 2D source filename reconciliation

The existing Phase 2D governance plan is
[`PHASE_2D_DATASET_GOVERNANCE_AND_EXPERIMENT_AUTHORIZATION_PLAN.md`](./PHASE_2D_DATASET_GOVERNANCE_AND_EXPERIMENT_AUTHORIZATION_PLAN.md).
It was confirmed present and read for this workshop. An earlier version of
this document used a filename containing `TOKENIZER`; that path does not
exist. This was a filename mismatch, not an absent Phase 2D document. The
governance plan remains planning-only and does not approve any source,
acquisition, tokenizer experiment, or model work.

### Pending work

No learned tokenizer, corpus, vocabulary, or model exists as a result of
these phases. No tokenizer algorithm, data source, license, normalization
policy, fallback, size, evaluation threshold, dependency, model training, or
integration is approved by this workshop.

## 2. Decision register

D-01 is **APPROVED**; D-02 through D-18 remain **PENDING USER DECISION**.
Phase 2F recommendations below are explicitly advisory. The exact
questions are for the user to answer; no answers have been pre-filled.

### D-01 — Intended use and supported domains

- **Original question:** What tokenizer use, domains, artifact distribution,
  and downstream use are in scope?
- **Status:** APPROVED.
- **Available options:** Research-only artifact; internal use; wider
  distribution; or defer/no experiment.
- **Phase 2F recommendation (advisory):** Defer until model/runtime, user
  needs, and artifact audience are specified.
- **Evidence still required:** Written purpose, domains, target runtime,
  distribution plan, downstream-use statement, exclusions, and stop
  conditions.
- **Dependencies:** D-04, D-09, D-10, D-17, D-18.
- **Exact approval question:** Which intended use, domains, and artifact
  distribution option do you approve, or do you choose to defer?
- **If deferred:** Scope remains undefined; later source, size, and evaluation
  choices cannot be grounded in intended use.
- **Required before bounded tokenizer-only experiment:** Yes.

### D-02 — Algorithm candidates and implementation/tooling

- **Original question:** Which of BPE, Unigram, and WordPiece should be
  compared, and which implementation/tooling may be used?
- **Status:** PENDING USER DECISION.
- **Available options:** One candidate; a controlled subset; all three; or
  defer.
- **Phase 2F recommendation (advisory):** Do not declare a winner. If later
  authorized, compare candidates under a common approved corpus and
  controlled preprocessing.
- **Evidence still required:** Model compatibility, permitted tooling,
  implementation versions/licenses, algorithm configurations, compute
  budget, and reproducibility plan.
- **Dependencies:** D-01, D-04, D-05, D-06, D-07, D-09, D-10, D-16.
- **Exact approval question:** Which candidate algorithm(s) and
  implementation/tooling, if any, do you approve for a future bounded
  comparison?
- **If deferred:** No algorithm comparison or fitting can begin.
- **Required before bounded tokenizer-only experiment:** Yes.

### D-03 — Vocabulary-size bands

- **Original question:** Which candidate sizes/ranges and reserved-token
  accounting should be tested?
- **Status:** PENDING USER DECISION.
- **Available options:** Illustrative 8k–16k, 16k–32k, and 32k–64k bands;
  another model-driven range; or defer.
- **Phase 2F recommendation (advisory):** Defer size selection until model
  dimensions, context/runtime budgets, and approved data estimates exist.
  Phase 2E bands are examples only.
- **Evidence still required:** Embedding width, output-head tying, precision,
  context budget, approved data volume/diversity, and fallback/control-ID
  accounting.
- **Dependencies:** D-04, D-07, D-08, D-09, D-10, D-15.
- **Exact approval question:** Which vocabulary-size range and total-ID
  accounting do you approve for a future comparison, or do you defer?
- **If deferred:** No size sweep can be planned or interpreted against model
  resource limits.
- **Required before bounded tokenizer-only experiment:** Yes.

### D-04 — Model and runtime constraints

- **Original question:** What architecture, embedding width, context size,
  memory, latency, and deployment targets constrain the tokenizer?
- **Status:** PENDING USER DECISION.
- **Available options:** Specify a target model/runtime first; compare
  compatible budgets; or defer tokenizer selection.
- **Phase 2F recommendation (advisory):** Define an approved provisional
  model/runtime envelope before vocabulary-size selection; keep it revisable.
- **Evidence still required:** Approved architecture/resource envelope and
  tokenizer/model interface.
- **Dependencies:** D-01, D-03, D-07, D-08, D-17, D-18.
- **Exact approval question:** Which model/runtime constraints, if any, do
  you approve as provisional design inputs?
- **If deferred:** Memory, context, and deployment feasibility cannot be
  assessed reliably.
- **Required before bounded tokenizer-only experiment:** Yes, at least
  provisional constraints are needed for meaningful size evaluation.

### D-05 — Unicode normalization

- **Original question:** Should text remain verbatim or use NFC, NFD,
  NFKC/NFKD, or another transformation?
- **Status:** PENDING USER DECISION.
- **Available options:** No normalization; NFC; NFD; compatibility
  normalization; or a separately justified reversible pipeline.
- **Phase 2F recommendation (advisory):** Retain Phase 2A verbatim behavior
  as a control; defer a learned-tokenizer policy until collision and
  round-trip evidence exists. Do not normalize silently.
- **Evidence still required:** Unicode version, collision analysis, exact
  reconstruction requirements, and tests for matras, conjuncts, nukta,
  combining forms, punctuation, and Roman Hindi variants.
- **Dependencies:** D-06, D-07, D-09, D-10, D-13, D-15.
- **Exact approval question:** Which normalization policy do you approve for
  a future experiment, or do you defer pending evidence?
- **If deferred:** No data normalization or tokenizer fit can proceed.
- **Required before bounded tokenizer-only experiment:** Yes.

### D-06 — Pre-tokenization and boundaries

- **Original question:** How should words, whitespace, punctuation, scripts,
  and control-token strings be segmented or escaped?
- **Status:** PENDING USER DECISION.
- **Available options:** Byte/character stream; whitespace/word splitting;
  punctuation splitting; script-aware boundaries; or a controlled
  combination.
- **Phase 2F recommendation (advisory):** Defer rules until tokenizer type
  and exact-decoding contract are approved; pre-register reversible
  alternatives for later comparison.
- **Evidence still required:** Reversible specification and edge-case
  evaluation across all target languages, punctuation, whitespace, and
  mixed-script spans.
- **Dependencies:** D-02, D-05, D-07, D-08, D-15.
- **Exact approval question:** Which pre-tokenization and boundary policy do
  you approve, or do you defer pending evaluation?
- **If deferred:** Candidate comparisons lack a fixed, reproducible input
  segmentation policy.
- **Required before bounded tokenizer-only experiment:** Yes.

### D-07 — Unknown and fallback policy

- **Original question:** Should unseen content use `UNK`, character fallback,
  byte fallback, or a hybrid?
- **Status:** PENDING USER DECISION.
- **Available options:** Single unknown ID; approved character inventory;
  complete UTF-8 byte fallback; hybrid; or defer.
- **Phase 2F recommendation (advisory):** Include complete byte fallback as
  a correctness control if model and vocabulary budgets permit, but defer
  the final production policy; do not describe unknown-only handling as
  lossless.
- **Evidence still required:** Exact-decoding contract, malformed-input
  behavior, total ID budget, per-language fallback rates, and
  model-interface support.
- **Dependencies:** D-03, D-05, D-06, D-08, D-15, D-18.
- **Exact approval question:** Which unknown/fallback behavior and
  reversibility guarantee do you approve for a future experiment?
- **If deferred:** Coverage, decoding, and vocabulary-budget requirements
  remain unsettled.
- **Required before bounded tokenizer-only experiment:** Yes.

### D-08 — Special/control tokens

- **Original question:** Are BOS/EOS, padding, unknown, or other control
  tokens needed?
- **Status:** PENDING USER DECISION.
- **Available options:** None for tokenizer-only evaluation; minimal
  approved set; or a later model-specific set.
- **Phase 2F recommendation (advisory):** Add no implicit special IDs to a
  tokenizer-only comparison; defer the final inventory until the model
  interface is defined.
- **Evidence still required:** Model interface contract, ID inventory,
  escaping/collision tests, and vocabulary-budget accounting.
- **Dependencies:** D-03, D-04, D-06, D-07, D-18.
- **Exact approval question:** Do you approve no special IDs for a bounded
  tokenizer-only experiment, a specified minimal set, or deferral?
- **If deferred:** No control IDs may be introduced; model-specific
  compatibility remains open.
- **Required before bounded tokenizer-only experiment:** Yes, explicitly
  resolve whether the experiment includes any reserved IDs.

### D-09 — Language/domain balance

- **Original question:** What sources, domains, dialects, scripts, and
  balancing unit define equal priority?
- **Status:** PENDING USER DECISION.
- **Available options:** Balance by examples, characters, bytes, words, or
  training tokens; use multiple stratified views; or defer.
- **Phase 2F recommendation (advisory):** Maintain separate English, Hindi,
  and Hinglish pools and an additional mixed group, with identical
  evaluation rigor. Defer the training-balance unit until approved source
  coverage is known.
- **Evidence still required:** Supported domains/dialects, label
  methodology/confidence, source inventory, and balancing/acceptance rules.
- **Dependencies:** D-01, D-10, D-11, D-12, D-13, D-15.
- **Exact approval question:** Which language/domain scope and balancing
  basis do you approve while keeping all three languages co-equal?
- **If deferred:** No training-pool proportions or data acquisition scope
  can be set.
- **Required before bounded tokenizer-only experiment:** Yes.

### D-10 — Source, license, attribution, and permitted use

- **Original question:** Which source/version and collection method, if any,
  may be used, and for which purposes?
- **Status:** PENDING USER DECISION.
- **Available options:** Individually reviewed public-domain,
  open-licensed, institutional, research, or other explicitly authorized
  sources; or no source/no experiment.
- **Phase 2F recommendation (advisory):** Approve no source by category.
  Require per-source, version-specific legal review before access; defer
  source selection until purpose and artifact distribution are defined.
- **Evidence still required:** Canonical source/version, exact
  license/jurisdiction, approved acquisition method, attribution, permitted
  uses, and source-specific legal/privacy review. This plan approves no
  source; those approvals remain pending.
- **Dependencies:** D-01, D-09, D-11, D-12, D-13, D-14, D-17.
- **Exact approval question:** Do you approve any specific source and
  version for stated tokenizer use after its terms are reviewed, or do you
  approve no source at this time?
- **If deferred:** No source may be accessed or used; a tokenizer experiment
  involving real data cannot proceed.
- **Required before bounded tokenizer-only experiment:** Yes for any
  source-based experiment; a synthetic-only scope would need its own explicit
  definition and authorization.

### D-11 — Privacy, consent, retention, and deletion

- **Original question:** What privacy standard, consent mechanism, retention
  period, withdrawal process, and deletion verification apply?
- **Status:** PENDING USER DECISION.
- **Available options:** Exclude user-contributed material; or consider only
  a narrowly scoped consent-based proposal after separate review.
- **Phase 2F recommendation (advisory):** Keep private conversations, chat
  history, SQLite memory, logs, credentials, secrets, and personal user data
  excluded by default. Do not consider exceptions without explicit consent
  and privacy/legal review.
- **Evidence still required:** Privacy authority, screening/minimization
  policy, consent/withdrawal process if applicable, access roles, retention,
  deletion/backup verification, and incident owner. Source-specific privacy
  evidence and approvals remain pending.
- **Dependencies:** D-01, D-09, D-10, D-12, D-14, D-17.
- **Exact approval question:** Do you approve strict exclusion of all
  user-contributed material as the default, and what privacy/retention
  controls must apply to any separately approved source?
- **If deferred:** No personal or user-contributed material may be used;
  source privacy review remains incomplete.
- **Required before bounded tokenizer-only experiment:** Yes for any
  real-source experiment.

### D-12 — Provenance and manifests

- **Original question:** Which manifest fields, fingerprints, access
  controls, and versioning rules are required?
- **Status:** PENDING USER DECISION.
- **Available options:** Minimal source-level manifest; item-level
  manifest; or protected tiered records.
- **Phase 2F recommendation (advisory):** Use a versioned,
  privacy-reviewed manifest containing source/version, license decision,
  attribution, language/script labels, transformations, split, approval,
  retention, and artifact references; avoid unnecessary raw text and review
  fingerprints for linkability.
- **Evidence still required:** Approved schema, minimization review,
  fingerprint/checksum approach, access controls, retention, and versioning
  policy. These source-specific controls and approvals remain pending.
- **Dependencies:** D-09, D-10, D-11, D-13, D-14, D-16.
- **Exact approval question:** Which provenance-manifest level and
  privacy/access controls do you approve?
- **If deferred:** Reproducible, auditable source use is blocked.
- **Required before bounded tokenizer-only experiment:** Yes for
  source-based work.

### D-13 — Exact/near deduplication

- **Original question:** Which representations, methods, thresholds, and
  review process identify duplicates without erasing diversity?
- **Status:** PENDING USER DECISION.
- **Available options:** Exact-only; exact plus reviewed near-duplicates;
  or staged language-aware and cross-script checks.
- **Phase 2F recommendation (advisory):** If later authorized, begin with
  documented exact matching, then review near-duplicate candidates and
  report removals by language. Set no threshold without representative
  approved examples and false-positive review.
- **Evidence still required:** Matching representation/normalization,
  thresholds, review protocol, false-positive/negative analysis, and
  duplicate-cluster manifest.
- **Dependencies:** D-05, D-09, D-10, D-12, D-14, D-15.
- **Exact approval question:** Which staged deduplication policy, matching
  scope, and human-review requirement do you approve?
- **If deferred:** No data deduplication or split-leakage claim can be made.
- **Required before bounded tokenizer-only experiment:** Yes when source
  material is used.

### D-14 — Train/validation/sealed-test design

- **Original question:** What proportions, grouping unit, seed, and test
  access rules prevent leakage?
- **Status:** PENDING USER DECISION.
- **Available options:** Group by source/document/contributor and duplicate
  cluster; stratified grouped alternatives; or defer proportions until an
  approved inventory exists.
- **Phase 2F recommendation (advisory):** Group related sources and
  duplicate clusters; fit vocabulary only on train; use validation only
  under a pre-registered protocol; seal test. Defer proportions and seed
  until the inventory is approved.
- **Evidence still required:** Approved inventory, duplicate clusters,
  grouping rules, proportions, deterministic assignment, split
  manifest/checksum, and test access controls.
- **Dependencies:** D-09, D-10, D-11, D-12, D-13, D-15.
- **Exact approval question:** Which grouping rule, split proportions,
  assignment method, and sealed-test controls do you approve?
- **If deferred:** No corpus-based fitting or evaluation can be considered
  leakage-resistant.
- **Required before bounded tokenizer-only experiment:** Yes for
  source-based work.

### D-15 — Quality gates and fairness metrics

- **Original question:** Which language-specific measurements and thresholds
  decide acceptability?
- **Status:** PENDING USER DECISION.
- **Available options:** Fertility, fallback/unknown rate, round-trip
  correctness, vocabulary use, sequence percentiles, Unicode coverage,
  worst-group gap, or a pre-approved combination.
- **Phase 2F recommendation (advisory):** Report each language separately
  and mixed text separately, with worst-group gaps. Set no numeric threshold
  until use, data, and model limits are approved.
- **Evidence still required:** Metric definitions, segmentation/Unicode
  version, test data, use-case limits, per-language gates, and reviewer
  approval.
- **Dependencies:** D-05, D-07, D-09, D-10, D-13, D-14, D-16.
- **Exact approval question:** Which metrics and equal per-language
  acceptance thresholds do you approve, or do you defer setting thresholds?
- **If deferred:** Results may be reported descriptively but cannot establish
  an approved pass/fail decision.
- **Required before bounded tokenizer-only experiment:** Yes for a
  comparative experiment; numeric thresholds may be explicitly deferred
  only if the experiment is authorized as descriptive and non-selecting.

### D-16 — Reproducibility and tooling

- **Original question:** Which software versions, seeds, configurations,
  tie-breaking, environment, and dependencies are required?
- **Status:** PENDING USER DECISION.
- **Available options:** Pinned implementation/environment; another
  reproducible mechanism; or defer tooling choice.
- **Phase 2F recommendation (advisory):** Require recorded versions,
  configs, seeds, tie-breaking, preprocessing, manifests, and artifact
  hashes before an experiment; defer actual tools and dependencies until
  approval.
- **Evidence still required:** Allowed-tool policy, license/security review,
  config schema, environment definition, deterministic-run plan, and
  artifact-record format.
- **Dependencies:** D-02, D-05, D-06, D-12, D-14, D-15.
- **Exact approval question:** Which reproducibility standard and tool
  approval process do you approve for a later experiment?
- **If deferred:** Results cannot be claimed reproducible or compared
  reliably across candidates.
- **Required before bounded tokenizer-only experiment:** Yes.

### D-17 — Artifact distribution and approval authority

- **Original question:** Who approves experiment start, source use, artifact
  release, and final tokenizer selection?
- **Status:** PENDING USER DECISION.
- **Available options:** User approval at each gate; designated
  technical/privacy/legal reviewers plus user authorization; or no
  distribution.
- **Phase 2F recommendation (advisory):** Require recorded user authorization
  plus documented technical, privacy, and licensing review before the
  experiment or release. Prior phase reports are not authorization.
- **Evidence still required:** Named approval roles, sequence, evidence
  retention, escalation path, and artifact release/withdrawal checklist.
- **Dependencies:** D-01, D-10, D-11, D-12, D-15, D-16, D-18.
- **Exact approval question:** Who must review and approve the bounded
  experiment and any artifact release, and do you approve that gate?
- **If deferred:** No experiment start or artifact release is authorized.
- **Required before bounded tokenizer-only experiment:** Yes.

### D-18 — Model training and integration boundary

- **Original question:** Will later model training, provider change, or live
  integration be considered, and under what separate authorization?
- **Status:** PENDING USER DECISION.
- **Available options:** Keep these outside the tokenizer experiment;
  propose separate future approval; or do not pursue them.
- **Phase 2F recommendation (advisory):** Keep model training, provider
  changes, inference behavior, and live integration outside the bounded
  tokenizer experiment. Require separate approval for future scope.
- **Evidence still required:** Separate project scope, model architecture,
  safety/operational review, and recorded user authorization for any later
  work.
- **Dependencies:** D-01, D-04, D-07, D-08, D-17, and separate model approval.
- **Exact approval question:** Do you confirm that model training, provider
  changes, inference changes, and live integration are excluded from this
  tokenizer decision workshop and require separate authorization?
- **If deferred:** Those activities remain excluded; no later integration
  may be inferred from this workshop.
- **Required before bounded tokenizer-only experiment:** The future model
  decision is not required; explicit acknowledgement of the current
  tokenizer-only boundary is required.

## 3. Decision groups and dependencies

These groups organize discussion; they do not imply approval. Resolve
upstream decisions before dependent choices where noted.

| Group | Decisions | Dependency order |
|---|---|---|
| Purpose and runtime | D-01, D-04 | Define purpose/domains, then establish provisional model/runtime constraints before size or interface choices. |
| Data rights and privacy | D-10, D-11, D-12 | Establish source-specific rights and privacy before access; record approved sources and restrictions in the manifest. The existing Phase 2D plan has been reviewed; source-specific approvals remain pending. |
| Language coverage | D-09 | Requires purpose, approved source inventory, privacy constraints, and language labeling; then set a balancing basis without collapsing Hinglish into English. |
| Text representation | D-05, D-06, D-07, D-08 | Resolve normalization before segmentation/deduplication; define segmentation before fallback and reserved-token behavior; check model constraints before final ID inventory. |
| Data integrity and evaluation | D-13, D-14, D-15 | Source and transformation policies precede deduplication; duplicate groups precede split assignment; frozen splits and metric definitions precede evaluation. |
| Algorithm and reproducibility | D-02, D-03, D-16 | Model/data/text/fallback constraints inform candidate algorithms and vocabulary bands; pin implementation/configuration before a run. |
| Authorization and boundaries | D-17, D-18 | User authorization follows all applicable evidence/reviews; model training, provider/inference changes, and integration remain outside the experiment. |

## 4. Approval record

D-01 approval is recorded below. D-02 through D-18 have no recorded
approvals. Copy or complete each record only after the user supplies a
decision. A recommendation above must not be copied into the choice field as
if approved.

### D-01 record

- User choice: Controlled learned-tokenizer comparison.
- User's reasoning: NOT PROVIDED.
- Conditions or limitations: Keep the existing deterministic UTF-8 byte
  tokenizer as the baseline; compare BPE, Unigram, and WordPiece; treat
  English, Hindi, and Hinglish as co-equal priorities; evaluate mixed-script
  text separately. This approval does not authorize dataset acquisition,
  tokenizer fitting or experiments, model training, or provider/inference
  integration.
- Evidence reviewed: Existing Phase 2A–2F reports and plans, as referenced
  in this workshop document.
- Approval date: 2026-11-24.
- Status: APPROVED.

### D-02 record

- User choice: NOT RECORDED.
- User's reasoning: NOT RECORDED.
- Conditions or limitations: NOT RECORDED.
- Evidence reviewed: NOT RECORDED.
- Approval date: NOT RECORDED.
- Status: PENDING USER DECISION.

### D-03 record

- User choice: NOT RECORDED.
- User's reasoning: NOT RECORDED.
- Conditions or limitations: NOT RECORDED.
- Evidence reviewed: NOT RECORDED.
- Approval date: NOT RECORDED.
- Status: PENDING USER DECISION.

### D-04 record

- User choice: NOT RECORDED.
- User's reasoning: NOT RECORDED.
- Conditions or limitations: NOT RECORDED.
- Evidence reviewed: NOT RECORDED.
- Approval date: NOT RECORDED.
- Status: PENDING USER DECISION.

### D-05 record

- User choice: NOT RECORDED.
- User's reasoning: NOT RECORDED.
- Conditions or limitations: NOT RECORDED.
- Evidence reviewed: NOT RECORDED.
- Approval date: NOT RECORDED.
- Status: PENDING USER DECISION.

### D-06 record

- User choice: NOT RECORDED.
- User's reasoning: NOT RECORDED.
- Conditions or limitations: NOT RECORDED.
- Evidence reviewed: NOT RECORDED.
- Approval date: NOT RECORDED.
- Status: PENDING USER DECISION.

### D-07 record

- User choice: NOT RECORDED.
- User's reasoning: NOT RECORDED.
- Conditions or limitations: NOT RECORDED.
- Evidence reviewed: NOT RECORDED.
- Approval date: NOT RECORDED.
- Status: PENDING USER DECISION.

### D-08 record

- User choice: NOT RECORDED.
- User's reasoning: NOT RECORDED.
- Conditions or limitations: NOT RECORDED.
- Evidence reviewed: NOT RECORDED.
- Approval date: NOT RECORDED.
- Status: PENDING USER DECISION.

### D-09 record

- User choice: NOT RECORDED.
- User's reasoning: NOT RECORDED.
- Conditions or limitations: NOT RECORDED.
- Evidence reviewed: NOT RECORDED.
- Approval date: NOT RECORDED.
- Status: PENDING USER DECISION.

### D-10 record

- User choice: NOT RECORDED.
- User's reasoning: NOT RECORDED.
- Conditions or limitations: NOT RECORDED.
- Evidence reviewed: NOT RECORDED.
- Approval date: NOT RECORDED.
- Status: PENDING USER DECISION.

### D-11 record

- User choice: NOT RECORDED.
- User's reasoning: NOT RECORDED.
- Conditions or limitations: NOT RECORDED.
- Evidence reviewed: NOT RECORDED.
- Approval date: NOT RECORDED.
- Status: PENDING USER DECISION.

### D-12 record

- User choice: NOT RECORDED.
- User's reasoning: NOT RECORDED.
- Conditions or limitations: NOT RECORDED.
- Evidence reviewed: NOT RECORDED.
- Approval date: NOT RECORDED.
- Status: PENDING USER DECISION.

### D-13 record

- User choice: NOT RECORDED.
- User's reasoning: NOT RECORDED.
- Conditions or limitations: NOT RECORDED.
- Evidence reviewed: NOT RECORDED.
- Approval date: NOT RECORDED.
- Status: PENDING USER DECISION.

### D-14 record

- User choice: NOT RECORDED.
- User's reasoning: NOT RECORDED.
- Conditions or limitations: NOT RECORDED.
- Evidence reviewed: NOT RECORDED.
- Approval date: NOT RECORDED.
- Status: PENDING USER DECISION.

### D-15 record

- User choice: NOT RECORDED.
- User's reasoning: NOT RECORDED.
- Conditions or limitations: NOT RECORDED.
- Evidence reviewed: NOT RECORDED.
- Approval date: NOT RECORDED.
- Status: PENDING USER DECISION.

### D-16 record

- User choice: NOT RECORDED.
- User's reasoning: NOT RECORDED.
- Conditions or limitations: NOT RECORDED.
- Evidence reviewed: NOT RECORDED.
- Approval date: NOT RECORDED.
- Status: PENDING USER DECISION.

### D-17 record

- User choice: NOT RECORDED.
- User's reasoning: NOT RECORDED.
- Conditions or limitations: NOT RECORDED.
- Evidence reviewed: NOT RECORDED.
- Approval date: NOT RECORDED.
- Status: PENDING USER DECISION.

### D-18 record

- User choice: NOT RECORDED.
- User's reasoning: NOT RECORDED.
- Conditions or limitations: NOT RECORDED.
- Evidence reviewed: NOT RECORDED.
- Approval date: NOT RECORDED.
- Status: PENDING USER DECISION.

## 5. Experiment authorization gate

Every applicable item must be complete, supported by evidence, and explicitly
approved. A blank or incomplete item means **NOT AUTHORIZED**.

- [ ] D-01 through D-18 have been reviewed; all applicable decisions are
      resolved and recorded without treating advisory recommendations as
      approval.
- [ ] Each source/version and acquisition method has source-specific license,
      attribution, permitted-use, privacy, and consent review.
- [ ] Data scope, exclusions, language labels, provenance manifest, retention,
      and deletion controls are approved.
- [ ] English, Hindi, and Hinglish have equal evaluation priority and
      separate reports; mixed-script text has its own report.
- [ ] Exact/near deduplication, leakage-resistant train/validation/sealed-test
      splits, and data-quality procedures are approved.
- [ ] Normalization, pre-tokenization, unknown/fallback, reserved-token, and
      exact-decoding policies are specified.
- [ ] The evaluation plan, per-language metrics, thresholds or descriptive
      limits, and independent reviewers are approved.
- [ ] Candidate algorithm, vocabulary-size range, implementation/tooling,
      reproducibility settings, and compute/resource limits are approved.
- [ ] Technical feasibility and constraints are reviewed against the
      intended model/runtime.
- [ ] The existing Phase 2D governance plan has been reviewed, and all
      applicable source-specific approvals are documented.
- [ ] A separate, explicit user authorization to begin the bounded
      tokenizer-only experiment is recorded, including scope and stop
      conditions.
- [ ] Model training, provider changes, inference changes, and live
      integration are excluded from this authorization.

**Gate result: NOT AUTHORIZED.** No item is checked and no separate user
authorization to begin an experiment has been recorded.

## 6. Explicit exclusions and co-equal priorities

Model training, provider changes, inference changes, and live integration are
outside this workshop and require separate future authorization. The current
byte tokenizer remains unchanged. Veronica's eventual language model must
generate its own final answers. English, Hindi (Devanagari), and Hinglish
(Roman Hindi/code-switching) remain co-equal priorities; mixed-script text
remains a separate evaluation group. No data may be used to fill a language
gap without source approval and privacy review.

## 7. Final verdict

**PLANNING WORKSHOP UPDATED — D-01 APPROVED — D-02 THROUGH D-18 PENDING — EXPERIMENT NOT AUTHORIZED.**

The Phase 2D filename mismatch is corrected above; the existing governance
plan was read. D-01 is recorded as approved; D-02 through D-18 remain blank
and pending.

## Before/after Git status

**Previously recorded before status (retrospective)**

```text
## main...origin/main
?? app/tokenizer.py
?? docs/PHASE_2A_INDEPENDENT_CODE_AUDIT.md
?? docs/PHASE_2A_NATIVE_TOKENIZER_IMPLEMENTATION_REPORT.md
?? docs/PHASE_2B_TOKENIZER_TESTING_AND_MULTILINGUAL_VALIDATION.md
?? docs/PHASE_2C_LEARNED_TOKENIZER_DESIGN_AND_VOCABULARY_PLAN.md
?? docs/PHASE_2D_DATASET_GOVERNANCE_AND_EXPERIMENT_AUTHORIZATION_PLAN.md
?? docs/PHASE_2E_TOKENIZER_EXPERIMENT_READINESS_AND_DECISION_CLOSURE_PLAN.md
?? docs/PHASE_2F_TOKENIZER_DECISION_REVIEW_AND_RECOMMENDATION_MATRIX.md
?? tests/test_tokenizer.py
```

The first before-status transcription omitted the pre-existing Phase 2D
file and was not a complete baseline. The list above is corrected
retrospectively; it is not a contemporaneously captured status snapshot.

**After**

```text
## main...origin/main
?? app/tokenizer.py
?? docs/PHASE_2A_INDEPENDENT_CODE_AUDIT.md
?? docs/PHASE_2A_NATIVE_TOKENIZER_IMPLEMENTATION_REPORT.md
?? docs/PHASE_2B_TOKENIZER_TESTING_AND_MULTILINGUAL_VALIDATION.md
?? docs/PHASE_2C_LEARNED_TOKENIZER_DESIGN_AND_VOCABULARY_PLAN.md
?? docs/PHASE_2D_DATASET_GOVERNANCE_AND_EXPERIMENT_AUTHORIZATION_PLAN.md
?? docs/PHASE_2E_TOKENIZER_EXPERIMENT_READINESS_AND_DECISION_CLOSURE_PLAN.md
?? docs/PHASE_2F_TOKENIZER_DECISION_REVIEW_AND_RECOMMENDATION_MATRIX.md
?? docs/PHASE_2G_USER_DECISION_WORKSHOP_AND_APPROVAL_RECORD.md
?? tests/test_tokenizer.py
```

Only the requested Phase 2G document was added; the pre-existing
status-visible files remain unchanged.

## Authorization boundary

This workshop records no user decisions and authorizes no data acquisition,
tokenizer fitting, model training, or integration.
