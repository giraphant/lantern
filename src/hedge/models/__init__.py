"""
Data models for hedge trading bot.
"""

from decimal import Decimal
from dataclasses import dataclass
from typing import Optional, Literal
from enum import Enum


class TradingState(Enum):
    """Trading state machine states."""
    IDLE = "idle"
    BUILDING = "building"
    HOLDING = "holding"
    WINDING_DOWN = "winding_down"
    EMERGENCY_STOP = "emergency_stop"


class OrderStatus(Enum):
    """Order status."""
    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELED = "canceled"
    FAILED = "failed"


@dataclass
class Position:
    """Position information."""
    grvt: Decimal
    lighter: Decimal

    @property
    def imbalance(self) -> Decimal:
        """Calculate position imbalance (should be near 0 for hedged positions)."""
        return self.grvt + self.lighter

    @property
    def total_exposure(self) -> Decimal:
        """Total absolute exposure."""
        return abs(self.grvt) + abs(self.lighter)

    def is_balanced(self, tolerance: Decimal) -> bool:
        """Check if positions are balanced within tolerance."""
        return abs(self.imbalance) <= tolerance


@dataclass
class OrderRequest:
    """Order request parameters."""
    exchange: Literal["grvt", "lighter"]
    side: Literal["buy", "sell"]
    quantity: Decimal
    price: Optional[Decimal] = None  # None for market orders
    order_type: Literal["market", "limit", "post_only"] = "post_only"

    def validate(self, max_order_size: Decimal) -> bool:
        """Validate order parameters."""
        if self.quantity <= 0:
            raise ValueError(f"Invalid quantity: {self.quantity}")
        if self.quantity > max_order_size:
            raise ValueError(f"Quantity {self.quantity} exceeds max {max_order_size}")
        return True


@dataclass
class OrderResult:
    """Order execution result."""
    success: bool
    order_id: Optional[str] = None
    filled_quantity: Decimal = Decimal('0')
    filled_price: Optional[Decimal] = None
    status: Optional[OrderStatus] = None
    error_message: Optional[str] = None


@dataclass
class SafetyCheckResult:
    """Result of safety checks."""
    passed: bool
    errors: list[str]
    warnings: list[str]

    @property
    def has_critical_errors(self) -> bool:
        """Check if there are critical errors requiring immediate stop."""
        return not self.passed and len(self.errors) > 0

    def __str__(self) -> str:
        if self.passed:
            return "✅ All safety checks passed"
        else:
            msg = "❌ Safety checks failed:\n"
            for error in self.errors:
                msg += f"  ERROR: {error}\n"
            for warning in self.warnings:
                msg += f"  WARNING: {warning}\n"
            return msg


@dataclass
class TradingConfig:
    """Trading configuration."""
    # API Keys
    grvt_api_key: str
    grvt_private_key: str
    lighter_api_key: str
    lighter_private_key: str
    lighter_api_host: str = "https://chain.lighter.xyz/api"

    # Basic parameters
    symbol: str = "BTC"  # Trading symbol
    ticker: Optional[str] = None  # Deprecated, use symbol
    order_quantity: Decimal = Decimal("0.3")

    # Safety limits
    max_position: Decimal = Decimal("10.0")
    max_position_diff: Decimal = Decimal("0.5")  # Rebalance tolerance
    rebalance_tolerance: Decimal = Decimal("0.5")  # Same as max_position_diff
    emergency_stop_loss: Decimal = Decimal("5.0")
    max_open_orders: int = 1

    # Cycle parameters
    target_cycles: int = 5
    build_iterations: Optional[int] = None  # Deprecated
    hold_time: int = 180  # seconds
    cycles: Optional[int] = None  # Deprecated, use target_cycles
    direction: Literal["long", "short", "random"] = "long"
    cycle_interval: int = 60  # seconds between cycles

    # Order parameters
    order_timeout: int = 30
    max_retries: int = 3
    spread_bps: int = 10  # Basis points for post-only orders

    # Control flags
    block_orders: bool = False
    block_order_recreation: bool = False