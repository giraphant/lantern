# Atomic Trading Framework

原子化交易框架 - 完全解耦的交易系统架构

## 🎯 核心理念

**原子化**：将所有操作拆分为最小的、不可再分的原子单元，然后通过组合实现复杂功能。

### 设计原则

1. **单一职责** - 每个类只做一件事
2. **交易所无关** - 不绑定任何具体交易所
3. **数据驱动** - 决策基于数据，不是硬编码逻辑
4. **纯函数** - 决策层完全无副作用
5. **可组合** - 通过组合原子操作实现复杂策略

## 📐 架构层次

```
┌─────────────────────────────────────────────┐
│ Layer 5: 编排层 (Orchestrator)               │
│   - ArbitrageOrchestrator                   │
│   - SimpleStrategyRunner                    │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│ Layer 4: 决策层 (Decisions)                  │
│   - FundingArbitrageDecision (纯函数)        │
│   - RebalanceDecision (纯函数)               │
│   - SafetyDecision (纯函数)                  │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│ Layer 3: 聚合层 (Aggregators)                │
│   - PositionAggregator                      │
│   - FundingRateAggregator                   │
│   - MarketAggregator                        │
│   - OrderAggregator                         │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│ Layer 2: 原子操作层 (Operations)             │
│   - AtomicQueryer (单个交易所查询)           │
│   - AtomicTrader (单个交易所交易)            │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│ Layer 1: 标准化模型 (Models)                 │
│   - Position, FundingRate, Order, Market    │
│   - ExchangeIdentifier, Symbol              │
│   - TradingSignal, TradeLeg                 │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│ Layer 0: 原始适配器 (exchanges/*)            │
│   - GrvtClient, LighterClient, etc.         │
└─────────────────────────────────────────────┘
```

## 🚀 快速开始

### 基本用法

```python
from atomic import (
    Symbol,
    ArbitrageConfig,
    AtomicQueryer,
    AtomicTrader,
    ArbitrageOrchestrator
)
from exchanges.grvt import GrvtClient
from exchanges.lighter import LighterClient

# 1. 定义交易对
symbol = Symbol(base="BTC", quote="USDT", contract_type="PERP")

# 2. 配置策略参数
config = ArbitrageConfig(
    build_threshold=Decimal("0.05"),  # 5% APR
    close_threshold=Decimal("0.02"),  # 2% APR
    max_position=Decimal("10"),
    trade_size=Decimal("0.1")
)

# 3. 初始化交易所客户端（使用现有适配器）
grvt_client = GrvtClient(grvt_config)
lighter_client = LighterClient(lighter_config)

await grvt_client.connect()
await lighter_client.connect()

# 4. 创建原子组件
queryers = {
    "grvt": AtomicQueryer(grvt_client, symbol),
    "lighter": AtomicQueryer(lighter_client, symbol)
}

traders = {
    "grvt": AtomicTrader(grvt_client, symbol),
    "lighter": AtomicTrader(lighter_client, symbol)
}

# 5. 创建编排器
orchestrator = ArbitrageOrchestrator(
    queryers=queryers,
    traders=traders,
    config=config,
    symbol=symbol
)

# 6. 运行策略
orders = await orchestrator.run_strategy_cycle()
```

### 添加新交易所

原子化架构的最大优势：**零代码修改**即可支持新交易所

```python
# 假设你有一个Binance客户端
from exchanges.binance import BinanceClient

binance_client = BinanceClient(binance_config)
await binance_client.connect()

# 直接添加到queryers和traders
queryers["binance"] = AtomicQueryer(binance_client, symbol)
traders["binance"] = AtomicTrader(binance_client, symbol)

# 策略会自动发现并使用Binance！
# 它会自动找到最佳套利对（可能是 GRVT-Binance 或 Lighter-Binance）
```

## 💡 核心概念

### 1. 原子数据模型

所有数据都表示**单个实体**，不是"对"或"组"：

```python
# ✅ 原子化：单个交易所的单个仓位
position = Position(
    exchange=ExchangeIdentifier("grvt"),
    symbol=Symbol("BTC", "USDT", "PERP"),
    quantity=Decimal("5.0"),
    side="long"
)

# ❌ 老架构：绑定两个交易所
class PositionState(NamedTuple):
    grvt_position: Decimal
    lighter_position: Decimal
```

### 2. 聚合器模式

通过聚合器组合多个原子数据：

```python
# 获取所有交易所的仓位
positions = await position_agg.get_all_positions()
# {"grvt": Position(...), "lighter": Position(...), "binance": Position(...)}

# 计算总敞口（自动聚合）
total_exposure = await position_agg.get_total_exposure()
```

### 3. 纯函数决策

所有策略决策都是纯函数，不依赖全局状态：

```python
# 输入数据 → 输出决策
signal = FundingArbitrageDecision.analyze_opportunity(
    rates=rates,
    positions=positions,
    config=config
)

# signal 可能是 None（无机会）或 TradingSignal（有机会）
```

### 4. 交易信号组合

交易信号可以包含任意数量的"腿"：

```python
# 双边套利（2腿）
signal = TradingSignal(
    legs=[
        TradeLeg(exchange_id="grvt", side="buy", quantity=0.1),
        TradeLeg(exchange_id="lighter", side="sell", quantity=0.1)
    ],
    reason="Funding spread 8% > threshold 5%"
)

# 三角套利（3腿） - 未来扩展
signal = TradingSignal(
    legs=[
        TradeLeg(exchange_id="grvt", side="buy", quantity=0.1),
        TradeLeg(exchange_id="binance", side="sell", quantity=0.1),
        TradeLeg(exchange_id="lighter", side="sell", quantity=0.1)
    ],
    reason="Three-way arbitrage opportunity"
)
```

## 🔍 与旧架构的对比

### 旧架构的问题

```python
# ❌ 硬编码交易所
class TradingExecutor:
    def __init__(self, grvt_client, lighter_client):
        self.grvt = grvt_client
        self.lighter = lighter_client

    async def build_long(self):
        # 必须是GRVT买入 + Lighter卖出
        await self.grvt.place_open_order(...)
        await self.lighter.place_open_order(...)

# ❌ 数据结构绑定交易所
class PositionState(NamedTuple):
    grvt_position: Decimal
    lighter_position: Decimal
```

**问题**：
- 换交易所需要改代码
- 无法支持3个或更多交易所
- 测试困难

### 新架构的优势

```python
# ✅ 完全解耦
orchestrator = ArbitrageOrchestrator(
    queryers={"ex_a": ..., "ex_b": ..., "ex_c": ...},  # 任意数量
    traders={"ex_a": ..., "ex_b": ..., "ex_c": ...},
    config=config,
    symbol=symbol
)

# ✅ 自动发现最佳套利对
signal = FundingArbitrageDecision.analyze_opportunity(
    rates=all_rates,  # 自动组合所有交易所
    positions=all_positions,
    config=config
)
```

**优势**：
- 零代码修改支持新交易所
- 自动发现最佳套利对
- 可以同时监控N个交易所
- 易于测试和Mock

## 📊 数据流示例

```
用户调用:
  orchestrator.run_strategy_cycle()
       ↓
Step 1: 获取数据
  position_agg.get_all_positions()
    ├─ queryer_grvt.get_position() → Position(grvt, long, 5.0)
    └─ queryer_lighter.get_position() → Position(lighter, short, 5.0)
       ↓
  funding_agg.get_all_rates()
    ├─ queryer_grvt.get_funding_rate() → FundingRate(grvt, 0.01%, 8h)
    └─ queryer_lighter.get_funding_rate() → FundingRate(lighter, 0.05%, 1h)
       ↓
Step 2: 决策
  FundingArbitrageDecision.analyze_opportunity(rates, positions, config)
    → 计算费率差: |10.95% - 43.8%| = 32.85% APR
    → 判断: 32.85% >= 5% (build_threshold)
    → 返回: TradingSignal(legs=[...])
       ↓
Step 3: 执行
  orchestrator.execute_signal(signal)
    ├─ trader_grvt.execute_trade(side="buy", qty=0.1)
    └─ trader_lighter.execute_trade(side="sell", qty=0.1)
       ↓
返回: [Order(...), Order(...)]
```

## 🧪 测试

运行测试示例：

```bash
cd /home/lantern/src
python test_atomic_framework.py
```

## 📝 未来扩展

原子化架构天然支持以下扩展（无需修改核心代码）：

1. **更多交易所** - 直接添加到queryers/traders字典
2. **更多策略** - 实现新的Decision类
3. **更复杂的信号** - TradingSignal支持任意数量的腿
4. **风控模块** - 添加新的Aggregator和Decision
5. **回测系统** - Mock AtomicQueryer返回历史数据

## 🔧 注意事项

1. **contract_id映射** - 目前仍需要在适配器层设置contract_id，未来可以优化
2. **错误处理** - 原子操作失败时返回默认值而不是抛异常
3. **并发执行** - execute_signal自动并发执行所有交易腿

## 📚 文件说明

- `models.py` - 原子数据模型定义
- `operations.py` - AtomicQueryer和AtomicTrader实现
- `aggregators.py` - 数据聚合器
- `decisions.py` - 策略决策函数
- `orchestrator.py` - 策略编排器
- `__init__.py` - 公共API导出

## 🎓 哲学

> "Make it work, make it right, make it fast."

这个框架遵循SOLID原则和函数式编程思想：
- **S**ingle Responsibility - 每个类只有一个职责
- **O**pen/Closed - 对扩展开放，对修改封闭
- **L**iskov Substitution - 可以替换任何交易所适配器
- **I**nterface Segregation - 小而专注的接口
- **D**ependency Inversion - 依赖抽象（Symbol）而非具体（"GRVT"）
