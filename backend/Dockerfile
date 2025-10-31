FROM python:3.10-slim

WORKDIR /app

# Install git (needed for git+ dependencies)
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Copy main requirements first (for exchange dependencies)
COPY requirements.txt /tmp/main-requirements.txt

# Install main dependencies first
RUN pip install --no-cache-dir -r /tmp/main-requirements.txt

# Then install backend-specific dependencies
COPY backend/requirements-minimal.txt .
RUN pip install --no-cache-dir -r requirements-minimal.txt

# Copy application
COPY backend/app ./app

# Copy src directory (for exchange clients)
COPY src ./src

# Create data directory
RUN mkdir -p /app/data

# Expose port
EXPOSE 8000

# Set Python path
ENV PYTHONPATH=/app:/app/src

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
