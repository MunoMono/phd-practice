# Backend Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Keep docling explicitly pinned in the image for ingestion scripts.
RUN pip install --no-cache-dir --prefer-binary docling==2.15.0

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p logs/sessions

# Copy and set up entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Expose port
EXPOSE 8000

# Run the application with entrypoint script
ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
