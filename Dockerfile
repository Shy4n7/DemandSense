# ── Stage 1: Build the React frontend ────────────────────────────────────────
FROM node:20-slim AS frontend-builder

WORKDIR /frontend

# Install dependencies (cached layer)
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --prefer-offline 2>/dev/null || npm install

# Copy source and build
COPY frontend/ ./
RUN npm run build


# ── Stage 2: Final image (Python API + Nginx + built frontend) ────────────────
FROM python:3.11-slim

# Install Nginx and supervisor
RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies (cached layer — copy requirements first)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY api/      ./api/
COPY lib/      ./lib/
COPY data/     ./data/
COPY models/   ./models/
COPY server.py .
COPY start.sh  .
RUN chmod +x start.sh

# Copy built React app from stage 1
COPY --from=frontend-builder /frontend/build ./frontend/build

# Nginx config
COPY nginx.conf /etc/nginx/sites-available/default
RUN ln -sf /etc/nginx/sites-available/default /etc/nginx/sites-enabled/default \
    && rm -f /etc/nginx/sites-enabled/default.bak

# Expose port 80 (Nginx)
EXPOSE 80

CMD ["/app/start.sh"]
