# 🐳 DevForge Universal Docker Guide

This master guide consolidates all Docker documentation for the DevForge Backend. It explains **what** we built, **how** it works, **when** to use each mode, and **how** to deploy it.

---

## 🏗️ 1. What We Built: The 3 Dockerfiles
We use a modular architecture with three specialized Dockerfiles. All share the same optimization strategies (multi-stage builds, non-root user, slim base images).

| File | Purpose | Key Features |
| :--- | :--- | :--- |
| **`Dockerfile`** | **The Default** (Dev/Full) | • **CPU-Only PyTorch** (~1GB size)<br>• Multi-stage build (build tools removed)<br>• Used for local dev & general deployment |
| **`Dockerfile.prod`** | **Production** | • **Identical** to default (pointer)<br>• Explicitly intended for immutable prod deployments<br>• Uses `gunicorn` for high availability |
| **`Dockerfile.gpu`** | **GPU Acceleration** | • **CUDA-Enabled PyTorch** (~3-4GB size)<br>• Installs NVIDIA dependencies<br>• Unlocks hardware acceleration for embeddings/LLMs |

#### 🧠 The "Why":
- **Optimization:** We stripped 1.5GB of build tools and unused CUDA binaries from the default image.
- **Security:** Everything runs as non-root user `devforge`.
- **Modularity:** One compose file controls everything via profiles.

---

## 🚦 2. Use Cases: Which Mode Do I Need?

### A. Minimal Mode (API Only)
> "I just want to run the tools (Cheatsheet, DataGen, GitHub Agent) and don't need RAG."
- **Resources:** ~300MB RAM.
- **Services:** `api` only.
- **Start:** `./docker-start.sh minimal`

### B. Full Mode (RAG Support)
> "I need to upload files, search documentation, and use the full RAG pipeline."
- **Resources:** ~1.5GB RAM.
- **Services:** `api`, `redis`, `postgres`, `celery-worker`, `flower`.
- **Start:** `./docker-start.sh full`

### C. GPU Mode (Hardware Accelerated)
> "I have an NVIDIA GPU and want faster processing."
- **Resources:** host GPU + ~2GB RAM.
- **Services:** Same as Full, but with GPU access.
- **Start:** `./docker-start.sh gpu`

---

## 🚀 3. Quick Start (Run Locally)

Prerequisite: Docker Desktop installed.

**1. Setup Environment** (First time only)
```bash
cp .env.docker .env
# Edit .env if you need custom keys (GROQ_API_KEY, etc.)
# Critical: OLLAMA_HOST=http://host.docker.internal:11434
```

**2. Run!**
```bash
chmod +x docker-start.sh

# Run the full stack
./docker-start.sh full
```

**3. Verify**
- **API:** http://localhost:8001
- **Docs:** http://localhost:8001/docs
- **Flower (Tasks):** http://localhost:5555

---

## 📦 4. Deployment Guide

### A. Publish to Docker Hub
1. **Build the Image:**
   ```bash
   docker build -t youruser/devforge-backend:0.9 .
   ```
2. **Push:**
   ```bash
   docker login
   docker push youruser/devforge-backend:0.9
   ```

### B. Run in Production (Server/Cloud)
On your VPS or Cloud (AWS/DigitalOcean/Railway), you only need:
1. `docker-compose.yml`
2. `docker-compose.prod.yml`
3. `.env` (secured!)

**Command:**
```bash
docker-compose \
  -f docker-compose.yml \
  -f docker-compose.prod.yml \
  --profile rag \
  up -d
```
*This activates production settings: Gunicorn server (4 workers), restarts on failure, and Redis persistence.*

---

## 🔄 5. Migration: Local vs Docker

Transitioning from running `uvicorn` locally to Docker? Here is what changed:

| Config | Local (`.env.local`) | Docker (`.env.docker`) | Why? |
| :--- | :--- | :--- | :--- |
| **Ollama** | `localhost:11434` | `host.docker.internal:11434` | Container needs to "break out" to reach host |
| **Redis** | `localhost:6379` | `redis:6379` | Accessible via service name inside network |
| **DB** | `localhost:5432` | `postgres:5432` | Accessible via service name inside network |
| **Uploads** | `./data/uploads` | `/app/data/uploads` | Mapped volume inside container |

**Data Persistence:**  
All your data (ChromaDB vectors, Uploaded files, Postgres data) is safely stored in the `./data` folder on your host machine. **Deleting the container does NOT delete your data.**

---

## 🛠️ Cheat Sheet
| Task | Command |
| :--- | :--- |
| Start Everything | `./docker-start.sh full` |
| View Logs | `./docker-start.sh logs` |
| Stop Everything | `./docker-start.sh down` |
| Rebuild Images | `./docker-start.sh rebuild full` |
| Check Status | `./docker-start.sh status` |
