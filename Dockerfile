# ── Stage 1: Build the React frontend ────────────────────────────────────────
FROM node:20-slim AS frontend-builder

WORKDIR /frontend

# Install dependencies (cached layer)
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --prefer-offline 2>/dev/null || npm install

# Copy source
COPY frontend/ ./

# VITE_API_BASE_URL: empty = relative paths through Nginx (same-host Docker).
# Override at build time if the frontend needs to call a separate backend host.
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build


# ── Stage 2: Final image (Python API + Nginx + built frontend) ────────────────
FROM python:3.11-slim

# Install Nginx
RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer cache — only rebuilds on requirements change)
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

# Nginx config — remove all default configs, install ours
RUN rm -f /etc/nginx/sites-enabled/default \
       /etc/nginx/sites-available/default
COPY nginx.conf /etc/nginx/sites-available/demandsense
RUN ln -s /etc/nginx/sites-available/demandsense /etc/nginx/sites-enabled/demandsense

# Health check — Oracle Cloud load balancer uses this to confirm readiness
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost/api/products || exit 1

EXPOSE 80

CMD ["/app/start.sh"]
