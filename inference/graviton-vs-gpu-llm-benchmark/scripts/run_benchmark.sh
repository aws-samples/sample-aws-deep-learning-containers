#!/usr/bin/env bash
# Drive inference-perf (v0.6.1) against a running OpenAI-compatible server, and
# alongside it capture single-stream raw decode speed and peak memory.
#
#   llama.cpp (CPU):
#     BASE_URL=http://localhost:8080 SCENARIO=sweep CONTAINER=llamacpp-bench \
#       MODEL_NAME=unsloth/Qwen3-8B-GGUF:Q4_K_M ./run_benchmark.sh
#   vLLM (GPU):
#     BASE_URL=http://localhost:8000 SCENARIO=saturation DEVICE=gpu \
#       MODEL_NAME=Qwen/Qwen3-8B ./run_benchmark.sh
#
# inference-perf requires Python >= 3.12 — the default system python3 (often 3.9)
# is too old. This script builds a local py3.12 venv on first run.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/env.sh"

BASE_URL="${BASE_URL:?set BASE_URL (e.g. http://localhost:8080)}"
MODEL_NAME="${MODEL_NAME:-$MODEL}"   # llama.cpp: unsloth/Qwen3-8B-GGUF:<QUANT>; vLLM: Qwen/Qwen3-8B
SCENARIO="${SCENARIO:-sweep}"        # concurrent: baseline|sweep|saturation ; rate-based: production|sharegpt
CONTAINER="${CONTAINER:-}"           # container name for docker-stats peak-mem capture (CPU)
DEVICE="${DEVICE:-cpu}"              # cpu|gpu — selects peak-mem source (docker stats vs nvidia-smi)
PYTHON="${PYTHON:-python3.12}"
OUTPUT_DIR="${OUTPUT_DIR:-$ROOT_DIR/results/${SCENARIO}-$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$OUTPUT_DIR"

VENV="${VENV:-$ROOT_DIR/.venv-ipf}"
if [[ ! -x "$VENV/bin/inference-perf" ]]; then
  "$PYTHON" -m venv "$VENV"
  "$VENV/bin/pip" install --quiet --upgrade pip
  "$VENV/bin/pip" install --quiet inference-perf
fi

template="$ROOT_DIR/config/${SCENARIO}.yaml"
[[ -f "$template" ]] || { echo "unknown scenario: $SCENARIO"; exit 1; }
config_file="$OUTPUT_DIR/config.yaml"
BASE_URL="$BASE_URL" MODEL_NAME="$MODEL_NAME" TOKENIZER="$TOKENIZER" \
  OUTPUT_DIR="$OUTPUT_DIR" SCENARIO="$SCENARIO" \
  envsubst < "$template" > "$config_file"
echo "scenario=$SCENARIO config=$config_file output=$OUTPUT_DIR"

mem_pid=""
if [[ "$DEVICE" == "gpu" ]]; then
  ( while true; do nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits; sleep 5; done ) \
    > "$OUTPUT_DIR/gpu_mem.log" 2>/dev/null &
  mem_pid=$!
elif [[ -n "$CONTAINER" ]]; then
  ( while docker ps -q -f "name=$CONTAINER" >/dev/null 2>&1; do
      docker stats --no-stream --format '{{.MemUsage}}' "$CONTAINER" 2>/dev/null
      sleep 5
    done ) > "$OUTPUT_DIR/mem_samples.log" &
  mem_pid=$!
fi

curl -sf "${BASE_URL}/v1/completions" \
  -H 'Content-Type: application/json' \
  -d "{\"model\":\"${MODEL_NAME}\",\"prompt\":\"Explain quantization in one paragraph.\",\"max_tokens\":128,\"temperature\":0,\"stream\":false}" \
  > "$OUTPUT_DIR/single_stream.json" 2>/dev/null \
  && echo "single-stream raw -> $OUTPUT_DIR/single_stream.json (llama.cpp decode = .timings.predicted_per_second)" \
  || echo "single-stream curl failed (vLLM does not return .timings; use the conc-1 decode from inference-perf)" >&2

"$VENV/bin/inference-perf" --config_file "$config_file" \
  || echo "inference-perf run failed — check $config_file" >&2

[[ -n "$mem_pid" ]] && kill "$mem_pid" 2>/dev/null || true

"$VENV/bin/python" - "$OUTPUT_DIR" <<'PY' || true
import glob, json, os, sys
out = sys.argv[1]
files = sorted(glob.glob(os.path.join(out, "*lifecycle_metrics.json")))
if not files:
    print("no inference-perf report JSON found in", out); sys.exit(0)
print(f"{'stage':>5} {'conc':>5} {'TTFT_ms':>9} {'ITL_ms':>8} {'TPOT_ms':>8} {'decode_t/s':>10} {'outTPS':>8} {'reqLat_s':>9}")
def ms(x): return f"{x*1000:.1f}" if isinstance(x, (int, float)) else "-"
def f2(x): return f"{x:.2f}" if isinstance(x, (int, float)) else "-"
for i, f in enumerate(files):
    d = json.load(open(f))
    conc = (d.get("load_summary") or {}).get("concurrency")
    if conc is None:            # summary file reports concurrency=null — skip it
        continue
    lat = d.get("successes", {}).get("latency", {})
    thr = d.get("successes", {}).get("throughput", {})
    itl = lat.get("inter_token_latency", {}).get("mean")   # seconds
    decode = (1.0 / itl) if itl else None                  # decode tok/s = 1 / ITL_seconds
    print(f"{i:>5} {str(conc):>5} "
          f"{ms(lat.get('time_to_first_token',{}).get('mean')):>9} "
          f"{ms(itl):>8} {ms(lat.get('time_per_output_token',{}).get('mean')):>8} "
          f"{f2(decode):>10} {f2(thr.get('output_tokens_per_sec')):>8} "
          f"{f2(lat.get('request_latency',{}).get('mean')):>9}")
PY

echo "Done. Results in $OUTPUT_DIR"
