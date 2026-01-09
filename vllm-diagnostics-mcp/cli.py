#!/usr/bin/env python3
"""CLI interface for vLLM diagnostics."""
import json
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.json import JSON
from tabulate import tabulate

from diagnostics.gpu_utils import GPUDiagnostics
from diagnostics.vllm_client import get_vllm_endpoints, get_vllm_models, test_vllm_connection

console = Console()


@click.group()
def cli():
    """vLLM Diagnostics CLI - Tools for understanding your vLLM deployment."""
    pass


@cli.command()
@click.option('--json-output', is_flag=True, help='Output in JSON format')
def get_system_specs(json_output):
    """Get system specifications and GPU information."""
    gpu_diag = GPUDiagnostics()
    specs = gpu_diag.get_system_specs()
    
    if json_output:
        console.print(JSON(json.dumps(specs, indent=2)))
        return
    
    # Rich formatted output
    console.print(Panel.fit("System Specifications", style="bold blue"))
    
    # GPU Information
    if "error" not in specs["gpu"]:
        gpu_table = Table(title="GPU Information")
        gpu_table.add_column("GPU", style="cyan")
        gpu_table.add_column("Memory (GB)", style="green")
        gpu_table.add_column("Utilization", style="yellow")
        gpu_table.add_column("Temperature", style="red")
        
        for gpu in specs["gpu"]["gpus"]:
            memory_str = f"{gpu['memory']['used_gb']:.1f} / {gpu['memory']['total_gb']:.1f} ({gpu['memory']['utilization_percent']:.1f}%)"
            util_str = f"GPU: {gpu['utilization']['gpu_percent']}% | Mem: {gpu['utilization']['memory_percent']}%"
            temp_str = f"{gpu['temperature_c']}°C" if gpu['temperature_c'] else "N/A"
            
            gpu_table.add_row(
                gpu['name'],
                memory_str,
                util_str,
                temp_str
            )
        
        console.print(gpu_table)
    else:
        console.print(f"[red]GPU Error: {specs['gpu']['error']}[/red]")
    
    # System Information
    sys_table = Table(title="System Resources")
    sys_table.add_column("Resource", style="cyan")
    sys_table.add_column("Details", style="white")
    
    sys_table.add_row("CPU Cores", f"{specs['cpu']['cores']} physical, {specs['cpu']['threads']} logical")
    sys_table.add_row("System Memory", f"{specs['memory']['used_gb']:.1f} / {specs['memory']['total_gb']:.1f} GB ({specs['memory']['percent_used']:.1f}%)")
    
    console.print(sys_table)


@cli.command()
@click.option('--vllm-url', default='http://localhost:8000', help='vLLM server URL')
@click.option('--json-output', is_flag=True, help='Output in JSON format')
def list_endpoints(vllm_url, json_output):
    """List available vLLM API endpoints."""
    console.print(f"[blue]Checking vLLM endpoints at {vllm_url}...[/blue]")
    
    endpoints_info = get_vllm_endpoints(vllm_url)
    
    if json_output:
        console.print(JSON(json.dumps(endpoints_info, indent=2)))
        return
    
    # Rich formatted output
    console.print(Panel.fit(f"vLLM API Endpoints - {vllm_url}", style="bold green"))
    
    endpoint_table = Table()
    endpoint_table.add_column("Endpoint", style="cyan")
    endpoint_table.add_column("Status", style="white")
    endpoint_table.add_column("Description", style="yellow")
    
    for endpoint, info in endpoints_info["endpoints"].items():
        status = "✅ Available" if info.get("available", False) else "❌ Not Available"
        if not info.get("available", False) and "error" in info:
            status += f" ({info['error'][:50]}...)" if len(info['error']) > 50 else f" ({info['error']})"
        
        endpoint_table.add_row(endpoint, status, info["description"])
    
    console.print(endpoint_table)
    
    # Summary
    summary = endpoints_info["summary"]
    console.print(f"\n[bold]Summary:[/bold] {summary['available_endpoints']}/{summary['total_endpoints']} endpoints available")


@cli.command()
@click.option('--vllm-url', default='http://localhost:8000', help='vLLM server URL')
@click.option('--json-output', is_flag=True, help='Output in JSON format')
def get_loaded_models(vllm_url, json_output):
    """Get currently loaded models in vLLM."""
    console.print(f"[blue]Fetching loaded models from {vllm_url}...[/blue]")
    
    models_info = get_vllm_models(vllm_url)
    
    if json_output:
        console.print(JSON(json.dumps(models_info, indent=2)))
        return
    
    if not models_info["success"]:
        console.print(f"[red]Error: {models_info['error']}[/red]")
        return
    
    # Rich formatted output
    console.print(Panel.fit("Loaded Models", style="bold green"))
    
    if models_info["model_count"] == 0:
        console.print("[yellow]No models currently loaded[/yellow]")
        return
    
    model_table = Table()
    model_table.add_column("Model ID", style="cyan")
    model_table.add_column("Object Type", style="white")
    model_table.add_column("Created", style="yellow")
    
    for model in models_info["models"]:
        model_table.add_row(
            model.get("id", "Unknown"),
            model.get("object", "Unknown"),
            str(model.get("created", "Unknown"))
        )
    
    console.print(model_table)
    console.print(f"\n[bold]Total models loaded:[/bold] {models_info['model_count']}")


@cli.command()
@click.option('--model-name', required=True, help='Model name to check capacity for')
@click.option('--model-size-gb', type=float, help='Model size in GB (if known)')
@click.option('--batch-size', default=1, help='Expected batch size')
@click.option('--json-output', is_flag=True, help='Output in JSON format')
def check_capacity(model_name, model_size_gb, batch_size, json_output):
    """Check if system has capacity for a specific model."""
    gpu_diag = GPUDiagnostics()
    
    # If model size not provided, try to estimate based on common models
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
        
        # Try to match model name
        model_size_gb = None
        for known_model, size in model_size_estimates.items():
            if known_model.lower() in model_name.lower() or model_name.lower() in known_model.lower():
                model_size_gb = size
                break
        
        if not model_size_gb:
            console.print(f"[yellow]Warning: Could not estimate size for '{model_name}'. Please provide --model-size-gb[/yellow]")
            model_size_gb = 10.0  # Default estimate
    
    recommendations = gpu_diag.recommend_instance_type(model_size_gb, batch_size)
    
    if json_output:
        console.print(JSON(json.dumps(recommendations, indent=2)))
        return
    
    # Rich formatted output
    console.print(Panel.fit(f"Capacity Analysis for {model_name}", style="bold blue"))
    
    console.print(f"[bold]Model:[/bold] {model_name}")
    console.print(f"[bold]Estimated Size:[/bold] {model_size_gb} GB")
    console.print(f"[bold]Batch Size:[/bold] {batch_size}")
    console.print(f"[bold]Estimated Memory Requirement:[/bold] {recommendations['estimated_memory_requirement_gb']:.1f} GB")
    
    # Check for GPU error
    if "gpu_error" in recommendations:
        console.print(f"\n[yellow]⚠️  GPU Detection Issue: {recommendations['gpu_error']}[/yellow]")
        console.print("[yellow]Recommendations based on estimated requirements only[/yellow]")
    
    # Current system analysis
    if recommendations["current_system_suitable"]:
        console.print("\n[green]✅ Current system appears suitable for this model[/green]")
        
        gpu_table = Table(title="Current GPU Analysis")
        gpu_table.add_column("GPU", style="cyan")
        gpu_table.add_column("Memory (GB)", style="white")
        gpu_table.add_column("Estimated Usage", style="yellow")
        
        for gpu_analysis in recommendations["current_gpu_analysis"]:
            gpu_table.add_row(
                gpu_analysis["current_gpu"],
                str(gpu_analysis["memory_gb"]),
                f"{gpu_analysis['estimated_usage_percent']:.1f}%"
            )
        
        console.print(gpu_table)
    else:
        if "gpu_error" in recommendations:
            console.print("\n[yellow]❓ Cannot determine current system suitability (no GPU info)[/yellow]")
        else:
            console.print("\n[red]❌ Current system may not be suitable for this model[/red]")
    
    # AWS instance suggestions
    console.print(f"\n[bold]Suggested AWS Instance Types:[/bold]")
    for instance in recommendations["suggested_aws_instances"]:
        console.print(f"  • {instance}")


@cli.command()
@click.option('--vllm-url', default='http://localhost:8000', help='vLLM server URL')
def test_connection(vllm_url):
    """Test connection to vLLM server."""
    console.print(f"[blue]Testing connection to {vllm_url}...[/blue]")
    
    result = test_vllm_connection(vllm_url)
    
    if result["success"]:
        console.print(f"[green]✅ Connection successful![/green]")
        console.print(f"Response time: {result['response_time_ms']:.1f}ms")
        console.print(f"Status code: {result['status_code']}")
    else:
        console.print(f"[red]❌ Connection failed: {result['error']}[/red]")


if __name__ == '__main__':
    cli()