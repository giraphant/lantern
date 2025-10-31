# Web Dashboard 设计文档

## 概述

将现有的多容器funding rate套利bot重构为统一的Web Dashboard，支持多交易对统一管理。

## 架构设计

```
┌─────────────────────────────────────────┐
│  Cloudflare Tunnel (可选)                │
│  - 公网访问                              │
│  - Cloudflare Access 认证                │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│  Frontend (React/Vite)                  │
│  - 费率监控仪表盘                        │
│  - 多交易对管理                          │
│  - 仓位实时显示                          │
│  - 策略配置界面                          │
│  - 历史数据图表                          │
└────────────────┬────────────────────────┘
                 │ REST API / WebSocket
┌────────────────▼────────────────────────┐
│  Backend (FastAPI)                      │
│  ┌──────────────────────────────────┐   │
│  │ Strategy Manager                 │   │
│  │ - 管理多个交易对策略              │   │
│  │ - 启动/停止策略                  │   │
│  │ - 参数动态调整                    │   │
│  └──────────────────────────────────┘   │
│  ┌──────────────────────────────────┐   │
│  │ Exchange Connection Pool         │   │
│  │ - 复用exchange clients           │   │
│  │ - WebSocket连接管理              │   │
│  └──────────────────────────────────┘   │
│  ┌──────────────────────────────────┐   │
│  │ Data Service                     │   │
│  │ - SQLite存储历史数据              │   │
│  │ - 费率历史                        │   │
│  │ - 交易记录                        │   │
│  │ - PNL计算                        │   │
│  └──────────────────────────────────┘   │
│  ┌──────────────────────────────────┐   │
│  │ WebSocket Service                │   │
│  │ - 实时费率推送                    │   │
│  │ - 仓位更新推送                    │   │
│  │ - 交易通知推送                    │   │
│  └──────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

## 核心功能

### 1. 后端 API (FastAPI)

#### REST Endpoints

**策略管理**
- `GET /api/strategies` - 获取所有策略列表
- `POST /api/strategies` - 创建新策略
- `GET /api/strategies/{id}` - 获取策略详情
- `PUT /api/strategies/{id}` - 更新策略配置
- `DELETE /api/strategies/{id}` - 删除策略
- `POST /api/strategies/{id}/start` - 启动策略
- `POST /api/strategies/{id}/stop` - 停止策略

**费率数据**
- `GET /api/funding-rates` - 获取当前所有交易对费率
- `GET /api/funding-rates/{pair}` - 获取特定交易对费率
- `GET /api/funding-rates/{pair}/history` - 获取历史费率数据

**仓位管理**
- `GET /api/positions` - 获取所有仓位
- `GET /api/positions/{strategy_id}` - 获取特定策略仓位

**交易记录**
- `GET /api/trades` - 获取交易历史
- `GET /api/trades/{strategy_id}` - 获取特定策略交易记录

**统计数据**
- `GET /api/stats/pnl` - 获取总体PNL
- `GET /api/stats/pnl/{strategy_id}` - 获取特定策略PNL

**交易所支持**
- `GET /api/exchanges` - 获取支持的交易所列表
- `GET /api/exchanges/{name}/symbols` - 获取交易所支持的交易对

#### WebSocket Endpoints

- `WS /ws/updates` - 实时更新推送
  - 费率更新
  - 仓位变化
  - 交易执行通知
  - 策略状态变化

#### 数据模型

```python
# 策略配置
class StrategyConfig:
    id: str
    name: str
    exchange_a: str  # GRVT, Binance, etc.
    exchange_b: str  # Lighter, Backpack, etc.
    symbol: str
    size: Decimal
    max_position: Decimal
    build_threshold_apr: Decimal
    close_threshold_apr: Decimal
    check_interval: int
    status: str  # running, stopped, error
    created_at: datetime
    updated_at: datetime

# 费率快照
class FundingRateSnapshot:
    timestamp: datetime
    strategy_id: str
    exchange_a_rate: Decimal
    exchange_b_rate: Decimal
    spread: Decimal
    spread_apr: Decimal

# 仓位快照
class PositionSnapshot:
    timestamp: datetime
    strategy_id: str
    exchange_a_position: Decimal
    exchange_b_position: Decimal
    total_position: Decimal
    unrealized_pnl: Decimal

# 交易记录
class Trade:
    id: str
    strategy_id: str
    timestamp: datetime
    exchange: str
    side: str
    symbol: str
    quantity: Decimal
    price: Decimal
    action: str  # build, winddown
```

### 2. 前端界面

#### 主要页面

**1. Dashboard（仪表盘）**
- 所有策略卡片展示
  - 当前费率差（APR）
  - 仓位大小
  - 当日PNL
  - 策略状态（运行/停止）
- 快速操作按钮（启动/停止）
- 实时更新（WebSocket）

**2. Strategy Detail（策略详情）**
- 费率历史图表（24h/7d/30d）
- 仓位历史图表
- PNL曲线
- 交易历史列表
- 参数配置表单

**3. Create/Edit Strategy（创建/编辑策略）**
- 交易所选择
- 交易对选择
- 参数配置
  - 交易大小
  - 最大仓位
  - 建仓阈值
  - 平仓阈值
  - 检查间隔

**4. Overview（总览）**
- 所有策略的总PNL
- 各交易对费率对比
- 最佳套利机会排行

#### 技术栈

**前端**
- Next.js 14 (App Router)
- TypeScript
- shadcn/ui (组件库)
- TailwindCSS (样式)
- Recharts (图表)
- WebSocket客户端
- TanStack Query (数据获取)

**后端**
- FastAPI
- SQLAlchemy (ORM)
- SQLite (数据库)
- python-telegram-bot (通知)
- asyncio (异步)

## 数据库设计

```sql
-- 策略配置表
CREATE TABLE strategies (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    exchange_a TEXT NOT NULL,
    exchange_b TEXT NOT NULL,
    symbol TEXT NOT NULL,
    size DECIMAL NOT NULL,
    max_position DECIMAL NOT NULL,
    build_threshold_apr DECIMAL NOT NULL,
    close_threshold_apr DECIMAL NOT NULL,
    check_interval INTEGER NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);

-- 费率历史表
CREATE TABLE funding_rate_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP NOT NULL,
    strategy_id TEXT NOT NULL,
    exchange_a_rate DECIMAL NOT NULL,
    exchange_b_rate DECIMAL NOT NULL,
    spread DECIMAL NOT NULL,
    spread_apr DECIMAL NOT NULL,
    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
);
CREATE INDEX idx_funding_history_time ON funding_rate_history(strategy_id, timestamp);

-- 仓位历史表
CREATE TABLE position_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP NOT NULL,
    strategy_id TEXT NOT NULL,
    exchange_a_position DECIMAL NOT NULL,
    exchange_b_position DECIMAL NOT NULL,
    total_position DECIMAL NOT NULL,
    unrealized_pnl DECIMAL,
    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
);
CREATE INDEX idx_position_history_time ON position_history(strategy_id, timestamp);

-- 交易记录表
CREATE TABLE trades (
    id TEXT PRIMARY KEY,
    strategy_id TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    exchange TEXT NOT NULL,
    side TEXT NOT NULL,
    symbol TEXT NOT NULL,
    quantity DECIMAL NOT NULL,
    price DECIMAL NOT NULL,
    action TEXT NOT NULL,
    FOREIGN KEY (strategy_id) REFERENCES strategies(id)
);
CREATE INDEX idx_trades_time ON trades(strategy_id, timestamp);
```

## 部署方式

### Docker Compose

```yaml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    environment:
      - DATABASE_URL=sqlite:///data/funding_bot.db
    restart: unless-stopped

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend
    restart: unless-stopped

  cloudflared:
    image: cloudflare/cloudflared:latest
    command: tunnel --no-autoupdate run
    environment:
      - TUNNEL_TOKEN=${CLOUDFLARE_TUNNEL_TOKEN}
    depends_on:
      - frontend
    restart: unless-stopped
```

## 优势对比

### 当前多容器方案
- ❌ 每个交易对一个容器，资源浪费
- ❌ 配置分散，难以管理
- ❌ 无统一监控界面
- ❌ TG Bot限制（只能一个polling）
- ✅ 隔离性好，互不影响

### Web Dashboard方案
- ✅ 单进程管理所有策略
- ✅ 统一配置和监控
- ✅ 实时Web界面
- ✅ 无TG Bot限制
- ✅ 历史数据可视化
- ✅ 灵活添加/删除策略
- ⚠️ 单点故障（但可以加监控重启）

## 开发计划

1. **Phase 1: 后端核心** (1天)
   - FastAPI项目结构
   - 数据库模型和迁移
   - 策略管理器
   - REST API基础

2. **Phase 2: 策略引擎** (1天)
   - 复用现有exchange clients
   - 多策略并发运行
   - WebSocket实时推送

3. **Phase 3: 前端基础** (1天)
   - React项目搭建
   - Dashboard页面
   - 策略列表和详情

4. **Phase 4: 高级功能** (按需)
   - 图表可视化
   - 历史数据查询
   - 性能优化
   - Cloudflare Tunnel配置

## 注意事项

1. **向后兼容**：保留现有的hedge_bot_funding.py，Web版本作为可选方案
2. **渐进式迁移**：可以先用Web管理一部分策略，其他继续用容器
3. **数据备份**：SQLite定期备份到volume
4. **监控告警**：保留TG Bot通知功能
5. **认证安全**：如果暴露公网，必须配置Cloudflare Access
