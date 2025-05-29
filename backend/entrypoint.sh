#!/bin/bash
set -e

# Wait for database to be ready
echo "Waiting for database..."
echo "POSTGRES_HOST: $POSTGRES_HOST"
echo "POSTGRES_USER: $POSTGRES_USER"
echo "POSTGRES_DB: $POSTGRES_DB"
echo "POSTGRES_PORT: ${POSTGRES_PORT:-5432}"

poetry run python -c "
from tenacity import retry, stop_after_attempt, wait_fixed
from sqlalchemy import create_engine
import os
import sys

@retry(stop=stop_after_attempt(15), wait=wait_fixed(5))
def check_db():
    try:
        user = os.getenv('POSTGRES_USER', 'airweave')
        password = os.getenv('POSTGRES_PASSWORD', 'airweave1234!')
        host = os.getenv('POSTGRES_HOST', 'db')
        db = os.getenv('POSTGRES_DB', 'airweave')
        port = os.getenv('POSTGRES_PORT', '5432')

        print(f'Attempting to connect to: postgresql://{user}:***@{host}:{port}/{db}')

        # Add SSL mode for Azure PostgreSQL
        connection_string = f'postgresql://{user}:{password}@{host}:{port}/{db}?sslmode=require'
        engine = create_engine(connection_string, connect_args={'connect_timeout': 10})
        connection = engine.connect()
        connection.close()
        print('Database connection successful!')

    except Exception as e:
        print(f'Database connection failed: {str(e)}')
        print(f'Error type: {type(e).__name__}')
        raise e

try:
    check_db()
except Exception as e:
    print(f'Final database connection error: {e}')
    sys.exit(1)
"

# Run migrations using our existing Alembic setup
echo "Running database migrations..."
cd /app && poetry run alembic upgrade head

# Start application
echo "Starting application..."
poetry run uvicorn airweave.main:app --host 0.0.0.0 --port 8001 --reload
