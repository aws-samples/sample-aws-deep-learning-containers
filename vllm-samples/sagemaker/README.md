# AWS SageMaker vLLM Inference

Deploy and run inference on vLLM models using AWS SageMaker and vLLM DLC.

## Files

- `deploy_and_test_sm_endpoint.py` - Complete workflow: deploy, inference, and cleanup
- `testNixlConnector.sh` - Multi-GPU NixlConnector test script

## Prerequisites

- AWS CLI configured with appropriate permissions
- HuggingFace token for model access (if required)

## Setup

### Create IAM Role

```bash
# Create role
aws iam create-role --role-name SageMakerExecutionRole

# Attach policies
aws iam attach-role-policy --role-name SageMakerExecutionRole --policy-arn arn:aws:iam::aws:policy/AmazonSageMakerFullAccess
aws iam attach-role-policy --role-name SageMakerExecutionRole --policy-arn arn:aws:iam::aws:policy/AmazonElasticContainerRegistryPublicFullAccess
```

## Quick Start

### 1. Set Environment Variables

```bash
# Check available images: https://gallery.ecr.aws/deep-learning-containers/vllm
export CONTAINER_URI="public.ecr.aws/deep-learning-containers/vllm:0.11.0-gpu-py312-cu128-ubuntu22.04-sagemaker-v1.1"
export IAM_ROLE="SageMakerExecutionRole"
export HF_TOKEN="your-huggingface-token" 
```

### 2. Run Complete Workflow

```bash
# Deploy, run inference, and cleanup automatically
python deploy_and_test_sm_endpoint.py --endpoint-name vllm-test-$(date +%s) --prompt "Write a Python function to calculate fibonacci numbers"

# Alternate with custom parameters
python deploy_and_test_sm_endpoint.py \
  --endpoint-name my-vllm-endpoint \
  --model-id deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B \
  --instance-type ml.g5.12xlarge \
  --prompt "Explain machine learning" \
  --max-tokens 1000 \
  --temperature 0.7
```

## Command Line Options

- `--endpoint-name` - SageMaker endpoint name (required)
- `--container-uri` - DLC image URI (default from env)
- `--iam-role` - IAM role ARN (default from env)
- `--instance-type` - Instance type (default: ml.g5.12xlarge)
- `--model-id` - HuggingFace model ID (default: deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B)
- `--hf-token` - HuggingFace token (default from env)
- `--prompt` - Inference prompt (default: code generation example)
- `--max-tokens` - Maximum response length (default: 2400)
- `--temperature` - Sampling randomness 0-1 (default: 0.01)

## Instance Types

Recommended GPU instances:
- `ml.g5.12xlarge` - 4 A10G GPUs, 48 vCPUs, 192 GB RAM
- `ml.g5.24xlarge` - 4 A10G GPUs, 96 vCPUs, 384 GB RAM
- `ml.p4d.24xlarge` - 8 A100 GPUs, 96 vCPUs, 1152 GB RAM

## Test NixlConnector

Test NixlConnector locally - [NixlConnector Documentation](https://docs.vllm.ai/en/latest/features/nixl_connector_usage.html#transport-configuration)

```bash
# Pull latest vLLM DLC for EC2
docker pull public.ecr.aws/deep-learning-containers/vllm:0.11-gpu-py312

# Run container with GPU access
docker run -it --entrypoint=/bin/bash --gpus=all \
  -v $(pwd):/workspace \
  public.ecr.aws/deep-learning-containers/vllm:0.11-gpu-py312

# Inside container, run the NixlConnector test
export HF_TOKEN= "<TOKEN>"
./testNixlConnector.sh
```

## Notes

- The script automatically cleans up resources after inference to avoid ongoing costs
- Deployment waits for endpoint to be ready before running inference
- All parameters can be set via environment variables or command line arguments