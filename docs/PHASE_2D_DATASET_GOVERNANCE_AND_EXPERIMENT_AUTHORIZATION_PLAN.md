# Veronica Phase 2D: Dataset Governance and Tokenizer Experiment Authorization Plan

## Status and scope

This document defines proposed governance controls and approval gates only.
It does not approve any data source, dataset, license, acquisition, processing,
tokenizer experiment, or model work. No data was acquired, inspected, or
processed while preparing this plan.

The existing Phase 2A tokenizer remains an independent deterministic UTF-8
byte baseline. Phase 2B evaluated only small synthetic strings. Neither
provides a training corpus or authorizes vocabulary fitting. English,
Hindi (Devanagari), and Hinglish (Roman Hindi) must remain equal priorities
in any future data design and evaluation.

Private conversations, assistant history, SQLite memory, logs, credentials,
and personal user data are excluded from tokenizer training and evaluation
by default. This plan does not change providers or authorize language-model
training. Veronica's eventual language model must generate its own final
answers.

## Governance principles

1. **Permission before access:** public availability is not proof of
   permission to collect, transform, train on, or redistribute material.
2. **Purpose limitation:** approve each source for stated tokenizer training,
   evaluation, artifact distribution, and any downstream use separately.
3. **Equal language priority:** maintain separately identifiable English,
   Devanagari Hindi, and Roman Hindi/Hinglish data and reports, plus a mixed
   language category. Do not let source volume alone set priority.
4. **Data minimization:** collect only approved material needed for the
   approved objective; exclude private or personal material by default.
5. **Traceability and reproducibility:** preserve a reviewable source
   manifest and transformation history without unnecessarily retaining raw
   text or personal data.
6. **Separation of approvals:** source approval, data acquisition, tokenizer
   fitting, tokenizer selection/distribution, model training, and system
   integration are distinct gates.
7. **No silent transformation:** document Unicode normalization, language
   labeling, filtering, and deduplication policies before applying them.

## Public-source categories to evaluate, not approve

The categories below are examples for later review only. No individual
resource is recommended, selected, accessed, or approved here.

| Category | Possible advantages | Required review and common risks |
|---|---|---|
| Government or public-institution publications | May have clear publication records, dates, and stable attribution. | Terms vary by jurisdiction and publisher; documents may contain personal data, third-party material, restrictive notices, or changing reuse conditions. Confirm the exact license and intended use. |
| Public-domain works and digitized books | Rights status may be established for some editions and jurisdictions. | A text's underlying work and its edition, annotations, scans, or transcription may have different rights. Verify provenance, jurisdiction, edition, and source-specific terms. |
| Open-licensed reference or educational text | May include explicit reuse terms and useful subject breadth. | Attribution, share-alike, noncommercial, no-derivatives, database, and contributor terms may affect transformation, tokenizer artifacts, or downstream use. Review the exact version and intended distribution. |
| Research or benchmark corpora with published documentation | May provide collection methods, language labels, and established splits. | Dataset access terms may restrict training or redistribution; consent, personal data, annotation rights, and split leakage need independent review. Public research use does not imply commercial or unrestricted permission. |
| Publicly posted news, blogs, forums, or general web pages | Could cover contemporary styles and varied topics. | Public accessibility is not a license. Copyright, site terms, privacy, personal data, robots/access restrictions, provenance, duplicates, and collection-method authorization require review. No scraping is authorized by this plan. |
| Publicly released transcripts or captions | May include conversational or spoken-language forms and code-switching. | Transcript rights, speaker consent, identifiable information, third-party content, platform terms, and transcription provenance may be unclear. Do not assume public posting grants training consent. |

For every future candidate source, approval must be based on the specific
source, version, license, jurisdiction, collection method, data fields,
transformation, and planned tokenizer/model use—not merely its category or
public visibility.

## Source approval and licensing criteria

Before any acquisition, a source-specific review should record and approve:

- The source owner/publisher, canonical location, version or release date,
  acquisition method, and accountable reviewer.
- The exact license or terms, applicable jurisdiction, required notices and
  attribution, restrictions on training, transformation, redistribution,
  commercial use, and derivative artifacts.
- Whether the terms cover text extraction and preprocessing, tokenizer
  fitting, distribution of vocabulary files or merges, and the intended
  downstream model. Resolve ambiguity with qualified legal review; do not
  infer permission from searchability, accessibility, or an “open” label.
- Whether third-party content, embedded quotations, annotations, or
  contributor agreements impose additional conditions.
- Whether the approved collection method is permitted and proportionate.
  Do not bypass access controls or use a collection method that has not been
  approved.
- How attribution, notices, license records, and any share-alike or
  redistribution obligations will be maintained with derived artifacts.
- What happens if a license changes, a source is withdrawn, or rights cannot
  be verified: quarantine the source, stop its use, and assess affected
  splits and artifacts.

Approval must state permitted and prohibited uses explicitly. Dataset
redistribution permission and tokenizer-artifact distribution permission
must not be treated as interchangeable.

## Privacy, consent, retention, and deletion

### Exclusions and minimization

- Exclude private conversations, chat history, SQLite memory, assistant
  session records, credentials, secrets, and personal user data by default.
- Do not inspect or repurpose user conversations to fill a language gap.
  Any proposed user-contributed material requires a separate explicit,
  informed, revocable consent process and privacy approval before collection.
- Identify and minimize personal or sensitive information in any separately
  approved source. Define screening, redaction, access controls, and
  limitations; do not claim automated screening is perfect.
- Treat names, contact details, account identifiers, health/financial
  information, sensitive attributes, and information about minors as
  requiring heightened review and exclusion unless a documented lawful
  basis and explicit approval permit a narrowly defined use.

### Consent and individual rights

For any consent-based source, document who consented, the purpose and scope,
what artifacts may be produced, the retention period, withdrawal mechanism,
and how withdrawal affects raw data, splits, vocabulary artifacts, and
downstream models. Consent for publication or research participation must
not be assumed to include tokenizer or model training.

### Retention and deletion

Before collection, set minimum necessary retention periods for raw material,
derived text, manifests, and review records. Define access limits, secure
storage, deletion verification, backup expiration, and a response owner.
Document whether a vocabulary can be retrained without a source and how a
source removal request will be handled. If deletion from a derived artifact
cannot be guaranteed, that limitation must be disclosed and resolved before
the source is approved.

## Provenance manifest and reproducibility

Maintain a versioned manifest with one record per source item or defensible
source unit. Proposed fields include:

- Stable internal item ID; source owner and canonical reference; version or
  release date; acquisition date and approved method.
- License/terms identifier and version, jurisdiction, permission decision,
  attribution text or notice reference, reviewer, approval date, and allowed
  uses.
- Language and script labels (English, Devanagari Hindi, Roman Hindi/Hinglish,
  mixed, or unknown), labeling method/confidence, domain, and any safe
  non-identifying quality metadata.
- Consent or privacy approval reference where applicable, retention
  deadline, access class, exclusion flags, and deletion/withdrawal state.
- Transformation pipeline/version, normalization policy, filtering and
  deduplication decisions, duplicate-cluster reference, split assignment,
  and reproducible content fingerprint where appropriate.
- Dataset release ID, manifest checksum, reviewer sign-off, and links to
  experiment configuration and resulting artifact IDs.

Do not put raw personal data, secrets, or unnecessary text into the manifest.
A content hash or source identifier can itself be sensitive or linkable;
approve its format and access controls. Keep the approved source inventory
and data snapshot immutable for each experiment. Record code/tool versions,
configuration, random seeds, tie-breaking rules, and environment without
installing or running anything as part of this planning phase.

## Deduplication without erasing language diversity

Future deduplication should occur only after a source is approved and only
under a documented policy:

1. Preserve the source-level record and derive a reversible or auditable
   duplicate decision; do not silently discard source provenance.
2. Detect exact duplicates first, using a documented representation and
   approved normalization. Retain the original form or a protected reference
   sufficient for audit, subject to privacy and retention rules.
3. Review near-duplicate clusters using a documented threshold and sample
   review. Near-duplicate algorithms can confuse shared short phrases,
   quotations, templates, transliterations, and related but distinct
   Devanagari/Hinglish text.
4. Compare within each language/script and across scripts where justified.
   Record cross-script matches separately; do not collapse Roman Hindi into
   English or remove a language's only examples merely because a translation
   or transliteration appears elsewhere.
5. Keep duplicate-cluster membership and retained-item decisions in the
   manifest. Report removed, retained, and uncertain items by language,
   source, and domain.
6. Require human review of uncertain clusters and check that deduplication
   has not disproportionately reduced English, Hindi, or Hinglish coverage.

No deduplication method, threshold, normalization, or dataset is selected or
run in this phase.

## Leakage-resistant data splits

After sources, deduplication policy, and split proportions are approved:

- Assign entire duplicate clusters, documents, source series, contributors,
  or other related groups to a single split wherever feasible. Avoid
  sentence-level random splitting that places copied or near-identical text
  on both sides.
- Create train, validation, and sealed test manifests. Fit tokenizer
  vocabulary only on the approved training split. Use validation only for
  pre-approved selection and tuning; do not inspect or tune against the test
  set.
- Keep mixed-language documents and their related translations or
  transliterations grouped to reduce cross-split leakage.
- Define split seeds and deterministic assignment rules before splitting.
  Record split counts and source/domain/language composition without exposing
  protected content.
- Freeze test data, access, and evaluation code. Any necessary changes to a
  sealed test set require documented approval, a new version, and clear
  disclosure.
- Audit near-duplicate overlap and source overlap across splits before any
  experiment. Keep a reproducible manifest/checksum for every split.

## Language-specific data quality and coverage

English, Hindi (Devanagari), and Hinglish (Roman Hindi) must have separately
reported counts and quality checks, with identical review rigor. Mixed
English/Hindi/Hinglish data must be an additional report category, not
silently assigned to English or Hindi. Equal priority does not require equal
vocabulary quotas or equal raw item counts; the balancing basis must be
explicitly approved.

For each group, future reports should include:

- Approved source count and contribution by source/domain, item and document
  counts, split counts, and size measured in characters, code points, UTF-8
  bytes, and whitespace-defined words where meaningful.
- Script/language label coverage, uncertain or mixed-label rates, and
  representative coverage limitations. Hinglish remains its own group even
  when it shares Latin-script words with English.
- Devanagari checks for matras, virama/conjunct sequences, nukta forms,
  combining marks, punctuation, and Unicode normalization variants.
- Roman Hindi checks for spelling/transliteration variants, optional
  diacritics, repeated letters, punctuation, and English code-switches.
- Quality screening for encoding damage, boilerplate, duplicates, spam,
  non-text artifacts, unsafe or sensitive content, and license/provenance
  gaps; report exclusions and uncertainty by language.
- Coverage and vocabulary evaluation per language in any later experiment:
  token fertility per word/grapheme/code point, unknown/fallback rates,
  sequence-length distributions, round-trip behavior, and relevant
  worst-group gaps.

Do not use a single language-weighted aggregate to hide a failure in one
group. Pre-register equal per-language acceptance gates and report each
group plus the worst-group result.

## Approval checklist for a bounded tokenizer-only experiment

No experiment may start until an authorized owner records affirmative
approval for every applicable item:

- [ ] Purpose, scope, stop conditions, and explicit exclusions are approved.
- [ ] Candidate tokenizer algorithms, implementation/tooling, vocabulary
      size range, and reproducibility settings are authorized.
- [ ] Every source and acquisition method has source-specific license,
      attribution, privacy, and permitted-use approval.
- [ ] Consent, personal-data exclusion, retention, deletion, and incident
      procedures are approved; private conversations and SQLite memory remain
      excluded.
- [ ] English, Hindi, and Hinglish pools and the mixed-language category are
      identifiable, balanced by an approved basis, and separately reportable.
- [ ] Data quality, language labels, deduplication, and leakage-resistant
      train/validation/sealed-test plans are documented and reviewed.
- [ ] Normalization, pre-tokenization, unknown/fallback, reserved-token, and
      exact-decoding policies are specified.
- [ ] Per-language metrics, equal acceptance criteria, reviewer roles, and
      artifact handling are pre-registered.
- [ ] The experiment is limited to tokenizer evaluation; no language-model
      training, provider replacement, or live-assistant integration is
      included.
- [ ] Final authorization is recorded by the user or designated approver
      after privacy, licensing, and technical review.

If any required approval is missing, ambiguous, expired, or contradicted by
source terms, do not acquire or process the source and do not run the
experiment. Escalate the issue for explicit resolution.

## Unresolved decisions requiring explicit user approval

1. The tokenizer experiment's purpose, supported domains, intended artifact
   distribution, and downstream use.
2. Which public-source categories or specific sources may be considered,
   their licenses, jurisdictions, attribution requirements, and permitted
   tokenizer/model uses.
3. Whether any user-contributed material may ever be considered; the consent
   authority, withdrawal process, and prohibited personal/sensitive data.
4. Privacy screening standard, data minimization, access roles, retention
   periods, deletion verification, backup expiry, and response owner.
5. Approved language/domain coverage and how equal priority is operationally
   balanced (examples, characters, bytes, words, or another pre-agreed unit).
6. Language labeling and uncertainty review for English, Devanagari Hindi,
   Hinglish, and mixed-language material.
7. Exact and near-duplicate methods, thresholds, normalization for matching,
   human-review process, and safeguards for transliterations and code-switches.
8. Train/validation/sealed-test proportions, grouping unit, seed, access
   controls, and procedures for changing a split.
9. Quality exclusion criteria, language-specific metrics, equal thresholds,
   acceptable worst-group gaps, and independent reviewers.
10. Which tokenizer algorithms, implementation/tooling, size sweep,
    normalization, pre-tokenization, unknown/fallback, and special-token
    policies may be tested in a later authorized phase.
11. Who may approve source use, the bounded experiment, artifact release, and
    any future tokenizer integration; what records constitute approval.
12. Whether later language-model training or integration is ever authorized.
    It remains outside this plan and must receive separate approval; the
    eventual Veronica language model must generate its own final answers.

## Final authorization boundary

This document is a governance and authorization plan only. **It does not
authorize data acquisition, tokenizer fitting, model training, or
integration.** It does not begin Phase 2E or any later phase.
