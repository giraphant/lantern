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

# Copy application code and structure
COPY src ./src

# Create logs directory
RUN mkdir -p logs

# Default command - run funding rate arbitrage bot
# Parameters are read from environment variables
CMD ["python3", "src/hedge_bot_funding.py"]
