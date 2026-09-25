# Multi-Node Ray Train on EKS

Run a distributed PyTorch FSDP training job with Ray Train across **two GPU
nodes** on Amazon EKS, using the Ray Train DLC. This is the training
counterpart to
[`inference/ray-serve/ray-serve-multi-node`](../../inference/ray-serve/ray-serve-multi-node):
same KubeRay-on-EKS foundation, but a `RayCluster` running a job to completion
instead of a `RayService` serving traffic.

The [Ray Train DLC](https://aws.github.io/deep-learning-containers/ray-train/)
ships Ray Train, PyTorch, and the EFA stack (libfabric and aws-ofi-nccl)
already built and version-matched, so the worker image needs no build step --
it is a public, pre-built image. That is the thing this sample demonstrates:
getting a correctly-configured multi-node, EFA-backed training job running on
EKS without hand-building any of that stack yourself.

## Success criteria

This sample's bar is infrastructure-level, not training quality -- the
training job itself (loss, convergence, dataset) is out of scope. What
`deploy_ray_train_job.sh` checks and gates on:

| # | Criterion | How it's checked |
| --- | --- | --- |
| 1 | Both GPU nodes advertise their GPUs | `nvidia.com/gpu` allocatable on both nodes |
| 2 | Both GPU nodes advertise EFA | `vpc.amazonaws.com/efa` allocatable on both nodes |
| 3 | The job schedules and runs | head pod Ready, both worker pods Running |
| 4 | NCCL selected the EFA fabric, not sockets | worker logs show `NET/OFI Selected provider is efa`, and *not* `Using network Socket` |
| 5 | EFA's RDMA capability is present | `fi_info -p efa` inside a worker pod reports `FI_RMA`/`FI_EP_RDM` |
| 6 | The job starts and completes | `ray job submit` exits 0; `train.py` prints a `[train] SUCCESS` line per rank |

**On RDMA, precisely:** `g6.12xlarge` is EFA-capable with real, network-level
RDMA (libfabric read/write between hosts), but it does **not** have
GPUDirect RDMA (the NIC DMA'ing straight into GPU memory) -- that requires
`p4d`/`p4de`/`p5`/`p5e`/`p5en`/`p6`/`trn1`. Criterion 5 above confirms the
former; it is not evidence of the latter, and this README does not claim it.

## What this sample builds

Two `g6.12xlarge` GPU worker nodes (4x NVIDIA L4, 48 vCPU, 192 GiB, 1 EFA
interface each), each running 4 Ray Train workers -- `WORLD_SIZE=8` total.
Ray Train's `TorchTrainer` full-parameter fine-tunes
[`Qwen/Qwen2.5-1.5B`](https://huggingface.co/Qwen/Qwen2.5-1.5B) (ungated) with
PyTorch **FSDP**, which shards the model's parameters, gradients, and AdamW
optimizer state across every GPU in the job. Any FSDP all-gather/
reduce-scatter between a rank on one node and a rank on the other crosses the
node boundary over **[EFA](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/efa.html)**.
`code/train.py` trains on synthetic token ids for a handful of steps -- the
point is exercising the real multi-node NCCL/EFA collective path, not
achieving a training result, so there is no dataset to stage.

## Architecture

```
EKS cluster
├── system node group (m7i.xlarge x1)    -- KubeRay operator + Ray head (CPU only)
└── gpu-workers node group (g6.12xlarge x2, EFA-enabled)
    ├── ray-worker pod (4 GPU, 1 EFA interface)  -- Ray Train workers, ranks 0-3
    └── ray-worker pod (4 GPU, 1 EFA interface)  -- Ray Train workers, ranks 4-7
```

## Prerequisites

Install the following tools before running any scripts:

- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html) with credentials configured
- [eksctl](https://eksctl.io/installation/)
- [kubectl](https://kubernetes.io/docs/tasks/tools/)
- [helm](https://helm.sh/docs/intro/install/) to install the KubeRay operator and GPU device plugins
- [envsubst](https://www.gnu.org/software/gettext/) is used to render the manifest

Verify that your AWS credentials are active, and check `g6.12xlarge` capacity
and G-family vCPU quota (2 x g6.12xlarge = 96 vCPU) in your target region
before picking one:

```bash
aws sts get-caller-identity
```

## Directory Structure

```
ray-train/
      scripts/      # Deployment and teardown scripts for EKS, node group, device plugins, KubeRay, and the job
      manifest/     # KubeRay RayCluster manifest
      code/         # The Ray Train training script (train.py)
```

## Configuration

All scripts share a single configuration file: `scripts/env.sh`. Override any
variable by exporting it before running a script.

| Variable | Default | Description |
| --- | --- | --- |
| CLUSTER_NAME | eks-cluster | EKS cluster name |
| REGION | us-east-2 | AWS region |
| K8S_VERSION | 1.36 | Kubernetes version |
| NODE_AMI_FAMILY | AmazonLinux2023 | Node AMI family, set explicitly rather than left to eksctl's default |
| SYSTEM_NODE_TYPE | m7i.xlarge | Instance type for system/head nodes |
| SYSTEM_NODE_COUNT | 1 | Number of system nodes |
| GPU_NODE_TYPE | g6.12xlarge | GPU worker instance type |
| GPU_NODE_COUNT | 2 | Number of GPU worker nodes |
| GPUS_PER_NODE | 4 | GPUs per `GPU_NODE_TYPE` -- must match the instance type if you change it |
| GPU_NODEGROUP_NAME | gpu-workers | Name of the GPU node group |
| GPU_AZ | _(auto)_ | AZ for the GPU node group; auto-discovered when empty |
| DLC_IMAGE | public.ecr.aws/deep-learning-containers/ray:train-ml-cuda | Ray Train DLC image |
| KUBERAY_VERSION | 1.4.0 | KubeRay operator version |
| RAY_VERSION | 2.58.0 | Ray version (must match the image) |
| NVIDIA_DEVICE_PLUGIN_VERSION | 0.20.0 | NVIDIA device plugin Helm chart version |
| EFA_DEVICE_PLUGIN_VERSION | v0.5.32 | AWS EFA device plugin Helm chart version -- confirmed to allowlist `g6.12xlarge` |
| NAMESPACE | ray-train | Kubernetes namespace |
| RAY_CLUSTER_NAME | ray-train-cluster | Name of the RayCluster |
| MODEL_ID | Qwen/Qwen2.5-1.5B | Model fine-tuned by `code/train.py` |
| STEPS | 5 | Optimizer steps -- a correctness smoke test, not a training run |
| SEQ_LEN | 128 | Synthetic sequence length |
| BATCH_SIZE | 1 | Per-worker batch size |
| LEARNING_RATE | 0.00002 | Optimizer learning rate |
| NUM_WORKERS | 0 | Ray Train workers; 0 = auto-size to the cluster's GPU count (8) |

## Step-by-step deployment

```bash
cd scripts
```

### Step 1: Create the EKS cluster

```bash
./deploy_cluster.sh
```

Provisions the EKS cluster (VPC, OIDC, core add-ons) and a CPU **system** node
group (`m7i.xlarge`, `AmazonLinux2023` AMI) that runs system workloads, the
KubeRay operator, and the Ray head. Nodes run in private subnets with
outbound access through a NAT Gateway. Cluster subnets are placed in the
Availability Zones that actually offer `$GPU_NODE_TYPE`, so the GPU node
group always has a usable subnet. Idempotent: safe to re-run if interrupted.
15-20 minutes on a fresh run.

### Step 2: Add GPU worker nodes

```bash
./deploy_node_group.sh
```

Creates the GPU node group: 2x `g6.12xlarge` with EFA enabled, pinned to a
single AZ (EFA cannot cross AZs), labeled `role=gpu-worker` so the Ray workers
target them via a `nodeSelector`, and labeled `nvidia.com/gpu.present=true` so
the NVIDIA device plugin's default affinity matches without needing Node
Feature Discovery. Runs in private subnets with no public IPs. `AmiType` is
resolved automatically to the accelerated, GPU-capable variant of
`NODE_AMI_FAMILY` -- the driver ships with that AMI, but is not yet advertised
to kubelet (that's the device plugin's job, next step). 3-5 minutes.

### Step 3: Install the GPU device plugins

```bash
./install_gpu_plugins.sh
```

The accelerated AMI provides the NVIDIA driver and the EFA kernel module, but
neither is advertised to kubelet as an allocatable resource without a device
plugin DaemonSet -- a fresh cluster has neither installed. This installs both
at pinned versions and waits for both DaemonSets to be Ready on every GPU
node before printing `nvidia.com/gpu`/`vpc.amazonaws.com/efa` allocatable
counts. **A healthy Helm release is not evidence the DaemonSet is running** --
both plugins have their own node-affinity requirements (an instance-type
allowlist for EFA, the `nvidia.com/gpu.present` label for NVIDIA), so this
step verifies the actual DaemonSet status, not just `helm list`. 1-2 minutes.

### Step 4: Install the KubeRay operator

```bash
./install_kuberay.sh
```

Installs the KubeRay operator via Helm, pinned to the system node group.
KubeRay watches the `RayCluster` you apply next and wires the head-to-worker
join automatically. Idempotent. 1-2 minutes.

### Step 5: Deploy the RayCluster and run the training job

```bash
./deploy_ray_train_job.sh
```

This is the sample's test script, and it gates on the success criteria above.
It renders `manifest/raycluster.yaml` and applies it, **re-checks**
`nvidia.com/gpu`/`vpc.amazonaws.com/efa` are allocatable (fails fast here
rather than as an opaque `Pending` timeout if a device plugin didn't
schedule), waits for the head pod to be Ready and both worker pods to be
Running, copies `code/` onto the head pod, then runs:

```bash
ray job submit --address http://localhost:8265 --working-dir /tmp/ray-train-code -- \
    python3 train.py --model_id Qwen/Qwen2.5-1.5B
```

`ray job submit` blocks and streams the job's logs; the script exits non-zero
if the job fails. After the job completes it checks the worker logs for the
EFA confirmation line (and, separately, for the sockets-fallback line -- a
job over TCP looks identical to a healthy one in `kubectl get pods`), then
runs `fi_info -p efa` inside a worker pod to confirm RDMA capability. It exits
non-zero if either check fails, so the whole script works as a CI gate on all
six criteria, not just "the job exited 0."

### Check status

```bash
./deploy_ray_train_job.sh status
```

Shows the RayCluster state, the head + worker pods (with the node each landed
on), and GPU capacity.

## Confirming EFA and RDMA yourself

```bash
# NCCL's transport choice
kubectl logs -n ray-train -l ray.io/node-type=worker -c ray-worker --tail=-1 | grep -iE "NET/OFI|Libfabric|Socket"
```

```
NET/OFI Selected provider is efa, fabric is efa (found 1 nics)
NCCL INFO Using network Libfabric
```

confirms EFA is carrying the collectives. `Using network Socket` or
`Selected provider is sockets` means it is not -- check that the pod requested
`vpc.amazonaws.com/efa`, that the EFA device plugin is Ready on that node,
and that `FI_PROVIDER=efa` reached the container (`kubectl get pod <pod> -o
jsonpath='{.spec.containers[0].env}'`).

```bash
# EFA's RDMA capability (network-level; not GPUDirect)
WPOD=$(kubectl get pod -n ray-train -l ray.io/node-type=worker -o jsonpath='{.items[0].metadata.name}')
kubectl exec "$WPOD" -n ray-train -c ray-worker -- fi_info -p efa
```

Look for `FI_RMA` / `FI_EP_RDM` in the capability flags.

## Beyond this sample

- **True GPUDirect RDMA.** Swap `GPU_NODE_TYPE`/`GPUS_PER_NODE` for a
  `p4d`/`p4de`/`p5`/`p5e`/`p5en`/`p6`/`trn1` instance to exercise transfers
  straight into GPU memory. Everything else in this sample is unchanged;
  only the EFA-vs-TCP bandwidth gap becomes far larger than on `g6`.
- **Placement group.** This sample pins the GPU node group to a single,
  explicitly-resolved AZ, which is EFA's real requirement. A cluster
  placement group additionally tightens physical proximity within that AZ
  for lower, more consistent latency -- worth adding if you're chasing
  bandwidth, not required for the correctness criteria above.
- **Shared storage for real training.** `code/train.py` has no dataset or
  checkpoint to persist, so there's no FSx/S3 dependency here. A real
  training job that stages a dataset/model or checkpoints across worker
  restarts needs shared storage such as FSx for Lustre or an `s3://` URI --
  see the [Ray Train DLC EKS guide](https://aws.github.io/deep-learning-containers/ray-train/deployment/eks/)
  for the FSx-backed manifest shape.

## Teardown (reverse order)

```bash
cd scripts
```

```bash
./delete_ray_train_job.sh        # Delete the RayCluster
./install_kuberay.sh cleanup     # Uninstall the KubeRay operator
./install_gpu_plugins.sh cleanup # Uninstall the GPU device plugins
./delete_node_group.sh           # Delete the GPU node group
./delete_cluster.sh              # Delete the EKS cluster
```

## Cost

Running cost is roughly **$9.50/hr** while the GPU node group is up: 2x
`g6.12xlarge`, the EKS control plane, and a NAT Gateway (no FSx in this
sample). Tear down when not actively working with it.

## Scripts Quick Reference

| Action | Command |
| --- | --- |
| Deploy cluster | `./deploy_cluster.sh` |
| Deploy GPU nodes | `./deploy_node_group.sh` |
| Install GPU device plugins | `./install_gpu_plugins.sh` |
| Install KubeRay | `./install_kuberay.sh` |
| Deploy RayCluster + run training job | `./deploy_ray_train_job.sh` |
| Check status | `./deploy_ray_train_job.sh status` |
| Delete RayCluster | `./delete_ray_train_job.sh` |
| Uninstall KubeRay | `./install_kuberay.sh cleanup` |
| Uninstall GPU device plugins | `./install_gpu_plugins.sh cleanup` |
| Delete GPU nodes | `./delete_node_group.sh` |
| Delete EKS cluster | `./delete_cluster.sh` |

## License

This library is licensed under the MIT-0 License. See the LICENSE file.

## Additional Resources

- [Ray Train DLC overview and EKS deployment guide](https://aws.github.io/deep-learning-containers/ray-train/)
- [Ray Train documentation](https://docs.ray.io/en/latest/train/train.html)
- [KubeRay documentation](https://docs.ray.io/en/latest/cluster/kubernetes/index.html)
- [Amazon EKS User Guide](https://docs.aws.amazon.com/eks/)
- [Amazon EC2 EFA User Guide](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/efa.html)
