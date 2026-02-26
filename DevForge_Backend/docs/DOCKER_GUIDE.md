# 🐳 DevForge Backend: Docker Guide (v2.0)

This guide will help you run the DevForge Backend using Docker. Docker ensures the app runs exactly the same way on every machine, without you needing to manually install Python, Postgres, or Redis.

---

## 🏗️ 1. Choose Your Mode
We use **Profiles** to keep things lightweight. You only run what you need.

| Mode | Use Case | Resources | Commands |
| :--- | :--- | :--- | :--- |
| **Minimal** | Fast testing, GitHub tools, Cheatsheet | ~300MB RAM | `api` service only |
| **Full (RAG)** | Document search, file uploads, full RAG | ~1.5GB RAM | `api` + `redis` + `postgres` + `celery` |
| **GPU** | Hardware-accelerated RAG (NVIDIA only) | Host GPU | Same as Full |

---

## 🚀 2. Quick Start

### Step 1: Initialize Environment
Before running Docker, you need a configuration file.
```bash
# Mac / Linux / Windows WSL
cp .env.docker .env

# Windows (PowerShell)
copy .env.docker .env
```
> [!IMPORTANT]
> If you are using **Ollama** installed on your host (Mac/Windows), ensure your `.env` has:  
> `OLLAMA_HOST=http://host.docker.internal:11434`

### Step 2: Run the Backend

#### 🍎 For Mac / Linux Users
Use the included helper script:
```bash
chmod +x docker-start.sh

# Run Full Stack (Recommended)
./docker-start.sh full

# Run Minimal (API Only)
./docker-start.sh minimal
```

#### 🪟 For Windows Users (Native PowerShell)
Run these commands directly in your terminal:
```powershell
# Run Full Stack (Recommended)
docker compose --profile rag up -d --build

# Run Minimal (API Only)
docker compose up api -d --build
```

---

## 🛠️ 3. Managing Your Backend

### 🔄 How to Update Dependencies
If you add a new library to `requirements.txt`, you **must** rebuild the image to see the changes inside Docker:
```bash
docker compose up -d --build api
```

### 📝 Viewing Logs (Troubleshooting)
If something isn't working, check the logs:
```bash
# All services
docker compose logs -f

# Only the API
docker compose logs -f api
```

### 🛑 Stopping Everything
```bash
docker compose --profile rag down
```

---

## 📦 4. Publishing to GitHub / Docker Hub
To share your image or deploy it to a server:

1. **Build & Tag:**
   ```bash
   docker build -t your-username/devforge:latest .
   ```
2. **Push to Docker Hub:**
   ```bash
   docker login
   docker push your-username/devforge:latest
   ```

---

## 🔍 Troubleshooting (Windows)

- **Port 8001 is busy:** If the container won't start because the port is in use, stop any local Python servers running on `8001`.
- **Can't connect to Database:** In **Minimal** mode, the database is NOT running. Switch to **Full** mode if you need RAG features.
- **Ollama Error:** Ensure Ollama is running on your Mac/PC and that your firewall allows Docker to reach it.

---

## 🔗 Useful Links
- **API Dashboard:** [http://localhost:8001](http://localhost:8001)
- **Interactive Docs:** [http://localhost:8001/docs](http://localhost:8001/docs)
- **Task Monitor (Flower):** [http://localhost:5555](http://localhost:5555)
