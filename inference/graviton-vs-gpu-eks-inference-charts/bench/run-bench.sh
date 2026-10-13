#!/usr/bin/env bash
# Usage: run-bench.sh <release> <config-template> <service> <model-name>
# Installs benchmark-charts as a helm release, waits, saves logs + JSON reports, uninstalls.
# Env: CHARTS_DIR (ai-on-eks-charts clone, default ./ai-on-eks-charts), AFFINITY (default true),
#      BENCH_TIMEOUT (seconds to wait for the Job, default 3600).
set -uo pipefail
D=$(cd "$(dirname "$0")/.." && pwd)
CHARTS_DIR=${CHARTS_DIR:-$D/ai-on-eks-charts}
BENCH_TIMEOUT=${BENCH_TIMEOUT:-3600}
rel=$1 tpl=$2 svc=$3 model=$4
out=$D/results/$rel; mkdir -p "$out"
sed -e "s|MODEL|$model|" -e "s|URL|http://$svc.benchmarking:8000|" "$tpl" > "$out/config.yml"
export BENCH_CONFIG=$out/config.yml
helm install "$rel" "$CHARTS_DIR/charts/benchmark-charts" -n benchmarking \
  --set benchmark.image.tag=v0.6.1 --set benchmark.serviceAccount.create=false --set benchmark.affinity.enabled=${AFFINITY:-true} \
  --set benchmark.target.modelName="$model" \
  --set benchmark.target.baseUrl="http://$svc.benchmarking:8000" \
  --set benchmark.affinity.targetLabels.app=null \
  --set "benchmark.affinity.targetLabels.app\.kubernetes\.io/component=$svc" \
  --set benchmark.resources.requests.cpu=3 --set benchmark.resources.requests.memory=6Gi \
  --set benchmark.resources.limits.cpu=3.9 --set benchmark.resources.limits.memory=12Gi \
  --post-renderer "$D/bench/postrender.py" > "$out/helm-install.txt" || exit 1
job=$(kubectl -n benchmarking get job -l app.kubernetes.io/instance="$rel" -o name)
if [ -z "$job" ]; then
  echo "no Job found for release $rel" >&2
  helm uninstall "$rel" -n benchmarking >/dev/null
  exit 1
fi
deadline=$((SECONDS + BENCH_TIMEOUT))
while s=$(kubectl -n benchmarking get "$job" -o jsonpath='{.status.succeeded}:{.status.failed}'); [ "$s" = ":" ]; do
  if [ "$SECONDS" -ge "$deadline" ]; then
    echo "timed out after ${BENCH_TIMEOUT}s waiting for $job" >&2
    kubectl -n benchmarking describe "$job" >&2
    kubectl -n benchmarking describe pod -l job-name="${job#*/}" >&2
    break
  fi
  sleep 20
done
kubectl -n benchmarking logs "$job" > "$out/job.log" 2>&1
echo "job $job status succeeded:failed=$s"
helm uninstall "$rel" -n benchmarking >/dev/null
[ -n "${s%%:*}" ] || exit 1
