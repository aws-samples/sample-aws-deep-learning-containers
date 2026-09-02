#!/usr/bin/env bash
# Launch a llama.cpp server (llama-server) in a DLC container.
#
#   Graviton CPU:  IMAGE=$LLAMACPP_ARM64_CPU_IMAGE QUANT=Q4_K_M ./serve_llamacpp.sh
#   x86 CPU:       IMAGE=$LLAMACPP_X86_CPU_IMAGE   QUANT=Q8_0   ./serve_llamacpp.sh
#   x86 GPU:       IMAGE=$LLAMACPP_X86_GPU_IMAGE   QUANT=Q4_K_M DEVICE=gpu ./serve_llamacpp.sh
#
# The image entrypoint (/usr/bin/serve) runs
# `llama-server --host 0.0.0.0 --port 8080 "$@"`, so the args below are appended
# after host/port. The served model id (inference-perf MODEL_NAME) is
# "${GGUF_REPO}:${QUANT}", e.g. unsloth/Qwen3-8B-GGUF:Q8_0.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/env.sh"

IMAGE="${IMAGE:?set IMAGE (e.g. \$LLAMACPP_ARM64_CPU_IMAGE)}"
QUANT="${QUANT:?set QUANT (BF16|Q8_0|Q4_K_M)}"
PORT="${PORT:-$LLAMACPP_PORT}"
NAME="${NAME:-llamacpp-bench}"
DEVICE="${DEVICE:-cpu}"          # cpu|gpu

args=(-hf "${GGUF_REPO}:${QUANT}" -c "$CTX" --jinja)
docker_gpu=()
if [[ "$DEVICE" == "gpu" ]]; then
  docker_gpu=(--gpus all)
  args+=(-ngl 99)   # offload all layers to the GPU
fi

mkdir -p "$LLAMA_CACHE"
docker run -d --rm --name "$NAME" \
  "${docker_gpu[@]}" \
  -p "${PORT}:8080" \
  -e LLAMA_CACHE=/cache -v "${LLAMA_CACHE}:/cache" \
  -e HF_TOKEN="$HF_TOKEN" \
  "$IMAGE" "${args[@]}"

echo "Waiting for llama.cpp /health on :${PORT} ..."
until curl -sf "http://localhost:${PORT}/health" >/dev/null; do
  docker ps -q -f "name=$NAME" >/dev/null || { echo "container exited"; docker logs "$NAME"; exit 1; }
  sleep 5
done
echo "llama.cpp ready: http://localhost:${PORT}/v1 (model_name=${GGUF_REPO}:${QUANT})"
