# Docker Deployment Quick Reference

Quick reference for deploying DevForge Backend with different configurations.

---

## 🎯 Deployment Modes

DevForge supports **modular deployment** using Docker Compose profiles:

| Mode | Services | Use Case | Command |
|------|----------|----------|---------|
| **Minimal** | API only | DataGen, GitHub, Cheatsheet, Prompt Refiner | `./docker-start.sh minimal` |
| **Full** | API + RAG stack | All features including RAG | `./docker-start.sh full` |
| **GPU** | Full stack + NVIDIA GPU | Hardware accelerated RAG | `./docker-start.sh gpu` |
| **Production** | Full stack (optimized) | Production deployment | `./docker-start.sh prod` |

---

## 🚀 Quick Start Commands

### Start API Only (Lightweight)

```bash
# Using the script (recommended)
./docker-start.sh minimal

# Or directly with docker-compose
docker-compose up api -d
```

**What you get:**
- ✅ FastAPI backend on port 8000
- ✅ DataGen tool (generate mock data)
- ✅ GitHub automation
- ✅ Cheatsheet generator
- ✅ Prompt refiner
- ❌ **RAG features disabled** (no file ingestion, no semantic search)

**Resource usage:** ~200-300 MB RAM

---

### Start Full Stack (with RAG)

```bash
# Using the script (recommended)
./docker-start.sh full

# Or directly with docker-compose
docker-compose --profile rag up -d

# Alternative using environment variable
COMPOSE_PROFILES=rag docker-compose up -d
```

**What you get:**
- ✅ Everything from minimal mode, PLUS:
- ✅ RAG document ingestion
- ✅ Semantic search with embeddings
- ✅ Redis (message broker)
- ✅ PostgreSQL + pgvector (vector database)
- ✅ Celery worker (async tasks)
- ✅ Flower monitoring UI

**Resource usage:** ~1-2 GB RAM

**Services:**
- API: http://localhost:8001
- API Docs: http://localhost:8001/docs
- Flower: http://localhost:5555
- PostgreSQL: localhost:5432
- Redis: localhost:6379

---

### Start GPU Mode (Hardware Accelerated)

```bash
# Using the script
./docker-start.sh gpu
```

**What you get:**
- ✅ All Full Mode features
- ✅ **GPU Acceleration** for PyTorch and Embeddings
- 🚀 Much faster document ingestion and search

**Requires:**
- NVIDIA GPU
- NVIDIA Container Toolkit on host


---

## 📊 Service Architecture

### Minimal Mode
```
┌─────────────────┐
│   FastAPI API   │  :8000
│                 │
│ • DataGen       │
│ • GitHub Agent  │
│ • Cheatsheet    │
│ • Prompt Refiner│
└─────────────────┘
```

### Full Mode (RAG Enabled)
```
┌─────────────────┐
│   FastAPI API   │  :8000
│                 │
│ • All Features  │
└────────┬────────┘
         │
    ┌────┴─────┬─────────┬──────────┐
    │          │         │          │
┌───▼───┐  ┌──▼───┐  ┌──▼────┐  ┌──▼────┐
│ Redis │  │Postgres│ │Celery │  │Flower │
│ :6379 │  │ :5432  │ │Worker │  │ :5555 │
└───────┘  └────────┘ └───────┘  └───────┘
```

---

## 🔧 Management Commands

### Check Service Status

```bash
./docker-start.sh status

# Or manually
docker-compose ps
curl http://localhost:8001/health
```

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f api
docker-compose logs -f celery-worker

# Or using script
./docker-start.sh logs api
```

### Stop Services

```bash
./docker-start.sh down

# Or manually
docker-compose --profile rag down
```

### Rebuild After Code Changes

```bash
# Rebuild minimal mode
./docker-start.sh rebuild minimal

# Rebuild full mode
./docker-start.sh rebuild full

# Or manually
docker-compose build
docker-compose --profile rag up -d --build
```

---

## 🎛️ Switching Between Modes

### From Minimal to Full (Enable RAG)

```bash
# Stop current services
docker-compose down

# Start with RAG profile
./docker-start.sh full
```

### From Full to Minimal (Disable RAG)

```bash
# Stop all services (including RAG)
docker-compose --profile rag down

# Start only API
./docker-start.sh minimal
```

---

## 🔍 Feature Availability Matrix

| Feature | Minimal | Full | Dependencies |
|---------|---------|------|--------------|
| DataGen | ✅ | ✅ | None |
| GitHub Agent | ✅ | ✅ | GitHub token |
| Cheatsheet | ✅ | ✅ | LLM (Ollama/Groq) |
| Prompt Refiner | ✅ | ✅ | LLM (Ollama/Groq) |
| RAG Ingestion | ❌ | ✅ | Redis + Celery + Postgres |
| RAG Search | ❌ | ✅ | Redis + Celery + Postgres |
| Flower UI | ❌ | ✅ | Celery |

---

## 💡 When to Use Each Mode

### Use **Minimal Mode** when:
- You only need non-RAG features (DataGen, GitHub, etc.)
- Running on limited resources (< 1 GB RAM)
- Quick testing or development
- Don't need document ingestion or semantic search
- Running in CI/CD pipelines

### Use **Full Mode** when:
- You need RAG features (document upload, semantic search)
- Running development environment
- Have adequate resources (> 1 GB RAM)
- Need async task processing
- Want to monitor tasks via Flower

### Use **Production Mode** when:
- Deploying to staging/production
- Need performance tuning (Gunicorn, more workers)
- Require security hardening
- Need persistent data and backups

---

## 🐛 Troubleshooting

### RAG Features Not Working in Minimal Mode

**This is expected!** RAG requires Redis, Postgres, and Celery.

**Solution:**
```bash
docker-compose down
./docker-start.sh full
```

### Port Conflicts

```bash
# Change ports in docker-compose.yml
# API: Change "8000:8000" to "8001:8000"
# Redis: Change "6379:6379" to "6380:6379"
# etc.
```

### Cannot Connect to Ollama

```bash
# In .env, use host.docker.internal for Mac/Windows
OLLAMA_HOST=http://host.docker.internal:11434

# For Linux, use host IP
OLLAMA_HOST=http://172.17.0.1:11434
```

### Database Connection Errors

**In minimal mode:** This is normal - no database is running.

**In full mode:**
```bash
# Check if postgres is healthy
docker-compose exec postgres pg_isready -U devforge

# View postgres logs
docker-compose logs postgres
```

---

## 📦 Resource Requirements

### Minimal Mode
- **RAM**: 200-300 MB
- **Disk**: ~500 MB (Docker image)
- **CPU**: 1 core sufficient

### Full Mode
- **RAM**: 1-2 GB (more with active RAG tasks)
- **Disk**: ~2 GB (images + data volumes)
- **CPU**: 2+ cores recommended

### Production Mode
- **RAM**: 2-4 GB
- **Disk**: 5-10 GB (with logs and backups)
- **CPU**: 4+ cores recommended

---

## 🔗 Additional Resources

- [Full Docker Deployment Guide](./docker-deployment.md)
- [Main README](../README.md)
- [RAG Architecture Docs](./rag_architecture.md)

---

**Quick Help:**
```bash
# Show all available commands
./docker-start.sh help

# Check service status
./docker-start.sh status
```
