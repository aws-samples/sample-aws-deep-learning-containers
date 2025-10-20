from sagemaker.model import Model

# Configuration - replace placeholders with actual values
aws_region = "<REGION>"
instance_type = "ml.g5.12xlarge"  # GPU instance for vLLM
iam_role = "<IAM-ROLE>"
endpoint_name = "<NAME>"
container_uri = "<IMAGE_URI>"  # DLC image with vLLM

try:
    print(f"Starting deployment of endpoint: {endpoint_name}")
    print(f"Using image: {container_uri}")
    print(f"Instance type: {instance_type}")

    print("Creating SageMaker model...")

    model = Model(
        name=endpoint_name,
        image_uri=container_uri,
        role="SageMakerRole",
        env={
            "SM_VLLM_MODEL": "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B",  # Model to load
            "SM_VLLM_HF_TOKEN": "<HF-TOKEN>",  # HuggingFace token for model access
        },
    )
    print("Model created successfully")
    print("Starting endpoint deployment (this may take 10-15 minutes)...")

    endpoint_config = model.deploy(
        instance_type=instance_type,
        initial_instance_count=1,
        endpoint_name=endpoint_name,
        wait=False,  # Deploy asynchronously
    )
except Exception as e:
    print(f"Deployment failed: {str(e)}")
