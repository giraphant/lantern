# Lantern - 多交易所对冲交易机器人

一个专业的对冲交易机器人，在多个交易所之间维持市场中性仓位。

## 🚀 快速开始

### Docker 部署（推荐）

```bash
# 1. 复制并配置环境变量
cp .env.docker.example .env
# 编辑 .env 文件，填入你的 API 密钥和参数

# 2. 使用 Docker Compose 运行
docker-compose up
```

### 手动安装

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境
cp .env.docker.example .env
# 编辑 .env 文件，配置你的凭证

# 3. 运行机器人（使用V2架构）
python hedge/hedge_bot_v2.py
```

## 🏗️ 架构设计 (V2)

机器人采用模块化架构，安全优先设计：

```
hedge/
├── core/                 # 核心交易逻辑
│   └── trading_state_machine.py
├── managers/            # 专门管理器
│   ├── safety_manager.py      # 安全检查
│   ├── position_manager.py    # 仓位管理
│   └── order_manager.py       # 订单管理
└── models/              # 数据模型
```

### 核心特性

- **安全第一**：每笔交易前进行多层安全检查
- **纯API仓位**：不做本地仓位累积，始终从交易所获取
- **基于仓位的进度**：使用实际仓位计算进度，而非循环计数（V2新特性）
- **自动恢复**：程序重启后自动识别当前进度并继续
- **原子操作**：每个操作要么完全成功，要么完全失败
- **状态机**：清晰的状态转换（建仓 → 持仓 → 平仓）

## ⚙️ 配置说明

### 核心参数

| 参数 | 说明 | 默认值 |
|-----|------|--------|
| `SIZE` | 每笔订单大小 | 0.1 |
| `REBALANCE_TOLERANCE` | 最大仓位偏差 | 0.15 |
| `BUILD_UP_ITERATIONS` | 建仓阶段交易次数 | 30 |
| `HOLD_TIME` | 持仓时间（秒） | 180 |
| `CYCLES` | 循环次数 | 1 |
| `DIRECTION` | 交易方向 | long |

### 安全参数

| 参数 | 说明 | 默认值 |
|-----|------|--------|
| `MAX_POSITION` | 单边最大仓位 | 10 |
| `MAX_OPEN_ORDERS` | 最大挂单数 | 1 |
| `ORDER_TIMEOUT` | 订单超时（秒） | 30 |

## 🔒 安全特性

1. **仓位限制**：永不超过配置的最大仓位
2. **偏差保护**：对冲偏差超过容忍度时停止交易
3. **订单大小限制**：所有订单都受SIZE参数限制
4. **紧急停止**：关键错误时自动停止
5. **无本地状态**：始终使用交易所API获取仓位

## 📊 支持的交易所

- **GRVT**：Post-only maker订单
- **Lighter**：Market taker订单
- **Apex** (Beta)
- **Backpack** (Beta)

## 📚 文档

- [架构设计图](docs/ARCHITECTURE.md)
- [基于仓位的逻辑说明](docs/POSITION_BASED_LOGIC.md) 🆕
- [Docker部署指南](docs/DOCKER.md)
- [English Documentation](docs/README_EN.md)
- [环境配置示例](docs/env_example.txt)

## ⚠️ 重要提醒

- 请先用小额测试
- 监控两个交易所的仓位
- 保持REBALANCE_TOLERANCE在0.1-0.2之间以确保安全
- 生产环境使用V2架构（`hedge_bot_v2.py`）

## 📝 License

MIT