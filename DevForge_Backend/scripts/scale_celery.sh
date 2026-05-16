#!/bin/bash

# DevForge Celery Worker Scaling Script
# Usage: ./scripts/scale_celery.sh [profile] [action]

set -e

PROFILE=${1:-rag}
ACTION=${2:-status}

echo "🔧 DevForge Celery Worker Management"
echo "=================================="

case $ACTION in
    "start")
        echo "🚀 Starting Celery workers with profile: $PROFILE"
        docker-compose --profile $PROFILE up -d celery-worker celery-worker-analytics
        echo "✅ Primary and analytics workers started"
        ;;
    
    "scale")
        echo "📈 Scaling up with additional workers"
        docker-compose --profile $PROFILE,scale up -d
        echo "✅ All workers scaled up"
        ;;
    
    "stop")
        echo "🛑 Stopping all Celery workers"
        docker-compose --profile $PROFILE,scale stop celery-worker celery-worker-analytics celery-worker-secondary
        echo "✅ Workers stopped"
        ;;
    
    "restart")
        echo "🔄 Restarting Celery workers"
        docker-compose --profile $PROFILE restart celery-worker celery-worker-analytics
        echo "✅ Workers restarted"
        ;;
    
    "status")
        echo "📊 Checking worker status..."
        docker-compose --profile $PROFILE ps
        echo ""
        echo "🌸 Flower monitoring: http://localhost:5555"
        ;;
    
    "logs")
        echo "📋 Showing worker logs..."
        docker-compose --profile $PROFILE logs -f --tail=50 celery-worker celery-worker-analytics
        ;;
    
    "monitor")
        echo "🌸 Opening Flower monitoring..."
        if curl -s http://localhost:5555 > /dev/null; then
            echo "Flower is running at http://localhost:5555"
        else
            echo "Starting Flower..."
            docker-compose --profile $PROFILE up -d flower
            sleep 5
            echo "Flower available at http://localhost:5555"
        fi
        ;;
    
    *)
        echo "Usage: $0 [profile] [action]"
        echo ""
        echo "Profiles:"
        echo "  rag      - RAG profile (default)"
        echo "  scale    - Include secondary workers"
        echo ""
        echo "Actions:"
        echo "  start    - Start primary workers"
        echo "  scale    - Start all workers (including secondary)"
        echo "  stop     - Stop all workers"
        echo "  restart  - Restart workers"
        echo "  status   - Show worker status"
        echo "  logs     - Show worker logs"
        echo "  monitor  - Open Flower monitoring"
        echo ""
        echo "Examples:"
        echo "  $0 rag start     # Start primary workers"
        echo "  $0 rag scale     # Start all workers"
        echo "  $0 rag status    # Check status"
        echo "  $0 rag monitor   # Open Flower UI"
        exit 1
        ;;
esac
