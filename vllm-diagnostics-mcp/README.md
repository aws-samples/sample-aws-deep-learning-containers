# vLLM Diagnostics MCP Server

An MCP server that provides diagnostic tools for vLLM deployments, helping customers understand system capacity, available APIs, and workload compatibility.

## Features

- GPU memory and utilization inspection
- System specifications and instance type recommendations
- vLLM API endpoint discovery
- Model loading/unloading capabilities
- Capacity planning for new workloads
- Synthetic benchmarks and probes

## Usage

```bash
# Run as CLI commands
python cli.py get-system-specs
python cli.py list-endpoints --vllm-url http://localhost:8000
python cli.py check-capacity --model-name meta-llama/Llama-2-7b-hf
python cli.py get-loaded-models --vllm-url http://localhost:8000
```

## Docker Usage

```bash
docker build -t vllm-diagnostics-mcp .
docker run --gpus all -p 8001:8001 vllm-diagnostics-mcp
```