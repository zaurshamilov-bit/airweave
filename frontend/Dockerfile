FROM node:20-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy application code
COPY . .

# Build the application
RUN npm run build

# Expose port
EXPOSE 8080

# Use serve to serve the static content
RUN npm install -g serve

# Start serve
CMD ["serve", "-s", "dist", "-l", "8080"]
