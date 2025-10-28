#!/usr/bin/env python3
"""
Hedge Mode Entry Point

This script serves as the main entry point for hedge mode trading.
It imports and runs the appropriate hedge mode implementation based on the exchange parameter.

Usage:
    python hedge_mode.py --exchange <exchange> [other arguments]

Supported exchanges:
    - backpack: Uses HedgeBot from hedge_mode_bp.py (Backpack + Lighter)
    - extended: Uses HedgeBot from hedge_mode_ext.py (Extended + Lighter)
    - apex: Uses HedgeBot from hedge_mode_apex.py (Apex + Lighter)
    - grvt: Uses HedgeBot from hedge_mode_grvt.py (GRVT + Lighter)

Cross-platform compatibility:
    - Works on Linux, macOS, and Windows
    - Direct imports instead of subprocess calls for better performance
"""

import asyncio
import sys
import argparse
import os
from decimal import Decimal
from pathlib import Path
import dotenv

def parse_arguments():
    """Parse command line arguments with environment variable fallbacks."""
    parser = argparse.ArgumentParser(
        description='Hedge Mode Trading Bot Entry Point',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python hedge_mode.py --exchange backpack --ticker BTC --size 0.002 --iter 10
    python hedge_mode.py --exchange extended --ticker ETH --size 0.1 --iter 5
    python hedge_mode.py --exchange apex --ticker BTC --size 0.002 --iter 10
    python hedge_mode.py --exchange grvt --ticker BTC --size 0.05 --iter 10

Environment Variables (can be used instead of command-line arguments):
    EXCHANGE - Exchange to use (backpack, extended, apex, or grvt)
    TICKER - Ticker symbol (default: BTC)
    SIZE - Number of tokens to buy/sell per order
    ITERATIONS - Number of iterations to run
    FILL_TIMEOUT - Timeout in seconds for maker order fills (default: 5)
    PRICE_TOLERANCE - Price tolerance in ticks (default: 3)
    MIN_ORDER_LIFETIME - Minimum order lifetime in seconds (default: 30)
    REBALANCE_THRESHOLD - Position imbalance threshold (default: 0.15)
    AUTO_REBALANCE - Enable auto-rebalance (default: true)
    BUILD_UP_ITERATIONS - Number of iterations to build up position
    HOLD_TIME - Time in seconds to hold position (default: 0)
    CYCLES - Number of build-hold-winddown cycles (default: 1)
    DIRECTION - Trading direction: long, short, or random (default: long)
        """
    )

    parser.add_argument('--exchange', type=str,
                        default=os.getenv('EXCHANGE'),
                        help='Exchange to use (backpack, extended, apex, or grvt)')
    parser.add_argument('--ticker', type=str,
                        default=os.getenv('TICKER', 'BTC'),
                        help='Ticker symbol (default: BTC)')
    parser.add_argument('--size', type=str,
                        default=os.getenv('SIZE'),
                        help='Number of tokens to buy/sell per order')
    parser.add_argument('--iter', type=int,
                        default=int(os.getenv('ITERATIONS')) if os.getenv('ITERATIONS') else None,
                        help='Number of iterations to run')
    parser.add_argument('--fill-timeout', type=int,
                        default=int(os.getenv('FILL_TIMEOUT', '5')),
                        help='Timeout in seconds for maker order fills (default: 5)')
    parser.add_argument('--price-tolerance', type=int,
                        default=int(os.getenv('PRICE_TOLERANCE', '3')),
                        help='Price tolerance in ticks before canceling order (default: 3)')
    parser.add_argument('--min-order-lifetime', type=int,
                        default=int(os.getenv('MIN_ORDER_LIFETIME', '30')),
                        help='Minimum order lifetime in seconds before considering cancellation (default: 30)')
    parser.add_argument('--rebalance-threshold', type=float,
                        default=float(os.getenv('REBALANCE_THRESHOLD', '0.15')),
                        help='Position imbalance threshold before triggering rebalance (default: 0.15)')
    parser.add_argument('--no-auto-rebalance', action='store_true',
                        default=os.getenv('AUTO_REBALANCE', 'true').lower() == 'false',
                        help='Disable automatic position rebalancing (default: enabled)')
    parser.add_argument('--build-up-iterations', type=int,
                        default=int(os.getenv('BUILD_UP_ITERATIONS')) if os.getenv('BUILD_UP_ITERATIONS') else None,
                        help='Number of iterations to build up position before holding (default: same as --iter)')
    parser.add_argument('--hold-time', type=int,
                        default=int(os.getenv('HOLD_TIME', '0')),
                        help='Time in seconds to hold position (default: 0, e.g., 1800 for 30 min)')
    parser.add_argument('--cycles', type=int,
                        default=int(os.getenv('CYCLES')) if os.getenv('CYCLES') else None,
                        help='Number of build-hold-winddown cycles to run (default: 1)')
    parser.add_argument('--direction', type=str,
                        default=os.getenv('DIRECTION', 'long'),
                        help='Lighter direction: long (Lighter buy), short (Lighter sell), or random (default: long)')
    parser.add_argument('--env-file', type=str, default=".env",
                        help=".env file path (default: .env)")

    args = parser.parse_args()

    # Validate required arguments
    if not args.exchange:
        parser.error("--exchange is required (or set EXCHANGE environment variable)")
    if not args.size:
        parser.error("--size is required (or set SIZE environment variable)")
    if args.iter is None:
        parser.error("--iter is required (or set ITERATIONS environment variable)")

    return args


def validate_exchange(exchange):
    """Validate that the exchange is supported."""
    supported_exchanges = ['backpack', 'extended', 'apex', 'grvt']
    if exchange.lower() not in supported_exchanges:
        print(f"Error: Unsupported exchange '{exchange}'")
        print(f"Supported exchanges: {', '.join(supported_exchanges)}")
        sys.exit(1)


def get_hedge_bot_class(exchange):
    """Import and return the appropriate HedgeBot class."""
    try:
        if exchange.lower() == 'backpack':
            from hedge.hedge_mode_bp import HedgeBot
            return HedgeBot
        elif exchange.lower() == 'extended':
            from hedge.hedge_mode_ext import HedgeBot
            return HedgeBot
        elif exchange.lower() == 'apex':
            from hedge.hedge_mode_apex import HedgeBot
            return HedgeBot
        elif exchange.lower() == 'grvt':
            from hedge.hedge_mode_grvt import HedgeBot
            return HedgeBot
        else:
            raise ValueError(f"Unsupported exchange: {exchange}")
    except ImportError as e:
        print(f"Error importing hedge mode implementation: {e}")
        sys.exit(1)


async def main():
    """Main entry point that creates and runs the appropriate hedge bot."""
    args = parse_arguments()

    # Load .env file if it exists (optional in containerized environments)
    env_path = Path(args.env_file)
    if env_path.exists():
        dotenv.load_dotenv(args.env_file)
        print(f"✓ Loaded environment from {args.env_file}")
    else:
        print(f"ℹ No .env file found at {args.env_file}, using system environment variables")

    # Debug: Print all trading parameter environment variables
    print("\n" + "="*60)
    print("🔍 Environment Variables (Trading Parameters):")
    print("="*60)
    trading_env_vars = [
        'EXCHANGE', 'TICKER', 'SIZE', 'ITERATIONS',
        'BUILD_UP_ITERATIONS', 'HOLD_TIME', 'CYCLES', 'DIRECTION',
        'PRICE_TOLERANCE', 'MIN_ORDER_LIFETIME', 'REBALANCE_THRESHOLD',
        'AUTO_REBALANCE', 'FILL_TIMEOUT'
    ]
    for var in trading_env_vars:
        value = os.getenv(var)
        if value:
            print(f"  {var} = {value}")
        else:
            print(f"  {var} = (not set)")
    print("="*60 + "\n")
    
    # Validate exchange
    validate_exchange(args.exchange)
    
    # Get the appropriate HedgeBot class
    try:
        HedgeBotClass = get_hedge_bot_class(args.exchange)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    print(f"Starting hedge mode for {args.exchange} exchange...")
    print(f"Ticker: {args.ticker}, Size: {args.size}, Iterations: {args.iter}")
    print("-" * 50)
    
    try:
        # Create the hedge bot instance
        bot = HedgeBotClass(
            ticker=args.ticker.upper(),
            order_quantity=Decimal(args.size),
            fill_timeout=args.fill_timeout,
            iterations=args.iter,
            price_tolerance_ticks=args.price_tolerance,
            min_order_lifetime=args.min_order_lifetime,
            rebalance_threshold=Decimal(str(args.rebalance_threshold)),
            auto_rebalance=not args.no_auto_rebalance,
            build_up_iterations=args.build_up_iterations,
            hold_time=args.hold_time,
            cycles=args.cycles,
            direction=args.direction
        )

        # Run the bot
        await bot.run()
        
    except KeyboardInterrupt:
        print("\nHedge mode interrupted by user")
        return 1
    except Exception as e:
        print(f"Error running hedge mode: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))