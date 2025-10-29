# V3架构重构总结

## 架构改进

### 之前的问题（V2）
1. **重复造轮子**：OrderManager和PositionManager重新实现了exchanges/目录下已有的功能
2. **过度耦合**：各个Manager直接操作交易所客户端，职责不清
3. **代码"浆糊在一起"**：缺乏清晰的抽象层次

### 新架构（V3）的解决方案

```
应用层（TradingEngine）
    ↓
服务层（HedgeService接口）
    ↓
实现层（GrvtLighterHedgeService）
    ↓
交易所层（复用现有的GrvtClient和SignerClient）
```

## 核心组件

### 1. HedgeService（抽象接口）
- **文件**: `hedge/services/hedge_service.py`
- **职责**: 定义对冲操作的抽象接口
- **主要方法**:
  - `get_positions()` - 获取当前仓位
  - `execute_hedge_cycle()` - 执行对冲周期
  - `rebalance_positions()` - 重平衡仓位
  - `close_all_positions()` - 紧急平仓

### 2. GrvtLighterHedgeService（具体实现）
- **文件**: `hedge/services/grvt_lighter_service.py`
- **职责**: 使用现有交易所客户端实现对冲逻辑
- **特点**:
  - 直接复用`exchanges/grvt.py`和`lighter/signer_client.py`
  - 不重新实现已有功能
  - 处理GRVT和Lighter之间的协调

### 3. TradingEngine（业务引擎）
- **文件**: `hedge/core/trading_engine.py`
- **职责**: 纯业务逻辑，不关心具体实现
- **状态管理**:
  - IDLE → BUILDING → HOLDING → WINDING_DOWN
  - 基于仓位的进度跟踪（不依赖计数）

### 4. SafetyManager（安全管理）
- **文件**: `hedge/managers/safety_manager.py`
- **保留并增强**:
  - 分级安全响应（NORMAL → WARNING → AUTO_REBALANCE → PAUSE → EMERGENCY）
  - 集中的安全检查
  - 明确的阈值管理

## 主要改进

### 1. 代码复用
- ✅ 完全复用现有交易所实现
- ✅ 删除了冗余的OrderManager和PositionManager
- ✅ 减少代码重复

### 2. 解耦
- ✅ TradingEngine只依赖HedgeService接口
- ✅ 具体实现细节被隔离在服务层
- ✅ 易于扩展新的交易所组合

### 3. 安全性
- ✅ 保留所有安全检查
- ✅ 更清晰的错误边界
- ✅ 支持事务性操作和回滚

### 4. 可维护性
- ✅ 清晰的分层架构
- ✅ 职责单一
- ✅ 更容易测试和调试

## 文件变更

### 新增文件
- `hedge/services/__init__.py`
- `hedge/services/hedge_service.py`
- `hedge/services/grvt_lighter_service.py`
- `hedge/core/trading_engine.py`
- `hedge/hedge_bot_v3.py`

### 删除文件（移至deprecated/）
- `hedge/managers/order_manager.py`
- `hedge/managers/position_manager.py`

### 更新文件
- `hedge/managers/safety_manager.py` - 添加SafetyLevel枚举
- `hedge/models/__init__.py` - 更新TradingConfig
- `docker-compose.yml` - 更新环境变量
- `Dockerfile` - 使用hedge_bot_v3.py

## 使用方式

### Docker启动
```bash
docker-compose up --build
```

### 直接运行
```bash
python3 hedge/hedge_bot_v3.py
```

### 环境变量
```env
# GRVT配置
GRVT_API_KEY=xxx
GRVT_PRIVATE_KEY=xxx

# Lighter配置
LIGHTER_API_KEY=xxx
LIGHTER_PRIVATE_KEY=xxx

# 交易参数
SYMBOL=BTC
SIZE=0.3
TARGET_CYCLES=5
MAX_POSITION=10.0
REBALANCE_TOLERANCE=0.5
```

## 测试

运行架构测试：
```bash
python3 test_v3_basic.py
```

## 总结

V3架构成功解决了"代码浆糊在一起"的问题，通过清晰的分层和抽象，实现了：
1. 更好的代码复用
2. 更低的耦合度
3. 更高的可维护性
4. 保持了原有的安全性

这个架构现在更加"原子化"，每个组件职责明确，易于理解和扩展。