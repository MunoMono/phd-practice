#!/bin/bash

# Docker Setup and Management Script for Testamentary Traces Research Platform

set -e

echo "🔬 Testamentary Traces Research Platform - Docker Setup"
echo "=================================================="

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Function to display help
show_help() {
    echo ""
    echo "Usage: ./docker-setup.sh [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  setup       - Initial setup (create .env, build images)"
    echo "  start       - Start all services"
    echo "  stop        - Stop all services"
    echo "  restart     - Restart all services"
    echo "  logs        - Show logs from all services"
    echo "  logs-fe     - Show frontend logs"
    echo "  logs-be     - Show backend logs"
    echo "  logs-db     - Show database logs"
    echo "  shell-be    - Open shell in backend container"
    echo "  shell-db    - Open PostgreSQL shell"
    echo "  rebuild     - Rebuild all containers"
    echo "  clean       - Stop and remove all containers, networks, volumes"
    echo "  help        - Show this help message"
    echo ""
}

# Setup environment
setup_env() {
    echo "📋 Setting up environment..."
    
    if [ ! -f .env ]; then
        echo "Creating .env file from template..."
        cp .env.docker .env
        echo "✅ .env file created. Please edit it with your configuration."
        echo "   Especially update passwords and S3 credentials!"
        read -p "Press enter to continue after editing .env..."
    else
        echo "✅ .env file already exists"
    fi
    
    echo ""
    echo "🏗️  Building Docker images..."
    docker-compose build
    
    echo ""
    echo "✅ Setup complete!"
    echo ""
    echo "Next steps:"
    echo "  1. Review and edit .env file"
    echo "  2. Run './docker-setup.sh start' to start services"
}

# Start services
start_services() {
    echo "🚀 Starting services..."
    docker-compose up -d
    
    echo ""
    echo "⏳ Waiting for services to be ready..."
    sleep 5
    
    echo ""
    echo "✅ Services started!"
    echo ""
    echo "Access the application:"
    echo "  Frontend:  http://localhost:3000"
    echo "  Backend:   http://localhost:8000"
    echo "  API Docs:  http://localhost:8000/docs"
    echo "  MinIO UI:  http://localhost:9001"
    echo "  Database:  localhost:5432"
    echo ""
    echo "Run './docker-setup.sh logs' to see service logs"
}

# Stop services
stop_services() {
    echo "🛑 Stopping services..."
    docker-compose down
    echo "✅ Services stopped"
}

# Restart services
restart_services() {
    echo "🔄 Restarting services..."
    docker-compose restart
    echo "✅ Services restarted"
}

# Show logs
show_logs() {
    docker-compose logs -f
}

show_frontend_logs() {
    docker-compose logs -f frontend
}

show_backend_logs() {
    docker-compose logs -f backend
}

show_db_logs() {
    docker-compose logs -f db
}

# Backend shell
backend_shell() {
    echo "🐚 Opening shell in backend container..."
    docker-compose exec backend /bin/bash
}

# Database shell
db_shell() {
    echo "🗄️  Opening PostgreSQL shell..."
    docker-compose exec db psql -U postgres -d testamentary-traces
}

# Rebuild containers
rebuild() {
    echo "🔨 Rebuilding containers..."
    docker-compose down
    docker-compose build --no-cache
    docker-compose up -d
    echo "✅ Rebuild complete"
}

# Clean everything
clean() {
    echo "⚠️  This will remove all containers, networks, and volumes!"
    read -p "Are you sure? (yes/no): " confirm
    
    if [ "$confirm" == "yes" ]; then
        echo "🧹 Cleaning up..."
        docker-compose down -v
        echo "✅ Cleanup complete"
    else
        echo "❌ Cleanup cancelled"
    fi
}

# Main command router
case "$1" in
    setup)
        setup_env
        ;;
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        restart_services
        ;;
    logs)
        show_logs
        ;;
    logs-fe)
        show_frontend_logs
        ;;
    logs-be)
        show_backend_logs
        ;;
    logs-db)
        show_db_logs
        ;;
    shell-be)
        backend_shell
        ;;
    shell-db)
        db_shell
        ;;
    rebuild)
        rebuild
        ;;
    clean)
        clean
        ;;
    help|*)
        show_help
        ;;
esac
