# 已废弃代码 (Deprecated Code)

⚠️ **此目录下的代码已被新的Atomic框架取代，仅保留作为参考**

## 内容

### 老Bot实现
- `hedge_bot_funding.py` - 硬编码GRVT+Lighter的老Bot
- `hedge_bot_v3.py` - 更老的版本

### 老策略模块 (hedge/)
- `trading_executor.py` - 硬编码的交易执行器
- `funding_rate_checker.py` - 费率检查器
- `funding_rate_normalizer.py` - 费率标准化
- `safety_checker.py` - 安全检查器
- `rebalancer.py` - 再平衡器
- `phase_detector.py` - 阶段检测

## 为什么废弃？

### 主要问题
1. **硬编码交易所** - 只支持GRVT和Lighter两个固定交易所
2. **数据结构耦合** - `PositionState(grvt_position, lighter_position)`
3. **扩展性差** - 添加新交易所需要大量修改代码
4. **无法自动选择** - 不能自动发现最佳套利对

### 代码示例（问题所在）

```python
# ❌ 老架构的问题

# 1. 硬编码交易所
class TradingExecutor:
    def __init__(self, grvt_client, lighter_client):
        self.grvt = grvt_client      # 绑定GRVT
        self.lighter = lighter_client # 绑定Lighter

# 2. 数据结构绑定
class PositionState(NamedTuple):
    grvt_position: Decimal
    lighter_position: Decimal

# 3. 决策逻辑耦合
def check_funding_opportunity(
    spread: FundingRateSpread,  # 包含grvt/lighter字段
    position: PositionState      # 包含grvt/lighter字段
):
    # 硬编码使用grvt和lighter
    pass
```

## 新架构在哪里？

✅ **使用新的Atomic框架**

位置：`/home/lantern/src/atomic/`

新Bot：`/home/lantern/src/hedge_bot_atomic.py`

文档：
- `/home/lantern/src/atomic/README.md` - 框架详细文档
- `/home/lantern/ATOMIC_MIGRATION_GUIDE.md` - 迁移指南
- `/home/lantern/PROJECT_STRUCTURE.md` - 项目结构

## 如果需要参考

这些代码保留用于：
1. **参考旧逻辑** - 如果需要查看之前的实现思路
2. **紧急回滚** - 如果新架构出现问题需要临时回退
3. **学习对比** - 理解新旧架构的差异

## 删除计划

计划在新架构稳定运行1个月后删除此目录（预计2025年12月）

## 不要使用！

⚠️ **请勿在新代码中引用此目录下的任何模块**

如果你看到代码中有：
```python
from hedge.trading_executor import TradingExecutor  # ❌ 不要这样
from deprecated.hedge.xxx import xxx                 # ❌ 不要这样
```

应该使用：
```python
from atomic import AtomicTrader, ArbitrageOrchestrator  # ✅ 用这个
```

---

最后更新：2025-11-02
移动原因：架构重构为原子化框架
负责人：Claude Code
