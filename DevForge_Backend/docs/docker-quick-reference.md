# ⚡ Docker Cheat Sheet

## 🚀 Quick Launch

| Goal | Mac / Linux | Windows (PowerShell) |
| :--- | :--- | :--- |
| **Full Stack** | `./docker-start.sh full` | `docker compose --profile rag up -d` |
| **Minimal API**| `./docker-start.sh minimal`| `docker compose up api -d` |
| **Stop All** | `./docker-start.sh down` | `docker compose --profile rag down` |
| **Rebuild API**| `./docker-start.sh rebuild minimal` | `docker compose up -d --build api` |

---

## 🛠️ Management Commands

### Logs & Monitoring
- **View All Logs:** `docker compose logs -f`
- **View API Logs:** `docker compose logs -f api`
- **Check Status:** `docker compose ps`
- **Health Check:** `curl http://localhost:8001/health`

### Dependency Updates
If you change `requirements.txt`, run this to rebuild the Python environment:
```bash
docker compose up -d --build api
```

---

## 📦 Deployment & Publishing

### Step 1: Login
```bash
docker login
```

### Step 2: Build & Tag
```bash
docker build -t your-username/devforge:0.9 .
```

### Step 3: Push
```bash
docker push your-username/devforge:0.9
```

---

## 🌐 Network Essentials
- **Internal API:** `http://localhost:8001`
- **Internal Docs:** `http://localhost:8001/docs`
- **Internal Database:** `localhost:5432` (Only in Full mode)
- **Host Link (Ollama):** `http://host.docker.internal:11434`
