"""
Hedge Bot V2 - Refactored with modular architecture.

This is the new entry point that uses the modular architecture
with proper safety checks and state management.
"""

import asyncio
import logging
import os
import sys
from decimal import Decimal
from pathlib import Path

import dotenv

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hedge.models import TradingConfig
from hedge.managers import SafetyManager, PositionManager, OrderManager
from hedge.core.trading_state_machine_v2 import TradingStateMachineV2
from exchanges.grvt import GrvtClient
from lighter.signer_client import SignerClient


class Config:
    """Simple config class for GRVT client compatibility."""
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class HedgeBotV2:
    """
    Main hedge bot class - V2 with modular architecture.
    """

    def __init__(self, config: TradingConfig):
        self.config = config
        self.logger = self._setup_logger()

        # Exchange clients
        self.grvt_client = None
        self.lighter_client = None

        # Managers
        self.safety_manager = None
        self.position_manager = None
        self.order_manager = None

        # State machine
        self.state_machine = None

    def _setup_logger(self) -> logging.Logger:
        """Setup logging configuration."""
        logger = logging.getLogger(f"hedge_bot_v2_{self.config.ticker}")
        logger.setLevel(logging.INFO)

        # Clear existing handlers
        logger.handlers.clear()

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)

        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)

        logger.addHandler(console_handler)
        logger.propagate = False

        return logger

    async def initialize(self):
        """Initialize all components."""
        self.logger.info("🚀 Initializing Hedge Bot V2...")

        # Initialize GRVT client
        self.logger.info("Initializing GRVT client...")
        grvt_config = Config(
            ticker=self.config.ticker,
            quantity=self.config.order_quantity,
            contract_id="",  # Will be set by GRVT client
            tick_size=Decimal('0'),  # Will be set by GRVT client
        )
        self.grvt_client = GrvtClient(grvt_config)
        await self.grvt_client.connect()

        # Get contract details
        contract_id, tick_size = await self.grvt_client.get_contract_attributes()
        self.logger.info(f"GRVT Contract: {contract_id}, Tick: {tick_size}")

        # Initialize Lighter client
        self.logger.info("Initializing Lighter client...")
        lighter_blockchain_id = "lighter_chain_42161"
        lighter_market_id = self._get_lighter_market_id(self.config.ticker)

        self.lighter_client = SignerClient.from_env(
            blockchain_id=lighter_blockchain_id,
            market_id=lighter_market_id
        )
        await self.lighter_client.connect()

        # Initialize managers
        self.logger.info("Initializing managers...")

        self.safety_manager = SafetyManager(
            config=self.config,
            logger=self.logger
        )

        self.position_manager = PositionManager(
            grvt_client=self.grvt_client,
            lighter_market_index=lighter_market_id,
            logger=self.logger
        )

        self.order_manager = OrderManager(
            grvt_client=self.grvt_client,
            lighter_client=self.lighter_client,
            config=self.config,
            logger=self.logger
        )

        # Initialize state machine V2 (position-based)
        self.logger.info("Initializing state machine V2 (position-based)...")
        self.state_machine = TradingStateMachineV2(
            safety_manager=self.safety_manager,
            position_manager=self.position_manager,
            order_manager=self.order_manager,
            config=self.config,
            logger=self.logger
        )

        self.logger.info("✅ Initialization complete")

    def _get_lighter_market_id(self, ticker: str) -> int:
        """Get Lighter market ID for ticker."""
        market_map = {
            "BTC": 3,
            "ETH": 1,
            "HYPE": 103,
            # Add more mappings as needed
        }
        market_id = market_map.get(ticker.upper())
        if not market_id:
            raise ValueError(f"Unknown Lighter market for ticker: {ticker}")
        return market_id

    async def run(self):
        """Run the hedge bot."""
        try:
            await self.initialize()

            # Log configuration
            self._log_configuration()

            # Run state machine
            await self.state_machine.run()

        except KeyboardInterrupt:
            self.logger.info("Interrupted by user")
            if self.state_machine:
                self.state_machine.request_stop()
        except Exception as e:
            self.logger.error(f"Fatal error: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
        finally:
            await self.cleanup()

    async def cleanup(self):
        """Clean up resources."""
        self.logger.info("Cleaning up...")

        if self.grvt_client:
            try:
                await self.grvt_client.disconnect()
            except:
                pass

        if self.lighter_client:
            try:
                await self.lighter_client.close()
            except:
                pass

        self.logger.info("✅ Cleanup complete")

    def _log_configuration(self):
        """Log current configuration."""
        self.logger.info("=" * 60)
        self.logger.info("📋 CONFIGURATION")
        self.logger.info("=" * 60)
        self.logger.info(f"Ticker: {self.config.ticker}")
        self.logger.info(f"Order Size: {self.config.order_quantity}")
        self.logger.info(f"Max Position: {self.config.max_position}")
        self.logger.info(f"Max Position Diff: {self.config.max_position_diff}")
        self.logger.info(f"Cycles: {self.config.cycles}")
        self.logger.info(f"Build Iterations: {self.config.build_iterations}")
        self.logger.info(f"Hold Time: {self.config.hold_time}s")
        self.logger.info(f"Direction: {self.config.direction}")
        self.logger.info("=" * 60)


async def main():
    """Main entry point."""
    # Load environment variables
    env_path = Path(".env")
    if env_path.exists():
        dotenv.load_dotenv()
        print(f"✓ Loaded environment from .env")

    # Create configuration from environment
    config = TradingConfig(
        ticker=os.getenv("TICKER", "BTC"),
        order_quantity=Decimal(os.getenv("SIZE", "0.1")),
        max_position=Decimal(os.getenv("MAX_POSITION", "10")),
        max_position_diff=Decimal(os.getenv("REBALANCE_TOLERANCE", "0.15")),
        max_open_orders=int(os.getenv("MAX_OPEN_ORDERS", "1")),
        build_iterations=int(os.getenv("BUILD_UP_ITERATIONS", "30")),
        hold_time=int(os.getenv("HOLD_TIME", "180")),
        cycles=int(os.getenv("CYCLES", "1")),
        direction=os.getenv("DIRECTION", "long"),
        order_timeout=int(os.getenv("ORDER_TIMEOUT", "30")),
        max_retries=int(os.getenv("MAX_RETRIES", "3"))
    )

    # Create and run bot
    bot = HedgeBotV2(config)
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())