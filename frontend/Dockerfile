# Frontend Dockerfile
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built assets from builder
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configurations (both dev and prod)
COPY nginx.conf /etc/nginx/conf.d/nginx.conf
COPY nginx.prod.conf /etc/nginx/conf.d/nginx.prod.conf

# By default, use the standard config (can be overridden)
RUN ln -sf /etc/nginx/conf.d/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80 443

CMD ["nginx", "-g", "daemon off;"]
