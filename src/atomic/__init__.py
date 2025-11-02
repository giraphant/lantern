"""
Atomic Trading Framework - 原子化交易架构

这是一个完全解耦的交易框架，核心特点：

1. 原子化数据模型 - 所有数据都是单个实体（单个交易所、单个仓位）
2. 组合式设计 - 通过组合原子操作实现复杂策略
3. 交易所无关 - 不绑定任何具体交易所
4. 纯函数决策 - 所有策略决策都是纯函数

架构层次：
- Layer 0: 原始适配器 (exchanges/*)
- Layer 1: 标准化模型 (atomic.models)
- Layer 2: 原子操作 (atomic.operations)
- Layer 3: 聚合层 (atomic.aggregators)
- Layer 4: 决策层 (atomic.decisions)
- Layer 5: 编排层 (atomic.orchestrator)
"""

# 数据模型
from atomic.models import (
    # 标识符
    ExchangeIdentifier,
    Symbol,

    # 核心数据
    Position,
    FundingRate,
    Order,
    Market,

    # 交易指令
    TradeLeg,
    TradingSignal,

    # 配置
    ArbitrageConfig
)

# 原子操作
from atomic.operations import (
    AtomicQueryer,
    AtomicTrader
)

# 聚合器
from atomic.aggregators import (
    PositionAggregator,
    FundingRateAggregator,
    MarketAggregator,
    OrderAggregator
)

# 决策
from atomic.decisions import (
    FundingArbitrageDecision,
    RebalanceDecision,
    SafetyDecision,
    ActionType
)

# 编排
from atomic.orchestrator import (
    ArbitrageOrchestrator,
    SimpleStrategyRunner
)


__all__ = [
    # Models
    "ExchangeIdentifier",
    "Symbol",
    "Position",
    "FundingRate",
    "Order",
    "Market",
    "TradeLeg",
    "TradingSignal",
    "ArbitrageConfig",

    # Operations
    "AtomicQueryer",
    "AtomicTrader",

    # Aggregators
    "PositionAggregator",
    "FundingRateAggregator",
    "MarketAggregator",
    "OrderAggregator",

    # Decisions
    "FundingArbitrageDecision",
    "RebalanceDecision",
    "SafetyDecision",
    "ActionType",

    # Orchestrator
    "ArbitrageOrchestrator",
    "SimpleStrategyRunner",
]

__version__ = "0.1.0"
