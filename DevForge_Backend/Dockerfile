# Dockerfile
FROM python:3.12-slim

# 1. Install System Dependencies
# libmagic is REQUIRED for the new MIME type detection in V3
RUN apt-get update && apt-get install -y \
    libmagic1 \
    libmagic-dev \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 2. Setup Workdir
WORKDIR /app

# 3. Install Python Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy Code
COPY . .

# 5. Create Data Directory & Set Permissions
# This ensures the worker can write to the uploads folder
RUN mkdir -p data/uploads && chmod 777 data/uploads

# Default command
CMD ["celery", "-A", "src.workers.celery_app", "worker", "-l", "info"]