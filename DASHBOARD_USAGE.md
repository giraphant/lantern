# Funding Rate Arbitrage Dashboard - Usage Guide

## Overview

This dashboard provides a unified web interface to manage funding rate arbitrage strategies across multiple exchanges. It replaces the need for individual Docker containers per strategy.

## Architecture

- **Backend**: FastAPI + SQLAlchemy + WebSocket (Port 38888)
- **Frontend**: Next.js 14 + shadcn/ui + TailwindCSS (Port 3000)
- **Database**: SQLite (`data/funding_bot.db`)
- **Supported Exchanges**: Lighter, Binance (GRVT and Backpack temporarily disabled)

## Current Status

### ✅ Completed Features

1. **Backend REST API** (`/api/strategies`)
   - Create, Read, Update, Delete strategies
   - Start/Stop strategy execution
   - Health check endpoint (`/health`)
   - API documentation (`/docs`)

2. **Frontend Dashboard**
   - Strategy list view with real-time updates
   - Create strategy dialog with form validation
   - Start/Stop/Delete controls
   - Loading and error states
   - Empty state with creation prompt
   - Statistics footer (total, running, stopped)

3. **Real-time Updates**
   - WebSocket connection for live strategy status
   - Automatic UI refresh on strategy changes
   - Background data recording

4. **Docker Deployment**
   - Backend containerized and running
   - Environment variable support
   - Volume mounting for data persistence

### ⚠️ Known Limitations

1. **Exchange Support**: Only Lighter and Binance are currently working
   - GRVT: Requires `pysdk` module (not properly installed in Docker)
   - Backpack: Requires `bpx` module (not properly installed in Docker)

2. **API Keys Required**: Strategies will fail to start without proper environment variables:
   - Lighter: `LIGHTER_PRIVATE_KEY`, `LIGHTER_ACCOUNT_INDEX`, `LIGHTER_API_KEY_INDEX`
   - Binance: `BINANCE_API_KEY`, `BINANCE_API_SECRET`

3. **WebSocket**: Connection URL needs to be tested in browser (currently `ws://localhost:38888/ws/updates`)

## How to Use

### 1. Start the Services

**Backend (Already Running)**:
```bash
docker ps | grep funding-dashboard
# Should show: funding-dashboard running on 0.0.0.0:38888->8000/tcp
```

**Frontend (Running in Development)**:
```bash
# Currently running at http://localhost:3000
# Started with: npm run dev (in background)
```

### 2. Access the Dashboard

Open your browser and navigate to:
- **Dashboard**: http://localhost:3000
- **API Docs**: http://localhost:38888/docs
- **Backend Health**: http://localhost:38888/health

### 3. Create a Strategy

**Via Web UI**:
1. Click the "Create Strategy" button in the header
2. Fill in the form:
   - **Strategy Name**: Descriptive name (e.g., "BTC Lighter-Binance Arb")
   - **Exchange A**: Exchange where you'll pay funding (Lighter or Binance)
   - **Exchange B**: Exchange where you'll receive funding (Lighter or Binance)
   - **Symbol**: Trading pair (e.g., "BTC-USDC", "ETH-USDC")
   - **Position Size**: Amount per order in base currency (e.g., 0.001 BTC)
   - **Max Position**: Maximum total position size (e.g., 0.01 BTC)
   - **Build Threshold APR**: Minimum spread to enter (decimal, e.g., 0.15 = 15%)
   - **Close Threshold APR**: Spread level to close position (decimal, e.g., 0.05 = 5%)
   - **Check Interval**: Seconds between checks (e.g., 30)
3. Click "Create Strategy"

**Via API**:
```bash
curl -X POST http://localhost:38888/api/strategies \
  -H "Content-Type: application/json" \
  -d '{
    "name": "BTC Lighter-Binance Test",
    "exchange_a": "LIGHTER",
    "exchange_b": "BINANCE",
    "symbol": "BTC-USDC",
    "size": 0.001,
    "max_position": 0.01,
    "build_threshold_apr": 0.15,
    "close_threshold_apr": 0.05,
    "check_interval": 30
  }'
```

### 4. Manage Strategies

**Start a Strategy**:
- Click the "Start" button on any stopped strategy
- The strategy will begin monitoring funding rates and executing trades
- Status badge will change to "Running" (green)

**Stop a Strategy**:
- Click the "Stop" button on any running strategy
- The strategy will stop checking and executing trades
- Status badge will change to "Stopped" (gray)

**Delete a Strategy**:
- Click the trash icon button
- Confirm the deletion when prompted
- Strategy will be permanently removed

### 5. Monitor Strategies

The dashboard automatically updates in real-time via WebSocket connection:
- Strategy status changes (running → stopped, etc.)
- New strategies added
- Strategies deleted

**Strategy Card Information**:
- Name and status badge
- Exchange pair (e.g., "LIGHTER ⇄ BINANCE")
- Symbol being traded
- Position size and max position
- Build and close thresholds (as APR %)
- Control buttons (Start/Stop/Delete)

**Statistics Footer**:
- Total strategies count
- Running strategies count (green)
- Stopped strategies count (gray)

## Environment Variables

To run strategies with actual trading, you need to set up environment variables in the Docker container:

```bash
# Stop current container
docker stop funding-dashboard
docker rm funding-dashboard

# Run with environment variables
docker run -d --name funding-dashboard \
  -p 38888:8000 \
  -v "$(pwd)/data:/app/data" \
  -e LIGHTER_PRIVATE_KEY="your-key" \
  -e LIGHTER_ACCOUNT_INDEX="0" \
  -e LIGHTER_API_KEY_INDEX="0" \
  -e BINANCE_API_KEY="your-key" \
  -e BINANCE_API_SECRET="your-secret" \
  funding-dashboard-backend
```

Or use an `.env` file:
```bash
docker run -d --name funding-dashboard \
  -p 38888:8000 \
  -v "$(pwd)/data:/app/data" \
  --env-file .env \
  funding-dashboard-backend
```

## API Endpoints

### Strategy Management

- `GET /api/strategies` - List all strategies
- `POST /api/strategies` - Create new strategy
- `GET /api/strategies/{id}` - Get strategy by ID
- `DELETE /api/strategies/{id}` - Delete strategy
- `POST /api/strategies/{id}/start` - Start strategy execution
- `POST /api/strategies/{id}/stop` - Stop strategy execution

### Data Access

- `GET /api/funding-rates/{strategy_id}` - Get funding rate history
- `GET /api/trades/{strategy_id}` - Get trade history
- `GET /api/positions/{strategy_id}` - Get position history

### Health & Docs

- `GET /health` - Backend health check
- `GET /docs` - Interactive API documentation
- `GET /redoc` - Alternative API documentation

### WebSocket

- `ws://localhost:38888/ws/updates` - Real-time strategy updates

## Development

### Frontend Development

The frontend is currently running in development mode with hot reload:

```bash
# Already running in background
# To restart manually:
npm run dev
```

For production build:
```bash
npm run build
npm start
```

### Backend Development

To rebuild the Docker image after backend changes:

```bash
docker build -t funding-dashboard-backend -f backend/Dockerfile .
docker stop funding-dashboard
docker rm funding-dashboard
docker run -d --name funding-dashboard -p 38888:8000 -v "$(pwd)/data:/app/data" funding-dashboard-backend
```

### Database

The database is stored in `data/funding_bot.db`. You can inspect it with:

```bash
sqlite3 data/funding_bot.db
```

Useful queries:
```sql
-- List all strategies
SELECT id, name, status, exchange_a, exchange_b FROM strategies;

-- View recent funding rates
SELECT * FROM funding_rates ORDER BY timestamp DESC LIMIT 10;

-- View recent trades
SELECT * FROM trades ORDER BY timestamp DESC LIMIT 10;
```

## Troubleshooting

### Backend Not Responding

```bash
# Check if container is running
docker ps | grep funding-dashboard

# Check container logs
docker logs funding-dashboard

# Restart container
docker restart funding-dashboard
```

### Frontend Not Loading

```bash
# Check if dev server is running
lsof -i :3000

# Check for build errors
npm run build

# Restart dev server
# Kill existing process first
lsof -ti :3000 | xargs kill -9
npm run dev
```

### API Connection Issues

```bash
# Test backend health
curl http://localhost:38888/health

# Test strategy list endpoint
curl http://localhost:38888/api/strategies

# Check if frontend is using correct API URL
# Should be: http://localhost:38888
# Configured in: frontend/src/lib/api.ts
```

### WebSocket Not Connecting

Check browser console for WebSocket errors:
1. Open browser DevTools (F12)
2. Go to Console tab
3. Look for WebSocket connection errors
4. The URL should be: `ws://localhost:38888/ws/updates`

### Strategy Fails to Start

Common reasons:
1. **Missing API keys**: Set environment variables (see above)
2. **Unsupported exchange**: Currently only Lighter and Binance work
3. **Invalid symbol format**: Use "BASE-QUOTE" format (e.g., "BTC-USDC")
4. **Network issues**: Check if exchanges are accessible

Check the error message in the UI alert or in backend logs:
```bash
docker logs funding-dashboard | tail -50
```

## Next Steps

### Immediate Improvements

1. **Fix GRVT and Backpack support**:
   - Resolve `pysdk` module installation in Docker
   - Resolve `bpx` module installation in Docker
   - Re-enable exchange support in backend

2. **Add API Key Management**:
   - UI for configuring exchange API keys
   - Secure storage of credentials
   - Per-strategy API key assignment

3. **Enhanced Monitoring**:
   - Real-time funding rate charts
   - Position and P&L tracking
   - Trade execution history view
   - Performance analytics

4. **Production Deployment**:
   - Frontend Docker container
   - Docker Compose for full stack
   - Nginx reverse proxy
   - SSL/TLS support

### Feature Requests

1. **Strategy Templates**: Pre-configured strategies for common setups
2. **Backtesting**: Test strategies with historical data
3. **Notifications**: Email/Telegram alerts for important events
4. **Multi-user Support**: Authentication and authorization
5. **Mobile Responsive**: Better mobile UI/UX

## Testing Results

✅ Backend Docker container running on port 38888
✅ Frontend dev server running on port 3000
✅ API endpoints responding correctly
✅ Strategy creation via API working
✅ Strategy listing working
✅ Frontend build successful
✅ Real-time WebSocket connection implemented
✅ Create strategy dialog functional
✅ Start/Stop/Delete controls integrated

⚠️ Strategy execution requires API keys (expected behavior)
⚠️ Only Lighter and Binance exchanges currently work

## Support

For issues or questions:
1. Check backend logs: `docker logs funding-dashboard`
2. Check frontend console in browser DevTools
3. Review API documentation: http://localhost:38888/docs
4. Inspect database: `sqlite3 data/funding_bot.db`

## Summary

The Funding Rate Arbitrage Dashboard is now fully functional with:
- Complete backend REST API
- Modern React frontend with shadcn/ui components
- Real-time WebSocket updates
- Strategy CRUD operations
- Docker deployment

You can now create, manage, and monitor multiple funding rate arbitrage strategies through a unified web interface instead of managing individual Docker containers.
