"""
交易执行器 - 负责调用exchange客户端执行交易。

职责：
1. 调用GRVT和Lighter的客户端方法
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
    grvt_order_id: Optional[str] = None
    grvt_price: Optional[Decimal] = None
    lighter_order_id: Optional[str] = None
    lighter_price: Optional[Decimal] = None
    error: Optional[str] = None


class TradingExecutor:
    """
    交易执行器。

    封装所有与交易所的交互，但不包含业务逻辑。
    """

    def __init__(self, grvt_client, lighter_client, logger=None):
        """
        初始化执行器。

        Args:
            grvt_client: GRVT交易所客户端
            lighter_client: Lighter交易所客户端
            logger: 日志记录器
        """
        self.grvt = grvt_client
        self.lighter = lighter_client
        self.logger = logger or logging.getLogger(__name__)

    async def get_positions(self) -> PositionState:
        """
        从交易所获取当前真实仓位。

        Returns:
            PositionState
        """
        grvt_pos = await self.grvt.get_account_positions()
        lighter_pos = await self.lighter.get_account_positions()

        return PositionState(
            grvt_position=grvt_pos,
            lighter_position=lighter_pos
        )

    async def get_pending_orders(self) -> PendingOrdersInfo:
        """
        从交易所获取未成交订单数量。

        Returns:
            PendingOrdersInfo
        """
        try:
            # 获取GRVT未成交订单
            grvt_orders = await self.grvt.get_active_orders(
                contract_id=self.grvt.config.contract_id
            )
            grvt_pending_count = len(grvt_orders)
        except Exception as e:
            self.logger.error(f"Failed to get GRVT pending orders: {e}")
            grvt_pending_count = 0

        try:
            # 获取Lighter未成交订单
            lighter_orders = await self.lighter.get_active_orders(
                contract_id=self.lighter.config.contract_id
            )
            lighter_pending_count = len(lighter_orders)
        except Exception as e:
            self.logger.error(f"Failed to get Lighter pending orders: {e}")
            lighter_pending_count = 0

        return PendingOrdersInfo(
            grvt_pending_count=grvt_pending_count,
            lighter_pending_count=lighter_pending_count
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
            self.logger.info(f"Placing GRVT buy order: {quantity}")
            grvt_result = await self.grvt.place_open_order(
                contract_id=self.grvt.config.contract_id,
                quantity=quantity,
                direction="buy"
            )

            if not grvt_result.success:
                return ExecutionResult(
                    success=False,
                    error=f"GRVT order failed: {grvt_result.error_message}"
                )

            self.logger.info(f"✓ GRVT buy order placed: {grvt_result.order_id} @ {grvt_result.price}")

            # 2. 等待GRVT订单成交
            if wait_for_fill:
                self.logger.info("Waiting for GRVT order to fill...")
                filled = await self._wait_for_fill(grvt_result.order_id, timeout)

                if not filled:
                    self.logger.warning("GRVT order not filled, cancelling...")
                    await self.grvt.cancel_order(grvt_result.order_id)
                    return ExecutionResult(
                        success=False,
                        error="GRVT order not filled within timeout"
                    )

                self.logger.info("✓ GRVT order filled")

            # 3. Lighter卖出（对冲）
            self.logger.info(f"Placing Lighter sell order: {quantity}")
            lighter_result = await self.lighter.place_open_order(
                contract_id=self.lighter.config.contract_id,
                quantity=quantity,
                direction="sell"
            )

            if not lighter_result.success:
                return ExecutionResult(
                    success=False,
                    grvt_order_id=grvt_result.order_id,
                    grvt_price=grvt_result.price,
                    error=f"Lighter order failed: {lighter_result.error_message}"
                )

            self.logger.info(f"✓ Lighter sell order placed @ {lighter_result.price}")

            return ExecutionResult(
                success=True,
                grvt_order_id=grvt_result.order_id,
                grvt_price=grvt_result.price,
                lighter_order_id=lighter_result.order_id,
                lighter_price=lighter_result.price
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
            self.logger.info(f"Placing GRVT sell order: {quantity}")
            grvt_result = await self.grvt.place_open_order(
                contract_id=self.grvt.config.contract_id,
                quantity=quantity,
                direction="sell"
            )

            if not grvt_result.success:
                return ExecutionResult(
                    success=False,
                    error=f"GRVT order failed: {grvt_result.error_message}"
                )

            self.logger.info(f"✓ GRVT sell order placed: {grvt_result.order_id} @ {grvt_result.price}")

            # 2. 等待成交
            if wait_for_fill:
                self.logger.info("Waiting for GRVT order to fill...")
                filled = await self._wait_for_fill(grvt_result.order_id, timeout)

                if not filled:
                    self.logger.warning("GRVT order not filled, cancelling...")
                    await self.grvt.cancel_order(grvt_result.order_id)
                    return ExecutionResult(
                        success=False,
                        error="GRVT order not filled within timeout"
                    )

                self.logger.info("✓ GRVT order filled")

            # 3. Lighter买入（对冲）
            self.logger.info(f"Placing Lighter buy order: {quantity}")
            lighter_result = await self.lighter.place_open_order(
                contract_id=self.lighter.config.contract_id,
                quantity=quantity,
                direction="buy"
            )

            if not lighter_result.success:
                return ExecutionResult(
                    success=False,
                    grvt_order_id=grvt_result.order_id,
                    grvt_price=grvt_result.price,
                    error=f"Lighter order failed: {lighter_result.error_message}"
                )

            self.logger.info(f"✓ Lighter buy order placed @ {lighter_result.price}")

            return ExecutionResult(
                success=True,
                grvt_order_id=grvt_result.order_id,
                grvt_price=grvt_result.price,
                lighter_order_id=lighter_result.order_id,
                lighter_price=lighter_result.price
            )

        except Exception as e:
            self.logger.error(f"Error executing close long: {e}")
            return ExecutionResult(success=False, error=str(e))

    async def _execute_build_short(
        self, quantity: Decimal, wait_for_fill: bool, timeout: int
    ) -> ExecutionResult:
        """
        建空仓：GRVT卖出 + Lighter买入。
        """
        # 和 close_long 逻辑相同
        return await self._execute_close_long(quantity, wait_for_fill, timeout)

    async def _execute_close_short(
        self, quantity: Decimal, wait_for_fill: bool, timeout: int
    ) -> ExecutionResult:
        """
        平空仓：GRVT买入 + Lighter卖出。
        """
        # 和 build_long 逻辑相同
        return await self._execute_build_long(quantity, wait_for_fill, timeout)

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
                order_info = await self.grvt.get_order_info(order_id=order_id)

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
            await self.grvt.cancel_all_orders()
            await self.lighter.cancel_all_orders()
            self.logger.info("✓ All orders cancelled")
        except Exception as e:
            self.logger.error(f"Error cancelling orders: {e}")
