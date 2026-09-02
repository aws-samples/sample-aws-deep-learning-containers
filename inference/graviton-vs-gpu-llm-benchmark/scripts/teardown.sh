#!/usr/bin/env bash
# Stop and remove the benchmark containers.
# NOTE: terminating the EC2 instance itself is a manual step (see README Teardown).
set -euo pipefail

for name in vllm-bench llamacpp-bench "$@"; do
  [[ -n "$name" ]] || continue
  docker rm -f "$name" 2>/dev/null && echo "removed $name" || true
done
echo "Containers removed. Remember to terminate the EC2 instance to stop billing."
