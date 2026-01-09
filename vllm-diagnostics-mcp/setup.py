from setuptools import setup, find_packages

setup(
    name="vllm-diagnostics-mcp",
    version="1.0.0",
    description="MCP server for vLLM diagnostics and capacity planning",
    packages=find_packages(),
    install_requires=[
        "mcp>=1.0.0",
        "pydantic>=2.0.0",
        "httpx>=0.25.0",
        "click>=8.0.0",
        "psutil>=5.9.0",
        "py3nvml>=0.2.7",
        "requests>=2.28.0",
        "tabulate>=0.9.0",
        "rich>=13.0.0"
    ],
    entry_points={
        'console_scripts': [
            'vllm-diag=cli:cli',
        ],
    },
    python_requires=">=3.8",
)