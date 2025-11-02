"""
聚合层 - 聚合多个原子数据源的信息

设计原则:
1. 从多个AtomicQueryer收集数据
2. 提供统一的查询接口
3. 不包含决策逻辑，只负责数据聚合
"""

import logging
from decimal import Decimal
from typing import Dict, List, Tuple, Optional
from itertools import combinations

from atomic.models import (
    Position,
    FundingRate,
    Market,
    Order,
    Symbol
)
from atomic.operations import AtomicQueryer


class PositionAggregator:
    """
    仓位聚合器 - 聚合多个交易所的仓位数据

    职责：
    - 查询所有交易所的仓位
    - 计算总敞口、不平衡度等聚合指标
    - 不包含任何交易决策
    """

    def __init__(self, queryers: Dict[str, AtomicQueryer]):
        """
        Args:
            queryers: {"grvt": AtomicQueryer(...), "lighter": AtomicQueryer(...)}
        """
        self.queryers = queryers
        self.logger = logging.getLogger(__name__)

    async def get_all_positions(self) -> Dict[str, Position]:
        """
        获取所有交易所的仓位

        Returns:
            {"grvt": Position(...), "lighter": Position(...)}
        """
        positions = {}

        for exchange_name, queryer in self.queryers.items():
            try:
                position = await queryer.get_position()
                positions[exchange_name] = position
                self.logger.debug(
                    f"{exchange_name}: {position.side} {position.quantity}"
                )
            except Exception as e:
                self.logger.error(f"Failed to get position from {exchange_name}: {e}")
                # 继续处理其他交易所

        return positions

    async def get_total_exposure(self) -> Decimal:
        """
        计算总敞口（所有交易所带符号仓位之和）

        完美对冲时应该为0
        正数表示净多仓，负数表示净空仓

        Returns:
            Decimal: 总敞口
        """
        positions = await self.get_all_positions()
        total = sum(pos.signed_quantity for pos in positions.values())
        return total

    async def get_imbalance(self) -> Decimal:
        """
        计算不平衡度（总敞口的绝对值）

        完美对冲时应该为0

        Returns:
            Decimal: 不平衡度
        """
        exposure = await self.get_total_exposure()
        return abs(exposure)

    async def get_single_side_position(self) -> Decimal:
        """
        获取单边仓位大小（对冲策略中的有效仓位）

        例如：GRVT多5个，Lighter空5个 → 单边仓位=5

        Returns:
            Decimal: 单边仓位
        """
        positions = await self.get_all_positions()

        # 取所有交易所绝对值仓位的最大值
        max_position = max(
            (abs(pos.signed_quantity) for pos in positions.values()),
            default=Decimal(0)
        )

        return max_position

    async def check_position_balance(self, tolerance: Decimal = Decimal("0.1")) -> Tuple[bool, str]:
        """
        检查仓位是否平衡

        Args:
            tolerance: 容忍的不平衡度

        Returns:
            (is_balanced, reason)
        """
        imbalance = await self.get_imbalance()

        if imbalance <= tolerance:
            return True, f"Balanced: imbalance={imbalance}"
        else:
            return False, f"Imbalanced: imbalance={imbalance} > tolerance={tolerance}"


class FundingRateAggregator:
    """
    资金费率聚合器 - 聚合多个交易所的费率数据

    职责：
    - 查询所有交易所的费率
    - 计算费率差、找到最佳套利对
    - 不包含建仓/平仓决策
    """

    def __init__(self, queryers: Dict[str, AtomicQueryer]):
        """
        Args:
            queryers: {"grvt": AtomicQueryer(...), "lighter": AtomicQueryer(...)}
        """
        self.queryers = queryers
        self.logger = logging.getLogger(__name__)

    async def get_all_rates(self) -> Dict[str, FundingRate]:
        """
        获取所有交易所的费率

        Returns:
            {"grvt": FundingRate(...), "lighter": FundingRate(...)}
        """
        rates = {}

        for exchange_name, queryer in self.queryers.items():
            try:
                rate = await queryer.get_funding_rate()
                rates[exchange_name] = rate
                self.logger.debug(
                    f"{exchange_name}: {rate.rate} ({rate.interval_hours}h) "
                    f"→ {rate.annual_rate:.4%} APR"
                )
            except Exception as e:
                self.logger.error(f"Failed to get funding rate from {exchange_name}: {e}")

        return rates

    async def get_best_spread(self) -> Optional[Tuple[str, str, Decimal, FundingRate, FundingRate]]:
        """
        找到最佳费率差的交易所对

        原子化特点：
        - 自动组合任意两个交易所
        - 不需要预先知道交易所名称

        Returns:
            (exchange_high, exchange_low, spread_apr, rate_high, rate_low)
            或 None（如果交易所不足2个）
        """
        rates = await self.get_all_rates()

        if len(rates) < 2:
            self.logger.warning(f"Not enough exchanges to calculate spread: {len(rates)}")
            return None

        best_spread = Decimal(0)
        best_pair = None

        # 组合所有交易所对
        for (ex_a, rate_a), (ex_b, rate_b) in combinations(rates.items(), 2):
            spread = abs(rate_a.annual_rate - rate_b.annual_rate)

            if spread > best_spread:
                best_spread = spread
                # 返回费率高的在前，费率低的在后
                if rate_a.annual_rate > rate_b.annual_rate:
                    best_pair = (ex_a, ex_b, spread, rate_a, rate_b)
                else:
                    best_pair = (ex_b, ex_a, spread, rate_b, rate_a)

        return best_pair

    async def get_spread_between(self, exchange_a: str, exchange_b: str) -> Optional[Decimal]:
        """
        获取两个指定交易所的费率差

        Args:
            exchange_a: 交易所A名称
            exchange_b: 交易所B名称

        Returns:
            Decimal: 年化费率差（绝对值）或 None
        """
        rates = await self.get_all_rates()

        rate_a = rates.get(exchange_a)
        rate_b = rates.get(exchange_b)

        if not rate_a or not rate_b:
            return None

        return abs(rate_a.annual_rate - rate_b.annual_rate)


class MarketAggregator:
    """
    市场数据聚合器 - 聚合多个交易所的市场数据

    职责：
    - 查询所有交易所的市场数据
    - 比较价格差异、流动性等
    """

    def __init__(self, queryers: Dict[str, AtomicQueryer]):
        """
        Args:
            queryers: {"grvt": AtomicQueryer(...), "lighter": AtomicQueryer(...)}
        """
        self.queryers = queryers
        self.logger = logging.getLogger(__name__)

    async def get_all_markets(self) -> Dict[str, Market]:
        """
        获取所有交易所的市场数据

        Returns:
            {"grvt": Market(...), "lighter": Market(...)}
        """
        markets = {}

        for exchange_name, queryer in self.queryers.items():
            try:
                market = await queryer.get_market()
                markets[exchange_name] = market
                self.logger.debug(
                    f"{exchange_name}: bid={market.best_bid}, ask={market.best_ask}, "
                    f"mid={market.mid_price}"
                )
            except Exception as e:
                self.logger.error(f"Failed to get market data from {exchange_name}: {e}")

        return markets

    async def get_price_spread(self) -> Optional[Dict[str, Decimal]]:
        """
        计算所有交易所的价格差异

        Returns:
            {"grvt_lighter": Decimal("50.0"), ...}
            表示交易所间的中间价差异
        """
        markets = await self.get_all_markets()

        spreads = {}

        exchanges = list(markets.keys())
        for i, ex_a in enumerate(exchanges):
            for ex_b in exchanges[i+1:]:
                market_a = markets[ex_a]
                market_b = markets[ex_b]

                if market_a.mid_price and market_b.mid_price:
                    spread = abs(market_a.mid_price - market_b.mid_price)
                    key = f"{ex_a}_{ex_b}"
                    spreads[key] = spread

        return spreads if spreads else None


class OrderAggregator:
    """
    订单聚合器 - 聚合多个交易所的订单状态

    职责：
    - 查询所有交易所的活跃订单
    - 统计订单数量
    """

    def __init__(self, queryers: Dict[str, AtomicQueryer]):
        """
        Args:
            queryers: {"grvt": AtomicQueryer(...), "lighter": AtomicQueryer(...)}
        """
        self.queryers = queryers
        self.logger = logging.getLogger(__name__)

    async def get_all_active_orders(self) -> Dict[str, List[Order]]:
        """
        获取所有交易所的活跃订单

        Returns:
            {"grvt": [Order(...), ...], "lighter": [...]}
        """
        all_orders = {}

        for exchange_name, queryer in self.queryers.items():
            try:
                orders = await queryer.get_active_orders()
                all_orders[exchange_name] = orders
                self.logger.debug(f"{exchange_name}: {len(orders)} active orders")
            except Exception as e:
                self.logger.error(f"Failed to get active orders from {exchange_name}: {e}")
                all_orders[exchange_name] = []

        return all_orders

    async def get_pending_counts(self) -> Dict[str, int]:
        """
        获取各交易所的挂单数量

        Returns:
            {"grvt": 2, "lighter": 1}
        """
        all_orders = await self.get_all_active_orders()
        return {
            exchange: len(orders)
            for exchange, orders in all_orders.items()
        }

    async def has_excessive_pending(self, max_per_exchange: int = 3) -> Tuple[bool, Optional[str]]:
        """
        检查是否有交易所挂单过多

        Args:
            max_per_exchange: 单个交易所最大挂单数

        Returns:
            (has_excessive, exchange_name or None)
        """
        counts = await self.get_pending_counts()

        for exchange, count in counts.items():
            if count > max_per_exchange:
                return True, exchange

        return False, None
