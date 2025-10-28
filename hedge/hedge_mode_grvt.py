import asyncio
import json
import signal
import logging
import os
import sys
import time
import requests
import argparse
import traceback
import csv
from decimal import Decimal
from typing import Tuple

from lighter.signer_client import SignerClient
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from exchanges.grvt import GrvtClient
import websockets
from datetime import datetime
import pytz


class Config:
    """Simple config class to wrap dictionary for GRVT client."""
    def __init__(self, config_dict):
        for key, value in config_dict.items():
            setattr(self, key, value)


class HedgeBot:
    """Trading bot that places post-only orders on GRVT and hedges with market orders on Lighter."""

    def __init__(self, ticker: str, order_quantity: Decimal, fill_timeout: int = 5, iterations: int = 20,
                 price_tolerance_ticks: int = 3, min_order_lifetime: int = 30,
                 rebalance_threshold: Decimal = Decimal('0.15'), auto_rebalance: bool = True,
                 build_up_iterations: int = None, hold_time: int = 0, cycles: int = None,
                 direction: str = 'long'):
        self.ticker = ticker
        self.order_quantity = order_quantity
        self.fill_timeout = fill_timeout
        self.lighter_order_filled = False
        self.iterations = iterations
        self.grvt_position = Decimal('0')
        self.lighter_position = Decimal('0')
        self.current_order = {}

        # Price tolerance parameters
        self.price_tolerance_ticks = price_tolerance_ticks
        self.min_order_lifetime = min_order_lifetime

        # Auto-rebalance parameters
        self.rebalance_threshold = rebalance_threshold
        self.auto_rebalance = auto_rebalance
        self.rebalance_attempts = 0
        self.max_rebalance_attempts = 3

        # Cycle mode parameters
        self.build_up_iterations = build_up_iterations if build_up_iterations else iterations
        self.hold_time = hold_time
        self.cycles = cycles if cycles else 1

        # Direction parameter (based on Lighter position: long, short, or random)
        # long = Lighter long (buy) + GRVT short (sell) hedge
        # short = Lighter short (sell) + GRVT long (buy) hedge
        self.direction = direction.lower()
        if self.direction not in ['long', 'short', 'random']:
            raise ValueError(f"Invalid direction: {direction}. Must be 'long', 'short', or 'random'")

        # Initialize logging to file
        os.makedirs("logs", exist_ok=True)
        self.log_filename = f"logs/grvt_{ticker}_hedge_mode_log.txt"
        self.csv_filename = f"logs/grvt_{ticker}_hedge_mode_trades.csv"
        self.original_stdout = sys.stdout

        # Initialize CSV file with headers if it doesn't exist
        self._initialize_csv_file()

        # Setup logger
        self.logger = logging.getLogger(f"hedge_bot_{ticker}")
        self.logger.setLevel(logging.INFO)

        # Clear any existing handlers to avoid duplicates
        self.logger.handlers.clear()

        # Disable verbose logging from external libraries
        logging.getLogger('urllib3').setLevel(logging.CRITICAL)
        logging.getLogger('requests').setLevel(logging.CRITICAL)
        logging.getLogger('websockets').setLevel(logging.CRITICAL)
        logging.getLogger('pysdk').setLevel(logging.CRITICAL)
        logging.getLogger('pysdk.grvt_ccxt').setLevel(logging.CRITICAL)
        logging.getLogger('pysdk.grvt_ccxt_ws').setLevel(logging.CRITICAL)
        logging.getLogger('pysdk.grvt_ccxt_logging_selector').setLevel(logging.CRITICAL)
        logging.getLogger('pysdk.grvt_ccxt_env').setLevel(logging.CRITICAL)
        logging.getLogger('lighter').setLevel(logging.CRITICAL)
        logging.getLogger('lighter.signer_client').setLevel(logging.CRITICAL)
        
        # Disable root logger propagation to prevent external logs
        logging.getLogger().setLevel(logging.CRITICAL)

        # Create file handler
        file_handler = logging.FileHandler(self.log_filename)
        file_handler.setLevel(logging.INFO)

        # Create console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)

        # Create different formatters for file and console
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_formatter = logging.Formatter('%(levelname)s:%(name)s:%(message)s')

        file_handler.setFormatter(file_formatter)
        console_handler.setFormatter(console_formatter)

        # Add handlers to logger
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

        # Prevent propagation to root logger to avoid duplicate messages and external logs
        self.logger.propagate = False
        
        # Ensure our logger only shows our messages
        self.logger.setLevel(logging.INFO)

        # State management
        self.stop_flag = False
        self.order_counter = 0

        # GRVT state
        self.grvt_client = None
        self.grvt_contract_id = None
        self.grvt_tick_size = None
        self.grvt_order_status = None

        # GRVT order book state (not used since we use REST API for BBO)
        # Keeping variables for potential future use but not initializing them

        # Lighter order book state
        self.lighter_client = None
        self.lighter_order_book = {"bids": {}, "asks": {}}
        self.lighter_best_bid = None
        self.lighter_best_ask = None
        self.lighter_order_book_ready = False
        self.lighter_order_book_offset = 0
        self.lighter_order_book_sequence_gap = False
        self.lighter_snapshot_loaded = False
        self.lighter_order_book_lock = asyncio.Lock()

        # Lighter WebSocket state
        self.lighter_ws_task = None
        self.lighter_order_result = None

        # Lighter order management
        self.lighter_order_status = None
        self.lighter_order_price = None
        self.lighter_order_side = None
        self.lighter_order_size = None
        self.lighter_order_start_time = None

        # Strategy state
        self.waiting_for_lighter_fill = False
        self.wait_start_time = None

        # Order execution tracking
        self.order_execution_complete = False

        # Event-driven order tracking (initialized later in async context)
        self.grvt_filled_event = None
        self.lighter_filled_event = None

        # Current order details for immediate execution
        self.current_lighter_side = None
        self.current_lighter_quantity = None
        self.current_lighter_price = None
        self.lighter_order_info = None
        self.current_grvt_order_id = None

        # Lighter API configuration
        self.lighter_base_url = "https://mainnet.zklighter.elliot.ai"
        self.account_index = int(os.getenv('LIGHTER_ACCOUNT_INDEX'))
        self.api_key_index = int(os.getenv('LIGHTER_API_KEY_INDEX'))

        # GRVT configuration
        self.grvt_trading_account_id = os.getenv('GRVT_TRADING_ACCOUNT_ID')
        self.grvt_private_key = os.getenv('GRVT_PRIVATE_KEY')
        self.grvt_api_key = os.getenv('GRVT_API_KEY')
        self.grvt_environment = os.getenv('GRVT_ENVIRONMENT', 'prod')

    def shutdown(self, signum=None, frame=None):
        """Graceful shutdown handler."""
        self.stop_flag = True
        self.logger.info("\n🛑 Stopping...")

        # Close WebSocket connections
        if self.grvt_client:
            try:
                # Note: disconnect() is async, but shutdown() is sync
                # We'll let the cleanup happen naturally
                self.logger.info("🔌 GRVT WebSocket will be disconnected")
            except Exception as e:
                self.logger.error(f"Error disconnecting GRVT WebSocket: {e}")

        # Cancel Lighter WebSocket task
        if self.lighter_ws_task and not self.lighter_ws_task.done():
            try:
                self.lighter_ws_task.cancel()
                self.logger.info("🔌 Lighter WebSocket task cancelled")
            except Exception as e:
                self.logger.error(f"Error cancelling Lighter WebSocket task: {e}")

        # Close logging handlers properly
        for handler in self.logger.handlers[:]:
            try:
                handler.close()
                self.logger.removeHandler(handler)
            except Exception:
                pass

    def _initialize_csv_file(self):
        """Initialize CSV file with headers if it doesn't exist."""
        if not os.path.exists(self.csv_filename):
            with open(self.csv_filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(['exchange', 'timestamp', 'side', 'price', 'quantity'])

    def log_trade_to_csv(self, exchange: str, side: str, price: str, quantity: str):
        """Log trade details to CSV file."""
        timestamp = datetime.now(pytz.UTC).isoformat()

        with open(self.csv_filename, 'a', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                exchange,
                timestamp,
                side,
                price,
                quantity
            ])

        self.logger.info(f"📊 Trade logged to CSV: {exchange} {side} {quantity} @ {price}")

    def handle_lighter_order_result(self, order_data):
        """Handle Lighter order result from WebSocket."""
        try:
            order_data["avg_filled_price"] = (Decimal(order_data["filled_quote_amount"]) /
                                              Decimal(order_data["filled_base_amount"]))
            if order_data["is_ask"]:
                order_data["side"] = "SHORT"
                order_type = "OPEN"
                self.lighter_position -= Decimal(order_data["filled_base_amount"])
            else:
                order_data["side"] = "LONG"
                order_type = "CLOSE"
                self.lighter_position += Decimal(order_data["filled_base_amount"])

            client_order_index = order_data["client_order_id"]

            self.logger.info(f"[{client_order_index}] [{order_type}] [Lighter] [FILLED]: "
                             f"{order_data['filled_base_amount']} @ {order_data['avg_filled_price']}")

            # Log Lighter trade to CSV
            self.log_trade_to_csv(
                exchange='Lighter',
                side=order_data['side'],
                price=str(order_data['avg_filled_price']),
                quantity=str(order_data['filled_base_amount'])
            )

            # Mark execution as complete
            self.lighter_order_filled = True  # Mark order as filled
            self.order_execution_complete = True

            # Trigger event for hybrid waiting
            if self.lighter_filled_event:
                self.lighter_filled_event.set()

        except Exception as e:
            self.logger.error(f"Error handling Lighter order result: {e}")

    async def reset_lighter_order_book(self):
        """Reset Lighter order book state."""
        async with self.lighter_order_book_lock:
            self.lighter_order_book["bids"].clear()
            self.lighter_order_book["asks"].clear()
            self.lighter_order_book_offset = 0
            self.lighter_order_book_sequence_gap = False
            self.lighter_snapshot_loaded = False
            self.lighter_best_bid = None
            self.lighter_best_ask = None

    def update_lighter_order_book(self, side: str, levels: list):
        """Update Lighter order book with new levels."""
        for level in levels:
            # Handle different data structures - could be list [price, size] or dict {"price": ..., "size": ...}
            if isinstance(level, list) and len(level) >= 2:
                price = Decimal(level[0])
                size = Decimal(level[1])
            elif isinstance(level, dict):
                price = Decimal(level.get("price", 0))
                size = Decimal(level.get("size", 0))
            else:
                self.logger.warning(f"⚠️ Unexpected level format: {level}")
                continue

            if size > 0:
                self.lighter_order_book[side][price] = size
            else:
                # Remove zero size orders
                self.lighter_order_book[side].pop(price, None)

    def validate_order_book_offset(self, new_offset: int) -> bool:
        """Validate order book offset sequence."""
        if new_offset <= self.lighter_order_book_offset:
            self.logger.warning(
                f"⚠️ Out-of-order update: new_offset={new_offset}, current_offset={self.lighter_order_book_offset}")
            return False
        return True

    def validate_order_book_integrity(self) -> bool:
        """Validate order book integrity."""
        # Check for negative prices or sizes
        for side in ["bids", "asks"]:
            for price, size in self.lighter_order_book[side].items():
                if price <= 0 or size <= 0:
                    self.logger.error(f"❌ Invalid order book data: {side} price={price}, size={size}")
                    return False
        return True

    def get_lighter_best_levels(self) -> Tuple[Tuple[Decimal, Decimal], Tuple[Decimal, Decimal]]:
        """Get best bid and ask levels from Lighter order book."""
        best_bid = None
        best_ask = None

        if self.lighter_order_book["bids"]:
            best_bid_price = max(self.lighter_order_book["bids"].keys())
            best_bid_size = self.lighter_order_book["bids"][best_bid_price]
            best_bid = (best_bid_price, best_bid_size)

        if self.lighter_order_book["asks"]:
            best_ask_price = min(self.lighter_order_book["asks"].keys())
            best_ask_size = self.lighter_order_book["asks"][best_ask_price]
            best_ask = (best_ask_price, best_ask_size)

        return best_bid, best_ask

    def get_lighter_mid_price(self) -> Decimal:
        """Get mid price from Lighter order book."""
        best_bid, best_ask = self.get_lighter_best_levels()

        if best_bid is None or best_ask is None:
            raise Exception("Cannot calculate mid price - missing order book data")

        mid_price = (best_bid[0] + best_ask[0]) / Decimal('2')
        return mid_price

    def get_lighter_order_price(self, is_ask: bool) -> Decimal:
        """Get order price from Lighter order book."""
        best_bid, best_ask = self.get_lighter_best_levels()

        if best_bid is None or best_ask is None:
            raise Exception("Cannot calculate order price - missing order book data")

        if is_ask:
            order_price = best_bid[0] + Decimal('0.1')
        else:
            order_price = best_ask[0] - Decimal('0.1')

        return order_price

    def calculate_adjusted_price(self, original_price: Decimal, side: str, adjustment_percent: Decimal) -> Decimal:
        """Calculate adjusted price for order modification."""
        adjustment = original_price * adjustment_percent

        if side.lower() == 'buy':
            # For buy orders, increase price to improve fill probability
            return original_price + adjustment
        else:
            # For sell orders, decrease price to improve fill probability
            return original_price - adjustment

    async def request_fresh_snapshot(self, ws):
        """Request fresh order book snapshot."""
        await ws.send(json.dumps({"type": "subscribe", "channel": f"order_book/{self.lighter_market_index}"}))

    async def handle_lighter_ws(self):
        """Handle Lighter WebSocket connection and messages."""
        url = "wss://mainnet.zklighter.elliot.ai/stream"
        cleanup_counter = 0

        while not self.stop_flag:
            timeout_count = 0
            try:
                # Reset order book state before connecting
                await self.reset_lighter_order_book()

                async with websockets.connect(url) as ws:
                    # Subscribe to order book updates
                    await ws.send(json.dumps({"type": "subscribe", "channel": f"order_book/{self.lighter_market_index}"}))

                    # Subscribe to account orders updates
                    account_orders_channel = f"account_orders/{self.lighter_market_index}/{self.account_index}"

                    # Get auth token for the subscription
                    try:
                        # Set auth token to expire in 10 minutes
                        ten_minutes_deadline = int(time.time() + 10 * 60)
                        auth_token, err = self.lighter_client.create_auth_token_with_expiry(ten_minutes_deadline)
                        if err is not None:
                            self.logger.warning(f"⚠️ Failed to create auth token for account orders subscription: {err}")
                        else:
                            auth_message = {
                                "type": "subscribe",
                                "channel": account_orders_channel,
                                "auth": auth_token
                            }
                            await ws.send(json.dumps(auth_message))
                            self.logger.info("✅ Subscribed to account orders with auth token (expires in 10 minutes)")
                    except Exception as e:
                        self.logger.warning(f"⚠️ Error creating auth token for account orders subscription: {e}")

                    while not self.stop_flag:
                        try:
                            msg = await asyncio.wait_for(ws.recv(), timeout=1)

                            try:
                                data = json.loads(msg)
                            except json.JSONDecodeError as e:
                                self.logger.warning(f"⚠️ JSON parsing error in Lighter websocket: {e}")
                                continue

                            # Reset timeout counter on successful message
                            timeout_count = 0

                            async with self.lighter_order_book_lock:
                                if data.get("type") == "subscribed/order_book":
                                    # Initial snapshot - clear and populate the order book
                                    self.lighter_order_book["bids"].clear()
                                    self.lighter_order_book["asks"].clear()

                                    # Handle the initial snapshot
                                    order_book = data.get("order_book", {})
                                    if order_book and "offset" in order_book:
                                        self.lighter_order_book_offset = order_book["offset"]
                                        self.logger.info(f"✅ Initial order book offset set to: {self.lighter_order_book_offset}")

                                    # Debug: Log the structure of bids and asks
                                    bids = order_book.get("bids", [])
                                    asks = order_book.get("asks", [])
                                    if bids:
                                        self.logger.debug(f"📊 Sample bid structure: {bids[0] if bids else 'None'}")
                                    if asks:
                                        self.logger.debug(f"📊 Sample ask structure: {asks[0] if asks else 'None'}")

                                    self.update_lighter_order_book("bids", bids)
                                    self.update_lighter_order_book("asks", asks)
                                    self.lighter_snapshot_loaded = True
                                    self.lighter_order_book_ready = True

                                    self.logger.info(f"✅ Lighter order book snapshot loaded with "
                                                     f"{len(self.lighter_order_book['bids'])} bids and "
                                                     f"{len(self.lighter_order_book['asks'])} asks")

                                elif data.get("type") == "update/order_book" and self.lighter_snapshot_loaded:
                                    # Extract offset from the message
                                    order_book = data.get("order_book", {})
                                    if not order_book or "offset" not in order_book:
                                        self.logger.warning("⚠️ Order book update missing offset, skipping")
                                        continue

                                    new_offset = order_book["offset"]

                                    # Validate offset sequence
                                    if not self.validate_order_book_offset(new_offset):
                                        self.lighter_order_book_sequence_gap = True
                                        break

                                    # Update the order book with new data
                                    self.update_lighter_order_book("bids", order_book.get("bids", []))
                                    self.update_lighter_order_book("asks", order_book.get("asks", []))

                                    # Validate order book integrity after update
                                    if not self.validate_order_book_integrity():
                                        self.logger.warning("🔄 Order book integrity check failed, requesting fresh snapshot...")
                                        break

                                    # Get the best bid and ask levels
                                    best_bid, best_ask = self.get_lighter_best_levels()

                                    # Update global variables
                                    if best_bid is not None:
                                        self.lighter_best_bid = best_bid[0]
                                    if best_ask is not None:
                                        self.lighter_best_ask = best_ask[0]

                                elif data.get("type") == "ping":
                                    # Respond to ping with pong
                                    await ws.send(json.dumps({"type": "pong"}))
                                elif data.get("type") == "update/account_orders":
                                    # Handle account orders updates
                                    orders = data.get("orders", {}).get(str(self.lighter_market_index), [])
                                    for order in orders:
                                        if order.get("status") == "filled":
                                            self.handle_lighter_order_result(order)
                                elif data.get("type") == "update/order_book" and not self.lighter_snapshot_loaded:
                                    # Ignore updates until we have the initial snapshot
                                    continue

                            # Periodic cleanup outside the lock
                            cleanup_counter += 1
                            if cleanup_counter >= 1000:
                                cleanup_counter = 0

                            # Handle sequence gap and integrity issues outside the lock
                            if self.lighter_order_book_sequence_gap:
                                try:
                                    await self.request_fresh_snapshot(ws)
                                    self.lighter_order_book_sequence_gap = False
                                except Exception as e:
                                    self.logger.error(f"⚠️ Failed to request fresh snapshot: {e}")
                                    break

                        except asyncio.TimeoutError:
                            timeout_count += 1
                            if timeout_count % 3 == 0:
                                self.logger.warning(f"⏰ No message from Lighter websocket for {timeout_count} seconds")
                            continue
                        except websockets.exceptions.ConnectionClosed as e:
                            self.logger.warning(f"⚠️ Lighter websocket connection closed: {e}")
                            break
                        except websockets.exceptions.WebSocketException as e:
                            self.logger.warning(f"⚠️ Lighter websocket error: {e}")
                            break
                        except Exception as e:
                            self.logger.error(f"⚠️ Error in Lighter websocket: {e}")
                            self.logger.error(f"⚠️ Full traceback: {traceback.format_exc()}")
                            break
            except Exception as e:
                self.logger.error(f"⚠️ Failed to connect to Lighter websocket: {e}")

            # Wait a bit before reconnecting
            await asyncio.sleep(2)

    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

    def initialize_lighter_client(self):
        """Initialize the Lighter client."""
        if self.lighter_client is None:
            api_key_private_key = os.getenv('LIGHTER_PRIVATE_KEY')
            if not api_key_private_key:
                raise Exception("LIGHTER_PRIVATE_KEY environment variable not set")

            self.lighter_client = SignerClient(
                url=self.lighter_base_url,
                private_key=api_key_private_key,
                account_index=self.account_index,
                api_key_index=self.api_key_index,
            )

            # Check client
            err = self.lighter_client.check_client()
            if err is not None:
                raise Exception(f"CheckClient error: {err}")

            self.logger.info("✅ Lighter client initialized successfully")
        return self.lighter_client

    def initialize_grvt_client(self):
        """Initialize the GRVT client."""
        if not all([self.grvt_trading_account_id, self.grvt_private_key, self.grvt_api_key]):
            raise ValueError("GRVT_TRADING_ACCOUNT_ID, GRVT_PRIVATE_KEY, and GRVT_API_KEY must be set in environment variables")

        # Create config for GRVT client
        config_dict = {
            'ticker': self.ticker,
            'contract_id': '',  # Will be set when we get contract info
            'quantity': self.order_quantity,
            'tick_size': Decimal('0.01'),  # Will be updated when we get contract info
            'close_order_side': 'sell'  # Default, will be updated based on strategy
        }

        # Wrap in Config class for GRVT client
        config = Config(config_dict)

        # Initialize GRVT client
        self.grvt_client = GrvtClient(config)

        self.logger.info("✅ GRVT client initialized successfully")
        return self.grvt_client

    def get_lighter_market_config(self) -> Tuple[int, int, int]:
        """Get Lighter market configuration."""
        url = f"{self.lighter_base_url}/api/v1/orderBooks"
        headers = {"accept": "application/json"}

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            if not response.text.strip():
                raise Exception("Empty response from Lighter API")

            data = response.json()

            if "order_books" not in data:
                raise Exception("Unexpected response format")

            for market in data["order_books"]:
                if market["symbol"] == self.ticker:
                    return (market["market_id"],
                            pow(10, market["supported_size_decimals"]),
                            pow(10, market["supported_price_decimals"]))

            raise Exception(f"Ticker {self.ticker} not found")

        except Exception as e:
            self.logger.error(f"⚠️ Error getting market config: {e}")
            raise

    async def get_grvt_contract_info(self) -> Tuple[str, Decimal]:
        """Get GRVT contract ID and tick size."""
        if not self.grvt_client:
            raise Exception("GRVT client not initialized")

        contract_id, tick_size = await self.grvt_client.get_contract_attributes()

        if self.order_quantity < self.grvt_client.config.quantity:
            raise ValueError(
                f"Order quantity is less than min quantity: {self.order_quantity} < {self.grvt_client.config.quantity}")

        return contract_id, tick_size

    async def fetch_grvt_bbo_prices(self) -> Tuple[Decimal, Decimal]:
        """Fetch best bid/ask prices from GRVT using REST API with timeout."""
        if not self.grvt_client:
            raise Exception("GRVT client not initialized")

        try:
            best_bid, best_ask = await asyncio.wait_for(
                self.grvt_client.fetch_bbo_prices(self.grvt_contract_id),
                timeout=10.0  # 10 second timeout for price fetch
            )
            return best_bid, best_ask
        except asyncio.TimeoutError:
            self.logger.warning("⚠️ Fetching BBO prices timed out, retrying...")
            # Retry once
            best_bid, best_ask = await asyncio.wait_for(
                self.grvt_client.fetch_bbo_prices(self.grvt_contract_id),
                timeout=10.0
            )
            return best_bid, best_ask

    def round_to_tick(self, price: Decimal) -> Decimal:
        """Round price to tick size."""
        if self.grvt_tick_size is None:
            return price
        return (price / self.grvt_tick_size).quantize(Decimal('1')) * self.grvt_tick_size

    async def place_bbo_order(self, side: str, quantity: Decimal):
        # Place the order using GRVT client with timeout
        try:
            order_result = await asyncio.wait_for(
                self.grvt_client.place_open_order(
                    contract_id=self.grvt_contract_id,
                    quantity=quantity,
                    direction=side.lower()
                ),
                timeout=30.0  # 30 second timeout for order placement
            )

            if order_result.success:
                return order_result.order_id, order_result.price
            else:
                raise Exception(f"Failed to place order: {order_result.error_message}")
        except asyncio.TimeoutError:
            raise Exception("Order placement timed out after 30 seconds")

    async def place_grvt_post_only_order(self, side: str, quantity: Decimal):
        """Place a post-only order on GRVT."""
        if not self.grvt_client:
            raise Exception("GRVT client not initialized")

        self.grvt_order_status = None

        # Reset event for new order
        if self.grvt_filled_event:
            self.grvt_filled_event.clear()

        self.logger.info(f"[OPEN] [GRVT] [{side}] Placing GRVT POST-ONLY order")
        order_id, order_price = await self.place_bbo_order(side, quantity)
        self.current_grvt_order_id = order_id

        start_time = time.time()
        while not self.stop_flag:
            if self.grvt_order_status == 'CANCELED':
                self.grvt_order_status = 'NEW'
                order_id, order_price = await self.place_bbo_order(side, quantity)
                start_time = time.time()
                await asyncio.sleep(0.5)
            elif self.grvt_order_status in ['NEW', 'OPEN', 'PENDING', 'CANCELING', 'PARTIALLY_FILLED']:
                await asyncio.sleep(0.5)

                # Check if enough time has passed and order needs adjustment
                time_elapsed = time.time() - start_time

                # Only consider canceling after minimum order lifetime
                if time_elapsed > self.min_order_lifetime:
                    best_bid, best_ask = await self.fetch_grvt_bbo_prices()
                    should_cancel = False

                    # Calculate tolerance in price units
                    price_tolerance = Decimal(self.price_tolerance_ticks) * self.grvt_tick_size

                    if side == 'buy':
                        # Cancel only if our price is worse than (best_bid - tolerance)
                        if order_price < best_bid - price_tolerance:
                            should_cancel = True
                            self.logger.info(f"📊 Buy order price {order_price} is {best_bid - order_price:.2f} below best bid {best_bid} (tolerance: {price_tolerance})")
                    else:
                        # Cancel only if our price is worse than (best_ask + tolerance)
                        if order_price > best_ask + price_tolerance:
                            should_cancel = True
                            self.logger.info(f"📊 Sell order price {order_price} is {order_price - best_ask:.2f} above best ask {best_ask} (tolerance: {price_tolerance})")

                    if should_cancel:
                        try:
                            # Cancel the order using GRVT client
                            self.logger.info(f"🔄 Canceling order {order_id} after {time_elapsed:.1f}s - price outside tolerance")
                            cancel_result = await self.grvt_client.cancel_order(order_id)
                            if not cancel_result.success:
                                self.logger.error(f"❌ Error canceling GRVT order: {cancel_result.error_message}")
                        except Exception as e:
                            self.logger.error(f"❌ Error canceling GRVT order: {e}")
                    else:
                        self.logger.debug(f"✅ Order {order_id} price within tolerance, waiting for fill")
                        start_time = time.time()  # Reset timer
            elif self.grvt_order_status == 'FILLED':
                break
            else:
                if self.grvt_order_status is not None:
                    self.logger.error(f"❌ Unknown GRVT order status: {self.grvt_order_status}")
                    break
                else:
                    await asyncio.sleep(0.5)


    def handle_grvt_order_update(self, order_data):
        """Handle GRVT order updates from WebSocket."""
        side = order_data.get('side', '').lower()
        filled_size = Decimal(order_data.get('filled_size', '0'))
        price = Decimal(order_data.get('price', '0'))

        if side == 'buy':
            lighter_side = 'sell'
        else:
            lighter_side = 'buy'

        # Store order details for immediate execution
        self.current_lighter_side = lighter_side
        self.current_lighter_quantity = filled_size
        self.current_lighter_price = price

        self.lighter_order_info = {
            'lighter_side': lighter_side,
            'quantity': filled_size,
            'price': price
        }

        self.waiting_for_lighter_fill = True


    async def place_lighter_market_order(self, lighter_side: str, quantity: Decimal, price: Decimal):
        if not self.lighter_client:
            await self.initialize_lighter_client()

        best_bid, best_ask = self.get_lighter_best_levels()

        # Determine order parameters
        if lighter_side.lower() == 'buy':
            order_type = "CLOSE"
            is_ask = False
            price = best_ask[0] * Decimal('1.002')
        else:
            order_type = "OPEN"
            is_ask = True
            price = best_bid[0] * Decimal('0.998')


        # Reset order state
        self.lighter_order_filled = False
        self.lighter_order_price = price
        self.lighter_order_side = lighter_side
        self.lighter_order_size = quantity

        # Reset event for new order
        if self.lighter_filled_event:
            self.lighter_filled_event.clear()

        try:
            client_order_index = int(time.time() * 1000)
            # Sign the order transaction
            tx_info, error = self.lighter_client.sign_create_order(
                market_index=self.lighter_market_index,
                client_order_index=client_order_index,
                base_amount=int(quantity * self.base_amount_multiplier),
                price=int(price * self.price_multiplier),
                is_ask=is_ask,
                order_type=self.lighter_client.ORDER_TYPE_LIMIT,
                time_in_force=self.lighter_client.ORDER_TIME_IN_FORCE_GOOD_TILL_TIME,
                reduce_only=False,
                trigger_price=0,
            )
            if error is not None:
                raise Exception(f"Sign error: {error}")

            # Prepare the form data
            tx_hash = await self.lighter_client.send_tx(
                tx_type=self.lighter_client.TX_TYPE_CREATE_ORDER,
                tx_info=tx_info
            )

            self.logger.info(f"[{client_order_index}] [{order_type}] [Lighter] [OPEN]: {quantity}")

            await self.monitor_lighter_order(client_order_index)

            return tx_hash
        except Exception as e:
            self.logger.error(f"❌ Error placing Lighter order: {e}")
            return None

    async def monitor_lighter_order(self, client_order_index: int):
        """Monitor Lighter order using hybrid approach."""
        # Use the hybrid waiting method
        success = await self.wait_for_lighter_fill_with_fallback(client_order_index, timeout=30)

        if not success:
            # Timeout reached and order not confirmed filled
            self.logger.error(f"❌ Lighter order {client_order_index} did not fill in time")
            self.logger.warning("⚠️ Check position manually - potential mismatch")
        else:
            self.logger.info(f"✅ Lighter order {client_order_index} confirmed filled")

    async def modify_lighter_order(self, client_order_index: int, new_price: Decimal):
        """Modify current Lighter order with new price using client_order_index."""
        try:
            if client_order_index is None:
                self.logger.error("❌ Cannot modify order - no order ID available")
                return

            # Calculate new Lighter price
            lighter_price = int(new_price * self.price_multiplier)

            self.logger.info(f"🔧 Attempting to modify order - Market: {self.lighter_market_index}, "
                             f"Client Order Index: {client_order_index}, New Price: {lighter_price}")

            # Use the native SignerClient's modify_order method
            tx_info, tx_hash, error = await self.lighter_client.modify_order(
                market_index=self.lighter_market_index,
                order_index=client_order_index,  # Use client_order_index directly
                base_amount=int(self.lighter_order_size * self.base_amount_multiplier),
                price=lighter_price,
                trigger_price=0
            )

            if error is not None:
                self.logger.error(f"❌ Lighter order modification error: {error}")
                return

            self.lighter_order_price = new_price
            self.logger.info(f"🔄 Lighter order modified successfully: {self.lighter_order_side} "
                             f"{self.lighter_order_size} @ {new_price}")

        except Exception as e:
            self.logger.error(f"❌ Error modifying Lighter order: {e}")
            import traceback
            self.logger.error(f"❌ Full traceback: {traceback.format_exc()}")

    async def wait_for_grvt_fill_with_fallback(self, order_id: str, timeout: int = 180) -> bool:
        """Wait for GRVT order to fill using hybrid approach: event-driven + periodic status check.

        Args:
            order_id: GRVT order ID to monitor
            timeout: Maximum time to wait in seconds

        Returns:
            True if order filled, False if timeout or error
        """
        start_time = time.time()
        last_status_check = 0
        status_check_interval = 5  # Check actual status every 5 seconds as fallback

        self.logger.info(f"⏳ Waiting for GRVT order {order_id} to fill (hybrid mode)")

        while time.time() - start_time < timeout:
            try:
                # Try to wait for event with short timeout (1 second)
                await asyncio.wait_for(self.grvt_filled_event.wait(), timeout=1.0)
                self.logger.info(f"✅ GRVT order filled (event triggered)")
                return True

            except asyncio.TimeoutError:
                # Event didn't trigger in 1 second, check actual status periodically
                if time.time() - last_status_check >= status_check_interval:
                    try:
                        order_info = await self.grvt_client.get_order_info(order_id)
                        last_status_check = time.time()

                        if order_info and order_info.status == 'FILLED':
                            self.logger.warning(f"⚠️ GRVT order filled but event missed (WebSocket issue?)")
                            # Manually trigger the handling since event was missed
                            self.grvt_order_status = 'FILLED'
                            return True
                        elif order_info and order_info.status == 'CANCELED':
                            self.logger.warning(f"⚠️ GRVT order was canceled")
                            return False

                    except Exception as e:
                        self.logger.warning(f"⚠️ Error checking GRVT order status: {e}")

                # Continue waiting
                continue

        # Timeout reached
        self.logger.error(f"❌ Timeout waiting for GRVT order {order_id} after {timeout}s")
        return False

    async def wait_for_lighter_fill_with_fallback(self, client_order_index: int, timeout: int = 30) -> bool:
        """Wait for Lighter order to fill using hybrid approach.

        Args:
            client_order_index: Lighter client order index
            timeout: Maximum time to wait in seconds

        Returns:
            True if order filled, False if timeout
        """
        start_time = time.time()

        self.logger.info(f"⏳ Waiting for Lighter order {client_order_index} to fill (hybrid mode)")

        while time.time() - start_time < timeout:
            try:
                # Try to wait for event with short timeout (0.5 second)
                await asyncio.wait_for(self.lighter_filled_event.wait(), timeout=0.5)
                self.logger.info(f"✅ Lighter order filled (event triggered)")
                return True

            except asyncio.TimeoutError:
                # Event didn't trigger, continue waiting
                # Note: Lighter doesn't have REST API to check status, rely on WebSocket
                continue

        # Timeout reached
        self.logger.error(f"❌ Timeout waiting for Lighter order {client_order_index} after {timeout}s")

        # Last resort: check if order was actually filled via WebSocket but event missed
        if self.lighter_order_filled:
            self.logger.warning(f"⚠️ Lighter order marked as filled (flag check)")
            return True

        return False

    async def check_position_balance(self) -> Tuple[bool, Decimal]:
        """Check if positions are balanced.

        Returns:
            Tuple of (is_balanced, position_diff)
        """
        position_diff = self.grvt_position + self.lighter_position
        is_balanced = abs(position_diff) <= self.rebalance_threshold

        return is_balanced, position_diff

    async def auto_rebalance_positions(self) -> bool:
        """Automatically rebalance positions if imbalance detected.

        Returns:
            True if rebalance successful or not needed, False if failed
        """
        is_balanced, position_diff = await self.check_position_balance()

        if is_balanced:
            return True

        if not self.auto_rebalance:
            self.logger.error(f"⚠️ Position imbalance detected: {position_diff:.4f}, but auto-rebalance is disabled")
            return False

        self.logger.warning(f"⚠️ Position imbalance detected: GRVT={self.grvt_position}, Lighter={self.lighter_position}, Diff={position_diff:.4f}")
        self.logger.info(f"🔧 Starting auto-rebalance (attempt {self.rebalance_attempts + 1}/{self.max_rebalance_attempts})")

        self.rebalance_attempts += 1

        if self.rebalance_attempts > self.max_rebalance_attempts:
            self.logger.error(f"❌ Max rebalance attempts ({self.max_rebalance_attempts}) reached. Manual intervention required.")
            return False

        try:
            # Determine which side to trade to rebalance
            rebalance_quantity = abs(position_diff)

            if position_diff > 0:
                # GRVT has more long position, need to sell on GRVT
                side = 'sell'
                self.logger.info(f"🔄 Rebalancing: Selling {rebalance_quantity} on GRVT")
            else:
                # GRVT has more short position (or less long), need to buy on GRVT
                side = 'buy'
                self.logger.info(f"🔄 Rebalancing: Buying {rebalance_quantity} on GRVT")

            # Reset execution flags
            self.order_execution_complete = False
            self.waiting_for_lighter_fill = False

            # Place GRVT order to rebalance
            await self.place_grvt_post_only_order(side, rebalance_quantity)

            # Wait for execution
            start_time = time.time()
            while not self.order_execution_complete and not self.stop_flag:
                if self.waiting_for_lighter_fill:
                    await self.place_lighter_market_order(
                        self.current_lighter_side,
                        self.current_lighter_quantity,
                        self.current_lighter_price
                    )
                    break

                await asyncio.sleep(0.1)
                if time.time() - start_time > 120:
                    self.logger.error("❌ Timeout during rebalance")
                    return False

            # Check if rebalance was successful
            is_balanced, new_diff = await self.check_position_balance()

            if is_balanced:
                self.logger.info(f"✅ Rebalance successful! New diff: {new_diff:.4f}")
                self.rebalance_attempts = 0  # Reset counter on success
                return True
            else:
                self.logger.warning(f"⚠️ Rebalance completed but still imbalanced: {new_diff:.4f}")
                # Try again if we haven't hit max attempts
                return await self.auto_rebalance_positions()

        except Exception as e:
            self.logger.error(f"❌ Error during rebalance: {e}")
            self.logger.error(f"❌ Full traceback: {traceback.format_exc()}")
            return False

    async def setup_grvt_websocket(self):
        """Setup GRVT websocket for order updates and order book data."""
        if not self.grvt_client:
            raise Exception("GRVT client not initialized")

        def order_update_handler(order_data):
            """Handle order updates from GRVT WebSocket."""
            if order_data.get('contract_id') != self.grvt_contract_id:
                return
            try:
                order_id = order_data.get('order_id')
                status = order_data.get('status')
                side = order_data.get('side', '').lower()
                filled_size = Decimal(order_data.get('filled_size', '0'))
                size = Decimal(order_data.get('size', '0'))
                price = order_data.get('price', '0')

                if side == 'buy':
                    order_type = "OPEN"
                else:
                    order_type = "CLOSE"
                
                if status == 'CANCELED' and filled_size > 0:
                    status = 'FILLED'

                # Handle the order update
                if status == 'FILLED' and self.grvt_order_status != 'FILLED':
                    if side == 'buy':
                        self.grvt_position += filled_size
                    else:
                        self.grvt_position -= filled_size
                    self.logger.info(f"[{order_id}] [{order_type}] [GRVT] [{status}]: {filled_size} @ {price}")
                    self.grvt_order_status = status

                    # Log GRVT trade to CSV
                    self.log_trade_to_csv(
                        exchange='GRVT',
                        side=side,
                        price=str(price),
                        quantity=str(filled_size)
                    )

                    # Trigger event for hybrid waiting
                    if self.grvt_filled_event:
                        self.grvt_filled_event.set()

                    self.handle_grvt_order_update({
                        'order_id': order_id,
                        'side': side,
                        'status': status,
                        'size': size,
                        'price': price,
                        'contract_id': self.grvt_contract_id,
                        'filled_size': filled_size
                    })
                elif self.grvt_order_status != 'FILLED':
                    if status == 'OPEN':
                        self.logger.info(f"[{order_id}] [{order_type}] [GRVT] [{status}]: {size} @ {price}")
                    else:
                        self.logger.info(f"[{order_id}] [{order_type}] [GRVT] [{status}]: {filled_size} @ {price}")
                    self.grvt_order_status = status

            except Exception as e:
                self.logger.error(f"Error handling GRVT order update: {e}")

        try:
            # Setup order update handler
            self.grvt_client.setup_order_update_handler(order_update_handler)
            self.logger.info("✅ GRVT WebSocket order update handler set up")

            # Connect to GRVT WebSocket
            await self.grvt_client.connect()
            self.logger.info("✅ GRVT WebSocket connection established")


        except Exception as e:
            self.logger.error(f"Could not setup GRVT WebSocket handlers: {e}")


    async def trading_loop(self):
        """Main trading loop implementing the new strategy."""
        self.logger.info(f"🚀 Starting hedge bot for {self.ticker}")

        # Initialize event objects for hybrid mode
        self.grvt_filled_event = asyncio.Event()
        self.lighter_filled_event = asyncio.Event()
        self.logger.info("✅ Event objects initialized for hybrid mode")

        # Log configuration
        self.logger.info("=== Configuration ===")
        self.logger.info(f"Order Quantity: {self.order_quantity}")
        self.logger.info(f"Iterations: {self.iterations}")
        self.logger.info(f"Price Tolerance: {self.price_tolerance_ticks} ticks")
        self.logger.info(f"Min Order Lifetime: {self.min_order_lifetime}s")
        self.logger.info(f"Rebalance Threshold: {self.rebalance_threshold}")
        self.logger.info(f"Auto Rebalance: {self.auto_rebalance}")
        self.logger.info(f"Hybrid Mode: Enabled (event-driven + periodic fallback)")
        self.logger.info("")
        self.logger.info(f"=== Cycle Mode ===")
        self.logger.info(f"Cycles: {self.cycles}")
        self.logger.info(f"Build-up Iterations: {self.build_up_iterations}")
        self.logger.info(f"Hold Time: {self.hold_time}s ({self.hold_time/60:.1f} min)")
        self.logger.info(f"Strategy: Build-up → Hold → Wind-down → Repeat")
        self.logger.info("=" * 20)

        # Initialize clients
        try:
            self.initialize_lighter_client()
            self.initialize_grvt_client()

            # Get contract info
            self.grvt_contract_id, self.grvt_tick_size = await self.get_grvt_contract_info()
            self.lighter_market_index, self.base_amount_multiplier, self.price_multiplier = self.get_lighter_market_config()

            self.logger.info(f"Contract info loaded - GRVT: {self.grvt_contract_id}, "
                             f"Lighter: {self.lighter_market_index}")
            self.logger.info(f"GRVT tick size: {self.grvt_tick_size}, "
                             f"Price tolerance: {Decimal(self.price_tolerance_ticks) * self.grvt_tick_size}")

        except Exception as e:
            self.logger.error(f"❌ Failed to initialize: {e}")
            return

        # Setup GRVT websocket
        try:
            await self.setup_grvt_websocket()
            self.logger.info("✅ GRVT WebSocket connection established")

        except Exception as e:
            self.logger.error(f"❌ Failed to setup GRVT websocket: {e}")
            return

        # Setup Lighter websocket
        try:
            self.lighter_ws_task = asyncio.create_task(self.handle_lighter_ws())
            self.logger.info("✅ Lighter WebSocket task started")

            # Wait for initial Lighter order book data with timeout
            self.logger.info("⏳ Waiting for initial Lighter order book data...")
            timeout = 10  # seconds
            start_time = time.time()
            while not self.lighter_order_book_ready and not self.stop_flag:
                if time.time() - start_time > timeout:
                    self.logger.warning(f"⚠️ Timeout waiting for Lighter WebSocket order book data after {timeout}s")
                    break
                await asyncio.sleep(0.5)

            if self.lighter_order_book_ready:
                self.logger.info("✅ Lighter WebSocket order book data received")
            else:
                self.logger.warning("⚠️ Lighter WebSocket order book not ready")

        except Exception as e:
            self.logger.error(f"❌ Failed to setup Lighter websocket: {e}")
            return

        await asyncio.sleep(5)

        # Main cycle loop
        for cycle in range(self.cycles):
            if self.stop_flag:
                break

            self.logger.info("=" * 60)
            self.logger.info(f"🔄 CYCLE {cycle + 1}/{self.cycles}")
            self.logger.info("=" * 60)

            # Phase 1: Build-up (累积仓位)
            # Determine build-up direction for this cycle (based on Lighter side)
            import random
            if self.direction == 'random':
                cycle_direction = random.choice(['long', 'short'])
            else:
                cycle_direction = self.direction

            # Lighter determines the direction, GRVT hedges opposite
            # long = Lighter buy (long), GRVT sell (short hedge)
            # short = Lighter sell (short), GRVT buy (long hedge)
            grvt_side = 'sell' if cycle_direction == 'long' else 'buy'
            lighter_side = 'buy' if cycle_direction == 'long' else 'sell'
            direction_emoji = '📈' if cycle_direction == 'long' else '📉'

            self.logger.info(f"{direction_emoji} PHASE 1: Building up {cycle_direction.upper()} position ({self.build_up_iterations} iterations)")
            self.logger.info(f"   Lighter will {lighter_side.upper()} ({cycle_direction}), GRVT will {grvt_side.upper()} (hedge)")

            for iteration in range(self.build_up_iterations):
                if self.stop_flag:
                    break

                self.logger.info("-" * 50)
                self.logger.info(f"📊 Build-up iteration {iteration + 1}/{self.build_up_iterations}")
                self.logger.info(f"   Current positions - GRVT: {self.grvt_position} | Lighter: {self.lighter_position}")
                self.logger.info("-" * 50)

                # Check and auto-rebalance if needed
                is_balanced, position_diff = await self.check_position_balance()
                if not is_balanced:
                    self.logger.warning(f"⚠️ Position imbalance detected: diff={position_diff:.4f}")
                    if self.auto_rebalance:
                        rebalance_success = await self.auto_rebalance_positions()
                        if not rebalance_success:
                            self.logger.error(f"❌ Failed to rebalance. Stopping.")
                            break
                    else:
                        self.logger.error(f"❌ Position diff too large. Stopping.")
                        break

                # Place GRVT order with hedge direction
                self.order_execution_complete = False
                self.waiting_for_lighter_fill = False
                try:
                    await self.place_grvt_post_only_order(grvt_side, self.order_quantity)
                except Exception as e:
                    self.logger.error(f"⚠️ Error placing GRVT order: {e}")
                    self.logger.error(f"⚠️ Full traceback: {traceback.format_exc()}")
                    break

                # Wait for GRVT order to fill
                grvt_filled = await self.wait_for_grvt_fill_with_fallback(self.current_grvt_order_id, timeout=180)
                if not grvt_filled:
                    self.logger.error("❌ GRVT order did not fill")
                    break

                # Place Lighter hedge order
                if self.waiting_for_lighter_fill:
                    await self.place_lighter_market_order(
                        self.current_lighter_side,
                        self.current_lighter_quantity,
                        self.current_lighter_price
                    )

            if self.stop_flag:
                break

            # Phase 2: Hold (持有仓位)
            if self.hold_time > 0:
                self.logger.info("=" * 60)
                self.logger.info(f"⏳ PHASE 2: Holding position for {self.hold_time} seconds ({self.hold_time/60:.1f} minutes)")
                self.logger.info(f"   Current positions - GRVT: {self.grvt_position} | Lighter: {self.lighter_position}")
                self.logger.info("=" * 60)

                hold_start = time.time()
                while time.time() - hold_start < self.hold_time and not self.stop_flag:
                    await asyncio.sleep(10)
                    elapsed = time.time() - hold_start
                    remaining = self.hold_time - elapsed
                    if int(elapsed) % 60 == 0:  # Log every minute
                        self.logger.info(f"⏱️  Holding... {elapsed/60:.1f} min elapsed, {remaining/60:.1f} min remaining")

            if self.stop_flag:
                break

            # Phase 3: Wind-down (平仓)
            self.logger.info("=" * 60)
            self.logger.info(f"📉 PHASE 3: Winding down position")
            self.logger.info(f"   Positions to close - GRVT: {self.grvt_position} | Lighter: {self.lighter_position}")
            self.logger.info("=" * 60)

            # Calculate how many close iterations we need
            close_iterations = int(abs(self.grvt_position) / self.order_quantity) if self.grvt_position != 0 else 0

            for iteration in range(close_iterations):
                if self.stop_flag:
                    break

                self.logger.info("-" * 50)
                self.logger.info(f"📊 Wind-down iteration {iteration + 1}/{close_iterations}")
                self.logger.info(f"   Current positions - GRVT: {self.grvt_position} | Lighter: {self.lighter_position}")
                self.logger.info("-" * 50)

                # Determine side based on current position
                if self.grvt_position > 0:
                    side = 'sell'
                    quantity = min(self.order_quantity, self.grvt_position)
                else:
                    side = 'buy'
                    quantity = min(self.order_quantity, abs(self.grvt_position))

                # Place GRVT close order
                self.order_execution_complete = False
                self.waiting_for_lighter_fill = False
                try:
                    await self.place_grvt_post_only_order(side, quantity)
                except Exception as e:
                    self.logger.error(f"⚠️ Error placing GRVT order: {e}")
                    self.logger.error(f"⚠️ Full traceback: {traceback.format_exc()}")
                    break

                # Wait for GRVT order to fill
                grvt_filled = await self.wait_for_grvt_fill_with_fallback(self.current_grvt_order_id, timeout=180)
                if not grvt_filled:
                    self.logger.error("❌ GRVT order did not fill")
                    break

                # Place Lighter hedge order
                if self.waiting_for_lighter_fill:
                    await self.place_lighter_market_order(
                        self.current_lighter_side,
                        self.current_lighter_quantity,
                        self.current_lighter_price
                    )

            # Clean up any remaining position
            if abs(self.grvt_position) > 0.001:
                self.logger.info(f"🧹 Cleaning up remaining position: {self.grvt_position}")
                side = 'sell' if self.grvt_position > 0 else 'buy'

                self.order_execution_complete = False
                self.waiting_for_lighter_fill = False
                try:
                    await self.place_grvt_post_only_order(side, abs(self.grvt_position))
                    grvt_filled = await self.wait_for_grvt_fill_with_fallback(self.current_grvt_order_id, timeout=180)

                    if grvt_filled and self.waiting_for_lighter_fill:
                        await self.place_lighter_market_order(
                            self.current_lighter_side,
                            self.current_lighter_quantity,
                            self.current_lighter_price
                        )
                except Exception as e:
                    self.logger.error(f"⚠️ Error in cleanup: {e}")

            self.logger.info("=" * 60)
            self.logger.info(f"✅ CYCLE {cycle + 1} COMPLETED")
            self.logger.info(f"   Final positions - GRVT: {self.grvt_position} | Lighter: {self.lighter_position}")
            self.logger.info("=" * 60)

        # Legacy iteration loop (kept for backward compatibility)
        iterations = 0
        while iterations < self.iterations and not self.stop_flag and self.cycles == 1 and self.hold_time == 0:
            iterations += 1
            self.logger.info("-----------------------------------------------")
            self.logger.info(f"🔄 Trading loop iteration {iterations}")
            self.logger.info("-----------------------------------------------")

            self.logger.info(f"[STEP 1] GRVT position: {self.grvt_position} | Lighter position: {self.lighter_position}")

            # Check and auto-rebalance positions if needed
            is_balanced, position_diff = await self.check_position_balance()
            if not is_balanced:
                self.logger.warning(f"⚠️ Position imbalance detected before iteration: diff={position_diff:.4f}")

                if self.auto_rebalance:
                    rebalance_success = await self.auto_rebalance_positions()
                    if not rebalance_success:
                        self.logger.error(f"❌ Failed to rebalance positions. Stopping trading.")
                        break
                else:
                    self.logger.error(f"❌ Position diff too large: {position_diff:.4f}, auto-rebalance disabled. Stopping.")
                    break

            self.order_execution_complete = False
            self.waiting_for_lighter_fill = False
            try:
                # Determine side based on some logic (for now, alternate)
                side = 'buy'
                await self.place_grvt_post_only_order(side, self.order_quantity)
            except Exception as e:
                self.logger.error(f"⚠️ Error in trading loop: {e}")
                self.logger.error(f"⚠️ Full traceback: {traceback.format_exc()}")
                break

            # Wait for GRVT order to fill using hybrid mode
            grvt_filled = await self.wait_for_grvt_fill_with_fallback(self.current_grvt_order_id, timeout=180)

            if not grvt_filled:
                self.logger.error("❌ GRVT order did not fill, skipping hedge")
                break

            # GRVT filled, place Lighter hedge order
            if self.waiting_for_lighter_fill:
                await self.place_lighter_market_order(
                    self.current_lighter_side,
                    self.current_lighter_quantity,
                    self.current_lighter_price
                )

            if self.stop_flag:
                break

            # Close position
            self.logger.info(f"[STEP 2] GRVT position: {self.grvt_position} | Lighter position: {self.lighter_position}")
            self.order_execution_complete = False
            self.waiting_for_lighter_fill = False
            try:
                # Determine side based on some logic (for now, alternate)
                side = 'sell'
                await self.place_grvt_post_only_order(side, self.order_quantity)
            except Exception as e:
                self.logger.error(f"⚠️ Error in trading loop: {e}")
                self.logger.error(f"⚠️ Full traceback: {traceback.format_exc()}")
                break

            # Wait for GRVT order to fill using hybrid mode
            grvt_filled = await self.wait_for_grvt_fill_with_fallback(self.current_grvt_order_id, timeout=180)

            if not grvt_filled:
                self.logger.error("❌ GRVT order did not fill, skipping hedge")
                break

            # GRVT filled, place Lighter hedge order
            if self.waiting_for_lighter_fill:
                await self.place_lighter_market_order(
                    self.current_lighter_side,
                    self.current_lighter_quantity,
                    self.current_lighter_price
                )

            # Close remaining position
            self.logger.info(f"[STEP 3] GRVT position: {self.grvt_position} | Lighter position: {self.lighter_position}")
            self.order_execution_complete = False
            self.waiting_for_lighter_fill = False
            if self.grvt_position == 0:
                continue
            elif self.grvt_position > 0:
                side = 'sell'
            else:
                side = 'buy'

            try:
                # Determine side based on some logic (for now, alternate)
                await self.place_grvt_post_only_order(side, abs(self.grvt_position))
            except Exception as e:
                self.logger.error(f"⚠️ Error in trading loop: {e}")
                self.logger.error(f"⚠️ Full traceback: {traceback.format_exc()}")
                break

            # Wait for GRVT order to fill using hybrid mode
            grvt_filled = await self.wait_for_grvt_fill_with_fallback(self.current_grvt_order_id, timeout=180)

            if not grvt_filled:
                self.logger.error("❌ GRVT order did not fill in STEP 3")
                break

            # GRVT filled, place Lighter hedge order
            if self.waiting_for_lighter_fill:
                await self.place_lighter_market_order(
                    self.current_lighter_side,
                    self.current_lighter_quantity,
                    self.current_lighter_price
                )

    async def run(self):
        """Run the hedge bot."""
        self.setup_signal_handlers()

        try:
            await self.trading_loop()
        except KeyboardInterrupt:
            self.logger.info("\n🛑 Received interrupt signal...")
        finally:
            self.logger.info("🔄 Cleaning up...")
            self.shutdown()


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Trading bot for GRVT and Lighter')
    parser.add_argument('--exchange', type=str,
                        help='Exchange')
    parser.add_argument('--ticker', type=str, default='BTC',
                        help='Ticker symbol (default: BTC)')
    parser.add_argument('--size', type=str,
                        help='Number of tokens to buy/sell per order')
    parser.add_argument('--iter', type=int,
                        help='Number of iterations to run')
    parser.add_argument('--fill-timeout', type=int, default=5,
                        help='Timeout in seconds for maker order fills (default: 5)')
    parser.add_argument('--price-tolerance', type=int, default=3,
                        help='Price tolerance in ticks before canceling order (default: 3)')
    parser.add_argument('--min-order-lifetime', type=int, default=30,
                        help='Minimum order lifetime in seconds before considering cancellation (default: 30)')
    parser.add_argument('--rebalance-threshold', type=float, default=0.15,
                        help='Position imbalance threshold before triggering rebalance (default: 0.15)')
    parser.add_argument('--no-auto-rebalance', action='store_true',
                        help='Disable automatic position rebalancing (default: enabled)')
    parser.add_argument('--build-up-iterations', type=int, default=None,
                        help='Number of iterations to build up position before holding (default: same as --iter)')
    parser.add_argument('--hold-time', type=int, default=0,
                        help='Time in seconds to hold position (default: 0, e.g., 1800 for 30 min)')
    parser.add_argument('--cycles', type=int, default=None,
                        help='Number of build-hold-winddown cycles to run (default: 1)')

    return parser.parse_args()
