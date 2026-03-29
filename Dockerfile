FROM python:3.11-slim

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directories
RUN mkdir -p data/ceo_desk data/router_inbox \
    data/departments/marketing data/departments/sales \
    data/departments/consulting data/departments/delivery \
    data/departments/automation data/departments/finance

# Non-root user for security
RUN useradd -m -r appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Production: uvicorn with multiple workers
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--log-level", "info"]
