"""
决策层 - 纯函数式的策略决策

设计原则:
1. 所有函数都是纯函数（无副作用）
2. 输入数据，输出决策
3. 不执行任何交易操作
4. 不依赖具体交易所名称
"""

import logging
from decimal import Decimal
from typing import Dict, Optional, Tuple, List
from enum import Enum

from atomic.models import (
    Position,
    FundingRate,
    TradingSignal,
    TradeLeg,
    Symbol,
    ArbitrageConfig
)


logger = logging.getLogger(__name__)


class ActionType(Enum):
    """策略动作类型"""
    BUILD = "BUILD"        # 建仓
    HOLD = "HOLD"          # 持仓
    WINDDOWN = "WINDDOWN"  # 平仓
    REBALANCE = "REBALANCE"  # 再平衡


class FundingArbitrageDecision:
    """
    资金费率套利决策器（纯函数）

    原子化特点：
    - 不知道具体交易所名称
    - 可以处理任意数量的交易所
    - 自动找到最佳套利对
    """

    @staticmethod
    def analyze_opportunity(
        rates: Dict[str, FundingRate],
        positions: Dict[str, Position],
        config: ArbitrageConfig
    ) -> Optional[TradingSignal]:
        """
        分析资金费率套利机会

        Args:
            rates: 所有交易所的费率 {"grvt": FundingRate(...), ...}
            positions: 所有交易所的仓位 {"grvt": Position(...), ...}
            config: 套利配置

        Returns:
            TradingSignal 或 None
        """
        if len(rates) < 2:
            logger.debug("Need at least 2 exchanges for arbitrage")
            return None

        # 1. 找到费率差最大的交易所对
        best_pair = FundingArbitrageDecision._find_best_rate_pair(rates)
        if not best_pair:
            return None

        exchange_high, exchange_low, spread, rate_high, rate_low = best_pair

        logger.debug(
            f"Best spread: {exchange_high} ({rate_high.annual_rate:.4%}) "
            f"vs {exchange_low} ({rate_low.annual_rate:.4%}) = {spread:.4%}"
        )

        # 2. 检查是否满足建仓条件
        if spread >= config.build_threshold:
            return FundingArbitrageDecision._create_build_signal(
                exchange_high=exchange_high,
                exchange_low=exchange_low,
                spread=spread,
                positions=positions,
                config=config,
                symbol=rate_high.symbol  # 假设所有交易所交易对相同
            )

        # 3. 检查是否满足平仓条件
        if spread < config.close_threshold:
            return FundingArbitrageDecision._create_winddown_signal(
                exchange_high=exchange_high,
                exchange_low=exchange_low,
                spread=spread,
                positions=positions,
                config=config,
                symbol=rate_high.symbol
            )

        # 4. 否则持仓
        return None

    @staticmethod
    def _find_best_rate_pair(
        rates: Dict[str, FundingRate]
    ) -> Optional[Tuple[str, str, Decimal, FundingRate, FundingRate]]:
        """
        找到费率差最大的交易所对

        Returns:
            (exchange_high, exchange_low, spread, rate_high, rate_low)
        """
        best_spread = Decimal(0)
        best_pair = None

        exchanges = list(rates.keys())
        for i, ex_a in enumerate(exchanges):
            for ex_b in exchanges[i+1:]:
                rate_a = rates[ex_a]
                rate_b = rates[ex_b]

                spread = abs(rate_a.annual_rate - rate_b.annual_rate)

                if spread > best_spread:
                    best_spread = spread
                    # 返回费率高的在前
                    if rate_a.annual_rate > rate_b.annual_rate:
                        best_pair = (ex_a, ex_b, spread, rate_a, rate_b)
                    else:
                        best_pair = (ex_b, ex_a, spread, rate_b, rate_a)

        return best_pair

    @staticmethod
    def _create_build_signal(
        exchange_high: str,
        exchange_low: str,
        spread: Decimal,
        positions: Dict[str, Position],
        config: ArbitrageConfig,
        symbol: Symbol
    ) -> Optional[TradingSignal]:
        """
        创建建仓信号

        策略：做多低费率交易所，做空高费率交易所
        """
        # 检查仓位限制
        pos_high = positions.get(exchange_high)
        pos_low = positions.get(exchange_low)

        # 检查是否已达到最大仓位
        if pos_high and abs(pos_high.signed_quantity) >= config.max_position:
            logger.debug(f"{exchange_high} position limit reached")
            return None

        if pos_low and abs(pos_low.signed_quantity) >= config.max_position:
            logger.debug(f"{exchange_low} position limit reached")
            return None

        # 生成交易信号
        # 策略：在低费率交易所做多，在高费率交易所做空
        legs = [
            TradeLeg(
                exchange_id=exchange_low,
                symbol=symbol,
                side="buy",
                quantity=config.trade_size,
                order_type="post_only"
            ),
            TradeLeg(
                exchange_id=exchange_high,
                symbol=symbol,
                side="sell",
                quantity=config.trade_size,
                order_type="post_only"
            )
        ]

        return TradingSignal(
            legs=legs,
            reason=f"BUILD: Spread {spread:.4%} >= threshold {config.build_threshold:.4%}",
            confidence=Decimal("0.8"),
            expected_profit=spread * config.trade_size
        )

    @staticmethod
    def _create_winddown_signal(
        exchange_high: str,
        exchange_low: str,
        spread: Decimal,
        positions: Dict[str, Position],
        config: ArbitrageConfig,
        symbol: Symbol
    ) -> Optional[TradingSignal]:
        """
        创建平仓信号

        策略：平掉现有仓位
        """
        pos_high = positions.get(exchange_high)
        pos_low = positions.get(exchange_low)

        # 检查是否有仓位需要平
        if not pos_high or pos_high.is_empty:
            if not pos_low or pos_low.is_empty:
                logger.debug("No position to winddown")
                return None

        legs = []

        # 平掉高费率交易所的仓位（如果有）
        if pos_high and not pos_high.is_empty:
            # 如果是空仓，需要买入平仓
            close_side = "buy" if pos_high.side == "short" else "sell"
            legs.append(
                TradeLeg(
                    exchange_id=exchange_high,
                    symbol=symbol,
                    side=close_side,
                    quantity=min(pos_high.quantity, config.trade_size),
                    order_type="post_only"
                )
            )

        # 平掉低费率交易所的仓位（如果有）
        if pos_low and not pos_low.is_empty:
            close_side = "buy" if pos_low.side == "short" else "sell"
            legs.append(
                TradeLeg(
                    exchange_id=exchange_low,
                    symbol=symbol,
                    side=close_side,
                    quantity=min(pos_low.quantity, config.trade_size),
                    order_type="post_only"
                )
            )

        if not legs:
            return None

        return TradingSignal(
            legs=legs,
            reason=f"WINDDOWN: Spread {spread:.4%} < threshold {config.close_threshold:.4%}",
            confidence=Decimal("0.9")
        )


class RebalanceDecision:
    """
    再平衡决策器（纯函数）

    职责：检查对冲是否平衡，生成再平衡信号
    """

    @staticmethod
    def analyze_imbalance(
        positions: Dict[str, Position],
        config: ArbitrageConfig,
        symbol: Symbol
    ) -> Optional[TradingSignal]:
        """
        分析仓位不平衡并生成再平衡信号

        Args:
            positions: 所有交易所的仓位
            config: 配置
            symbol: 交易对

        Returns:
            TradingSignal 或 None
        """
        if len(positions) < 2:
            return None

        # 计算总敞口
        total_exposure = sum(pos.signed_quantity for pos in positions.values())
        imbalance = abs(total_exposure)

        logger.debug(f"Total exposure: {total_exposure}, imbalance: {imbalance}")

        # 如果不平衡度在容忍范围内，不需要再平衡
        if imbalance <= config.max_imbalance:
            return None

        # 需要再平衡：在敞口方向相反的一侧交易
        # 例如：总敞口=+5（净多仓），需要在某个交易所卖出5
        if total_exposure > 0:
            # 净多仓，需要卖出
            side = "sell"
        else:
            # 净空仓，需要买入
            side = "buy"

        # 选择一个交易所执行再平衡（简单起见，选第一个）
        exchange_id = list(positions.keys())[0]

        quantity = min(imbalance, config.trade_size)

        legs = [
            TradeLeg(
                exchange_id=exchange_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type="post_only"
            )
        ]

        return TradingSignal(
            legs=legs,
            reason=f"REBALANCE: Imbalance {imbalance} > threshold {config.max_imbalance}",
            confidence=Decimal("1.0")  # 再平衡是强制性的
        )


class SafetyDecision:
    """
    安全检查决策器（纯函数）

    职责：检查风险限制，决定是否需要暂停或取消订单
    """

    @staticmethod
    def check_position_limits(
        positions: Dict[str, Position],
        config: ArbitrageConfig
    ) -> Tuple[bool, Optional[str]]:
        """
        检查仓位是否超限

        Args:
            positions: 所有交易所的仓位
            config: 配置

        Returns:
            (is_safe, reason)
        """
        for exchange, position in positions.items():
            # 检查单个交易所仓位限制
            if abs(position.signed_quantity) > config.max_position_per_exchange:
                return False, f"{exchange} position {position.signed_quantity} exceeds limit {config.max_position_per_exchange}"

        # 检查总敞口限制
        total_exposure = sum(pos.signed_quantity for pos in positions.values())
        if abs(total_exposure) > config.max_total_exposure:
            return False, f"Total exposure {total_exposure} exceeds limit {config.max_total_exposure}"

        return True, None

    @staticmethod
    def check_pending_orders(
        pending_counts: Dict[str, int],
        max_per_exchange: int = 3
    ) -> Tuple[bool, Optional[str]]:
        """
        检查挂单是否过多

        Args:
            pending_counts: {"grvt": 2, "lighter": 1}
            max_per_exchange: 单个交易所最大挂单数

        Returns:
            (is_safe, exchange_name)
        """
        for exchange, count in pending_counts.items():
            if count > max_per_exchange:
                return False, exchange

        return True, None
