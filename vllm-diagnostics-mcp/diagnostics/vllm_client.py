"""vLLM client utilities for API discovery and model management."""
import json
import httpx
from typing import Dict, List, Optional
import asyncio


class VLLMClient:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.client = httpx.AsyncClient(timeout=30.0)

    async def get_available_endpoints(self) -> Dict:
        """Discover available vLLM API endpoints."""
        endpoints = {}
        
        # Common vLLM endpoints to check
        endpoint_checks = [
            ("/v1/models", "List available models"),
            ("/v1/completions", "Text completion endpoint"),
            ("/v1/chat/completions", "Chat completion endpoint"),
            ("/v1/embeddings", "Text embeddings endpoint"),
            ("/health", "Health check endpoint"),
            ("/metrics", "Prometheus metrics endpoint"),
            ("/version", "vLLM version information")
        ]
        
        for endpoint, description in endpoint_checks:
            try:
                response = await self.client.get(f"{self.base_url}{endpoint}")
                endpoints[endpoint] = {
                    "available": response.status_code < 400,
                    "status_code": response.status_code,
                    "description": description
                }
                if endpoint == "/v1/models" and response.status_code == 200:
                    endpoints[endpoint]["models"] = response.json()
            except Exception as e:
                endpoints[endpoint] = {
                    "available": False,
                    "error": str(e),
                    "description": description
                }
        
        return {
            "base_url": self.base_url,
            "endpoints": endpoints,
            "summary": {
                "total_endpoints": len(endpoint_checks),
                "available_endpoints": sum(1 for ep in endpoints.values() if ep.get("available", False))
            }
        }

    async def get_loaded_models(self) -> Dict:
        """Get currently loaded models and their information."""
        try:
            response = await self.client.get(f"{self.base_url}/v1/models")
            if response.status_code == 200:
                models_data = response.json()
                return {
                    "success": True,
                    "models": models_data.get("data", []),
                    "model_count": len(models_data.get("data", []))
                }
            else:
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}"
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to connect to vLLM: {str(e)}"
            }

    async def get_model_info(self, model_name: str) -> Dict:
        """Get detailed information about a specific model."""
        try:
            models_response = await self.get_loaded_models()
            if not models_response["success"]:
                return models_response
            
            for model in models_response["models"]:
                if model.get("id") == model_name:
                    return {
                        "success": True,
                        "model": model,
                        "capabilities": {
                            "chat": "/v1/chat/completions" in await self._get_available_endpoints_list(),
                            "completions": "/v1/completions" in await self._get_available_endpoints_list(),
                            "embeddings": "/v1/embeddings" in await self._get_available_endpoints_list()
                        }
                    }
            
            return {
                "success": False,
                "error": f"Model '{model_name}' not found in loaded models"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to get model info: {str(e)}"
            }

    async def _get_available_endpoints_list(self) -> List[str]:
        """Helper to get list of available endpoint paths."""
        endpoints_info = await self.get_available_endpoints()
        return [ep for ep, info in endpoints_info["endpoints"].items() if info.get("available", False)]

    async def test_connection(self) -> Dict:
        """Test connection to vLLM server."""
        try:
            response = await self.client.get(f"{self.base_url}/health")
            return {
                "success": True,
                "status_code": response.status_code,
                "response_time_ms": response.elapsed.total_seconds() * 1000,
                "server_reachable": True
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "server_reachable": False
            }

    async def get_server_stats(self) -> Dict:
        """Get vLLM server statistics if available."""
        try:
            # Try to get metrics endpoint
            response = await self.client.get(f"{self.base_url}/metrics")
            if response.status_code == 200:
                return {
                    "success": True,
                    "metrics_available": True,
                    "metrics": response.text
                }
            else:
                return {
                    "success": False,
                    "metrics_available": False,
                    "error": "Metrics endpoint not available"
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to get server stats: {str(e)}"
            }

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


# Synchronous wrapper functions for CLI usage
def get_vllm_endpoints(base_url: str = "http://localhost:8000") -> Dict:
    """Synchronous wrapper for getting vLLM endpoints."""
    async def _get():
        client = VLLMClient(base_url)
        try:
            return await client.get_available_endpoints()
        finally:
            await client.close()
    
    return asyncio.run(_get())


def get_vllm_models(base_url: str = "http://localhost:8000") -> Dict:
    """Synchronous wrapper for getting loaded models."""
    async def _get():
        client = VLLMClient(base_url)
        try:
            return await client.get_loaded_models()
        finally:
            await client.close()
    
    return asyncio.run(_get())


def test_vllm_connection(base_url: str = "http://localhost:8000") -> Dict:
    """Synchronous wrapper for testing vLLM connection."""
    async def _test():
        client = VLLMClient(base_url)
        try:
            return await client.test_connection()
        finally:
            await client.close()
    
    return asyncio.run(_test())