#!/usr/bin/env python3
"""MCP Server for vLLM diagnostics."""
import json
import asyncio
from typing import Any, Dict, List
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    LoggingLevel
)

from diagnostics.gpu_utils import GPUDiagnostics
from diagnostics.vllm_client import VLLMClient

# Initialize diagnostics
gpu_diag = GPUDiagnostics()
server = Server("vllm-diagnostics")


@server.list_tools()
async def handle_list_tools() -> List[Tool]:
    """List available diagnostic tools."""
    return [
        Tool(
            name="get_system_specs",
            description="Get comprehensive system specifications including GPU, CPU, and memory information",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="get_vllm_endpoints",
            description="Discover available vLLM API endpoints and their status",
            inputSchema={
                "type": "object",
                "properties": {
                    "vllm_url": {
                        "type": "string",
                        "description": "vLLM server URL",
                        "default": "http://localhost:8000"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_loaded_models",
            description="Get currently loaded models in vLLM server",
            inputSchema={
                "type": "object",
                "properties": {
                    "vllm_url": {
                        "type": "string",
                        "description": "vLLM server URL",
                        "default": "http://localhost:8000"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="check_model_capacity",
            description="Check if system has sufficient capacity for a specific model",
            inputSchema={
                "type": "object",
                "properties": {
                    "model_name": {
                        "type": "string",
                        "description": "Name of the model to check"
                    },
                    "model_size_gb": {
                        "type": "number",
                        "description": "Model size in GB (optional, will estimate if not provided)"
                    },
                    "batch_size": {
                        "type": "integer",
                        "description": "Expected batch size",
                        "default": 1
                    }
                },
                "required": ["model_name"]
            }
        ),
        Tool(
            name="test_vllm_connection",
            description="Test connection to vLLM server",
            inputSchema={
                "type": "object",
                "properties": {
                    "vllm_url": {
                        "type": "string",
                        "description": "vLLM server URL",
                        "default": "http://localhost:8000"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_gpu_utilization",
            description="Get real-time GPU utilization and memory usage",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
    """Handle tool calls."""
    
    if name == "get_system_specs":
        specs = gpu_diag.get_system_specs()
        return [TextContent(
            type="text",
            text=json.dumps(specs, indent=2)
        )]
    
    elif name == "get_vllm_endpoints":
        vllm_url = arguments.get("vllm_url", "http://localhost:8000")
        client = VLLMClient(vllm_url)
        try:
            endpoints = await client.get_available_endpoints()
            return [TextContent(
                type="text",
                text=json.dumps(endpoints, indent=2)
            )]
        finally:
            await client.close()
    
    elif name == "get_loaded_models":
        vllm_url = arguments.get("vllm_url", "http://localhost:8000")
        client = VLLMClient(vllm_url)
        try:
            models = await client.get_loaded_models()
            return [TextContent(
                type="text",
                text=json.dumps(models, indent=2)
            )]
        finally:
            await client.close()
    
    elif name == "check_model_capacity":
        model_name = arguments["model_name"]
        model_size_gb = arguments.get("model_size_gb")
        batch_size = arguments.get("batch_size", 1)
        
        # Estimate model size if not provided
        if not model_size_gb:
            model_size_estimates = {
                "meta-llama/Llama-2-7b": 13.5,
                "meta-llama/Llama-2-13b": 26.0,
                "meta-llama/Llama-2-70b": 140.0,
                "mistralai/Mistral-7B": 14.0,
                "microsoft/DialoGPT-medium": 1.5,
                "gpt2": 0.5,
                "gpt2-medium": 1.5,
                "gpt2-large": 3.0,
                "gpt2-xl": 6.0
            }
            
            model_size_gb = None
            for known_model, size in model_size_estimates.items():
                if known_model.lower() in model_name.lower() or model_name.lower() in known_model.lower():
                    model_size_gb = size
                    break
            
            if not model_size_gb:
                model_size_gb = 10.0  # Default estimate
        
        recommendations = gpu_diag.recommend_instance_type(model_size_gb, batch_size)
        recommendations["model_name"] = model_name
        
        return [TextContent(
            type="text",
            text=json.dumps(recommendations, indent=2)
        )]
    
    elif name == "test_vllm_connection":
        vllm_url = arguments.get("vllm_url", "http://localhost:8000")
        client = VLLMClient(vllm_url)
        try:
            result = await client.test_connection()
            return [TextContent(
                type="text",
                text=json.dumps(result, indent=2)
            )]
        finally:
            await client.close()
    
    elif name == "get_gpu_utilization":
        gpu_info = gpu_diag.get_gpu_info()
        return [TextContent(
            type="text",
            text=json.dumps(gpu_info, indent=2)
        )]
    
    else:
        raise ValueError(f"Unknown tool: {name}")


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="vllm-diagnostics",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=None,
                    experimental_capabilities=None,
                )
            )
        )


if __name__ == "__main__":
    asyncio.run(main())