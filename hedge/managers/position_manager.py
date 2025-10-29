"""
Position Manager - Centralized position management from exchange APIs.

This module provides the SINGLE source of truth for positions.
No local accumulation - always fetches from exchange APIs.
"""

import time
import logging
import asyncio
from decimal import Decimal
from typing import Optional, Tuple
import os
import aiohttp

from hedge.models import Position


class PositionCache:
    """Simple position cache with TTL."""

    def __init__(self, ttl_seconds: int = 5):
        self.ttl = ttl_seconds
        self._cache: Optional[Position] = None
        self._cache_time: float = 0

    def is_valid(self) -> bool:
        """Check if cache is still valid."""
        return (
            self._cache is not None and
            (time.time() - self._cache_time) < self.ttl
        )

    def get(self) -> Optional[Position]:
        """Get cached position if valid."""
        if self.is_valid():
            return self._cache
        return None

    def set(self, position: Position):
        """Update cache."""
        self._cache = position
        self._cache_time = time.time()

    def invalidate(self):
        """Invalidate cache."""
        self._cache = None
        self._cache_time = 0


class PositionManager:
    """
    Centralized position management.

    This is the ONLY place where positions should be queried.
    Never accumulate positions locally - always fetch from APIs.
    """

    def __init__(
        self,
        grvt_client,
        lighter_market_index: int,
        logger: Optional[logging.Logger] = None,
        cache_ttl: int = 5
    ):
        self.grvt_client = grvt_client
        self.lighter_market_index = lighter_market_index
        self.logger = logger or logging.getLogger(__name__)

        # Position cache to reduce API calls
        self._cache = PositionCache(ttl_seconds=cache_ttl)

        # Lighter API configuration
        self.lighter_account_index = os.getenv('LIGHTER_ACCOUNT_INDEX')
        if not self.lighter_account_index:
            raise ValueError("LIGHTER_ACCOUNT_INDEX must be set")

    async def get_positions(self, force_refresh: bool = False) -> Position:
        """
        Get current positions from both exchanges.

        This is the PRIMARY method for getting positions.
        Always returns real positions from exchange APIs (with caching).

        Args:
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
            Position object with current GRVT and Lighter positions
        """
        # Use cache if valid and not forcing refresh
        if not force_refresh:
            cached = self._cache.get()
            if cached:
                self.logger.debug(f"Using cached positions: {cached}")
                return cached

        # Fetch fresh positions
        try:
            # Fetch both positions in parallel
            grvt_task = self._fetch_grvt_position()
            lighter_task = self._fetch_lighter_position()

            grvt_pos, lighter_pos = await asyncio.gather(
                grvt_task, lighter_task,
                return_exceptions=True
            )

            # Handle exceptions
            if isinstance(grvt_pos, Exception):
                self.logger.error(f"Failed to fetch GRVT position: {grvt_pos}")
                grvt_pos = self._get_fallback_grvt_position()

            if isinstance(lighter_pos, Exception):
                self.logger.error(f"Failed to fetch Lighter position: {lighter_pos}")
                lighter_pos = self._get_fallback_lighter_position()

            # Create position object
            position = Position(grvt=grvt_pos, lighter=lighter_pos)

            # Update cache
            self._cache.set(position)

            # Log position update
            self.logger.info(
                f"📊 Positions fetched | GRVT: {grvt_pos} | "
                f"Lighter: {lighter_pos} | Imbalance: {position.imbalance:.4f}"
            )

            return position

        except Exception as e:
            self.logger.error(f"Critical error fetching positions: {e}")
            # Return last cached position if available
            cached = self._cache.get()
            if cached:
                self.logger.warning("Using stale cached positions due to error")
                return cached
            # Return zero positions as last resort
            return Position(grvt=Decimal('0'), lighter=Decimal('0'))

    async def _fetch_grvt_position(self) -> Decimal:
        """
        Fetch GRVT position from API.

        Returns:
            GRVT position with proper sign (positive=long, negative=short)
        """
        try:
            position = await asyncio.wait_for(
                self.grvt_client.get_account_positions(),
                timeout=10.0
            )
            return position
        except asyncio.TimeoutError:
            raise TimeoutError("GRVT position fetch timeout")
        except Exception as e:
            raise Exception(f"GRVT position fetch failed: {e}")

    async def _fetch_lighter_position(self) -> Decimal:
        """
        Fetch Lighter position from public REST API.

        Uses the public API that doesn't require private key.

        Returns:
            Lighter position with proper sign (positive=long, negative=short)
        """
        url = (
            f"https://mainnet.zklighter.elliot.ai/api/v1/account"
            f"?by=index&value={self.lighter_account_index}"
        )

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status != 200:
                        raise Exception(f"Lighter API returned status {response.status}")

                    data = await response.json()
                    accounts = data.get('accounts', [])

                    if not accounts:
                        raise Exception("No accounts found in Lighter API response")

                    account = accounts[0]
                    positions = account.get('positions', [])

                    # Find position for our market
                    for position in positions:
                        if position.get('market_id') == self.lighter_market_index:
                            pos_size = Decimal(str(position.get('position', 0)))
                            sign = position.get('sign', 1)
                            return pos_size * sign

                    # No position found for this market
                    return Decimal('0')

        except asyncio.TimeoutError:
            raise TimeoutError("Lighter position fetch timeout")
        except Exception as e:
            raise Exception(f"Lighter position fetch failed: {e}")

    def _get_fallback_grvt_position(self) -> Decimal:
        """Get fallback GRVT position from cache or zero."""
        cached = self._cache.get()
        if cached:
            return cached.grvt
        return Decimal('0')

    def _get_fallback_lighter_position(self) -> Decimal:
        """Get fallback Lighter position from cache or zero."""
        cached = self._cache.get()
        if cached:
            return cached.lighter
        return Decimal('0')

    def invalidate_cache(self):
        """Force cache invalidation (use after trades)."""
        self._cache.invalidate()

    async def wait_for_balance(
        self,
        tolerance: Decimal,
        max_wait_seconds: int = 30,
        check_interval: float = 1.0
    ) -> bool:
        """
        Wait for positions to become balanced.

        Useful after placing orders to wait for execution and settlement.

        Args:
            tolerance: Maximum acceptable position imbalance
            max_wait_seconds: Maximum time to wait
            check_interval: How often to check positions

        Returns:
            True if positions became balanced, False if timeout
        """
        start_time = time.time()

        while time.time() - start_time < max_wait_seconds:
            position = await self.get_positions(force_refresh=True)

            if position.is_balanced(tolerance):
                self.logger.info(f"✅ Positions balanced: {position}")
                return True

            self.logger.debug(
                f"Waiting for balance... Imbalance: {position.imbalance:.4f}"
            )

            await asyncio.sleep(check_interval)

        self.logger.warning(f"⏱️ Timeout waiting for position balance")
        return False

    async def get_position_summary(self) -> str:
        """Get formatted position summary for logging."""
        position = await self.get_positions()

        lines = [
            "=" * 50,
            "📊 POSITION SUMMARY",
            f"   GRVT: {position.grvt}",
            f"   Lighter: {position.lighter}",
            f"   Imbalance: {position.imbalance:.4f}",
            f"   Total Exposure: {position.total_exposure}",
            "=" * 50
        ]

        return "\n".join(lines)