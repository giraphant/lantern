"""
原子化数据模型 - 所有数据结构都是单个交易所/单个实体的表示

设计原则:
1. 每个类代表一个"原子"概念（单个交易所的单个实体）
2. 不包含任何业务逻辑，只是数据容器
3. 使用dataclass提供不可变性和类型安全
"""

from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime
from typing import Optional, Literal, List


@dataclass(frozen=True)
class ExchangeIdentifier:
    """
    交易所唯一标识符

    支持同一交易所的多个账户/实例
    """
    name: str                              # "grvt", "lighter", "binance"
    instance_id: Optional[str] = None      # 可选：区分多账户

    def __str__(self) -> str:
        if self.instance_id:
            return f"{self.name}:{self.instance_id}"
        return self.name

    def __hash__(self) -> int:
        return hash((self.name, self.instance_id))


@dataclass(frozen=True)
class Symbol:
    """
    标准化的交易对符号

    统一表示不同交易所的交易对
    """
    base: str                  # "BTC"
    quote: str                 # "USDT", "USD", "USDC"
    contract_type: str         # "PERP", "SPOT", "FUTURE"

    def __str__(self) -> str:
        return f"{self.base}-{self.quote}-{self.contract_type}"

    def __hash__(self) -> int:
        return hash((self.base, self.quote, self.contract_type))


@dataclass
class Position:
    """
    单一交易所的单一仓位（最原子）

    特点：
    - 只表示一个交易所的一个仓位
    - 不知道其他交易所
    - 不包含对冲逻辑
    """
    exchange: ExchangeIdentifier
    symbol: Symbol
    quantity: Decimal                      # 绝对值（>= 0）
    side: Literal["long", "short", "none"] # 方向
    entry_price: Optional[Decimal] = None
    unrealized_pnl: Optional[Decimal] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def signed_quantity(self) -> Decimal:
        """
        带符号的仓位数量

        Returns:
            +quantity for long
            -quantity for short
            0 for none
        """
        if self.side == "long":
            return self.quantity
        elif self.side == "short":
            return -self.quantity
        return Decimal(0)

    @property
    def value(self) -> Optional[Decimal]:
        """仓位名义价值"""
        if self.entry_price is not None:
            return abs(self.quantity) * self.entry_price
        return None

    @property
    def is_empty(self) -> bool:
        """是否空仓"""
        return self.side == "none" or self.quantity == 0


@dataclass
class FundingRate:
    """
    单一交易所的单一资金费率（最原子）

    特点：
    - 只表示一个交易所的费率
    - 包含周期信息
    - 可计算年化费率
    """
    exchange: ExchangeIdentifier
    symbol: Symbol
    rate: Decimal                          # 原始费率 (如 0.0001 = 0.01%)
    interval_hours: int                    # 结算周期（小时）
    next_funding_time: Optional[datetime] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def annual_rate(self) -> Decimal:
        """
        年化费率

        Formula: rate × (24 / interval_hours) × 365
        """
        periods_per_day = Decimal(24) / Decimal(self.interval_hours)
        return self.rate * periods_per_day * Decimal(365)

    @property
    def daily_rate(self) -> Decimal:
        """日化费率"""
        periods_per_day = Decimal(24) / Decimal(self.interval_hours)
        return self.rate * periods_per_day


@dataclass
class Order:
    """
    单一订单（最原子）

    特点：
    - 标准化的订单状态
    - 统一的字段名称
    """
    exchange: ExchangeIdentifier
    symbol: Symbol
    order_id: str
    side: Literal["buy", "sell"]
    quantity: Decimal
    price: Optional[Decimal]               # limit单有价格，market单可能没有
    order_type: Literal["market", "limit", "post_only"]
    status: Literal["pending", "open", "filled", "cancelled", "rejected"]
    filled_quantity: Decimal = field(default=Decimal(0))
    average_fill_price: Optional[Decimal] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def remaining_quantity(self) -> Decimal:
        """剩余未成交数量"""
        return self.quantity - self.filled_quantity

    @property
    def is_complete(self) -> bool:
        """订单是否完成（成交或取消）"""
        return self.status in ("filled", "cancelled", "rejected")

    @property
    def fill_percentage(self) -> Decimal:
        """成交百分比"""
        if self.quantity == 0:
            return Decimal(0)
        return (self.filled_quantity / self.quantity) * Decimal(100)


@dataclass
class Market:
    """
    市场数据快照（最原子）

    特点：
    - 时间点的市场状态
    - 包含最佳买卖价
    - 包含合约规格
    """
    exchange: ExchangeIdentifier
    symbol: Symbol
    best_bid: Optional[Decimal] = None
    best_ask: Optional[Decimal] = None
    last_price: Optional[Decimal] = None
    tick_size: Optional[Decimal] = None
    min_quantity: Optional[Decimal] = None
    max_quantity: Optional[Decimal] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def mid_price(self) -> Optional[Decimal]:
        """中间价"""
        if self.best_bid is not None and self.best_ask is not None:
            return (self.best_bid + self.best_ask) / Decimal(2)
        return None

    @property
    def spread(self) -> Optional[Decimal]:
        """买卖价差"""
        if self.best_bid is not None and self.best_ask is not None:
            return self.best_ask - self.best_bid
        return None

    @property
    def spread_bps(self) -> Optional[Decimal]:
        """价差（基点 basis points）"""
        if self.spread is not None and self.mid_price is not None and self.mid_price > 0:
            return (self.spread / self.mid_price) * Decimal(10000)
        return None


@dataclass
class TradeLeg:
    """
    单腿交易指令（最原子）

    用于组合成复杂的交易策略
    """
    exchange_id: str                       # 交易所名称（字符串，方便查找）
    symbol: Symbol
    side: Literal["buy", "sell"]
    quantity: Decimal
    order_type: Literal["market", "limit", "post_only"] = "post_only"
    price: Optional[Decimal] = None

    def __str__(self) -> str:
        action = "BUY" if self.side == "buy" else "SELL"
        return f"{action} {self.quantity} {self.symbol} @ {self.exchange_id}"


@dataclass
class TradingSignal:
    """
    交易信号（可以包含任意数量的交易腿）

    特点：
    - 不绑定具体交易所数量
    - 可以表示单边、对冲、三角套利等任意策略
    """
    legs: List[TradeLeg]
    reason: str
    confidence: Decimal                    # 0-1之间
    expected_profit: Optional[Decimal] = None
    risk_score: Optional[Decimal] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def exchange_count(self) -> int:
        """涉及的交易所数量"""
        return len(set(leg.exchange_id for leg in self.legs))

    @property
    def is_hedge(self) -> bool:
        """是否是对冲策略（买卖平衡）"""
        buy_qty = sum(leg.quantity for leg in self.legs if leg.side == "buy")
        sell_qty = sum(leg.quantity for leg in self.legs if leg.side == "sell")
        return buy_qty == sell_qty

    def __str__(self) -> str:
        legs_str = " + ".join(str(leg) for leg in self.legs)
        return f"Signal({legs_str}): {self.reason}"


# ==================== 配置数据类 ====================

@dataclass
class ArbitrageConfig:
    """套利策略配置"""
    build_threshold: Decimal               # 建仓阈值（年化费率差）
    close_threshold: Decimal               # 平仓阈值
    max_position: Decimal                  # 单边最大仓位
    trade_size: Decimal                    # 每次交易大小
    max_position_per_exchange: Decimal = field(default=Decimal("999999"))
    max_total_exposure: Decimal = field(default=Decimal("999999"))
    max_imbalance: Decimal = field(default=Decimal("1"))
