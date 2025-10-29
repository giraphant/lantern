# Use Python 3.10 slim image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install git (required for pip to clone dependencies from GitHub)
RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir grvt-pysdk

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p logs

# Default command - parameters are read from environment variables
# Set these in Coolify's environment variables section
CMD ["python3", "hedge/hedge_bot_v2.py"]
