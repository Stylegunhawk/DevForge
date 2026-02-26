#!/bin/bash
# =============================================================================
# DevForge Backend - Docker Quick Start Script
# =============================================================================
# This script helps you get started with DevForge using Docker
# Supports both minimal (API-only) and full (with RAG) deployments
# =============================================================================

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo -e "${BLUE}=================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}=================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    print_header "Checking Prerequisites"
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    print_success "Docker installed"
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    print_success "Docker Compose installed"
    
    if [ ! -f .env.docker ]; then
        print_warning ".env.docker file not found. Creating from .env.docker.example..."
        cp .env.docker.example .env.docker
        print_warning "Please edit .env.docker with your API keys and settings!"
        echo -e "${YELLOW}Press Enter after you've configured .env.docker, or Ctrl+C to exit${NC}"
        read -r
    else
        print_success ".env.docker file exists"
    fi
}

# Start API only (minimal mode - no RAG)
start_minimal() {
    print_header "Starting DevForge (Minimal Mode - API Only)"
    check_prerequisites
    
    echo "This mode runs ONLY the FastAPI backend"
    echo "Available features: DataGen, GitHub, Cheatsheet, Prompt Refiner"
    echo "RAG features will NOT be available"
    echo ""
    
    docker-compose up api -d --build
    
    echo ""
    print_success "DevForge API is starting!"
    echo ""
    echo "Services available:"
    echo "  • API: http://localhost:8001"
    echo "  • API Docs: http://localhost:8001/docs"
    echo ""
    echo "Waiting for API to be healthy..."
    sleep 5
    
    # Health check
    if curl -sf http://localhost:8001/health > /dev/null; then
        print_success "API is healthy!"
    else
        print_warning "API is still starting up. Check logs with: docker-compose logs -f api"
    fi
    
    echo ""
    echo "Useful commands:"
    echo "  View logs:    docker-compose logs -f api"
    echo "  Stop:         docker-compose down"
    echo "  Add RAG:      ./docker-start.sh full"
}

# Start full stack (with RAG)
start_full() {
    print_header "Starting DevForge (Full Stack - API + RAG)"
    check_prerequisites
    
    echo "This mode runs the complete stack:"
    echo "  • FastAPI backend"
    echo "  • Redis (message broker)"
    echo "  • PostgreSQL + pgvector (vector database)"
    echo "  • Celery worker (async tasks)"
    echo "  • Flower (monitoring UI)"
    echo ""
    
    docker-compose --profile rag up -d --build
    
    echo ""
    print_success "DevForge full stack is starting!"
    echo ""
    echo "Services will be available at:"
    echo "  • API: http://localhost:8001"
    echo "  • API Docs: http://localhost:8001/docs"
    echo "  • Flower: http://localhost:5555"
    echo "  • PostgreSQL: localhost:5432"
    echo "  • Redis: localhost:6379"
    echo ""
    echo "Waiting for services to be healthy..."
    sleep 15
    
    # Health check
    if curl -sf http://localhost:8001/health > /dev/null; then
        print_success "API is healthy!"
    else
        print_warning "API is still starting up. Check logs with: docker-compose logs -f api"
    fi
    
    echo ""
    echo "Useful commands:"
    echo "  View logs:    docker-compose logs -f"
    echo "  View API:     docker-compose logs -f api"
    echo "  View worker:  docker-compose logs -f celery-worker"
    echo "  Stop:         docker-compose down"
}

# Start production mode
start_prod() {
    print_header "Starting DevForge (Production Mode)"
    check_prerequisites
    
    # Check for production password
    if ! grep -q "POSTGRES_PASSWORD" .env || grep -q "devforge123" .env; then
        print_error "Please set a strong POSTGRES_PASSWORD in .env for production!"
        exit 1
    fi
    
    print_warning "Starting in production mode with full RAG stack..."
    echo "Using production configuration with Gunicorn and increased workers"
    
    docker-compose --profile rag -f docker-compose.yml -f docker-compose.prod.yml up -d --build
    
    echo ""
    print_success "DevForge is running in production mode!"
    echo ""
    echo "Services:"
    echo "  • API: http://localhost:8001"
    echo "  • Flower: http://localhost:5555 (basic auth required)"
}

# Start GPU mode
start_gpu() {
    print_header "Starting DevForge (GPU Mode - Full Stack)"
    check_prerequisites
    
    print_warning "Ensure you have nvidia-container-toolkit installed on this host!"
    
    echo "This mode runs the complete stack with GPU acceleration:"
    echo "  • FastAPI backend (GPU enabled)"
    echo "  • Celery worker (GPU enabled)"
    echo "  • Redis + Postgres + Flower"
    echo ""
    
    docker-compose --profile rag -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
    
    echo ""
    print_success "DevForge (GPU) is starting!"
    echo ""
    echo "Services will be available at:"
    echo "  • API: http://localhost:8001"
    echo "  • Flower: http://localhost:5555"
    echo ""
    echo "Waiting for services..."
    sleep 15
    
    if curl -sf http://localhost:8001/health > /dev/null; then
        print_success "API is healthy!"
    else
        print_warning "API is still starting. Check logs: ./docker-start.sh logs api"
    fi
}

# Stop all services
stop_services() {
    print_header "Stopping DevForge"
    docker-compose --profile rag down
    print_success "All services stopped"
}

# View logs
view_logs() {
    print_header "Viewing Logs"
    echo "Press Ctrl+C to exit log viewer"
    
    # Check if service name is provided
    if [ -n "$2" ]; then
        docker-compose logs -f "$2"
    else
        docker-compose logs -f
    fi
}

# Rebuild services
rebuild_services() {
    print_header "Rebuilding DevForge"
    
    MODE="${2:-full}"
    
    echo "Stopping services..."
    docker-compose --profile rag down
    
    echo "Rebuilding images..."
    docker-compose build --no-cache
    
    if [ "$MODE" = "minimal" ]; then
        echo "Starting in minimal mode (API only)..."
        docker-compose up api -d
    else
        echo "Starting in full mode (API + RAG)..."
        docker-compose --profile rag up -d
    fi
    
    print_success "Rebuild complete!"
}

# Show status
show_status() {
    print_header "Service Status"
    docker-compose ps
    
    echo ""
    echo "Health Checks:"
    
    # API health
    if curl -sf http://localhost:8001/health > /dev/null 2>&1; then
        print_success "API: Healthy (http://localhost:8001)"
    else
        print_error "API: Unhealthy or not running"
    fi
    
    # Check if RAG services are running
    if docker ps | grep -q "devforge-redis"; then
        echo ""
        echo "RAG Services:"
        
        # Redis health
        if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
            print_success "Redis: Healthy"
        else
            print_error "Redis: Unhealthy"
        fi
        
        # Postgres health
        if docker-compose exec -T postgres pg_isready -U devforge > /dev/null 2>&1; then
            print_success "Postgres: Healthy"
        else
            print_error "Postgres: Unhealthy"
        fi
        
        # Worker status
        if docker ps | grep -q "devforge-celery-worker"; then
            print_success "Celery Worker: Running"
        else
            print_error "Celery Worker: Not running"
        fi
        
        # Flower status
        if docker ps | grep -q "devforge-flower"; then
            print_success "Flower: Running (http://localhost:5555)"
        fi
    else
        echo ""
        print_warning "RAG services not running (minimal mode)"
        echo "Run './docker-start.sh full' to enable RAG features"
    fi
}

# Main script
COMMAND="${1:-help}"

case "$COMMAND" in
    minimal|api-only)
        start_minimal
        ;;
    full|rag)
        start_full
        ;;
    prod|production)
        start_prod
        ;;
    gpu|nvidia)
        start_gpu
        ;;
    down|stop)
        stop_services
        ;;
    logs)
        view_logs "$@"
        ;;
    rebuild)
        rebuild_services "$@"
        ;;
    status)
        show_status
        ;;
    help|*)
        echo "DevForge Backend - Docker Management Script"
        echo ""
        echo "Usage: $0 <command>"
        echo ""
        echo "Commands:"
        echo "  ${GREEN}minimal${NC}    Start API only (DataGen, GitHub, Cheatsheet)"
        echo "             No Redis, Postgres, or Celery"
        echo ""
        echo "  ${GREEN}full${NC}       Start full stack with RAG services"
        echo "             Includes: API + Redis + Postgres + Celery + Flower"
        echo ""
        echo "  ${YELLOW}prod${NC}       Start in production mode (full stack)"
        echo ""
        echo "  ${BLUE}gpu${NC}        Start with NVIDIA GPU support"
        echo "             Requires nvidia-container-toolkit"
        echo ""
        echo "  ${RED}down${NC}       Stop all services"
        echo ""
        echo "  logs       View logs (add service name: logs api)"
        echo "  rebuild    Rebuild and restart (add 'minimal' or 'full')"
        echo "  status     Show service status and health"
        echo ""
        echo "Examples:"
        echo "  ${BLUE}./docker-start.sh minimal${NC}        # Just FastAPI backend"
        echo "  ${BLUE}./docker-start.sh full${NC}           # Complete stack with RAG"
        echo "  ${BLUE}./docker-start.sh logs api${NC}       # View API logs"
        echo "  ${BLUE}./docker-start.sh rebuild minimal${NC} # Rebuild minimal mode"
        ;;
esac
