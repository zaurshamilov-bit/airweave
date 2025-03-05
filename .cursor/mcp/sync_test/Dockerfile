FROM python:3.11-slim

WORKDIR /app

# Install git and other dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . .

# Install the package
RUN pip install --no-cache-dir -e .

# Run the server
ENTRYPOINT ["python", "-m", "mcp_server_sync_test"] 