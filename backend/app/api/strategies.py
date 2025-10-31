"""
Strategy management API endpoints.
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models import Strategy as StrategyModel
from app.schemas import Strategy, StrategyCreate, StrategyUpdate

router = APIRouter()


@router.get("/", response_model=list[Strategy])
async def list_strategies(db: AsyncSession = Depends(get_db)):
    """Get all strategies."""
    result = await db.execute(select(StrategyModel))
    strategies = result.scalars().all()
    return strategies


@router.post("/", response_model=Strategy, status_code=201)
async def create_strategy(
    strategy_data: StrategyCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new strategy."""
    # Generate unique ID
    strategy_id = str(uuid.uuid4())

    # Create strategy model
    strategy = StrategyModel(
        id=strategy_id,
        name=strategy_data.name,
        exchange_a=strategy_data.exchange_a,
        exchange_b=strategy_data.exchange_b,
        symbol=strategy_data.symbol,
        size=strategy_data.size,
        max_position=strategy_data.max_position,
        build_threshold_apr=strategy_data.build_threshold_apr,
        close_threshold_apr=strategy_data.close_threshold_apr,
        check_interval=strategy_data.check_interval,
        status="stopped"  # New strategies start stopped
    )

    db.add(strategy)
    await db.commit()
    await db.refresh(strategy)

    return strategy


@router.get("/{strategy_id}", response_model=Strategy)
async def get_strategy(strategy_id: str, db: AsyncSession = Depends(get_db)):
    """Get a specific strategy by ID."""
    result = await db.execute(
        select(StrategyModel).where(StrategyModel.id == strategy_id)
    )
    strategy = result.scalar_one_or_none()

    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    return strategy


@router.put("/{strategy_id}", response_model=Strategy)
async def update_strategy(
    strategy_id: str,
    strategy_data: StrategyUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a strategy."""
    result = await db.execute(
        select(StrategyModel).where(StrategyModel.id == strategy_id)
    )
    strategy = result.scalar_one_or_none()

    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    # Update fields
    update_data = strategy_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(strategy, field, value)

    await db.commit()
    await db.refresh(strategy)

    return strategy


@router.delete("/{strategy_id}", status_code=204)
async def delete_strategy(strategy_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a strategy."""
    result = await db.execute(
        select(StrategyModel).where(StrategyModel.id == strategy_id)
    )
    strategy = result.scalar_one_or_none()

    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    await db.delete(strategy)
    await db.commit()

    return None


@router.post("/{strategy_id}/start", response_model=Strategy)
async def start_strategy(strategy_id: str, db: AsyncSession = Depends(get_db)):
    """Start a strategy."""
    from app.services.strategy_manager import strategy_manager

    result = await db.execute(
        select(StrategyModel).where(StrategyModel.id == strategy_id)
    )
    strategy = result.scalar_one_or_none()

    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    # Start strategy execution
    try:
        config = {
            'exchange_a': strategy.exchange_a,
            'exchange_b': strategy.exchange_b,
            'symbol': strategy.symbol,
            'size': float(strategy.size),
            'max_position': float(strategy.max_position),
            'build_threshold_apr': float(strategy.build_threshold_apr),
            'close_threshold_apr': float(strategy.close_threshold_apr),
            'check_interval': strategy.check_interval,
        }

        await strategy_manager.start_strategy(strategy_id, config)

        strategy.status = "running"
        await db.commit()
        await db.refresh(strategy)

    except Exception as e:
        strategy.status = "error"
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Failed to start strategy: {str(e)}")

    return strategy


@router.post("/{strategy_id}/stop", response_model=Strategy)
async def stop_strategy(strategy_id: str, db: AsyncSession = Depends(get_db)):
    """Stop a strategy."""
    from app.services.strategy_manager import strategy_manager

    result = await db.execute(
        select(StrategyModel).where(StrategyModel.id == strategy_id)
    )
    strategy = result.scalar_one_or_none()

    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    # Stop strategy execution
    try:
        await strategy_manager.stop_strategy(strategy_id)

        strategy.status = "stopped"
        await db.commit()
        await db.refresh(strategy)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop strategy: {str(e)}")

    return strategy
