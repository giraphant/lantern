#!/bin/bash
# Quick start script for local testing without Docker

set -e

echo "🚀 Starting Funding Rate Arbitrage Dashboard (Local Mode)"
echo "=========================================================="

# Check if virtual env exists
if [ ! -d "backend/venv" ]; then
    echo "📦 Creating Python virtual environment..."
    cd backend
    python3 -m venv venv
    cd ..
fi

# Install backend dependencies
echo "📦 Installing backend dependencies..."
cd backend
source venv/bin/activate
pip install -q -r requirements.txt
cd ..

# Create data directory
mkdir -p data

# Start backend in background
echo "🔧 Starting backend on port 38888..."
cd backend
source venv/bin/activate
PYTHONPATH=/home/lantern DATABASE_URL=sqlite+aiosqlite:///../data/funding_bot.db uvicorn app.main:app --host 0.0.0.0 --port 38888 > ../data/backend.log 2>&1 &
BACKEND_PID=$!
cd ..

echo "✅ Backend started (PID: $BACKEND_PID)"
echo "📊 Backend API: http://localhost:38888"
echo "📚 API Docs: http://localhost:38888/docs"
echo ""
echo "📝 View backend logs: tail -f data/backend.log"
echo ""
echo "⏳ Waiting 3 seconds for backend to start..."
sleep 3

# Test backend
if curl -s http://localhost:38888/health > /dev/null; then
    echo "✅ Backend health check passed"
else
    echo "❌ Backend health check failed"
    kill $BACKEND_PID 2>/dev/null || true
    exit 1
fi

echo ""
echo "=========================================================="
echo "🎉 Dashboard is running!"
echo ""
echo "Backend API: http://localhost:38888"
echo "API Docs: http://localhost:38888/docs"
echo ""
echo "To stop:"
echo "  kill $BACKEND_PID"
echo ""
echo "To view logs:"
echo "  tail -f data/backend.log"
echo "=========================================================="

# Save PID for easy cleanup
echo $BACKEND_PID > data/backend.pid

# Keep script running
wait $BACKEND_PID
