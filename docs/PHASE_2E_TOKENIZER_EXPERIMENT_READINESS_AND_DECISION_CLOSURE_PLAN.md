# Veronica Phase 2E: Tokenizer Experiment Readiness and Decision Closure Plan

## Status and scope

This is a planning-only assessment. It makes no source selection, algorithm
selection, vocabulary-size decision, data approval, or experiment
authorization. No data was accessed or processed. No tokenizer, vocabulary,
model, or integration was created.

English, Hindi (Devanagari), and Hinglish (Roman Hindi) remain equal
priorities. Any future tokenizer must support each with the same evaluation
rigor; a mixed-script group must also be reported separately. Veronica's
eventual language model must generate its own final answers.

## 1. Current baseline and Phase 2A–2D outcomes

### Phase 2A byte tokenizer

`app/tokenizer.py` exposes `encode(text: str) -> list[int]` and
`decode(token_ids: Iterable[int]) -> str`. Encoding returns the unchanged
UTF-8 byte values (IDs 0–255). Decoding validates integer types and range,
then strictly decodes UTF-8. There are no added special IDs, learned merges,
or external tokenizer/model dependencies. The module is not integrated into
the assistant or an AI provider.

The Phase 2A report records 15 focused tests passed (17 subtests passed) and
the full suite at 382 collected, 381 passed, 1 skipped, 0 failed. The skip is
the Windows directory-symlink privilege test. The independent Phase 2A audit
approved the implementation against its byte-level scope. Neither result
demonstrates a learned tokenizer or model.

### Phase 2B synthetic validation

Phase 2B used small deterministic synthetic strings. It confirmed exact
round trips and direct byte mapping for English, Hindi, Hinglish, mixed
text, Unicode, whitespace, punctuation, and long repetitions. Token counts
equaled UTF-8 byte counts. The language-group token/code-point rates reflect
UTF-8 representation length, not compression quality. No real corpus,
vocabulary fitting, or learned-tokenizer comparison occurred.

### Phase 2C design and Phase 2D governance

Phase 2C compared BPE, Unigram, and WordPiece conceptually and identified
unresolved algorithm, size, Unicode, fallback, fairness, and data-policy
choices. It did not select or fit a vocabulary. Phase 2D established
source-specific licensing, consent, privacy, provenance, deduplication,
split, reporting, and approval gates. It does not approve any dataset or
authorize acquisition, fitting, training, or integration.

## 2. Algorithm comparison by language and script

The approaches below have different segmentation and coverage trade-offs.
Their suitability cannot be settled without an approved model/runtime,
licensed and representative data, and the per-language evaluation described
later. No winner is declared.

| Approach | English | Hindi (Devanagari) | Hinglish and code-switching | Mixed-script text |
|---|---|---|---|---|
| **BPE** | Frequent English words and morphemes can merge efficiently; rare names, inflections, and domain terms may split. Frequency-driven merges depend on corpus composition. | Frequent matras, conjuncts, and common words may be merged; low-frequency forms can fragment. Byte-based BPE can retain coverage if all UTF-8 bytes are in the base vocabulary. | English overlap may create reusable units, while transliteration and spelling variants may remain fragmented. Merge counts can favor the most represented spelling. | Can merge recurring cross-script sequences or preserve byte coverage; segmentation around script switches depends on pre-tokenization and learned merge order. |
| **Unigram** | Scored alternative segmentations may provide flexible splits for frequent and rare forms; results depend on candidate inventory and learned probabilities. | Candidate substrings and segmentation scores can represent script-specific forms, but matras, conjuncts, and nukta coverage still depend on the input alphabet and training data. | Multiple candidate segmentations can represent spelling variants differently; frequency imbalance can still under-serve less common variants. Any sampled segmentation must be disabled or seeded for deterministic evaluation. | A scored segmentation can handle candidate paths across switches, but mixed examples need their own reporting and coverage checks. |
| **WordPiece** | Longest-match greedy segmentation with word-boundary/continuation conventions can preserve frequent units; greedy decisions can leave suboptimal remainder splits. | Continuation markers and boundary rules require explicit validation for Devanagari sequences and pre-tokenization; an unseen unit may become unknown without a fallback. | Latin-script overlap with English can help shared forms, but tokenization does not itself identify Roman Hindi meaning. Spelling variation can increase fragmentation or unknowns. | Greedy matching can behave differently at script transitions; mixed spans and punctuation require explicit tests. |

Across all approaches, corpus balance, pre-tokenization, normalization,
vocabulary size, and unknown/fallback policy materially affect results.
Byte-level bases/fallbacks can guarantee UTF-8 coverage but can increase
sequence lengths. Character/subword-only vocabularies need a defined
out-of-vocabulary strategy. Training and inference settings must be recorded
and deterministic for comparison.

## 3. Illustrative vocabulary-size options

These are **planning bands only**, not selections or approvals. The final
choice depends on model dimensions, context budget, training-data quantity
and diversity, language balance, special/fallback token accounting, and
measured evaluation results.

| Illustrative band | Potential benefits | Costs and risks | Data implications |
|---|---|---|---|
| **8k–16k entries** | Lower embedding/output-table capacity cost; more shared subword units and potentially broad reuse. | Higher fertility and longer sequences; rare names, morphology, spellings, and script-specific patterns may fragment. | Requires enough balanced examples to learn useful units, but a smaller inventory can reduce pressure to support many rare entries. Verify all language groups and fallback rates. |
| **16k–32k entries** | Middle trade-off between common-unit coverage and vocabulary parameter cost; candidate band for controlled comparison only. | May still fragment minority forms or reserve capacity for units that provide little benefit. Results remain corpus-dependent. | Needs broader, balanced coverage and careful frequency review; cannot be justified by English volume alone. |
| **32k–64k entries** | More capacity for frequent words, subwords, and script/domain-specific forms; may reduce fertility for well-represented data. | Larger embedding and output projection, memory/checkpoint costs, sparse or unused entries, and potential over-specialization. | Requires materially more diverse and representative data in all three groups to estimate useful entries; a large vocabulary cannot fix missing or unlicensed coverage. |

In an embedding table, parameter storage scales approximately with vocabulary
size times embedding width; an untied output projection can require a
comparable additional matrix. Runtime memory and compute also depend on
precision, batching, architecture, and decoding. Veronica's eventual model
dimensions are not established here, so no memory estimate or size choice is
approved. If a candidate reserves byte fallback IDs, count those within the
total vocabulary budget and state the accounting convention.

Any later sweep should use user-approved candidate points/bands and the same
constraints where technically comparable. It must not choose a size based on
aggregate fertility alone.

## 4. Unicode and normalization policy options

The Phase 2A tokenizer preserves valid input exactly through UTF-8 bytes and
does not normalize. A learned tokenizer may tokenize normalized text, but
normalization changes the input representation and can prevent exact
round-trip to the original unless the original is retained separately.
Choose and test a policy explicitly; never normalize silently.

| Policy option | Potential benefit | Risks and effects to evaluate |
|---|---|---|
| **No normalization / verbatim input** | Preserves exact code-point sequence, spelling, and punctuation; simplest basis for exact reconstruction. | Canonically equivalent strings can produce different IDs; corpus may spend capacity on equivalent forms; Unicode version and malformed-input behavior still need specification. |
| **NFC** | Composes canonically equivalent sequences where Unicode defines a composition; can reduce some representation variation without compatibility folding. | Not every visually similar or decomposed sequence composes. Devanagari nukta forms and combining sequences need explicit examples. Exact original spelling is not recoverable from normalized IDs alone. |
| **NFD** | Represents canonically equivalent text as decomposed sequences, potentially making combining structure explicit. | Can increase code-point counts and fertility; changes raw representation and may interact with grapheme boundaries, matras, conjuncts, and tokenizer pre-segmentation. |
| **NFKC/NFKD** | Can fold compatibility variants and reduce some forms of representational variation. | Compatibility folding can erase distinctions and alter symbols, typography, or user intent. It is not a harmless default; require a concrete use case and collision analysis. |
| **Additional case/transliteration rewriting** | Could consolidate selected variants if explicitly designed. | Lossy and language-policy dependent; can erase Hinglish spelling diversity or conflate English and Roman Hindi. Not implied by Unicode normalization and requires separate approval. |

Evaluate original and candidate-normalized forms side by side for:

- Devanagari matras, virama sequences and conjuncts, nukta-bearing letters,
  canonically equivalent sequences, and combining marks.
- Roman Hindi spellings, repeated letters, optional diacritics, transliteration
  variants, capitalization, and English code-switches.
- Punctuation, whitespace, emoji, symbols, and mixed-script boundaries.
- Exact token/decode round trips, normalization collisions, and changes in
  per-language fertility and unknown/fallback rates.

Retain an approved raw-form reference if normalization is used and policy
permits it. The normalization form, Unicode data version, order of
pre-tokenization, and treatment of malformed input remain pending decisions.

## 5. Unknown-token and fallback options

| Option | Reversibility and robustness | Vocabulary and sequence trade-offs |
|---|---|---|
| **Single unknown token (`UNK`)** | Handles an unseen item operationally but collapses distinct unseen strings to one ID. It is not lossless; exact reconstruction requires preserving the original text out-of-band. | Minimal vocabulary cost and short unknown encoding, but conceals coverage failures and can disproportionately affect rare script forms. Report unknown rate per language. |
| **Byte fallback** | A complete byte fallback can represent any valid UTF-8 input exactly, provided byte boundaries and decoding are defined. Strict UTF-8 decoding should reject malformed byte sequences. | Requires reserving all 256 byte IDs or an equivalent complete mapping; uncommon strings may expand to many IDs. Count fallback IDs in vocabulary budget and report fallback frequency. |
| **Character fallback** | Can cover an approved character inventory and preserve those characters if segmentation is defined. It may not cover new Unicode code points or sequences; an additional fallback is needed for complete coverage. | Smaller than a full byte fallback for limited alphabets, but alphabet/normalization coverage and code-point segmentation need maintenance; unseen characters remain a risk. |
| **Hybrid subword plus fallback** | Uses subwords for common text and a complete fallback for uncommon material; can preserve reversibility if decoder and normalization rules are lossless. | Balances common sequence length and coverage, but increases design complexity and requires accurate per-language subword/fallback reporting. |

No option is selected. Approval must specify fallback coverage, reserved IDs,
whether decoding must reproduce the exact original input, malformed-text
behavior, and how unknown/fallback events are measured.

## 6. Proposed evaluation protocol

After separate data and experiment authorization, create separate results for
English, Hindi (Devanagari), and Hinglish (Roman Hindi), and a distinct
mixed-script report. Apply the same approved checks and acceptance gates to
each language group. Report data quantity and composition alongside results;
do not infer fairness from one aggregate score.

For each candidate algorithm, approved vocabulary size, language group, and
mixed group, report:

- **Fertility:** tokens per whitespace-delimited word, grapheme cluster, and
  Unicode code point; define the Unicode/grapheme version and segmentation
  method.
- **Unknown/fallback rate:** examples and text units using `UNK`, byte, or
  character fallback; report rates and counts by group and script.
- **Round-trip correctness:** exact input/output match under the approved
  normalization policy; separately count expected normalization changes,
  malformed input handling, and decoder failures.
- **Vocabulary utilization:** used/unused entries, frequency distribution,
  token overlap/shared units, script-specific units, rare entries, and
  fallback/reserved-token accounting.
- **Sequence lengths:** median, 95th, and 99th percentile per example, plus
  maximum, with byte/code-point context and a documented sample unit.
- **Unicode edge cases:** matras, conjuncts, nukta forms, combining and
  precomposed forms, Roman Hindi variants, punctuation, whitespace, emoji,
  symbols, and mixed-script transitions.
- **Equal-priority summary:** each language's results, pre-approved gate
  status, and worst-group gaps. Do not conceal a group's result with a
  corpus-weighted mean.

Freeze evaluation code and test splits before fitting. Fit vocabulary only
on the approved training split; validation may be used only for pre-approved
selection. Seal the test split and do not tune against it. No thresholds,
weights, or measured learned-tokenizer results are established in this plan.

## 7. Dataset governance: evidence required before use

Phase 2D governs. No source may be used until its specific approval and
evidence are recorded. Public availability alone does not establish a right
to acquire, train on, transform, or distribute material. Public-source
categories discussed in Phase 2D are possibilities for review, not approved
sources.

For each source/version, require:

1. **Identity and provenance:** owner/publisher, canonical reference, version
   or release date, acquisition method/date, accountable reviewer, and a
   traceable source-level manifest entry.
2. **License and use authorization:** exact terms, version and jurisdiction;
   explicit permission for collection, preprocessing, tokenizer fitting,
   vocabulary/artifact distribution, attribution, and intended downstream
   use; qualified legal review for ambiguity.
3. **Privacy and consent:** data minimization, prohibited fields, screening
   and redaction limits, access controls, retention and deletion, consent
   scope/withdrawal if applicable, and an incident owner.
4. **Exclusion checks:** private conversations, chat history, SQLite memory,
   credentials, logs, secrets, and personal user data remain excluded by
   default. Do not inspect or repurpose them for language balancing.
5. **Language coverage and quality:** separately recorded English, Hindi,
   Hinglish, and mixed-script labels; labeling uncertainty; source/domain
   coverage; quality exclusions; and balance review.
6. **Deduplication and splits:** approved exact/near-duplicate policy,
   cross-script review that does not erase language diversity, grouped
   leakage-resistant train/validation/sealed-test manifests, and reproducible
   assignment rules.
7. **Reproducibility:** transformation history, normalization, filters,
   fingerprints where safe, manifest checksum, dataset snapshot/version,
   experiment config, software versions, seeds, and reviewers.

If rights, consent, provenance, or privacy are ambiguous, quarantine the
candidate and stop. Dataset redistribution permission and tokenizer-artifact
distribution permission are separate questions. Retention and deletion
requirements must account for source text, derived data, manifests, backups,
and any downstream artifacts.

## 8. Experiment prerequisites checklist

All items must be resolved and affirmatively approved before a bounded
tokenizer-only experiment can be authorized:

- [ ] Intended use, scope, exclusions, stop conditions, and artifact
      distribution are defined.
- [ ] Candidate algorithms and permitted tooling are chosen for the
      experiment; no algorithm is chosen by this plan.
- [ ] Vocabulary candidate bands, model/context budget, fallback and
      reserved-ID accounting are approved; no size is chosen by this plan.
- [ ] Unicode normalization, pre-tokenization, special-token, malformed-text,
      and exact-decoding policies are specified.
- [ ] Unknown/fallback behavior and per-language coverage gates are approved.
- [ ] Every proposed source has documented license, attribution, privacy,
      provenance, consent, and intended-use approval.
- [ ] Private conversations, chat history, SQLite memory, credentials, logs,
      and personal user data remain excluded unless a separate explicit
      approval changes a narrowly defined policy.
- [ ] Language/domain pools, balancing basis, label confidence, and equal
      English/Hindi/Hinglish review criteria are approved.
- [ ] Deduplication rules, false-positive review, and leakage-resistant
      train/validation/sealed-test assignments are approved.
- [ ] Evaluation metrics, reporting format, equal acceptance gates, and
      independent reviewers are pre-registered.
- [ ] Provenance manifest, retention/deletion plan, reproducibility record,
      access controls, and stop/escalation path are ready.
- [ ] The user/designated approver gives explicit, recorded authorization
      for the bounded tokenizer-only experiment.
- [ ] Model training, provider changes, live integration, and later phases
      are explicitly outside the authorization.

Any missing, expired, disputed, or ambiguous item blocks execution.

## 9. Decision register

Every item below is **PENDING**. Options and trade-offs are planning inputs,
not recommendations or approved decisions. Evidence listed is required
before closure.

### D-01 — Intended use and supported domains

- **Question:** What tokenizer use, domains, artifact distribution, and
  downstream use are in scope?
- **Options:** Research-only tokenizer artifact; internal use; wider
  distribution; or no experiment.
- **Advantages/disadvantages:** Narrow use limits rights and privacy exposure
  but may not support later deployment. Wider use improves portability but
  requires broader license, privacy, and compatibility evidence.
- **Evidence required:** Written purpose, target users/runtime, distribution
  plan, downstream-use statement, exclusions, and stop conditions.
- **Status:** PENDING.

### D-02 — Algorithm candidates and implementation/tooling

- **Question:** Which of BPE, Unigram, and WordPiece should be compared, and
  which implementation/tooling may be used?
- **Options:** One candidate; a controlled subset; all three; or defer.
- **Advantages/disadvantages:** More candidates provide comparative evidence
  but increase review, compute, implementation, and reproducibility burden.
  Tool choice affects behavior and licensing.
- **Evidence required:** Model compatibility, algorithm configuration,
  implementation license/security review, reproducibility plan, and approval
  for allowed tooling.
- **Status:** PENDING.

### D-03 — Vocabulary-size bands

- **Question:** Which candidate sizes/ranges and reserved-token accounting
  should be tested?
- **Options:** Illustrative 8k–16k, 16k–32k, 32k–64k bands; a smaller or
  larger model-driven range; or defer.
- **Advantages/disadvantages:** Larger sizes may lower fertility but increase
  model memory and require more diverse data; smaller sizes reduce parameter
  costs but may increase sequence lengths and fallback.
- **Evidence required:** Model width, context and memory budgets, training
  data estimates after source approval, and total-ID accounting for fallback
  and control tokens.
- **Status:** PENDING.

### D-04 — Model and runtime constraints

- **Question:** What architecture, embedding width, context size, memory,
  latency, and deployment targets constrain the tokenizer?
- **Options:** Select a target model/runtime first; compare several
  compatible budgets; or postpone tokenizer selection.
- **Advantages/disadvantages:** Early constraints make vocabulary costs
  measurable; premature constraints can limit future architecture choices.
- **Evidence required:** Approved architecture/resource envelope and
  tokenizer/model interface specification.
- **Status:** PENDING.

### D-05 — Unicode normalization

- **Question:** Should text remain verbatim or use NFC, NFD, NFKC/NFKD, or
  another explicitly justified transformation?
- **Options:** No normalization; NFC; NFD; compatibility normalization; or
  a separately approved reversible pipeline.
- **Advantages/disadvantages:** Normalization may reduce representational
  variants but can alter exact text or distinctions; verbatim handling
  preserves forms but may increase vocabulary/fertility for variants.
- **Evidence required:** Collision analysis and round-trip tests for matras,
  conjuncts, nukta, combining/precomposed forms, punctuation, and Roman Hindi
  variants, plus a Unicode version and policy owner.
- **Status:** PENDING.

### D-06 — Pre-tokenization and boundaries

- **Question:** How should words, whitespace, punctuation, scripts, and
  control-token strings be segmented or escaped?
- **Options:** Byte/character stream; whitespace/word splitting; punctuation
  splitting; script-aware boundaries; or a controlled combination.
- **Advantages/disadvantages:** Boundaries can improve common token reuse but
  may prevent useful cross-boundary merges or impair exact reconstruction;
  script-aware rules add complexity and can bias mixed text.
- **Evidence required:** Reversible specification and edge-case evaluation
  across all three language groups and mixed-script spans.
- **Status:** PENDING.

### D-07 — Unknown and fallback policy

- **Question:** Should unseen content use `UNK`, character fallback, byte
  fallback, or a hybrid?
- **Options:** Single unknown ID; approved character inventory; complete
  UTF-8 byte fallback; hybrid; or no experiment until selected.
- **Advantages/disadvantages:** `UNK` is compact but lossy; character
  fallback may miss unseen code points; byte fallback is robust/reversible
  but can lengthen sequences and consumes IDs.
- **Evidence required:** Coverage requirements, malformed-input contract,
  exact-decoding tests, vocabulary budget, and per-language fallback metrics.
- **Status:** PENDING.

### D-08 — Special/control tokens

- **Question:** Are BOS/EOS, padding, unknown, or other control tokens needed?
- **Options:** None for tokenizer-only evaluation; minimal approved set; or
  model-specific set later.
- **Advantages/disadvantages:** Reserved IDs support model interfaces but
  consume vocabulary and introduce collision/escaping risks; no reserved
  tokens simplify the tokenizer but may not fit a future model.
- **Evidence required:** Model interface contract, unique ID inventory,
  escaping/collision tests, and accounting within vocabulary size.
- **Status:** PENDING.

### D-09 — Language/domain balance

- **Question:** What sources, domains, dialects, scripts, and balancing unit
  define equal priority for English, Hindi, and Hinglish?
- **Options:** Balance by examples, characters, bytes, words, or training
  tokens; use multiple stratified views; or defer until sources are approved.
- **Advantages/disadvantages:** Count-based balancing is understandable but
  units differ by script; token-based balance depends on the tokenizer being
  evaluated. Overlap between English and Hinglish can obscure group coverage.
- **Evidence required:** Approved scope, label methodology/confidence,
  per-language coverage inventory, and pre-registered balance criteria.
- **Status:** PENDING.

### D-10 — Source, license, attribution, and permitted use

- **Question:** Which specific source/version and collection method, if any,
  may be used, and for which training/distribution purposes?
- **Options:** Individually reviewed public-domain, open-licensed,
  institutional, research, or other explicitly authorized sources; or no
  source/no experiment.
- **Advantages/disadvantages:** Better provenance can support auditability;
  each source adds rights, attribution, privacy, and compatibility review.
  Public accessibility alone grants no permission.
- **Evidence required:** Source manifest, exact license/version/jurisdiction,
  acquisition authorization, attribution terms, intended-use decision, and
  qualified legal review for ambiguity.
- **Status:** PENDING.

### D-11 — Privacy, consent, retention, and deletion

- **Question:** What privacy standard, consent mechanism, retention period,
  withdrawal process, and deletion verification apply?
- **Options:** Strict exclusion of all user-contributed material; or a
  narrowly scoped consent-based proposal reviewed separately.
- **Advantages/disadvantages:** Strict exclusion lowers privacy risk but
  limits some conversational forms; consent-based use may add data but
  creates substantial notice, withdrawal, retention, and derived-artifact
  obligations.
- **Evidence required:** Privacy review, consent language/process if
  applicable, data minimization plan, access roles, retention/deletion
  schedule, backup handling, and incident owner.
- **Status:** PENDING.

### D-12 — Provenance and manifests

- **Question:** Which manifest fields, fingerprints, access controls, and
  versioning rules are required?
- **Options:** Source-level minimal manifest; item-level manifest; or
  protected tiered records.
- **Advantages/disadvantages:** More detailed records improve traceability but
  can increase privacy/linkability risks and retention burden.
- **Evidence required:** Approved schema, data-minimization review,
  reproducibility needs, checksum/version policy, and access-control review.
- **Status:** PENDING.

### D-13 — Exact/near deduplication

- **Question:** Which representations, methods, thresholds, and human-review
  process identify duplicates without erasing language diversity?
- **Options:** Exact-only; exact plus near-duplicate review; or staged
  language-aware and cross-script checks.
- **Advantages/disadvantages:** Broader deduplication reduces leakage but
  risks collapsing translations, transliterations, quotations, or distinct
  variants; conservative deduplication may leave leakage.
- **Evidence required:** Approved matching policy, false-positive/negative
  review method, per-language removal impact, and duplicate-cluster manifest.
- **Status:** PENDING.

### D-14 — Train/validation/sealed-test design

- **Question:** What split proportions, grouping unit, seed, and test access
  rules prevent leakage?
- **Options:** Source/document/contributor grouping with frozen proportions;
  stratified grouped alternatives; or defer until data inventory is approved.
- **Advantages/disadvantages:** Grouping reduces leakage but may complicate
  balancing and reduce split flexibility; random item splits are simpler but
  can leak near-duplicates.
- **Evidence required:** Approved source inventory, duplicate clusters,
  split manifest/checksum plan, deterministic assignment, and sealed-test
  access control.
- **Status:** PENDING.

### D-15 — Quality gates and fairness metrics

- **Question:** Which language-specific measurements and thresholds decide
  acceptability?
- **Options:** Fertility, fallback/unknown rate, round-trip correctness,
  vocabulary use, sequence percentiles, Unicode coverage, worst-group gap,
  or a pre-approved combination.
- **Advantages/disadvantages:** Multiple metrics reveal trade-offs but make
  decisions more complex; a single aggregate is simple but can hide one
  language's failure.
- **Evidence required:** Metric definitions, Unicode/word segmentation
  version, test protocol, equal per-language acceptance criteria, reviewer
  sign-off, and sealed-test plan.
- **Status:** PENDING.

### D-16 — Reproducibility and tooling

- **Question:** Which software versions, seeds, configurations, tie-breaking,
  environment, and allowed dependencies are required?
- **Options:** Pinned implementation/environment; containerized run later;
  or another approved reproducibility mechanism.
- **Advantages/disadvantages:** Pinning improves repeatability but creates
  maintenance and licensing review; flexible environments are easier to use
  but complicate comparisons.
- **Evidence required:** Tool/license inventory, configuration schema,
  version/seed capture, deterministic-run test plan, and artifact hashes.
- **Status:** PENDING.

### D-17 — Artifact distribution and approval authority

- **Question:** Who approves experiment start, source use, artifact release,
  and final tokenizer selection?
- **Options:** User approval at each gate; designated technical/privacy/legal
  reviewers plus user authorization; or no distribution.
- **Advantages/disadvantages:** Multiple reviewers improve governance but
  add coordination; a single approval path is faster but may miss specialist
  risks.
- **Evidence required:** Named approval roles, recorded decisions, source
  license conditions, release checklist, and withdrawal/escalation process.
- **Status:** PENDING.

### D-18 — Model training and integration boundary

- **Question:** Will any later model training, provider change, or live
  integration be considered, and under what separate authorization?
- **Options:** Keep all outside the tokenizer experiment; propose separate
  future approval; or do not pursue them.
- **Advantages/disadvantages:** Separation protects the bounded experiment
  and current assistant behavior; eventual model integration requires
  additional architecture, safety, and operational review.
- **Evidence required:** Separate project scope and user authorization.
  The eventual Veronica model must generate its own final answers.
- **Status:** PENDING.

## 10. Final readiness verdict

**Planning readiness:** The current byte-tokenizer baseline, Phase 2A–2D
reports, algorithm trade-offs, illustrative vocabulary bands, governance
gates, and unresolved-decision register provide a basis for decisions.

**Experiment readiness:** **Not ready to execute.** All decisions D-01
through D-18 remain PENDING. No specific source, license, data balance,
normalization, fallback policy, algorithm, vocabulary size, evaluation
threshold, tooling, or approval authority has been closed.

**Authorization:** Planning readiness is not permission. A bounded
tokenizer-only experiment requires affirmative closure of applicable
decisions, source-specific evidence, governance review, and explicit recorded
user authorization. No data source is approved by this document.

## Before/after Git status

The starting status was captured before creating this document. No tracked
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
?? tests/test_tokenizer.py
```

No unrelated files were modified.

## Authorization boundary

This plan does not authorize data acquisition, tokenizer fitting, model
training, tokenizer integration, or Phase 2F or any later experiment.
