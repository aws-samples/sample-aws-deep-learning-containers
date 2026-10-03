#!/bin/bash
# benchmark_efa_vs_tcp.sh - Run the same FSDP job twice on the same cluster,
# changing only the NCCL transport (EFA/RDMA vs TCP sockets), and compare
# steps/second. Verifies from the worker logs that each run used the intended
# transport, so a silent fallback can't invalidate the comparison.
#
# Usage: bash benchmark_efa_vs_tcp.sh
# Prerequisites: the RayCluster is already running (deploy_ray_train_job.sh).
set -eo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/env.sh"
source "$SCRIPT_DIR/_lib.sh"
CODE_DIR="$(dirname "$SCRIPT_DIR")/code"
REMOTE_CODE_DIR="/tmp/ray-train-code"
SECONDS=0

find_head_pod() {
    local pod
    pod=$(kubectl get pod -n "$NAMESPACE" \
        -l "ray.io/cluster=${RAY_CLUSTER_NAME},ray.io/node-type=head" \
        -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    if [ -z "$pod" ]; then
        print_error "No head pod for RayCluster '$RAY_CLUSTER_NAME'. Deploy it first: bash deploy_ray_train_job.sh"
        exit 1
    fi
    echo "$pod"
}

# Run one pass and echo its mean steps/sec on stdout; progress goes to stderr.
#   $1 = label (EFA|TCP), $2 = runtime env_vars JSON, $3 = head pod
run_pass() {
    local label="$1" env_vars="$2" head_pod="$3"
    print_section "Benchmark run: ${label}" >&2

    # Ray reuses one session dir across both job submits, so NCCL logs from the
    # two runs accumulate in the same files. Drop a marker file on each worker
    # immediately before submitting, then only read worker logs newer than it --
    # otherwise the EFA run's lines leak into the TCP run's grep and vice versa.
    local wpods
    wpods=$(kubectl get pods -n "$NAMESPACE" -l "ray.io/cluster=${RAY_CLUSTER_NAME},ray.io/node-type=worker" -o jsonpath='{.items[*].metadata.name}' 2>/dev/null)
    for wpod in $wpods; do
        kubectl exec "$wpod" -n "$NAMESPACE" -c ray-worker -- touch /tmp/bench_marker 2>/dev/null || true
    done

    set +e
    kubectl exec "$head_pod" -n "$NAMESPACE" -c ray-head -- \
        ray job submit --address http://localhost:8265 --working-dir "$REMOTE_CODE_DIR" \
        --runtime-env-json "{\"pip\": [\"transformers==4.46.3\"], \"env_vars\": ${env_vars}}" -- \
        python3 train.py \
            --model_id "$MODEL_ID" --steps "$BENCH_STEPS" --warmup_steps "$BENCH_WARMUP_STEPS" \
            --seq_len "$SEQ_LEN" --batch_size "$BATCH_SIZE" \
            --learning_rate "$LEARNING_RATE" --num_workers "$NUM_WORKERS" 1>&2
    local job_exit=$?
    set -e
    if [ "$job_exit" -ne 0 ]; then
        print_error "${label} run failed (exit $job_exit)." >&2
        exit "$job_exit"
    fi

    # NCCL transport lines land in the worker-*.out session logs, train.py's
    # steps_per_sec in train/ray-train-app-worker-*.log -- both inside the pod,
    # not on container stdout. Read only files newer than the marker.
    local logs="" efa_line socket_line
    for wpod in $wpods; do
        logs+=$(kubectl exec "$wpod" -n "$NAMESPACE" -c ray-worker -- \
            bash -c 'find /tmp/ray/session_*/logs -newer /tmp/bench_marker \( -name "worker-*.out" -o -name "ray-train-app-worker-*.log" \) -exec grep -hiE "NET/OFI Selected provider|Using network Socket|Selected provider is sockets|steps_per_sec=" {} +' 2>/dev/null || true)
        logs+=$'\n'
    done
    efa_line=$(echo "$logs" | grep -iE "NET/OFI Selected provider is efa" | tail -1 || true)
    socket_line=$(echo "$logs" | grep -iE "Using network Socket|Selected provider is sockets" | tail -1 || true)

    # Require the run's intended transport and reject the other, so a silent
    # fallback (or a TCP override that didn't take) can't pass as a valid run.
    if [ "$label" = "EFA" ]; then
        [ -n "$socket_line" ] && { print_error "EFA run fell back to sockets: $socket_line" >&2; exit 1; }
        [ -z "$efa_line" ] && { print_error "EFA run: no EFA provider line found." >&2; exit 1; }
        print_success "EFA transport confirmed: $efa_line" >&2
    else
        [ -n "$efa_line" ] && { print_error "TCP run still selected EFA: $efa_line" >&2; exit 1; }
        [ -z "$socket_line" ] && { print_error "TCP run: no socket transport line found." >&2; exit 1; }
        print_success "TCP transport confirmed: $socket_line" >&2
    fi

    local per_rank mean
    per_rank=$(echo "$logs" | grep -oE "steps_per_sec=[0-9.]+" | cut -d= -f2 || true)
    if [ -z "$per_rank" ]; then
        print_error "${label} run: no 'steps_per_sec=' line in worker logs." >&2
        exit 1
    fi
    mean=$(echo "$per_rank" | awk '{ s += $1; n++ } END { printf "%.4f", (n ? s / n : 0) }')
    print_success "${label} mean steps/sec: ${mean}" >&2
    echo "$mean"
}

echo -e "${BLUE}"
echo "=================================================="
echo "  Benchmark: EFA/RDMA vs TCP  (multi-node FSDP)"
echo "=================================================="
echo -e "${NC}"
echo "  RayCluster:   $RAY_CLUSTER_NAME"
echo "  Model:        $MODEL_ID"
echo "  Workers:      $GPU_NODE_COUNT x $GPU_NODE_TYPE (${GPUS_PER_NODE} GPU each)"
echo "  Steps/run:    $BENCH_STEPS ($BENCH_WARMUP_STEPS warm-up, excluded)"
echo

check_kubectl_prerequisites rayclusters.ray.io "Install KubeRay first: bash install_kuberay.sh"
HEAD_POD=$(find_head_pod)
print_success "Head pod: $HEAD_POD"

print_section "Syncing training code to head pod"
kubectl exec "$HEAD_POD" -n "$NAMESPACE" -c ray-head -- rm -rf "$REMOTE_CODE_DIR"
kubectl cp "$CODE_DIR" "${NAMESPACE}/${HEAD_POD}:${REMOTE_CODE_DIR}" -c ray-head
print_success "Code synced"

EFA_SPS=$(run_pass "EFA" '{"FI_PROVIDER": "efa", "NCCL_NET_PLUGIN": "ofi", "NCCL_SOCKET_IFNAME": "eth0"}' "$HEAD_POD")
# NCCL_NET=Socket forces NCCL's built-in TCP transport; FI_PROVIDER=tcp and a
# disabled OFI plugin keep libfabric off EFA. This is the degraded path
# deploy_ray_train_job.sh guards against, induced here as the baseline.
TCP_SPS=$(run_pass "TCP" '{"NCCL_NET": "Socket", "NCCL_SOCKET_IFNAME": "eth0", "FI_PROVIDER": "tcp", "NCCL_NET_PLUGIN": "none"}' "$HEAD_POD")

print_section "Results: EFA/RDMA vs TCP"
SPEEDUP=$(awk -v e="$EFA_SPS" -v t="$TCP_SPS" 'BEGIN { printf (t > 0 ? "%.2f" : "n/a", e / t) }')
printf "  %-26s %s\n" "TCP (sockets, baseline)" "$TCP_SPS steps/sec"
printf "  %-26s %s\n" "EFA / RDMA" "$EFA_SPS steps/sec"
echo
echo -e "  ${GREEN}EFA/RDMA speedup vs TCP: ${SPEEDUP}x${NC}"
print_elapsed

awk -v s="$SPEEDUP" 'BEGIN { exit !(s + 0 >= 1.0) }' \
    || print_warning "EFA was not faster than TCP -- re-check the transport lines above, or raise BENCH_STEPS if the run was too short to be stable."
