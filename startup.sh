#!/bin/bash

# Check if container exists
if ! docker ps -a --format '{{.Names}}' | grep -q '^airweave-db$'; then
    echo "Creating airweave database container..."
    docker run -d \
        --name airweave-db \
        -e POSTGRES_DB=airweave \
        -e POSTGRES_USER=airweave \
        -e POSTGRES_PASSWORD=airweave1234! \
        -p 5432:5432 \
        postgres:16
else
    # Check if container is running
    if ! docker ps --format '{{.Names}}' | grep -q '^airweave-db$'; then
        echo "Starting existing airweave database container..."
        docker start airweave-db
    else
        echo "airweave database container is already running"
    fi
fi

# Wait for database to be ready
echo "Waiting for database to be ready..."
until docker exec airweave-db pg_isready -U airweave > /dev/null 2>&1; do
    sleep 1
done
echo "Database is ready!"
