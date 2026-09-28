#!/bin/bash
# env.sh - Single source of truth for all shared variables. No side effects.
# Usage: source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

export CLUSTER_NAME=${CLUSTER_NAME:-"eks-cluster"}
export REGION=${REGION:-"us-east-2"}
export K8S_VERSION=${K8S_VERSION:-"1.36"}
# AL2 AMIs aren't released for K8s 1.33+ anyway, but this is set explicitly
# rather than left to eksctl's default so it can't silently change.
export NODE_AMI_FAMILY=${NODE_AMI_FAMILY:-"AmazonLinux2023"}
export AWS_REGION="$REGION"
export AWS_DEFAULT_REGION="$REGION"
export NAMESPACE=${NAMESPACE:-"ray-train"}

export SYSTEM_NODE_TYPE=${SYSTEM_NODE_TYPE:-"m7i.xlarge"}
export SYSTEM_NODE_COUNT=${SYSTEM_NODE_COUNT:-1}

# g6.12xlarge: 4x NVIDIA L4, 48 vCPU, 192 GiB, 1 EFA interface. EFA cannot
# cross AZs, so the GPU node group is pinned to a single AZ; GPU_AZ is
# auto-discovered when empty. Two nodes -> WORLD_SIZE=8, the smallest cluster
# that exercises cross-node NCCL/EFA collectives during training.
export GPU_NODE_TYPE=${GPU_NODE_TYPE:-"g6.12xlarge"}
export GPU_NODE_COUNT=${GPU_NODE_COUNT:-2}
export GPUS_PER_NODE=${GPUS_PER_NODE:-4}
export GPU_NODEGROUP_NAME=${GPU_NODEGROUP_NAME:-"gpu-workers"}
export GPU_AZ=${GPU_AZ:-""}

# Public DLC image: no ECR auth needed. Ray Train, PyTorch, and the EFA stack
# (libfabric, aws-ofi-nccl) all ship in the image.
export DLC_IMAGE=${DLC_IMAGE:-"public.ecr.aws/deep-learning-containers/ray:train-ml-cuda"}

export KUBERAY_VERSION=${KUBERAY_VERSION:-"1.4.0"}
# Must match the Ray version installed in DLC_IMAGE.
export RAY_VERSION=${RAY_VERSION:-"2.58.0"}
export RAY_CLUSTER_NAME=${RAY_CLUSTER_NAME:-"ray-train-cluster"}

# Pinned, not "latest": floating these is how a working cluster silently
# becomes a broken one later. The EFA plugin chart affinities on an explicit
# node.kubernetes.io/instance-type allowlist -- v0.5.32 is confirmed to
# include g6.12xlarge.
export NVIDIA_DEVICE_PLUGIN_VERSION=${NVIDIA_DEVICE_PLUGIN_VERSION:-"0.20.0"}
export EFA_DEVICE_PLUGIN_VERSION=${EFA_DEVICE_PLUGIN_VERSION:-"v0.5.32"}

# FSDP fine-tune of an ungated ~1.5B-param causal LM (see ../code/train.py).
export MODEL_ID=${MODEL_ID:-"Qwen/Qwen2.5-1.5B"}
export STEPS=${STEPS:-5}
export SEQ_LEN=${SEQ_LEN:-128}
export BATCH_SIZE=${BATCH_SIZE:-1}
export LEARNING_RATE=${LEARNING_RATE:-0.00002}
# 0 = auto-size Ray Train workers to the cluster's GPU count.
export NUM_WORKERS=${NUM_WORKERS:-0}

# Benchmark (benchmark_efa_vs_tcp.sh): larger than STEPS for a stable steps/sec;
# the first BENCH_WARMUP_STEPS are timed but discarded (one-off warm-up costs).
export BENCH_STEPS=${BENCH_STEPS:-20}
export BENCH_WARMUP_STEPS=${BENCH_WARMUP_STEPS:-3}
