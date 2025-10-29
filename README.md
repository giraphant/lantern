# Lantern Hedge Trading Bot

基于V3架构的对冲交易机器人，支持GRVT和Lighter交易所。

## 📁 项目结构

```
lantern/
├── src/                  # 源代码
│   ├── hedge/           # 对冲交易核心
│   │   ├── core/        # 交易引擎
│   │   ├── services/    # 服务层（HedgeService）
│   │   ├── managers/    # 管理器（SafetyManager）
│   │   ├── models/      # 数据模型
│   │   └── hedge_bot.py # 主程序入口
│   ├── exchanges/       # 交易所接口
│   └── helpers/         # 辅助工具（日志、通知）
│
├── tests/               # 测试文件
├── config/              # 配置文件
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── docs/                # 文档
├── run_hedge.py        # 运行脚本
└── requirements.txt    # 依赖
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

创建`.env`文件：

```env
# GRVT配置
GRVT_API_KEY=your_key
GRVT_PRIVATE_KEY=your_private_key

# Lighter配置
API_KEY_PRIVATE_KEY=your_lighter_api_private_key
LIGHTER_ACCOUNT_INDEX=your_account_index
LIGHTER_API_KEY_INDEX=4

# 交易参数
SYMBOL=BTC
SIZE=0.3
TARGET_CYCLES=5
MAX_POSITION=10.0
REBALANCE_TOLERANCE=0.5
```

### 3. 运行

```bash
python run_hedge.py
```

或使用Docker：

```bash
docker-compose -f config/docker-compose.yml up
```

## 🏗️ V3架构

### 核心组件

1. **HedgeService** - 对冲服务抽象层
   - 定义统一的对冲操作接口
   - 隐藏具体交易所实现细节

2. **TradingEngine** - 交易引擎
   - 管理交易状态（IDLE → BUILDING → HOLDING → WINDING_DOWN）
   - 纯业务逻辑，不依赖具体实现

3. **SafetyManager** - 安全管理
   - 分级安全响应（NORMAL → WARNING → AUTO_REBALANCE → PAUSE → EMERGENCY）
   - 仓位限制和风险控制

4. **GrvtLighterHedgeService** - 具体实现
   - GRVT作为做市商（post-only）
   - Lighter作为吃单商（market taker）

### 特点

- ✅ 清晰的分层架构
- ✅ 复用现有交易所实现
- ✅ 无状态设计，支持崩溃恢复
- ✅ 基于仓位的进度跟踪
- ✅ 完善的安全机制

## 📊 监控

支持Telegram和Lark通知，在`.env`中配置：

```env
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
```

## 📝 许可

MIT License