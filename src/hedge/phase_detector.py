"""
决策器 - 纯函数，原子化判断每一轮该做什么。

职责：
根据当前状态（仓位 + 时间），决定这一轮应该执行什么操作。
完全无状态，每轮独立判断。
"""

from decimal import Decimal
from datetime import datetime
from typing import NamedTuple, Optional
from enum import Enum

from hedge.safety_checker import PositionState


class TradingPhase(Enum):
    """交易操作"""
    BUILDING = "BUILDING"              # 建仓
    HOLDING = "HOLDING"                # 持仓等待
    WINDING_DOWN = "WINDING_DOWN"      # 平仓


class PhaseInfo(NamedTuple):
    """决策信息"""
    phase: TradingPhase
    reason: str
    time_remaining: Optional[int] = None


class PhaseDetector:
    """
    决策器 - 纯函数式设计。

    每轮原子化判断：给定当前状态，这一轮该做什么？
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
        原子化判断：这一轮该做什么？

        判断逻辑（按顺序）：
        1. 仓位接近0 → BUILD
        2. 超时（最后一笔buy订单时间 >= hold_time）→ WINDDOWN
        3. 仓位 < target → BUILD
        4. 其他（仓位达标且未超时）→ WAIT

        Args:
            position: 当前仓位状态
            target_cycles: 目标循环次数
            order_size: 每次订单大小
            hold_time: 持仓时间（秒）
            last_order_side: 最后一笔成交订单的方向（仅用于记录）
            last_order_time: 最后一笔成交订单的时间（用于计算超时）

        Returns:
            PhaseInfo: 这一轮应该做什么
        """
        current_grvt = abs(position.grvt_position)
        target_grvt = order_size * target_cycles

        # 计算距离最后一笔buy订单的时间
        time_since_last_build = None
        if last_order_time:
            time_since_last_build = (datetime.utcnow() - last_order_time).total_seconds()

        # ========== 判断1: 仓位接近0 → BUILD ==========
        if current_grvt < order_size * Decimal("0.1"):
            return PhaseInfo(
                phase=TradingPhase.BUILDING,
                reason="Position near zero, build"
            )

        # ========== 判断2: 超时 → WINDDOWN ==========
        if time_since_last_build and time_since_last_build >= hold_time:
            return PhaseInfo(
                phase=TradingPhase.WINDING_DOWN,
                reason=f"Timeout ({int(time_since_last_build)}s >= {hold_time}s), winddown"
            )

        # ========== 判断3: 仓位 < target → BUILD ==========
        if current_grvt < target_grvt:
            return PhaseInfo(
                phase=TradingPhase.BUILDING,
                reason=f"Building: {current_grvt:.2f}/{target_grvt:.2f}"
            )

        # ========== 判断4: 其他 → WAIT ==========
        time_remaining = None
        if time_since_last_build:
            time_remaining = int(hold_time - time_since_last_build)

        return PhaseInfo(
            phase=TradingPhase.HOLDING,
            reason=f"Position reached, holding ({time_remaining}s remaining)" if time_remaining else "Position reached, holding",
            time_remaining=time_remaining
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
