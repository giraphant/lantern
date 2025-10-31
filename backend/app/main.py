"""
FastAPI main application.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.api import strategies, funding_rates, positions, trades, websocket


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    await init_db()

    # Initialize data recorder
    from app.database import async_session_maker
    from app.services.data_recorder import DataRecorder
    from app.services.strategy_manager import strategy_manager

    data_recorder = DataRecorder(async_session_maker)

    # Set up callbacks for all strategies
    def setup_strategy_callbacks(executor):
        executor.on_funding_rate_update = data_recorder.record_funding_rate
        executor.on_position_update = data_recorder.record_position

    # Hook into strategy creation
    original_start = strategy_manager.start_strategy

    async def start_with_callbacks(strategy_id, config):
        await original_start(strategy_id, config)
        executor = strategy_manager.strategies.get(strategy_id)
        if executor:
            setup_strategy_callbacks(executor)

    strategy_manager.start_strategy = start_with_callbacks

    yield

    # Shutdown - stop all strategies
    for strategy_id in list(strategy_manager.strategies.keys()):
        await strategy_manager.stop_strategy(strategy_id)


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="Dashboard for managing funding rate arbitrage strategies",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(strategies.router, prefix="/api/strategies", tags=["strategies"])
app.include_router(funding_rates.router, prefix="/api/funding-rates", tags=["funding-rates"])
app.include_router(positions.router, prefix="/api/positions", tags=["positions"])
app.include_router(trades.router, prefix="/api/trades", tags=["trades"])
app.include_router(websocket.router, prefix="/ws", tags=["websocket"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "app": settings.app_name,
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}
