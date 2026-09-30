#!/usr/bin/env bash
# Known chart issue 3 (see README): llama-cpp-deployment.yaml renders no tolerations. Add one for the tainted bench node.
# Usage: patch-llamacpp-toleration.sh <deployment> <graviton|gpu> [namespace]
set -euo pipefail
case "${2:-}" in
  graviton|gpu) ;;
  *) echo "usage: $0 <deployment> <graviton|gpu> [namespace]" >&2; exit 1 ;;
esac
kubectl -n "${3:-benchmarking}" patch deployment "$1" --type=json -p "[{\"op\":\"add\",\"path\":\"/spec/template/spec/tolerations\",\"value\":[{\"key\":\"bench\",\"operator\":\"Equal\",\"value\":\"$2\",\"effect\":\"NoSchedule\"}]}]"
