#!/usr/bin/env python3
"""
Hedge Trading Bot V3 - Main Entry Point

This is the main entry point for running the hedge trading bot.
Uses the V3 architecture with clean separation of concerns.
"""

import sys
import os

# Add src to path so we can import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Now run the hedge bot V3
from hedge_bot_v3 import main

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())