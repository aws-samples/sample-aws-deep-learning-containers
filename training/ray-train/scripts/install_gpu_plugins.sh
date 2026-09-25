#!/bin/bash
# install_gpu_plugins.sh - Install the two device plugins the accelerated AMI
# does not run for you: the NVIDIA device plugin (advertises nvidia.com/gpu)
# and the AWS EFA device plugin (advertises vpc.amazonaws.com/efa, injects
# /dev/infiniband). The AMI provides the GPU driver and the EFA kernel
# module/rdma-core; neither is advertised to kubelet without these.
#
# Usage:
#   bash install_gpu_plugins.sh            # Install both
#   bash install_gpu_plugins.sh cleanup    # Uninstall both
#
# Prerequisites: GPU node group running (deploy_node_group.sh), helm installed.

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/env.sh"
source "$SCRIPT_DIR/_lib.sh"

SECONDS=0

check_prerequisites() {
    command -v helm &>/dev/null || { print_error "helm not found. Install: https://helm.sh/docs/intro/install/"; exit 1; }
    check_kubectl_prerequisites
    print_success "Prerequisites satisfied (kubectl, helm)"
}

cleanup() {
    print_section "Uninstalling GPU Device Plugins"
    helm uninstall nvidia-device-plugin -n kube-system 2>/dev/null || true
    helm uninstall aws-efa-k8s-device-plugin -n kube-system 2>/dev/null || true
    print_success "Device plugins uninstalled"
}

if [ "${1:-install}" = "cleanup" ]; then
    check_prerequisites
    cleanup
    exit 0
fi

echo -e "${BLUE}"
echo "=================================================="
echo "  Install GPU Device Plugins"
echo "=================================================="
echo -e "${NC}"
echo "  NVIDIA device plugin: $NVIDIA_DEVICE_PLUGIN_VERSION"
echo "  AWS EFA device plugin: $EFA_DEVICE_PLUGIN_VERSION"
echo

check_prerequisites

print_section "Adding Helm repos"
helm repo add nvdp https://nvidia.github.io/k8s-device-plugin >/dev/null
helm repo add eks https://aws.github.io/eks-charts >/dev/null
helm repo update >/dev/null

print_section "Installing NVIDIA device plugin"
if helm status nvidia-device-plugin -n kube-system &>/dev/null; then
    print_success "NVIDIA device plugin already installed"
else
    # nodeSelector scopes it to GPU nodes; the chart's own affinity on
    # nvidia.com/gpu.present (set on the node group) is the second gate.
    helm install nvidia-device-plugin nvdp/nvidia-device-plugin \
        --version "$NVIDIA_DEVICE_PLUGIN_VERSION" \
        --namespace kube-system \
        --set nodeSelector.role=gpu-worker
    print_success "NVIDIA device plugin installed"
fi

print_section "Installing AWS EFA device plugin"
if helm status aws-efa-k8s-device-plugin -n kube-system &>/dev/null; then
    print_success "AWS EFA device plugin already installed"
else
    # The chart's own affinity also allowlists node.kubernetes.io/instance-type;
    # v0.5.32 is confirmed to include g6.12xlarge (see env.sh).
    helm install aws-efa-k8s-device-plugin eks/aws-efa-k8s-device-plugin \
        --version "$EFA_DEVICE_PLUGIN_VERSION" \
        --namespace kube-system \
        --set nodeSelector.role=gpu-worker
    print_success "AWS EFA device plugin installed"
fi

print_section "Waiting for DaemonSets to be Ready on both GPU nodes"
for _ in $(seq 1 36); do
    NVIDIA_READY=$(kubectl get daemonset nvidia-device-plugin -n kube-system -o jsonpath='{.status.numberReady}' 2>/dev/null || echo 0)
    EFA_READY=$(kubectl get daemonset aws-efa-k8s-device-plugin -n kube-system -o jsonpath='{.status.numberReady}' 2>/dev/null || echo 0)
    if [ "${NVIDIA_READY:-0}" -ge "$GPU_NODE_COUNT" ] && [ "${EFA_READY:-0}" -ge "$GPU_NODE_COUNT" ]; then
        break
    fi
    sleep 5
done

print_section "Allocatable Resources Per GPU Node"
kubectl get nodes -l role=gpu-worker \
    -o custom-columns='NAME:.metadata.name,GPU:.status.allocatable.nvidia\.com/gpu,EFA:.status.allocatable.vpc\.amazonaws\.com/efa'

NVIDIA_READY=$(kubectl get daemonset nvidia-device-plugin -n kube-system -o jsonpath='{.status.numberReady}' 2>/dev/null || echo 0)
EFA_READY=$(kubectl get daemonset aws-efa-k8s-device-plugin -n kube-system -o jsonpath='{.status.numberReady}' 2>/dev/null || echo 0)
if [ "${NVIDIA_READY:-0}" -lt "$GPU_NODE_COUNT" ] || [ "${EFA_READY:-0}" -lt "$GPU_NODE_COUNT" ]; then
    print_error "Not all DaemonSets are Ready on all $GPU_NODE_COUNT GPU node(s) (nvidia=$NVIDIA_READY efa=$EFA_READY). A healthy 'helm status' does not mean the DaemonSet scheduled -- check 'kubectl get pods -n kube-system -l app.kubernetes.io/name=nvidia-device-plugin -o wide' and node labels/affinity."
    exit 1
fi
print_success "Both device plugins Ready on all $GPU_NODE_COUNT GPU node(s)"
print_elapsed
