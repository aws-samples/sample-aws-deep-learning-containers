# Graviton CPU vs x86 GPU LLM Benchmark (vLLM & llama.cpp)

Reproducible benchmark for serving `Qwen/Qwen3-8B` with two inference engines
across three compute targets — AWS Graviton (arm64) CPU, x86 CPU, and x86 GPU —
using **prebuilt public AWS Deep Learning Container (DLC) images**. No image
build required.

## Overview

This sample measures the latency, throughput, memory, and cost characteristics
of running the same model on different engines and hardware so you can decide
where to serve it.

- **vLLM** — a general-purpose, high-throughput inference server with
  continuous batching and paged attention. Strong on GPU and for concurrent
  serving.
- **llama.cpp** — a CPU-first, quantized inference engine (GGUF weights) that
  runs well on commodity CPUs, including Graviton, and also supports GPU
  offload.

The interesting question is cost/performance: a Graviton CPU instance is far
cheaper per hour than a GPU instance, but slower per token. This benchmark
quantifies that trade-off with a consistent methodology so the comparison is
apples-to-apples.

## Prerequisites

- An AWS account with permission to launch EC2 instances.
- One instance per target you want to benchmark:
  - **Graviton CPU** (arm64): e.g. `m8g.4xlarge` (Graviton3+ required).
  - **x86 CPU**: e.g. `m7i.4xlarge`.
  - **x86 GPU**: e.g. `g6e.xlarge`.
- **Docker** installed on each instance (NVIDIA Container Toolkit on the GPU
  instance).
- **HuggingFace access** to `Qwen/Qwen3-8B` and `unsloth/Qwen3-8B-GGUF`
  (both ungated — no token needed). Export a token via `HF_TOKEN` in
  `scripts/env.sh` only if you swap in a gated model.
- **Python 3.12+** on whichever host drives the load (can be the serving
  instance itself). `inference-perf` requires 3.12; `run_benchmark.sh` creates a
  local `python3.12` venv and installs `inference-perf` automatically.
- **`envsubst`** (from the `gettext` package) — `run_benchmark.sh` uses it to
  render the config templates. Install with `sudo dnf install -y gettext` (AL2023)
  or `sudo apt-get install -y gettext-base` (Ubuntu).

## Directory Structure

```
graviton-vs-gpu-llm-benchmark/
├── README.md
├── scripts/
│   ├── env.sh              # shared config — edit this first
│   ├── serve_vllm.sh       # launch a vLLM container
│   ├── serve_llamacpp.sh   # launch a llama.cpp container
│   ├── run_benchmark.sh    # drive inference-perf + capture decode/mem
│   └── teardown.sh         # remove containers
└── config/                 # one inference-perf config per scenario
    ├── baseline.yaml
    ├── saturation.yaml
    ├── sweep.yaml
    ├── production.yaml
    └── sharegpt.yaml
```

## Configuration

All knobs live in `scripts/env.sh`. Edit it, then `source scripts/env.sh`.

| Variable | Purpose |
|---|---|
| `MODEL` | Full-precision HF model repo (`Qwen/Qwen3-8B`). |
| `GGUF_REPO` | GGUF quant repo for llama.cpp (`unsloth/Qwen3-8B-GGUF`). |
| `TOKENIZER` | Tokenizer used by the benchmark. |
| `VLLM_GPU_IMAGE` | Public vLLM DLC tag (`vllm:server-cuda-v2.3.0`). GPU only — there is no public vLLM CPU image. |
| `LLAMACPP_ARM64_CPU_IMAGE` | Public llama.cpp arm64 CPU DLC tag (`llama-cpp-arm64:server-cpu-v1`). |
| `LLAMACPP_X86_CPU_IMAGE` | Public llama.cpp x86 CPU DLC tag (`llama-cpp:server-cpu-v1`). |
| `LLAMACPP_X86_GPU_IMAGE` | Public llama.cpp x86 GPU/CUDA DLC tag (`llama-cpp:server-cuda-v1`). |
| `VLLM_PORT` / `LLAMACPP_PORT` | Host ports (8000 / 8080). |
| `MAX_MODEL_LEN` / `CTX` | Context window for vLLM / llama.cpp (4096). |
| `LLAMA_CACHE` | Host dir mounted into llama.cpp so downloaded GGUFs persist across restarts. |
| `HF_TOKEN` | HuggingFace token for gated repos (empty by default; not needed for Qwen3-8B). |

> All image tags are public on `public.ecr.aws/deep-learning-containers/` and
> require no ECR login. They are set in `scripts/env.sh`.

## Quick Start

```bash
source scripts/env.sh

# Example: llama.cpp Q4_K_M on Graviton CPU
IMAGE="$LLAMACPP_ARM64_CPU_IMAGE" QUANT=Q4_K_M scripts/serve_llamacpp.sh
BASE_URL="http://localhost:${LLAMACPP_PORT}" SCENARIO=sweep \
  CONTAINER=llamacpp-bench MODEL_NAME="${GGUF_REPO}:Q4_K_M" scripts/run_benchmark.sh
scripts/teardown.sh
```

## Step-by-Step

1. **Set env** — edit `scripts/env.sh` (image tags, `HF_TOKEN`), then
   `source scripts/env.sh`.
2. **Launch a server** for one cell of the matrix:
   - vLLM full precision (GPU only):
     `IMAGE="$VLLM_GPU_IMAGE" scripts/serve_vllm.sh`
   - llama.cpp on Graviton CPU:
     `IMAGE="$LLAMACPP_ARM64_CPU_IMAGE" QUANT=Q4_K_M scripts/serve_llamacpp.sh`
   - llama.cpp on x86 GPU:
     `IMAGE="$LLAMACPP_X86_GPU_IMAGE" QUANT=Q4_K_M DEVICE=gpu scripts/serve_llamacpp.sh`
   Each script polls `/health` and prints the base URL and served `model_name`
   when ready. (vLLM cannot serve GGUF with the DLC image — see the matrix.)
3. **Run the benchmark** against the server. For llama.cpp, pass the served GGUF
   id as `MODEL_NAME`:
   `BASE_URL=http://localhost:8080 SCENARIO=sweep CONTAINER=llamacpp-bench MODEL_NAME=unsloth/Qwen3-8B-GGUF:Q4_K_M scripts/run_benchmark.sh`
   Use `DEVICE=gpu` on GPU targets (switches peak-mem capture to `nvidia-smi`).
   Pick a scenario from the config matrix below.
4. **Read metrics** from the `results/<scenario>-<timestamp>/` directory: the
   inference-perf per-stage report JSON (`run_benchmark.sh` prints a summary
   table), `single_stream.json` (llama.cpp raw decode via
   `.timings.predicted_per_second`), and `mem_samples.log` / `gpu_mem.log`
   (peak memory).
5. **Teardown**: `scripts/teardown.sh` removes the containers.

### Scenarios

| Scenario | Load model | Best for |
|---|---|---|
| `baseline` | concurrent, conc 1 | Single-stream latency (TTFT/ITL/decode), any target. |
| `sweep` | concurrent, conc 1/2/4/8 | Primary CPU sweep — clean per-concurrency System TPS. Also valid on GPU. |
| `saturation` | concurrent, conc 1/4/16/32/64 | GPU throughput ceiling under continuous batching. On CPU/llama.cpp high levels just queue. |
| `production` | Poisson rate ramp | Rate-based production traffic — meaningful for vLLM on GPU (won't just queue). |
| `sharegpt` | Poisson, ShareGPT data | Optional realistic-traffic add-on (not part of the fixed-length matrix). |

CPU targets use fixed-**concurrency** load because a fixed request rate against a
slow CPU server just unboundedly queues. GPU/vLLM can additionally use the
**rate-based** scenarios since continuous batching absorbs the arrival rate.

## Benchmark Metrics Explained

- **TTFT (Time To First Token)** — prompt-processing plus queue latency before
  the first token streams. Directly felt in interactive UX; high TTFT makes a
  UI feel unresponsive.
- **ITL / TPOT (Inter-Token Latency / Time Per Output Token)** — steady-state
  per-token latency during generation. Governs how smoothly text streams to the
  user.
- **System TPS** — aggregate tokens/second across all concurrent requests. This
  is the throughput that drives cost: more TPS per instance means fewer
  instances for the same load.
- **Per-user TPS** — tokens/second experienced by a single request under load.
  Shows how much concurrency degrades the individual-user experience.
- **Single-stream decode tok/s** — raw generation speed for one request with no
  batching. Measures the engine/hardware's ceiling independent of scheduling.
- **Peak memory** — the maximum resident memory of the server container. Sets
  the minimum instance size you must pay for, so it feeds directly into cost.
- **Cost per 1M output tokens** — the bottom-line efficiency metric:
  `instance $/hr ÷ (System TPS × 3600) × 1e6`. Lets you compare a cheap-but-slow
  CPU instance against an expensive-but-fast GPU instance on equal footing.

## Configuration Matrix

| Engine | Graviton CPU | x86 CPU | x86 GPU |
|---|---|---|---|
| **llama.cpp** | BF16, Q8_0, Q4_K_M | BF16, Q8_0, Q4_K_M | BF16, Q8_0, Q4_K_M |
| **vLLM** | — | — | BF16 |

- **llama.cpp** covers all three targets × three precisions (native GGUF).
- **vLLM is GPU-only** here: there is no public vLLM CPU/arm64 DLC image
  (serving vLLM on CPU needs a custom build, out of scope for this sample).
- **vLLM cannot serve GGUF with the DLC images** (CPU or GPU): the wheel is built
  without a GGUF loader, so vLLM rejects `--quantization gguf` with "Unknown
  quantization method: gguf". Use llama.cpp for any quantized (GGUF) serving.
- The pairing is therefore vLLM(BF16 native) vs llama.cpp(GGUF quants) on GPU.

## Instance Selection Guide

| Target | Example instance | Notes |
|---|---|---|
| Graviton CPU | `m8g.4xlarge` | Graviton3+ required; cheapest per hour. Best with Q4_K_M / Q8_0. |
| x86 CPU | `m7i.4xlarge` | Baseline x86 CPU comparison (vCPU/mem parity with the m8g above). |
| x86 GPU | `g6e.xlarge` (L40S) or `g6.2xlarge` (L4) | Needs NVIDIA Container Toolkit. Highest throughput. |

Size the instance so peak memory (measured in the run) fits with headroom. BF16
weights of an 8B model need ~16 GB; Q8_0 ~9 GB; Q4_K_M ~5 GB.

**GPU decode is memory-bandwidth-bound**, so the specific GPU matters: an
NVIDIA L4 has ~300 GB/s of memory bandwidth while an L40S has ~864 GB/s.
Single-stream decode tok/s scales roughly as `bandwidth ÷ weight_bytes`, so the
same model/quant decodes ~2.5–3× faster on an L40S than on an L4. Note which GPU
you actually landed on (`nvidia-smi`) — capacity fallbacks can silently swap
`g6e` (L40S) for `g6` (L4). This is also why quantization speeds up single-stream
decode substantially even on GPU.

## Cost Estimate

Compute cost per 1M output tokens as `instance $/hr ÷ (System TPS × 3600) × 1e6`
using the on-demand price of the instance in your region and the System TPS from
the saturation run. Compare cells to find the cheapest target that meets your
latency (TTFT/ITL) requirements. Running the full matrix on three instances for
a few hours is inexpensive — terminate instances promptly (see Teardown).

## Teardown

```bash
scripts/teardown.sh          # docker rm -f the benchmark containers
```

Then terminate the EC2 instances (console, or `aws ec2 terminate-instances
--instance-ids <id>`) — this is a manual step and is required to stop billing.

## References

- AWS Deep Learning Containers: https://github.com/aws-samples/sample-aws-deep-learning-containers
- vLLM: https://docs.vllm.ai/
- llama.cpp: https://github.com/ggml-org/llama.cpp
- inference-perf: https://github.com/kubernetes-sigs/inference-perf
- Qwen3: https://huggingface.co/Qwen/Qwen3-8B
