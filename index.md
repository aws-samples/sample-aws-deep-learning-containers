# Tutorials

Step-by-step guides for using AWS Deep Learning Containers.

## Training

- [EKS Training](training/eks/README.md) - Train models on Amazon EKS with PyTorch FSDP
- [Distributed Fraud Detection](xgboost/fraud-detection-distributed/README.md) - Multi-GPU distributed training with XGBoost and Dask

## Inference

- [vLLM on SageMaker](vllm-samples/sagemaker/README.md) - Deploy vLLM on SageMaker endpoints
- [DeepSeek on EKS](vllm-samples/deepseek/eks/README.md) - Deploy DeepSeek models with vLLM on EKS
- [Fraud Detection Demo](vllm-samples/deepseek/eks/fraud-detection-demo/README.md) - End-to-end fraud detection with DeepSeek
- [Graviton vs GPU LLM Benchmark](inference/graviton-vs-gpu-llm-benchmark/README.md) - Benchmark Qwen3-8B on Graviton CPU, x86 CPU, and x86 GPU with vLLM and llama.cpp DLCs

## Integrations

- [MLflow](mlflow/dlc-with-mlflow/README.md) - Use MLflow with Deep Learning Containers
- [SOCI](SOCI/README.md) - Seekable OCI for faster container startup
