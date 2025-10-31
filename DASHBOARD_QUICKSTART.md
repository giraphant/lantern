# Web Dashboard 快速开始指南

## ✅ 当前状态

Web Dashboard **后端已成功运行**在 `http://localhost:38888`！

### 已完成功能

- ✅ FastAPI 后端框架
- ✅ SQLite 数据库（自动创建）
- ✅ REST API（策略管理、费率、仓位、交易）
- ✅ WebSocket 实时推送
- ✅ 策略执行引擎
- ✅ 数据记录服务
- ✅ Docker 容器化

### 支持的交易所

- ✅ **Lighter** - 完全支持
- ✅ **Binance** - 完全支持
- ⚠️ **GRVT** - 待修复（pysdk依赖问题）
- ⚠️ **Backpack** - 待修复（bpx依赖问题）

## 🚀 立即开始

### 方式1：使用Docker（推荐）

```bash
# 1. 确保已有Docker环境

# 2. 构建镜像（首次）
docker build -f backend/Dockerfile -t funding-bot-backend:latest .

# 3. 运行容器
docker run -d --name funding-bot-backend \
  -p 38888:8000 \
  -v $(pwd)/data:/app/data \
  -e DATABASE_URL=sqlite+aiosqlite:///data/funding_bot.db \
  funding-bot-backend:latest

# 4. 验证运行
curl http://localhost:38888/health
# 应返回: {"status":"healthy"}
```

### 方式2：停止/启动容器

```bash
# 停止
docker stop funding-bot-backend

# 启动
docker start funding-bot-backend

# 查看日志
docker logs -f funding-bot-backend

# 删除容器
docker stop funding-bot-backend
docker rm funding-bot-backend
```

## 📊 访问 Dashboard

### Backend API

- **健康检查**: http://localhost:38888/health
- **API文档（Swagger）**: http://localhost:38888/docs
- **API文档（ReDoc）**: http://localhost:38888/redoc
- **根路径**: http://localhost:38888/

### API 端点

#### 策略管理
```bash
# 获取所有策略
curl http://localhost:38888/api/strategies/

# 创建策略
curl -X POST http://localhost:38888/api/strategies/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "BTC Lighter-Binance",
    "exchange_a": "Lighter",
    "exchange_b": "Binance",
    "symbol": "BTC",
    "size": 0.01,
    "max_position": 0.1,
    "build_threshold_apr": 0.05,
    "close_threshold_apr": 0.02,
    "check_interval": 300
  }'

# 获取特定策略
curl http://localhost:38888/api/strategies/{strategy_id}/

# 启动策略
curl -X POST http://localhost:38888/api/strategies/{strategy_id}/start/

# 停止策略
curl -X POST http://localhost:38888/api/strategies/{strategy_id}/stop/

# 删除策略
curl -X DELETE http://localhost:38888/api/strategies/{strategy_id}/
```

#### 费率数据
```bash
# 获取当前费率
curl http://localhost:38888/api/funding-rates/

# 获取历史费率
curl http://localhost:38888/api/funding-rates/{strategy_id}/history?limit=100
```

#### 仓位数据
```bash
# 获取当前仓位
curl http://localhost:38888/api/positions/

# 获取历史仓位
curl http://localhost:38888/api/positions/{strategy_id}/history?limit=100
```

#### 交易记录
```bash
# 获取所有交易
curl http://localhost:38888/api/trades/?limit=50

# 获取特定策略交易
curl http://localhost:38888/api/trades/{strategy_id}?limit=50
```

### WebSocket 实时更新

```javascript
// 连接WebSocket
const ws = new WebSocket('ws://localhost:38888/ws/updates');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Received:', data);

  // 消息类型:
  // - connected: 连接成功
  // - funding_rate_update: 费率更新
  // - position_update: 仓位更新
  // - strategy_status: 策略状态变化
};
```

## 🔍 测试示例

### 1. 创建并启动一个策略

```bash
# 创建策略
STRATEGY_ID=$(curl -s -X POST http://localhost:38888/api/strategies/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ETH Lighter-Binance Test",
    "exchange_a": "Lighter",
    "exchange_b": "Binance",
    "symbol": "ETH",
    "size": 0.01,
    "max_position": 0.1,
    "build_threshold_apr": 0.05,
    "close_threshold_apr": 0.02,
    "check_interval": 60
  }' | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")

echo "Created strategy: $STRATEGY_ID"

# 启动策略
curl -X POST http://localhost:38888/api/strategies/$STRATEGY_ID/start/

# 查看策略状态
curl http://localhost:38888/api/strategies/$STRATEGY_ID/ | python3 -m json.tool
```

### 2. 监控运行

```bash
# 实时查看日志
docker logs -f funding-bot-backend

# 查看费率数据
watch -n 5 'curl -s http://localhost:38888/api/funding-rates/ | python3 -m json.tool'

# 查看仓位
watch -n 5 'curl -s http://localhost:38888/api/positions/ | python3 -m json.tool'
```

## 📁 数据存储

所有数据存储在 `./data/funding_bot.db` SQLite数据库中。

### 查看数据库

```bash
# 安装sqlite3
sudo apt-get install sqlite3

# 查看数据
sqlite3 data/funding_bot.db

# SQL查询示例
sqlite> .tables
sqlite> SELECT * FROM strategies;
sqlite> SELECT * FROM funding_rate_history ORDER BY timestamp DESC LIMIT 10;
sqlite> SELECT * FROM position_history ORDER BY timestamp DESC LIMIT 10;
sqlite> SELECT * FROM trades ORDER BY timestamp DESC LIMIT 10;
sqlite> .exit
```

## 🐛 故障排查

### 问题：容器无法启动

```bash
# 查看容器日志
docker logs funding-bot-backend

# 常见问题：
# 1. 端口被占用
lsof -i:38888
# 解决：kill占用端口的进程或使用其他端口

# 2. 数据库权限问题
ls -la data/
chmod 666 data/funding_bot.db
```

### 问题：API返回错误

```bash
# 检查容器状态
docker ps | grep funding-bot-backend

# 重启容器
docker restart funding-bot-backend

# 查看详细日志
docker logs --tail 100 funding-bot-backend
```

### 问题：策略无法启动

检查：
1. 交易所API密钥是否配置（如果需要）
2. 选择的交易所是否支持（目前仅Lighter和Binance）
3. 交易对是否在交易所上可用

## 📝 环境变量配置

如果策略需要交易所API密钥（实际下单），在启动容器时添加环境变量：

```bash
docker run -d --name funding-bot-backend \
  -p 38888:8000 \
  -v $(pwd)/data:/app/data \
  -e DATABASE_URL=sqlite+aiosqlite:///data/funding_bot.db \
  -e LIGHTER_PRIVATE_KEY=your_key \
  -e LIGHTER_ACCOUNT_INDEX=0 \
  -e BINANCE_API_KEY=your_api_key \
  -e BINANCE_SECRET_KEY=your_secret_key \
  funding-bot-backend:latest
```

## 🎯 下一步

1. **添加前端** - Next.js Dashboard UI
2. **修复GRVT支持** - 解决pysdk依赖问题
3. **添加Backpack支持** - 解决bpx依赖问题
4. **增强功能**:
   - 图表可视化
   - 策略详情页
   - 历史数据分析
   - 告警通知

## 📞 获取帮助

- 查看 API 文档: http://localhost:38888/docs
- 查看设计文档: `docs/web-dashboard-design.md`
- 查看详细 README: `README.web-dashboard.md`
- 后端代码: `backend/`
- 前端代码: `frontend/` (待完成)

---

**当前版本**: v1.0 Beta
**分支**: `feature/web-dashboard`
**状态**: Backend ✅ | Frontend ⏳ | GRVT ⚠️ | Backpack ⚠️
