"""
安全检查模块 - 纯函数，只做判断。

职责：
1. 检查仓位是否在安全范围内
2. 检查两边对冲是否平衡
3. 不执行任何交易操作，只返回判断结果
"""

from decimal import Decimal
from enum import Enum
from typing import NamedTuple, Optional


class PositionState(NamedTuple):
    """仓位状态"""
    exchange_a_position: Decimal
    exchange_b_position: Decimal

    # 保持向后兼容的别名
    @property
    def grvt_position(self) -> Decimal:
        """向后兼容：返回exchange_a_position"""
        return self.exchange_a_position

    @property
    def lighter_position(self) -> Decimal:
        """向后兼容：返回exchange_b_position"""
        return self.exchange_b_position

    @property
    def total_position(self) -> Decimal:
        """总仓位"""
        return self.exchange_a_position + self.exchange_b_position

    @property
    def imbalance(self) -> Decimal:
        """不平衡度（绝对值）"""
        return abs(self.total_position)


class SafetyAction(Enum):
    """安全检查后需要的操作"""
    CONTINUE = "CONTINUE"                    # 安全，继续执行
    CANCEL_ALL_ORDERS = "CANCEL_ALL_ORDERS"  # 取消所有挂单
    PAUSE = "PAUSE"                          # 暂停交易


class SafetyCheckResult(NamedTuple):
    """安全检查结果"""
    action: SafetyAction
    reason: Optional[str] = None

    @property
    def is_safe(self) -> bool:
        """是否安全（向后兼容）"""
        return self.action == SafetyAction.CONTINUE


class PendingOrdersInfo(NamedTuple):
    """未成交订单信息"""
    exchange_a_pending_count: int
    exchange_b_pending_count: int

    # 保持向后兼容的别名
    @property
    def grvt_pending_count(self) -> int:
        """向后兼容：返回exchange_a_pending_count"""
        return self.exchange_a_pending_count

    @property
    def lighter_pending_count(self) -> int:
        """向后兼容：返回exchange_b_pending_count"""
        return self.exchange_b_pending_count


class SafetyChecker:
    """
    安全检查器 - 纯函数式设计。

    所有方法都是静态的，不依赖实例状态。
    """

    @staticmethod
    def check_pending_orders(
        pending_orders: PendingOrdersInfo,
        max_pending_per_side: int = 1
    ) -> SafetyCheckResult:
        """
        检查未成交订单数量限制。

        Args:
            pending_orders: 未成交订单信息
            max_pending_per_side: 单边最大未成交订单数

        Returns:
            SafetyCheckResult: 如果挂单超限，返回CANCEL_ALL_ORDERS
        """
        if pending_orders.grvt_pending_count > max_pending_per_side:
            return SafetyCheckResult(
                action=SafetyAction.CANCEL_ALL_ORDERS,
                reason=f"GRVT pending orders {pending_orders.grvt_pending_count} exceeds limit {max_pending_per_side}"
            )

        if pending_orders.lighter_pending_count > max_pending_per_side:
            return SafetyCheckResult(
                action=SafetyAction.CANCEL_ALL_ORDERS,
                reason=f"Lighter pending orders {pending_orders.lighter_pending_count} exceeds limit {max_pending_per_side}"
            )

        return SafetyCheckResult(action=SafetyAction.CONTINUE)

    @staticmethod
    def check_position_limits(
        position: PositionState,
        max_position_per_side: Decimal,
        max_total_position: Decimal
    ) -> SafetyCheckResult:
        """
        检查仓位是否超限。

        Args:
            position: 当前仓位状态
            max_position_per_side: 单边最大仓位
            max_total_position: 总仓位最大值

        Returns:
            SafetyCheckResult
        """
        # 检查单边仓位
        if abs(position.grvt_position) > max_position_per_side:
            return SafetyCheckResult(
                action=SafetyAction.PAUSE,
                reason=f"GRVT position {position.grvt_position} exceeds limit {max_position_per_side}"
            )

        if abs(position.lighter_position) > max_position_per_side:
            return SafetyCheckResult(
                action=SafetyAction.PAUSE,
                reason=f"Lighter position {position.lighter_position} exceeds limit {max_position_per_side}"
            )

        # 检查总仓位
        if abs(position.total_position) > max_total_position:
            return SafetyCheckResult(
                action=SafetyAction.PAUSE,
                reason=f"Total position {position.total_position} exceeds limit {max_total_position}"
            )

        return SafetyCheckResult(action=SafetyAction.CONTINUE)

    @staticmethod
    def check_imbalance(
        position: PositionState,
        max_imbalance: Decimal
    ) -> SafetyCheckResult:
        """
        检查两边对冲是否平衡。

        Args:
            position: 当前仓位状态
            max_imbalance: 允许的最大不平衡度

        Returns:
            SafetyCheckResult
        """
        if position.imbalance > max_imbalance:
            return SafetyCheckResult(
                action=SafetyAction.PAUSE,
                reason=f"Imbalance {position.imbalance} exceeds limit {max_imbalance}"
            )

        return SafetyCheckResult(action=SafetyAction.CONTINUE)

    @staticmethod
    def check_all(
        position: PositionState,
        max_position_per_side: Decimal,
        max_total_position: Decimal,
        max_imbalance: Decimal,
        pending_orders: Optional[PendingOrdersInfo] = None,
        max_pending_per_side: int = 1
    ) -> SafetyCheckResult:
        """
        执行所有安全检查。

        Args:
            position: 当前仓位状态
            max_position_per_side: 单边最大仓位
            max_total_position: 总仓位最大值
            max_imbalance: 允许的最大不平衡度
            pending_orders: 未成交订单信息（可选）
            max_pending_per_side: 单边最大未成交订单数

        Returns:
            SafetyCheckResult
        """
        # 检查挂单限制（优先级最高，立即处理）
        if pending_orders is not None:
            result = SafetyChecker.check_pending_orders(pending_orders, max_pending_per_side)
            if result.action != SafetyAction.CONTINUE:
                return result

        # 检查仓位限制
        result = SafetyChecker.check_position_limits(
            position, max_position_per_side, max_total_position
        )
        if result.action != SafetyAction.CONTINUE:
            return result

        # 检查不平衡
        result = SafetyChecker.check_imbalance(position, max_imbalance)
        if result.action != SafetyAction.CONTINUE:
            return result

        return SafetyCheckResult(action=SafetyAction.CONTINUE)
