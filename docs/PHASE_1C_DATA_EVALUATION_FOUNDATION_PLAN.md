# Veronica Phase 1C: Data Governance and Evaluation Foundation Plan

**Status:** Planning only
**Reviewed:** 2026-11-24
**Approved direction:** Train Veronica's first tiny language model from scratch
**Scope:** No source/test/configuration changes, installations, downloads, tokenizer training, or model training are authorized by this plan.

## 1. Executive summary

Veronica's repository currently has no language-model training corpus, dataset pipeline, custom tokenizer, language-model evaluation harness, or model checkpoint. Its application has provider-neutral interfaces, but Ollama remains the only complete text provider. The `VeronicaModelProvider` is a nonfunctional scaffold. Existing SQLite memory is user-approved personal data and is not training data.

For the first small, from-scratch model, data quality, provenance, leakage control, and truthful evaluation matter more than collecting the largest possible corpus. The recommended starting sources are:

- The official Python documentation and its code examples as a small, well-scoped technical English source with explicit PSF licensing terms.
- Carefully filtered English and Hindi Wikimedia text only after license, attribution, privacy, and model-distribution implications receive review.
- IndicCorpV2 as a research candidate for Hindi/Indic coverage only after source-level provenance and privacy review; its dataset card states CC0, but its scale and web-derived-content risks make it inappropriate as an automatic first corpus.
- An original, consented, creator-licensed Hinglish set, because no suitable public Hinglish source with verified terms was established in this review.
- FLORES-200 only as a possible held-out language evaluation resource, not as training text; it is a benchmark, its use is subject to access conditions and CC BY-SA 4.0, and public benchmark leakage must be controlled.

None of these candidates is approved for collection or training by this plan. Dataset licenses and permission to use a corpus for training, distribute derived data, or distribute model weights are distinct questions; obtain legal review rather than infer permission from public access or a dataset-card label.

**Tokenizer recommendation:** make a from-scratch SentencePiece BPE tokenizer with byte fallback the first candidate, then compare small vocabulary settings on an approved training-only corpus. This is a recommendation for an experiment, not a chosen model configuration. Keep all tokenizer fitting strictly out of validation and test data.

**Evaluation recommendation:** establish a frozen, human-checked, multilingual test set and a held-out source/document split before the first training run. Report language-model metrics (negative log-likelihood, perplexity, next-token accuracy) separately from task-level language comprehension, reasoning, and factual consistency. Lower loss is evidence of improved next-token prediction, not proof of assistant-level intelligence.

## 2. Repository assessment

### Verified current state

| Component | Current implementation and constraint |
|---|---|
| Application and provider boundary | `dev_ai.py` uses the provider factory. `app/ai/base.py` defines provider-neutral contracts and `app/ai/provider.py` registers factories, with Ollama the default. Ollama is still the only complete text-generation provider. |
| Native-provider placeholder | `app/ai/veronica_provider.py` reports no implemented capabilities, is unhealthy, and raises a model-unavailable error; it loads no model. |
| Conversation and tools | `app/ai/service.py` (`AIService.respond`) assembles persona/role/tool instructions, maintains bounded in-process conversation, retrieves optional memories, and invokes an injected tool service. `app/ai/tool_calling.py` and `app/tools/registry.py` provide neutral tool orchestration and validated registered-tool dispatch. These are reusable application layers, not a training system. |
| Memory | `app/memory/service.py` stores only explicitly requested memories, rejects a small set of recognizable credential patterns, and searches using bounded lexical `LIKE` matching. `app/memory/database.py` creates a local SQLite table. This is personal memory, not a document corpus, semantic knowledge base, conversation archive, or training source. The credential checks are useful application safeguards but are not a comprehensive corpus privacy scanner. |
| Configuration and dependencies | `app/config.py` reads environment settings and includes the `VERONICA_AI_PROVIDER` selection. `requirements.txt` contains voice/media dependencies and Pillow, not a language-model training stack. The current `.venv` reports Python 3.14.5. |
| Data and model assets | Existing local Whisper and Piper assets are speech models, not text-generation training data or Veronica language-model weights. No dataset preparation/training assets were added for Phase 1B. |
| Tests | `tests/test_memory.py` tests SQLite CRUD, bounded matching, credential refusal, and conversation-memory behavior. Other AI/provider/tool tests cover application contracts. There are no dataset, tokenizer, split-leakage, training, or model-quality tests. The Phase 1B plan records the last full test run as 356 collected, 355 passed, 1 skipped (Windows symlink privilege); this Phase 1C planning task did not rerun the suite. |

This agrees with the [Phase 1B foundation plan](PHASE_1B_NATIVE_AI_FOUNDATION_PLAN.md), [Phase 1 audit](PHASE_1_AUDIT.md), and [Phase 1A independent approval audit](PHASE_1A_INDEPENDENT_APPROVAL_AUDIT.md). The latest Phase 1A approval verifies the application/orchestration boundary only; it does not imply that a native provider, training code, or data-governance system exists.

### Source files checked

- [app/ai/base.py](../app/ai/base.py), [app/ai/provider.py](../app/ai/provider.py), [app/ai/service.py](../app/ai/service.py), and [app/ai/veronica_provider.py](../app/ai/veronica_provider.py)
- [app/memory/service.py](../app/memory/service.py), [app/memory/database.py](../app/memory/database.py), and [app/memory/models.py](../app/memory/models.py)
- [app/tools/registry.py](../app/tools/registry.py) and the existing [tests/](../tests/)
- [app/config.py](../app/config.py), [requirements.txt](../requirements.txt), and [docs/PHASE_1B_NATIVE_AI_FOUNDATION_PLAN.md](PHASE_1B_NATIVE_AI_FOUNDATION_PLAN.md)

No local SQLite memory contents or `.env` values were read for this plan.

## 3. Candidate data sources

The table distinguishes a source being openly accessible from having confirmed rights for this particular training and distribution plan. Licenses below are reported by the cited source; this is not a legal conclusion about model weights or outputs. No source was downloaded.

| Source and location | License/permission evidence | Language and approximate availability | Quality and privacy considerations | Suitability for Veronica |
|---|---|---|---|---|
| **Python documentation**: [docs.python.org](https://docs.python.org/3/) and the documentation tree in [python/cpython](https://github.com/python/cpython/tree/main/Doc) | Python's official license page says software and documentation are under the PSF License Version 2. Starting with Python 3.8.6, documentation examples/recipes/code are dual-licensed under PSF-2 and Zero-Clause BSD [1]. Preserve applicable notices and record the precise revision and terms. Training and checkpoint distribution still require review. | English prose, programming documentation, and code examples. It is a maintained but domain-limited collection; an authoritative token/word count was not identified in this review. Hindi/Hinglish coverage is not provided. | Official, edited technical material is comparatively clean and useful for programming vocabulary. Examples may contain names, paths, or illustrative credentials; scan and manually review extracts. Limited prose style and subject diversity. | **Recommended as a small technical source candidate**, after pinning a release/revision and preserving its licenses. Not sufficient for general English training or Hindi/Hinglish. |
| **Wikimedia English and Hindi Wikipedia text**: [Wikimedia dumps](https://dumps.wikimedia.org/) / [MediaWiki Content File Exports](https://dumps.wikimedia.org/other/mediawiki_content_history/readme.html) | The dump legal guide says most original text is available under GFDL and CC BY-SA 4.0, with exceptions and project-specific details; the Terms of Use and dump contents control. It also warns that dumps may contain material believed to be fair use or potential infringement [2]. CC BY-SA requires attribution and share-alike for adaptations; the effect on training and model distribution needs legal review [3]. | Broad English and Hindi (Devanagari) encyclopedic coverage. Edition sizes change; no current per-edition size/count was measured here. The January 2027 sunset notice applies to specified legacy XML database-backup dump formats, not every Wikimedia data format; Wikimedia recommends MediaWiki Content File Exports as the replacement [4]. | Useful factual/expository breadth, but article quality varies, contains biographies and personal details, and may include vandalism or disputed content. Dump metadata/history can contain contributor identifiers; exclude it from text and protect processing logs. Copyright exceptions and source-level problems require filtering. | **Conditional candidate only after source-specific licensing, attribution, and privacy review.** Retain page/revision attribution and license lineage. Do not assume model-weight distribution is compatible with source terms. |
| **AI4Bharat IndicCorpV2**: [dataset card](https://huggingface.co/datasets/ai4bharat/IndicCorpV2) and [ACL 2023 paper](https://aclanthology.org/2023.acl-long.693/) | The dataset card states that datasets created in the work are released under CC0 [5]. That declaration does not automatically resolve every underlying third-party rights or privacy question, later revisions, or every intended use. Verify source provenance and terms before any use. | Hindi in Devanagari and other Indic languages. The paper reports 20.9B tokens across 24 languages. At review time, the hosted card/viewer displayed about 481M rows and 23 splits; these figures may describe different revisions or representations from the paper. They are not verified permanent corpus statistics. Pin the exact revision and verify its contents, metadata, and counts before considering any future use. | The card describes it as pretraining data. The scale and web-corpus nature create risks of personal information, copied material, duplication, noisy or stale text, and uneven language quality. No guarantee of Hinglish or Latin-script Hindi coverage. | **Research candidate, not an initial approved corpus.** A carefully bounded, documented subset might be considered after exact-revision, license/provenance, and privacy review; do not ingest or train on the full corpus by default. |
| **FLORES-200**: [dataset card](https://huggingface.co/datasets/facebook/flores) | Its card states CC BY-SA 4.0 and requires accepting conditions to access the files; access conditions and attribution must be respected [6]. | Parallel benchmark material for 200 languages, including English and Hindi; the card reports 3,001 sentences sourced from 842 web articles, split into dev, devtest, and hidden test. It is small and benchmark-oriented. | Professional translation/verification is valuable for multilingual checks but domain and sentence style are limited. The card explicitly emphasizes protecting evaluation integrity. Text/URLs and public availability create contamination and attribution concerns. | **Evaluation-only candidate**, not training or tokenizer-fit data. Use only under its access terms; keep test data sealed and check for overlap with all training sources. It is not a standalone Hindi/Hinglish comprehension evaluation. |
| **Veronica-commissioned original Hinglish and bilingual technical examples** (to be authored locally after approval; no existing source URL) | Obtain written rights from each author or use a reviewed license that grants the required use, adaptation, and distribution. Record contributor, consent, license version, and any restrictions per item. | English, Hindi Devanagari, Latin-script Roman Hindi/Hinglish, and code-switch examples can be deliberately authored. No existing volume is available or estimated. | Potentially high relevance and script control if reviewed by bilingual authors. Keep examples generic and synthetic/original; do not solicit personal stories, private chats, or secrets. Requires labor and quality review. | **Recommended only as distinct, split-specific collections.** Do not reuse the same small authored Hinglish collection for tokenizer fitting/training and final evaluation. It will not, by itself, supply enough varied text for useful pretraining. |

### Sources not approved by default

- A public URL, dataset-hosting page, or “open” label is not sufficient permission. Do not use scraped corpora, source-code collections, user-contributed Q&A, or benchmark data unless the exact version, underlying licenses, privacy conditions, and intended model/checkpoint distribution have been reviewed.
- Avoid using FLORES or any evaluation benchmark as training data. Public test data can leak into broad web corpora; a decontamination check is still required.
- Project Gutenberg and similar book collections are not selected here: per-work public-domain status and terms must be verified for each intended work and jurisdiction before use. No blanket “publicly readable” permission is assumed.

## 4. Language distribution strategy

The corpus inventory and human quality review must precede any fixed percentages. Do not let a large English source dominate simply because it has more raw lines, and do not manufacture balance by repeatedly oversampling a tiny Hinglish set.

1. Assign each document a primary language/script label: English; Hindi-Devanagari; Hinglish-Roman; or technical/code. Preserve secondary tags (for example, Hindi text containing English technical terms). Treat source code as a separate task/format tag, not as a substitute for natural-language Hindi or Hinglish.
2. Measure eligible **tokens and documents** per source and stratum after filtering. Report coverage, duplicates, quality rejections, and source concentration by language.
3. Use a capped, token-based sampling schedule. A source may not dominate a training epoch solely by size. Set per-language batch quotas only where there is sufficient independent high-quality material; do not duplicate records to fill a quota.
4. For the first diagnostic experiment, compare balanced sampling against the natural eligible-data mixture. A balanced schedule is an experimental control, not an assertion that equal language shares are optimal. Record and approve the final schedule before training.
5. Report training/validation loss, tokenization fertility, and task metrics separately for English, Hindi-Devanagari, Hinglish-Roman, and technical/code. Also report aggregate metrics with an explicitly stated macro or token-weighted averaging method.
6. Preserve each original script and code formatting. Do not automatically transliterate Hindi, normalize Hinglish into English, or merge the Hindi-Devanagari and Hinglish-Roman evaluation buckets.

The user's relative priority among the four strata is still a decision. Corpus imbalance, the availability of licensed Hinglish material, and the intended first-model objective determine feasible ratios; they cannot be responsibly fixed before source approval and inventory.

## 5. Data preparation architecture

Keep dataset tooling and artifacts outside the interactive application and separate from `app/memory/`. The future pipeline should be deterministic, auditable, offline-capable after approved source snapshots are obtained, and fail closed on missing/ambiguous license records.

### Proposed pipeline

1. **Approve and register source.** Create a source record before collection: canonical location, publisher/creator, exact revision or snapshot date/hash, applicable license and terms URL, allowed purposes, attribution obligations, language coverage, privacy review, and approval owner. Reject sources with unknown terms.
2. **Collect only approved snapshots.** Later collection requires explicit approval and obeys the source's rate limits/access rules. Store original snapshot separately with restrictive access. Do not silently crawl URLs or fetch unreviewed sources.
3. **Extract with provenance.** Convert source-native files to text with versioned extractors. Keep a stable document/revision ID and source/license IDs attached to every derived record. Strip non-content navigation while retaining needed attribution outside the model text.
4. **Normalize conservatively.** Decode valid Unicode; normalize canonically (NFC) where appropriate; standardize line endings and whitespace; remove known markup/boilerplate. Preserve Devanagari combining marks, punctuation, casing, code blocks, indentation, and meaningful mixed-script text. Never apply transliteration or destructive compatibility normalization without a measured reason. Quarantine invalid encodings rather than silently replacing unknown content.
5. **Identify language/script.** Combine Unicode script detection and language identification, then manually audit representative samples and all ambiguous/short Hinglish samples. Store confidence and "mixed/uncertain" labels. Never treat a script detector alone as reliable Hinglish detection.
6. **Deduplicate before splitting.** Compute exact hashes after the documented normalization. Cluster near duplicates using a pinned algorithm/threshold; inspect false positives. Deduplicate across every source and language pair, not just within files. Keep translation/alignment groups and source revisions together.
7. **Quality filter.** Reject or quarantine extraction artifacts, navigation, spam, repeated boilerplate, corrupted text, implausible language labels, malformed code, and low-quality OCR. Use source-aware rules plus measured automated checks and human review. Keep rejection counts/reasons, not rejected sensitive text in logs.
8. **Privacy and rights filter.** Scan for credentials and personal information before accepting text; quarantine uncertain matches for restricted review or reject them. Never print sample contents in logs. Apply source-specific exclusion lists, and record approvals/exclusions without storing unnecessary personal data.
9. **Split by document and duplicate cluster.** Assign whole works/articles/source groups and near-duplicate clusters to a split; do not randomly split individual lines or chunks from the same document. Keep translations, paraphrases, revisions, and extracted fragments of one work in one split. Use a seeded, versioned group assignment and preserve a frozen, separately authored evaluation set.
10. **Fit tokenizer on training split only.** Train vocabulary/normalization only from the training records. Then encode training, validation, and test with the same frozen tokenizer. Never inspect test loss to choose vocabulary size or training hyperparameters.
11. **Validate and publish a versioned dataset artifact.** Generate a manifest and report before training. Refuse export if source/license lineage is missing, splits overlap, required language strata are absent, or integrity/privacy checks fail.

### Leakage controls and split policy

- Deduplicate/cluster the full approved corpus **before** split assignment. Store cluster IDs, not just row IDs.
- Split by source document/work/repository/version and, where possible, by author or source domain. A document's paragraphs, code examples, translations, and revisions must not be scattered across splits.
- Preserve parallel translations and templated question/answer variants in the same split. For synthetic reasoning examples, hold out generation templates and random seeds so evaluation tests structural generalization rather than memorized instances.
- Use exact normalized hashes and near-duplicate checks between all splits and every evaluation set. Record match rates and quarantine unresolved matches.
- Keep the final test set read-only and use it only after model selection. Use validation data for checkpoint/hyperparameter decisions; use training data for gradient updates and tokenizer fitting.
- A fixed percentage split cannot be justified until source volume and independent document counts are known. Choose group-level ratios after inventory; never weaken source grouping just to achieve a target percentage.
- Public benchmark overlap can occur even if its hidden test partition is not directly downloaded. Exclude benchmark sources from training where feasible and report residual overlap/contamination limitations.

### Hinglish split isolation

- Maintain separate Hinglish-Roman training, validation, and sealed final-test manifests. Each example must belong to exactly one split.
- Keep the final Hinglish test examples inaccessible to both model training and tokenizer fitting. Fit the tokenizer only on training examples; validation and final-test text may be encoded with the frozen tokenizer but must not affect its vocabulary or normalization.
- Assign related Hinglish templates, paraphrases, translations, and exact/near-duplicate examples to the same split. Deduplicate and cluster these examples before assigning splits.
- Do not divide a single small authored Hinglish collection among training and final evaluation. Use distinct source collections for training/tokenizer fitting and sealed testing; if there is not enough independent material, defer the final evaluation rather than reuse examples.

### Versioning and reproducibility manifest

Each dataset version should record:

- dataset release ID, parent release, creation timestamp, pipeline source revision, dependency/tool versions, and deterministic seeds;
- per-source identifier, canonical URL, publisher, snapshot/revision/hash, license/terms and their snapshot, approval record, and allowed-use decision;
- per-document opaque ID, source/license ID, language/script labels and confidence, normalization/extractor versions, duplicate-cluster ID, and split assignment;
- per-language/source document and token counts, rejection counts by reason, deduplication statistics, privacy-review result, and dataset-level content hashes;
- explicit policy for whether raw, normalized, tokenized, and evaluation artifacts may be retained or distributed.

Do not place names, credentials, sensitive text, or private source content in logs/manifests. Store any necessary author attribution in a protected, access-controlled provenance ledger separate from model input. A manifest hash makes a release identifiable; it does not itself prove a source license.

## 6. Tokenizer foundation

### Comparison

| Approach | Unicode and unknown characters | Strengths | Trade-offs for English/Hindi/Hinglish/code |
|---|---|---|---|
| **Byte-level BPE** | Starts with byte symbols, so every valid UTF-8 string can be represented without an unknown Unicode character. Output decoding must still handle incomplete/invalid byte sequences safely. | Robust coverage for unseen scripts and mixed text; no language-specific pre-tokenization required. | Rare Devanagari characters may fragment into several byte tokens; potentially longer sequences. A byte-oriented base vocabulary consumes some slots. |
| **Character/subword BPE** | Learns merges over character units; unseen code points need `<unk>` or byte fallback. | Deterministic greedy segmentation, simple merge history, and common strings/code can become compact. SentencePiece supports BPE trained from raw text [7]. | Unicode coverage depends on character inventory/fallback; Devanagari marks and rare code points need explicit tests. Script imbalance can produce poor Hindi/Hinglish fertility. |
| **Unigram subword model** | Uses a learned set of pieces and probabilistic segmentation; unseen characters need `<unk>` or byte fallback. | Can retain alternative segmentations and supports subword regularization; SentencePiece supports training from raw sentences [7]. | More implementation/segmentation choices to validate. Sampling alternate segmentations is not required for the first deterministic baseline and may complicate reproducibility. |

### Recommendation and vocabulary policy

Use **SentencePiece BPE with byte fallback** as the recommended first candidate for an experiment, not as a final implementation decision. SentencePiece supports BPE and Unigram on raw Unicode text and exposes byte-fallback options [7, 8]. Byte fallback avoids a hard unknown-token failure for valid UTF-8 characters; it does not guarantee that the model will learn meaningful Hindi or Hinglish.

Do not lock a vocabulary size in this plan. Compare a small, predeclared candidate set such as 2,048 / 4,096 / 8,192 entries after checking eligible corpus size and language balance. These are experiment settings, not benchmarks or a justified final value. Vocabulary size has a direct model parameter cost: for example, 8,192 vocabulary entries × 256 hidden dimensions = 2,097,152 embedding parameters for one embedding matrix. If input and output embeddings are separate rather than shared, their combined parameter cost can be higher. Choose vocabulary size only after the model architecture, hidden dimension, and total parameter budget are approved. Select based on:

- token fertility (tokens per character/word) by English, Hindi-Devanagari, Hinglish-Roman, and code;
- byte-fallback frequency and exact encode/decode round trips on held-out text;
- frequency coverage of useful technical terms and common Hindi morphemes;
- model parameter budget: input embeddings and output projection grow with vocabulary, while small vocabularies increase sequence length and attention/context cost;
- repeatable tokenization quality without fitting vocabulary statistics on validation or test.

A larger vocabulary compresses frequent words and shortens sequences but allocates more model parameters to embeddings/output and may poorly represent rare words. A smaller vocabulary saves those parameters but fragments text, consumes context, and can lengthen generation. No single vocabulary size can be asserted optimal without the approved corpus and model architecture.

### Unicode, special tokens, and compatibility rules

- Apply one documented Unicode normalization policy (initially NFC for text where safe); preserve Devanagari combining marks and do not transliterate. Preserve code whitespace/case.
- Maintain independent coverage checks for Devanagari and Romanized Hindi. Hinglish has variable spelling and code-switching; tokenizer tests must use reviewed variants rather than silently "correcting" them.
- Reserve and version IDs for at least padding, beginning-of-sequence, and end-of-sequence markers as the model/trainer require. Mask padding from loss. Keep control tokens unambiguous and escape literal occurrences in source text.
- With byte fallback, ordinary valid UTF-8 input should not need `<unk>` for an unseen character. Retain a defined error/replacement policy for invalid byte input and test generated byte sequences before displaying text.
- Do not add chat-role, tool-call, or vision tokens to the first next-token pretraining vocabulary unless the approved training objective needs them. Later instruction tuning must add/use special tokens in a separately versioned and tested way.
- Save the tokenizer model, vocabulary, exact special-token IDs, normalization settings, algorithm/options, training-corpus manifest hash, tokenizer-tool version, and a content fingerprint alongside every model checkpoint. A model must refuse to load with a mismatched tokenizer fingerprint.
- Once model training starts, treat the tokenizer as frozen for that run lineage. A changed tokenizer means a new model/checkpoint lineage; token-ID compatibility must never be assumed.

## 7. Evaluation foundation

Create and freeze the evaluation set before training. Keep tests grouped by task, language, script, source, and difficulty. Use original or properly licensed evaluation material, do not copy private user conversations, and keep answer keys/sealed test examples inaccessible to the training pipeline.

### Metrics

| Evaluation layer | Measure | What it establishes / does not establish |
|---|---|---|
| Training and validation | Mean token negative log-likelihood (NLL) over non-padding targets; plot by step and separately by language/source. Perplexity is `exp(mean NLL)` using the same tokenization and mask. | Measures next-token prediction on the specified distribution. A training/validation gap can signal memorization/overfit. Loss is not a measure of assistant intelligence. |
| Held-out test | NLL and perplexity on a frozen, untouched test split; macro-average by language as well as a clearly labeled token-weighted aggregate. | Estimates next-token generalization to held-out documents. Run only after choosing a checkpoint; do not tune on test metrics. |
| Next-token prediction | Top-1 next-token accuracy on deterministic held-out prefixes, plus top-k accuracy if useful; break out script/language. | Measures prediction of a reference continuation. Multiple continuations can be valid, so interpret alongside NLL/perplexity rather than as standalone quality. |
| Basic language generation | For a fixed prompt set and decoding configuration, report successful nonempty completions, EOS/length behavior, invalid UTF-8/replacement events, and human-rated readability/coherence on a fixed rubric. Record decoding parameters and random seeds. | Checks whether generation runs and is legible; does not show factuality or useful instructions. |
| English comprehension | Accuracy/exact match on held-out, human-authored short questions and simple text-understanding tasks; report a separate human rubric for semantically correct free text. | Tests a narrow task set, not broad English comprehension. |
| Hindi comprehension | The same task families, written/reviewed in Devanagari by fluent readers. Report normalized exact match and blinded human semantic correctness separately. | Prevents English aggregate scores masking Hindi failure. |
| Hinglish comprehension | Original Roman-Hindi/code-switched prompts with independently reviewed reference answers; report exact/normalized match, code-switch preservation, and human task success. | Evaluates the explicitly targeted Roman Hindi style; do not combine this with Devanagari Hindi results. |
| Simple reasoning | Deterministic, safe arithmetic/pattern/order questions generated from templates. Report exact-match accuracy, error categories, and performance on held-out templates/seeds. | Tests specified small procedures and whether template memorization is present; not general reasoning. |
| Basic factual consistency | Supply a short held-out evidence passage and question. Human raters mark supported claims, contradictions, and unsupported factual claims. Report supported-claim fraction, contradiction rate, and abstention when the passage lacks an answer. | Measures grounded consistency with provided text, not factual knowledge from model weights. |
| Repetition / incoherence | Report repeated 4-gram rate (fraction of 4-gram positions whose n-gram appeared earlier), distinct-2 (`unique bigrams / all bigrams`), completion length, and blinded coherence rubric. | Detects common looping/degeneration signals; no single statistic defines coherent language. Compare identical prompts and decoding settings. |

Score all language-specific tasks separately and publish sample counts, confidence intervals where counts support them, scoring/normalization rules, and representative failure categories. Have at least two human reviewers for subjective language/factual rubrics where practical, with disagreements recorded. Do not use an external language model as the sole evaluator or silently introduce a pretrained model dependency.

### Language modeling versus assistant-level capability

Next-token training teaches a model to assign probabilities to token sequences. Better held-out loss may indicate that it models the test text distribution more effectively. It does **not** by itself prove it understands instructions, reasons reliably, knows current facts, follows Veronica's personality, handles tools, protects privacy, or behaves safely. Those require separate task tests, instruction data, policy checks, and robust evaluation. A tiny first model may generate incoherent or memorized text even when its training loss decreases; report that honestly.

### Proposed evaluation pass/fail gates

Before any model training begins, approve the evaluation set, baseline, scoring process, and numeric pass/fail thresholds. No numeric thresholds are set in this plan; every threshold below requires separate user approval.

- **Language-specific performance:** set minimum criteria independently for English, Hindi-Devanagari, and Hinglish-Roman. A strong aggregate score must not conceal a failed language-specific gate.
- **Readability and coherence:** set a minimum human-rated readability/coherence score and define the reviewer rubric and disagreement process.
- **Repetition and incoherence:** set maximum acceptable repeated n-gram/repetition rates and incoherence ratings using the measures in the metrics table.
- **Task performance:** set minimum task-level criteria separately for comprehension and simple reasoning, with sample counts and scoring rules fixed in advance.
- **Safety, privacy, and factual support:** define pass conditions for safety checks, prohibited-data leakage/privacy checks, and the maximum acceptable unsupported-factual-claim or contradiction rate on evidence-grounded tasks.
- **Failure reporting and limitations:** require a report of all failed gates, per-language/task results, sample sizes, uncertainty where meaningful, representative error categories, and known model limitations. Do not average away failures or claim general assistant competence from language-model loss.

The evaluation set and a baseline must be approved and measured before these thresholds are chosen; the user must approve the numeric values before the first training run. If a baseline requires an external pretrained model, that use needs separate approval and does not change the requirement that Veronica's own model generate final answers in native mode.

## 8. Privacy and data governance rules

1. **No automatic conversation training.** Never ingest chat logs or personal conversations. Any future opt-in process must be explicit, item-specific, revocable, and documented; default remains excluded.
2. **No memory training.** Never read `data/veronica_memory.db` or include SQLite memories in a corpus. Memory is personal application state, not a dataset.
3. **No credentials/private information.** Exclude passwords, API keys, access tokens, private keys, financial/health records, personal addresses, government IDs, and unnecessary contact details. Regex scans alone are insufficient; combine source rules, automated detectors, review/quarantine, and a safe deletion process.
4. **Least data and least access.** Collect only approved text fields. Do not retain source accounts, author profiles, IPs, or unrelated metadata. Restrict raw and quarantined data; avoid printing text into logs or reports.
5. **Per-source rights record.** Require a license/terms snapshot, creator/source attribution, version/hash, approved purpose, and distribution decision before processing. Unknown/ambiguous terms mean reject pending review.
6. **Attribution and license obligations.** Preserve source attribution and change history where required. Do not claim that a license for a dataset automatically grants rights to all underlying items or settles the license of model weights/outputs.
7. **Immutable splits and test protection.** Keep train, validation, and test manifests separate; prohibit training processes from opening validation/test payloads. Version access controls and audits.
8. **Source removal and revocation.** Maintain source-to-document-to-derived-record-to-split lineage. On a rights/privacy request: quarantine the source immediately, remove its records from future dataset builds, rerun deduplication/splits/tokenizer fitting as needed, and issue a new dataset version. If an affected model has already been trained, do not claim that deleting the text removes its learned influence; quarantine/retire the checkpoint and retrain a clean lineage unless a reviewed alternative is approved.
9. **No silent license changes.** Pin the source revision and terms at acquisition. A changed card or license requires re-review, not automatic acceptance.
10. **Separation from runtime.** Dataset tooling must not run when Veronica starts; model inference must load only a deliberately selected, versioned checkpoint. Training artifacts and raw datasets must not be embedded in the application or committed by default.

## 9. Hardware and technical feasibility

Only the following are treated as verified for this task: Windows, NVIDIA RTX 3050 Laptop GPU with 6 GB VRAM, and active Python 3.14.5 virtual environment. CPU, system RAM, free disk, CUDA toolkit/driver compatibility, and thermal/power limits remain unknown. No training performance or memory benchmark was run.

- Data manifesting, text inspection, and many tokenizer experiments can be CPU-oriented, but RAM and disk availability are unknown and must be measured before choosing corpus subsets.
- A GPU having 6 GB VRAM does not establish that a specific tokenizer, training library, model architecture, sequence length, optimizer, or CUDA wheel works on this Windows/Python environment.
- `requirements.txt` does not declare a training/tokenizer framework. Compatibility, Python 3.14.5 wheels, CUDA support, and license obligations must be verified only after the user separately approves dependency investigation/installation.
- The source candidates range from a small documentation corpus to multi-billion-token web corpora. Their published size is not a recommendation to process/train on that size. The first tiny-model data budget must be selected from a source-approved inventory and measured training pilot, not from a guessed token count.
- Before estimating scale, record available RAM/disk and GPU/driver details, then benchmark a short approved-data preprocessing run and a tiny model dry run. This document makes no throughput, duration, VRAM-fit, or model-quality promise.

## 10. Future training-pipeline integration

The future offline pipeline should emit a validated, immutable dataset artifact plus a manifest, never connect directly to chat, memory, or tool execution. A training job must accept only a specific dataset release ID and training split; validation is read-only for checkpoint selection; test is accessible only to the final evaluator.

Every model checkpoint and derived/exported model should carry a machine-readable manifest containing:

- dataset release ID and hash, training split ID, source/license/provenance ledger version, and preprocessing pipeline revision;
- tokenizer release ID/hash, vocabulary size, algorithm, normalization, byte/unknown fallback behavior, and special-token IDs;
- model architecture/configuration, parameter count, initialization method, and model code revision;
- training configuration: seed, optimizer/scheduler, learning rate, batch/sequence lengths, precision, step/token counts, hardware/runtime versions, and checkpoint parent;
- evaluation harness revision, frozen test-set version, metrics by task/language, scoring notes, and known contamination/quality limitations;
- allowed-use/distribution status, approvals, and any source-removal restrictions.

The native provider can later validate that checkpoint manifest and tokenizer fingerprint at load time. Dataset versioning and provider integration must remain decoupled from `AIService`, `ToolCallingService`, and interactive startup. This design makes it possible for the Veronica model to generate its final answer from its own weights while retrieved external sources, when explicitly enabled, provide evidence only.

## 11. Risks and limitations

- **Legal ambiguity:** dataset license labels do not resolve every jurisdiction's training, derivative-work, model-weight, attribution, privacy, or output question. Legal review is a prerequisite for restricted sources.
- **Hinglish scarcity and variation:** publicly available Roman-Hindi data with clear rights was not verified. A small authored sample may support testing but can be too narrow and overfit easily.
- **Corpus imbalance:** large English or web sources can overwhelm Hindi/Hinglish despite row-level balancing. Track tokens, source concentration, and per-language loss.
- **Data quality and personal information:** web-crawl corpora can contain copied, stale, noisy, or personal content. Automated PII filters can miss secrets and falsely flag ordinary text.
- **Benchmark contamination:** public test material may be copied into training sources. Freeze test sets, use source-level exclusion, and publish overlap limitations.
- **Tokenizer trade-offs:** byte fallback prevents unknown Unicode input but can increase token count for underrepresented scripts; larger vocabularies compete for a tiny model's parameter budget.
- **Tiny-model limitations:** an educational from-scratch model may not produce reliable language, factual answers, or assistant behavior. Training loss is not evidence that the final system is useful.
- **Reproducibility limits:** deterministic seeds do not guarantee identical outputs across different tool/library versions or hardware. Pin versions and preserve artifacts while labeling remaining sources of nondeterminism.
- **Unlearning limits:** removing a record from a future corpus cannot prove its influence has disappeared from an already trained checkpoint. Preserve full lineage and be prepared to retire and retrain.
- **Platform constraints:** Python 3.14.5 and Windows package/GPU support are unverified for a future ML stack; the current tests do not test model training or CUDA.

## 12. Decisions requiring user approval

1. Approve or reject each candidate source individually, including whether CC BY-SA sources are acceptable after legal review.
2. Decide whether to proceed with a legal/provenance review of IndicCorpV2 and whether to exclude it from the first experiment due to its scale and web-derived privacy risks.
3. Approve Python documentation as the first technical-text source, with a pinned release and its required notices.
4. Approve whether to commission original Hinglish examples, the author-consent/rights process, and the intended script/code-switch style.
5. Set the relative priority of English, Hindi-Devanagari, Hinglish-Roman, and technical/code. Until then, no final sampling percentages are set.
6. Approve the proposed SentencePiece BPE + byte-fallback tokenizer comparison and the candidate vocabulary experiments; no tokenizer is trained in this phase.
7. Define the evaluation tasks, who may author/review them, and who can access the final sealed test set.
8. Approve retention and access rules for raw source snapshots, attribution/provenance records, and quarantined privacy matches.
9. Decide whether source license and model-weight distribution questions require counsel before any corpus collection. Recommendation: yes.
10. Separately authorize dependencies, downloads, tokenizer training, model training, and hardware measurement work when ready. None is authorized by this planning document.
11. Approve the evaluation baseline and numeric pass/fail thresholds for each language, readability/coherence, repetition/incoherence, task performance, safety, privacy, and unsupported factual claims before training.

## 13. References

1. Python Software Foundation, *History and License*: https://docs.python.org/3/license.html
2. Wikimedia Dumps, *License information*: https://dumps.wikimedia.org/legal.html
3. Creative Commons, *Attribution-ShareAlike 4.0 International*: https://creativecommons.org/licenses/by-sa/4.0/
4. Wikimedia Dumps, data-download formats and XML-dump sunset notice: https://dumps.wikimedia.org/
5. AI4Bharat, [IndicCorpV2 dataset card](https://huggingface.co/datasets/ai4bharat/IndicCorpV2); Doddapaneni et al., [ACL 2023 IndicCorp paper](https://aclanthology.org/2023.acl-long.693/)
6. Meta, [FLORES-200 dataset card](https://huggingface.co/datasets/facebook/flores)
7. Google SentencePiece, [project README](https://github.com/google/sentencepiece)
8. Google SentencePiece, [training options](https://github.com/google/sentencepiece/blob/master/doc/options.md)
