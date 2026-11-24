# Veronica Phase 1D: Decisions and Approval Matrix

**Project:** Veronica — Native AI Development
**Status:** Planning only
**Purpose:** Record confirmed directions, non-binding recommendations, and decisions still requiring the user's explicit approval before future work.

## 1. Decision status and authority

- **Confirmed** means an explicit direction in the user's instructions or the Phase 1A approval audit. It does not authorize implementation, data acquisition, installation, or training.
- **Pending** means no final user decision is recorded. Recommendations remain advice, not approval.
- **Not authorized** means an operation is explicitly outside the current approval. It remains prohibited until separately authorized.
- **User's final decision** records only what has actually been stated. “Not provided” is intentional; no approval is inferred from a recommendation, a source license, a test result, or the Phase 1A architecture approval.

This matrix consolidates decisions in the [Phase 1B foundation plan](PHASE_1B_NATIVE_AI_FOUNDATION_PLAN.md), the [Phase 1C data and evaluation plan](PHASE_1C_DATA_EVALUATION_FOUNDATION_PLAN.md), and the [Phase 1A independent approval audit](PHASE_1A_INDEPENDENT_APPROVAL_AUDIT.md). Phase 1A approved application/orchestration boundaries; it did not approve another implemented provider, a model, data use, or a training operation.

## 2. Confirmed directions

### DEC-01 — Equal language priority

- **Topic:** Relative priority and separate reporting for the target languages.
- **Available options and trade-offs:**
  - Give English, Hindi (Devanagari), and Hinglish (Roman Hindi) equal priority — preserves the user's explicit direction; actual source volumes and data quality may still differ.
  - Rank one language above another — could simplify short-term data allocation, but conflicts with the confirmed requirement.
- **Recommendation:** Keep the three language priorities equal. Maintain separate approved-data inventory, training/validation/test evaluation, and quality reports for each language. Equal priority does **not** imply equal sampling percentages.
- **Risks and dependencies:** Source availability, clean/licensed data volume, and tokenizer fertility may differ. Measure them independently before proposing a sampling schedule; do not fill a language quota by duplicating a small corpus.
- **Approval status:** **Confirmed by user** for equal priority; exact sampling ratios remain pending under DEC-07.
- **User's final decision:** **English: Equal priority. Hindi (Devanagari): Equal priority. Hinglish (Roman Hindi): Equal priority. No ranking among the three.**

### DEC-02 — First model provenance and goal

- **Topic:** Whether Veronica's first native language model is trained from scratch or based on another model.
- **Available options and trade-offs:**
  - Train the first tiny educational model from scratch — satisfies the approved learning direction and avoids inherited pretrained weights; likely produces limited capability and depends on approved data, tokenizer, compute, and evaluation.
  - Start from an externally pretrained model — may improve initial capability, but does not meet the stated first-model-from-scratch direction and would make generation depend on external weights.
- **Recommendation:** Follow the confirmed from-scratch direction for the first tiny model. A lower training loss or provider abstraction must not be presented as evidence of assistant-level intelligence.
- **Risks and dependencies:** Dataset rights, language balance, architecture, compute, and evaluation are unresolved. The first model may be a toy prototype, not a useful general assistant.
- **Approval status:** **Confirmed direction only.** Training work itself is not authorized (see DEC-19).
- **User's final decision:** **The first tiny model is to be trained from scratch. Veronica's native final-answer generation must not depend on Ollama or another pretrained AI model.**

## 3. Decision register

| ID | Topic | Approval status |
|---|---|---|
| DEC-01 | Equal language priority | Confirmed; sampling ratios pending |
| DEC-02 | First model trained from scratch | Confirmed direction; execution unauthorized |
| DEC-03 | Temporary pretrained research baseline | Pending |
| DEC-04 | Data-source selection | Pending; no source approved |
| DEC-05 | Licensing and legal review | Pending |
| DEC-06 | Privacy, personal data, and contributor consent | Guardrails confirmed; future opt-in/retention decisions pending |
| DEC-07 | Corpus mixture and sampling ratios | Pending; no percentages approved |
| DEC-08 | Split assignment and leakage controls | Recommendation recorded; final dataset policy pending |
| DEC-09 | Dataset/checkpoint storage and retention | Pending |
| DEC-10 | Tokenizer method and vocabulary | Candidate recommended; implementation decision pending |
| DEC-11 | Model architecture, size, and training objective | From-scratch goal confirmed; design pending |
| DEC-12 | Hardware and compute budget | Pending; several hardware facts unknown |
| DEC-13 | Dependencies and training toolchain | Pending; installation unauthorized |
| DEC-14 | Evaluation set, baseline, and pass/fail gates | Pending; numeric thresholds not approved |
| DEC-15 | Knowledge retrieval and memory scope | Pending |
| DEC-16 | Inference runtime versus custom engine | Pending |
| DEC-17 | API, network access, and deployment | Pending |
| DEC-18 | Native-provider release, default switch, and Ollama fallback | Pending |
| DEC-19 | Training and data-operation authorization | Not authorized |

## 4. Detailed decision records

### DEC-03 — Temporary pretrained research baseline

- **Topic:** Whether a pretrained external model may be used for comparison during research.
- **Available options and trade-offs:**
  - Do not use a pretrained baseline — strongest separation from external models and no baseline-model licensing/download dependency; makes capability comparisons harder.
  - Use a separately approved, temporary model only for non-production comparison — can provide a reference for task scores or interaction design; requires model/license review and may blur the independence boundary.
  - Use a pretrained model for final native answers — may provide stronger responses sooner, but directly conflicts with the confirmed native-answer-generation requirement.
- **Recommendation:** Do not use a baseline unless the user separately approves it. Never treat a temporary baseline as Veronica's native final-answer engine.
- **Risks and dependencies:** A baseline may require model downloads, extra dependencies, Internet access, and review of model and output terms. None is approved by this matrix.
- **Approval status:** **Pending** for temporary research use; use for final native generation is not an available approved option.
- **User's final decision:** **Not provided.**

### DEC-04 — Data-source selection

- **Topic:** Which exact source revisions may be acquired and used for training or evaluation.
- **Available options and trade-offs:**
  - **Python documentation:** explicit PSF licensing terms make it a promising, narrow English technical candidate; low subject/language breadth and exact revision/notice requirements remain. No collection is approved.
  - **Wikimedia English/Hindi:** broad language coverage; source-specific GFDL/CC BY-SA terms, attribution, privacy, exceptions, and possible problematic content require review. No collection is approved.
  - **IndicCorpV2:** may provide Hindi/Indic breadth and its dataset card declares CC0; exact revision/statistics, underlying third-party rights, privacy, and corpus quality require verification. No collection is approved.
  - **FLORES-200:** a small multilingual benchmark candidate for evaluation only; access conditions, CC BY-SA terms, and test-set integrity apply. It is not approved for training or tokenizer fitting.
  - **Newly authored/commissioned Hinglish examples:** can target Roman Hindi and code-switching; requires author consent, rights, quality review, and enough independent material to keep training separate from final evaluation. No commissioning or authoring is approved.
  - **Other public or scraped sources, including books and code collections:** may add volume, but public availability does not establish training rights, privacy, or compatibility with weight distribution. Do not select without source-specific review.
- **Recommendation:** Review and approve each exact source/revision separately. Keep FLORES evaluation-only. Do not treat any candidate in the Phase 1C plan as already selected or authorized.
- **Risks and dependencies:** Rights, source formats, version drift, personal information, attribution, licensing, and evaluation contamination vary by source. IndicCorpV2 statistics in different releases/representations must not be assumed interchangeable; pin and verify the exact revision.
- **Approval status:** **Pending. No data source is approved for acquisition or use.**
- **User's final decision:** **Not provided for any source.**

### DEC-05 — Licensing and legal review

- **Topic:** How source licenses, dataset terms, attribution duties, and model/checkpoint distribution will be cleared.
- **Available options and trade-offs:**
  - Rely on a visible dataset-card/license declaration — faster to assess, but may not cover underlying content, third-party rights, jurisdiction, privacy, or model-weight distribution.
  - Perform documented source/revision-level legal review before use — slower, but better addresses provenance, attribution, permitted purposes, derivative-data handling, and distribution.
  - Exclude sources whose terms or provenance remain unclear — reduces legal exposure but limits corpus choice and volume.
- **Recommendation:** Require a documented legal/source review before using ambiguous, share-alike, web-derived, or third-party content. Treat CC0 as a dataset-level declaration, not automatic resolution of every underlying rights/privacy question.
- **Risks and dependencies:** Legal conclusions depend on jurisdiction, source revision, intended training and distribution, and specific content. Attribution metadata must remain linked to derived records.
- **Approval status:** **Pending.**
- **User's final decision:** **Not provided.**

### DEC-06 — Privacy, personal data, and contributor consent

- **Topic:** Permitted personal data, opt-in content, screening, and withdrawal.
- **Available options and trade-offs:**
  - Exclude personal conversations and memories entirely — strongest privacy boundary; removes a possible source of personalized examples.
  - Permit only separately and explicitly consented items under a revocable process — may permit additional data, but requires consent records, deletion lineage, access controls, and a policy for already-trained checkpoints.
  - Automatically include conversations or SQLite memories — easiest technically, but violates the stated privacy guardrails and is not acceptable under the current direction.
- **Recommendation:** Maintain the confirmed default exclusions: never automatically use personal conversations or SQLite memories; exclude passwords, API keys, credentials, and private information. Do not introduce an opt-in path without separate approval and documented retention/revocation rules.
- **Risks and dependencies:** Automated secret/PII detection is incomplete. Source-derived PII needs separate screening; removal from future datasets cannot prove removal of influence from an existing checkpoint.
- **Approval status:** **Guardrails confirmed; any future opt-in, retention, and revocation policy is pending.**
- **User's final decision:** **No automatic conversation or SQLite-memory training; exclude credentials/private information. Broader opt-in policy not provided.**

### DEC-07 — Corpus mixture and sampling ratios

- **Topic:** How approved data will be sampled for training while preserving equal priority.
- **Available options and trade-offs:**
  - Sample in proportion to approved corpus size — reflects source availability, but a large English source could dominate.
  - Use language-stratified/capped sampling — can prevent one language from overwhelming another, but may repeatedly sample a small corpus or reduce diversity if quotas are too aggressive.
  - Use a measured hybrid schedule — can cap source dominance while respecting data quality and volume, but requires language-specific inventory and experiments first.
- **Recommendation:** Inventory and quality-review approved data first; then compare natural and balanced/capped token mixtures without duplicating scarce data. Report English, Hindi-Devanagari, and Hinglish-Roman separately.
- **Risks and dependencies:** Equal priority is not equal corpus size or equal sampling percentage. Ratios depend on approved sources, unique document counts, quality, and tokenizer fertility.
- **Approval status:** **Pending. No sampling percentages are approved.**
- **User's final decision:** **Not provided.**

### DEC-08 — Dataset splits and leakage controls

- **Topic:** Final split groups, ratios, and independent language-specific evaluation sets.
- **Available options and trade-offs:**
  - Random row/line splits — simple, but can leak related passages, paraphrases, revisions, translations, or duplicated material across splits.
  - Source/document/duplicate-cluster splits with frozen tests — better estimates generalization and protects held-out examples; requires provenance and enough independent examples.
- **Recommendation:** Use document/source and duplicate-cluster grouping, exact and near-duplicate checks, and held-out templates. Maintain separate train/validation/sealed-test manifests for English, Hindi-Devanagari, and Hinglish-Roman. Never fit the tokenizer or train the model on final-test examples. Do not reuse the same small authored Hinglish collection for training and final evaluation.
- **Risks and dependencies:** Source lineage and near-duplicate detection must exist before assignment. Fixed split percentages cannot be responsibly chosen until corpus size and independent groups are known.
- **Approval status:** **Pending final dataset-policy approval; leakage controls are planning recommendations.**
- **User's final decision:** **Not provided.**

### DEC-09 — Dataset and checkpoint storage, access, and retention

- **Topic:** Where raw sources, derived datasets, manifests, attribution records, checkpoints, and evaluation keys may be stored and who may access them.
- **Available options and trade-offs:**
  - Local-only, access-controlled storage — supports offline/privacy goals, but depends on unknown free disk and backup capability.
  - Approved external/cloud storage — may provide capacity and backup, but introduces network, provider, access-control, and data-processing risks.
  - Publish or share artifacts — improves reproducibility, but only where every source license, privacy obligation, and checkpoint distribution condition permits it.
- **Recommendation:** Decide retention, access, backup, and distribution separately for raw, normalized, tokenized, evaluation, and checkpoint artifacts. Keep attribution/provenance separate from model input and protect sealed evaluation data.
- **Risks and dependencies:** Available disk and RAM are unknown. Source withdrawal requires lineage; do not claim a trained model has forgotten removed data.
- **Approval status:** **Pending.**
- **User's final decision:** **Not provided.**

### DEC-10 — Tokenizer method and vocabulary

- **Topic:** Tokenizer algorithm, fallback policy, special tokens, and vocabulary size.
- **Available options and trade-offs:**
  - SentencePiece BPE with byte fallback — recommended candidate for robust Unicode handling and deterministic merges; Hindi/Hinglish token fertility and model embedding cost need measurement.
  - Unigram subword model — supports probabilistic segmentation/regularization; adds segmentation choices to validate.
  - Other byte-level BPE implementation — broad valid UTF-8 coverage; may fragment underrepresented scripts and requires its own compatible implementation.
- **Recommendation:** Keep SentencePiece BPE with byte fallback as a candidate, not an implementation decision. Compare token fertility, round-trip coverage, fallback rate, and embedding cost on approved training data only.
- **Risks and dependencies:** Vocabulary consumes model parameters. As illustrated in Phase 1C, 8,192 entries × 256 hidden dimensions is 2,097,152 parameters for one matrix; separate input/output matrices may cost more. Select vocabulary size only after architecture, hidden dimension, and total parameter budget are approved.
- **Approval status:** **Pending. No tokenizer or vocabulary size is approved for training.**
- **User's final decision:** **Not provided.**

### DEC-11 — Model architecture, scale, and training objective

- **Topic:** Architecture and parameter budget for the first tiny from-scratch language model, and whether/when to add assistant instruction tuning.
- **Available options and trade-offs:**
  - Tiny decoder-only next-token model — aligns with the Phase 1B educational proposal and supports autoregressive generation; likely limited capability and must be sized against data and hardware.
  - Other architecture/objective — may suit a different task, but increases design/evaluation complexity and may not match the answer-generation goal.
  - Add instruction tuning later using Veronica's own checkpoint — may improve task formatting/following; requires separately approved examples and does not guarantee assistant-level capability.
- **Recommendation:** Treat a tiny decoder-only causal LM as a candidate for the first educational experiment, not an approved architecture or parameter count. Choose model size only after data inventory, tokenizer, hidden dimension/vocabulary cost, hardware measurements, and evaluation criteria are settled.
- **Risks and dependencies:** Dataset size/quality, tokenizer vocabulary, memory, sequence length, training stack, and 6 GB VRAM constrain design. No scale or quality target is justified yet.
- **Approval status:** **From-scratch first-model direction confirmed; architecture, scale, objective details, and instruction-tuning scope pending.**
- **User's final decision:** **First tiny model from scratch; specific architecture/size and later tuning plan not provided.**

### DEC-12 — Hardware and compute budget

- **Topic:** Laptop-only development versus any future external compute, and which hardware facts will gate a run.
- **Available options and trade-offs:**
  - Laptop-only experiments — keeps data/local control and cost bounded; 6 GB VRAM, Windows, and unknown CPU/RAM/disk/driver/thermal limits constrain what can be tested.
  - Propose external/cloud compute after a tiny feasibility study — can expand capacity; requires budget, privacy, network, storage, and deployment approvals.
- **Recommendation:** Do not commit to model scale or schedule before measuring the actual system. First confirm CPU, RAM, free disk, driver/CUDA compatibility, and thermals; any external compute requires separate approval.
- **Risks and dependencies:** Only Windows, RTX 3050 Laptop GPU with 6 GB VRAM, and Python 3.14.5 are confirmed in the plans. No performance benchmark is available.
- **Approval status:** **Pending.**
- **User's final decision:** **Not provided regarding laptop-only limits or external-compute allowance.**

### DEC-13 — Dependencies and training toolchain

- **Topic:** Whether to add Python packages, native runtimes, or other tools for dataset, tokenizer, and training work.
- **Available options and trade-offs:**
  - Keep current dependencies and use only already available tooling — no installation risk; current manifest lacks a model-training/tokenizer stack.
  - After approval, evaluate compatible tokenizer/training/runtime options — enables a reproducible experiment; compatibility, licensing, Windows/Python 3.14.5 wheels, and CUDA support must be checked.
- **Recommendation:** Perform a compatibility investigation only after authorization; add no package until an approved design requires it and compatibility is verified.
- **Risks and dependencies:** Python 3.14.5 and CUDA compatibility are unverified for candidate ML libraries. Dependency approval does not imply dataset/model download approval.
- **Approval status:** **Pending; package installation is not authorized.**
- **User's final decision:** **Not provided.**

### DEC-14 — Evaluation set, baseline, and pass/fail gates

- **Topic:** Evaluation material, scoring, baselines, acceptance criteria, and failure reporting before training.
- **Available options and trade-offs:**
  - Use only language-model metrics — reproducible and direct for next-token learning; insufficient for comprehension, reasoning, readability, factual support, privacy, or safety.
  - Use language-model metrics plus separate human-reviewed task evaluation — broader evidence across English, Hindi-Devanagari, and Hinglish-Roman; requires independently sourced/authored sets, reviewers, and data isolation.
- **Recommendation:** Approve and freeze per-language evaluation sets and a baseline before training; separately set numeric minimums for each language, readability/coherence, comprehension/reasoning, safety/privacy, repetition/incoherence, and unsupported factual claims. Report each language and task separately, all failed gates, limitations, and uncertainty.
- **Risks and dependencies:** Public benchmarks can contaminate training. Thresholds cannot be responsibly invented before the evaluation set and baseline are approved and measured. An external model baseline requires DEC-03 approval.
- **Approval status:** **Pending. No baseline, numeric threshold, or final evaluation set is approved.**
- **User's final decision:** **Not provided.**

### DEC-15 — Knowledge retrieval and memory scope

- **Topic:** Which local knowledge sources, retrieval mechanisms, and personal-memory uses should accompany native generation.
- **Available options and trade-offs:**
  - First model without document retrieval — simplest separation of learned language behavior; factual knowledge remains limited to training and context.
  - Add local, provenance-aware document retrieval — can ground answers in approved current sources; requires source rights, indexing, update/deletion policy, and separate storage.
  - Add online web retrieval — can supply current evidence; requires network/API approvals and privacy controls for queries.
- **Recommendation:** Keep personal SQLite memory separate from training and document knowledge. If retrieval is later approved, pass bounded source-attributed evidence to the native model; the native model, not an external LLM, generates the final answer.
- **Risks and dependencies:** No document knowledge system exists. Data rights, stale-source handling, citations, privacy, and offline behavior are unresolved.
- **Approval status:** **Pending.**
- **User's final decision:** **Not provided.**

### DEC-16 — Inference runtime versus custom engine

- **Topic:** Whether Veronica initially uses a compatible lightweight runtime to execute its own weights or builds and owns an inference engine.
- **Available options and trade-offs:**
  - Use a compatible lightweight runtime with Veronica-trained weights — reduces engine-building scope; constrains formats/architectures and does not mean Veronica owns the engine.
  - Build a custom inference engine — offers deeper control; substantially increases implementation, correctness, and maintenance burden.
- **Recommendation:** The Phase 1B plan recommends deferring a custom engine until a native checkpoint and measured bottleneck exist; this is not an approval to select or install a runtime.
- **Risks and dependencies:** Compatibility with model format, tokenizer, Windows, GPU, and chosen architecture is unknown. Model-weight ownership and inference-engine ownership are separate goals.
- **Approval status:** **Pending.**
- **User's final decision:** **Not provided.**

### DEC-17 — API, network access, and deployment

- **Topic:** Local API/server scope, remote/cloud operation, external services, and offline guarantees.
- **Available options and trade-offs:**
  - Embedded/local-only inference and no server initially — smaller attack surface and supports offline use; limits clients and concurrent access.
  - Loopback-only local API — enables desktop/web clients on the same machine; requires request/resource limits and API design.
  - Remote/cloud service — enables remote access and scaling; requires authentication, authorization, TLS, privacy/data-transfer rules, operations budget, and security review.
- **Recommendation:** If separately authorized later, begin loopback-only and preserve offline native generation. Treat retrieval, online TTS, cloud deployment, and remote access as independent opt-in capabilities.
- **Risks and dependencies:** The repository has no API/server. Public exposure creates security, privacy, abuse, availability, and cost risks.
- **Approval status:** **Pending. No server, network feature, or cloud deployment is authorized.**
- **User's final decision:** **Not provided.**

### DEC-18 — Native-provider release, default switch, and Ollama fallback

- **Topic:** When Veronica's provider may become the default and what happens to Ollama.
- **Available options and trade-offs:**
  - Keep Ollama as the default while native work remains experimental — preserves current functionality; native usage requires explicit opt-in after implementation.
  - Switch the default only after approved quality, privacy, safety, offline, reliability, and resource gates pass — advances the native system; requires measured evidence and explicit approval.
  - Remove Ollama immediately — would remove the current working provider before a native model exists and is not justified.
- **Recommendation:** Retain Ollama unchanged until a Veronica-trained provider passes DEC-14 and the user explicitly approves a default change. Preserve a documented fallback/rollback path.
- **Risks and dependencies:** Phase 1A approved provider-independent application/orchestration boundaries, not multiple implemented providers. Ollama is currently the only complete provider; `VeronicaModelProvider` is a scaffold.
- **Approval status:** **Pending. No default change or Ollama removal is authorized.**
- **User's final decision:** **Not provided beyond the requirement that Veronica's eventual native final answers use its own model.**

### DEC-19 — Authorization for collection, training, and implementation

- **Topic:** The operational gate for turning plans into data collection or code/model work.
- **Available options and trade-offs:**
  - Keep the current planning-only state until each required approval is recorded — prevents accidental collection, dependency changes, or training before governance is ready.
  - Authorize a specific next phase with named sources, data policy, toolchain, hardware, and acceptance gates — enables bounded progress while preserving reviewability.
- **Recommendation:** Require explicit approval of the applicable gates before each operation. Approval of a high-level from-scratch direction is not approval to collect data, install tools, train, or change the application.
- **Risks and dependencies:** Operations can create privacy, license, cost, compatibility, or irreproducibility consequences. Authorization must be scoped and recorded.
- **Approval status:** **Not authorized under the current planning-only request.**
- **User's final decision:** **No implementation, downloads, installations, tokenizer training, or model training has been authorized.**

## 5. Separate approval gates

Every gate below is independent. A recommendation, confirmed direction, or pass at one gate does not grant approval at another.

| Gate | Decision record | Current status | Minimum evidence/decision needed before proceeding |
|---|---|---|---|
| Language priorities | DEC-01 | **Confirmed:** equal priority for all three languages | Keep data inventory, training/evaluation results, and quality reporting separate. Sampling percentages remain unapproved. |
| Data sources | DEC-04 | **Pending** | Approve exact source, revision, purpose (training/evaluation), and source-specific constraints. No source download/use currently approved. |
| Licensing and legal review | DEC-05 | **Pending** | Document rights, attribution, permitted training and distribution, and any counsel review. |
| Privacy and consent | DEC-06 | **Guardrails confirmed; extensions pending** | Retain automatic exclusions; separately approve any opt-in personal-data use, author consent, screening, withdrawal, and deletion policy. |
| Dataset splits/leakage | DEC-08 | **Pending** | Approve group assignment and sealed, language-specific test-set rules, including tokenizer-fit exclusion. |
| Storage and retention | DEC-09 | **Pending** | Approve local/external storage, access, retention, backup, deletion, and artifact distribution policies. |
| Tokenizer | DEC-10 | **Pending** | Approve algorithm candidate, training data, compatibility/versioning rules, and vocabulary only after model architecture/budget. |
| Model architecture | DEC-11 | **Pending** | Approve architecture, parameter/hidden-size budget, sequence length, training objective, and any own-checkpoint tuning scope. |
| Hardware/compute | DEC-12 | **Pending** | Verify missing machine facts and approve laptop-only or separately budgeted external compute. |
| Dependencies/toolchain | DEC-13 | **Pending** | Approve compatibility investigation and each dependency/runtime installation separately. |
| Evaluation | DEC-14 | **Pending** | Approve the evaluation set, baseline, human rubric, per-language metrics, and numeric pass/fail thresholds before training. |
| Knowledge/retrieval | DEC-15 | **Pending** | Approve local/online sources, indexing, attribution, and memory boundaries. |
| Inference runtime | DEC-16 | **Pending** | Approve runtime ownership approach after architecture/model-format compatibility is known. |
| API/network/deployment | DEC-17 | **Pending** | Approve local server, network capabilities, data handling, and any remote/cloud exposure separately. |
| Native default/release | DEC-18 | **Pending** | Require evidence against approved gates and explicit user approval before changing default or fallback. |
| Data/model operations | DEC-19 | **Not authorized** | Explicitly authorize a bounded phase after prerequisite gates; no current operational approval exists. |

## 6. Confirmed language reporting policy

| Language | Priority | Inventory and reporting rule |
|---|---|---|
| English | **Equal priority** | Inventory approved data separately; report its training, validation, sealed-test, and quality metrics separately. |
| Hindi (Devanagari) | **Equal priority** | Inventory approved data separately; report its training, validation, sealed-test, and quality metrics separately. |
| Hinglish (Roman Hindi) | **Equal priority** | Inventory approved data separately; report its training, validation, sealed-test, and quality metrics separately. |

No language is ranked above another. Equal priority means each language must have visible evidence and its own approved quality criteria; it does not mean equal data volume, equal sampling percentages, or that unavailable data may be duplicated.

## 7. Exactly what remains unauthorized

As of this planning matrix, none of the following is authorized:

1. Acquiring, downloading, scraping, or processing any dataset, including the candidate sources in DEC-04.
2. Using a source for training, tokenizer fitting, or evaluation before its exact revision, license, privacy conditions, and purpose are approved.
3. Commissioning, collecting, or reusing Hinglish examples across training and sealed final evaluation.
4. Downloading, installing, or using a pretrained model as a research baseline or final-answer generator.
5. Installing or upgrading packages, adding a training/tokenizer/runtime dependency, or changing project configuration.
6. Training or fitting a tokenizer, including vocabulary selection or tokenizer preprocessing on validation/test material.
7. Training, fine-tuning, evaluating as a production release, exporting, or deploying any Veronica model checkpoint.
8. Running a hardware/training benchmark or committing to an architecture, vocabulary size, parameter count, training scale, or schedule.
9. Modifying application source, tests, dependencies, or configuration; changing provider startup/default behavior; or removing/replacing Ollama.
10. Building a knowledge index, enabling external retrieval/TTS/network features, or creating an API/server, cloud deployment, or remote endpoint.
11. Committing or pushing repository changes.

Only the documentation work that creates this decision matrix is within the current planning scope. Confirmed priorities and the from-scratch model direction do not override these restrictions.
