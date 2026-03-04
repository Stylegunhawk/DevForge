#!/bin/bash

# DevForge Celery Monitoring Script
# Shows worker health, queue status, and task distribution

echo "🔍 DevForge Celery Monitoring"
echo "============================"
echo ""

# Check worker status
echo "📊 Worker Status:"
docker-compose --profile rag ps celery-worker celery-worker-analytics celery-worker-secondary 2>/dev/null | grep -E "(NAME|celery-)" || echo "No workers running"
echo ""

# Check active queues and task counts
echo "📈 Queue Status:"
echo "Checking Redis queue lengths..."
docker exec devforge-redis redis-cli llen default 2>/dev/null | xargs -I {} echo "  default queue: {} tasks"
docker exec devforge-redis redis-cli llen analytics 2>/dev/null | xargs -I {} echo "  analytics queue: {} tasks" || echo "  analytics queue: 0 tasks"
docker exec devforge-redis redis-cli llen usage 2>/dev/null | xargs -I {} echo "  usage queue: {} tasks" || echo "  usage queue: 0 tasks"
docker exec devforge-redis redis-cli llen rag 2>/dev/null | xargs -I {} echo "  rag queue: {} tasks" || echo "  rag queue: 0 tasks"
echo ""

# Check recent task activity
echo "🔄 Recent Task Activity (last 5 minutes):"
if docker exec devforge-postgres psql -U devforge -d devforge -c "SELECT tool_name, COUNT(*) as requests, AVG(duration_ms) as avg_ms FROM request_logs WHERE created_at > NOW() - INTERVAL '5 minutes' GROUP BY tool_name ORDER BY requests DESC;" 2>/dev/null; then
    echo ""
else
    echo "  No recent activity"
fi
echo ""

# Check worker health from logs
echo "💚 Worker Health:"
echo "Primary worker last activity:"
docker logs devforge-celery-worker --tail=5 2>/dev/null | grep -E "(succeeded|received)" | tail -2 || echo "  No recent activity"
echo ""
echo "Analytics worker last activity:"
docker logs devforge-celery-worker-analytics --tail=5 2>/dev/null | grep -E "(succeeded|received)" | tail -2 || echo "  No recent activity"
echo ""

# Flower monitoring status
echo "🌸 Flower Monitoring:"
if curl -s http://localhost:5555 > /dev/null 2>&1; then
    echo "  ✅ Flower is running at http://localhost:5555"
    echo "  📊 View detailed metrics and task history"
else
    echo "  ❌ Flower is not accessible"
    echo "  💡 Start with: docker-compose --profile rag up -d flower"
fi
echo ""

# Memory usage
echo "💾 Memory Usage:"
docker stats --no-stream --format "table {{.Container}}\t{{.MemUsage}}\t{{.CPUPerc}}" | grep -E "(CONTAINER|celery-)" || echo "  No containers found"
echo ""

echo "✨ Monitoring complete!"
echo "💡 Use './scripts/scale_celery.sh rag monitor' to open Flower UI"
