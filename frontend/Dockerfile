
FROM node:20 AS builder

WORKDIR /app

# Copy everything at once
COPY . .

# Install dependencies and build in a single layer
# Using npx to run vite directly, with Node options to increase memory
RUN npm install --ignore-scripts && \
    NODE_OPTIONS="--max-old-space-size=4096" npx vite build

# Runtime stage
FROM node:20-alpine

WORKDIR /app

# Install serve for hosting the built app
RUN npm install -g serve

# Copy built app from builder stage
COPY --from=builder /app/dist /app/dist
COPY docker-entrypoint.sh /usr/local/bin/

# Make entrypoint executable
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Use entrypoint script for runtime configuration
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
