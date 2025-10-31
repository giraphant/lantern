"""
资金费率检查器 - 纯函数，判断是否满足套利条件。

职责：
1. 检查费率差是否满足建仓/平仓条件
2. 结合仓位限制做判断
3. 不执行任何交易操作，只返回判断结果
"""

from decimal import Decimal
from enum import Enum
from typing import NamedTuple, Optional

from hedge.safety_checker import PositionState
from hedge.funding_rate_normalizer import FundingRateSpread


class FundingAction(Enum):
    """资金费率套利操作"""
    BUILD = "BUILD"          # 建仓
    HOLD = "HOLD"            # 持仓
    WINDDOWN = "WINDDOWN"    # 平仓


class FundingCheckResult(NamedTuple):
    """费率检查结果"""
    action: FundingAction
    reason: str
    annual_spread: Decimal  # 年化费率差
    profitable_side: str    # 盈利方向


class FundingRateChecker:
    """
    资金费率检查器 - 纯函数式设计。

    判断逻辑：
    1. 费率差足够大 + 仓位未满 → BUILD
    2. 费率差太小 OR 仓位达上限 → WINDDOWN
    3. 其他 → HOLD
    """

    @staticmethod
    def check_funding_opportunity(
        spread: FundingRateSpread,
        position: PositionState,
        build_threshold_apr: Decimal,   # 建仓阈值（年化，如0.05 = 5% APR）
        close_threshold_apr: Decimal,   # 平仓阈值（年化，如0.02 = 2% APR）
        max_position: Decimal,          # 最大仓位
        min_position_for_close: Decimal = Decimal("0.1")  # 最小平仓仓位
    ) -> FundingCheckResult:
        """
        检查资金费率套利机会。

        Args:
            spread: 归一化后的费率差信息
            position: 当前仓位状态
            build_threshold_apr: 建仓阈值（年化费率差，如0.05 = 5% APR）
            close_threshold_apr: 平仓阈值（年化费率差，如0.02 = 2% APR）
            max_position: 最大仓位
            min_position_for_close: 最小平仓仓位（低于此值视为已平完）

        Returns:
            FundingCheckResult: 检查结果
        """
        # 使用年化费率差的绝对值
        annual_spread = abs(spread.annual_spread)
        current_position = abs(position.total_position)

        # ========== 判断1: 费率差足够大 + 仓位未满 → BUILD ==========
        if annual_spread >= build_threshold_apr and current_position < max_position:
            return FundingCheckResult(
                action=FundingAction.BUILD,
                reason=f"Spread {annual_spread:.2%} APR >= threshold {build_threshold_apr:.2%}",
                annual_spread=annual_spread,
                profitable_side=spread.profitable_side
            )

        # ========== 判断2: 费率差太小 OR 仓位达上限 → WINDDOWN ==========
        # 只有在有仓位的情况下才考虑平仓
        if current_position >= min_position_for_close:
            if annual_spread < close_threshold_apr:
                return FundingCheckResult(
                    action=FundingAction.WINDDOWN,
                    reason=f"Spread {annual_spread:.2%} APR < threshold {close_threshold_apr:.2%}",
                    annual_spread=annual_spread,
                    profitable_side=spread.profitable_side
                )

            if current_position >= max_position:
                return FundingCheckResult(
                    action=FundingAction.WINDDOWN,
                    reason=f"Position {current_position} reached limit {max_position}",
                    annual_spread=annual_spread,
                    profitable_side=spread.profitable_side
                )

        # ========== 判断3: 其他 → HOLD ==========
        if current_position < min_position_for_close:
            reason = f"No position to hold (spread={annual_spread:.2%} APR)"
        else:
            reason = f"Holding position={current_position} (spread={annual_spread:.2%} APR)"

        return FundingCheckResult(
            action=FundingAction.HOLD,
            reason=reason,
            annual_spread=annual_spread,
            profitable_side=spread.profitable_side
        )

    @staticmethod
    def should_reverse_direction(
        current_side: str,
        profitable_side: str,
        position: PositionState
    ) -> bool:
        """
        检查是否需要反向操作。

        如果当前仓位方向与盈利方向相反，需要先平仓再反向开仓。

        Args:
            current_side: 当前持仓方向（"long"或"short"）
            profitable_side: 费率盈利方向（"long"或"short"）
            position: 当前仓位状态

        Returns:
            bool: True如果需要反向
        """
        current_position = position.total_position

        # 如果没有仓位，不需要反向
        if abs(current_position) < Decimal("0.01"):
            return False

        # 判断当前方向
        if current_position > 0:
            current_side = "long"
        else:
            current_side = "short"

        # 如果方向相反，需要反向
        return current_side != profitable_side

    @staticmethod
    def estimate_daily_profit(
        spread: FundingRateSpread,
        position_size: Decimal
    ) -> Decimal:
        """
        估算每日收益。

        收益 = abs(daily_spread) × position_size

        Args:
            spread: 费率差信息
            position_size: 仓位大小（USD）

        Returns:
            Decimal: 预估每日收益（USD）
        """
        return abs(spread.daily_spread) * position_size


# 示例使用
if __name__ == "__main__":
    from hedge.funding_rate_normalizer import (
        FundingRateData,
        FundingRateNormalizer
    )

    # 示例：GRVT 0.01% (8小时) vs Lighter 0.005% (1小时)
    grvt = FundingRateData(
        rate=Decimal("0.0001"),  # 0.01%
        interval_hours=8,
        exchange_name="GRVT"
    )

    lighter = FundingRateData(
        rate=Decimal("0.00005"),  # 0.005%
        interval_hours=1,
        exchange_name="Lighter"
    )

    # 计算归一化费率差
    spread = FundingRateNormalizer.calculate_spread(grvt, lighter)

    print("=== Funding Rate Spread Analysis ===")
    print(FundingRateNormalizer.format_rate_info(spread))
    print()

    # 模拟仓位状态
    position = PositionState(
        grvt_position=Decimal("0"),
        lighter_position=Decimal("0")
    )

    # 检查套利机会
    check_result = FundingRateChecker.check_funding_opportunity(
        spread=spread,
        position=position,
        build_threshold_apr=Decimal("0.05"),    # 5% APR
        close_threshold_apr=Decimal("0.02"),    # 2% APR
        max_position=Decimal("10")
    )

    print(f"Action: {check_result.action.value}")
    print(f"Reason: {check_result.reason}")
    print(f"Profitable Side: {check_result.profitable_side.upper()}")
    print()

    # 估算收益
    if check_result.action == FundingAction.BUILD:
        daily_profit = FundingRateChecker.estimate_daily_profit(
            spread=spread,
            position_size=Decimal("1000")
        )
        print(f"Estimated daily profit on $1000: ${daily_profit:.2f}")
