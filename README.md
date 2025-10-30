# Lantern Hedge Trading Bot V3

基于 V3 简洁架构的对冲交易机器人，支持 GRVT 和 Lighter 交易所。

## 📁 项目结构

```
lantern/
├── src/
│   ├── hedge_bot_v3.py          # 主程序入口
│   ├── hedge/                    # 对冲交易核心模块
│   │   ├── safety_checker.py    # 安全检查（纯函数）
│   │   ├── phase_detector.py    # 阶段检测（纯函数）
│   │   ├── rebalancer.py        # 再平衡计算（纯函数）
│   │   └── trading_executor.py  # 交易执行层
│   ├── exchanges/                # 交易所客户端
│   │   ├── base.py
│   │   ├── grvt.py
│   │   └── lighter.py
│   └── helpers/                  # 辅助工具
│
├── config/                       # 配置文件
├── run_hedge.py                 # 运行脚本
└── requirements.txt             # Python 依赖
```

## 🏗️ V3 架构设计

### 核心原则

1. **完全无状态** - 每次循环从交易所获取真实状态
2. **纯函数设计** - SafetyChecker、PhaseDetector、Rebalancer 都是纯函数
3. **清晰职责分离**：
   - `SafetyChecker`: 安全检查，返回安全动作（CONTINUE/CANCEL_ALL_ORDERS/PAUSE）
   - `PhaseDetector`: 从订单历史判断当前阶段（BUILDING/HOLDING/WINDING_DOWN）
   - `Rebalancer`: 计算如何平衡两边仓位
   - `TradingExecutor`: 执行交易，调用交易所客户端
   - `HedgeBotV3`: 主循环，纯编排逻辑

### 交易流程

```
循环开始
  ↓
1. 获取真实状态（仓位 + 挂单）
  ↓
2. 安全检查 → CANCEL_ALL_ORDERS / PAUSE / CONTINUE
  ↓
3. 检查不平衡 → 如果超过阈值，执行 Rebalancer 打平
  ↓
4. 阶段检测（从订单历史） → BUILDING / HOLDING / WINDING_DOWN
  ↓
5. 根据阶段执行对应操作
   - BUILDING: GRVT 买入 + Lighter 卖出
   - HOLDING: 等待持仓时间
   - WINDING_DOWN: GRVT 卖出 + Lighter 买入
  ↓
循环继续
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

创建 `.env` 文件：

```env
# GRVT 配置（必需）
GRVT_API_KEY=your_grvt_api_key
GRVT_PRIVATE_KEY=your_grvt_private_key_path_or_content
GRVT_TRADING_ACCOUNT_ID=your_trading_account_id
GRVT_ENVIRONMENT=prod  # 可选: prod, testnet, staging, dev

# Lighter 配置（必需）
LIGHTER_PRIVATE_KEY=your_lighter_private_key_hex
LIGHTER_ACCOUNT_INDEX=0  # 默认 0
LIGHTER_API_KEY_INDEX=0  # 默认 0

# 交易参数（可选，有默认值）
TRADING_SYMBOL=BNB       # 默认: BNB
TRADING_SIZE=0.1         # 默认: 0.1（每次交易数量）
CYCLE_TARGET=5           # 默认: 5（目标循环次数）
CYCLE_HOLD_TIME=180      # 默认: 180秒（持仓时间）

# Pushover 推送通知（可选）
PUSHOVER_USER_KEY=your_pushover_user_key
PUSHOVER_API_TOKEN=your_pushover_app_token
```

**获取Pushover配置：**
1. 访问 https://pushover.net/ 注册账户
2. 获取 User Key（在首页显示）
3. 创建应用获取 API Token
4. 配置环境变量后，bot会在发生错误或安全限制时发送推送通知

### 3. 运行

**方式 1: 直接运行**
```bash
python3 run_hedge.py
# 或
python3 src/hedge_bot_v3.py
```

**方式 2: 使用 Screen（推荐）**
```bash
screen -S hedge_bot
python3 src/hedge_bot_v3.py
# Ctrl+A, D 退出 screen
# screen -r hedge_bot 重新进入
```

**方式 3: 后台运行**
```bash
nohup python3 src/hedge_bot_v3.py > hedge_bot.log 2>&1 &
tail -f hedge_bot.log  # 查看日志
```

## 🔒 安全机制

### 自动安全检查

1. **挂单限制**: GRVT 挂单不超过 1 张，超过自动取消所有订单
2. **仓位限制**: 单边最大仓位 = TRADING_SIZE × CYCLE_TARGET × 2
3. **不平衡检查**: 总仓位不平衡超过 TRADING_SIZE 时自动打平
4. **异常处理**: 订单失败自动重试，严重错误暂停交易

### 安全参数（自动计算）

- `max_position_per_side` = TRADING_SIZE × CYCLE_TARGET × 2
- `max_total_position` = TRADING_SIZE × CYCLE_TARGET × 2
- `max_imbalance` = TRADING_SIZE × 3

## 📊 交易特性

- **GRVT**: 做市商（maker），使用 post-only 订单，等待成交
- **Lighter**: 吃单商（taker），使用市价单 + 滑点，立即成交
- **对冲方式**: GRVT 买入时 Lighter 卖出，实现完全对冲
- **循环模式**: 建仓 → 持仓 → 平仓 → 重复

## 🛠️ 故障排查

### 常见问题

1. **连接失败**: 检查 API key 和网络连接
2. **订单不成交**: 检查账户余额和仓位限制
3. **Nonce 错误**: Lighter 链上确认问题，程序会自动重试

### 日志位置

- 控制台输出：实时显示交易状态
- 可选：使用 `> hedge_bot.log` 重定向到文件

## 📝 许可

MIT License
