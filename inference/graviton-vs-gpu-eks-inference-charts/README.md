# Graviton CPU vs x86 GPU LLM Benchmark on EKS (inference-charts)

Reproducible benchmark for serving `Qwen/Qwen3-8B` on Amazon EKS with the
[ai-on-eks-charts](https://github.com/awslabs/ai-on-eks-charts) Helm charts and
prebuilt public AWS Deep Learning Container (DLC) images. The model servers are
deployed with `charts/inference-charts`, and load is generated in-cluster with
`charts/benchmark-charts` (a Kubernetes Job running
[inference-perf](https://github.com/kubernetes-sigs/inference-perf)).

The sample compares two engines on two devices, with Graviton as the common point:

- **llama.cpp** serving GGUF quants (Q4_K_M, Q8_0, BF16) on Graviton and on GPU.
- **vLLM** serving the native bf16 checkpoint on Graviton and on GPU.

It ships the cluster definition, one values file per cell, the inference-perf
configs, and the helper scripts. It contains no results; run it to produce your own.

## Test Matrix

| Engine | Graviton CPU (`m8g.4xlarge`) | x86 GPU (`g6e.xlarge`, 1x L40S) |
|---|---|---|
| llama.cpp (`unsloth/Qwen3-8B-GGUF`) | Q4_K_M, Q8_0, BF16 | Q4_K_M, Q8_0, BF16 |
| vLLM (`Qwen/Qwen3-8B`) | bf16 | bf16 |

The workload is fixed-length: 512 input tokens, 128 output tokens, `ignore_eos: true`,
streaming completions. The inference-perf client runs on a separate untainted `system`
node (`m7i.xlarge`) so it never shares CPU with the server, and only one engine runs on
each bench node at a time.

**llama.cpp request slots.** The llama.cpp values files do not set `--parallel`, so
`llama-server` runs its default of 4 slots (`n_slots = 4` in the server log). For llama.cpp
cells, stages above concurrency 4 therefore measure queueing in `llama-server`, not larger
batches. To benchmark batched llama.cpp with N slots, add `--parallel N` and raise
`--ctx-size` so the context fits N concurrent 512 + 128 token requests with headroom, for
example `--parallel 8 --ctx-size 8192`:

- Graviton values files: add `parallel: "8"` and set `ctxSize: "8192"` under `modelParameters`.
- GPU values files: add `--parallel 8 --ctx-size 8192` to `llamaCpp.command`, before the
  trailing `#`.

## Images

All images are pulled from `public.ecr.aws/deep-learning-containers/` and need no
registry login.

| Cell | Image |
|---|---|
| llama.cpp Graviton | `public.ecr.aws/deep-learning-containers/llama-cpp-arm64:server-cpu-v1` |
| llama.cpp GPU | `public.ecr.aws/deep-learning-containers/llama-cpp:server-cuda-v1` |
| vLLM Graviton | `public.ecr.aws/deep-learning-containers/vllm-arm64:server-cpu-v1` |
| vLLM GPU | `public.ecr.aws/deep-learning-containers/vllm:server-cuda-v2` |

The tags are floating major-version tags. Pin a full version tag in the values files if
you need an exactly repeatable run.

## Prerequisites

- An AWS account with permission to create EKS clusters and EC2 instances
  (`m8g.4xlarge`, `g6e.xlarge`, `m7i.xlarge`) in your chosen Region.
- Local tools: AWS CLI v2, `eksctl`, `kubectl`, **Helm 3** (the benchmark uses an
  executable `--post-renderer`, which Helm 4 only accepts as a plugin), `git`, `jq`,
  `envsubst` (from `gettext`), and `python3` with PyYAML (`pip install 'pyyaml>=6,<7'`) for the
  post-renderer.
- Hugging Face access to `Qwen/Qwen3-8B` and `unsloth/Qwen3-8B-GGUF`. Both are ungated, so
  no token is needed. Set `HF_TOKEN` only if you swap in a gated model.

## Directory Structure

```
graviton-vs-gpu-eks-inference-charts/
├── README.md
├── cluster.yaml                      # eksctl cluster (render with envsubst)
├── values/                           # one inference-charts values file per cell
│   ├── llamacpp-graviton-{q4-k-m,q8-0,bf16}.yaml
│   ├── llamacpp-gpu-{q4-k-m,q8-0,bf16}.yaml
│   ├── vllm-graviton-bf16.yaml
│   └── vllm-gpu-bf16.yaml
├── bench/
│   ├── cpu-concurrent.yaml           # concurrency sweep for Graviton cells
│   ├── cpu-bf16-short.yaml           # optional two-stage sweep for cells with high per-request latency
│   ├── gpu-concurrent.yaml           # concurrency sweep for GPU cells
│   ├── gpu-rate.yaml                 # Poisson rate sweep for the vLLM GPU cell
│   ├── run-bench.sh                  # install benchmark-charts, wait, save logs, uninstall
│   ├── postrender.py                 # helm post-renderer, see known chart issues 5 and 6
│   ├── parse.py                      # job log to per-stage markdown table
│   ├── curl-decode.sh                # isolated single-stream decode tokens/s
│   └── peakmem.sh                    # server peak RSS, plus GPU memory on GPU nodes
└── scripts/
    └── patch-llamacpp-toleration.sh  # see known chart issue 3
```

Run all commands from this directory (`inference/graviton-vs-gpu-eks-inference-charts/`).

## Step 1: Create the Cluster

Pick a Region and one Availability Zone that offers all three instance types:

```bash
export AWS_REGION=us-west-2          # your Region
export CLUSTER_NAME=llm-bench        # any name
export EKS_VERSION=1.35              # a version supported by EKS and your eksctl

aws ec2 describe-instance-type-offerings --region "$AWS_REGION" \
  --location-type availability-zone \
  --filters Name=instance-type,Values=m8g.4xlarge,g6e.xlarge,m7i.xlarge \
  --query 'InstanceTypeOfferings[].[Location,InstanceType]' --output text | sort

export AWS_AZ=<zone offering all three>     # all nodegroups go here
export AWS_AZ_2=<any other zone>            # only used for control plane subnets
```

Create the cluster:

```bash
envsubst < cluster.yaml | eksctl create cluster -f -
```

`cluster.yaml` creates three managed nodegroups in `$AWS_AZ`:

| Nodegroup | Instance | Taint | Runs |
|---|---|---|---|
| `graviton` | `m8g.4xlarge` | `bench=graviton:NoSchedule` | Graviton model servers |
| `gpu` | `g6e.xlarge` | `bench=gpu:NoSchedule` | GPU model servers |
| `system` | `m7i.xlarge` | none | add-ons, inference-perf job, curl pod |

The taints keep the benchmark client off the bench nodes. eksctl installs the NVIDIA
device plugin for the GPU nodegroup; confirm the GPU is schedulable:

```bash
kubectl get nodes -l bench=gpu -o jsonpath='{.items[0].status.allocatable.nvidia\.com/gpu}{"\n"}'
```

## Step 2: Prepare the Cluster

Clone the charts at the pinned commit (chart `inference-charts` 0.2.7) inside this
directory, which is where `bench/run-bench.sh` looks by default (override with `CHARTS_DIR`):

```bash
git clone https://github.com/awslabs/ai-on-eks-charts.git
git -C ai-on-eks-charts checkout 21fda29
export CHARTS_DIR=$PWD/ai-on-eks-charts
```

Create the namespace and the objects the charts expect:

```bash
kubectl create namespace benchmarking

# Both deployment templates require this secret even for ungated models (issue 11).
# Reading the token from stdin keeps it out of your shell history and process list.
printf %s "${HF_TOKEN:-}" | kubectl -n benchmarking create secret generic hf-token --from-file=token=/dev/stdin

# benchmark-charts runs as this service account; create it once (issue 7).
kubectl -n benchmarking create serviceaccount inference-perf-sa

# Client pod for health checks and single-stream decode measurements. The bench nodes
# are tainted, so it lands on the system node.
kubectl -n benchmarking run curlpod --image=public.ecr.aws/amazonlinux/amazonlinux:2023 \
  --restart=Never --command -- sleep infinity
kubectl -n benchmarking wait --for=condition=Ready pod/curlpod --timeout=5m
```

## Step 3: Deploy a Cell

Each cell is one Helm release of `inference-charts`. Use the service name as the release
name:

| Cell | Values file | Service (`SVC`) | Model name (`MODEL`) | Bench config |
|---|---|---|---|---|
| llama.cpp Graviton Q4_K_M | `values/llamacpp-graviton-q4-k-m.yaml` | `llamacpp-grv-q4-k-m` | `unsloth/Qwen3-8B-GGUF:Q4_K_M` | `bench/cpu-concurrent.yaml` |
| llama.cpp Graviton Q8_0 | `values/llamacpp-graviton-q8-0.yaml` | `llamacpp-grv-q8-0` | `unsloth/Qwen3-8B-GGUF:Q8_0` | `bench/cpu-concurrent.yaml` |
| llama.cpp Graviton BF16 | `values/llamacpp-graviton-bf16.yaml` | `llamacpp-grv-bf16` | `unsloth/Qwen3-8B-GGUF:BF16` | none by default; see [Cells with high per-request latency](#cells-with-high-per-request-latency) |
| llama.cpp GPU Q4_K_M | `values/llamacpp-gpu-q4-k-m.yaml` | `llamacpp-gpu-q4-k-m` | `unsloth/Qwen3-8B-GGUF:Q4_K_M` | `bench/gpu-concurrent.yaml` |
| llama.cpp GPU Q8_0 | `values/llamacpp-gpu-q8-0.yaml` | `llamacpp-gpu-q8-0` | `unsloth/Qwen3-8B-GGUF:Q8_0` | `bench/gpu-concurrent.yaml` |
| llama.cpp GPU BF16 | `values/llamacpp-gpu-bf16.yaml` | `llamacpp-gpu-bf16` | `unsloth/Qwen3-8B-GGUF:BF16` | `bench/gpu-concurrent.yaml` |
| vLLM Graviton bf16 | `values/vllm-graviton-bf16.yaml` | `vllm-grv-bf16` | `Qwen/Qwen3-8B` | `bench/cpu-concurrent.yaml` |
| vLLM GPU bf16 | `values/vllm-gpu-bf16.yaml` | `vllm-gpu-bf16` | `Qwen/Qwen3-8B` | `bench/gpu-concurrent.yaml`, `bench/gpu-rate.yaml` |

### vLLM cells

The vLLM values files set the bench-node toleration and a startup probe, so a rollout
wait is enough:

```bash
SVC=vllm-gpu-bf16 MODEL=Qwen/Qwen3-8B VALUES=values/vllm-gpu-bf16.yaml BENCH=bench/gpu-concurrent.yaml
# Graviton: SVC=vllm-grv-bf16 MODEL=Qwen/Qwen3-8B VALUES=values/vllm-graviton-bf16.yaml BENCH=bench/cpu-concurrent.yaml
helm install "$SVC" "$CHARTS_DIR/charts/inference-charts" -n benchmarking -f "$VALUES"
kubectl -n benchmarking rollout status "deploy/$SVC" --timeout=30m
```

### llama.cpp cells

The llama.cpp template renders no tolerations (issue 3) and no probes (issue 10). Patch
in the toleration after install, then poll `/health` until the GGUF download finishes:

```bash
SVC=llamacpp-grv-q4-k-m MODEL=unsloth/Qwen3-8B-GGUF:Q4_K_M
VALUES=values/llamacpp-graviton-q4-k-m.yaml NODE=graviton BENCH=bench/cpu-concurrent.yaml
# GPU cells: NODE=gpu BENCH=bench/gpu-concurrent.yaml, with the matching SVC, MODEL, VALUES
helm install "$SVC" "$CHARTS_DIR/charts/inference-charts" -n benchmarking -f "$VALUES"
scripts/patch-llamacpp-toleration.sh "$SVC" "$NODE"
kubectl -n benchmarking rollout status "deploy/$SVC" --timeout=15m
until kubectl -n benchmarking exec curlpod -- curl -sf "http://$SVC:8000/health"; do sleep 15; done; echo
```

Uninstall a cell (`helm uninstall "$SVC" -n benchmarking`) before deploying the next one
on the same node.

## Step 4: Run the Benchmark

`bench/run-bench.sh <release> <config> <service> <model>` renders the config template,
installs `benchmark-charts` with the post-renderer, waits for the Job, saves its log, and
uninstalls the release:

```bash
bench/run-bench.sh "b-$SVC" "$BENCH" "$SVC" "$MODEL"
```

The script waits up to `BENCH_TIMEOUT` seconds (default 3600) for the Job, prints
`kubectl describe` output if the deadline passes, and exits non-zero unless the Job
succeeded. For the vLLM GPU cell, also run the rate sweep under a distinct release name:

```bash
bench/run-bench.sh "b-$SVC-rate" bench/gpu-rate.yaml "$SVC" "$MODEL"
```

The benchmark pod uses a required same-zone pod affinity to the server. With all
nodegroups in `$AWS_AZ` this schedules normally; if your nodes end up in different zones,
set `AFFINITY=false` (issue 8).

### Config choice

- Graviton cells use `cpu-concurrent.yaml`, a fixed-**concurrency** sweep (1, 2, 4, 8), so
  every stage has a bounded number of in-flight requests.
- GPU cells use `gpu-concurrent.yaml`, a fixed-concurrency sweep up to 64.
- The vLLM GPU cell also runs `gpu-rate.yaml`, a Poisson arrival-rate sweep.

### Cells with high per-request latency

The llama.cpp Graviton BF16 cell is measured without a load sweep:

- **Single-stream decode:** `bench/curl-decode.sh` (Step 5).
- **Prefill:** the timings `llama-server` logs after each request. The `prompt eval time`
  line gives prompt tokens and prefill time, and the `eval time` line gives decode time:

  ```bash
  kubectl -n benchmarking logs "deploy/$SVC" | grep -E 'prompt eval time|eval time'
  ```

  The `curl-decode.sh` prompt is only a few tokens long. For prefill at the benchmark's
  512-token prompt length, read the timings of a request from `bench/cpu-bf16-short.yaml`.

`bench/cpu-bf16-short.yaml` (concurrency 1, then 4) is optional for this cell. A full
512 + 128 token request takes several minutes there, so set `BENCH_TIMEOUT` accordingly.

## Step 5: Collect Results

Each run writes `results/<release>/` with `config.yml`, `helm-install.txt`, and `job.log`.
The post-renderer makes the Job print every inference-perf JSON report into its log
between `=====BEGIN` and `=====END` markers. Summarize one run as a markdown table:

```bash
bench/parse.py "results/b-$SVC/job.log"
```

Columns are p50 TTFT, p50 inter-token latency, per-user tokens/s (`1 / ITL`), aggregate
output tokens/s, and p50 request latency, one row per stage.

With the cell still deployed, take two more measurements from the system node:

```bash
# Isolated single-stream decode: times a 1-token and a 129-token completion and reports
# 128 / (t129 - t1). For llama.cpp it also prints .timings.predicted_per_second.
bench/curl-decode.sh "$SVC" "$MODEL" 3 | tee "results/curl-$SVC.txt"

# Peak server memory (VmHWM), plus GPU memory used on GPU nodes. Run after the load test.
bench/peakmem.sh "$SVC" | tee "results/mem-$SVC.txt"
```

For cost comparisons, compute `instance $/hr / (output tokens/s * 3600) * 1e6` for dollars
per 1M output tokens using your Region's on-demand price.

## Step 6: Teardown

```bash
helm -n benchmarking list -q | xargs -r -n1 helm -n benchmarking uninstall
kubectl delete namespace benchmarking
eksctl delete cluster --name "$CLUSTER_NAME" --region "$AWS_REGION"
```

Between sessions you can keep the cluster and scale the bench nodegroups to zero instead:

```bash
eksctl scale nodegroup --cluster "$CLUSTER_NAME" --region "$AWS_REGION" --name gpu --nodes 0
eksctl scale nodegroup --cluster "$CLUSTER_NAME" --region "$AWS_REGION" --name graviton --nodes 0
```

## Known Chart Issues and Workarounds

Found with `ai-on-eks-charts` at commit `21fda29` (`inference-charts` 0.2.7). Each item
names the workaround this sample uses. Some are built into the values files and scripts,
some are manual steps in the instructions above (issues 3, 7, 10, and 11), and issue 12
has no workaround here.

1. **Numeric `modelParameters` render as `%!s(float64=...)`.** The helper formats
   non-string values with `printf "--%s %s"`. Quote every number, for example
   `ctxSize: "4096"`.
2. **`llama-cpp` with `accelerator: gpu` appends `--tensor-parallel-size 1`,** which
   `llama-server` rejects. The GPU llama.cpp values files set the full command in
   `llamaCpp.command` and end it with ` #`. The template renders the container args as a
   plain YAML scalar, so the YAML parser treats ` #` and everything after it, including the
   appended flags, as a comment.
3. **`llama-cpp-deployment.yaml` renders no `tolerations`, and `benchmark-charts` has no
   `nodeSelector`.** The bench nodes are tainted, the vLLM values set `tolerations`, and
   llama.cpp deployments get a toleration from `scripts/patch-llamacpp-toleration.sh`
   after install (Step 3). The inference-perf Job can then only land on the untainted
   `system` node.
4. **Raising `resources.graviton.requests.cpu` alone fails validation.** The defaults are
   `requests.cpu: 4` and `limits.cpu: 8`, and Helm deep-merges maps, so a request of 15
   keeps the limit of 8 and the API server rejects the Deployment. The Graviton values
   files set `limits: {cpu: null, memory: ...}` explicitly.
5. **`benchmark-charts` config.yml is a fixed template** that only emits rate-based stages
   (`{rate, duration}`), `data.type: synthetic`, and S3 storage. It cannot express
   `load.type: concurrent`, fixed input/output distributions, `report:`, or local storage.
   `bench/postrender.py`, used as a `helm --post-renderer`, replaces config.yml with the
   hand-written config from `bench/` and rewrites the Job command.
6. **The only results sink is S3** (`storage.simple_storage_service`). Without a writable
   bucket and IRSA the reports are unreachable. The post-renderer appends a loop that
   prints `/tmp/reports/*.json` to the pod log.
7. **`benchmark.serviceAccount.create: true` cannot adopt an existing `inference-perf-sa`**
   (for example one created by eksctl for IRSA). Install fails with "invalid ownership
   metadata". Step 2 creates the service account, and `run-bench.sh` passes
   `--set benchmark.serviceAccount.create=false`.
8. **`benchmark.affinity` does not work as shipped.** It defaults to
   `targetLabels: {app: qwen3-vllm}`, a label inference-charts never sets (its pods carry
   `app.kubernetes.io/component: <serviceName>`), and because Helm merges maps the default
   must be nulled rather than replaced. The rule is also a required same-zone pod affinity,
   so the benchmark pod stays Pending if server and client nodes are in different zones.
   `run-bench.sh` nulls the default label, targets `app.kubernetes.io/component`, and honors
   `AFFINITY=false`.
9. **`benchmark.image.tag` defaults to an old inference-perf (`v0.2.0`).** The configs in
   `bench/` need a recent release; `run-bench.sh` pins `v0.6.1`.
10. **`llama-cpp-deployment.yaml` renders no startup, readiness, or liveness probe,** so the
    Service routes traffic while `llama-server` is still downloading the GGUF. Step 3 polls
    `/health` before benchmarking. The vLLM template does render a startup probe.
11. **Both deployment templates reference the `hf-token` secret through a non-optional
    `secretKeyRef`,** so even an ungated model needs the secret to exist or the pod never
    starts. Step 2 creates it, empty if `HF_TOKEN` is unset.
12. **The token env var name differs between templates.** `vllm-deployment.yaml` exposes
    the secret as `HF_TOKEN`, while `llama-cpp-deployment.yaml` exposes it as
    `HUGGING_FACE_HUB_TOKEN`. `llama-server` reads `HF_TOKEN` for `-hf` downloads, so a
    gated GGUF repository may fail to download on the llama.cpp cells. This has not been
    verified against the llama.cpp DLC image, because both models in this sample are
    ungated. If you use a gated GGUF repository, check the server log for authentication
    errors first.

## References

- ai-on-eks-charts: https://github.com/awslabs/ai-on-eks-charts
- inference-perf: https://github.com/kubernetes-sigs/inference-perf
- eksctl: https://eksctl.io/
- vLLM: https://docs.vllm.ai/
- llama.cpp: https://github.com/ggml-org/llama.cpp
- Qwen3-8B: https://huggingface.co/Qwen/Qwen3-8B
- Qwen3-8B GGUF: https://huggingface.co/unsloth/Qwen3-8B-GGUF
