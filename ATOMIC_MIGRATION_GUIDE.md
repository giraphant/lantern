# Atomic架构迁移指南

## 📋 概览

从硬编码双交易所架构迁移到原子化的多交易所架构。

## 🔄 核心变化

### 1. 文件结构对比

#### 旧架构
```
src/
├── exchanges/          # ✅ 保留不变
│   ├── base.py
│   ├── grvt.py
│   ├── lighter.py
│   └── ...
├── hedge/              # ⚠️  部分过时
│   ├── trading_executor.py      # 硬编码GRVT+Lighter
│   ├── funding_rate_checker.py
│   ├── safety_checker.py        # PositionState绑定两个交易所
│   └── rebalancer.py
└── hedge_bot_funding.py          # ⚠️  硬编码架构
```

#### 新架构
```
src/
├── exchanges/          # ✅ 完全保留
│   └── (不变)
├── atomic/             # ✨ 新增原子化框架
│   ├── models.py                # 原子数据模型
│   ├── operations.py            # 原子操作层
│   ├── aggregators.py           # 聚合层
│   ├── decisions.py             # 决策层
│   ├── orchestrator.py          # 编排层
│   └── README.md
├── hedge/              # ⚠️  保留但不推荐使用
└── hedge_bot_atomic.py # ✨ 新的bot入口
```

## 🔑 关键差异

### 数据结构：从"对"到"原子"

#### 旧架构 ❌
```python
# 硬编码两个交易所
class PositionState(NamedTuple):
    grvt_position: Decimal
    lighter_position: Decimal

class FundingRateSpread(NamedTuple):
    grvt_normalized: NormalizedFundingRate
    lighter_normalized: NormalizedFundingRate
```

**问题**：
- 只能支持GRVT和Lighter
- 换交易所需要改代码
- 无法扩展到3个或更多交易所

#### 新架构 ✅
```python
# 原子化：单个交易所的单个数据
@dataclass
class Position:
    exchange: ExchangeIdentifier  # 任意交易所
    symbol: Symbol
    quantity: Decimal
    side: Literal["long", "short", "none"]

# 通过字典聚合多个原子数据
positions = {
    "grvt": Position(...),
    "lighter": Position(...),
    "binance": Position(...)  # 随意添加！
}
```

**优势**：
- 支持任意数量交易所
- 添加新交易所零代码修改
- 自动发现最佳套利对

### 执行器：从硬编码到组合

#### 旧架构 ❌
```python
class TradingExecutor:
    def __init__(self, grvt_client, lighter_client, logger=None):
        self.grvt = grvt_client      # 绑定具体交易所
        self.lighter = lighter_client

    async def _execute_build_long(self, quantity, ...):
        # 硬编码：GRVT买入 + Lighter卖出
        grvt_result = await self.grvt.place_open_order(...)
        lighter_result = await self.lighter.place_open_order(...)
```

**问题**：
- 必须是GRVT和Lighter组合
- 换成Binance+Backpack需要改代码

#### 新架构 ✅
```python
# 原子操作：单个交易所的单笔交易
class AtomicTrader:
    def __init__(self, exchange_client, symbol):
        self.client = exchange_client  # 任意交易所
        self.symbol = symbol

    async def execute_trade(self, side, quantity, ...):
        # 不知道其他交易所的存在
        return await self.client.place_open_order(...)

# 组合多个原子操作实现策略
traders = {
    "grvt": AtomicTrader(grvt_client, symbol),
    "lighter": AtomicTrader(lighter_client, symbol),
    "binance": AtomicTrader(binance_client, symbol)  # 随意添加
}

# 策略会自动选择最佳组合
```

**优势**：
- 每个AtomicTrader只关心自己的交易所
- 编排层自动组合
- 支持任意交易所组合

### 决策：从耦合到纯函数

#### 旧架构 ❌
```python
# 决策函数知道具体交易所
class FundingRateChecker:
    @staticmethod
    def check_funding_opportunity(
        spread: FundingRateSpread,  # 包含grvt/lighter字段
        position: PositionState,     # 包含grvt/lighter字段
        ...
    ):
        # 使用 spread.grvt_normalized, spread.lighter_normalized
        # 使用 position.grvt_position, position.lighter_position
```

#### 新架构 ✅
```python
# 纯函数：不知道具体交易所名称
class FundingArbitrageDecision:
    @staticmethod
    def analyze_opportunity(
        rates: Dict[str, FundingRate],      # {"ex_a": ..., "ex_b": ...}
        positions: Dict[str, Position],     # {"ex_a": ..., "ex_b": ...}
        config: ArbitrageConfig
    ) -> Optional[TradingSignal]:
        # 自动找费率差最大的两个交易所
        best_pair = _find_best_rate_pair(rates)

        # 生成交易信号（不绑定具体交易所）
        return TradingSignal(
            legs=[
                TradeLeg(exchange_id=exchange_a, side="buy", ...),
                TradeLeg(exchange_id=exchange_b, side="sell", ...)
            ],
            reason="..."
        )
```

**优势**：
- 完全交易所无关
- 自动发现最佳套利对
- 易于测试（纯函数）

## 🚀 如何使用新架构

### 1. 配置交易所（零代码修改）

在`.env`文件中配置：

```bash
# 旧方式（只支持两个固定交易所）
EXCHANGE_A=GRVT
EXCHANGE_B=Lighter

# 新方式（支持任意数量）
EXCHANGES=GRVT,Lighter,Binance,Backpack
```

### 2. 启动bot

```bash
cd /home/lantern/src
./start_atomic_bot.sh
```

或者直接运行：

```bash
python3 hedge_bot_atomic.py
```

### 3. 添加新交易所

假设你要添加OKX：

**旧架构** ❌ 需要改代码：
1. 修改`trading_executor.py`添加okx客户端
2. 修改`PositionState`添加okx_position字段
3. 修改所有使用PositionState的地方
4. 修改`FundingRateSpread`
5. 修改所有决策逻辑...

**新架构** ✅ 零代码修改：
1. 在`exchanges/okx.py`实现OKX适配器（继承BaseExchangeClient）
2. 在`hedge_bot_atomic.py`的`_init_exchange_client`添加OKX初始化
3. 在`.env`添加`EXCHANGES=GRVT,Lighter,OKX`
4. 完成！策略会自动发现OKX并找最佳套利对

## 📊 性能对比

### 扩展性

| 场景 | 旧架构 | 新架构 |
|------|--------|--------|
| 添加第3个交易所 | 需要重构代码 | 零代码修改 |
| 同时监控5个交易所 | 不支持 | ✅ 支持 |
| 自动选择最佳套利对 | 不支持 | ✅ 支持 |
| 三角套利（3腿） | 不支持 | ✅ 支持 |

### 代码复杂度

| 指标 | 旧架构 | 新架构 |
|------|--------|--------|
| 核心代码行数 | ~1500行 | ~1800行 |
| 耦合度 | 高（硬编码） | 低（组合） |
| 可测试性 | 中 | 高（纯函数） |
| 维护成本 | 高 | 低 |

## 🔧 迁移步骤

### 方案1：直接切换（推荐）

1. 备份当前运行的bot
2. 配置`.env`文件
3. 运行`hedge_bot_atomic.py`
4. 观察日志确认正常

### 方案2：并行运行

1. 保持旧bot运行
2. 启动新bot（notification-only模式）
3. 对比两者的决策
4. 确认无误后切换

### 方案3：渐进迁移

1. 先用新框架重写数据聚合部分
2. 保留旧的决策逻辑
3. 逐步替换决策函数
4. 最后替换执行层

## ⚠️ 注意事项

### 1. 适配器层保持不变

所有`exchanges/*.py`文件**完全保留**，不需要修改。新架构通过`AtomicQueryer`和`AtomicTrader`包装现有适配器。

### 2. 配置兼容性

旧的环境变量仍然有效：
- `GRVT_API_KEY`, `LIGHTER_PRIVATE_KEY` 等
- `TRADING_SYMBOL`, `TRADING_SIZE`
- `FUNDING_BUILD_THRESHOLD_APR`

新增环境变量：
- `EXCHANGES` - 要使用的交易所列表（逗号分隔）

### 3. 旧代码保留

`hedge/`目录下的旧代码保留，方便：
- 回滚到旧架构
- 参考旧逻辑
- 渐进迁移

### 4. 日志格式变化

新架构的日志更清晰：

```
旧日志：
2025-11-02 - INFO: GRVT position: 5.0, Lighter position: -5.0

新日志：
2025-11-02 - INFO: 📊 Current State:
2025-11-02 - INFO:   Positions:
2025-11-02 - INFO:     grvt: long 5.0
2025-11-02 - INFO:     lighter: short 5.0
2025-11-02 - INFO:   Total Exposure: 0.0 (imbalance: 0.0)
```

## 🎯 优势总结

### 旧架构的限制
1. ❌ 只能支持2个固定交易所
2. ❌ 换交易所需要改代码
3. ❌ 数据结构硬编码交易所名称
4. ❌ 决策逻辑耦合具体交易所
5. ❌ 无法自动发现最佳套利对

### 新架构的优势
1. ✅ 支持任意数量交易所（2-N个）
2. ✅ 添加交易所零代码修改
3. ✅ 原子化数据模型，完全解耦
4. ✅ 纯函数决策，易于测试
5. ✅ 自动发现最佳套利对
6. ✅ 支持更复杂策略（三角套利等）
7. ✅ 更清晰的代码结构和日志

## 📚 更多文档

- [Atomic框架详细文档](src/atomic/README.md)
- [测试示例](src/test_atomic_framework.py)
- [新bot实现](src/hedge_bot_atomic.py)

## 🤝 反馈

如果遇到问题或有建议，请查看日志文件或提issue。
