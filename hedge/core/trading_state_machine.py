"""
Trading State Machine - Core trading logic with proper state management.

This is the main orchestrator that coordinates all managers and
implements the trading strategy.
"""

import asyncio
import logging
import time
import random
from decimal import Decimal
from typing import Optional, Literal

from hedge.models import TradingState, TradingConfig, Position
from hedge.managers.safety_manager import SafetyManager
from hedge.managers.position_manager import PositionManager
from hedge.managers.order_manager import OrderManager


class TradingStateMachine:
    """
    Core trading state machine implementing the hedge strategy.

    Lifecycle: IDLE -> BUILDING -> HOLDING -> WINDING_DOWN -> IDLE

    Emergency stop can be triggered from any state.
    """

    def __init__(
        self,
        safety_manager: SafetyManager,
        position_manager: PositionManager,
        order_manager: OrderManager,
        config: TradingConfig,
        logger: Optional[logging.Logger] = None
    ):
        self.safety = safety_manager
        self.positions = position_manager
        self.orders = order_manager
        self.config = config
        self.logger = logger or logging.getLogger(__name__)

        # State
        self.state = TradingState.IDLE
        self.current_cycle = 0
        self.stop_requested = False

        # Direction for current cycle
        self.current_direction: Literal["long", "short"] = config.direction

    async def run(self):
        """
        Main entry point - run trading cycles.
        """
        self.logger.info("=" * 60)
        self.logger.info("🚀 Starting Trading State Machine")
        self.logger.info(f"   Cycles: {self.config.cycles}")
        self.logger.info(f"   Build iterations: {self.config.build_iterations}")
        self.logger.info(f"   Hold time: {self.config.hold_time}s")
        self.logger.info(f"   Direction: {self.config.direction}")
        self.logger.info("=" * 60)

        try:
            # Initial safety check
            position = await self.positions.get_positions(force_refresh=True)
            safety_result = await self.safety.run_pre_trade_checks(position)

            if not safety_result.passed:
                self.logger.error("Initial safety check failed. Aborting.")
                self.logger.error(str(safety_result))
                return

            # Run cycles
            for cycle in range(self.config.cycles):
                if self.stop_requested:
                    break

                self.current_cycle = cycle + 1
                await self._run_single_cycle()

        except Exception as e:
            self.logger.error(f"Fatal error in state machine: {e}")
            await self._emergency_stop()
        finally:
            await self._cleanup()

    async def _run_single_cycle(self):
        """Run a single trading cycle: BUILD -> HOLD -> WINDDOWN."""
        self.logger.info("=" * 60)
        self.logger.info(f"📈 CYCLE {self.current_cycle}/{self.config.cycles} STARTING")
        self.logger.info("=" * 60)

        # Determine direction for this cycle
        if self.config.direction == "random":
            self.current_direction = random.choice(["long", "short"])
            self.logger.info(f"🎲 Random direction selected: {self.current_direction}")
        else:
            self.current_direction = self.config.direction

        # Phase 1: BUILD
        await self._build_phase()

        if self.stop_requested:
            return

        # Phase 2: HOLD
        await self._hold_phase()

        if self.stop_requested:
            return

        # Phase 3: WINDDOWN
        await self._winddown_phase()

        self.logger.info("=" * 60)
        self.logger.info(f"✅ CYCLE {self.current_cycle} COMPLETED")
        self.logger.info("=" * 60)

    async def _build_phase(self):
        """Build up hedged position."""
        self.state = TradingState.BUILDING
        self.logger.info("=" * 60)
        self.logger.info(f"🔨 BUILD PHASE - {self.config.build_iterations} iterations")
        self.logger.info(f"   Direction: {self.current_direction}")
        self.logger.info("=" * 60)

        # Determine order sides based on direction
        if self.current_direction == "long":
            # Lighter long (buy) + GRVT short (sell) hedge
            grvt_side = "sell"
            lighter_side = "buy"
        else:
            # Lighter short (sell) + GRVT long (buy) hedge
            grvt_side = "buy"
            lighter_side = "sell"

        for iteration in range(1, self.config.build_iterations + 1):
            if self.stop_requested:
                break

            self.logger.info("-" * 50)
            self.logger.info(f"📊 Build iteration {iteration}/{self.config.build_iterations}")

            # Pre-trade safety check
            position = await self.positions.get_positions()
            self.logger.info(f"   Position: GRVT={position.grvt} | Lighter={position.lighter}")

            # Check for excessive orders
            has_excessive, order_count = await self.orders.check_excessive_orders()
            if has_excessive:
                self.logger.warning(f"Canceling {order_count} excessive orders")
                await self.orders.cancel_all_orders()

            safety_result = await self.safety.run_pre_trade_checks(
                position,
                open_orders_count=order_count,
                proposed_order_size=self.config.order_quantity
            )

            if not safety_result.passed:
                self.logger.error("Safety check failed during build phase")
                self.logger.error(str(safety_result))
                await self._emergency_stop()
                return

            # Place hedge order
            grvt_result, lighter_result = await self.orders.place_hedge_order(
                grvt_side=grvt_side,
                quantity=self.config.order_quantity,
                execute_hedge=True
            )

            if not grvt_result.success:
                self.logger.error(f"Build order failed: {grvt_result.error_message}")
                # Continue to next iteration
                continue

            # Brief delay between iterations
            if iteration < self.config.build_iterations:
                await asyncio.sleep(1.0)

        # Final position after build
        position = await self.positions.get_positions(force_refresh=True)
        self.logger.info("=" * 60)
        self.logger.info(f"✅ Build phase complete")
        self.logger.info(f"   Final: GRVT={position.grvt} | Lighter={position.lighter}")
        self.logger.info("=" * 60)

    async def _hold_phase(self):
        """Hold position for configured time."""
        if self.config.hold_time <= 0:
            return

        self.state = TradingState.HOLDING
        position = await self.positions.get_positions(force_refresh=True)

        self.logger.info("=" * 60)
        self.logger.info(f"⏳ HOLD PHASE - {self.config.hold_time}s")
        self.logger.info(f"   Position: GRVT={position.grvt} | Lighter={position.lighter}")
        self.logger.info("=" * 60)

        hold_start = time.time()
        last_log_time = hold_start

        while time.time() - hold_start < self.config.hold_time:
            if self.stop_requested:
                break

            # Log progress every minute
            if time.time() - last_log_time >= 60:
                elapsed = int(time.time() - hold_start)
                remaining = self.config.hold_time - elapsed
                self.logger.info(
                    f"⏱️  Holding... {elapsed}s elapsed, {remaining}s remaining"
                )
                last_log_time = time.time()

            await asyncio.sleep(10)

    async def _winddown_phase(self):
        """Wind down position to zero."""
        self.state = TradingState.WINDING_DOWN
        self.logger.info("=" * 60)
        self.logger.info("📉 WINDDOWN PHASE")
        self.logger.info("=" * 60)

        max_iterations = 200  # Safety limit
        iteration = 0

        while iteration < max_iterations and not self.stop_requested:
            iteration += 1

            # Get current position
            position = await self.positions.get_positions(force_refresh=True)

            # Check if we're done
            if abs(position.grvt) < 0.001:
                self.logger.info(f"✅ Position closed after {iteration} iterations")
                self.logger.info(f"   Final: GRVT={position.grvt} | Lighter={position.lighter}")
                break

            self.logger.info(f"📊 Winddown iteration {iteration}")
            self.logger.info(f"   Position: GRVT={position.grvt} | Lighter={position.lighter}")

            # Pre-trade safety check
            safety_result = await self.safety.run_pre_trade_checks(position)
            if not safety_result.passed:
                self.logger.error("Safety check failed during winddown")
                self.logger.error(str(safety_result))
                await self._emergency_stop()
                return

            # Determine close order parameters
            if position.grvt > 0:
                grvt_side = "sell"
                quantity = min(self.config.order_quantity, position.grvt)
            else:
                grvt_side = "buy"
                quantity = min(self.config.order_quantity, abs(position.grvt))

            # Place close order
            grvt_result, lighter_result = await self.orders.place_hedge_order(
                grvt_side=grvt_side,
                quantity=quantity,
                execute_hedge=True
            )

            if not grvt_result.success:
                self.logger.error(f"Winddown order failed: {grvt_result.error_message}")
                # Continue trying
                await asyncio.sleep(2.0)

        if iteration >= max_iterations:
            self.logger.error(f"❌ Winddown exceeded max iterations ({max_iterations})")
            await self._emergency_stop()

    async def _emergency_stop(self):
        """Emergency stop - cancel all orders and halt trading."""
        self.state = TradingState.EMERGENCY_STOP
        self.stop_requested = True

        self.logger.critical("=" * 60)
        self.logger.critical("🚨 EMERGENCY STOP TRIGGERED")
        self.logger.critical("=" * 60)

        try:
            # Cancel all open orders
            canceled = await self.orders.cancel_all_orders()
            self.logger.info(f"Canceled {canceled} open orders")

            # Get final positions
            position = await self.positions.get_positions(force_refresh=True)
            self.logger.critical(
                f"Final positions: GRVT={position.grvt} | "
                f"Lighter={position.lighter} | "
                f"Imbalance={position.imbalance:.4f}"
            )

            # Log safety status
            status = self.safety.get_status_summary(position)
            self.logger.critical(status)

        except Exception as e:
            self.logger.error(f"Error during emergency stop: {e}")

    async def _cleanup(self):
        """Cleanup on exit."""
        self.logger.info("Performing cleanup...")

        # Final position check
        try:
            position = await self.positions.get_positions(force_refresh=True)
            summary = await self.positions.get_position_summary()
            self.logger.info(summary)
        except:
            pass

        self.state = TradingState.IDLE
        self.logger.info("✅ Cleanup complete")

    def request_stop(self):
        """Request graceful stop."""
        self.logger.info("Stop requested - will halt after current operation")
        self.stop_requested = True