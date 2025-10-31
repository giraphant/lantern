# Funding Rate Arbitrage - Backend API

FastAPI backend for the funding rate arbitrage dashboard.

## Features

- REST API for strategy management
- WebSocket for real-time updates
- SQLite database for historical data
- Multi-exchange support (GRVT, Lighter, Binance, Backpack)

## Development

### Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Run locally

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs will be available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Run with Docker

```bash
docker build -t funding-bot-backend .
docker run -p 8000:8000 -v $(pwd)/data:/app/data funding-bot-backend
```

## API Endpoints

### Strategies

- `GET /api/strategies` - List all strategies
- `POST /api/strategies` - Create new strategy
- `GET /api/strategies/{id}` - Get strategy details
- `PUT /api/strategies/{id}` - Update strategy
- `DELETE /api/strategies/{id}` - Delete strategy
- `POST /api/strategies/{id}/start` - Start strategy
- `POST /api/strategies/{id}/stop` - Stop strategy

### Funding Rates

- `GET /api/funding-rates` - Get current funding rates
- `GET /api/funding-rates/{strategy_id}/history` - Get historical rates

### Positions

- `GET /api/positions` - Get current positions
- `GET /api/positions/{strategy_id}/history` - Get historical positions

### Trades

- `GET /api/trades` - Get all trades
- `GET /api/trades/{strategy_id}` - Get trades for a strategy

### WebSocket

- `WS /ws/updates` - Real-time updates stream

## Environment Variables

See `.env.example` for all available configuration options.

Key variables:
- `DATABASE_URL` - SQLite database path
- `GRVT_*` - GRVT exchange credentials
- `LIGHTER_*` - Lighter exchange credentials
- `BINANCE_*` - Binance exchange credentials
- `BACKPACK_*` - Backpack exchange credentials

## Database

SQLite database with the following tables:
- `strategies` - Strategy configurations
- `funding_rate_history` - Historical funding rates
- `position_history` - Historical positions
- `trades` - Trade execution records

Database is automatically initialized on first run.

## TODO

- [ ] Implement strategy execution engine
- [ ] Add real-time funding rate monitoring
- [ ] Implement position tracking
- [ ] Add trade execution logging
- [ ] Add authentication/authorization
- [ ] Add rate limiting
- [ ] Add comprehensive error handling
- [ ] Add logging
- [ ] Add tests
