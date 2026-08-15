# Frontend Dockerfile
FROM node:20-alpine AS builder

WORKDIR /app/frontend

ARG VITE_API_URL
ENV VITE_API_URL=${VITE_API_URL}

# Copy package files
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci

# Copy source code and canonical documentation sources.
COPY frontend/ ./
COPY docs/turin_experiment/technology-statement-of-work-turin-experiment-v0.2.md /app/docs/turin_experiment/
COPY docs/turin_experiment/using-the-turin-research-instrument.md /app/docs/turin_experiment/

# Build the application
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built assets from builder
COPY --from=builder /app/frontend/dist /usr/share/nginx/html

# Copy nginx configuration
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80 443

CMD ["nginx", "-g", "daemon off;"]
