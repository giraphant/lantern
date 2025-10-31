# Funding Rate Arbitrage - Web Dashboard

统一的Web管理界面，用于监控和管理多个资金费率套利策略。

## 🎯 特性

- **统一管理**：一个界面管理所有交易对策略
- **实时监控**：WebSocket实时推送费率和仓位变化
- **可视化**：费率曲线、PNL图表、交易历史
- **灵活配置**：动态添加/删除/调整策略参数
- **多交易所**：支持 GRVT、Lighter、Binance、Backpack
- **数据持久化**：SQLite存储历史数据

## 📁 项目结构

```
.
├── backend/              # FastAPI后端
│   ├── app/
│   │   ├── api/         # REST API路由
│   │   ├── models/      # 数据库模型
│   │   ├── schemas/     # Pydantic schemas
│   │   ├── services/    # 业务逻辑
│   │   ├── config.py    # 配置
│   │   ├── database.py  # 数据库连接
│   │   └── main.py      # 主应用
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/            # Next.js前端
│   ├── src/
│   │   ├── app/        # Next.js页面
│   │   ├── components/ # React组件
│   │   └── lib/        # 工具函数
│   ├── Dockerfile
│   └── package.json
│
├── src/                 # 共享代码（exchange clients等）
├── docs/                # 文档
│   └── web-dashboard-design.md
│
└── docker-compose.dashboard.yml  # Docker编排
```

## 🚀 快速开始

### 方法1：使用 Docker Compose（推荐）

1. **准备配置文件**

```bash
# 复制示例配置
cp .env.funding.example .env

# 编辑 .env 填入你的API密钥
vim .env
```

2. **启动服务**

```bash
docker-compose -f docker-compose.dashboard.yml up -d
```

3. **访问Dashboard**

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### 方法2：本地开发

**启动后端：**

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**启动前端：**

```bash
cd frontend
npm install
npm run dev
```

## 📊 使用指南

### 1. 创建策略

在Dashboard首页点击"Create Strategy"，填写：

- **策略名称**：例如 "BTC GRVT-Lighter"
- **交易所A**：选择 GRVT、Binance等
- **交易所B**：选择 Lighter、Backpack等
- **交易对**：BTC、ETH等
- **交易大小**：每次交易数量
- **最大仓位**：单侧最大仓位
- **建仓阈值**：费率差 > 此值开始建仓（如5% APR）
- **平仓阈值**：费率差 < 此值开始平仓（如2% APR）

### 2. 启动策略

创建后点击"Start"按钮启动策略。

### 3. 监控运行

- **实时费率**：查看当前费率差和APR
- **仓位状态**：查看两边仓位和净仓位
- **交易历史**：查看所有交易记录
- **收益统计**：查看今日/累计PNL

### 4. 调整参数

点击策略卡片进入详情页，可以动态调整阈值等参数。

## 🔧 配置说明

### 环境变量

在 `.env` 文件中配置：

```bash
# ========== 交易所密钥 ==========
# GRVT
GRVT_API_KEY=your_key
GRVT_PRIVATE_KEY=your_private_key
GRVT_TRADING_ACCOUNT_ID=your_account_id

# Lighter
LIGHTER_PRIVATE_KEY=your_private_key_hex
LIGHTER_ACCOUNT_INDEX=0

# Binance
BINANCE_API_KEY=your_api_key
BINANCE_SECRET_KEY=your_secret_key

# Backpack
BACKPACK_PUBLIC_KEY=your_public_key_base64
BACKPACK_SECRET_KEY=your_secret_key_base64

# ========== Telegram通知（可选） ==========
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 数据库

默认使用SQLite，数据存储在 `./data/funding_bot.db`

要查看数据库：

```bash
sqlite3 ./data/funding_bot.db
.tables
SELECT * FROM strategies;
```

## 🌐 Cloudflare Tunnel（可选）

如果要通过公网访问，可以配置Cloudflare Tunnel：

1. **创建Tunnel**

```bash
cloudflared tunnel create funding-bot
```

2. **配置DNS**

在Cloudflare Dashboard中添加CNAME记录指向tunnel

3. **启用Tunnel服务**

取消注释 `docker-compose.dashboard.yml` 中的 `cloudflared` 服务，并设置：

```bash
CLOUDFLARE_TUNNEL_TOKEN=your_tunnel_token
```

4. **安全建议**

建议配置 Cloudflare Access 进行认证保护。

## 🆚 与多容器方案对比

### 多容器方案（当前的 docker-compose.yml）

✅ 每个策略独立隔离
❌ 资源占用多
❌ 配置分散
❌ 无统一界面
❌ TG Bot限制

**适用场景**：少量策略（1-3个），稳定运行

### Web Dashboard方案（本方案）

✅ 统一管理界面
✅ 资源利用率高
✅ 配置集中
✅ 实时可视化
✅ 灵活添加策略
⚠️ 单进程（可通过监控保证可靠性）

**适用场景**：多策略管理（3+个），频繁调整

## 📝 API文档

详细API文档访问：http://localhost:8000/docs

主要端点：

- `GET /api/strategies` - 获取所有策略
- `POST /api/strategies` - 创建策略
- `POST /api/strategies/{id}/start` - 启动策略
- `POST /api/strategies/{id}/stop` - 停止策略
- `GET /api/funding-rates` - 获取当前费率
- `GET /api/positions` - 获取当前仓位
- `GET /api/trades` - 获取交易历史
- `WS /ws/updates` - WebSocket实时更新

## 🐛 故障排查

### 后端无法启动

```bash
# 查看日志
docker logs funding-bot-backend

# 常见问题：
# - 端口8000被占用 → 修改 docker-compose.yml 端口映射
# - 数据库权限问题 → 检查 ./data 目录权限
# - 缺少环境变量 → 检查 .env 文件
```

### 前端无法访问后端

```bash
# 检查网络连接
docker network inspect funding-bot_default

# 检查后端健康状态
curl http://localhost:8000/health
```

### 策略无法启动

- 检查交易所API密钥是否正确
- 查看后端日志中的错误信息
- 确认交易对在交易所上可用

## 🔜 TODO / 路线图

- [ ] 实现策略执行引擎（当前仅框架）
- [ ] 集成现有的 hedge_bot_funding.py 逻辑
- [ ] 添加费率图表（Recharts）
- [ ] 添加PNL曲线图
- [ ] 实现WebSocket实时推送
- [ ] 添加策略详情页
- [ ] 添加用户认证
- [ ] 移动端适配
- [ ] 暗色模式
- [ ] 导出报表功能
- [ ] 多用户支持
- [ ] 告警规则配置

## 📄 许可

MIT

## 🤝 贡献

欢迎提交Issue和Pull Request！

---

## 注意事项

⚠️ **当前状态**：基础框架已完成，核心策略执行引擎待实现

此Web Dashboard是一个**独立分支**，不影响现有的多容器方案。你可以：

1. **继续使用多容器方案**运行生产环境
2. **同时开发Web版本**，测试新功能
3. **待Web版本成熟后**，再决定是否切换

两种方案可以并存使用不同的配置文件和端口。
