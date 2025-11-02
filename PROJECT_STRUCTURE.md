# 项目结构说明

## 🎯 核心架构（使用这些）

### 新架构 - Atomic Framework
```
src/
├── atomic/                          # ✅ 原子化交易框架（核心）
│   ├── models.py                   # 数据模型
│   ├── operations.py               # 原子操作
│   ├── aggregators.py              # 聚合层
│   ├── decisions.py                # 决策层
│   ├── orchestrator.py             # 编排层
│   └── README.md                   # 框架文档
│
├── exchanges/                       # ✅ 交易所适配器（保持不变）
│   ├── base.py                     # 基类
│   ├── grvt.py                     # GRVT适配器
│   ├── lighter.py                  # Lighter适配器
│   ├── binance.py                  # Binance适配器
│   ├── backpack.py                 # Backpack适配器
│   └── ...                         # 其他交易所
│
├── helpers/                         # ✅ 工具类（通知等）
│   ├── pushover_notifier.py
│   ├── telegram_interactive_bot.py
│   └── logger.py
│
├── hedge_bot_atomic.py             # ✅ 新Bot入口（使用这个）
├── test_atomic_framework.py        # ✅ 测试示例
└── start_atomic_bot.sh             # ✅ 启动脚本
```

## 📦 已废弃（不要使用）

```
src/
└── deprecated/                      # ❌ 废弃代码（仅供参考）
    ├── hedge_bot_funding.py        # 老Bot（硬编码GRVT+Lighter）
    ├── hedge_bot_v3.py             # 老版本Bot
    └── hedge/                      # 老策略模块
        ├── trading_executor.py     # 硬编码交易执行器
        ├── funding_rate_checker.py
        ├── safety_checker.py
        └── ...
```

## 🎨 架构对比

### ❌ 老架构（deprecated/）
**特点**：
- 硬编码GRVT和Lighter两个交易所
- `PositionState(grvt_position, lighter_position)`
- `TradingExecutor(grvt_client, lighter_client)`
- 添加新交易所需要改代码

**文件**：
- `deprecated/hedge_bot_funding.py` - 老Bot
- `deprecated/hedge/` - 老策略模块

### ✅ 新架构（atomic/）
**特点**：
- 支持任意数量交易所（2-N个）
- 原子化数据模型：`{"grvt": Position(), "lighter": Position()}`
- 组合式执行器：`{"grvt": AtomicTrader(), ...}`
- 添加新交易所只需修改.env配置
- 自动发现最佳套利对

**文件**：
- `atomic/` - 原子化框架
- `hedge_bot_atomic.py` - 新Bot

## 🚀 使用指南

### 启动新Bot
```bash
cd /home/lantern/src
./start_atomic_bot.sh
```

### 配置文件 (.env)
```bash
# 新架构配置
EXCHANGES=GRVT,Lighter              # 可以添加更多：GRVT,Lighter,Binance,Backpack
TRADING_SYMBOL=BTC
TRADING_SIZE=0.1
FUNDING_BUILD_THRESHOLD_APR=0.05
FUNDING_CLOSE_THRESHOLD_APR=0.02
```

### 添加新交易所（零代码修改）
1. 在 `exchanges/` 实现新的适配器（继承BaseExchangeClient）
2. 在 `hedge_bot_atomic.py` 的 `_init_exchange_client()` 添加初始化逻辑
3. 在 `.env` 添加到 `EXCHANGES` 列表
4. 完成！

## 📊 文件用途清单

### ✅ 必须保留
| 文件 | 用途 | 状态 |
|------|------|------|
| `atomic/*` | 原子化框架核心 | ✅ 使用中 |
| `exchanges/*` | 交易所适配器 | ✅ 使用中 |
| `helpers/*` | 工具类 | ✅ 使用中 |
| `hedge_bot_atomic.py` | 新Bot入口 | ✅ 使用中 |

### ⚠️ 可选保留
| 文件 | 用途 | 状态 |
|------|------|------|
| `test_atomic_framework.py` | 测试示例 | ⚠️ 仅测试用 |
| `start_atomic_bot.sh` | 启动脚本 | ⚠️ 可选 |

### ❌ 已废弃（可删除）
| 文件 | 用途 | 状态 |
|------|------|------|
| `deprecated/hedge_bot_funding.py` | 老Bot | ❌ 已废弃 |
| `deprecated/hedge_bot_v3.py` | 老版本 | ❌ 已废弃 |
| `deprecated/hedge/*` | 老策略模块 | ❌ 已废弃 |

## 🔍 如何判断使用哪个？

**看文件路径**：
- ✅ `atomic/` 开头 → 使用
- ✅ `exchanges/` 开头 → 使用
- ✅ `helpers/` 开头 → 使用
- ✅ `hedge_bot_atomic.py` → 使用
- ❌ `deprecated/` 开头 → 不使用
- ❌ `hedge_bot_funding.py` → 已移到deprecated

## 📝 迁移完成

已完成的清理：
- [x] 移动老Bot到 `deprecated/`
- [x] 移动老策略模块到 `deprecated/hedge/`
- [x] 保留所有交易所适配器（完全兼容）
- [x] 创建新Bot `hedge_bot_atomic.py`
- [x] 创建原子化框架 `atomic/`

## 🎯 核心原则

**记住一个原则**：
- 看到 `atomic/` 或 `hedge_bot_atomic.py` → ✅ 用这个
- 看到 `deprecated/` 或 `hedge/` → ❌ 不要用

**exchanges/ 永远保留**，它是所有架构的基础！
