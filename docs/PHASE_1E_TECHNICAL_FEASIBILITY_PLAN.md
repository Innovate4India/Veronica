# Veronica Phase 1E: Technical Feasibility and Resource Assessment Plan

**Status:** Planning only
**Investigation date:** 2026-11-24
**Authorization:** Documentation and read-only investigation only
**Scope:** No packages, drivers, models, or datasets were installed or downloaded. No benchmark or training run was performed.

## 1. Executive summary

The read-only system probe confirms an Intel Core i5-13420H (8 cores / 12 logical processors), 16 GB installed RAM (about 15.7 GiB visible to Windows), Windows 11 64-bit, an NVIDIA GeForce RTX 3050 Laptop GPU with 6,144 MiB VRAM, and 281.95 GiB free on the project drive (D:). At the time of the probe, only about 2.81 GiB of physical RAM was free; that value is a transient snapshot, not a fixed training budget. NVIDIA's compute-capability table lists the GeForce RTX 3050 at capability 8.6.

The installed NVIDIA driver is 576.93 and `nvidia-smi` reports CUDA 12.9 compatibility. This does **not** establish that the CUDA Toolkit, `nvcc`, framework CUDA libraries, or a compatible Python/GPU framework are installed. `nvcc` was not found on PATH. The existing `.venv` uses Python 3.14.5 and contains none of the checked ML packages (PyTorch, TensorFlow, JAX, SentencePiece, or Transformers). Framework compatibility for this exact Python/Windows/driver combination is not established.

A tiny model is a plausible educational experiment after the required approvals and a compatible stack are established; it is not evidence that a capable general assistant can be trained on this laptop. For perspective, a 100-million-parameter model's FP16 weights alone are about 200 MB, but ordinary FP32 Adam training states are about 1.6 GB before activations, temporary buffers, CUDA context, and other use of the GPU. A 1-billion-parameter model would require about 16 GB for FP32 parameters, gradients, and two Adam moments before those additional costs, exceeding the GPU's 6 GB VRAM. Inference uses materially less memory than training, but weight-size arithmetic alone does not establish runtime fit or acceptable speed.

These are feasibility comparisons, not a selected architecture or parameter target. No data source, tokenizer, model size, framework, storage policy, or training operation is approved here. English, Hindi (Devanagari), and Hinglish (Roman Hindi) remain equal priority; inventory, evaluation, and quality reporting should stay separate by language.

## 2. Verified hardware facts

The values below were observed through read-only Windows system queries and `nvidia-smi` on 2026-11-24. Free RAM and disk figures can change with running applications and storage activity.

| Component | Observed value | Evidence and interpretation |
|---|---|---|
| Operating system | Microsoft Windows 11 Home Single Language, 64-bit, version 10.0.26200 | `Win32_OperatingSystem`; the GPU was reported in WDDM mode. |
| CPU | 13th Gen Intel Core i5-13420H; 8 cores, 12 logical processors | `Win32_Processor`. Its `MaxClockSpeed` field returned 2,100 MHz; this should not be read as the CPU's maximum turbo clock or sustained performance. |
| Installed / visible RAM | 16,852,574,208 bytes installed (about 15.7 GiB); Windows reported about 15.7 GiB visible | `Win32_ComputerSystem` and `Win32_OperatingSystem`. |
| Free physical RAM at probe | About 2.81 GiB | Snapshot only; other applications consume memory and this figure changes over time. |
| GPU | NVIDIA GeForce RTX 3050 6GB Laptop GPU | Confirmed by `nvidia-smi` and Windows video-device inventory. |
| GPU VRAM | 6,144 MiB (6 GiB) | `nvidia-smi` memory total; use this instead of the truncated WMI `AdapterRAM` field. |
| GPU compute capability | 8.6 | NVIDIA's CUDA GPU table lists the GeForce RTX 3050 under 8.6. This is a product-specification lookup, not a runtime kernel test on this computer. |
| Driver | NVIDIA 576.93 | `nvidia-smi`. |
| CUDA compatibility reported by driver | 12.9 | The CUDA version shown by `nvidia-smi` is the maximum CUDA compatibility reported by the driver; it is not proof of an installed CUDA Toolkit. |
| Project-drive free space | D: 281.95 GiB free; C: 18.42 GiB free | `Get-PSDrive` snapshot. The repository is on D:. Drive type/performance and storage allocation policy were not measured. |

The full `nvidia-smi` snapshot showed the GPU in WDDM mode, at 0% utilization and 0 MiB reported memory use at that instant. Its displayed power reading was a momentary reading, not a sustained thermal or power characterization. A later structured query returned the power limit as unavailable.

## 3. Unknown or unverified hardware facts

- Sustained CPU/GPU throughput, GPU utilization under a representative workload, and actual training tokens per second.
- Sustained laptop power limits, cooling behavior, thermal throttling, and acceptable long-run temperature/noise.
- Dedicated versus shared memory behavior under the eventual framework, the display's sustained VRAM use, and practical VRAM available to a job.
- Physical storage type, read/write throughput, health, and how much of the free space the user is willing to allocate.
- Stable available RAM during a training run; the single free-memory reading is not a capacity guarantee.
- CUDA Toolkit installation, `nvcc` version, framework CUDA libraries, and whether any future package can use the installed driver.
- WSL2 availability/configuration and whether it can access the NVIDIA GPU.
- Any multi-GPU capability; none was observed or assumed.

No stress test, thermal test, disk benchmark, CUDA sample, or ML benchmark was run.

## 4. GPU and CUDA assessment

### Verified compatibility signals

- NVIDIA lists the GeForce RTX 3050 at compute capability **8.6**. That is within the architecture range of many contemporary CUDA frameworks, but each framework build still must include compatible kernels and libraries.
- The installed 576.93 driver reports CUDA 12.9 compatibility. Driver compatibility does not mean that CUDA 12.9 Toolkit is installed, nor that an arbitrary framework wheel bundles or supports a matching CUDA runtime.
- The device is operating through Windows' WDDM display-driver model. Windows, display activity, and other GPU processes can reduce VRAM and compute available to training or inference.
- `nvcc` was not found on PATH. This does not prove that no Toolkit files exist elsewhere; it means a compiler/toolkit version was not verified through PATH.

### Windows-specific limitations

- Framework GPU support is framework- and release-specific. TensorFlow's current installation guide says its native-Windows GPU support ended after TensorFlow 2.10; later TensorFlow GPU use on Windows requires WSL2. Its current pip guide lists Python 3.9–3.12, so Python 3.14.5 is outside that documented range.
- JAX's current installation guide lists native Windows x86_64 CPU support, but no native Windows NVIDIA GPU support; NVIDIA GPU support under WSL2 is marked experimental. The guide does not establish this environment's Python 3.14.5 compatibility.
- PyTorch is a reasonable candidate to investigate. Current official PyTorch Windows documentation lists Python 3.10–3.14 as supported, so Python 3.14.5 is within the documented range. The exact PyTorch release, CUDA wheel, driver/runtime combination, and execution on this RTX 3050 remain unverified.
- A future compatibility check must match the exact framework release, Python ABI, Windows platform, GPU architecture, CUDA runtime, and driver. No framework package was installed or imported during this investigation.

**Assessment:** CUDA hardware capability is promising for small experiments, but end-to-end software compatibility and effective VRAM availability remain unverified. Do not equate “CUDA 12.9” in `nvidia-smi` with a working training stack.

## 5. Python and ML framework compatibility

The active interpreter is `.venv\Scripts\python.exe`, Python **3.14.5** (64-bit CPython on Windows). The existing [requirements.txt](../requirements.txt) contains speech/media dependencies and Pillow, but no PyTorch, TensorFlow, JAX, SentencePiece, Transformers, or language-model training stack. Read-only package metadata checks found none of those five packages installed in the active environment.

| Framework/tool | Published compatibility evidence reviewed | Assessment for this project |
|---|---|---|
| **PyTorch** | Current official PyTorch Windows documentation lists Python 3.10–3.14 as supported; Python 3.14.5 falls within that documented range. | Candidate for a later compatibility investigation, not verified or installed. The exact PyTorch release, CUDA wheel, driver/runtime combination, and RTX 3050 execution remain unverified. |
| **TensorFlow** | Current official pip guide lists Python 3.9–3.12. It states native-Windows GPU support ends after TensorFlow 2.10; newer GPU use requires WSL2. | Python 3.14.5 is outside the documented range; current native-Windows GPU TensorFlow is not a suitable assumed path. A separately approved WSL2/Python environment would still need compatibility verification. |
| **JAX** | Current official installation guide marks native Windows x86_64 CPU as supported, native Windows NVIDIA GPU as unsupported, and WSL2 NVIDIA GPU as experimental. The guide reviewed does not specify a Python 3.14 support range. | Not a verified native-Windows GPU path. Do not assume JAX GPU training on this Windows environment. |
| **SentencePiece / Transformers** | Neither was present in the environment. The relevant Python/wheel and dependency compatibility for this exact platform was not established in this investigation. Transformers also requires a compatible backend for model training/inference. | No tokenizer library or model stack is selected. Verify exact release, wheel, license, and dependency compatibility only after separate approval. |

**Recommendation:** Keep the existing application environment unchanged. If a future compatibility investigation is authorized, evaluate an isolated environment first and record Python, framework, CUDA runtime, GPU visibility, and CPU fallback behavior. Do not change the project's Python version based only on the current framework documentation.

## 6. Storage architecture and estimates

### Measured free-space snapshot

| Volume | Free space at probe | Planning implication |
|---|---:|---|
| C: | 18.42 GiB | Limited headroom for large duplicate datasets or checkpoint collections. |
| D: (project drive) | 281.95 GiB | Appears ample for small educational artifacts by raw-size arithmetic, but does not approve any allocation, data source, or retention policy. |

Free space does not establish storage speed, durability, backup coverage, or the user's permission to consume it. External or cloud storage is **not approved or assumed**.

### Storage categories

| Category | Estimate or sizing rule | Assumptions and limitations |
|---|---|---|
| Raw training datasets | No responsible fixed estimate before exact sources and revisions are approved. Record each source snapshot's actual size. | Retaining both a raw snapshot and normalized copy may require roughly twice the source text size, before tokenized copies, indexes, logs, or backups. This is an illustrative planning multiplier, not a corpus forecast. |
| Curated/tokenized data | For `N` tokens, packed IDs need about 2 bytes/token with 16-bit IDs, 4 bytes with 32-bit IDs, or 8 bytes with 64-bit IDs. Thus 100 million tokens correspond to roughly 0.2–0.8 GB of packed IDs. | Actual vocabulary, token count, serialization, metadata, temporary buffers, and duplicated split manifests are unknown. Some training pipelines materialize additional copies. |
| Tokenizer artifacts | Expected to be small relative to a corpus or model checkpoint, but no file-size estimate is validated. | Depends on algorithm, vocabulary, normalization, training metadata, and version history. No tokenizer or vocabulary is approved. |
| Model weights/checkpoints | See the parameter storage table below. | Raw tensor arithmetic only; file format metadata, quantization scales, optimizer state, and multiple checkpoints add storage. |
| Optimizer state | FP32 Adam's two moment tensors require about 8 bytes/parameter: about 0.8 GB at 100M parameters or 8 GB at 1B. | This is optimizer state alone. Resumable checkpoints also include model weights and metadata; training gradients are generally live memory, not necessarily checkpointed. |
| Evaluation datasets | Size depends on the approved task set and encoding; no set or size is currently approved. | Keep sealed test data separately access-controlled. Tokenized evaluation copies follow the token-ID sizing rule above. |
| Backups and retained checkpoints | Each additional full copy adds the size of the artifacts copied; one complete backup roughly doubles the backed-up subset's storage need. | Number of retained checkpoints, backup location, encryption, and external storage remain undecided. |

### Parameter-weight storage arithmetic

Decimal units are used (1 MB = 1 million bytes; 1 GB = 1 billion bytes). These are raw weight-size calculations, not a model design or fit guarantee.

| Parameters | FP16/BF16 weights (2 bytes/parameter) | FP32 weights (4 bytes/parameter) | FP32 Adam training state* (16 bytes/parameter) |
|---:|---:|---:|---:|
| 1 million | 2 MB | 4 MB | 16 MB |
| 10 million | 20 MB | 40 MB | 160 MB |
| 50 million | 100 MB | 200 MB | 800 MB |
| 100 million | 200 MB | 400 MB | 1.6 GB |
| 1 billion | 2 GB | 4 GB | 16 GB |

*The 16-byte/parameter training estimate is a conventional full-precision Adam baseline: FP32 parameters (4), gradients (4), and two FP32 optimizer moments (8). It excludes activations, attention/workspace buffers, CUDA context, temporary copies, allocator fragmentation, and other applications. A different precision, optimizer, or offload strategy changes the figure and needs separate validation. A resumable disk checkpoint often includes weights and optimizer moments (about 12 bytes/parameter for FP32 weights plus two FP32 moments), with additional space possible for master weights, metadata, and serialization copies.

## 7. Tiny-model feasibility comparison

These bands are planning comparisons only. They are **not** a final architecture, parameter count, training target, or authorization. The embedding matrix, including vocabulary cost, is part of the total parameter count.

| Illustrative size band | Inference perspective | From-scratch training perspective | Feasibility interpretation |
|---|---|---|---|
| **1–10M parameters** | FP16/BF16 weights alone are about 2–20 MB; runtime, activations, and context cache still add overhead. | FP32 Adam baseline is about 16–160 MB before activations and other overhead. | Most plausible educational scale to investigate first, after approvals. This says nothing about whether the resulting text is useful. |
| **10–50M parameters** | FP16/BF16 weights alone are about 20–100 MB. | FP32 Adam baseline is about 160–800 MB before activations and other overhead. | Potentially feasible for a bounded local experiment, but batch, sequence length, framework overhead, free VRAM, and thermal behavior must be measured. |
| **50–100M parameters** | FP16/BF16 weights alone are about 100–200 MB. | FP32 Adam baseline is about 0.8–1.6 GB before activations and other overhead. | Higher-risk exploratory tier on 6 GB VRAM. Do not promise fit or training speed without an approved representative run. |
| **Around 1B parameters** | FP16 weights alone are about 2 GB; quantized weight-only files may be smaller, subject to quality/runtime costs. | FP32 Adam baseline is about 16 GB before activations, already far beyond 6 GB VRAM. | Not a realistic full-parameter local training target under the ordinary Adam assumption. Inference might fit in some configurations, but context cache, runtime, and speed remain unverified. |

### Inference is not training

- **Inference** loads weights and runs forward passes. Memory is dominated by weight representation, runtime/kernel buffers, per-request activations, and (for autoregressive generation) the key/value cache, which grows with context length and concurrent requests. It has no backpropagation gradients or optimizer state. Quantization can reduce weight storage, but does not make an untrained model capable or change the provenance of its learned weights.
- **Training from scratch** starts with randomly initialized Veronica weights and repeatedly performs forward and backward passes. It needs the model, gradients, optimizer states, saved activations or recomputation workspace, data-loader buffers, and checkpoint I/O. Longer sequences, larger batches, and more layers/hidden units increase activation/workspace costs; attention implementations can also have substantial sequence-length-dependent memory.
- **The exact memory footprint is architecture- and implementation-dependent.** A weights-only file that fits in 6 GB does not establish training fit. Conversely, arithmetic model-state estimates do not certify GPU kernels, compatibility, stable thermal operation, or useful throughput.

## 8. Training and inference resource requirements

| Resource | Training from scratch | Inference |
|---|---|---|
| GPU VRAM | Weights + gradients + optimizer state + activations + temporary/framework buffers. The 6 GB card strongly limits full-precision model/sequence/batch choices. | Weights + runtime buffers + context/KV cache + per-request activations. Small models are more plausible, but context/concurrency still matter. |
| System RAM | Dataset/cache buffers, Python/runtime state, checkpoint staging, CPU fallback, and possible offload. Only 2.81 GiB was free in the observed snapshot. | Model loading/staging, application, context, and any CPU fallback. Memory availability can vary considerably. |
| CPU | Text preprocessing, data loading, tokenizer work, CPU kernels, and orchestration. The i5-13420H has 8 cores/12 logical processors, but throughput was not benchmarked. | Tokenization, request handling, sampling, and CPU fallback. GPU use and latency remain unverified. |
| Disk | Approved source snapshots, normalized/tokenized datasets, checkpoints, optimizer states, logs, temporary files, and backups. | Model/tokenizer files, application/runtime caches, and logs. No model or tokenizer files were downloaded. |
| Power/thermal | Sustained compute can be thermally or power limited on a laptop. No sustained run was conducted. | Usually lower than long training workloads, but depends on runtime, model, context, and concurrency. No measurement was made. |

## 9. Risks and limitations

1. **Capability:** A tiny from-scratch model is an educational milestone, not a promised assistant. Next-token loss and model size do not prove comprehension, reasoning, safety, factual reliability, or multilingual quality.
2. **Framework compatibility:** The current environment lacks the relevant ML packages. Python 3.14.5, Windows, driver 576.93, and CUDA 12.9 have not been tested together with a selected framework.
3. **VRAM overhead:** The full 6 GiB is not necessarily available to a training process. Windows display use, framework allocations, activation memory, attention workspaces, and fragmentation reduce usable capacity.
4. **System-memory headroom:** About 2.81 GiB RAM was free during the probe; this can change, and CPU offload could compete with applications and dataset buffers.
5. **Storage policy:** D: has substantial free space, but dataset size and checkpoint-retention needs cannot be estimated until data sources, training scale, and backup policy are approved.
6. **Thermal and performance uncertainty:** No training, GPU benchmark, sustained load, or disk benchmark was run. No duration, tokens/second, temperature, or quality claim is supported.
7. **Data governance:** No dataset is approved by the Phase 1C/1D plans. Public availability, a dataset-card license, or available storage is not permission to collect or train.
8. **Online/offline boundary:** Future external storage, cloud compute, online retrieval, or remote serving introduces separate privacy, security, cost, and authorization requirements.
9. **Hardware variation:** Laptop GPU power limits and cooling differ by device configuration and workload. Desktop GPU specifications cannot be used as a laptop performance promise.

## 10. Recommended next steps

These are recommendations for a future, explicitly approved phase; they are not authorization to proceed.

1. Preserve the current environment and provider/Ollama setup.
2. Decide whether future experiments are strictly laptop-only and what disk allocation, backup, and maximum run-time/thermal limits are acceptable.
3. Resolve the Phase 1D data, licensing, privacy, storage, tokenizer, architecture, dependency, and evaluation gates before acquiring or processing data.
4. If framework investigation is authorized, compare isolated Python environments against official release support for Windows, Python ABI, CUDA runtime, and RTX 3050 compute capability. Do not install into the existing project environment by default.
5. Only after approvals, establish a tiny, representative, language-separated data/evaluation pilot and perform a measured framework/device smoke test before selecting a model configuration.
6. Select model size only from measured peak VRAM, RAM, disk, throughput, and thermal behavior. Record the entire checkpoint/optimizer and backup footprint, not just model weights.
7. Keep English, Hindi-Devanagari, and Hinglish-Roman inventory, evaluation, and quality reporting independent. Equal language priority does not pre-approve equal sampling percentages.
8. Keep the Phase 1A provider boundary and the current Ollama implementation unchanged until a Veronica-trained provider passes separately approved release gates and the user explicitly approves any default change.

## 11. Decisions requiring explicit user approval

- Whether the first experiment is laptop-only or may later propose approved external compute/storage.
- Storage locations, disk allocation, retention, backups, access controls, and whether any future external/cloud storage is permitted.
- The exact Python/framework/runtime stack and any isolated environment, dependency installation, driver/toolkit change, or WSL2 setup.
- Each dataset source and revision, its allowed purpose, licensing/legal review, privacy review, and retention.
- The tokenizer method, vocabulary, model architecture, parameter count, precision, optimizer, sequence length, and batch size. None is fixed here.
- Evaluation set, baseline, per-language pass/fail thresholds, and safety/privacy criteria.
- A bounded authorization for any download, data processing, benchmark, tokenizer training, model training, or code change. The confirmed from-scratch direction alone does not authorize these operations.
- Whether/when an experimental native provider may be integrated or selected; the existing Ollama setup remains unchanged absent approval.

## 12. References

1. NVIDIA, [CUDA GPU Compute Capability](https://developer.nvidia.com/cuda-gpus) — GeForce RTX 3050 listed under compute capability 8.6.
2. NVIDIA, [CUDA Compatibility](https://docs.nvidia.com/deploy/cuda-compatibility/) — distinction between driver compatibility and toolkit/runtime compatibility.
3. PyTorch, [Windows installation and Python compatibility documentation](https://pytorch.org/get-started/locally/) — lists Python 3.10–3.14 as supported.
4. TensorFlow, [Install TensorFlow with pip](https://www.tensorflow.org/install/pip) — Python version range and Windows GPU/WSL2 guidance.
5. TensorFlow, [Build from source on Windows](https://www.tensorflow.org/install/source_windows) — native-Windows GPU limitation.
6. JAX, [Installation](https://docs.jax.dev/en/latest/installation.html) — Windows CPU, NVIDIA GPU, and WSL2 platform support status.
7. Veronica, [Phase 1B Native AI Foundation Plan](PHASE_1B_NATIVE_AI_FOUNDATION_PLAN.md), [Phase 1C Data Evaluation Foundation Plan](PHASE_1C_DATA_EVALUATION_FOUNDATION_PLAN.md), and [Phase 1D Decisions and Approval Matrix](PHASE_1D_DECISIONS_AND_APPROVAL_MATRIX.md).
