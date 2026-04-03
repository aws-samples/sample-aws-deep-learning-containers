# Distributed Fraud Detection with XGBoost and Dask on Amazon SageMaker

Train an XGBoost fraud detection model at scale using **distributed multi-GPU training with Dask** on the SageMaker XGBoost Deep Learning Container in **Algorithm mode**.

## Overview

Fraud detection systems process millions of transactions and must retrain frequently as attack patterns evolve. This tutorial demonstrates how to use SageMaker's built-in XGBoost algorithm with Dask-based distributed GPU training to handle large-scale, imbalanced fraud datasets efficiently.

**What you'll learn:**
- Use the SageMaker XGBoost DLC in Algorithm mode (no custom training script needed)
- Generate a realistic synthetic fraud dataset with class imbalance
- Run distributed multi-GPU training with Dask across multiple GPUs
- Handle class imbalance with `scale_pos_weight`
- Partition data correctly for Dask-based training

**Why distributed GPU training?**
- Train on datasets with millions of rows in minutes instead of hours
- Dask utilizes all GPUs across one or more instances
- Cost-effective — faster training means lower total compute cost
- Available since XGBoost 1.5-1 on SageMaker

## Prerequisites

- AWS account with SageMaker permissions
- AWS CLI configured
- Python 3.8+ with `boto3`, `sagemaker`, `pandas`, `scikit-learn` installed
- An S3 bucket for training data and model artifacts

## Files

- `run_tutorial.py` — End-to-end orchestration: synthetic data generation, training, deployment, inference, cleanup

## Quick Start

### 1. Install Dependencies

```bash
pip install boto3 sagemaker pandas scikit-learn
```

### 2. Set Environment Variables

```bash
export SAGEMAKER_ROLE="arn:aws:iam::<account-id>:role/<SageMakerExecutionRole>"
export S3_BUCKET="<your-s3-bucket>"
```

### 3. Run the Tutorial

```bash
# Single multi-GPU instance (recommended starting point)
python run_tutorial.py \
  --role "$SAGEMAKER_ROLE" \
  --bucket "$S3_BUCKET" \
  --instance-type ml.g5.12xlarge \
  --instance-count 1

# Scale out: 2 multi-GPU instances
python run_tutorial.py \
  --role "$SAGEMAKER_ROLE" \
  --bucket "$S3_BUCKET" \
  --instance-type ml.g5.12xlarge \
  --instance-count 2 \
  --num-samples 2000000
```

## Step-by-Step Walkthrough

### Step 1: Generate Synthetic Fraud Data

The script generates a realistic imbalanced dataset mimicking credit card fraud:
- 30 numerical features (transaction amount, velocity, distance, etc.)
- ~2% fraud rate (configurable)
- Default: 500K transactions, scalable to millions

```python
from sklearn.datasets import make_classification

X, y = make_classification(
    n_samples=500_000,
    n_features=30,
    n_informative=15,
    n_redundant=5,
    weights=[0.98, 0.02],  # 2% fraud rate
    random_state=42,
)
```

### Step 2: Partition Data for Dask

Dask reads each file as a partition, with one Dask worker per GPU. The number of data files should exceed the total GPU count.

```python
# For ml.g5.12xlarge (4 GPUs) × 2 instances = 8 GPUs
# Create 16 partitions (2× GPU count)
num_partitions = num_gpus * 2
```

> **Important:** Dask distributed training only supports **CSV and Parquet** formats. LIBSVM and PROTOBUF will cause the training job to fail.

### Step 3: Launch Distributed GPU Training

```python
from sagemaker.estimator import Estimator

estimator = Estimator(
    image_uri=xgboost_image_uri,  # XGBoost 3.0-5
    role=role,
    instance_count=2,
    instance_type="ml.g5.12xlarge",
    hyperparameters={
        "objective": "binary:logistic",
        "num_round": 200,
        "max_depth": 8,
        "eta": 0.1,
        "tree_method": "gpu_hist",
        "scale_pos_weight": 49,  # ratio of negatives to positives
        "eval_metric": "auc",
        "use_dask_gpu_training": "true",
    },
)

# FullyReplicated — Dask handles data distribution internally
train_input = TrainingInput(s3_data=train_s3_uri, distribution="FullyReplicated")
estimator.fit({"train": train_input, "validation": val_input})
```

Key hyperparameters for distributed GPU training:
- `tree_method: gpu_hist` — enables GPU-accelerated histogram-based training
- `use_dask_gpu_training: "true"` — enables Dask multi-GPU coordination
- `scale_pos_weight: 49` — compensates for 2% fraud rate (98/2 ≈ 49)

### Step 4: Deploy and Test

```python
predictor = estimator.deploy(
    initial_instance_count=1,
    instance_type="ml.m5.large",  # CPU is fine for inference
)
```

### Step 5: Clean Up

```bash
predictor.delete_endpoint()
```

## Instance Selection Guide

| Instance | GPUs | GPU Memory | Best For |
|---|---|---|---|
| ml.g5.xlarge | 1 × A10G | 24 GB | Small datasets, testing |
| ml.g5.12xlarge | 4 × A10G | 96 GB | Medium datasets (recommended) |
| ml.g5.24xlarge | 4 × A10G | 96 GB | Large datasets, more CPU/RAM |

> **XGBoost 3.0-5 note:** P3 instances are **not supported**. Use G4dn or G5 family.

## Dask Training Best Practices

1. **File count:** Create more files than total GPUs (instance_count × GPUs per instance). Too few files underutilizes GPUs; too many degrades performance.
2. **File format:** Use CSV or Parquet only. Parquet column names must be strings.
3. **Distribution:** Set `distribution="FullyReplicated"` or omit it. Do not use `ShardedByS3Key`.
4. **No pipe mode:** Dask does not support pipe mode input.
5. **File sizes:** Aim for roughly equal-sized partitions for balanced GPU utilization.

## XGBoost Version Comparison

| Feature | 1.5-1 | 1.7-1 | 3.0-5 |
|---|---|---|---|
| Dask multi-GPU | ✅ | ✅ | ✅ |
| GPU instance support | P2, P3, G4dn, G5 | P3, G4dn, G5 | G4dn, G5 |
| SageMaker Debugger | ✅ | ✅ | ❌ |

## Cost Estimate

| Configuration | Instance | Training Time (500K rows) | Approximate Cost |
|---|---|---|---|
| 1 × ml.g5.xlarge | 1 GPU | ~8 min | ~$0.14 |
| 1 × ml.g5.12xlarge | 4 GPUs | ~3 min | ~$0.28 |
| 2 × ml.g5.12xlarge | 8 GPUs | ~2 min | ~$0.37 |

> GPU training is faster and often more cost-effective than CPU despite higher per-instance cost.

## References

- [XGBoost Algorithm — Amazon SageMaker AI](https://docs.aws.amazon.com/sagemaker/latest/dg/xgboost.html)
- [SageMaker XGBoost Distributed GPU Training](https://aws.amazon.com/blogs/machine-learning/amazon-sagemaker-xgboost-now-offers-fully-distributed-gpu-training/)
- [Dask Best Practices](https://docs.dask.org/en/stable/best-practices.html)
- [SageMaker XGBoost Container Registry Paths](https://docs.aws.amazon.com/sagemaker/latest/dg-ecr-paths/sagemaker-algo-docker-registry-paths.html)
