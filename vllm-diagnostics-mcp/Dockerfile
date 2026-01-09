FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    nvidia-ml-py3 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose MCP server port
EXPOSE 8001

# Default command runs the MCP server
CMD ["python", "server.py"]