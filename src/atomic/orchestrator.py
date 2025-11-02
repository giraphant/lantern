"""
编排层 - 协调所有组件，执行完整的交易策略

设计原则:
1. 组合使用Aggregators、Decisions、Operations
2. 协调执行流程
3. 处理错误和重试
"""

import asyncio
import logging
from decimal import Decimal
from typing import Dict, List, Optional

from atomic.models import (
    Symbol,
    TradingSignal,
    Order,
    ArbitrageConfig
)
from atomic.operations import AtomicQueryer, AtomicTrader
from atomic.aggregators import (
    PositionAggregator,
    FundingRateAggregator,
    OrderAggregator
)
from atomic.decisions import (
    FundingArbitrageDecision,
    RebalanceDecision,
    SafetyDecision
)


class ArbitrageOrchestrator:
    """
    套利策略编排器

    职责：
    - 协调所有原子组件
    - 执行完整的策略循环
    - 处理错误和异常
    """

    def __init__(
        self,
        queryers: Dict[str, AtomicQueryer],
        traders: Dict[str, AtomicTrader],
        config: ArbitrageConfig,
        symbol: Symbol
    ):
        """
        Args:
            queryers: {"grvt": AtomicQueryer(...), "lighter": ...}
            traders: {"grvt": AtomicTrader(...), "lighter": ...}
            config: 套利配置
            symbol: 交易对
        """
        self.queryers = queryers
        self.traders = traders
        self.config = config
        self.symbol = symbol

        # 初始化聚合器
        self.position_agg = PositionAggregator(queryers)
        self.funding_agg = FundingRateAggregator(queryers)
        self.order_agg = OrderAggregator(queryers)

        self.logger = logging.getLogger(__name__)

    async def run_strategy_cycle(self) -> Optional[List[Order]]:
        """
        运行一个完整的策略周期

        流程：
        1. 安全检查
        2. 再平衡检查
        3. 套利机会分析
        4. 执行交易

        Returns:
            List[Order] 或 None
        """
        try:
            # ========== 步骤1: 获取数据 ==========
            self.logger.info("=" * 60)
            self.logger.info("Starting strategy cycle...")

            positions = await self.position_agg.get_all_positions()
            rates = await self.funding_agg.get_all_rates()
            pending_counts = await self.order_agg.get_pending_counts()

            # 记录当前状态
            self._log_current_state(positions, rates, pending_counts)

            # ========== 步骤2: 安全检查 ==========
            is_safe, reason = SafetyDecision.check_position_limits(positions, self.config)
            if not is_safe:
                self.logger.warning(f"⚠️  Position limit exceeded: {reason}")
                # 可以选择取消所有订单或暂停
                return None

            is_safe, exchange = SafetyDecision.check_pending_orders(pending_counts, max_per_exchange=3)
            if not is_safe:
                self.logger.warning(f"⚠️  Too many pending orders on {exchange}")
                # 取消该交易所的所有订单
                await self._cancel_orders_on_exchange(exchange)
                return None

            # ========== 步骤3: 再平衡检查 ==========
            rebalance_signal = RebalanceDecision.analyze_imbalance(
                positions=positions,
                config=self.config,
                symbol=self.symbol
            )

            if rebalance_signal:
                self.logger.info(f"⚖️  {rebalance_signal.reason}")
                return await self.execute_signal(rebalance_signal)

            # ========== 步骤4: 套利机会分析 ==========
            arbitrage_signal = FundingArbitrageDecision.analyze_opportunity(
                rates=rates,
                positions=positions,
                config=self.config
            )

            if arbitrage_signal:
                self.logger.info(f"💰 {arbitrage_signal.reason}")
                return await self.execute_signal(arbitrage_signal)

            # ========== 没有交易机会 ==========
            self.logger.info("😴 HOLD: No trading opportunity")
            return None

        except Exception as e:
            self.logger.error(f"Error in strategy cycle: {e}", exc_info=True)
            return None

    async def execute_signal(self, signal: TradingSignal) -> List[Order]:
        """
        执行交易信号

        原子化特点：
        - 自动路由到正确的交易所
        - 可以处理任意数量的交易腿
        - 并发执行所有交易

        Args:
            signal: 交易信号

        Returns:
            List[Order]: 执行的订单列表
        """
        self.logger.info(f"🔧 Executing signal: {signal}")

        orders = []
        tasks = []

        # 为每个交易腿创建执行任务
        for leg in signal.legs:
            trader = self.traders.get(leg.exchange_id)
            if not trader:
                self.logger.error(f"No trader for exchange: {leg.exchange_id}")
                continue

            task = trader.execute_trade(
                side=leg.side,
                quantity=leg.quantity,
                order_type=leg.order_type,
                price=leg.price
            )
            tasks.append((leg.exchange_id, task))

        # 并发执行所有订单
        results = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)

        # 处理结果
        for (exchange_id, _), result in zip(tasks, results):
            if isinstance(result, Exception):
                self.logger.error(f"Order failed on {exchange_id}: {result}")
            elif isinstance(result, Order):
                orders.append(result)
                self.logger.info(
                    f"  ✅ {exchange_id}: {result.side} {result.quantity} @ {result.price} "
                    f"(status: {result.status})"
                )

        return orders

    async def cancel_all_orders(self) -> Dict[str, int]:
        """
        取消所有交易所的所有订单

        Returns:
            {"grvt": 2, "lighter": 1} - 每个交易所取消的订单数
        """
        self.logger.warning("🚫 Cancelling all orders...")

        cancelled_counts = {}

        for exchange_id, trader in self.traders.items():
            try:
                count = await trader.cancel_all_orders()
                cancelled_counts[exchange_id] = count
                self.logger.info(f"  {exchange_id}: {count} orders cancelled")
            except Exception as e:
                self.logger.error(f"Failed to cancel orders on {exchange_id}: {e}")
                cancelled_counts[exchange_id] = 0

        return cancelled_counts

    async def _cancel_orders_on_exchange(self, exchange_id: str):
        """取消指定交易所的所有订单"""
        trader = self.traders.get(exchange_id)
        if trader:
            try:
                await trader.cancel_all_orders()
                self.logger.info(f"Cancelled all orders on {exchange_id}")
            except Exception as e:
                self.logger.error(f"Failed to cancel orders on {exchange_id}: {e}")

    def _log_current_state(self, positions, rates, pending_counts):
        """记录当前状态"""
        self.logger.info("")
        self.logger.info("📊 Current State:")

        # 仓位
        self.logger.info("  Positions:")
        for exchange, pos in positions.items():
            self.logger.info(f"    {exchange}: {pos.side} {pos.quantity}")

        # 费率
        self.logger.info("  Funding Rates:")
        for exchange, rate in rates.items():
            self.logger.info(
                f"    {exchange}: {rate.rate:.6f} ({rate.interval_hours}h) "
                f"→ {rate.annual_rate:.4%} APR"
            )

        # 挂单
        self.logger.info("  Pending Orders:")
        for exchange, count in pending_counts.items():
            self.logger.info(f"    {exchange}: {count}")

        # 总敞口
        total_exposure = sum(pos.signed_quantity for pos in positions.values())
        imbalance = abs(total_exposure)
        self.logger.info(f"  Total Exposure: {total_exposure} (imbalance: {imbalance})")
        self.logger.info("")


class SimpleStrategyRunner:
    """
    简单的策略运行器（用于测试）

    职责：
    - 定时运行策略循环
    - 处理异常和重连
    """

    def __init__(self, orchestrator: ArbitrageOrchestrator, interval: int = 60):
        """
        Args:
            orchestrator: 策略编排器
            interval: 运行间隔（秒）
        """
        self.orchestrator = orchestrator
        self.interval = interval
        self.logger = logging.getLogger(__name__)
        self.is_running = False

    async def start(self):
        """开始运行策略"""
        self.is_running = True
        self.logger.info(f"Strategy runner started (interval: {self.interval}s)")

        while self.is_running:
            try:
                # 运行策略循环
                await self.orchestrator.run_strategy_cycle()

                # 等待下一个周期
                await asyncio.sleep(self.interval)

            except KeyboardInterrupt:
                self.logger.info("Received shutdown signal")
                break

            except Exception as e:
                self.logger.error(f"Unexpected error in strategy loop: {e}", exc_info=True)
                # 等待一段时间后重试
                await asyncio.sleep(10)

        self.logger.info("Strategy runner stopped")

    def stop(self):
        """停止运行策略"""
        self.is_running = False
