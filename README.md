# AWS Deep Learning Containers Samples

This repository contains sample code and configurations for using AWS Deep Learning Containers (DLCs) in various scenarios. AWS Deep Learning Containers are Docker images pre-installed with deep learning frameworks and tools, optimized for performance on AWS infrastructure.

## Repository Structure

- **vllm-samples/**: Samples for deploying vLLM (a high-throughput serving engine for LLMs) using AWS Deep Learning Containers
  - **deepseek/**: Samples for deploying DeepSeek models
    - **eks/**: Configuration files and instructions for deploying DeepSeek models on Amazon EKS with GPU support, EFA, and FSx Lustre integration

## Featured Samples

### vLLM DeepSeek Model on EKS

Deploy a DeepSeek model using the AWS public vLLM deep learning container ECR image on an Amazon EKS cluster with:
- GPU support (p4d.24xlarge instances with NVIDIA A100 GPUs)
- Elastic Fabric Adapter (EFA) for high-performance networking
- FSx Lustre for persistent model storage
- LeaderWorkerSet pattern for improved node parallelism

See the [vLLM DeepSeek EKS README](vllm-samples/deepseek/eks/README.md) for detailed instructions.

## Getting Started

1. Clone this repository:
   ```bash
   git clone https://github.com/aws-samples/sample-aws-deep-learning-containers.git
   cd sample-aws-deep-learning-containers
   ```

2. Navigate to the sample you want to use:
   ```bash
   cd vllm-samples/deepseek/eks/
   ```

3. Follow the instructions in the sample's README file.

## AWS Deep Learning Containers

AWS Deep Learning Containers provide optimized environments with pre-installed deep learning frameworks and tools:

- **Performance Optimized**: Tuned for maximum performance on AWS infrastructure
- **Pre-configured**: Ready-to-use environments with popular frameworks
- **Regularly Updated**: Latest versions of frameworks and security patches
- **AWS Integration**: Seamless integration with AWS services like EKS, ECS, and SageMaker

Learn more about [AWS Deep Learning Containers](https://aws.amazon.com/machine-learning/containers/).
