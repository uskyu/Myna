FROM node:20-slim

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm ci --production 2>/dev/null || npm install --production

# Copy source
COPY src/ ./src/
COPY .env.example ./.env.example

# Create data directory
RUN mkdir -p /app/db

ENV NODE_ENV=production
ENV PORT=3000
ENV DATA_DIR=/app/db

EXPOSE 3000

CMD ["node", "src/index.js"]
