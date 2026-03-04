# Celery Worker Scaling Guide

DevForge backend supports horizontal scaling of Celery workers for handling increased analytics load and task distribution.

## Architecture Overview

### Worker Types

1. **Primary Worker** (`celery-worker`)
   - Concurrency: 4 workers (configurable via `CELERY_WORKERS`)
   - Queues: `default`, `analytics`
   - Handles: General tasks, API key updates, fallback analytics

2. **Analytics Worker** (`celery-worker-analytics`)
   - Concurrency: 2 workers (configurable via `CELERY_ANALYTICS_WORKERS`)
   - Queues: `analytics`, `usage`
   - Handles: Request logging, LLM usage tracking

3. **Secondary Worker** (`celery-worker-secondary`)
   - Concurrency: 2 workers (configurable via `CELERY_SECONDARY_WORKERS`)
   - Queues: `default`, `usage`
   - Handles: Load balancing for high traffic

### Queue Configuration

```python
task_routes = {
    'src.workers.tasks.analytics_tasks.log_request_call': {'queue': 'analytics'},
    'src.workers.tasks.usage_tasks.log_llm_usage': {'queue': 'usage'},
    'src.workers.tasks.auth_tasks.update_key_last_used': {'queue': 'default'},
    'src.workers.tasks.rag_tasks.*': {'queue': 'rag'},
}
```

## Quick Start

### Start All Workers
```bash
./scripts/scale_celery.sh rag scale
```

### Check Status
```bash
./scripts/scale_celery.sh rag status
```

### Monitor Performance
```bash
./scripts/monitor_celery.sh
```

## Management Scripts

### scale_celery.sh
```bash
# Start primary workers
./scripts/scale_celery.sh rag start

# Scale up all workers (including secondary)
./scripts/scale_celery.sh rag scale

# Stop all workers
./scripts/scale_celery.sh rag stop

# Restart workers
./scripts/scale_celery.sh rag restart

# Check status
./scripts/scale_celery.sh rag status

# View logs
./scripts/scale_celery.sh rag logs

# Open Flower monitoring
./scripts/scale_celery.sh rag monitor
```

### monitor_celery.sh
```bash
# Comprehensive monitoring
./scripts/monitor_celery.sh
```

Shows:
- Worker status and health
- Queue lengths
- Recent task activity
- Memory usage
- Flower monitoring status

## Environment Configuration

### Worker Concurrency Settings

```bash
# .env.docker
CELERY_WORKERS=4                    # Primary worker concurrency
CELERY_ANALYTICS_WORKERS=2          # Analytics-dedicated worker concurrency  
CELERY_SECONDARY_WORKERS=2          # Secondary worker concurrency
```

### Scaling Recommendations

| Load Level | Primary | Analytics | Secondary | Total Workers |
|------------|---------|-----------|-----------|--------------|
| Low        | 2       | 1         | -         | 3            |
| Medium     | 4       | 2         | -         | 6            |
| High       | 6       | 3         | 2         | 11           |
| Production | 8       | 4         | 4         | 16           |

## Docker Compose Profiles

### Standard Profile
```bash
docker-compose --profile rag up -d
# Starts: api, redis, postgres, celery-worker, flower
```

### Scale Profile
```bash
docker-compose --profile rag,scale up -d
# Starts: + celery-worker-analytics, celery-worker-secondary
```

## Queue Monitoring

### Redis Queue Lengths
```bash
# Check queue backlog
docker exec devforge-redis redis-cli llen default
docker exec devforge-redis redis-cli llen analytics
docker exec devforge-redis redis-cli llen usage
docker exec devforge-redis redis-cli llen rag
```

### Task Distribution
```bash
# View recent task activity
docker exec devforge-postgres psql -U devforge -c "
  SELECT tool_name, COUNT(*) as requests, AVG(duration_ms) as avg_ms 
  FROM request_logs 
  WHERE created_at > NOW() - INTERVAL '5 minutes' 
  GROUP BY tool_name 
  ORDER BY requests DESC;"
```

## Performance Tuning

### Worker Concurrency
- **CPU-bound tasks**: Set concurrency to number of CPU cores
- **I/O-bound tasks**: Set concurrency 2-4x CPU cores
- **Mixed workload**: Start with 4 workers per container

### Prefetch Multiplier
```python
# In celery_app.py
worker_prefetch_multiplier=1  # Prevents worker overload
```

### Task Time Limits
```bash
CELERY_TASK_SOFT_TIME_LIMIT=300  # 5 minutes
CELERY_TASK_TIME_LIMIT=360       # 6 minutes
```

## Flower Monitoring

### Access Flower UI
```bash
# Start Flower
docker-compose --profile rag up -d flower

# Access at http://localhost:5555
```

### Flower Features
- Real-time task monitoring
- Worker status and health
- Task success/failure rates
- Execution time analytics
- Queue depth visualization

## Troubleshooting

### Common Issues

1. **Workers not starting**
   ```bash
   # Check logs
   docker logs devforge-celery-worker
   
   # Verify Redis connection
   docker exec devforge-redis redis-cli ping
   ```

2. **Queue backlog building up**
   ```bash
   # Scale up workers
   ./scripts/scale_celery.sh rag scale
   
   # Check worker health
   ./scripts/monitor_celery.sh
   ```

3. **High memory usage**
   ```bash
   # Reduce concurrency
   export CELERY_WORKERS=2
   docker-compose restart celery-worker
   ```

4. **Tasks not routing correctly**
   ```bash
   # Verify queue configuration
   docker logs devforge-celery-worker | grep -i queue
   ```

### Health Checks

```bash
# Worker health
docker exec devforge-celery-worker celery -A src.workers.celery_app inspect active

# Queue health
docker exec devforge-redis redis-cli info memory

# Database health
docker exec devforge-postgres pg_isready -U devforge
```

## Production Deployment

### Recommended Configuration
```bash
# Production worker settings
CELERY_WORKERS=8
CELERY_ANALYTICS_WORKERS=4
CELERY_SECONDARY_WORKERS=4

# Enable all workers
docker-compose --profile rag,scale up -d
```

### Monitoring Setup
```bash
# Set up monitoring
./scripts/monitor_celery.sh

# Configure alerts for:
# - Queue depth > 100 tasks
# - Worker failure rate > 5%
# - Memory usage > 80%
# - Task duration > 5 minutes
```

### Backup and Recovery
```bash
# Backup Redis queues
docker exec devforge-redis redis-cli BGSAVE

# Restore from backup
docker exec devforge-redis redis-cli FLUSHALL
docker exec devforge-redis redis-cli RESTORE /data/dump.rdb
```

## Load Testing

### Concurrent Request Test
```bash
# Test with 20 concurrent requests
for i in {1..20}; do
  curl -s -X POST http://localhost:8001/api/gateway \
    -H "Content-Type: application/json" \
    -H "x-api-key: YOUR_API_KEY" \
    -d '{"name": "generate_data", "arguments": {"rows": 10}}' \
    > /dev/null &
done
wait

# Monitor results
./scripts/monitor_celery.sh
```

### Stress Test
```bash
# High-volume test (100 requests)
seq 1 100 | xargs -I {} -P 10 curl -s -X POST \
  http://localhost:8001/api/gateway \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_KEY" \
  -d '{"name": "refine_prompt", "arguments": {"prompt": "test"}}' \
  > /dev/null
```

This scaling configuration ensures DevForge can handle increased analytics load while maintaining performance and reliability.
