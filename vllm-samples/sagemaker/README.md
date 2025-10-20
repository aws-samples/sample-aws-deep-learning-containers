# AWS SageMaker vLLM Inference

Deploy and run inference on vLLM models using AWS SageMaker and vLLM DLC.

## Files

- `endpoint.py` - Deploy vLLM model to SageMaker endpoint
- `inference.py` - Run inference against deployed endpoint

## Prerequisites

- AWS CLI configured with appropriate permissions
- HuggingFace token for model access (if required)

## Setup

### Create IAM Role

```bash
# Create trust policy
cat > trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "sagemaker.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create role
aws iam create-role --role-name SageMakerExecutionRole --assume-role-policy-document file://trust-policy.json

# Attach policies
aws iam attach-role-policy --role-name SageMakerExecutionRole --policy-arn arn:aws:iam::aws:policy/AmazonSageMakerFullAccess
aws iam attach-role-policy --role-name SageMakerExecutionRole --policy-arn arn:aws:iam::aws:policy/AmazonElasticContainerRegistryPublicFullAccess
```

## Quick Start

### 1. Get Latest Image URI

```bash
# Check available images: https://gallery.ecr.aws/deep-learning-containers/vllm
# Get latest vLLM DLC image URI
export CONTAINER_URI="public.ecr.aws/deep-learning-containers/vllm:0.11.0-gpu-py312-cu128-ubuntu22.04-sagemaker-v1.1"
```

### 2. Deploy Endpoint

```bash
# update variables in endpoint.py and run
python endpoint.py
```

### 3. Run Inference

```bash
# update endpoint_name in inference.py and run
python inference.py
```

## Configuration

### Model Parameters
- `SM_VLLM_MODEL` - HuggingFace model ID
- `SM_VLLM_HF_TOKEN` - HuggingFace access token

### Inference Parameters
- `max_tokens` - Maximum response length
- `temperature` - Sampling randomness (0-1)
- `top_p` - Nucleus sampling threshold
- `top_k` - Top-k sampling limit

## Instance Types

Recommended GPU instances:
- `ml.g5.12xlarge` - 4 A10G GPUs, 48 vCPUs, 192 GB RAM
- `ml.g5.24xlarge` - 4 A10G GPUs, 96 vCPUs, 384 GB RAM
- `ml.p4d.24xlarge` - 8 A100 GPUs, 96 vCPUs, 1152 GB RAM

## Test NixlConnector

Test NixlConnector locally - [NixlConnector Documentation](https://docs.vllm.ai/en/latest/features/nixl_connector_usage.html#transport-configuration)

```bash
# Pull latest vLLM DLC for EC2
docker pull public.ecr.aws/deep-learning-containers/vllm:0.11.0-gpu-py312-cu128-ubuntu22.04-sagemaker-v1.1

# Run container with GPU access
docker run -it --entrypoint=/bin/bash --gpus=all \
  -v $(pwd):/workspace \
  public.ecr.aws/deep-learning-containers/vllm:0.11.0-gpu-py312-cu128-ubuntu22.04-sagemaker-v1.1

# Inside container, run the NixlConnector test
export HF_TOKEN= "<TOKEN>"
./testNixlConnector.sh
```

## Cleanup

```python
import boto3
sagemaker = boto3.client('sagemaker')
sagemaker.delete_endpoint(EndpointName='<endpoint-name>')
```