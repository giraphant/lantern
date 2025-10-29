"""
Safety Manager - Centralized safety checks for hedge trading.

This module is responsible for all pre-trade and runtime safety checks.
Every trading operation MUST pass safety checks before execution.
"""

import logging
from decimal import Decimal
from enum import Enum, IntEnum
from typing import Optional, List

from hedge.models import Position, SafetyCheckResult, TradingConfig


class SafetyLevel(IntEnum):
    """
    Safety levels for graduated response.
    Higher values indicate more severe conditions.
    """
    NORMAL = 0          # Normal operation
    WARNING = 1         # Warning but continue
    AUTO_REBALANCE = 2  # Trigger automatic rebalancing
    PAUSE = 3           # Pause new operations
    EMERGENCY = 4       # Emergency stop all operations


class SafetyManager:
    """
    Centralized safety management system.

    Responsibilities:
    - Pre-trade safety checks
    - Position limit validation
    - Order size validation
    - Emergency stop triggers
    """

    def __init__(self, config: TradingConfig, logger: Optional[logging.Logger] = None):
        self.config = config
        self.logger = logger or logging.getLogger(__name__)

        # Safety thresholds
        self.max_position = config.max_position
        self.max_position_diff = config.max_position_diff
        self.max_order_size = config.order_quantity
        self.max_open_orders = config.max_open_orders

        # Critical thresholds (triggers emergency stop)
        self.critical_position_diff = config.order_quantity * 10  # 10x order size
        self.critical_position_size = self.max_position * 2  # 2x max position

    async def run_pre_trade_checks(
        self,
        position: Position,
        open_orders_count: int = 0,
        proposed_order_size: Optional[Decimal] = None
    ) -> SafetyCheckResult:
        """
        Run all pre-trade safety checks.

        This method MUST be called before any trading operation.

        Args:
            position: Current positions on both exchanges
            open_orders_count: Number of currently open orders
            proposed_order_size: Size of the proposed order (if applicable)

        Returns:
            SafetyCheckResult with pass/fail status and detailed errors/warnings
        """
        errors = []
        warnings = []

        # Check 1: Critical position imbalance (immediate stop)
        if abs(position.imbalance) > self.critical_position_diff:
            errors.append(
                f"CRITICAL: Position imbalance {position.imbalance:.4f} exceeds "
                f"critical threshold {self.critical_position_diff:.4f}"
            )
            self.logger.critical(
                f"🚨 CRITICAL POSITION IMBALANCE: {position.imbalance:.4f} | "
                f"GRVT: {position.grvt} | Lighter: {position.lighter}"
            )

        # Check 2: Position imbalance exceeds tolerance
        # This should stop new orders but not trigger emergency stop
        elif abs(position.imbalance) > self.max_position_diff:
            errors.append(
                f"Position imbalance {position.imbalance:.4f} exceeds "
                f"tolerance {self.max_position_diff:.4f} - stopping new orders"
            )

        # Check 3: Individual position size limits
        if abs(position.grvt) > self.critical_position_size:
            errors.append(
                f"GRVT position {position.grvt} exceeds critical size {self.critical_position_size}"
            )
        elif abs(position.grvt) > self.max_position:
            warnings.append(
                f"GRVT position {position.grvt} exceeds max position {self.max_position}"
            )

        if abs(position.lighter) > self.critical_position_size:
            errors.append(
                f"Lighter position {position.lighter} exceeds critical size {self.critical_position_size}"
            )
        elif abs(position.lighter) > self.max_position:
            warnings.append(
                f"Lighter position {position.lighter} exceeds max position {self.max_position}"
            )

        # Check 4: Open orders count
        if open_orders_count > self.max_open_orders * 2:
            errors.append(
                f"Excessive open orders: {open_orders_count} (max: {self.max_open_orders})"
            )
        elif open_orders_count > self.max_open_orders:
            warnings.append(
                f"Open orders {open_orders_count} exceeds recommended {self.max_open_orders}"
            )

        # Check 5: Proposed order size (if provided)
        if proposed_order_size:
            if proposed_order_size > self.max_order_size:
                errors.append(
                    f"Proposed order size {proposed_order_size} exceeds "
                    f"max order size {self.max_order_size}"
                )
            elif proposed_order_size <= 0:
                errors.append(f"Invalid order size: {proposed_order_size}")

        # Create result
        passed = len(errors) == 0
        result = SafetyCheckResult(
            passed=passed,
            errors=errors,
            warnings=warnings
        )

        # Log result
        self._log_safety_check(result, position)

        return result

    def _log_safety_check(self, result: SafetyCheckResult, position: Position):
        """Log safety check results."""
        if result.passed:
            self.logger.debug(
                f"✅ Safety check passed | Imbalance: {position.imbalance:.4f} | "
                f"GRVT: {position.grvt} | Lighter: {position.lighter}"
            )
        else:
            self.logger.error(f"❌ Safety check failed:\n{result}")

    def calculate_safe_order_size(
        self,
        position: Position,
        side: str,
        exchange: str
    ) -> Decimal:
        """
        Calculate the maximum safe order size given current positions.

        This ensures we don't exceed position limits after the order.

        Args:
            position: Current positions
            side: "buy" or "sell"
            exchange: "grvt" or "lighter"

        Returns:
            Maximum safe order size (may be 0 if no safe size exists)
        """
        if exchange == "grvt":
            current_pos = position.grvt
        else:
            current_pos = position.lighter

        # Calculate position after order
        if side == "buy":
            position_delta = self.max_order_size
        else:
            position_delta = -self.max_order_size

        projected_position = current_pos + position_delta

        # Check if projected position exceeds limits
        if abs(projected_position) > self.max_position:
            # Calculate reduced size to stay within limits
            available_room = self.max_position - abs(current_pos)
            safe_size = max(Decimal('0'), min(available_room, self.max_order_size))
        else:
            safe_size = self.max_order_size

        return safe_size

    def check_positions(self, grvt_position: float, lighter_position: float) -> SafetyLevel:
        """
        Check current positions and return appropriate safety level.

        Args:
            grvt_position: GRVT position
            lighter_position: Lighter position

        Returns:
            SafetyLevel indicating the current safety status
        """
        # Calculate imbalance
        imbalance = abs(grvt_position + lighter_position)
        max_position = max(abs(grvt_position), abs(lighter_position))

        # Check for emergency conditions
        if imbalance > self.critical_position_diff:
            self.logger.critical(f"EMERGENCY: Critical imbalance {imbalance:.4f}")
            return SafetyLevel.EMERGENCY

        if max_position > self.critical_position_size:
            self.logger.critical(f"EMERGENCY: Critical position size {max_position:.4f}")
            return SafetyLevel.EMERGENCY

        # Check for pause conditions
        if imbalance > self.max_position_diff * 2:
            self.logger.warning(f"PAUSE: Large imbalance {imbalance:.4f}")
            return SafetyLevel.PAUSE

        if max_position > self.max_position * 1.5:
            self.logger.warning(f"PAUSE: Large position {max_position:.4f}")
            return SafetyLevel.PAUSE

        # Check for auto-rebalance conditions
        if imbalance > self.max_position_diff:
            self.logger.info(f"AUTO_REBALANCE: Imbalance {imbalance:.4f} exceeds tolerance")
            return SafetyLevel.AUTO_REBALANCE

        # Check for warning conditions
        if imbalance > self.max_position_diff * 0.8:
            self.logger.debug(f"WARNING: Imbalance {imbalance:.4f} approaching tolerance")
            return SafetyLevel.WARNING

        if max_position > self.max_position * 0.8:
            self.logger.debug(f"WARNING: Position {max_position:.4f} approaching limit")
            return SafetyLevel.WARNING

        # Normal operation
        return SafetyLevel.NORMAL

    async def should_emergency_stop(self, position: Position) -> bool:
        """
        Determine if emergency stop should be triggered.

        Args:
            position: Current positions

        Returns:
            True if emergency stop should be triggered
        """
        # Critical imbalance
        if abs(position.imbalance) > self.critical_position_diff:
            return True

        # Critical position size
        if abs(position.grvt) > self.critical_position_size:
            return True
        if abs(position.lighter) > self.critical_position_size:
            return True

        return False

    def get_status_summary(self, position: Position) -> str:
        """
        Get a formatted status summary for logging.

        Args:
            position: Current positions

        Returns:
            Formatted status string
        """
        status_lines = [
            "=" * 60,
            "🛡️  SAFETY STATUS",
            f"   GRVT Position: {position.grvt}",
            f"   Lighter Position: {position.lighter}",
            f"   Imbalance: {position.imbalance:.4f} (tolerance: {self.max_position_diff})",
            f"   Total Exposure: {position.total_exposure}",
        ]

        # Add status indicator
        if abs(position.imbalance) <= self.max_position_diff:
            status_lines.append("   Status: ✅ SAFE")
        elif abs(position.imbalance) <= self.critical_position_diff:
            status_lines.append("   Status: ⚠️ WARNING - Exceeds tolerance")
        else:
            status_lines.append("   Status: 🚨 CRITICAL - Emergency stop required")

        status_lines.append("=" * 60)

        return "\n".join(status_lines)