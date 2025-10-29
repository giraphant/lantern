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

        核心逻辑：看最后一笔成交订单的方向
        - 如果是建仓方向（buy）→ 检查持仓时间
        - 如果是平仓方向（sell）→ 正在平仓中或已平完
        - 如果没有订单 → 开始建仓

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
        # 情况1：没有订单历史，开始建仓
        if last_order_side is None or last_order_time is None:
            return PhaseInfo(
                phase=TradingPhase.BUILDING,
                reason="No order history, starting build phase"
            )

        # 情况2：最后一笔是卖出（平仓方向），说明在平仓中
        if last_order_side == "sell":
            # 检查是否已经平完了
            current_grvt = abs(position.grvt_position)
            if current_grvt < order_size * Decimal("0.1"):
                # 仓位接近0，平仓完成，准备重新建仓
                return PhaseInfo(
                    phase=TradingPhase.BUILDING,
                    reason="Winddown complete, ready to rebuild"
                )
            else:
                # 还有仓位，继续平仓
                return PhaseInfo(
                    phase=TradingPhase.WINDING_DOWN,
                    reason=f"Winding down, remaining position: {current_grvt}"
                )

        # 情况3：最后一笔是买入（建仓方向），检查持仓时间
        if last_order_side == "buy":
            time_since_last_build = (datetime.utcnow() - last_order_time).total_seconds()

            # 检查是否达到目标仓位
            target_grvt = order_size * target_cycles
            current_grvt = abs(position.grvt_position)

            # 如果还没达到目标，继续建仓
            if current_grvt < target_grvt * Decimal("0.8"):
                return PhaseInfo(
                    phase=TradingPhase.BUILDING,
                    reason=f"Building position: {current_grvt}/{target_grvt}"
                )

            # 达到目标了，检查持仓时间
            if time_since_last_build >= hold_time:
                # 持仓时间够了，开始平仓
                return PhaseInfo(
                    phase=TradingPhase.WINDING_DOWN,
                    reason=f"Hold time {int(time_since_last_build)}s >= {hold_time}s, starting winddown"
                )
            else:
                # 还在持仓期内，等待
                time_remaining = int(hold_time - time_since_last_build)
                return PhaseInfo(
                    phase=TradingPhase.HOLDING,
                    reason=f"Target reached, holding for {time_remaining}s more",
                    time_remaining=time_remaining
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
