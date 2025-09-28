FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package.json ./

# Install dependencies with legacy peer deps to avoid conflicts
# This is more reliable in Docker environments with cross-platform builds
RUN npm install --legacy-peer-deps

# Copy application code
COPY . .

# Build the application in production mode
RUN npm run build

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
