FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir pymysql cryptography

# Copy application
COPY backend/ ./backend/
COPY src/web/public/ ./src/web/public/

# Create data directory
RUN mkdir -p /app/data /app/db

WORKDIR /app/backend

EXPOSE 3456

CMD ["python3", "main.py"]
