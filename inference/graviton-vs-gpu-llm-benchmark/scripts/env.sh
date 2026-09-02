#!/usr/bin/env bash
# Shared configuration for the Graviton-vs-GPU LLM benchmark sample.
# Edit the values below, then `source scripts/env.sh` before running any script.
# No `set -e`/`-u` here — this file is sourced; the runnable scripts set them.

# --- Model ---
export MODEL="Qwen/Qwen3-8B"                 # full-precision HF repo (vLLM, transformers)
export GGUF_REPO="unsloth/Qwen3-8B-GGUF"     # GGUF quant repo (llama.cpp)
export TOKENIZER="Qwen/Qwen3-8B"             # tokenizer used by the benchmark

# --- DLC images (public ECR — no login required) ---
export VLLM_GPU_IMAGE="public.ecr.aws/deep-learning-containers/vllm:server-cuda-v2.3.0"
export LLAMACPP_ARM64_CPU_IMAGE="public.ecr.aws/deep-learning-containers/llama-cpp-arm64:server-cpu-v1"
export LLAMACPP_X86_CPU_IMAGE="public.ecr.aws/deep-learning-containers/llama-cpp:server-cpu-v1"
export LLAMACPP_X86_GPU_IMAGE="public.ecr.aws/deep-learning-containers/llama-cpp:server-cuda-v1"
# NOTE: there is no public vLLM CPU/arm64 DLC image. Serving vLLM on a CPU
# (Graviton or x86) requires a custom build and is out of scope for this public
# sample — the vLLM cells here are GPU-only.

# --- Serving ---
export VLLM_PORT="8000"
export LLAMACPP_PORT="8080"
export MAX_MODEL_LEN="4096"   # vLLM
export CTX="4096"             # llama.cpp context window

# llama.cpp downloads GGUF weights at runtime via -hf; mount this cache so the
# quants persist (and don't re-download) across container restarts.
export LLAMA_CACHE="${LLAMA_CACHE:-$HOME/llama-cache}"

# --- HuggingFace ---
export HF_TOKEN=""            # set if the model repos require gated access (not needed for Qwen3-8B)
