FROM python:3.11-slim

WORKDIR /app

# System deps + Docker CLI (for self-update via mounted docker.sock)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl ca-certificates gnupg && \
    install -m 0755 -d /etc/apt/keyrings && \
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian bookworm stable" > /etc/apt/sources.list.d/docker.list && \
    apt-get update && apt-get install -y --no-install-recommends docker-ce-cli docker-compose-plugin && \
    rm -rf /var/lib/apt/lists/*

# Install Hermes Agent from source
RUN git clone --depth 1 https://github.com/NousResearch/hermes-agent.git /root/hermes && \
    cd /root/hermes && \
    pip install --no-cache-dir -e . && \
    pip install --no-cache-dir anthropic httpx[socks]

# Install Myna backend dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir pymysql cryptography

# Copy application
COPY backend/ ./backend/
COPY src/web/public/ ./src/web/public/

# Version (injected at build time by CI)
ARG MYNA_VERSION=dev
ENV MYNA_VERSION=${MYNA_VERSION}

# Create data directories
RUN mkdir -p /app/data /app/db /root/.hermes/profiles

WORKDIR /app/backend

EXPOSE 3456

CMD ["python3", "main.py"]
