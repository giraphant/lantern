"""
Binance exchange client implementation.
支持现货和永续合约的funding rate套利
"""

import os
import asyncio
import hmac
import hashlib
import time
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple
import aiohttp

from .base import BaseExchangeClient, OrderResult, OrderInfo, query_retry
from helpers.logger import TradingLogger


class BinanceClient(BaseExchangeClient):
    """Binance exchange client implementation."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize Binance client."""
        super().__init__(config)

        # Binance credentials from environment
        self.api_key = os.getenv('BINANCE_API_KEY')
        self.secret_key = os.getenv('BINANCE_SECRET_KEY')

        if not self.api_key or not self.secret_key:
            raise ValueError("BINANCE_API_KEY and BINANCE_SECRET_KEY must be set in environment variables")

        # API endpoints
        self.base_url = "https://fapi.binance.com"  # Futures API

        # Initialize logger
        self.logger = TradingLogger(exchange="binance", ticker=self.config.ticker, log_to_console=False)

        # Session for HTTP requests
        self.session: Optional[aiohttp.ClientSession] = None

    def _validate_config(self):
        """Validate configuration."""
        required = ['ticker', 'quantity']
        missing_vars = [var for var in required if not hasattr(self.config, var)]
        if missing_vars:
            raise ValueError(f"Missing required config: {missing_vars}")

    async def connect(self):
        """Connect to Binance."""
        self.logger.log("Connecting to Binance...", "INFO")
        self.session = aiohttp.ClientSession()

        # Set contract_id (Binance uses symbol like BTCUSDT)
        self.config.contract_id = f"{self.config.ticker}USDT"

        self.logger.log(f"Connected to Binance, contract: {self.config.contract_id}", "INFO")

    async def disconnect(self):
        """Disconnect from Binance."""
        if self.session:
            await self.session.close()
            self.session = None

    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """Generate HMAC SHA256 signature for Binance API."""
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature

    async def _request(self, method: str, endpoint: str, signed: bool = False, **kwargs) -> Dict:
        """Make HTTP request to Binance API."""
        url = f"{self.base_url}{endpoint}"
        headers = {'X-MBX-APIKEY': self.api_key}

        if signed:
            params = kwargs.get('params', {})
            params['timestamp'] = int(time.time() * 1000)
            params['signature'] = self._generate_signature(params)
            kwargs['params'] = params

        async with self.session.request(method, url, headers=headers, **kwargs) as resp:
            data = await resp.json()
            if resp.status != 200:
                raise Exception(f"Binance API error: {data}")
            return data

    @query_retry(reraise=True)
    async def get_funding_rate(self, contract_id: str) -> Decimal:
        """
        Get the current funding rate for a contract.

        Returns:
            Decimal: Funding rate as a decimal (e.g., 0.0001 = 0.01%)
        """
        try:
            # Get funding rate from Binance Futures API
            data = await self._request(
                'GET',
                '/fapi/v1/premiumIndex',
                params={'symbol': contract_id}
            )

            if 'lastFundingRate' in data:
                return Decimal(str(data['lastFundingRate']))
            else:
                self.logger.log(f"No funding rate data for {contract_id}", "WARNING")
                return Decimal("0")

        except Exception as e:
            self.logger.log(f"Error fetching funding rate for {contract_id}: {e}", "ERROR")
            return Decimal("0")

    @query_retry(reraise=True)
    async def get_funding_interval_hours(self, contract_id: str) -> int:
        """
        Get the funding interval in hours for a contract.

        Binance uses 8-hour funding intervals for most contracts.

        Returns:
            int: Funding interval in hours (always 8 for Binance)
        """
        return 8

    async def get_positions(self) -> Decimal:
        """
        Get current position size.

        Returns:
            Decimal: Position size (positive for long, negative for short)
        """
        try:
            data = await self._request(
                'GET',
                '/fapi/v2/positionRisk',
                signed=True,
                params={'symbol': self.config.contract_id}
            )

            for position in data:
                if position['symbol'] == self.config.contract_id:
                    return Decimal(str(position['positionAmt']))

            return Decimal("0")

        except Exception as e:
            self.logger.log(f"Error fetching positions: {e}", "ERROR")
            return Decimal("0")

    async def place_open_order(self, contract_id: str, quantity: Decimal, price: Decimal, side: str) -> OrderResult:
        """
        Place an open order.

        Args:
            contract_id: Contract identifier
            quantity: Order quantity
            price: Order price
            side: 'buy' or 'sell'

        Returns:
            OrderResult: Order placement result
        """
        try:
            params = {
                'symbol': contract_id,
                'side': side.upper(),
                'type': 'LIMIT',
                'timeInForce': 'GTC',
                'quantity': str(quantity),
                'price': str(price)
            }

            data = await self._request(
                'POST',
                '/fapi/v1/order',
                signed=True,
                params=params
            )

            return OrderResult(
                success=True,
                order_id=str(data['orderId']),
                side=side,
                size=quantity,
                price=price,
                status='OPEN'
            )

        except Exception as e:
            self.logger.log(f"Error placing order: {e}", "ERROR")
            return OrderResult(success=False, error_message=str(e))

    async def place_close_order(self, contract_id: str, quantity: Decimal, price: Decimal, side: str) -> OrderResult:
        """Place a close order (same as open order for Binance)."""
        return await self.place_open_order(contract_id, quantity, price, side)

    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order."""
        try:
            await self._request(
                'DELETE',
                '/fapi/v1/order',
                signed=True,
                params={
                    'symbol': self.config.contract_id,
                    'orderId': order_id
                }
            )
            return True

        except Exception as e:
            self.logger.log(f"Error canceling order: {e}", "ERROR")
            return False

    async def cancel_all_orders(self):
        """Cancel all active orders."""
        try:
            await self._request(
                'DELETE',
                '/fapi/v1/allOpenOrders',
                signed=True,
                params={'symbol': self.config.contract_id}
            )
            self.logger.log("All orders canceled", "INFO")

        except Exception as e:
            self.logger.log(f"Error canceling all orders: {e}", "ERROR")

    async def get_active_orders(self, contract_id: str) -> List[OrderInfo]:
        """Get all active orders."""
        try:
            data = await self._request(
                'GET',
                '/fapi/v1/openOrders',
                signed=True,
                params={'symbol': contract_id}
            )

            orders = []
            for order in data:
                orders.append(OrderInfo(
                    order_id=str(order['orderId']),
                    side=order['side'].lower(),
                    size=Decimal(str(order['origQty'])),
                    filled_size=Decimal(str(order['executedQty'])),
                    price=Decimal(str(order['price'])),
                    status=order['status']
                ))

            return orders

        except Exception as e:
            self.logger.log(f"Error fetching active orders: {e}", "ERROR")
            return []

    async def fetch_bbo_prices(self, contract_id: str) -> Tuple[Decimal, Decimal]:
        """
        Fetch best bid and best offer prices.

        Returns:
            Tuple[Decimal, Decimal]: (best_bid, best_ask)
        """
        try:
            data = await self._request(
                'GET',
                '/fapi/v1/ticker/bookTicker',
                params={'symbol': contract_id}
            )

            best_bid = Decimal(str(data['bidPrice']))
            best_ask = Decimal(str(data['askPrice']))

            return best_bid, best_ask

        except Exception as e:
            self.logger.log(f"Error fetching BBO: {e}", "ERROR")
            return Decimal("0"), Decimal("0")
