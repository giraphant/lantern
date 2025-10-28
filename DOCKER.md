# Docker 部署指南

## 🐳 快速开始

### 1. 准备环境变量

复制示例环境文件并填入你的API密钥：

```bash
cp .env.docker.example .env
# 编辑 .env 文件，填入你的API密钥
```

### 2. 使用 Docker Compose（推荐）

```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止
docker-compose down

# 重启
docker-compose restart
```

### 3. 使用 Docker 命令

```bash
# 构建镜像
docker build -t lantern-hedge-bot .

# 运行（使用环境变量文件）
docker run -d \
  --name lantern \
  --env-file .env \
  -v $(pwd)/logs:/app/logs \
  lantern-hedge-bot

# 查看日志
docker logs -f lantern

# 停止
docker stop lantern

# 删除容器
docker rm lantern
```

## ⚙️ 自定义参数

### 方法1: 修改 docker-compose.yml

在 `docker-compose.yml` 中取消注释并修改 `command` 部分：

```yaml
command: >
  python3 hedge_mode.py
  --exchange grvt
  --ticker BTC
  --size 0.05
  --build-up-iterations 30
  --hold-time 3600
  --cycles 24
```

### 方法2: 直接在 docker run 中指定

```bash
docker run -d \
  --name lantern \
  --env-file .env \
  -v $(pwd)/logs:/app/logs \
  lantern-hedge-bot \
  python3 hedge_mode.py \
  --exchange grvt \
  --ticker BTC \
  --size 0.05 \
  --build-up-iterations 30 \
  --hold-time 3600 \
  --cycles 24
```

## 📊 查看日志

### Docker日志
```bash
docker logs -f lantern
# 或
docker-compose logs -f
```

### 应用日志（CSV和TXT）
日志保存在 `./logs` 目录：
```bash
# 查看交易日志
tail -f logs/grvt_HYPE_hedge_mode_log.txt

# 查看CSV交易记录
cat logs/grvt_HYPE_hedge_mode_trades.csv
```

## 🔄 更新代码

```bash
# 拉取最新代码
git pull

# 重新构建并重启
docker-compose down
docker-compose up -d --build
```

## 🚀 Coolify 部署

### 配置参数

- **Branch**: `main`
- **Build Pack**: `Dockerfile`
- **Port**: 留空（不是Web服务）
- **Is it a static site?**: 否

### 环境变量

在Coolify中添加以下环境变量：

#### GRVT配置
```
GRVT_TRADING_ACCOUNT_ID=你的交易账户ID
GRVT_PRIVATE_KEY=0x你的私钥
GRVT_API_KEY=你的API密钥
GRVT_ENVIRONMENT=prod
```

#### Lighter配置
```
LIGHTER_ACCOUNT_INDEX=你的账户索引（获取方法见下方）
LIGHTER_API_KEY_INDEX=4（通常是4）
API_KEY_PRIVATE_KEY=你的Lighter API私钥（hex字符串，无0x前缀）
```

**如何获取 LIGHTER_ACCOUNT_INDEX**:
1. 访问: `https://mainnet.zklighter.elliot.ai/api/v1/account?by=l1_address&value=YOUR_WALLET_ADDRESS`
2. 将 `YOUR_WALLET_ADDRESS` 替换为你的钱包地址
3. 在返回结果中找到 `account_index`
   - 短的数字是主账户
   - 长的数字是子账户

### Health Check

**禁用**健康检查（这不是HTTP服务）

## 💡 常用命令

```bash
# 查看运行状态
docker ps | grep lantern

# 查看资源使用
docker stats lantern

# 进入容器调试
docker exec -it lantern /bin/bash

# 查看容器详细信息
docker inspect lantern

# 重启容器
docker restart lantern
```

## ⚠️ 注意事项

1. **环境变量安全**: 确保 `.env` 文件不要提交到Git
2. **日志管理**: 定期清理 `logs/` 目录的旧日志
3. **资源监控**: 虽然资源占用很低，但建议定期查看
4. **自动重启**: docker-compose.yml 已配置 `restart: unless-stopped`

## 🐛 故障排查

### 容器启动失败
```bash
# 查看详细错误
docker logs lantern

# 检查环境变量
docker exec lantern env | grep -E "GRVT|LIGHTER"
```

### 订单不成交
```bash
# 查看应用日志
docker exec lantern cat logs/grvt_HYPE_hedge_mode_log.txt

# 检查网络连接
docker exec lantern ping -c 3 grvt.io
```

### 磁盘空间不足
```bash
# 清理未使用的镜像
docker image prune -a

# 清理旧日志
rm -rf logs/*.log
rm -rf logs/*.csv
```
