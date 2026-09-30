#!/usr/bin/env bash
# Usage: peakmem.sh <deployment>. Prints server process VmHWM, plus GPU VRAM used if nvidia-smi exists.
set -euo pipefail
deploy=$1
k=(kubectl -n benchmarking exec "deploy/$deploy" --)
"${k[@]}" sh -c 'for p in /proc/[0-9]*; do n=$(cat "$p/comm" 2>/dev/null); case "$n" in llama-server|vllm|python*|VLLM*) echo "$n $(grep VmHWM "$p/status")";; esac; done; if command -v nvidia-smi >/dev/null; then nvidia-smi --query-gpu=memory.used --format=csv,noheader; fi || true'
