FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy MVP application files
COPY *.py .
COPY *.html .

# Expose ports for different MVP services
EXPOSE 8765 8080 8081

# Default command (can be overridden in docker-compose)
CMD ["python", "realtime_market_summary.py"]