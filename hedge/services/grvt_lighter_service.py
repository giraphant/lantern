"""
GRVT-Lighter对冲服务实现。

使用GRVT作为做市商（post-only），Lighter作为吃单商（market taker）。
"""

import asyncio
import logging
from decimal import Decimal
from typing import Optional, Dict, Any

from hedge.services.hedge_service import (
    HedgeService, HedgePosition, HedgeResult, HedgeLeg, OrderSide
)


class GrvtLighterHedgeService(HedgeService):
    """
    GRVT-Lighter对冲服务实现。

    直接使用现有的交易所客户端，不重复实现已有功能。
    """

    def __init__(
        self,
        grvt_client,
        lighter_client,
        config,
        logger: Optional[logging.Logger] = None
    ):
        """
        初始化对冲服务。

        Args:
            grvt_client: GRVT交易所客户端（来自exchanges/grvt.py）
            lighter_client: Lighter客户端（来自lighter/signer_client.py）
            config: 配置对象
            logger: 日志记录器
        """
        self.grvt = grvt_client
        self.lighter = lighter_client
        self.config = config
        self.logger = logger or logging.getLogger(__name__)

        # 从配置中提取关键参数
        self.symbol = config.symbol
        self.order_quantity = Decimal(str(config.order_quantity))
        self.rebalance_tolerance = Decimal(str(config.rebalance_tolerance))
        self.max_position = Decimal(str(config.max_position))

        # Lighter市场参数
        self.lighter_market_index = 0  # BTC market
        self.lighter_base_multiplier = 10**9  # 1 BTC = 10^9 base units
        self.lighter_price_multiplier = 10**9  # Price precision

    async def initialize(self) -> None:
        """初始化服务，建立连接"""
        try:
            # GRVT使用WebSocket连接
            if hasattr(self.grvt, 'connect'):
                await self.grvt.connect()
                self.logger.info("GRVT WebSocket connected")

            # Lighter已经在初始化时连接
            self.logger.info("Hedge service initialized")

        except Exception as e:
            self.logger.error(f"Failed to initialize hedge service: {e}")
            raise

    async def get_positions(self) -> HedgePosition:
        """
        获取当前对冲仓位。

        直接调用现有的交易所方法，不重新实现。
        """
        try:
            # 并行获取两个交易所的仓位
            grvt_task = self._get_grvt_position()
            lighter_task = self._get_lighter_position()

            grvt_pos, lighter_pos = await asyncio.gather(
                grvt_task, lighter_task, return_exceptions=True
            )

            # 处理异常
            if isinstance(grvt_pos, Exception):
                self.logger.error(f"Failed to get GRVT position: {grvt_pos}")
                grvt_pos = Decimal("0")

            if isinstance(lighter_pos, Exception):
                self.logger.error(f"Failed to get Lighter position: {lighter_pos}")
                lighter_pos = Decimal("0")

            position = HedgePosition(
                maker_position=grvt_pos,
                taker_position=lighter_pos
            )

            self.logger.debug(f"Current positions: {position}")
            return position

        except Exception as e:
            self.logger.error(f"Failed to get positions: {e}")
            raise

    async def _get_grvt_position(self) -> Decimal:
        """获取GRVT仓位 - 使用现有方法"""
        positions = await self.grvt.fetch_positions()
        for pos in positions:
            if pos.get('symbol') == self.symbol:
                # 注意：不要用abs()，需要保留符号
                return Decimal(str(pos.get('size', 0)))
        return Decimal("0")

    async def _get_lighter_position(self) -> Decimal:
        """获取Lighter仓位 - 使用现有方法"""
        positions = self.lighter.query_positions()
        if positions and len(positions) > 0:
            # BTC在索引0
            btc_position = positions[0]
            # 从base units转换到BTC
            return Decimal(str(btc_position)) / Decimal(str(self.lighter_base_multiplier))
        return Decimal("0")

    async def execute_hedge_cycle(self, direction: str, quantity: Decimal) -> HedgeResult:
        """
        执行一个对冲周期。

        策略：
        1. GRVT下post-only做市单（获得手续费返佣）
        2. Lighter下市价单对冲（支付手续费）
        """
        result = HedgeResult(success=False)

        try:
            # 确定每边的方向
            if direction == "long":
                grvt_side = "sell"  # GRVT做空
                lighter_is_ask = False  # Lighter做多（买入）
            else:  # short
                grvt_side = "buy"  # GRVT做多
                lighter_is_ask = True  # Lighter做空（卖出）

            # Step 1: 在GRVT下post-only订单
            self.logger.info(f"Placing GRVT {grvt_side} order for {quantity}")
            grvt_result = await self._place_grvt_order(grvt_side, quantity)

            if not grvt_result.success:
                result.maker_leg = grvt_result
                result.error = f"GRVT order failed: {grvt_result.error}"
                return result

            result.maker_leg = grvt_result

            # Step 2: 在Lighter下对冲订单
            self.logger.info(f"Placing Lighter {'sell' if lighter_is_ask else 'buy'} order for {quantity}")
            lighter_result = await self._place_lighter_order(lighter_is_ask, quantity)

            if not lighter_result.success:
                # Lighter失败，尝试取消GRVT订单
                self.logger.warning("Lighter order failed, attempting to cancel GRVT order")
                if grvt_result.order_id:
                    try:
                        await self.grvt.cancel_order(grvt_result.order_id)
                        self.logger.info("GRVT order cancelled successfully")
                    except Exception as e:
                        self.logger.error(f"Failed to cancel GRVT order: {e}")

                result.taker_leg = lighter_result
                result.error = f"Lighter order failed: {lighter_result.error}"
                return result

            result.taker_leg = lighter_result

            # Step 3: 获取更新后的仓位
            await asyncio.sleep(0.5)  # 给交易所一点时间更新
            result.position_after = await self.get_positions()

            result.success = True
            self.logger.info(f"Hedge cycle completed: {result}")

            return result

        except Exception as e:
            self.logger.error(f"Hedge cycle failed: {e}")
            result.error = str(e)
            return result

    async def _place_grvt_order(self, side: str, quantity: Decimal) -> HedgeLeg:
        """在GRVT下post-only订单 - 使用现有方法"""
        try:
            # 使用现有的place_post_only_order方法
            order = await self.grvt.place_post_only_order(
                side=side,
                quantity=float(quantity),
                offset_bps=self.config.spread_bps
            )

            if order and order.get('status') != 'REJECTED':
                return HedgeLeg(
                    success=True,
                    exchange="GRVT",
                    side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
                    quantity=quantity,
                    price=Decimal(str(order.get('price', 0))),
                    order_id=order.get('orderId')
                )
            else:
                return HedgeLeg(
                    success=False,
                    exchange="GRVT",
                    side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
                    quantity=quantity,
                    error=order.get('reason', 'Order rejected') if order else 'No response'
                )

        except Exception as e:
            return HedgeLeg(
                success=False,
                exchange="GRVT",
                side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
                quantity=quantity,
                error=str(e)
            )

    async def _place_lighter_order(self, is_ask: bool, quantity: Decimal) -> HedgeLeg:
        """在Lighter下市价单 - 使用现有方法"""
        try:
            # 获取参考价格（使用GRVT的价格）
            best_bid, best_ask = await self.grvt.fetch_bbo_prices(self.symbol)

            # 设置滑点价格（市价单效果）
            if is_ask:  # 卖出
                price = best_bid * Decimal("0.95")  # 低于买价5%，确保成交
            else:  # 买入
                price = best_ask * Decimal("1.05")  # 高于卖价5%，确保成交

            # 转换为Lighter格式
            base_amount = int(quantity * self.lighter_base_multiplier)
            price_scaled = int(price * self.lighter_price_multiplier)

            # 使用现有的Lighter客户端方法
            client_order_index = self.lighter.get_next_order_index()

            tx_info, error = self.lighter.sign_create_order(
                market_index=self.lighter_market_index,
                client_order_index=client_order_index,
                base_amount=base_amount,
                price=price_scaled,
                is_ask=is_ask,
                order_type=0,  # Limit order
                time_in_force=0,  # GTC
                reduce_only=False,
                trigger_price=0
            )

            if error:
                return HedgeLeg(
                    success=False,
                    exchange="Lighter",
                    side=OrderSide.SELL if is_ask else OrderSide.BUY,
                    quantity=quantity,
                    error=error
                )

            # 发送交易
            tx_hash = await self.lighter.send_tx(
                tx_type=self.lighter.TX_TYPE_CREATE_ORDER,
                tx_info=tx_info
            )

            if tx_hash:
                return HedgeLeg(
                    success=True,
                    exchange="Lighter",
                    side=OrderSide.SELL if is_ask else OrderSide.BUY,
                    quantity=quantity,
                    price=price,
                    order_id=str(client_order_index)
                )
            else:
                return HedgeLeg(
                    success=False,
                    exchange="Lighter",
                    side=OrderSide.SELL if is_ask else OrderSide.BUY,
                    quantity=quantity,
                    error="Failed to send transaction"
                )

        except Exception as e:
            return HedgeLeg(
                success=False,
                exchange="Lighter",
                side=OrderSide.SELL if is_ask else OrderSide.BUY,
                quantity=quantity,
                error=str(e)
            )

    async def rebalance_positions(self, max_rebalance_size: Optional[Decimal] = None) -> HedgeResult:
        """重新平衡仓位"""
        result = HedgeResult(success=False)

        try:
            positions = await self.get_positions()
            imbalance = positions.total_position

            # 如果已经平衡，无需操作
            if abs(imbalance) <= self.rebalance_tolerance:
                result.success = True
                result.position_after = positions
                self.logger.info(f"Positions already balanced: {positions}")
                return result

            # 计算重平衡数量
            rebalance_qty = min(
                abs(imbalance),
                max_rebalance_size or self.order_quantity
            )

            # 决定方向：如果总仓位为正，需要做空；反之做多
            direction = "short" if imbalance > 0 else "long"

            self.logger.info(f"Rebalancing: imbalance={imbalance:.4f}, direction={direction}, qty={rebalance_qty:.4f}")

            # 只在需要重平衡的交易所下单
            if abs(positions.maker_position) > abs(positions.taker_position):
                # GRVT仓位过大，在Lighter补单
                lighter_result = await self._place_lighter_order(
                    is_ask=(direction == "short"),
                    quantity=rebalance_qty
                )
                result.taker_leg = lighter_result
                result.success = lighter_result.success
            else:
                # Lighter仓位过大，在GRVT补单
                grvt_side = "sell" if direction == "short" else "buy"
                grvt_result = await self._place_grvt_order(grvt_side, rebalance_qty)
                result.maker_leg = grvt_result
                result.success = grvt_result.success

            # 获取更新后的仓位
            if result.success:
                await asyncio.sleep(0.5)
                result.position_after = await self.get_positions()

            return result

        except Exception as e:
            self.logger.error(f"Rebalance failed: {e}")
            result.error = str(e)
            return result

    async def close_all_positions(self) -> HedgeResult:
        """关闭所有仓位"""
        result = HedgeResult(success=False)

        try:
            # 先取消所有订单
            await self.cancel_all_orders()

            positions = await self.get_positions()
            self.logger.info(f"Closing all positions: {positions}")

            tasks = []

            # GRVT平仓
            if abs(positions.maker_position) > 0.01:
                side = "buy" if positions.maker_position < 0 else "sell"
                qty = abs(positions.maker_position)
                tasks.append(self._place_grvt_order(side, qty))

            # Lighter平仓
            if abs(positions.taker_position) > 0.01:
                is_ask = positions.taker_position > 0  # 仓位为正则卖出
                qty = abs(positions.taker_position)
                tasks.append(self._place_lighter_order(is_ask, qty))

            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # 检查结果
                all_success = all(
                    isinstance(r, HedgeLeg) and r.success
                    for r in results
                    if not isinstance(r, Exception)
                )

                result.success = all_success
                if len(results) > 0 and not isinstance(results[0], Exception):
                    result.maker_leg = results[0]
                if len(results) > 1 and not isinstance(results[1], Exception):
                    result.taker_leg = results[1]
            else:
                result.success = True
                self.logger.info("No positions to close")

            # 获取最终仓位
            await asyncio.sleep(1)
            result.position_after = await self.get_positions()

            return result

        except Exception as e:
            self.logger.error(f"Failed to close positions: {e}")
            result.error = str(e)
            return result

    async def cancel_all_orders(self) -> bool:
        """取消所有未成交订单"""
        try:
            # GRVT取消订单
            grvt_task = self.grvt.cancel_all_orders(self.symbol)

            # Lighter暂时不实现取消（需要查询订单ID）
            # TODO: 实现Lighter订单查询和取消

            await grvt_task
            self.logger.info("All orders cancelled")
            return True

        except Exception as e:
            self.logger.error(f"Failed to cancel orders: {e}")
            return False

    async def get_market_info(self) -> Dict[str, Any]:
        """获取市场信息"""
        try:
            # 获取GRVT价格
            best_bid, best_ask = await self.grvt.fetch_bbo_prices(self.symbol)

            return {
                "grvt": {
                    "bid": float(best_bid),
                    "ask": float(best_ask),
                    "spread": float(best_ask - best_bid)
                },
                "lighter": {
                    "reference_bid": float(best_bid),
                    "reference_ask": float(best_ask)
                }
            }

        except Exception as e:
            self.logger.error(f"Failed to get market info: {e}")
            return {}

    async def cleanup(self) -> None:
        """清理资源"""
        try:
            # 取消所有订单
            await self.cancel_all_orders()

            # 关闭GRVT连接
            if hasattr(self.grvt, 'disconnect'):
                await self.grvt.disconnect()

            self.logger.info("Hedge service cleaned up")

        except Exception as e:
            self.logger.error(f"Cleanup error: {e}")
            raise