# Veronica Phase 1F: Model Architecture and Parameter Budget Plan

**Status:** Planning only
**Authorization:** Documentation and read-only technical research only
**Scope:** No model source code, tokenizer, dataset, package, benchmark, or training run is created or authorized by this plan.

## 1. Executive summary

This plan compares small, decoder-only Transformer configurations that could be trained from random initialization for Veronica's first educational language-model experiment. A causal decoder is a reasonable candidate because it predicts the next token and can generate a response autoregressively. It is not a selected architecture, and parameter counts, vocabulary, context, training precision, optimizer, and objective details remain pending user approval.

The comparison uses illustrative configurations close to 1M, 5M, 10M, and 25M total parameters. Under the explicit counting convention in §3, the examples total 1,004,256; 4,891,392; 10,067,456; and 24,739,968 parameters. They use tied input/output token embeddings to contain vocabulary cost. Different choices such as untied output weights, rotary rather than learned positions, biases, or another feed-forward design change those counts.

All three target languages—English, Hindi (Devanagari), and Hinglish (Roman Hindi)—have equal priority. An architecture or tokenizer does not guarantee equal quality. Future data inventories, tokenization-fertility measures, evaluation sets, and quality reports must remain separate for each language; no equal sampling percentages are implied.

The memory calculations show parameter state only, not whether a model will fit or train usefully on the RTX 3050. For the 25M example, the FP32 Adam baseline is about 377.5 MiB before activations, attention workspaces, framework/runtime memory, and other GPU use. No configuration is promised to fit the 6 GB GPU without measurement. This comparison selects no final parameter budget and sets no pass/fail thresholds.

## 2. Scope and prior decisions

- **Confirmed direction:** Veronica's first tiny language model is to be trained from scratch, and Veronica's eventual native final answers must not depend on Ollama or another pretrained AI model.
- **Confirmed language priority:** English, Hindi (Devanagari), and Hinglish (Roman Hindi) are equal priority. No language is ranked above another.
- **Not approved:** Any particular architecture, tokenizer, data source, parameter count, layer/head configuration, context length, precision, optimizer, evaluation threshold, dependency, or training operation.
- **Integration boundary:** Phase 1A approved provider-neutral application/orchestration seams. It did not create a native model or authorize changing the existing Ollama setup.
- **Hardware facts:** The Phase 1E plan records the Intel Core i5-13420H, 16 GB RAM, Windows 11 64-bit, RTX 3050 Laptop GPU with 6,144 MiB VRAM, and Python 3.14.5. Framework/device execution, sustained throughput, and thermal behavior remain unverified.

The records in the [Phase 1D approval matrix](PHASE_1D_DECISIONS_AND_APPROVAL_MATRIX.md) and [Phase 1E feasibility plan](PHASE_1E_TECHNICAL_FEASIBILITY_PLAN.md) remain in force. Examples below are arithmetic exercises only.

## 3. Decoder-only Transformer components

An illustrative decoder-only model is a stack of causal Transformer blocks. At each position, it receives the prefix tokens and predicts a distribution over the next token. It is initialized randomly for the stated from-scratch goal; it does not inherit pretrained model weights.

1. **Token embeddings:** Map each token ID in a vocabulary of size \(V\) to a learned vector of width \(d\). The input matrix has \(Vd\) parameters.
2. **Positional information:** Self-attention alone does not encode token order. A model can add a learned absolute position vector at each of \(C\) positions, costing \(Cd\) parameters, or use a parameter-free positional method such as rotary position embeddings (RoPE) applied to query/key vectors. Learned positions impose a configured maximum table length; rotary methods avoid that table but have their own implementation and extrapolation behavior. Neither is selected here.
3. **Self-attention:** Each hidden vector is projected to query \(Q\), key \(K\), and value \(V_a\) vectors. Attention compares queries to keys, scales the scores, applies a causal mask and softmax, then combines values. The mask prevents a position from using future tokens during training or generation.
4. **Multi-head attention:** Several attention heads operate on subspaces of the hidden width. With \(h\) heads, each head has width \(d_h=d/h\) when \(d\) is divisible by \(h\). Head count changes how the features are partitioned and memory/workspace shapes; for fixed total width \(d\), it does not by itself change the dense projection parameter count.
5. **Feed-forward network (FFN):** A position-wise MLP expands each \(d\)-wide vector to an intermediate width \(f\), applies a nonlinearity such as GELU, then projects back to \(d\). It contributes much of each block's parameters and compute.
6. **Layer normalization:** Normalizes hidden activations and usually has learned scale and bias parameters. The arithmetic convention below uses two affine LayerNorms per block plus a final affine LayerNorm.
7. **Residual connections:** Add a block's input to its attention or FFN result. They provide a direct signal path through depth; residual paths do not add trainable parameters in this convention.
8. **Output projection / language-model head:** Converts the final \(d\)-wide state to \(V\) vocabulary logits. The examples tie this matrix to the input token embedding, so the output projection adds no second \(Vd\) matrix. Tying is only a counting assumption, not a decision.
9. **Autoregressive generation:** Select or sample a token from the next-token distribution, append it to the prefix, and repeat until a stopping rule or context limit. This describes generation mechanics, not instruction-following or factual reliability.

### Justified small-model alternatives

| Candidate | Potential advantage | Trade-off for Veronica's first from-scratch text generator |
|---|---|---|
| **Decoder-only causal Transformer** | Direct next-token objective and natural autoregressive text generation; token positions within a batch can be trained in parallel subject to the causal mask. | Attention memory and compute grow with sequence length; small parameter count does not guarantee useful language or safe assistant behavior. |
| **GRU/LSTM language model** | Recurrent architecture can be a compact educational baseline and does not materialize a full self-attention score matrix. | Sequential recurrence reduces training parallelism; long-range information and generation quality remain limited at tiny scales. It is a different architecture, not a drop-in Transformer configuration. |
| **Encoder-only masked-language model** | Bidirectional context can be useful for representation and classification tasks. | Masked-token prediction is not a direct left-to-right generation objective; producing final answers would require a different generation design. |
| **Encoder-decoder Transformer** | Explicit source-to-target generation can suit translation or conditioned transformations. | Two stacks and cross-attention add design and parameter-budget choices; it is not needed to compare a simple causal language model. |
| **State-space/linear-attention variants** | Some designs aim to reduce long-sequence cost. | Adds algorithm/kernel and implementation choices; no need has been established for the first tiny experiment. |

**Recommendation:** Use a decoder-only causal Transformer as the reference architecture for comparing budgets, while keeping recurrent and encoder-decoder alternatives visible as research choices. Do not treat the recommendation as approval to implement or train any architecture.

## 4. Parameter-counting convention and equations

The examples use a deliberately explicit, GPT-like counting convention:

- \(L\) decoder blocks, hidden width \(d\), \(h\) attention heads, FFN width \(f\), vocabulary \(V\), and context length \(C\);
- learned absolute position embeddings;
- combined dense Q/K/V projection and dense attention-output projection, each with bias;
- two dense FFN layers with biases;
- two affine LayerNorms per block and one final affine LayerNorm;
- tied input token embeddings and output projection; no output-head bias;
- no other trainable parameters (for example, dropout has no parameters).

For one block:

\[
\begin{aligned}
P_{\mathrm{attn}} &= 3(d^2+d)+(d^2+d)=4d^2+4d,\\
P_{\mathrm{ffn}} &= (df+f)+(fd+d)=2df+f+d,\\
P_{\mathrm{norms}} &= 2(2d)=4d,\\
P_{\mathrm{block}} &= 4d^2+2df+9d+f.
\end{aligned}
\]

With tied embeddings and learned positions:

\[
P_{\mathrm{total}} = Vd + Cd + L(4d^2+2df+9d+f)+2d.
\]

The final \(2d\) is the final LayerNorm scale and bias. The output projection uses the same \(Vd\) token matrix, so it is not counted twice. If input/output embeddings are untied, add \(Vd\) parameters (and add \(V\) more if an output bias is used). If RoPE replaces learned positions, remove the \(Cd\) learned position-table parameters. Other normalization, bias, or FFN choices also change the result.

## 5. Illustrative parameter-budget configurations

These are **possible configurations for comparison only**. All use context length 256 and the parameter-counting convention in §4. The vocabulary choices are arithmetic examples, not tokenizer recommendations. The modest differences from the round-number budgets are intentional; no final parameter count is selected.

| Approximate budget | Layers \(L\) | Hidden \(d\) | Heads \(h\) | Head width \(d/h\) | FFN \(f\) | Vocabulary \(V\) | Context \(C\) | Input/tied embedding \(Vd\) | Learned positions \(Cd\) | Parameters per block | Total parameters |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1M | 7 | 96 | 4 | 24 | 384 | 2,048 | 256 | 196,608 | 24,576 | 111,840 | **1,004,256** |
| 5M | 10 | 192 | 6 | 32 | 768 | 2,048 | 256 | 393,216 | 49,152 | 444,864 | **4,891,392** |
| 10M | 12 | 256 | 8 | 32 | 1,024 | 2,048 | 256 | 524,288 | 65,536 | 789,760 | **10,067,456** |
| 25M | 13 | 384 | 8 | 48 | 1,536 | 4,096 | 256 | 1,572,864 | 98,304 | 1,774,464 | **24,739,968** |

### Auditable total-parameter sums

| Budget example | Calculation | Total |
|---|---|---:|
| 1M | \(196{,}608 + 24{,}576 + 7 \times 111{,}840 + 192\) | 1,004,256 |
| 5M | \(393{,}216 + 49{,}152 + 10 \times 444{,}864 + 384\) | 4,891,392 |
| 10M | \(524{,}288 + 65{,}536 + 12 \times 789{,}760 + 512\) | 10,067,456 |
| 25M | \(1{,}572{,}864 + 98{,}304 + 13 \times 1{,}774{,}464 + 768\) | 24,739,968 |

The head dimensions are integers, but that does not establish that a given kernel is efficient or supported on the selected runtime. A different vocabulary, untied output matrix, or position method changes the totals; recompute before comparing any future model choices.

## 6. Vocabulary and embedding cost

For a token vocabulary of size \(V\) and hidden width \(d\):

- Input embedding parameters: \(P_{\mathrm{in}}=Vd\).
- Tied output projection: uses the same \(Vd\) matrix, so it adds zero new matrix parameters.
- Untied output projection: adds \(P_{\mathrm{out}}=Vd\), plus an optional \(V\)-parameter bias.
- Thus, the tied token input/output matrix costs \(Vd\); the untied pair costs \(2Vd\) (plus any output bias).

At a fixed hidden width \(d=256\):

| Vocabulary \(V\) | Input/tied matrix \(Vd\) | Untied output matrix (additional) | Tied input/output matrices combined | Untied pair (no output bias) |
|---:|---:|---:|---:|---:|
| 2,048 | 524,288 | 524,288 | 524,288 | 1,048,576 |
| 4,096 | 1,048,576 | 1,048,576 | 1,048,576 | 2,097,152 |
| 8,192 | 2,097,152 | 2,097,152 | 2,097,152 | 4,194,304 |
| 16,384 | 4,194,304 | 4,194,304 | 4,194,304 | 8,388,608 |

For example, \(8{,}192 \times 256 = 2{,}097{,}152\) parameters for one embedding/projection matrix. If input and output matrices are separate, the pair costs 4,194,304 parameters before any output bias. This is a material share of a 1M–25M total budget.

Each FP32 parameter uses 4 bytes for raw weights; FP16/BF16 use 2 bytes. Larger vocabularies therefore increase both parameter count and weight/logit storage. The output layer must also produce \(V\) logits per position, so a larger vocabulary increases output projection compute and temporary logits memory.

For a multilingual model, vocabulary size and training-corpus composition affect how English, Devanagari Hindi, and Romanized Hinglish are segmented:

- More subword entries may make frequent words/morphemes more compact, but consume model capacity and may be allocated unevenly if source data is imbalanced.
- A smaller vocabulary saves embedding/head parameters but can fragment words into more tokens, increasing effective sequence length, context consumption, and attention compute.
- Byte fallback can represent valid Unicode without an unknown character, but underrepresented scripts may require more tokens. It does not ensure the model learns the represented language.
- Vocabulary fitting, tokenizer choice, and sampling must be evaluated using approved training-only material. No language receives a higher priority or guaranteed larger vocabulary share here.

**No tokenizer, vocabulary, tied/untied choice, or language sampling percentage is selected.**

## 7. Memory and compute estimates

### Parameter-state estimates for each configuration

The estimates below use MiB (1 MiB = \(2^{20}\) bytes) and the exact totals in §5.

Assumptions:

- FP32 weights: 4 bytes per parameter.
- FP16/BF16 weights: 2 bytes per parameter.
- FP32 gradients: 4 bytes per parameter.
- Adam moments: two FP32 moment tensors, 8 bytes per parameter.
- Approximate full-FP32 Adam training state: FP32 weights + FP32 gradients + Adam moments = 16 bytes per parameter.

| Example | FP32 weights | FP16/BF16 weights | FP32 gradients | FP32 Adam moments | Approx. FP32 Adam parameter state |
|---|---:|---:|---:|---:|---:|
| 1,004,256 params | 3.831 MiB | 1.915 MiB | 3.831 MiB | 7.662 MiB | 15.324 MiB |
| 4,891,392 params | 18.659 MiB | 9.330 MiB | 18.659 MiB | 37.318 MiB | 74.637 MiB |
| 10,067,456 params | 38.404 MiB | 19.202 MiB | 38.404 MiB | 76.809 MiB | 153.617 MiB |
| 24,739,968 params | 94.375 MiB | 47.188 MiB | 94.375 MiB | 188.751 MiB | 377.502 MiB |

These are separate state components; do not add the FP16 weight column to the FP32-state total as if it were the same training recipe. Mixed-precision training may also keep FP32 master parameters and use implementation-specific gradient/optimizer dtypes. Optimizer implementations can allocate extra temporary buffers. The table excludes activations, attention intermediates, logits, CUDA context, framework/kernel workspaces, allocator fragmentation, data-loader buffers, and display/other-process GPU use. It is not a claim that any configuration fits or trains efficiently on 6 GB VRAM.

### Activation, attention, and inference examples

For comparison only, assume a single sequence (\(B=1\)), the listed context \(T=C=256\), and FP16/BF16 activations:

- One materialized attention score tensor per layer has \(B h T^2\) elements, or \(B h T^2 \times 2\) bytes.
- One FFN intermediate tensor per layer has \(B T f\) elements, or \(B T f \times 2\) bytes.
- A standard multi-head key/value cache across all layers is approximately \(2 L B T d \times 2\) bytes (two tensors, key and value).

| Example | One attention-score tensor per layer | One FFN intermediate per layer | Approx. full-model FP16 KV cache at \(B=1,T=256\) |
|---|---:|---:|---:|
| 1M configuration | 0.500 MiB | 0.188 MiB | 0.656 MiB |
| 5M configuration | 0.750 MiB | 0.375 MiB | 1.875 MiB |
| 10M configuration | 1.000 MiB | 0.500 MiB | 3.000 MiB |
| 25M configuration | 1.000 MiB | 0.750 MiB | 4.875 MiB |

The score and FFN values are per tensor and per layer, not a complete activation budget. Training may retain or recompute multiple activations for backward propagation; multiply relevant activation terms by batch size and account for all layers, residuals, normalization, gradients, and implementation buffers. Fused/Flash attention may avoid storing the full \(T \times T\) score matrix, but availability and memory behavior depend on the exact backend. The KV-cache calculation assumes ordinary multi-head attention without grouped-query reductions; actual cache dtype, layout, allocation, and context limits are runtime-dependent.

For inference, the FP16/BF16 weight column above plus runtime buffers, prompt/generation activations, logits, and KV cache is a more relevant starting point than the training-state column. The KV-cache example is small only because context and hidden widths are small; longer contexts and concurrent sequences increase it. Quantization could reduce weight memory with accuracy/runtime trade-offs but is not assumed or approved.

## 8. Causal language-model training objective

The following describes the objective conceptually; no data is prepared and no training is performed.

1. A tokenizer maps text to token IDs \(x_0, x_1, \ldots, x_T\).
2. For a sequence window, the model input is \(x_0,\ldots,x_{T-1}\), and the aligned targets are shifted one token to the right: \(x_1,\ldots,x_T\).
3. A causal attention mask ensures that the logit vector \(z_t\) at position \(t\) can depend only on tokens at or before \(x_t\), never on its target \(x_{t+1}\) or later tokens.
4. The next-token cross-entropy objective is:

$$
\mathcal{L}_{\mathrm{NLL}}
=
-\frac{1}{N}
\sum_{t\in\mathcal{M}}
\log\left(
\operatorname{softmax}(z_t)_{x_{t+1}}
\right)
$$

where \(\mathcal{M}\) is the set of valid, non-padding target positions and \(N=|\mathcal{M}|\). Padding and any deliberately excluded boundary positions must be masked out. Document packing and end-of-document tokens need a separately approved policy so examples do not unintentionally attend across boundaries.

5. Backpropagation updates randomly initialized parameters using an optimizer. Training loss is measured on batches used for updates; validation loss is measured on separate, read-only validation data and may guide checkpoint selection.
6. If training loss keeps falling while validation loss worsens or stalls, that is one signal of overfitting. Repeated examples, a tiny corpus, or tuning against held-out test data can create misleading results. The final test set must remain sealed and must not be used to fit tokenizer statistics or choose checkpoints.
7. Report loss/perplexity and task-level behavior separately for English, Hindi-Devanagari, and Hinglish-Roman. A pooled average must not hide a weak language. Lower next-token loss is not proof of comprehension, reasoning, factual knowledge, or safe assistant behavior.

## 9. Expected capabilities and limitations

These qualitative expectations are risks, not performance predictions. Data quality, tokenization, training-token count, optimization, and evaluation can dominate parameter count.

| Illustrative size | Realistic expectation if successfully trained from scratch | Do not assume |
|---|---|---|
| **About 1M** | May learn local spelling, frequent short patterns, and corpus-specific continuations. | Coherent multi-sentence answers, reliable multilingual ability, facts, reasoning, or useful tool calls. |
| **About 5M** | May represent more patterns and produce somewhat longer continuations on familiar training-like text. | Robust instruction following, factual recall, generalization beyond a narrow corpus, or consistent quality across all three languages. |
| **About 10M** | Could support a more informative educational comparison and expose effects of data, context, and model depth. | Human-level comprehension/reasoning, dependable code generation, safety, or factual reliability. |
| **About 25M** | Offers greater parameter capacity for a tiny experiment, but still depends on sufficient clean data and training compute. | A general-purpose assistant, broad factual knowledge, reliable tool use, or a production-ready model. |

Across all sizes:

- **Language generation:** Short, fluent-looking fragments can coexist with repetition, incoherence, malformed text, and failure on unfamiliar prompts.
- **Basic language patterns:** A model can learn statistical continuations without understanding their meaning or intent.
- **Factual knowledge:** A small training corpus gives narrow and potentially stale coverage. Fluent statements may be unsupported or wrong.
- **Reasoning:** Template-like arithmetic or pattern performance does not establish general reasoning; memorization and prompt sensitivity are likely concerns.
- **Long context:** The illustrative context is 256 tokens. Longer context increases activation/attention costs; a context limit is not evidence that the model can use all of it.
- **Tool calling:** Producing a syntactically valid tool request requires suitable examples, decoding/validation, and safe orchestration. Model size alone does not provide tool competence or permission to execute commands.
- **Multilingual quality:** English, Devanagari Hindi, and Romanized Hinglish have different scripts and tokenization patterns. Equal priority requires separate data/evaluation evidence, not an assumption that shared parameters yield equal results.

## 10. Evaluation and future configuration selection

Compare candidate configurations only after the user approves data, tokenizer, training, and evaluation policies. Keep language-specific results separate.

| Criterion | Proposed evidence for comparison |
|---|---|
| Parameter efficiency | Total parameters, token embedding/output share, held-out language-model loss, and task outcomes per parameter; report exact architecture and tokenizer fingerprints. |
| Memory requirements | Measured peak GPU and system RAM for the same sequence/batch/precision, including optimizer and activation memory—not just weight-file size. |
| Training feasibility | Stable step completion, throughput, checkpoint/resume behavior, storage consumed, temperature/power observation, and reproducibility on the approved machine. No benchmark is run in this planning task. |
| Language-specific quality | Separate tokenization fertility, held-out NLL/perplexity, comprehension, and human-rated generation quality for English, Hindi-Devanagari, and Hinglish-Roman. Do not rank the languages or mask results with only a pooled score. |
| Repetition and coherence | Fixed prompts/decoding settings; report repeated n-grams, non-empty completion rates, length behavior, and human coherence/readability ratings. |
| Factual reliability | Evidence-grounded questions; rate supported claims, contradictions, unsupported claims, and appropriate abstention. Do not treat memorized training text as verified truth. |
| Safety and privacy | Approved safety probes, sensitive-data/credential leakage checks, and prompt/data isolation checks. Any release criteria require explicit approval. |
| Reproducibility | Record random seeds, code/dependency versions, tokenizer/data versions, model configuration, optimizer/scheduler, precision, hardware, and evaluation harness. Rerun a bounded subset to characterize variance. |

No numerical acceptance threshold, benchmark set, or model-selection rule is established here. Such gates require a separately approved evaluation set, baseline, scoring policy, and user-approved criteria before training.

## 11. Risks and recommendations

### Risks

1. **Capacity is not capability:** A configuration near 25M parameters remains tiny. More parameters do not compensate for inadequate or unapproved data, poor tokenization, or weak evaluation.
2. **Parameter accounting changes with design:** Untied embeddings, a larger vocabulary, extra biases, alternative FFNs, or normalization choices can materially alter a small model's total.
3. **Activation estimates are incomplete:** The simple state tables exclude activation storage and implementation-specific workspace; training may require substantially more GPU memory than the parameter-state estimate.
4. **Context and multilingual tokenization interact:** Fragmented Hindi/Hinglish consumes context and compute. A nominal vocabulary-size increase can displace transformer parameters and does not guarantee coverage.
5. **Tiny-test overfitting:** A small hand-written or templated test can be memorized or leaked. Dataset and tokenizer split isolation must be established before training.
6. **Evaluation can overclaim:** Loss, a few fluent examples, or successful generation proves neither reasoning nor assistant usefulness, factuality, safety, or provider readiness.
7. **Operational approvals remain separate:** Selecting this reference architecture would not authorize dependency installation, downloads, tokenizer fitting, training, code changes, provider changes, or using cloud resources.

### Recommendations (not approvals)

- Use the decoder-only causal Transformer as an arithmetic and evaluation reference, not as a finalized design.
- Keep a tied-embedding example in the comparison to show how parameter sharing can contain vocabulary cost; compare untied head costs explicitly before a future choice.
- Treat 1M–25M configurations as educational scale examples only. Use measured memory and quality results, not parameter count alone, to compare them.
- Preserve equal priority and independent evaluation/reporting for English, Hindi-Devanagari, and Hinglish-Roman.
- Follow the Phase 1D gates for data rights/privacy, tokenizer, architecture, hardware, dependencies, storage, and evaluation. Preserve Ollama until a separately approved native implementation passes release gates.

## 12. Decisions requiring explicit user approval

No item below is selected by this plan. Each remains pending unless the user separately approves it:

- Model architecture and positional-information method.
- Total parameter count or which illustrative budget to investigate.
- Vocabulary size, tokenizer, byte-fallback policy, and tied versus untied input/output embeddings.
- Hidden dimension \(d\), number of layers \(L\), number of attention heads \(h\), and FFN dimension \(f\).
- Maximum context length \(C\), training sequence length, batch size, and document-packing/boundary policy.
- Training and inference precision, gradient precision, optimizer, optimizer hyperparameters, scheduler, and checkpoint format.
- Training-objective details, initialization, any later instruction-tuning scope, and permitted data.
- Language-specific training mixture/sampling; equal priority does not approve equal percentages.
- Evaluation sets, human-review process, scoring rules, safety/privacy checks, and pass/fail criteria. No numeric thresholds are proposed.
- Hardware allocation, memory/thermal limits, dependencies/runtime, storage/retention, and any benchmark or training authorization.

The high-level direction—train Veronica's first tiny model from scratch and eventually generate native final answers from its own model—is confirmed. It does not authorize implementation, data acquisition, tokenizer creation, training, or changes to the current Ollama/provider setup.
## 13. References

1. Vaswani et al., [Attention Is All You Need](https://arxiv.org/abs/1706.03762) — Transformer architecture reference.
2. Su et al., [RoFormer: Enhanced Transformer with Rotary Position Embedding](https://arxiv.org/abs/2104.09864) — Rotary position embedding reference.
3. Kingma and Ba, [Adam: A Method for Stochastic Optimization](https://arxiv.org/abs/1412.6980) — Adam optimizer reference.
4. Veronica, [Phase 1B Native AI Foundation Plan](PHASE_1B_NATIVE_AI_FOUNDATION_PLAN.md), [Phase 1C Data Evaluation Foundation Plan](PHASE_1C_DATA_EVALUATION_FOUNDATION_PLAN.md), [Phase 1D Decisions and Approval Matrix](PHASE_1D_DECISIONS_AND_APPROVAL_MATRIX.md), and [Phase 1E Technical Feasibility Plan](PHASE_1E_TECHNICAL_FEASIBILITY_PLAN.md).