"""
Abstract hedge service interface.

定义对冲交易的抽象接口，不依赖具体交易所实现。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional, Dict, Any
from enum import Enum


class OrderSide(Enum):
    """订单方向"""
    BUY = "buy"
    SELL = "sell"


@dataclass
class HedgePosition:
    """对冲仓位信息"""
    maker_position: Decimal  # 做市商仓位 (GRVT)
    taker_position: Decimal  # 吃单商仓位 (Lighter)

    @property
    def total_position(self) -> Decimal:
        """总仓位"""
        return self.maker_position + self.taker_position

    @property
    def imbalance(self) -> Decimal:
        """仓位不平衡度（应该接近0）"""
        return abs(self.total_position)

    def __str__(self) -> str:
        return (f"Maker={self.maker_position:.4f}, "
                f"Taker={self.taker_position:.4f}, "
                f"Total={self.total_position:.4f}, "
                f"Imbalance={self.imbalance:.4f}")


@dataclass
class HedgeLeg:
    """单边交易结果"""
    success: bool
    exchange: str
    side: OrderSide
    quantity: Decimal
    price: Optional[Decimal] = None
    order_id: Optional[str] = None
    error: Optional[str] = None

    def __str__(self) -> str:
        if self.success:
            return f"{self.exchange}: {self.side.value} {self.quantity} @ {self.price}"
        else:
            return f"{self.exchange}: Failed - {self.error}"


@dataclass
class HedgeResult:
    """对冲操作结果"""
    success: bool
    maker_leg: Optional[HedgeLeg] = None
    taker_leg: Optional[HedgeLeg] = None
    position_after: Optional[HedgePosition] = None
    error: Optional[str] = None

    def __str__(self) -> str:
        if self.success:
            return f"Hedge successful: {self.maker_leg}, {self.taker_leg}"
        else:
            return f"Hedge failed: {self.error}"


class HedgeService(ABC):
    """
    对冲服务抽象接口。

    提供统一的对冲操作接口，隐藏具体交易所的实现细节。
    """

    @abstractmethod
    async def initialize(self) -> None:
        """初始化服务，建立连接等"""
        pass

    @abstractmethod
    async def get_positions(self) -> HedgePosition:
        """
        获取当前对冲仓位。

        Returns:
            HedgePosition: 包含做市商和吃单商的仓位信息
        """
        pass

    @abstractmethod
    async def execute_hedge_cycle(self, direction: str, quantity: Decimal) -> HedgeResult:
        """
        执行一个对冲周期。

        Args:
            direction: "long" 或 "short" - 对冲方向
            quantity: 每边的订单数量

        Returns:
            HedgeResult: 对冲操作结果
        """
        pass

    @abstractmethod
    async def rebalance_positions(self, max_rebalance_size: Optional[Decimal] = None) -> HedgeResult:
        """
        重新平衡仓位，使总仓位接近0。

        Args:
            max_rebalance_size: 最大重平衡数量限制

        Returns:
            HedgeResult: 重平衡操作结果
        """
        pass

    @abstractmethod
    async def close_all_positions(self) -> HedgeResult:
        """
        关闭所有仓位（紧急停止）。

        Returns:
            HedgeResult: 平仓操作结果
        """
        pass

    @abstractmethod
    async def cancel_all_orders(self) -> bool:
        """
        取消所有未成交订单。

        Returns:
            bool: 是否成功取消所有订单
        """
        pass

    @abstractmethod
    async def get_market_info(self) -> Dict[str, Any]:
        """
        获取市场信息（价格、深度等）。

        Returns:
            Dict: 包含市场信息的字典
        """
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """清理资源，关闭连接等"""
        pass