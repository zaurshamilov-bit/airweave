FROM python:3.11-slim

WORKDIR /app

# Install system dependencies and poetry
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && curl -sSL https://install.python-poetry.org | python3 -

# Add Poetry to PATH
ENV PATH="/root/.local/bin:$PATH"

# Copy poetry files
COPY pyproject.toml poetry.lock ./

# Configure poetry
RUN poetry config virtualenvs.create false

# Install dependencies only (no root project)
RUN poetry install --no-interaction --no-ansi --no-root

# Copy entrypoint script and set permissions
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod 755 /app/entrypoint.sh

# Copy application code
COPY . .

# Make sure the script is executable after the final copy
RUN chmod 755 /app/entrypoint.sh

ENTRYPOINT ["/bin/bash", "/app/entrypoint.sh"] 