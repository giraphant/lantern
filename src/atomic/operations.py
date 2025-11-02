"""
原子操作层 - 只负责单个交易所的单个操作

设计原则:
1. 每个类只操作一个交易所
2. 不知道其他交易所的存在
3. 负责适配器层的数据转换（原始格式 → 标准格式）
"""

import logging
from decimal import Decimal
from typing import Optional, List
from datetime import datetime

from atomic.models import (
    ExchangeIdentifier,
    Symbol,
    Position,
    FundingRate,
    Order,
    Market,
    TradeLeg
)
from exchanges.base import BaseExchangeClient, OrderResult, OrderInfo


class AtomicQueryer:
    """
    原子查询器 - 只负责单个交易所的数据查询

    职责：
    - 调用交易所适配器
    - 转换原始数据为标准化模型
    - 不包含任何业务逻辑
    """

    def __init__(self, exchange_client: BaseExchangeClient, symbol: Symbol):
        """
        Args:
            exchange_client: 交易所适配器实例
            symbol: 要查询的交易对
        """
        self.client = exchange_client
        self.symbol = symbol
        self.exchange_id = ExchangeIdentifier(name=exchange_client.get_exchange_name())
        self.logger = logging.getLogger(f"{__name__}.{self.exchange_id}")

    async def get_position(self) -> Position:
        """
        查询单个仓位（原子操作）

        Returns:
            Position: 标准化的仓位对象
        """
        try:
            # 调用适配器层
            raw_position = await self.client.get_account_positions()

            # 转换为标准化Position
            quantity = abs(raw_position)

            if raw_position > 0:
                side = "long"
            elif raw_position < 0:
                side = "short"
            else:
                side = "none"

            return Position(
                exchange=self.exchange_id,
                symbol=self.symbol,
                quantity=quantity,
                side=side,
                timestamp=datetime.utcnow()
            )

        except Exception as e:
            self.logger.error(f"Failed to get position: {e}")
            # 返回空仓位而不是抛出异常
            return Position(
                exchange=self.exchange_id,
                symbol=self.symbol,
                quantity=Decimal(0),
                side="none"
            )

    async def get_funding_rate(self) -> FundingRate:
        """
        查询单个费率（原子操作）

        Returns:
            FundingRate: 标准化的费率对象
        """
        try:
            # 需要contract_id - 从client的config获取
            contract_id = self.client.config.contract_id

            # 调用适配器层
            rate = await self.client.get_funding_rate(contract_id)
            interval = await self.client.get_funding_interval_hours(contract_id)

            return FundingRate(
                exchange=self.exchange_id,
                symbol=self.symbol,
                rate=rate,
                interval_hours=interval,
                timestamp=datetime.utcnow()
            )

        except Exception as e:
            self.logger.error(f"Failed to get funding rate: {e}")
            # 返回0费率而不是抛出异常
            return FundingRate(
                exchange=self.exchange_id,
                symbol=self.symbol,
                rate=Decimal(0),
                interval_hours=8  # 默认8小时
            )

    async def get_market(self) -> Market:
        """
        查询市场数据（原子操作）

        Returns:
            Market: 标准化的市场数据
        """
        try:
            contract_id = self.client.config.contract_id

            # 调用适配器层获取最佳买卖价
            bid, ask = await self.client.fetch_bbo_prices(contract_id)

            return Market(
                exchange=self.exchange_id,
                symbol=self.symbol,
                best_bid=bid,
                best_ask=ask,
                tick_size=self.client.config.tick_size if hasattr(self.client.config, 'tick_size') else None,
                timestamp=datetime.utcnow()
            )

        except Exception as e:
            self.logger.error(f"Failed to get market data: {e}")
            return Market(
                exchange=self.exchange_id,
                symbol=self.symbol
            )

    async def get_active_orders(self) -> List[Order]:
        """
        查询活跃订单（原子操作）

        Returns:
            List[Order]: 标准化的订单列表
        """
        try:
            contract_id = self.client.config.contract_id

            # 调用适配器层
            raw_orders = await self.client.get_active_orders(contract_id)

            # 转换为标准化Order
            orders = []
            for raw_order in raw_orders:
                order = self._convert_order_info(raw_order)
                orders.append(order)

            return orders

        except Exception as e:
            self.logger.error(f"Failed to get active orders: {e}")
            return []

    def _convert_order_info(self, order_info: OrderInfo) -> Order:
        """
        转换OrderInfo为标准化Order

        Args:
            order_info: 适配器层返回的订单信息

        Returns:
            Order: 标准化订单
        """
        # 标准化状态
        status_mapping = {
            "OPEN": "open",
            "NEW": "open",
            "FILLED": "filled",
            "CANCELLED": "cancelled",
            "CANCELED": "cancelled",  # Binance拼写
            "REJECTED": "rejected",
            "PENDING": "pending"
        }
        status = status_mapping.get(order_info.status, "open")

        return Order(
            exchange=self.exchange_id,
            symbol=self.symbol,
            order_id=order_info.order_id,
            side=order_info.side,
            quantity=order_info.size,
            price=order_info.price,
            order_type="limit",  # 大部分是limit单
            status=status,
            filled_quantity=order_info.filled_size,
            created_at=order_info.created_time or datetime.utcnow(),
            updated_at=order_info.filled_time or datetime.utcnow()
        )


class AtomicTrader:
    """
    原子交易执行器 - 只负责单个交易所的单笔交易

    职责：
    - 执行交易指令
    - 等待订单状态
    - 转换结果为标准格式
    - 不包含任何策略逻辑
    """

    def __init__(self, exchange_client: BaseExchangeClient, symbol: Symbol):
        """
        Args:
            exchange_client: 交易所适配器实例
            symbol: 要交易的交易对
        """
        self.client = exchange_client
        self.symbol = symbol
        self.exchange_id = ExchangeIdentifier(name=exchange_client.get_exchange_name())
        self.logger = logging.getLogger(f"{__name__}.{self.exchange_id}")

    async def execute_trade(
        self,
        side: str,
        quantity: Decimal,
        order_type: str = "post_only",
        price: Optional[Decimal] = None,
        wait_for_fill: bool = False,
        timeout: int = 30
    ) -> Order:
        """
        执行单笔交易（原子操作）

        Args:
            side: "buy" or "sell"
            quantity: 交易数量
            order_type: "market", "limit", "post_only"
            price: 限价单价格（可选）
            wait_for_fill: 是否等待成交
            timeout: 等待超时时间

        Returns:
            Order: 标准化的订单对象
        """
        try:
            contract_id = self.client.config.contract_id

            # 根据order_type选择不同的下单方法
            if order_type == "post_only":
                # 使用适配器的place_open_order（做市单）
                result = await self.client.place_open_order(
                    contract_id=contract_id,
                    quantity=quantity,
                    direction=side  # "buy" or "sell"
                )
            else:
                # 其他类型暂不支持，使用默认方法
                result = await self.client.place_open_order(
                    contract_id=contract_id,
                    quantity=quantity,
                    direction=side
                )

            # 转换为标准化Order
            order = self._convert_order_result(result, side, quantity, order_type)

            self.logger.info(f"Order placed: {order.order_id} - {side} {quantity} @ {order.price}")

            return order

        except Exception as e:
            self.logger.error(f"Failed to execute trade: {e}")
            # 返回失败的订单
            return Order(
                exchange=self.exchange_id,
                symbol=self.symbol,
                order_id="",
                side=side,
                quantity=quantity,
                price=price,
                order_type=order_type,
                status="rejected"
            )

    async def cancel_order(self, order_id: str) -> bool:
        """
        取消订单（原子操作）

        Args:
            order_id: 订单ID

        Returns:
            bool: 是否成功取消
        """
        try:
            result = await self.client.cancel_order(order_id)
            return result.success
        except Exception as e:
            self.logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    async def cancel_all_orders(self) -> int:
        """
        取消所有订单（原子操作）

        Returns:
            int: 取消的订单数量
        """
        try:
            await self.client.cancel_all_orders()
            self.logger.info("All orders cancelled")
            return 0  # 无法获取准确数量
        except Exception as e:
            self.logger.error(f"Failed to cancel all orders: {e}")
            return 0

    def _convert_order_result(
        self,
        result: OrderResult,
        side: str,
        quantity: Decimal,
        order_type: str
    ) -> Order:
        """
        转换OrderResult为标准化Order

        Args:
            result: 适配器层返回的结果
            side: 交易方向
            quantity: 数量
            order_type: 订单类型

        Returns:
            Order: 标准化订单
        """
        # 标准化状态
        status_mapping = {
            "OPEN": "open",
            "NEW": "open",
            "FILLED": "filled",
            "CANCELLED": "cancelled",
            "CANCELED": "cancelled",
            "REJECTED": "rejected",
            "PENDING": "pending"
        }

        if not result.success:
            status = "rejected"
        else:
            status = status_mapping.get(result.status, "open")

        return Order(
            exchange=self.exchange_id,
            symbol=self.symbol,
            order_id=result.order_id or "",
            side=side,
            quantity=quantity,
            price=result.price,
            order_type=order_type,
            status=status,
            filled_quantity=result.filled_size or Decimal(0)
        )
