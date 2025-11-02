"""
再平衡模块 - 纯函数，只做计算。

职责：
给定当前仓位和目标仓位，计算需要执行什么操作来达到目标。
不包含任何判断逻辑，只做纯计算。
"""

from decimal import Decimal
from enum import Enum
from typing import NamedTuple

from hedge.safety_checker import PositionState


class TradeAction(Enum):
    """交易动作"""
    BUILD_LONG = "BUILD_LONG"      # 建多仓：GRVT买入 + Lighter卖出
    BUILD_SHORT = "BUILD_SHORT"    # 建空仓：GRVT卖出 + Lighter买入
    CLOSE_LONG = "CLOSE_LONG"      # 平多仓：GRVT卖出 + Lighter买入
    CLOSE_SHORT = "CLOSE_SHORT"    # 平空仓：GRVT买入 + Lighter卖出
    HOLD = "HOLD"                  # 持仓，不操作


class TradeInstruction(NamedTuple):
    """交易指令"""
    action: TradeAction
    quantity: Decimal
    reason: str


class Rebalancer:
    """
    再平衡器 - 纯函数式设计。

    唯一职责：计算如何从当前状态到达目标状态。
    """

    @staticmethod
    def calculate_rebalance(
        current_position: PositionState,
        target_total_position: Decimal,
        order_size: Decimal,
        tolerance: Decimal = Decimal("0.01")
    ) -> TradeInstruction:
        """
        计算如何调整仓位到目标状态（用于打平不平衡）。

        目标：让 GRVT + Lighter = target_total_position (通常是0，让两边完全对冲)
        方法：调整Lighter侧的仓位（使用市价单立即成交）

        逻辑：
        - 如果 total > target，说明仓位过多，需要 Lighter 买入来减少净仓位
        - 如果 total < target，说明仓位不足，需要 Lighter 卖出来增加净仓位

        Args:
            current_position: 当前仓位状态
            target_total_position: 目标总仓位（通常是0）
            order_size: 每次交易的数量
            tolerance: 允许的偏差范围

        Returns:
            TradeInstruction: 需要执行的交易指令（REBALANCE_BUY/REBALANCE_SELL Lighter）
        """
        current_total = current_position.total_position
        diff = target_total_position - current_total

        # 如果已经接近目标，不操作
        if abs(diff) < tolerance:
            return TradeInstruction(
                action=TradeAction.HOLD,
                quantity=Decimal(0),
                reason=f"Position balanced: total={current_total}, target={target_total_position}"
            )

        # total < target: 净空头过多，需要减少空头 → Lighter买入
        if diff > 0:
            return TradeInstruction(
                action=TradeAction.CLOSE_SHORT,  # Lighter买入，减少空头仓位
                quantity=min(order_size, abs(diff)),
                reason=f"Rebalancing: Lighter buy to reduce short (total={current_total} -> {target_total_position})"
            )

        # total > target: 净多头过多，需要增加空头 → Lighter卖出
        else:
            return TradeInstruction(
                action=TradeAction.BUILD_SHORT,  # Lighter卖出，增加空头仓位
                quantity=min(order_size, abs(diff)),
                reason=f"Rebalancing: Lighter sell to increase short (total={current_total} -> {target_total_position})"
            )
