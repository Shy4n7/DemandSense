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

# Copy built React app (pre-built locally to save RAM)
COPY frontend/build ./frontend/build

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
