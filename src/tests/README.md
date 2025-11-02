# Atomic Framework Unit Tests

## 📊 测试覆盖

### 已完成测试
| 模块 | 测试文件 | 测试数量 | 状态 |
|------|---------|---------|------|
| `atomic.models` | `test_models.py` | 47 | ✅ 100% |
| `atomic.decisions` | `test_decisions.py` | 19 | ✅ 100% |

**总计**: 66个测试，全部通过 ✅

### 待完成测试
| 模块 | 优先级 | 说明 |
|------|-------|------|
| `atomic.aggregators` | 高 | 需要mock AtomicQueryer |
| `atomic.operations` | 高 | 需要mock exchange clients |
| `atomic.orchestrator` | 中 | 需要完整的集成测试 |

## 🧪 运行测试

### 运行所有测试
```bash
cd /home/lantern/src
python3 -m pytest tests/ -v
```

### 运行特定模块
```bash
# 只测试models
python3 -m pytest tests/test_models.py -v

# 只测试decisions
python3 -m pytest tests/test_decisions.py -v
```

### 详细输出
```bash
python3 -m pytest tests/ -v --tb=short
```

## ✅ 测试覆盖详情

### test_models.py (47个测试)

#### ExchangeIdentifier (7个测试)
- ✅ 创建（有/无instance_id）
- ✅ 字符串表示
- ✅ 哈希和字典键
- ✅ 不可变性（frozen）

#### Symbol (4个测试)
- ✅ 创建和字符串表示
- ✅ 哈希
- ✅ 不可变性

#### Position (10个测试)
- ✅ 创建多头/空头仓位
- ✅ signed_quantity属性（正负值）
- ✅ value计算
- ✅ is_empty判断
- ✅ 自动时间戳

#### FundingRate (4个测试)
- ✅ 创建
- ✅ annual_rate计算（8小时/1小时周期）
- ✅ daily_rate计算

#### Order (8个测试)
- ✅ 创建各种状态的订单
- ✅ remaining_quantity计算
- ✅ is_complete判断
- ✅ fill_percentage计算

#### Market (5个测试)
- ✅ 创建市场数据
- ✅ mid_price计算
- ✅ spread计算
- ✅ spread_bps计算

#### TradeLeg (2个测试)
- ✅ 创建交易腿
- ✅ 字符串表示

#### TradingSignal (5个测试)
- ✅ 创建交易信号
- ✅ exchange_count统计
- ✅ is_hedge判断
- ✅ 字符串表示

#### ArbitrageConfig (2个测试)
- ✅ 创建配置
- ✅ 默认值

### test_decisions.py (19个测试)

#### FundingArbitrageDecision (6个测试)
- ✅ 交易所数量不足
- ✅ BUILD信号生成
- ✅ WINDDOWN信号生成
- ✅ HOLD情况（无信号）
- ✅ 仓位限制阻止BUILD
- ✅ 寻找最佳费率对

#### RebalanceDecision (5个测试)
- ✅ 交易所数量不足
- ✅ 平衡仓位（无需再平衡）
- ✅ 净多头需要再平衡
- ✅ 净空头需要再平衡
- ✅ 数量限制为trade_size

#### SafetyDecision (7个测试)
- ✅ 仓位限制检查（安全）
- ✅ 单个交易所限制超出
- ✅ 总敞口限制超出
- ✅ 挂单数量检查（安全）
- ✅ 挂单数量超出
- ✅ 多个交易所超出

#### ActionType (1个测试)
- ✅ 枚举类型存在和值

## 🎯 测试原则

### 1. 完全隔离
每个测试独立运行，不依赖其他测试

### 2. 纯函数优先
`models.py` 和 `decisions.py` 是纯数据/纯函数，最容易测试到100%

### 3. Mock外部依赖
`aggregators.py` 和 `operations.py` 需要mock交易所客户端

### 4. 边界条件
测试边界情况：
- 空值、零值
- 极大/极小值
- 错误输入

## 📈 测试覆盖目标

### 当前状态
```
atomic/models.py      100% ✅
atomic/decisions.py   100% ✅
atomic/aggregators.py   0% ⏳
atomic/operations.py    0% ⏳
atomic/orchestrator.py  0% ⏳
```

### 目标: 100% 覆盖
所有核心模块达到100%测试覆盖

## 🔧 测试工具

### pytest
```bash
pip install pytest
```

### pytest-cov (可选，用于覆盖率报告)
```bash
pip install pytest-cov

# 生成覆盖率报告
python3 -m pytest tests/ --cov=atomic --cov-report=html
```

### pytest-asyncio (用于异步测试)
```bash
pip install pytest-asyncio
```

## 📝 编写新测试

### 示例: 测试纯函数
```python
def test_function_name():
    """Test description"""
    # Arrange
    input_data = ...

    # Act
    result = function(input_data)

    # Assert
    assert result == expected
```

### 示例: 测试数据类
```python
def test_dataclass_creation():
    """Test creating dataclass"""
    obj = MyDataClass(field1="value", field2=123)
    assert obj.field1 == "value"
    assert obj.field2 == 123
```

### 示例: 使用fixture
```python
@pytest.fixture
def config():
    return ArbitrageConfig(
        build_threshold=Decimal("0.05"),
        close_threshold=Decimal("0.02"),
        max_position=Decimal("10"),
        trade_size=Decimal("0.1")
    )

def test_with_fixture(config):
    assert config.build_threshold == Decimal("0.05")
```

## 🚀 持续集成

测试应该在每次代码提交前运行：

```bash
# 快速检查
python3 -m pytest tests/ -x  # 遇到第一个失败就停止

# 完整测试
python3 -m pytest tests/ -v

# 只运行失败的测试
python3 -m pytest tests/ --lf
```

## 📚 参考

- [pytest文档](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [pytest-cov](https://pytest-cov.readthedocs.io/)

---

最后更新: 2025-11-02
测试数量: 66个
通过率: 100% ✅
