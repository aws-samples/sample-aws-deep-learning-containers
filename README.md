# AWS Deep Learning Containers Samples

This repository contains sample code and configurations for using AWS Deep Learning Containers (DLCs) in various scenarios. AWS Deep Learning Containers are Docker images pre-installed with deep learning frameworks and tools, optimized for performance on AWS infrastructure.

## Repository Structure

- **vllm-samples/**: Samples for deploying vLLM (a high-throughput serving engine for LLMs) using AWS Deep Learning Containers
  - **deepseek/**: Samples for deploying DeepSeek models
    - **eks/**: Configuration files and instructions for deploying DeepSeek models on Amazon EKS with GPU support, EFA, and FSx Lustre integration

- **mlflow/**: Samples for using SageMaker managed MLflow with Deep Learning Containers and Deep Learning AMIs
  - **dlc-with-mlflow/**: Sample for integrating AWS DLCs with SageMaker managed MLflow for training. See [README](mlflow/dlc-with-mlflow/README.md) for detailed instructions.

## AWS Deep Learning Containers

AWS Deep Learning Containers provide optimized environments with pre-installed deep learning frameworks and tools:

- **Performance Optimized**: Tuned for maximum performance on AWS infrastructure
- **Pre-configured**: Ready-to-use environments with popular frameworks
- **Regularly Updated**: Latest versions of frameworks and security patches
- **AWS Integration**: Seamless integration with AWS services like EKS, ECS, and SageMaker

Learn more about [AWS Deep Learning Containers](https://aws.amazon.com/machine-learning/containers/).
