#!/usr/bin/env bash
# Usage: curl-decode.sh <service> <model> [n=3]. Isolated single-stream requests from the curl pod on the system node.
# decode_tps: llama.cpp .timings.predicted_per_second. wall_decode_tps: 128/(t(129 tok) - t(1 tok)),
# engine-agnostic (used for vLLM, which returns no timings).
set -euo pipefail
svc=$1 model=$2 n=${3:-3}
k=(kubectl -n benchmarking exec curlpod --)

chat=$(jq -nc --arg m "$model" \
  '{model: $m, messages: [{role: "user", content: "What is the capital of France? Answer in one word. /no_think"}], max_tokens: 32}')
"${k[@]}" curl -s "http://$svc:8000/v1/chat/completions" -H 'Content-Type: application/json' -d "$chat" \
  | jq -r '"SANITY: " + (.choices[0].message.content | gsub("\n"; " "))'

req() {
  local body
  body=$(jq -nc --arg m "$model" --argjson t "$1" \
    '{model: $m, prompt: "Write a long story about a lighthouse keeper.", max_tokens: $t, ignore_eos: true, temperature: 0}')
  "${k[@]}" curl -s -o /tmp/r.json -w '%{time_total}' "http://$svc:8000/v1/completions" -H 'Content-Type: application/json' -d "$body"
}

req 8 >/dev/null  # warmup
for _ in $(seq 1 "$n"); do
  t1=$(req 1); t129=$(req 129); body=$("${k[@]}" cat /tmp/r.json)
  jq -c --arg a "$t1" --arg b "$t129" \
    '{t1_s: ($a|tonumber), t129_s: ($b|tonumber), tokens: .usage.completion_tokens,
      wall_decode_tps: (128 / (($b|tonumber) - ($a|tonumber))), decode_tps: .timings.predicted_per_second}' <<<"$body"
done
