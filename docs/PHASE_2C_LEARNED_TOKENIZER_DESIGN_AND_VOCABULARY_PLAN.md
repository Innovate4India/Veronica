# Veronica Phase 2C: Learned Tokenizer Design and Vocabulary Plan

## Status and scope

This is a planning document only. It does not choose an algorithm, define a
final vocabulary size, acquire or process data, fit a vocabulary, or authorize
training. The Phase 2A byte tokenizer remains unchanged and independent of
Ollama and other providers.

The eventual Veronica language model must generate its own final answers.
A tokenizer only maps between text and model token IDs; it does not generate
answers and does not authorize replacing model generation with an external
provider.

Phase 2A provides a deterministic UTF-8 byte mapping with IDs 0–255.
Phase 2B measured synthetic English, Hindi (Devanagari), Hinglish (Roman
Hindi), and mixed inputs. Its results are a byte-count baseline, not a
learned-tokenizer benchmark. Neither phase collected a corpus or trained a
model.

## Candidate approaches

| Approach | Typical training and segmentation | Potential strengths | Trade-offs and unknown-token considerations |
|---|---|---|---|
| BPE (Byte Pair Encoding) | Iteratively merges frequent adjacent symbols or token pairs; applies learned merges at inference. | Simple merge list and deterministic segmentation; broad ecosystem familiarity; byte-level variants can represent arbitrary UTF-8 when all bytes are in the base vocabulary. | Frequency-driven merges may favor common scripts/domains; rare words and spelling variants can fragment. Character-based variants can emit unknown tokens unless all input characters or a fallback are covered. |
| Unigram language-model tokenizer | Starts with candidate subwords, estimates a subword model, and prunes candidates; inference selects a high-scoring segmentation, commonly by dynamic programming. | Explicit segmentation scores and potentially multiple plausible segmentations; pruning offers a different vocabulary/coverage trade-off from greedy pair merges. | Training and inference are more involved; scores and stochastic segmentation behavior need a deterministic evaluation configuration. Unknown handling still depends on the base alphabet and fallback. |
| WordPiece | Learns subwords using a likelihood-oriented objective; inference commonly chooses the longest available match at each position, with continuation markers. | Greedy segmentation is straightforward to apply and is familiar from transformer systems. | Greedy choices can differ from globally optimal segmentations; vocabulary and marker conventions are model-specific. Character coverage or an unknown-token fallback must be defined. |

This is a conceptual comparison, not a recommendation or selection. The
eventual model architecture, training implementation, inference runtime, and
quality results may change the relative suitability of each candidate.

## Vocabulary size, fertility, and coverage

A larger vocabulary can reduce average token fertility and sequence lengths
by storing more frequent words, morphemes, or script-specific sequences as
single tokens. It also increases token embedding and output-projection
parameters, memory and checkpoint size, and the risk that low-frequency
entries consume capacity without useful coverage.

A smaller vocabulary generally reduces those parameter costs, but tends to
split words into more pieces, increasing sequence lengths and compute. It
may improve reuse of subword units, but can make rare morphology, names, and
spelling variants more fragmented. These are tendencies, not guaranteed
outcomes; they must be measured for the chosen data and model.

Use the following measurements rather than a single aggregate:

- **Token fertility:** subword tokens per whitespace-delimited word and per
  Unicode grapheme cluster. Also report tokens per Unicode code point for
  continuity with Phase 2B. State the segmentation rules and Unicode version
  used for words and grapheme clusters.
- **Coverage:** unknown-token rate, byte/character fallback rate, and the
  share of evaluation text represented without loss. Report each language
  and script separately.
- **Length:** token-count distribution per example (median, 95th and 99th
  percentiles), plus UTF-8 bytes and code points for context.
- **Vocabulary use:** frequency and share of used vocabulary items by
  language group, shared versus script-specific units, and unused or
  extremely rare entries.

Do not treat “tokens per character” alone as a fairness score: Unicode
code-point counts differ from bytes and grapheme clusters, and whitespace
word conventions differ across text. Do not compare learned-tokenizer
compression claims against the Phase 2A byte baseline without stating the
unit, corpus, and preprocessing.

No vocabulary size is selected here. Before any experiment, approve a
candidate size range in light of model parameter and context budgets; apply
the same pre-approved range to candidate algorithms where technically
meaningful. If a candidate cannot use the same sizes or constraints, record
that limitation rather than presenting it as a directly controlled result.

## Unknown-token and Unicode policy decisions

The tokenizer must have a documented path for every permitted input:

- A byte-level base alphabet or byte fallback can provide coverage for
  arbitrary valid UTF-8, at the cost of longer sequences for uncommon text.
- A character/subword vocabulary may use an explicit unknown token, a
  character fallback, or a byte fallback. An unknown token is lossy unless
  the original text is retained elsewhere; fallback behavior affects
  fertility and must be included in measurements.
- The policy for malformed Unicode input, invalid UTF-8 at system boundaries,
  and token-ID decoding errors must be explicit and tested.

Do not silently normalize text. Before training, decide whether input is
preserved verbatim or normalized under a documented Unicode normalization
form. Evaluate normalization collisions and exact round trips. In particular:

- Devanagari vowel signs (matras), virama-based conjuncts, and nukta-bearing
  forms may appear as multiple code points and should be measured by both
  code points and grapheme clusters.
- Canonically equivalent or visually similar sequences must not be assumed
  identical. Include precomposed/decomposed forms and preserve their exact
  behavior in the test plan.
- Roman Hindi has spelling variation, transliteration variation, repeated
  letters, and optional diacritics. Do not silently rewrite spellings or
  conflate Roman Hindi with English merely because both use Latin script.
- Punctuation, whitespace, emoji, symbols, and mixed-script spans should
  remain covered. Decide whether pre-tokenization separates punctuation or
  whitespace and how exact reconstruction is maintained.
- Any reserved model-control tokens require an approved inventory, escaping
  rules, and collision tests. Do not introduce reserved IDs implicitly.

## Multilingual fairness and evaluation methodology

Treat English, Hindi (Devanagari), and Hinglish (Roman Hindi) as three
separately reported groups with equal evaluation priority. Also report mixed
English/Hindi/Hinglish examples separately. Equal priority means the groups
receive the same evaluation rigor and pre-approved quality criteria; it does
not imply an equal number of vocabulary entries per language.

After data and training are separately authorized, use this controlled
methodology:

1. **Pre-register scope and metrics.** Specify supported scripts and domains,
   normalization, word/grapheme measurement rules, unknown/fallback policy,
   and acceptable per-language thresholds before fitting.
2. **Build governed language-specific pools.** Maintain identifiable
   English, Devanagari Hindi, and Roman Hindi/Hinglish pools plus a mixed-text
   pool. Decide and document balancing by examples, characters, bytes, or
   training tokens. Hinglish overlap with English must not erase its
   separately measured results.
3. **Create leakage-resistant splits.** Deduplicate before splitting and
   group related documents, contributors, or sources so near-duplicates do
   not cross train, validation, and test. Freeze validation and test inputs;
   never fit vocabulary on the test split.
4. **Control candidate comparisons.** Use the same approved corpus,
   preprocessing, normalization, target vocabulary sizes, and evaluation
   splits for BPE, Unigram, and WordPiece where possible. Record all
   implementation versions, settings, seeds, and tie-breaking rules. Do not
   select a candidate from aggregate scores alone.
5. **Report language-specific results.** For every candidate and each of the
   three language groups, report fertility per word and grapheme, code-point
   counts, unknown/fallback rate, sequence-length percentiles, round-trip
   exactness, and vocabulary-use statistics. Report mixed-script results
   separately.
6. **Apply equal gates and inspect errors.** Use the same pre-approved
   thresholds for each group; report each group and the worst-group result,
   not only a weighted average. Inspect examples involving matras, conjuncts,
   nukta forms, spelling variation, punctuation, and script switches.
7. **Reproduce and review.** Re-run from versioned, licensed data manifests
   and recorded configurations. Require independent technical, privacy, and
   licensing review before choosing or distributing a tokenizer artifact.

This methodology specifies measurements only. It does not set thresholds,
weights, data quantities, or a vocabulary size.

## Data licensing, privacy, and provenance requirements

No data is authorized for collection or use by this plan. Before any future
data acquisition or tokenizer fitting:

- Maintain a source-level manifest: origin, acquisition date and method,
  owner, language/script, domain, license and version, attribution duties,
  redistribution limits, and permitted training/evaluation use.
- Obtain documented approval that each license permits the intended
  processing, tokenizer training, artifact distribution, and any downstream
  model use. Preserve notices and required attribution.
- Establish provenance from source through transformations and splits.
  Record filtering, normalization, deduplication, and exclusions so a
  tokenizer artifact can be traced to approved inputs.
- Exclude private conversations, chat history, SQLite memory, credentials,
  and personal user data by default. Any proposed user-contributed material
  requires explicit informed consent, a defined purpose and retention
  period, withdrawal handling, and privacy review before ingestion.
- Define privacy and sensitive-data screening, minimization, access controls,
  retention, deletion, and incident handling. Document limitations of
  filtering; do not claim perfect removal of personal information.
- Deduplicate exact and near-duplicate content before splitting. Record
  methods and review false positives, especially across scripts and
  transliterations. Deduplication must not be used to erase an entire
  language or source category.
- Split by source/document/contributor groups where possible, not only
  randomly by sentence. Keep training, validation, and test manifests
  separate; restrict test access and prevent vocabulary fitting on held-out
  test data.
- Review language balance, dialect and domain representation, and consent
  independently for English, Hindi, and Hinglish. A nominally balanced token
  count cannot compensate for unlicensed, private, or unrepresentative data.

## Safe future sequence

1. Keep the Phase 2A tokenizer and provider behavior unchanged.
2. Resolve and record all pending decisions below; authorize any data policy
   and acquisition separately.
3. Conduct privacy, provenance, consent, and license review before collecting
   or processing candidate data.
4. Design and approve the balanced pools, deduplication plan, frozen
   train/validation/test split, normalization, and evaluation protocol.
5. Obtain explicit authorization for a bounded tokenizer-only experiment,
   including candidate algorithms, size sweep, allowed tools, reproducibility
   requirements, and stop conditions.
6. Only after that authorization, fit candidate vocabularies and run the
   pre-registered evaluation. Keep the model-training pipeline and live
   assistant out of scope.
7. Independently review results and artifacts, then seek separate approval
   before selecting, integrating, or distributing a tokenizer.
8. Treat language-model training, inference integration, and any provider
   changes as distinct later work requiring their own approval. Veronica's
   eventual model must generate its own final answers.

No step in this document authorizes data acquisition, vocabulary fitting,
model training, provider replacement, or a later phase.

## Pending decisions requiring explicit user approval

1. **Intended model and runtime constraints:** architecture, context length,
   parameter/memory budget, tokenizer compatibility, and deployment targets.
2. **Candidate algorithms:** which of BPE, Unigram, and WordPiece to test,
   and whether any implementation/tooling is permitted later.
3. **Vocabulary-size sweep:** candidate sizes or range, reserved-token
   budget, and maximum acceptable tokenizer/model parameter overhead.
4. **Input policy:** normalization form or verbatim preservation,
   pre-tokenization rules, whitespace/punctuation handling, malformed-text
   behavior, and Unicode version.
5. **Unknown handling:** unknown-token versus character/byte fallback,
   coverage guarantees, and exact decode/round-trip requirements.
6. **Special tokens:** whether any are needed, their inventory, IDs,
   escaping, and collision behavior.
7. **Fairness objective:** how training pools are balanced, which domains and
   dialects are in scope, what metrics and equal per-language gates apply,
   and what worst-group trade-off is acceptable.
8. **Data authorization:** approved sources and licenses, intended
   redistribution rights, provenance requirements, and any attribution
   obligations.
9. **Privacy and consent:** prohibited data, whether any consented
   user-contributed data may ever be considered, retention/withdrawal rules,
   and the approving privacy authority.
10. **Dataset design:** sample quantities, language/domain coverage,
    contributor/source grouping, deduplication method, and train/validation/
    test proportions and access controls.
11. **Acceptance and governance:** fertility/unknown/sequence-length
    thresholds, reproducibility requirements, independent reviewers, and
    authority to approve a final tokenizer artifact.
12. **Future model boundary:** confirmation that tokenizer evaluation remains
    separate from model training and provider changes, and that Veronica's
    eventual language model—not an external answer-generation provider—must
    generate final answers.

Until these decisions are approved, no corpus should be acquired or
processed, no vocabulary should be fitted, and no tokenizer should be
selected or integrated.
