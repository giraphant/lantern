"""
阶段检测器 - 纯函数，从交易所数据判断当前阶段。

职责：
1. 根据仓位和订单历史判断当前处于哪个阶段
2. 判断是否应该继续建仓、持仓等待、或开始平仓
3. 不执行任何操作，只返回判断结果
"""

from decimal import Decimal
from datetime import datetime
from typing import NamedTuple, Optional
from enum import Enum

from hedge.safety_checker import PositionState


class TradingPhase(Enum):
    """交易阶段"""
    BUILDING = "BUILDING"              # 建仓中
    HOLDING = "HOLDING"                # 持仓等待中
    WINDING_DOWN = "WINDING_DOWN"      # 平仓中


class PhaseInfo(NamedTuple):
    """阶段信息"""
    phase: TradingPhase
    reason: str
    time_remaining: Optional[int] = None  # 如果在HOLDING，剩余多少秒


class PhaseDetector:
    """
    阶段检测器 - 纯函数式设计。

    从交易所的真实数据（仓位 + 订单历史）推断当前应该处于哪个阶段。
    """

    @staticmethod
    def detect_phase(
        position: PositionState,
        target_cycles: int,
        order_size: Decimal,
        hold_time: int,
        last_order_side: Optional[str] = None,
        last_order_time: Optional[datetime] = None
    ) -> PhaseInfo:
        """
        从交易所数据检测当前阶段。

        判断顺序：
        1. 先看仓位大小（是否接近0或超标）
        2. 再看订单方向（buy=建仓中, sell=平仓中）
        3. 根据具体情况判断下一步

        Args:
            position: 当前仓位状态
            target_cycles: 目标循环次数
            order_size: 每次订单大小
            hold_time: 持仓时间（秒）
            last_order_side: 最后一笔成交订单的方向（"buy"或"sell"）
            last_order_time: 最后一笔成交订单的时间

        Returns:
            PhaseInfo: 当前阶段信息
        """
        current_grvt = abs(position.grvt_position)
        target_grvt = order_size * target_cycles

        # ========== 第一优先级：仓位大小判断 ==========

        # 仓位接近0 → 从头开始建仓
        if current_grvt < order_size * Decimal("0.1"):
            return PhaseInfo(
                phase=TradingPhase.BUILDING,
                reason="Position near zero, starting build"
            )

        # 仓位超标（>1.5倍目标）→ 强制平仓
        if current_grvt > target_grvt * Decimal("1.5"):
            return PhaseInfo(
                phase=TradingPhase.WINDING_DOWN,
                reason=f"Position exceeded ({current_grvt:.2f} > {target_grvt * Decimal('1.5'):.2f}), forcing winddown"
            )

        # ========== 第二优先级：没有订单历史 ==========

        if last_order_side is None or last_order_time is None:
            return PhaseInfo(
                phase=TradingPhase.BUILDING,
                reason="No order history, starting build"
            )

        # ========== 第三优先级：根据最后订单方向判断 ==========

        # 最后一笔是 sell（平仓中）→ 继续平仓
        if last_order_side == "sell":
            return PhaseInfo(
                phase=TradingPhase.WINDING_DOWN,
                reason=f"Winding down, remaining: {current_grvt:.2f}"
            )

        # 最后一笔是 buy（建仓中）→ 检查是否该进入下一阶段
        if last_order_side == "buy":
            time_since_last = (datetime.utcnow() - last_order_time).total_seconds()

            # 还没建到目标80% → 继续建仓
            if current_grvt < target_grvt * Decimal("0.8"):
                return PhaseInfo(
                    phase=TradingPhase.BUILDING,
                    reason=f"Building: {current_grvt:.2f}/{target_grvt:.2f}"
                )

            # 已达目标，但持仓时间不够 → HOLDING
            if time_since_last < hold_time:
                time_remaining = int(hold_time - time_since_last)
                return PhaseInfo(
                    phase=TradingPhase.HOLDING,
                    reason=f"Holding: {time_remaining}s remaining",
                    time_remaining=time_remaining
                )

            # 已达目标且持仓时间够了 → 开始平仓
            return PhaseInfo(
                phase=TradingPhase.WINDING_DOWN,
                reason=f"Hold time reached ({int(time_since_last)}s >= {hold_time}s), starting winddown"
            )

        # 默认：建仓
        return PhaseInfo(
            phase=TradingPhase.BUILDING,
            reason="Default: building"
        )

    @staticmethod
    def should_execute_trade(phase_info: PhaseInfo) -> bool:
        """
        判断当前阶段是否应该执行交易。

        Args:
            phase_info: 阶段信息

        Returns:
            bool: True如果应该执行交易，False如果应该等待
        """
        # HOLDING阶段不执行交易，只等待
        return phase_info.phase != TradingPhase.HOLDING
