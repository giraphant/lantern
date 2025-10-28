# Lantern - Advanced Hedge Mode Trading Bot

一个优化的对冲交易机器人，支持GRVT + Lighter对冲策略，专注于市场中性交易和交易量优化。

## 📢 项目说明

本项目是对原始perp-dex-tools的优化和改进版本，主要针对对冲模式（Hedge Mode）进行了大幅增强。

## 🐳 Docker 部署（推荐）

最简单的部署方式是使用Docker：

```bash
# 1. 克隆仓库
git clone https://github.com/giraphant/lantern.git
cd lantern

# 2. 配置环境变量
cp .env.docker.example .env
# 编辑 .env 文件，填入你的API密钥

# 3. 启动
docker-compose up -d

# 4. 查看日志
docker-compose logs -f
```

📖 详细说明请查看 [DOCKER.md](DOCKER.md)

## 手动安装

Python 版本要求（最佳选项是 Python 3.10 - 3.12）：

- grvt 要求 python 版本在 3.10 及以上
- Paradex 要求 python 版本在 3.9 - 3.12
- 其他交易所需要 python 版本在 3.8 及以上

1. **克隆仓库**：

   ```bash
   git clone <repository-url>
   cd perp-dex-tools
   ```

2. **创建并激活虚拟环境**：

   首先确保你目前不在任何虚拟环境中：

   ```bash
   deactivate
   ```

   创建虚拟环境：

   ```bash
   python3 -m venv env
   ```

   激活虚拟环境（每次使用脚本时，都需要激活虚拟环境）：

   ```bash
   source env/bin/activate  # Windows: env\Scripts\activate
   ```

3. **安装依赖**：
   首先确保你目前不在任何虚拟环境中：

   ```bash
   deactivate
   ```

   激活虚拟环境（每次使用脚本时，都需要激活虚拟环境）：

   ```bash
   source env/bin/activate  # Windows: env\Scripts\activate
   ```

   ```bash
   pip install -r requirements.txt
   ```

   **grvt 用户**：如果您想使用 grvt 交易所，需要额外安装 grvt 专用依赖：
   激活虚拟环境（每次使用脚本时，都需要激活虚拟环境）：

   ```bash
   source env/bin/activate  # Windows: env\Scripts\activate
   ```

   ```bash
   pip install grvt-pysdk
   ```

   **Paradex 用户**：如果您想使用 Paradex 交易所，需要额外创建一个虚拟环境并安装 Paradex 专用依赖：

   首先确保你目前不在任何虚拟环境中：

   ```bash
   deactivate
   ```

   创建 Paradex 专用的虚拟环境（名称为 para_env）：

   ```bash
   python3 -m venv para_env
   ```

   激活虚拟环境（每次使用脚本时，都需要激活虚拟环境）：

   ```bash
   source para_env/bin/activate  # Windows: para_env\Scripts\activate
   ```

   安装 Paradex 依赖

   ```bash
   pip install -r para_requirements.txt
   ```

   **apex 用户**：如果您想使用 apex 交易所，需要额外安装 apex 专用依赖：
   激活虚拟环境（每次使用脚本时，都需要激活虚拟环境）：

   ```bash
   source env/bin/activate  # Windows: env\Scripts\activate
   ```

   ```bash
   pip install -r apex_requirements.txt
   ```

4. **设置环境变量**：
   在项目根目录创建`.env`文件，并使用 env_example.txt 作为样本，修改为你的 api 密匙。

5. **Telegram 机器人设置（可选）**：
   如需接收交易通知，请参考 [Telegram 机器人设置指南](docs/telegram-bot-setup.md) 配置 Telegram 机器人。

## 🆕 对冲模式 (Hedge Mode)

对冲模式 (`hedge_mode.py`) 是一个市场中性策略，通过在两个交易所同时持有相反头寸来降低风险并获取maker返佣。主要适用于需要大量刷交易量同时降低单边风险的场景。

### 💡 项目目的

本项目的核心目标是：
1. **降低单边风险**：通过对冲策略实现市场中性，避免价格波动带来的损失
2. **提升交易量**：在两个交易所同时产生交易量，最大化积分获取
3. **获取maker返佣**：使用post-only订单获取maker费率返佣
4. **优化Lighter评分**：通过持仓时间优化来提高Lighter积分评分

### 🚀 新增高级功能

#### 1. **价格容忍机制 (Price Tolerance)**
- **问题**：原版脚本在价格波动时频繁取消重下订单，导致永远无法成交
- **解决方案**：
  - 增加价格容忍度（默认3个tick）
  - 设置最小订单存活时间（默认30秒）
  - 只有当订单价格偏离超过容忍范围且存活时间超过阈值才取消
- **参数**：
  - `--price-tolerance`: 价格容忍度（tick数量，默认3）
  - `--min-order-lifetime`: 最小订单存活时间（秒，默认30）

#### 2. **自动仓位校准 (Auto-Rebalance)**
- **问题**：原版检测到仓位不平衡时直接退出，无法自动恢复
- **解决方案**：
  - 自动检测仓位偏差
  - 主动下单修复不平衡
  - 支持最多3次重试
- **参数**：
  - `--rebalance-threshold`: 触发校准的阈值（默认0.15）
  - `--no-auto-rebalance`: 禁用自动校准（默认启用）

#### 3. **混合事件驱动模式 (Hybrid Event-Driven)**
- **问题**：纯轮询浪费CPU，纯事件驱动在WebSocket断开时卡死
- **解决方案**：
  - 正常情况：事件驱动，毫秒级响应
  - WebSocket断开：每5秒查询REST API作为fallback
  - 终极保护：180秒硬超时
- **优势**：
  - CPU使用降低99%
  - WebSocket断开仍能正常工作
  - 消息丢失时自动通过API查询状态

#### 4. **循环持仓模式 (Cycle Mode)** 🆕
- **问题**：Lighter对秒开秒关的订单评分很低
- **解决方案**：实现"累积→持有→平仓"循环策略
  - **Phase 1 (Build-up)**：连续下N笔订单，累积仓位
  - **Phase 2 (Hold)**：持有仓位一段时间（如30-60分钟）
  - **Phase 3 (Wind-down)**：慢慢平掉仓位
  - **Repeat**：循环执行多个周期
- **优势**：
  - Lighter持仓时间评分大幅提升 ⭐⭐⭐⭐⭐
  - 更真实的做市商行为
  - 可控的交易量节奏
- **参数**：
  - `--build-up-iterations`: 累积阶段的订单数量（默认等于--iter）
  - `--hold-time`: 持有时间（秒，如1800=30分钟）
  - `--cycles`: 循环次数（默认1）

### 对冲模式工作原理

#### 传统模式（秒开秒关）
```
STEP 1: GRVT买1 → Lighter卖1对冲 (立即)
STEP 2: GRVT卖1 → Lighter买1平仓 (立即)
STEP 3: 清理残余
持有时间: 几秒钟 ❌
```

#### 新增循环模式（累积持有）
```
🔄 CYCLE 1/24
├─ 📈 PHASE 1: Build-up (20次)
│   ├─ GRVT买1 → Lighter卖1
│   ├─ GRVT买1 → Lighter卖1
│   └─ ... (重复20次)
│   └─ 仓位: GRVT+20, Lighter-20
│
├─ ⏳ PHASE 2: Hold (30分钟)
│   └─ 保持仓位不变
│
└─ 📉 PHASE 3: Wind-down (20次)
    ├─ GRVT卖1 → Lighter买1
    ├─ GRVT卖1 → Lighter买1
    └─ ... (慢慢平仓)
    └─ 仓位: GRVT 0, Lighter 0

(重复CYCLE 2, 3, ... 24) ✅
持有时间: 30-60分钟
```

### 对冲模式使用示例

#### 基础模式（兼容原版）
```bash
# 运行 BTC 对冲模式（GRVT + Lighter）
python hedge_mode.py --exchange grvt --ticker BTC --size 0.05 --iter 20
```

#### 循环模式（推荐）
```bash
# 每小时一个周期，累积20笔，持有30分钟
python hedge_mode.py --exchange grvt --ticker HYPE --size 1 \
  --build-up-iterations 20 \
  --hold-time 1800 \
  --cycles 24

# 目标: 每小时$100K交易量
# 参数计算: size × price × build_up_iterations × 4(买卖×开平)
# 例如: 10 × $41 × 30 × 4 = $49,200/周期
python hedge_mode.py --exchange grvt --ticker HYPE --size 10 \
  --build-up-iterations 30 \
  --hold-time 1800 \
  --cycles 24
```

#### 带所有优化参数
```bash
python hedge_mode.py --exchange grvt --ticker BTC --size 1 \
  --build-up-iterations 20 \
  --hold-time 1800 \
  --cycles 24 \
  --price-tolerance 5 \
  --min-order-lifetime 60 \
  --rebalance-threshold 0.2
```

### 对冲模式参数

#### 基础参数
- `--exchange`: 主要交易所（支持 'backpack', 'extended', 'apex', 'grvt'）
- `--ticker`: 交易对符号（如 BTC, ETH, HYPE）
- `--size`: 每笔订单数量
- `--iter`: 交易循环次数（在循环模式下此参数不常用）

#### 循环模式参数 🆕
- `--build-up-iterations`: 累积阶段的订单数量（默认等于--iter）
- `--hold-time`: 持有时间（秒，如1800=30分钟，默认0）
- `--cycles`: 循环次数（默认1，如24=24小时）

#### 高级参数 🆕
- `--price-tolerance`: 价格容忍度（tick数量，默认3）
- `--min-order-lifetime`: 最小订单存活时间（秒，默认30）
- `--rebalance-threshold`: 仓位不平衡阈值（默认0.15）
- `--no-auto-rebalance`: 禁用自动仓位校准
- `--fill-timeout`: maker订单填充超时时间（秒，默认5）

### 优势对比

| 特性 | 原版 | 优化版 |
|-----|------|--------|
| 订单稳定性 | ❌ 频繁取消 | ✅ 价格容忍 |
| 仓位管理 | ❌ 检测到问题就退出 | ✅ 自动修复 |
| 系统稳定性 | ⚠️ WebSocket断开卡死 | ✅ 混合模式容错 |
| Lighter评分 | ⭐ 低（秒开秒关） | ⭐⭐⭐⭐⭐ 高（持仓30-60分钟）|
| 交易量控制 | ⚠️ 难以精确控制 | ✅ 可精确计算 |
| CPU使用 | 高（轮询） | 低（事件驱动）|

### 交易量计算公式

```
每周期交易量 = size × price × build_up_iterations × 4
             └─────┴──────┴──────────────────┴───
             每笔   币价     累积次数         买卖×开平

每小时交易量 = 每周期交易量 × (3600 / 总周期时间)

例如：
- size=10, price=$41, build_up=30
- 每周期 = 10 × $41 × 30 × 4 = $49,200
- 如果周期=60分钟，则每小时约$49K
```

## 配置

### 环境变量

#### 通用配置

- `ACCOUNT_NAME`: 环境变量中当前账号的名称，用于多账号日志区分，可自定义，非必须

#### Telegram 配置（可选）

- `TELEGRAM_BOT_TOKEN`: Telegram 机器人令牌
- `TELEGRAM_CHAT_ID`: Telegram 对话 ID

#### EdgeX 配置

- `EDGEX_ACCOUNT_ID`: 您的 EdgeX 账户 ID
- `EDGEX_STARK_PRIVATE_KEY`: 您的 EdgeX API 私钥
- `EDGEX_BASE_URL`: EdgeX API 基础 URL（默认：https://pro.edgex.exchange）
- `EDGEX_WS_URL`: EdgeX WebSocket URL（默认：wss://quote.edgex.exchange）

#### Backpack 配置

- `BACKPACK_PUBLIC_KEY`: 您的 Backpack API Key
- `BACKPACK_SECRET_KEY`: 您的 Backpack API Secret

#### Paradex 配置

- `PARADEX_L1_ADDRESS`: L1 钱包地址
- `PARADEX_L2_PRIVATE_KEY`: L2 钱包私钥（点击头像，钱包，"复制 paradex 私钥"）

#### Aster 配置

- `ASTER_API_KEY`: 您的 Aster API Key
- `ASTER_SECRET_KEY`: 您的 Aster API Secret

#### Lighter 配置

- `API_KEY_PRIVATE_KEY`: Lighter API 私钥
- `LIGHTER_ACCOUNT_INDEX`: Lighter 账户索引
- `LIGHTER_API_KEY_INDEX`: Lighter API 密钥索引

#### GRVT 配置

- `GRVT_TRADING_ACCOUNT_ID`: 您的 GRVT 交易账户 ID
- `GRVT_PRIVATE_KEY`: 您的 GRVT 私钥
- `GRVT_API_KEY`: 您的 GRVT API 密钥

#### Extended 配置

- `EXTENDED_API_KEY`: Extended API Key
- `EXTENDED_STARK_KEY_PUBLIC`: 创建API后显示的 Stark 公钥
- `EXTENDED_STARK_KEY_PRIVATE`: 创建API后显示的 Stark 私钥
- `EXTENDED_VAULT`: 创建API后显示的 Extended Vault ID

#### Apex 配置

- `APEX_API_KEY`: 您的 Apex API 密钥
- `APEX_API_KEY_PASSPHRASE`: 您的 Apex API 密钥密码
- `APEX_API_KEY_SECRET`: 您的 Apex API 密钥私钥
- `APEX_OMNI_KEY_SEED`: 您的 Apex Omni 密钥种子

**获取 LIGHTER_ACCOUNT_INDEX 的方法**：

1. 在下面的网址最后加上你的钱包地址：

   ```
   https://mainnet.zklighter.elliot.ai/api/v1/account?by=l1_address&value=
   ```

2. 在浏览器中打开这个网址

3. 在结果中搜索 "account_index" - 如果你有子账户，会有多个 account_index，短的那个是你主账户的，长的是你的子账户。


## 日志记录

该机器人提供全面的日志记录：

- **交易日志**：包含订单详情的 CSV 文件
- **调试日志**：带时间戳的详细活动日志
- **控制台输出**：实时状态更新
- **错误处理**：全面的错误日志记录和处理

## Q & A

### 如何配置多个交易对？

将账号配置在 `.env` 文件后，通过更改命令行中的 `--ticker` 参数来交易不同的合约：
```bash
python hedge_mode.py --exchange grvt --ticker BTC --size 0.05 --iter 20
python hedge_mode.py --exchange grvt --ticker ETH --size 0.1 --iter 20
python hedge_mode.py --exchange grvt --ticker HYPE --size 1 --iter 20
```

### 如何计算合适的参数以达到目标交易量？

使用公式：`每周期交易量 = size × price × build_up_iterations × 4`

例如目标每小时$100K交易量，周期60分钟：
- 需要每周期$100K
- 如果HYPE价格$41，build_up=30
- 反推size: $100,000 / ($41 × 30 × 4) ≈ 20.3
- 因此设置 `--size 20 --build-up-iterations 30`

## 贡献

1. Fork 仓库
2. 创建功能分支
3. 进行更改
4. 如适用，添加测试
5. 提交拉取请求

## 许可证

本项目采用非商业许可证 - 详情请参阅[LICENSE](LICENSE)文件。

**重要提醒**：本软件仅供个人学习和研究使用，严禁用于任何商业用途。如需商业使用，请联系作者获取商业许可证。

## 免责声明

本软件仅供教育和研究目的。加密货币交易涉及重大风险，可能导致重大财务损失。使用风险自负，切勿用您无法承受损失的资金进行交易。
