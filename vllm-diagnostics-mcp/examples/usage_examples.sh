#!/bin/bash
# Example usage of vLLM Diagnostics CLI

echo "=== vLLM Diagnostics CLI Examples ==="

echo -e "\n1. Get system specifications:"
python cli.py get-system-specs

echo -e "\n2. Get system specs in JSON format:"
python cli.py get-system-specs --json-output

echo -e "\n3. List available vLLM endpoints (default localhost:8000):"
python cli.py list-endpoints

echo -e "\n4. List endpoints for custom vLLM URL:"
python cli.py list-endpoints --vllm-url http://your-vllm-server:8000

echo -e "\n5. Get loaded models:"
python cli.py get-loaded-models

echo -e "\n6. Check capacity for Llama-2-7B:"
python cli.py check-capacity --model-name meta-llama/Llama-2-7b-hf

echo -e "\n7. Check capacity with custom model size:"
python cli.py check-capacity --model-name custom-model --model-size-gb 15.5 --batch-size 4

echo -e "\n8. Test connection to vLLM server:"
python cli.py test-connection

echo -e "\n9. Test connection to custom vLLM URL:"
python cli.py test-connection --vllm-url http://your-vllm-server:8000

echo -e "\n=== Docker Usage ==="
echo "Build the container:"
echo "docker build -t vllm-diagnostics-mcp ."

echo -e "\nRun CLI commands in container:"
echo "docker run --gpus all vllm-diagnostics-mcp python cli.py get-system-specs"

echo -e "\nRun MCP server in container:"
echo "docker run --gpus all -p 8001:8001 vllm-diagnostics-mcp python server.py"