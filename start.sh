#!/usr/bin/env bash
set -euo pipefail

# Optional flags/env
NONINTERACTIVE="${NONINTERACTIVE:-}"
CI_COMPOSE_OVERRIDE="${CI_COMPOSE_OVERRIDE:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --noninteractive) NONINTERACTIVE=1; shift ;;
    --compose-override) CI_COMPOSE_OVERRIDE="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 2 ;;
  esac
done

die() { echo "❌ $*" >&2; exit 1; }
have_cmd() { command -v "$1" >/dev/null 2>&1; }

# .env bootstrap (backward compatible)
if [[ ! -f .env ]]; then
  echo "Creating .env file from example..."
  cp .env.example .env || touch .env
  echo ".env file created"
fi

get_env_val() { grep -E "^${1}=" .env 2>/dev/null | head -1 | cut -d'=' -f2- | sed 's/^"//; s/"$//' | tr -d ' '; }
set_env_val() {
  local key="$1" val="$2"
  grep -v -E "^${key}=" .env > .env.tmp 2>/dev/null || true
  mv .env.tmp .env
  echo "${key}=\"${val}\"" >> .env
}

EXISTING_KEY="$(get_env_val ENCRYPTION_KEY || true)"
if [[ -n "${EXISTING_KEY:-}" ]]; then
  echo "Encryption key already exists in .env (hidden)."
else
  echo "No valid encryption key found. Generating new encryption key..."
  NEW_KEY="$(openssl rand -base64 32)"
  set_env_val ENCRYPTION_KEY "$NEW_KEY"
  echo "Added new ENCRYPTION_KEY to .env file"
fi

if ! grep -q "^SKIP_AZURE_STORAGE=" .env; then
  echo "SKIP_AZURE_STORAGE=true" >> .env
  echo "Added SKIP_AZURE_STORAGE=true for faster startup"
fi

maybe_set_key() {
  local key="$1" envval="${!1:-}" existing
  existing="$(get_env_val "$key" || true)"
  if [[ -n "$existing" ]]; then
    echo "$key already present in .env (hidden)."; return
  fi
  if [[ -n "$envval" ]]; then
    set_env_val "$key" "$envval"; echo "Set $key from environment."; return
  fi
  if [[ -z "$NONINTERACTIVE" ]]; then
    echo ""; echo "$key is required for certain functionality."
    read -p "Would you like to add your $key now? (y/n): " ADD_KEY || true
    if [[ "$ADD_KEY" =~ ^[Yy]$ ]]; then
      read -p "Enter your $key: " INPUT || true
      if [[ -n "$INPUT" ]]; then set_env_val "$key" "$INPUT"; echo "$key added to .env file."; fi
    else
      echo "You can add $key later by editing the .env file."
      echo "$key=\"your-api-key-here\""
    fi
  else
    echo "NONINTERACTIVE: Skipping prompt for $key (not set)."
  fi
}
maybe_set_key OPENAI_API_KEY
maybe_set_key MISTRAL_API_KEY

# Engine & compose
if have_cmd docker && docker info >/dev/null 2>&1; then
  CONTAINER_CMD="docker"
elif have_cmd podman && podman info >/dev/null 2>&1; then
  CONTAINER_CMD="podman"
else
  die "Neither Docker nor Podman daemon is running. Please start one and retry."
fi

if have_cmd docker && docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
elif have_cmd docker-compose; then
  COMPOSE_CMD="docker-compose"
elif have_cmd podman-compose; then
  COMPOSE_CMD="podman-compose"
else
  die "No compose tool found. Install Docker Compose v2 or docker-compose."
fi

echo "Using: ${CONTAINER_CMD} + ${COMPOSE_CMD}"

# Clean up existing containers
EXISTING_CONTAINERS="$($CONTAINER_CMD ps -a --filter "name=airweave" --format "{{.Names}}" | tr '\n' ' ' || true)"
if [[ -n "$EXISTING_CONTAINERS" ]]; then
  echo "Found existing airweave containers: $EXISTING_CONTAINERS"
  if [[ -n "$NONINTERACTIVE" ]]; then
    echo "NONINTERACTIVE: removing existing containers..."
    $CONTAINER_CMD rm -f $EXISTING_CONTAINERS >/dev/null 2>&1 || true
    $CONTAINER_CMD volume rm airweave_postgres_data >/dev/null 2>&1 || true
  else
    read -p "Remove them before starting? (y/n): " REMOVE_CONTAINERS || true
    if [[ "$REMOVE_CONTAINERS" =~ ^[Yy]$ ]]; then
      echo "Removing existing containers..."
      $CONTAINER_CMD rm -f $EXISTING_CONTAINERS || true
      echo "Removing database volume..."
      $CONTAINER_CMD volume rm airweave_postgres_data || true
    else
      echo "Warning: Starting with existing containers may cause conflicts."
    fi
  fi
fi

# Compose files
COMPOSE_FILES="-f docker/docker-compose.yml"
if [[ -n "${CI_COMPOSE_OVERRIDE:-}" && -f "$CI_COMPOSE_OVERRIDE" ]]; then
  COMPOSE_FILES="$COMPOSE_FILES -f $CI_COMPOSE_OVERRIDE"
fi

# Start services
echo ""; echo "Starting Docker services..."
set +e
$COMPOSE_CMD $COMPOSE_FILES up -d
RC=$?
set -e
if [[ $RC -ne 0 ]]; then
  echo "❌ Failed to start Docker services"
  echo "Check: ${CONTAINER_CMD} logs airweave-backend  |  ${CONTAINER_CMD} logs airweave-frontend"
  exit 1
fi

echo ""; echo "Waiting for services to initialize..."
sleep 10

# Health checks
echo "Checking backend health..."
MAX_RETRIES=30
RETRY_COUNT=0
while [[ $RETRY_COUNT -lt $MAX_RETRIES ]]; do
  if curl -f http://localhost:8001/health >/dev/null 2>&1; then
    echo "✅ Backend is healthy!"; break
  fi
  echo "⏳ Backend is still starting... (attempt $((RETRY_COUNT + 1))/$MAX_RETRIES)"
  RETRY_COUNT=$((RETRY_COUNT + 1)); sleep 5
done

if [[ $RETRY_COUNT -ge $MAX_RETRIES ]]; then
  echo "❌ Backend failed to start after $MAX_RETRIES attempts"
  echo "Check backend logs with: ${CONTAINER_CMD} logs airweave-backend"
fi

FRONTEND_STATUS="$($CONTAINER_CMD inspect airweave-frontend --format='{{.State.Status}}' 2>/dev/null || true)"
if [[ "$FRONTEND_STATUS" == "created" || "$FRONTEND_STATUS" == "exited" ]]; then
  echo "Starting frontend container..."
  $CONTAINER_CMD start airweave-frontend || true
  sleep 5
fi

echo ""; echo "🚀 Airweave Status:"; echo "=================="
if curl -f http://localhost:8001/health >/dev/null 2>&1; then
  echo "✅ Backend API:    http://localhost:8001"
else
  echo "❌ Backend API:    Not responding (check: ${CONTAINER_CMD} logs airweave-backend)"
fi

if curl -f http://localhost:8080 >/dev/null 2>&1; then
  echo "✅ Frontend UI:    http://localhost:8080"
else
  echo "❌ Frontend UI:    Not responding (check: ${CONTAINER_CMD} logs airweave-frontend)"
fi

echo ""; echo "Other services:"
echo "📊 Temporal UI:    http://localhost:8088"
echo "🗄️  PostgreSQL:    localhost:5432"
echo "🔍 Qdrant:        http://localhost:6333"
echo ""; echo "To view logs: ${CONTAINER_CMD} logs <container-name>"
echo "To stop:      ${COMPOSE_CMD} $COMPOSE_FILES down"; echo ""
