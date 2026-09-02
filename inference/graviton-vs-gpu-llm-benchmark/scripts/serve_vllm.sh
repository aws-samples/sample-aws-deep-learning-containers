#!/usr/bin/env bash
# Launch a vLLM OpenAI-compatible server (GPU only): IMAGE=$VLLM_GPU_IMAGE ./serve_vllm.sh
# No public vLLM CPU/arm64 DLC image exists, and the DLC vLLM wheel has no GGUF
# loader (rejects `--quantization gguf`) — use llama.cpp for quantized serving.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/env.sh"

IMAGE="${IMAGE:-$VLLM_GPU_IMAGE}"
PORT="${PORT:-$VLLM_PORT}"
NAME="${NAME:-vllm-bench}"

mkdir -p "$HOME/hf-cache"

# Default --gpu-memory-utilization (0.9) is fine for an 8B model at 4096 ctx.
docker run -d --rm --name "$NAME" \
  --gpus all --ipc=host \
  -p "${PORT}:8000" \
  -v "$HOME/hf-cache:/root/.cache/huggingface" \
  -e HF_TOKEN="$HF_TOKEN" \
  "$IMAGE" \
  "$MODEL" --host 0.0.0.0 --port 8000 --max-model-len "$MAX_MODEL_LEN"

echo "Waiting for vLLM /health on :${PORT} ..."
until curl -sf "http://localhost:${PORT}/health" >/dev/null; do
  docker ps -q -f "name=$NAME" >/dev/null || { echo "container exited"; docker logs "$NAME"; exit 1; }
  sleep 5
done
echo "vLLM ready: http://localhost:${PORT}/v1 (model_name=$MODEL)"
