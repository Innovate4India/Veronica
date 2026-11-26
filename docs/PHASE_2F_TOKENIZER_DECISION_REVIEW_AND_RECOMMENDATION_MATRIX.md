# Veronica Phase 2F: Tokenizer Decision Review and Recommendation Matrix

## Status and scope

This is a planning-only review of the 18 pending decisions in Phase 2E. Each
recommendation is advice for user review, not an approved decision. No data
was accessed or processed, and no tokenizer, vocabulary, model, or
integration was created.

English, Hindi (Devanagari), and Hinglish (Roman Hindi) remain co-equal
priorities. Mixed-script text is a separate evaluation group. Veronica's
eventual language model must generate its own final answers.

## 1. Current project baseline

### Phase 2A

`app/tokenizer.py` exposes `encode(text: str) -> list[int]` and
`decode(token_ids: Iterable[int]) -> str`. It maps each UTF-8 byte unchanged
to an integer from 0 through 255. Decoding validates integer type and range,
then strictly decodes UTF-8. It adds no special IDs, vocabulary, or learned
merges and imports no external tokenizer or model. It is not integrated into
the assistant or a provider.

The Phase 2A report records 15 focused tests passed (17 subtests passed) and
382 full-suite tests collected, 381 passed, 1 skipped, 0 failed. The skip is
the Windows directory-symlink privilege test. The independent audit approved
the implementation for its byte-level scope; it did not approve a learned
tokenizer.

### Phase 2B

Phase 2B evaluated deterministic synthetic strings. It recorded exact
round-trips and direct byte mapping for English, Hindi, Hinglish, mixed
text, Unicode, whitespace, punctuation, and long repetitions. Token counts
equaled UTF-8 byte counts. Those results are a byte-count baseline, not a
learned-tokenizer compression benchmark and not corpus evidence.

### Phase 2C–2E

Phase 2C compared BPE, Unigram, and WordPiece conceptually and left
algorithm, vocabulary size, normalization, fallback, and evaluation choices
unselected. Phase 2D established source-specific licensing, consent,
privacy, provenance, deduplication, split, and approval requirements without
approving data. Phase 2E recorded decisions D-01–D-18 as pending and judged
the project not ready to execute. None of these documents authorizes data
acquisition, fitting, training, or integration.

The current tokenizer limitations remain: byte-level sequences may be long;
there is no learned subword vocabulary, language model, inference, or
provider integration; and synthetic tests cannot establish real-world
coverage or fairness.

## 2. Decision-by-decision review

All status labels below mean **PENDING USER APPROVAL**. A recommendation,
where provided, is not approval.

### D-01 — Intended use and supported domains

- **Original question:** What tokenizer use, domains, artifact distribution,
  and downstream use are in scope?
- **Options:** Research-only artifact; internal use; wider distribution; or
  defer/no experiment.
- **Trade-offs:** Narrow use limits rights, privacy, and compatibility burden
  but may not support future deployment. Wider distribution improves
  portability but increases licensing, attribution, privacy, and support
  obligations.
- **Recommendation:** Defer the scope decision until the intended model,
  runtime, user needs, and artifact audience are specified. Do not select
  downstream use by implication.
- **Why alternatives are less suitable:** Choosing a broad release target
  before license and model constraints are known creates avoidable
  commitments; choosing research-only may constrain later uses without
  evidence.
- **Evidence still missing:** Written purpose, domains, target runtime,
  artifact distribution plan, downstream-use statement, exclusions, and
  stop conditions.
- **Dependencies:** D-04, D-09, D-10, D-17, D-18.
- **Language implications:** English needs approved domain coverage; Hindi
  needs Devanagari domains in scope; Hinglish needs an explicit Roman Hindi
  and code-switching scope; mixed text needs a separately declared use case.
- **Status:** PENDING USER APPROVAL.

### D-02 — Algorithm candidates and implementation/tooling

- **Original question:** Which of BPE, Unigram, and WordPiece should be
  compared, and which implementation/tooling may be used?
- **Options:** One candidate, a controlled subset, all three, or defer.
- **Trade-offs:** More candidates provide comparisons but increase compute,
  implementation, license/security review, and reproducibility burden.
  Implementations can differ in normalization and pre-tokenization, so
  algorithm labels alone do not guarantee a fair comparison.
- **Recommendation:** Defer a winner. If an experiment is later approved,
  compare candidates only under a common approved corpus and controlled
  preprocessing; do not assume all three are necessary before model and
  tooling constraints are known.
- **Why alternatives are less suitable:** Picking BPE, Unigram, or WordPiece
  now has no measured learned-tokenizer evidence. Running all three without
  a defined model or data scope may add cost without resolving the important
  fairness questions.
- **Evidence still missing:** Model compatibility, permitted tooling,
  implementation versions/licenses, algorithm configurations, compute
  budget, and reproducibility plan.
- **Dependencies:** D-01, D-04, D-05, D-06, D-07, D-09, D-10, D-16.
- **Language implications:** English merges may reflect frequency; Hindi
  requires matra, conjunct, and nukta coverage; Hinglish requires spelling
  and transliteration analysis; mixed text requires testing switch boundaries
  for every candidate.
- **Status:** PENDING USER APPROVAL.

### D-03 — Vocabulary-size bands

- **Original question:** Which candidate sizes/ranges and reserved-token
  accounting should be tested?
- **Options:** Phase 2E's illustrative 8k–16k, 16k–32k, and 32k–64k bands;
  another model-driven range; or defer.
- **Trade-offs:** Larger vocabularies can reduce fertility for well-supported
  forms but increase embedding/output parameters, memory, and sparse entries.
  Smaller vocabularies reduce parameter costs but may increase sequence
  lengths and fallback.
- **Recommendation:** Defer any size selection until model dimensions,
  context/runtime budgets, and approved data estimates exist. Treat the
  Phase 2E bands as examples only.
- **Why alternatives are less suitable:** Selecting a band from general
  convention or synthetic byte tests would not establish fit for Veronica's
  model or balanced language data.
- **Evidence still missing:** Embedding width, output-head tying, precision,
  context budget, approved training-data volume/diversity, and accounting for
  fallback and control IDs.
- **Dependencies:** D-04, D-07, D-08, D-09, D-10, D-15.
- **Language implications:** English capacity depends on its approved
  domains; Hindi byte length and script coverage may affect fertility;
  Hinglish spelling variants may use capacity differently; mixed examples
  must not be hidden by an aggregate size result.
- **Status:** PENDING USER APPROVAL.

### D-04 — Model and runtime constraints

- **Original question:** What architecture, embedding width, context size,
  memory, latency, and deployment targets constrain the tokenizer?
- **Options:** Specify a target model/runtime first; compare compatible
  budgets; or defer tokenizer selection.
- **Trade-offs:** Defining constraints first makes vocabulary costs concrete
  but may prematurely narrow architecture options. Delaying constraints
  preserves flexibility but prevents meaningful parameter and context
  estimates.
- **Recommendation:** Before size selection, define at least an approved
  provisional model/runtime envelope. Keep it explicitly revisable.
- **Why alternatives are less suitable:** A vocabulary-size choice without
  embedding/context constraints cannot be evaluated for memory or sequence
  cost.
- **Evidence still missing:** Approved architecture/resource envelope and
  tokenizer/model interface.
- **Dependencies:** D-01, D-03, D-07, D-08, D-17, D-18.
- **Language implications:** English sequence costs need measurement; Hindi
  byte expansion can use context faster; Hinglish needs spelling/code-switch
  context measurements; mixed text needs script-transition and context tests.
- **Status:** PENDING USER APPROVAL.

### D-05 — Unicode normalization

- **Original question:** Should text remain verbatim or use NFC, NFD,
  NFKC/NFKD, or another transformation?
- **Options:** No normalization; NFC; NFD; compatibility normalization; or a
  separately justified reversible pipeline.
- **Trade-offs:** Normalization can consolidate some equivalent forms, but
  changes input and may prevent exact reconstruction without preserving the
  original. Compatibility normalization can erase distinctions. Verbatim
  text preserves forms but may create separate vocabulary demand.
- **Recommendation:** Use the Phase 2A verbatim behavior as a control and
  defer any learned-tokenizer normalization choice until side-by-side
  collision and round-trip evidence exists. No silent normalization.
- **Why alternatives are less suitable:** Selecting NFC/NFD or NFKC/NFKD
  without script-specific collision evidence can change user text; assuming
  visual equivalence is insufficient.
- **Evidence still missing:** Unicode version, normalization collision
  inventory, exact reconstruction requirements, matra/conjunct/nukta and
  combining-form results, and policy owner.
- **Dependencies:** D-06, D-07, D-09, D-10, D-13, D-15.
- **Language implications:** English needs canonical-variant checks; Hindi
  needs matra, conjunct, nukta, and combining tests; Hinglish must not have
  spelling/transliteration rewritten; mixed text needs consistent behavior
  at script boundaries.
- **Status:** PENDING USER APPROVAL.

### D-06 — Pre-tokenization and boundaries

- **Original question:** How should words, whitespace, punctuation, scripts,
  and control-token strings be segmented or escaped?
- **Options:** Byte/character stream; whitespace/word splitting; punctuation
  splitting; script-aware boundaries; or a controlled combination.
- **Trade-offs:** Boundaries can encourage reusable units but may prevent
  useful merges or complicate exact reconstruction. Script-aware rules can
  help analysis but add complexity and risk language-specific bias.
- **Recommendation:** Defer boundary rules until the target tokenizer and
  exact-decoding contract are approved; pre-register reversible alternatives
  for any later comparison.
- **Why alternatives are less suitable:** Choosing conventional English
  word splitting may mishandle Devanagari sequences and code-switching;
  script-specific rules without evidence can create unequal behavior.
- **Evidence still missing:** Reversible specification and edge-case
  measurements across spaces, punctuation, scripts, and mixed spans.
- **Dependencies:** D-02, D-05, D-07, D-08, D-15.
- **Language implications:** English word/punctuation splits affect merges;
  Hindi boundaries must respect orthographic sequences; Hinglish Latin text
  must not be presumed English; mixed spans need explicit switch-boundary
  tests.
- **Status:** PENDING USER APPROVAL.

### D-07 — Unknown and fallback policy

- **Original question:** Should unseen content use `UNK`, character fallback,
  byte fallback, or a hybrid?
- **Options:** Single unknown ID; approved character inventory; complete
  UTF-8 byte fallback; hybrid; or defer.
- **Trade-offs:** `UNK` is compact but lossy. Character fallback can be
  efficient for a bounded inventory but may miss unseen code points. Byte
  fallback provides coverage for valid UTF-8 with potentially longer
  sequences and reserved-ID cost.
- **Recommendation:** Include complete byte fallback as a correctness
  comparison/control if later model and vocabulary budgets permit, but defer
  the final production policy. Do not present an unknown-only path as
  lossless.
- **Why alternatives are less suitable:** `UNK` alone loses distinctions;
  character-only fallback cannot guarantee all Unicode input; choosing a
  hybrid now lacks coverage and cost measurements.
- **Evidence still missing:** Exact-decoding contract, malformed-input
  behavior, total ID budget, fallback rates by language, and model-interface
  support.
- **Dependencies:** D-03, D-05, D-06, D-08, D-15, D-18.
- **Language implications:** English needs rare-name/symbol checks; Hindi
  needs unseen Devanagari coverage; Hinglish needs uncommon spelling
  coverage; mixed text needs fallback across all scripts without loss.
- **Status:** PENDING USER APPROVAL.

### D-08 — Special/control tokens

- **Original question:** Are BOS/EOS, padding, unknown, or other control
  tokens needed?
- **Options:** None for tokenizer-only evaluation; minimal approved set; or a
  later model-specific set.
- **Trade-offs:** Reserved IDs support model interfaces but consume capacity
  and require collision/escaping rules. No special IDs simplify the
  tokenizer but may not satisfy a future model interface.
- **Recommendation:** Add no implicit special IDs to a tokenizer-only
  comparison; defer the final inventory until the model interface is defined.
- **Why alternatives are less suitable:** Inventing tokens before the model
  needs them adds undocumented mappings; declaring none permanently is
  premature without a model interface.
- **Evidence still missing:** Model interface contract, ID inventory,
  escaping/collision tests, and vocabulary-budget accounting.
- **Dependencies:** D-03, D-04, D-06, D-07, D-18.
- **Language implications:** English literal token-like strings need tests;
  Hindi content must not collide with controls; Hinglish may resemble Roman
  control spellings; mixed spans need cross-boundary collision checks.
- **Status:** PENDING USER APPROVAL.

### D-09 — Language/domain balance

- **Original question:** What sources, domains, dialects, scripts, and
  balancing unit define equal priority?
- **Options:** Balance by examples, characters, bytes, words, or training
  tokens; use multiple stratified views; or defer.
- **Trade-offs:** Example counts ignore length; byte/code-point counts differ
  by script; word counts depend on segmentation; token counts depend on the
  tokenizer being evaluated. Hinglish overlap with English complicates
  attribution.
- **Recommendation:** Require three separate language pools and an
  additional mixed group, with identical evaluation rigor and per-language
  reporting. Defer the training-balance unit until approved source coverage
  is known.
- **Why alternatives are less suitable:** One pooled corpus or one aggregate
  score can conceal under-coverage; equal raw counts alone do not guarantee
  representative content.
- **Evidence still missing:** Supported domains/dialects, language labeling
  method/confidence, source inventory, and balancing/acceptance rules.
- **Dependencies:** D-01, D-10, D-11, D-12, D-13, D-15.
- **Language implications:** English, Hindi, and Hinglish each need separate
  source and quality counts; Hinglish must not be absorbed into English;
  mixed text remains its own group and is not arbitrarily reassigned.
- **Status:** PENDING USER APPROVAL.

### D-10 — Source, license, attribution, and permitted use

- **Original question:** Which source/version and collection method, if any,
  may be used, and for which purposes?
- **Options:** Individually reviewed public-domain, open-licensed,
  institutional, research, or other explicitly authorized sources; or no
  source/no experiment.
- **Trade-offs:** Strong provenance can improve auditability, but every source
  adds license, attribution, privacy, and downstream-use review. Public
  availability is not permission.
- **Recommendation:** Approve no source by category. Require per-source,
  version-specific legal review before access; defer source selection until
  purpose and artifact distribution are defined.
- **Why alternatives are less suitable:** A blanket approval of “public” or
  “open” data ignores differing rights, collection terms, consent, and
  tokenizer-artifact distribution.
- **Evidence still missing:** Canonical source/version, exact terms and
  jurisdiction, approved acquisition method, attribution obligations,
  permitted uses, privacy review, and legal sign-off.
- **Dependencies:** D-01, D-09, D-11, D-12, D-13, D-14, D-17.
- **Language implications:** English permissions and domains need separate
  review; Hindi must have actual approved Devanagari coverage; Hinglish needs
  rights/provenance for Roman Hindi; mixed items need source and language
  labels retained.
- **Status:** PENDING USER APPROVAL.

### D-11 — Privacy, consent, retention, and deletion

- **Original question:** What privacy standard, consent mechanism, retention
  period, withdrawal process, and deletion verification apply?
- **Options:** Exclude user-contributed material; or consider only a narrowly
  scoped consent-based proposal after separate review.
- **Trade-offs:** Strict exclusion lowers privacy risk but limits some
  conversational styles. Consent-based use has substantial notice,
  withdrawal, retention, deletion, and derived-artifact burdens.
- **Recommendation:** Maintain strict default exclusion of private
  conversations, chat history, SQLite memory, logs, credentials, secrets,
  and personal user data. Do not consider exceptions without explicit
  informed consent and privacy/legal approval.
- **Why alternatives are less suitable:** Language gaps do not justify
  repurposing private data; publication or participation is not equivalent
  to training consent.
- **Evidence still missing:** Privacy authority, screening/minimization
  policy, consent/withdrawal process if applicable, access roles, retention
  schedule, deletion/backup verification, and incident owner.
- **Dependencies:** D-01, D-09, D-10, D-12, D-14, D-17.
- **Language implications:** Apply the same exclusions to English, Hindi,
  and Hinglish; conversational Roman Hindi is not consent; mixed-script data
  receives the same privacy controls.
- **Status:** PENDING USER APPROVAL.

### D-12 — Provenance and manifests

- **Original question:** Which manifest fields, fingerprints, access
  controls, and versioning rules are required?
- **Options:** Minimal source-level manifest; item-level manifest; or
  protected tiered records.
- **Trade-offs:** Detailed records improve traceability but can increase
  privacy/linkability and retention risk. Minimal records reduce exposure
  but may weaken reproducibility.
- **Recommendation:** Use a versioned, privacy-reviewed manifest with
  source/version, license decision, attribution, language/script label,
  transformations, split, approval, retention, and artifact references.
  Store no unnecessary raw text; review fingerprints for linkability.
- **Why alternatives are less suitable:** Unversioned or undocumented data
  cannot support audit or reproducibility; retaining raw text in manifests
  expands exposure.
- **Evidence still missing:** Approved schema, minimization review,
  fingerprint/checksum approach, access controls, retention, and versioning
  policy.
- **Dependencies:** D-09, D-10, D-11, D-13, D-14, D-16.
- **Language implications:** Preserve English labels, Devanagari script
  metadata, distinct Hinglish labels, and mixed/uncertain labels without
  conflating groups.
- **Status:** PENDING USER APPROVAL.

### D-13 — Exact/near deduplication

- **Original question:** Which representations, methods, thresholds, and
  review process identify duplicates without erasing diversity?
- **Options:** Exact-only; exact plus reviewed near-duplicates; or staged
  language-aware and cross-script checks.
- **Trade-offs:** Broader matching reduces leakage but can collapse
  translations, transliterations, quotations, or distinct variants.
  Conservative matching preserves diversity but may leave duplicates.
- **Recommendation:** If later authorized, begin with documented exact
  matching, then add near-duplicate candidates with human review and report
  removal impact by group. Do not set thresholds until representative,
  approved examples and false-positive review exist.
- **Why alternatives are less suitable:** Aggressive automatic cross-script
  deduplication can erase Hinglish or Hindi examples; exact-only may not
  prevent leakage.
- **Evidence still missing:** Matching representation/normalization,
  thresholds, review protocol, false-positive/negative analysis, and
  duplicate-cluster manifest.
- **Dependencies:** D-05, D-09, D-10, D-12, D-14, D-15.
- **Language implications:** Preserve meaningful repeated English text;
  review Devanagari normalization matches; do not collapse Hinglish into
  English; keep mixed translations/code-switch examples separately
  attributable.
- **Status:** PENDING USER APPROVAL.

### D-14 — Train/validation/sealed-test design

- **Original question:** What proportions, grouping unit, seed, and test
  access rules prevent leakage?
- **Options:** Group by source/document/contributor and duplicate cluster;
  stratified grouped alternatives; or defer proportions until data inventory
  is approved.
- **Trade-offs:** Grouping reduces leakage but can complicate balance and
  reduce split flexibility. Random item-level splitting is simpler but risks
  near-duplicate leakage.
- **Recommendation:** Group related sources, documents, contributors, and
  duplicate clusters within one split; fit vocabulary only on train, use
  validation only under a pre-registered protocol, and seal test. Defer
  proportions and seed until the approved inventory is known.
- **Why alternatives are less suitable:** Random sentence splits can leak
  copied text; selecting proportions without source counts is arbitrary.
- **Evidence still missing:** Approved inventory, duplicate clusters,
  grouping rules, proportions, deterministic assignment, manifest/checksum,
  and test access controls.
- **Dependencies:** D-09, D-10, D-11, D-12, D-13, D-15.
- **Language implications:** Stratify/report English independently; retain
  Devanagari test coverage; keep Hinglish distinct; group mixed documents
  and their translations/transliterations to avoid leakage.
- **Status:** PENDING USER APPROVAL.

### D-15 — Quality gates and fairness metrics

- **Original question:** Which language-specific measurements and thresholds
  decide acceptability?
- **Options:** Fertility, fallback/unknown rate, round-trip correctness,
  vocabulary use, sequence percentiles, Unicode coverage, worst-group gap,
  or a pre-approved combination.
- **Trade-offs:** Multiple measures expose trade-offs but complicate
  selection. One aggregate is simpler but may hide weak language coverage.
  Thresholds without an approved use case can be arbitrary.
- **Recommendation:** Report all three languages separately and mixed text
  separately; show each result and worst-group gaps. Set no numeric threshold
  until use, data, and model limits are approved.
- **Why alternatives are less suitable:** Phase 2B byte ratios are not
  learned-tokenizer quality evidence; an aggregate score can obscure
  Devanagari or Hinglish regressions.
- **Evidence still missing:** Metric definitions, grapheme/word segmentation
  version, test data, use-case limits, per-language gates, and reviewer
  approval.
- **Dependencies:** D-05, D-07, D-09, D-10, D-13, D-14, D-16.
- **Language implications:** English needs independent fertility/coverage;
  Hindi needs grapheme/code-point/byte interpretation; Hinglish needs
  separate Roman Hindi metrics; mixed text remains a fourth report group.
- **Status:** PENDING USER APPROVAL.

### D-16 — Reproducibility and tooling

- **Original question:** Which software versions, seeds, configurations,
  tie-breaking, environment, and dependencies are required?
- **Options:** Pinned environment; another reproducible mechanism; or defer
  tooling choice.
- **Trade-offs:** Pinning improves repeatability but creates maintenance and
  license/security review. Flexible environments are convenient but make
  comparisons harder to reproduce.
- **Recommendation:** Require recorded implementation/version, configs,
  seeds, tie-breaking, preprocessing, manifests, and artifact hashes before
  an experiment; defer actual tools and dependencies until approval.
- **Why alternatives are less suitable:** Unrecorded versions/settings make
  segmentation comparisons unauditable; choosing packages now is premature.
- **Evidence still missing:** Allowed-tool policy, license/security review,
  config schema, environment definition, deterministic-run plan, and
  artifact-record format.
- **Dependencies:** D-02, D-05, D-06, D-12, D-14, D-15.
- **Language implications:** Use identical reproducibility controls for
  English and Hindi; preserve Hinglish spelling labels; make mixed-script
  segmentation and normalization reproducible.
- **Status:** PENDING USER APPROVAL.

### D-17 — Artifact distribution and approval authority

- **Original question:** Who approves experiment start, source use, artifact
  release, and final tokenizer selection?
- **Options:** User approval at each gate; designated technical/privacy/legal
  reviewers plus user authorization; or no distribution.
- **Trade-offs:** Multiple reviewers improve governance but add coordination.
  A single approval path is faster but may miss specialist concerns.
- **Recommendation:** Require recorded user authorization plus documented
  technical, privacy, and licensing review before the bounded experiment or
  any release. Do not assume a prior phase report is authorization.
- **Why alternatives are less suitable:** Technical approval alone cannot
  settle rights or privacy; informal approval is difficult to audit.
- **Evidence still missing:** Named roles, approval sequence, evidence
  retention, escalation path, and artifact release/withdrawal checklist.
- **Dependencies:** D-01, D-10, D-11, D-12, D-15, D-16, D-18.
- **Language implications:** Reviewers must see English, Hindi, and Hinglish
  results separately; mixed-script outcomes require explicit review rather
  than being subsumed into another group.
- **Status:** PENDING USER APPROVAL.

### D-18 — Model training and integration boundary

- **Original question:** Will later model training, provider change, or live
  integration be considered, and under what separate authorization?
- **Options:** Keep all outside the tokenizer experiment; propose a separate
  future approval; or do not pursue them.
- **Trade-offs:** Separation protects the bounded evaluation and current
  assistant behavior. Integration requires architecture, safety, operational,
  and provider-boundary review.
- **Recommendation:** Keep model training, provider changes, inference
  behavior, and live integration expressly outside any tokenizer-only
  experiment. Require separate user approval for each later scope. Veronica's
  eventual language model must generate its own final answers.
- **Why alternatives are less suitable:** Combining tokenizer fitting with
  model training or provider replacement prevents a bounded experiment and
  exceeds current evidence and authorization.
- **Evidence still missing:** Any future model project scope, architecture,
  safety and operational review, and separate recorded user authorization.
- **Dependencies:** D-01, D-04, D-07, D-08, D-17, and separate model approval.
- **Language implications:** Any later generation evaluation must separately
  assess English, Hindi, and Hinglish, with mixed-script cases reported
  separately; tokenizer approval alone establishes none of these capabilities.
- **Status:** PENDING USER APPROVAL.

## 3. Multilingual fairness

English, Hindi (Devanagari), and Hinglish (Roman Hindi/code-switching) are
co-equal. For every applicable decision, the matrix above identifies
language-specific consequences. Fairness does not mean equal vocabulary
quotas or identical token counts; it means equivalent review rigor, explicit
coverage criteria, and transparent per-language outcomes.

Mixed-script text must be evaluated as its own group. Do not use a
corpus-weighted or language-aggregated metric to hide a weak result for any
one group. Report individual groups, mixed text, and worst-group outcomes
side by side.

## 4. Cross-decision dependency analysis

These are sequencing dependencies, not approvals:

- **Purpose and model constraints first:** D-01 informs D-04, D-10, D-15,
  D-17, and D-18. D-04 constrains D-03, D-07, and D-08.
- **Data governance before data-dependent choices:** D-10 and D-11 precede
  any access. D-12 records approved sources and transformations. D-09
  requires the approved source inventory and language labels.
- **Text policy before deduplication and metrics:** D-05 and D-06 affect
  D-07, D-13, and D-15. Unicode normalization and token boundaries must be
  specified before interpreting matching or fertility.
- **Splits before evaluation:** D-13 informs D-14; D-14 and D-15 define
  leakage-resistant evaluation. Vocabulary must not be fitted on held-out
  test data.
- **Algorithm and fallback before size accounting:** D-02 and D-07 inform
  D-03; D-08 adds reserved-ID accounting. D-16 records the implementation
  and configuration only after those choices are approved.
- **Evidence before authorization:** D-17 gathers technical, privacy, and
  legal sign-offs across the other applicable decisions. D-18 keeps model
  training and integration separate.

Do not resolve this graph by choosing an algorithm, vocabulary size, or
dataset first. A reasonable order is purpose/runtime requirements, source
and privacy gate, language/data scope, Unicode and fallback policy,
deduplication and splits, candidate comparison and size sweep, pre-registered
evaluation, then explicit authorization. Each gate can return a decision to
pending if evidence is inadequate.

## 5. Recommended decision sequence and approval roles

Recommendations are conditional and do not close any status.

1. **User decision — scope:** Resolve D-01 and provisional model/runtime
   constraints in D-04. Record intended use, exclusions, deployment
   boundaries, and stop conditions.
2. **Governance/legal gate — sources:** Resolve D-10 and D-11 per source.
   Require exact license/use rights, attribution, privacy, consent, retention,
   deletion, and source provenance. No source is eligible before sign-off.
3. **User and technical decision — language coverage:** Resolve D-09 and
   language-labeling policy. Keep English, Hindi, and Hinglish distinct;
   include mixed text separately.
4. **Technical decision — representation:** Resolve D-05 through D-08:
   normalization, pre-tokenization, unknown/fallback, and special tokens.
   Preserve reversibility requirements and test across scripts.
5. **Data/governance decision — integrity:** Resolve D-12 through D-14:
   manifest, privacy-aware exact/near deduplication, grouped splits, and a
   sealed test set.
6. **Technical/user decision — experiment design:** Resolve D-02, D-03,
   D-15, and D-16 based on actual model/resource constraints and approved
   data. Pre-register equal language metrics and acceptance criteria.
7. **Approval gate — bounded experiment:** Resolve D-17 and record explicit
   user authorization, with technical, legal, and privacy reviews attached.
   State tokenizer-only limits and stop conditions.
8. **Separate future gate:** Keep D-18 open for model training, provider
   changes, inference behavior, and integration; none is part of this
   authorization.

**Technical recommendations:** retain the byte tokenizer as an unchanged
control, compare per-language behavior, test exact reconstruction and Unicode
edges, and avoid aggregating away weak groups.

**Governance requirements:** exclude private/user data by default; require
source-specific rights and privacy evidence; preserve provenance; deduplicate
with review; keep test data sealed.

**User decisions:** purpose, intended domains, balancing unit, thresholds,
candidate algorithms/sizes, normalization/fallback policy, and any source
scope.

**Legal or specialist review:** source licenses/attribution, privacy/consent,
retention/deletion, data protection, tooling licenses, and artifact
distribution rights.

## 6. Explicit non-decisions

The following remain unapproved:

- Any dataset, public-source category as an actual source, source license,
  attribution decision, or permitted downstream use.
- Data acquisition, access, collection, scraping, inspection, or processing.
- A tokenizer algorithm or implementation/tooling.
- A vocabulary size, training corpus, merge list, learned vocabulary, or
  checkpoint.
- Unicode normalization, pre-tokenization, word/script boundaries, or
  special-token inventory.
- Unknown-token, character-fallback, byte-fallback, or hybrid strategy.
- Language/domain sampling weights, vocabulary quotas, or dataset split
  proportions.
- Numeric evaluation thresholds, model/resource budgets, or acceptance gates.
- Dependencies or package installation.
- Model training, provider configuration, inference behavior, or live
  integration.

Recommendations above do not turn any item into an approved decision.

## 7. Final verdict

**Experiment readiness: NOT READY. Authorization: NOT AUTHORIZED.**
Decisions D-01 through D-18 remain pending user approval; source-specific
evidence, legal/privacy review, and a recorded bounded-experiment
authorization are outstanding. Planning review is not permission to execute.
No experiment or Phase 2G work has started.

## Before/after Git status

The starting status was captured before creating this document; no tracked
modifications were present.

**Before**

```text
## main...origin/main
?? app/tokenizer.py
?? docs/PHASE_2A_INDEPENDENT_CODE_AUDIT.md
?? docs/PHASE_2A_NATIVE_TOKENIZER_IMPLEMENTATION_REPORT.md
?? docs/PHASE_2B_TOKENIZER_TESTING_AND_MULTILINGUAL_VALIDATION.md
?? docs/PHASE_2C_LEARNED_TOKENIZER_DESIGN_AND_VOCABULARY_PLAN.md
?? docs/PHASE_2D_DATASET_GOVERNANCE_AND_EXPERIMENT_AUTHORIZATION_PLAN.md
?? docs/PHASE_2E_TOKENIZER_EXPERIMENT_READINESS_AND_DECISION_CLOSURE_PLAN.md
?? tests/test_tokenizer.py
```

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
?? tests/test_tokenizer.py
```

Only the requested Phase 2F planning document was added. No unrelated files
were modified. No data was accessed, no experiment was performed, and no
commit or push was made.

## Authorization boundary

This matrix is advisory. **It does not authorize an experiment, data
acquisition, tokenizer fitting, model training, or integration.** All
applicable decisions and the bounded experiment require separate explicit
user approval.
