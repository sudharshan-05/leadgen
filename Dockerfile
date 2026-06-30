# Dockerfile - Production Cloud-Native Setup with Playwright + Chromium
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Set python environment flags
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    EXPORTS_FOLDER=/app/exports

# Workdir definition
WORKDIR /app

# Copy dependencies first (layer caching optimization)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Pre-verify and install Playwright chromium browser binaries
RUN playwright install chromium

# Copy app code
COPY . .

# Create all required runtime directories with full write permissions
# This is CRITICAL to prevent [Errno 13] Permission denied in cloud deployments
RUN mkdir -p /app/exports /app/logs /app/outputs \
    && chmod -R 777 /app/exports /app/logs /app/outputs

# Expose health API port
EXPOSE 8000

# Default cmd - override with --service flag in docker-compose.yml
CMD ["python", "main.py", "--service", "bot"]
