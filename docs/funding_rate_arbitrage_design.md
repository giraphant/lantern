# 资金费率套利策略设计文档

## 1. 策略概述

### 核心思路
利用GRVT和Lighter之间的资金费率差异进行套利：
- 当费率差足够大时建仓（一方收费率，另一方付费率）
- 持仓期间持续积累费率收益
- 当费率差缩小或仓位达上限时平仓

### 与现有对冲策略的区别

| 维度 | 时间对冲策略 | 资金费率套利策略 |
|------|------------|----------------|
| **触发条件** | 基于时间 | 基于费率差 |
| **BUILD** | 仓位 < target | funding_rate_spread > threshold |
| **HOLDING** | 固定时间（180s） | 动态，只要费率差够大 |
| **WINDDOWN** | 超时 | 费率差 < threshold OR 仓位达上限 |
| **仓位大小** | 固定 order_size × cycles | 动态根据费率和风险 |

---

## 2. 技术架构

### 2.1 模块设计

```
src/
├── hedge/
│   ├── funding_rate_checker.py      # 新增：费率检查器（纯函数）
│   ├── phase_detector.py            # 修改：支持funding_rate模式
│   ├── safety_checker.py            # 复用：安全检查
│   ├── rebalancer.py                # 复用：再平衡
│   └── trading_executor.py          # 复用：交易执行
├── exchanges/
│   ├── base.py                      # 修改：添加get_funding_rate()
│   ├── grvt.py                      # 修改：实现get_funding_rate()
│   └── lighter.py                   # 修改：实现get_funding_rate()
├── hedge_bot_v3.py                  # 现有：时间对冲策略
└── hedge_bot_funding.py             # 新增：资金费率套利主程序
```

### 2.2 新增数据结构

```python
# funding_rate_checker.py

class FundingRateInfo(NamedTuple):
    """资金费率信息"""
    grvt_rate: Decimal          # GRVT的资金费率
    lighter_rate: Decimal       # Lighter的资金费率
    spread: Decimal             # 费率差 (grvt_rate - lighter_rate)
    next_funding_time: datetime # 下次结算时间

class FundingRateCheckResult(NamedTuple):
    """费率检查结果"""
    should_build: bool          # 是否应该建仓
    should_winddown: bool       # 是否应该平仓
    reason: str                 # 原因
    spread: Decimal             # 当前费率差
```

---

## 3. 核心逻辑实现

### 3.1 FundingRateChecker（纯函数）

```python
class FundingRateChecker:
    """资金费率检查器 - 纯函数式设计"""

    @staticmethod
    def check_funding_rate(
        funding_info: FundingRateInfo,
        build_threshold: Decimal,      # 建仓阈值（如0.01% = 0.0001）
        close_threshold: Decimal,      # 平仓阈值（如0.005% = 0.00005）
        position: PositionState,
        max_position: Decimal
    ) -> FundingRateCheckResult:
        """
        检查资金费率是否满足交易条件

        判断逻辑：
        1. spread > build_threshold AND position < max → BUILD
        2. spread < close_threshold OR position >= max → WINDDOWN
        3. 其他 → HOLD
        """
        spread = abs(funding_info.spread)
        current_position = abs(position.total_position)

        # 判断1: 费率差足够大 + 仓位未满 → BUILD
        if spread >= build_threshold and current_position < max_position:
            return FundingRateCheckResult(
                should_build=True,
                should_winddown=False,
                reason=f"Funding spread {spread:.4%} >= threshold {build_threshold:.4%}",
                spread=spread
            )

        # 判断2: 费率差太小 OR 仓位达上限 → WINDDOWN
        if spread < close_threshold or current_position >= max_position:
            reason = "Funding spread too small" if spread < close_threshold else "Position limit reached"
            return FundingRateCheckResult(
                should_build=False,
                should_winddown=True,
                reason=f"{reason} (spread={spread:.4%})",
                spread=spread
            )

        # 判断3: 持有
        return FundingRateCheckResult(
            should_build=False,
            should_winddown=False,
            reason=f"Holding position (spread={spread:.4%})",
            spread=spread
        )
```

### 3.2 PhaseDetector扩展

修改 `detect_phase()` 支持两种模式：

```python
@staticmethod
def detect_phase(
    position: PositionState,
    # 时间模式参数
    target_cycles: Optional[int] = None,
    order_size: Optional[Decimal] = None,
    hold_time: Optional[int] = None,
    last_order_time: Optional[datetime] = None,
    # 资金费率模式参数
    funding_rate_info: Optional[FundingRateInfo] = None,
    funding_build_threshold: Optional[Decimal] = None,
    funding_close_threshold: Optional[Decimal] = None,
    max_position: Optional[Decimal] = None
) -> PhaseInfo:
    """
    原子化判断：这一轮该做什么？

    支持两种模式：
    1. 时间模式（原有逻辑）
    2. 资金费率模式（新增）
    """
    # 判断使用哪种模式
    if funding_rate_info is not None:
        # 资金费率模式
        return PhaseDetector._detect_phase_funding_rate(...)
    else:
        # 时间模式（原有逻辑）
        return PhaseDetector._detect_phase_time_based(...)
```

### 3.3 Exchange层实现

```python
# base.py
class BaseExchangeClient(ABC):
    @abstractmethod
    async def get_funding_rate(self, contract_id: str) -> Decimal:
        """获取当前资金费率"""
        pass

# grvt.py
async def get_funding_rate(self, contract_id: str) -> Decimal:
    """获取GRVT资金费率"""
    # 调用GRVT SDK获取funding rate
    funding_info = self.rest_client.fetch_funding_rate(symbol=contract_id)
    return Decimal(str(funding_info['funding_rate']))

# lighter.py
async def get_funding_rate(self, contract_id: str) -> Decimal:
    """获取Lighter资金费率"""
    # 调用Lighter API获取funding rate
    market_api = lighter.MarketApi(self.api_client)
    market_info = await market_api.market(market_id=contract_id)
    return Decimal(str(market_info.funding_rate))
```

---

## 4. 主程序实现

### hedge_bot_funding.py

```python
class HedgeBotFunding:
    """资金费率套利机器人"""

    def __init__(self):
        self.load_config()
        # 资金费率特定配置
        self.funding_build_threshold = Decimal(os.getenv("FUNDING_BUILD_THRESHOLD", "0.0001"))  # 0.01%
        self.funding_close_threshold = Decimal(os.getenv("FUNDING_CLOSE_THRESHOLD", "0.00005")) # 0.005%
        self.max_position = Decimal(os.getenv("MAX_POSITION", "10"))
        self.check_interval = int(os.getenv("FUNDING_CHECK_INTERVAL", "300"))  # 5分钟检查一次

    async def run(self):
        """主循环"""
        while True:
            # 步骤1: 获取仓位
            position = await self.executor.get_positions()

            # 步骤2: 安全检查（复用现有逻辑）
            safety_result = SafetyChecker.check_all(...)
            if safety_result.action != SafetyAction.CONTINUE:
                # 处理安全问题
                continue

            # 步骤3: 获取资金费率
            grvt_rate = await self.grvt.get_funding_rate(self.grvt.config.contract_id)
            lighter_rate = await self.lighter.get_funding_rate(self.lighter.config.contract_id)

            funding_info = FundingRateInfo(
                grvt_rate=grvt_rate,
                lighter_rate=lighter_rate,
                spread=grvt_rate - lighter_rate,
                next_funding_time=...
            )

            # 步骤4: 检查是否需要交易
            funding_check = FundingRateChecker.check_funding_rate(
                funding_info=funding_info,
                build_threshold=self.funding_build_threshold,
                close_threshold=self.funding_close_threshold,
                position=position,
                max_position=self.max_position
            )

            self.logger.info(f"💰 Funding: GRVT={grvt_rate:.4%}, Lighter={lighter_rate:.4%}, "
                           f"Spread={funding_info.spread:.4%} | {funding_check.reason}")

            # 步骤5: 执行交易
            if funding_check.should_build:
                await self._handle_building_phase(position)
            elif funding_check.should_winddown:
                await self._handle_winddown_phase(position)
            else:
                # 持有，等待下次检查
                await asyncio.sleep(self.check_interval)
```

---

## 5. 配置参数

### 环境变量

```bash
# 基础配置（复用现有）
GRVT_API_KEY=...
GRVT_PRIVATE_KEY=...
LIGHTER_PRIVATE_KEY=...
TRADING_SYMBOL=BTC

# 资金费率特定配置
FUNDING_BUILD_THRESHOLD=0.0001    # 0.01% - 建仓阈值
FUNDING_CLOSE_THRESHOLD=0.00005   # 0.005% - 平仓阈值
MAX_POSITION=10                    # 最大仓位
TRADING_SIZE=0.1                   # 每次交易大小
FUNDING_CHECK_INTERVAL=300         # 检查间隔（秒）
TRADING_DIRECTION=long             # 费率为正时做多还是做空
```

---

## 6. 优势分析

### 6.1 架构复用
- ✅ 复用 `SafetyChecker` - 仓位安全检查
- ✅ 复用 `Rebalancer` - 不平衡处理
- ✅ 复用 `TradingExecutor` - 交易执行
- ✅ 复用 Exchange clients - 统一接口

### 6.2 独立性
- ✅ 独立的主程序 `hedge_bot_funding.py`
- ✅ 独立的配置参数
- ✅ 不影响现有的时间对冲策略
- ✅ 可以同时运行两种策略（不同Docker）

### 6.3 灵活性
- ✅ 纯函数设计，易于测试
- ✅ 阈值可配置
- ✅ 检查间隔可调整
- ✅ 支持多币种

---

## 7. 风险控制

### 7.1 费率反转风险
- 定期检查费率差
- 费率差低于阈值立即平仓
- 避免长期持仓

### 7.2 仓位风险
- 设置最大仓位限制
- 复用现有安全检查机制
- 仓位达上限停止建仓

### 7.3 滑点风险
- 使用 Lighter 市价单快速成交
- GRVT 使用 post-only 订单优化成本

---

## 8. 实施计划

### Phase 1: 基础实现（1-2天）
1. ✅ 创建新分支 `feature/funding-rate-arbitrage`
2. 在 BaseExchangeClient 添加 `get_funding_rate()`
3. 实现 GRVT 和 Lighter 的 funding rate 获取
4. 创建 `FundingRateChecker` 模块

### Phase 2: 集成测试（1天）
5. 创建 `hedge_bot_funding.py`
6. 添加配置和环境变量
7. 本地测试费率获取和判断逻辑

### Phase 3: 部署验证（1天）
8. 小仓位测试
9. 监控费率变化和交易行为
10. 优化阈值参数

---

## 9. 示例交易流程

```
时间    | GRVT费率 | Lighter费率 | 费率差  | 仓位 | 操作
--------|---------|------------|--------|-----|------
00:00   | +0.015% | +0.002%    | 0.013% | 0   | BUILD（差值>0.01%）
00:05   | +0.014% | +0.003%    | 0.011% | 1   | BUILD
00:10   | +0.013% | +0.004%    | 0.009% | 2   | HOLD（差值在阈值之间）
00:15   | +0.012% | +0.005%    | 0.007% | 2   | HOLD
00:20   | +0.008% | +0.006%    | 0.002% | 2   | WINDDOWN（差值<0.005%）
00:25   | +0.007% | +0.007%    | 0.000% | 1   | WINDDOWN
00:30   | +0.006% | +0.008%    | -0.002%| 0   | 完成平仓
```

---

## 10. 监控指标

- 当前费率差
- 累计费率收益
- 建仓/平仓次数
- 平均持仓时间
- 费率差变化趋势
