"""
交易执行器 - 负责调用exchange客户端执行交易。

职责：
1. 调用Exchange A和Exchange B的客户端方法
2. 等待订单成交
3. 返回执行结果
4. 不包含业务逻辑判断
"""

import asyncio
import logging
from decimal import Decimal
from typing import NamedTuple, Optional

from hedge.rebalancer import TradeAction
from hedge.safety_checker import PositionState, PendingOrdersInfo


class ExecutionResult(NamedTuple):
    """执行结果"""
    success: bool
    exchange_a_order_id: Optional[str] = None
    exchange_a_price: Optional[Decimal] = None
    exchange_b_order_id: Optional[str] = None
    exchange_b_price: Optional[Decimal] = None
    error: Optional[str] = None


class TradingExecutor:
    """
    交易执行器。

    封装所有与交易所的交互，但不包含业务逻辑。
    """

    def __init__(self, exchange_a_client, exchange_b_client, logger=None):
        """
        初始化执行器。

        Args:
            exchange_a_client: 交易所A客户端 (主交易所，使用做市单)
            exchange_b_client: 交易所B客户端 (对冲交易所，使用市价单)
            logger: 日志记录器
        """
        self.exchange_a = exchange_a_client
        self.exchange_b = exchange_b_client
        self.logger = logger or logging.getLogger(__name__)

        # 获取交易所名称用于日志
        self.exchange_a_name = exchange_a_client.get_exchange_name().upper()
        self.exchange_b_name = exchange_b_client.get_exchange_name().upper()

    async def get_positions(self) -> PositionState:
        """
        从交易所获取当前真实仓位。

        Returns:
            PositionState
        """
        exchange_a_pos = await self.exchange_a.get_account_positions()
        exchange_b_pos = await self.exchange_b.get_account_positions()

        return PositionState(
            exchange_a_position=exchange_a_pos,
            exchange_b_position=exchange_b_pos
        )

    async def get_pending_orders(self) -> PendingOrdersInfo:
        """
        从交易所获取未成交订单数量。

        Returns:
            PendingOrdersInfo
        """
        try:
            # 获取GRVT未成交订单
            exchange_a_orders = await self.exchange_a.get_active_orders(
                contract_id=self.exchange_a.config.contract_id
            )
            exchange_a_pending_count = len(exchange_a_orders)
        except Exception as e:
            self.logger.error(f"Failed to get Exchange A pending orders: {e}")
            exchange_a_pending_count = 0

        try:
            # 获取Lighter未成交订单
            exchange_b_orders = await self.exchange_b.get_active_orders(
                contract_id=self.exchange_b.config.contract_id
            )
            exchange_b_pending_count = len(exchange_b_orders)
        except Exception as e:
            self.logger.error(f"Failed to get Exchange B pending orders: {e}")
            exchange_b_pending_count = 0

        return PendingOrdersInfo(
            exchange_a_pending_count=exchange_a_pending_count,
            exchange_b_pending_count=exchange_b_pending_count
        )

    async def execute_trade(
        self,
        action: TradeAction,
        quantity: Decimal,
        wait_for_fill: bool = True,
        fill_timeout: int = 30
    ) -> ExecutionResult:
        """
        执行交易指令。

        Args:
            action: 交易动作
            quantity: 交易数量
            wait_for_fill: 是否等待GRVT订单成交
            fill_timeout: 等待成交的超时时间（秒）

        Returns:
            ExecutionResult
        """
        self.logger.info(f"🔧 Executing action: {action.value}")

        if action == TradeAction.HOLD:
            return ExecutionResult(success=True)

        if action == TradeAction.BUILD_LONG:
            return await self._execute_build_long(quantity, wait_for_fill, fill_timeout)

        if action == TradeAction.CLOSE_LONG:
            return await self._execute_close_long(quantity, wait_for_fill, fill_timeout)

        if action == TradeAction.BUILD_SHORT:
            return await self._execute_build_short(quantity, wait_for_fill, fill_timeout)

        if action == TradeAction.CLOSE_SHORT:
            return await self._execute_close_short(quantity, wait_for_fill, fill_timeout)

        return ExecutionResult(success=False, error=f"Unknown action: {action}")

    async def _execute_build_long(
        self, quantity: Decimal, wait_for_fill: bool, timeout: int
    ) -> ExecutionResult:
        """
        建多仓：GRVT买入 + Lighter卖出。
        """
        try:
            # 1. GRVT买入（做市单）
            self.logger.info(f"Placing Exchange A buy order: {quantity}")
            exchange_a_result = await self.exchange_a.place_open_order(
                contract_id=self.exchange_a.config.contract_id,
                quantity=quantity,
                direction="buy"
            )

            if not exchange_a_result.success:
                return ExecutionResult(
                    success=False,
                    error=f"Exchange A order failed: {exchange_a_result.error_message}"
                )

            self.logger.info(f"✓ Exchange A buy order placed: {exchange_a_result.order_id} @ {exchange_a_result.price}")

            # 2. 等待GRVT订单成交
            if wait_for_fill:
                self.logger.info("Waiting for Exchange A order to fill...")
                filled = await self._wait_for_fill(exchange_a_result.order_id, timeout)

                if not filled:
                    self.logger.warning("Exchange A order not filled, cancelling...")
                    await self.exchange_a.cancel_order(exchange_a_result.order_id)
                    return ExecutionResult(
                        success=False,
                        error="Exchange A order not filled within timeout"
                    )

                self.logger.info("✓ Exchange A order filled")

            # 3. Lighter卖出（对冲）
            self.logger.info(f"Placing Exchange B sell order: {quantity}")
            exchange_b_result = await self.exchange_b.place_open_order(
                contract_id=self.exchange_b.config.contract_id,
                quantity=quantity,
                direction="sell"
            )

            if not exchange_b_result.success:
                return ExecutionResult(
                    success=False,
                    grvt_order_id=exchange_a_result.order_id,
                    grvt_price=exchange_a_result.price,
                    error=f"Exchange B order failed: {exchange_b_result.error_message}"
                )

            self.logger.info(f"✓ Exchange B sell order placed @ {exchange_b_result.price}")

            return ExecutionResult(
                success=True,
                grvt_order_id=exchange_a_result.order_id,
                grvt_price=exchange_a_result.price,
                lighter_order_id=exchange_b_result.order_id,
                lighter_price=exchange_b_result.price
            )

        except Exception as e:
            self.logger.error(f"Error executing build long: {e}")
            return ExecutionResult(success=False, error=str(e))

    async def _execute_close_long(
        self, quantity: Decimal, wait_for_fill: bool, timeout: int
    ) -> ExecutionResult:
        """
        平多仓：GRVT卖出 + Lighter买入。
        """
        try:
            # 1. GRVT卖出（做市单）
            self.logger.info(f"Placing Exchange A sell order: {quantity}")
            exchange_a_result = await self.exchange_a.place_open_order(
                contract_id=self.exchange_a.config.contract_id,
                quantity=quantity,
                direction="sell"
            )

            if not exchange_a_result.success:
                return ExecutionResult(
                    success=False,
                    error=f"Exchange A order failed: {exchange_a_result.error_message}"
                )

            self.logger.info(f"✓ Exchange A sell order placed: {exchange_a_result.order_id} @ {exchange_a_result.price}")

            # 2. 等待成交
            if wait_for_fill:
                self.logger.info("Waiting for Exchange A order to fill...")
                filled = await self._wait_for_fill(exchange_a_result.order_id, timeout)

                if not filled:
                    self.logger.warning("Exchange A order not filled, cancelling...")
                    await self.exchange_a.cancel_order(exchange_a_result.order_id)
                    return ExecutionResult(
                        success=False,
                        error="Exchange A order not filled within timeout"
                    )

                self.logger.info("✓ Exchange A order filled")

            # 3. Lighter买入（对冲）
            self.logger.info(f"Placing Exchange B buy order: {quantity}")
            exchange_b_result = await self.exchange_b.place_open_order(
                contract_id=self.exchange_b.config.contract_id,
                quantity=quantity,
                direction="buy"
            )

            if not exchange_b_result.success:
                return ExecutionResult(
                    success=False,
                    grvt_order_id=exchange_a_result.order_id,
                    grvt_price=exchange_a_result.price,
                    error=f"Exchange B order failed: {exchange_b_result.error_message}"
                )

            self.logger.info(f"✓ Exchange B buy order placed @ {exchange_b_result.price}")

            return ExecutionResult(
                success=True,
                grvt_order_id=exchange_a_result.order_id,
                grvt_price=exchange_a_result.price,
                lighter_order_id=exchange_b_result.order_id,
                lighter_price=exchange_b_result.price
            )

        except Exception as e:
            self.logger.error(f"Error executing close long: {e}")
            return ExecutionResult(success=False, error=str(e))

    async def _execute_build_short(
        self, quantity: Decimal, wait_for_fill: bool, timeout: int
    ) -> ExecutionResult:
        """
        Rebalance专用：Lighter卖出（市价单立即成交）。
        用于减少Lighter空头仓位，增加净多头。
        """
        try:
            self.logger.info(f"Rebalancing: Lighter sell {quantity}")
            exchange_b_result = await self.exchange_b.place_open_order(
                contract_id=self.exchange_b.config.contract_id,
                quantity=quantity,
                direction="sell"
            )

            if not exchange_b_result.success:
                return ExecutionResult(
                    success=False,
                    error=f"Exchange B rebalance sell failed: {exchange_b_result.error_message}"
                )

            self.logger.info(f"✓ Lighter rebalance sell @ {exchange_b_result.price}")

            return ExecutionResult(
                success=True,
                lighter_order_id=exchange_b_result.order_id,
                lighter_price=exchange_b_result.price
            )

        except Exception as e:
            self.logger.error(f"Error executing rebalance sell: {e}")
            return ExecutionResult(success=False, error=str(e))

    async def _execute_close_short(
        self, quantity: Decimal, wait_for_fill: bool, timeout: int
    ) -> ExecutionResult:
        """
        Rebalance专用：Lighter买入（市价单立即成交）。
        用于增加Lighter空头仓位，减少净多头。
        """
        try:
            self.logger.info(f"Rebalancing: Lighter buy {quantity}")
            exchange_b_result = await self.exchange_b.place_open_order(
                contract_id=self.exchange_b.config.contract_id,
                quantity=quantity,
                direction="buy"
            )

            if not exchange_b_result.success:
                return ExecutionResult(
                    success=False,
                    error=f"Exchange B rebalance buy failed: {exchange_b_result.error_message}"
                )

            self.logger.info(f"✓ Lighter rebalance buy @ {exchange_b_result.price}")

            return ExecutionResult(
                success=True,
                lighter_order_id=exchange_b_result.order_id,
                lighter_price=exchange_b_result.price
            )

        except Exception as e:
            self.logger.error(f"Error executing rebalance buy: {e}")
            return ExecutionResult(success=False, error=str(e))

    async def _wait_for_fill(self, order_id: str, timeout: int) -> bool:
        """
        等待GRVT订单成交。

        Args:
            order_id: 订单ID
            timeout: 超时时间（秒）

        Returns:
            bool: 是否成交
        """
        import time
        start = time.time()

        while time.time() - start < timeout:
            try:
                order_info = await self.exchange_a.get_order_info(order_id=order_id)

                if order_info and order_info.status == 'FILLED':
                    return True

                if order_info and order_info.status in ['CANCELLED', 'REJECTED']:
                    return False

                await asyncio.sleep(0.5)

            except Exception as e:
                self.logger.debug(f"Error checking order status: {e}")
                await asyncio.sleep(1)

        return False

    async def cancel_all_orders(self):
        """取消所有未成交订单"""
        try:
            self.logger.info("Cancelling all orders...")
            await self.exchange_a.cancel_all_orders()
            await self.exchange_b.cancel_all_orders()
            self.logger.info("✓ All orders cancelled")
        except Exception as e:
            self.logger.error(f"Error cancelling orders: {e}")
