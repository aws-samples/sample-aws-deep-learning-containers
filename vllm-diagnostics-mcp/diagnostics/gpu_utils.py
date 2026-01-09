"""GPU diagnostic utilities."""
import json
import subprocess
from typing import Dict, List, Optional
import psutil

try:
    import py3nvml.py3nvml as nvml
    NVML_AVAILABLE = True
except ImportError:
    NVML_AVAILABLE = False


class GPUDiagnostics:
    def __init__(self):
        if NVML_AVAILABLE:
            try:
                nvml.nvmlInit()
                self.nvml_initialized = True
            except Exception:
                self.nvml_initialized = False
        else:
            self.nvml_initialized = False

    def get_gpu_info(self) -> Dict:
        """Get comprehensive GPU information."""
        if not self.nvml_initialized:
            return {"error": "NVML not available or failed to initialize"}

        try:
            device_count = nvml.nvmlDeviceGetCount()
            gpus = []
            
            for i in range(device_count):
                handle = nvml.nvmlDeviceGetHandleByIndex(i)
                
                # Basic info
                name = nvml.nvmlDeviceGetName(handle).decode('utf-8')
                
                # Memory info
                mem_info = nvml.nvmlDeviceGetMemoryInfo(handle)
                
                # Utilization
                util = nvml.nvmlDeviceGetUtilizationRates(handle)
                
                # Temperature
                try:
                    temp = nvml.nvmlDeviceGetTemperature(handle, nvml.NVML_TEMPERATURE_GPU)
                except:
                    temp = None
                
                # Power
                try:
                    power = nvml.nvmlDeviceGetPowerUsage(handle) / 1000.0  # Convert to watts
                    max_power = nvml.nvmlDeviceGetMaxPowerManagement(handle) / 1000.0
                except:
                    power = None
                    max_power = None

                gpu_info = {
                    "index": i,
                    "name": name,
                    "memory": {
                        "total_gb": round(mem_info.total / (1024**3), 2),
                        "used_gb": round(mem_info.used / (1024**3), 2),
                        "free_gb": round(mem_info.free / (1024**3), 2),
                        "utilization_percent": round((mem_info.used / mem_info.total) * 100, 1)
                    },
                    "utilization": {
                        "gpu_percent": util.gpu,
                        "memory_percent": util.memory
                    },
                    "temperature_c": temp,
                    "power": {
                        "current_watts": power,
                        "max_watts": max_power
                    }
                }
                gpus.append(gpu_info)
            
            return {
                "gpu_count": device_count,
                "gpus": gpus,
                "driver_version": nvml.nvmlSystemGetDriverVersion().decode('utf-8')
            }
            
        except Exception as e:
            return {"error": f"Failed to get GPU info: {str(e)}"}

    def get_system_specs(self) -> Dict:
        """Get system specifications for capacity planning."""
        gpu_info = self.get_gpu_info()
        
        # CPU info
        cpu_info = {
            "cores": psutil.cpu_count(logical=False),
            "threads": psutil.cpu_count(logical=True),
            "frequency_mhz": psutil.cpu_freq().current if psutil.cpu_freq() else None
        }
        
        # Memory info
        memory = psutil.virtual_memory()
        memory_info = {
            "total_gb": round(memory.total / (1024**3), 2),
            "available_gb": round(memory.available / (1024**3), 2),
            "used_gb": round(memory.used / (1024**3), 2),
            "percent_used": memory.percent
        }
        
        return {
            "gpu": gpu_info,
            "cpu": cpu_info,
            "memory": memory_info,
            "timestamp": psutil.boot_time()
        }

    def recommend_instance_type(self, model_size_gb: float, batch_size: int = 1) -> Dict:
        """Recommend instance type based on model requirements."""
        gpu_info = self.get_gpu_info()
        
        # Estimate memory requirements (rough heuristic)
        # Model size + KV cache + activation memory + overhead
        estimated_memory_gb = model_size_gb * 1.2 + (batch_size * 0.5) + 2
        
        if "error" in gpu_info:
            # No GPU info available, just return recommendations based on estimated requirements
            instance_suggestions = []
            if estimated_memory_gb <= 16:
                instance_suggestions.extend(["g4dn.xlarge", "g5.xlarge"])
            elif estimated_memory_gb <= 24:
                instance_suggestions.extend(["g4dn.2xlarge", "g5.2xlarge"])
            elif estimated_memory_gb <= 48:
                instance_suggestions.extend(["g5.4xlarge", "p3.2xlarge"])
            elif estimated_memory_gb <= 80:
                instance_suggestions.extend(["g5.8xlarge", "p3.8xlarge", "p4d.xlarge"])
            else:
                instance_suggestions.extend(["p4d.24xlarge", "p5.48xlarge"])
            
            return {
                "model_size_gb": model_size_gb,
                "estimated_memory_requirement_gb": estimated_memory_gb,
                "current_system_suitable": False,
                "current_gpu_analysis": [],
                "suggested_aws_instances": instance_suggestions,
                "gpu_error": gpu_info["error"]
            }
        
        recommendations = []
        current_suitable = False
        
        for gpu in gpu_info["gpus"]:
            gpu_memory = gpu["memory"]["total_gb"]
            if gpu_memory >= estimated_memory_gb:
                current_suitable = True
                recommendations.append({
                    "current_gpu": gpu["name"],
                    "memory_gb": gpu_memory,
                    "estimated_usage_percent": round((estimated_memory_gb / gpu_memory) * 100, 1),
                    "suitable": True
                })
        
        # AWS instance type suggestions (simplified)
        instance_suggestions = []
        if estimated_memory_gb <= 16:
            instance_suggestions.extend(["g4dn.xlarge", "g5.xlarge"])
        elif estimated_memory_gb <= 24:
            instance_suggestions.extend(["g4dn.2xlarge", "g5.2xlarge"])
        elif estimated_memory_gb <= 48:
            instance_suggestions.extend(["g5.4xlarge", "p3.2xlarge"])
        elif estimated_memory_gb <= 80:
            instance_suggestions.extend(["g5.8xlarge", "p3.8xlarge", "p4d.xlarge"])
        else:
            instance_suggestions.extend(["p4d.24xlarge", "p5.48xlarge"])
        
        return {
            "model_size_gb": model_size_gb,
            "estimated_memory_requirement_gb": estimated_memory_gb,
            "current_system_suitable": current_suitable,
            "current_gpu_analysis": recommendations,
            "suggested_aws_instances": instance_suggestions
        }