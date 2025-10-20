import json
import sagemaker
from sagemaker import serializers
from sagemaker.predictor import Predictor


def invoke_endpoint(endpoint_name, prompt, max_tokens=2400, temperature=0.01):
    """Invoke SageMaker endpoint with vLLM model for text generation"""
    try:
        predictor = Predictor(
            endpoint_name=endpoint_name,
            serializer=serializers.JSONSerializer(),
        )

        payload = {
            "messages": [{"role": "user", "content": prompt}],  # Chat format
            "max_tokens": max_tokens,  # Response length limit
            "temperature": temperature,  # Randomness (0=deterministic, 1=creative)
            "top_p": 0.9,  # Nucleus sampling
            "top_k": 50,  # Top-k sampling
        }

        response = predictor.predict(payload)

        # Handle different response formats
        if isinstance(response, bytes):
            response = response.decode("utf-8")

        if isinstance(response, str):
            try:
                response = json.loads(response)
            except json.JSONDecodeError:
                print("Warning: Response is not valid JSON. Returning as string.")

        return response

    except Exception as e:
        print(f"Inference failed: {str(e)}")
        return None


def main():
    endpoint_name = "<NAME>"  # Replace with actual endpoint name

    # Sample prompt for testing
    test_prompt = "Write a python code to generate n prime numbers"

    print("Sending request to endpoint...")
    response = invoke_endpoint(
        endpoint_name=endpoint_name,
        prompt=test_prompt,
        max_tokens=2400,  # Adjust based on expected response length
        temperature=0.01,  # Low temperature for consistent code generation
    )

    if response:
        print("\nResponse from endpoint:")
        if isinstance(response, (dict, list)):
            print(json.dumps(response, indent=2))
        else:
            print(response)
    else:
        print("No response received from the endpoint.")


if __name__ == "__main__":
    main()
