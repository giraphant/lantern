# 测试指南

## 📋 测试前准备

### 1. 配置环境变量

创建 `.env` 文件在项目根目录：

```bash
# Lighter配置
LIGHTER_PRIVATE_KEY=your_private_key_here
LIGHTER_ACCOUNT_INDEX=0
LIGHTER_API_KEY_INDEX=0

# Backpack配置（如果要测试）
BACKPACK_API_KEY=your_api_key_here
BACKPACK_SECRET_KEY=your_secret_key_here

# 其他交易所（可选）
GRVT_API_KEY=...
GRVT_PRIVATE_KEY=...
```

### 2. 安装依赖

```bash
# 如果需要Backpack支持
pip install bpx

# Lighter依赖应该已经安装
# pip install lighter-py
```

## 🧪 测试脚本

### 测试1: 单独测试Lighter

```bash
cd /home/lantern/src
python3 test_lighter_only.py
```

**测试内容**：
- 连接到Lighter
- 获取BTC市场数据（bid/ask/mid价格）
- 获取funding rate（原始费率、年化APR）
- 获取当前仓位

**预期输出**：
```
============================================================
Testing Lighter Exchange
============================================================

1. Initializing Lighter client...
2. Connecting to Lighter...
   ✓ Connected

3. Fetching market data...
   Best Bid: 95000.0
   Best Ask: 95001.0
   Mid Price: 95000.5
   Spread: 1.0 (0.11 bps)

4. Fetching funding rate...
   Raw Rate: 0.00005 (0.0050%)
   Interval: 1 hours
   Annual Rate: 43.80% APR
   Daily Rate: 0.1200%

5. Fetching position...
   Side: none
   Quantity: 0.0
   Signed Quantity: 0.0

6. Disconnecting...
   ✓ Disconnected

============================================================
✅ Test completed successfully!
============================================================
```

### 测试2: Backpack vs Lighter对比

```bash
cd /home/lantern/src
python3 test_exchange_data.py
```

**测试内容**：
1. 分别测试Backpack
2. 分别测试Lighter
3. 对比两个交易所的价格和费率

**预期输出**：
```
============================================================
Comparison: Backpack vs Lighter
============================================================

✓ Both exchanges connected

📊 Fetching data from both exchanges...

💵 Price Comparison:
  Backpack Mid: 95000.5
  Lighter Mid:  95001.0
  Difference:   0.5 (0.0005%)

💰 Funding Rate Comparison:
  Backpack: 0.0100% (8h) → 10.95% APR
  Lighter:  0.0050% (1h) → 43.80% APR

  📈 Funding Spread: 32.85% APR
  ✅ Potential arbitrage opportunity!

✓ Comparison completed
```

### 测试3: 完整Bot运行（干跑）

```bash
cd /home/lantern/src
python3 test_atomic_framework.py
```

**测试内容**：
- 初始化原子化框架
- 运行一个完整的策略循环
- 不会真正下单（仅查询数据）

## 🎯 预期结果

### ✅ 成功标志

1. **连接成功**
   - 能连接到交易所
   - 能获取到市场数据

2. **数据有效**
   - Best Bid < Best Ask
   - Spread > 0
   - Funding Rate在合理范围（-0.01% ~ 0.01%）

3. **费率差**
   - 能计算出年化费率
   - 能对比两个交易所的费率差

### ❌ 常见错误

#### 错误1: 缺少环境变量
```
ValueError: Missing required environment variables: ['LIGHTER_PRIVATE_KEY', ...]
```

**解决**：创建 `.env` 文件并配置API密钥

#### 错误2: 模块未找到
```
ModuleNotFoundError: No module named 'bpx'
```

**解决**：安装依赖 `pip install bpx`

#### 错误3: WebSocket连接失败
```
ValueError: WebSocket not running. No bid/ask prices available
```

**解决**：等待WebSocket连接建立（通常需要2-3秒）

#### 错误4: API密钥无效
```
CheckClient error: invalid signature
```

**解决**：检查API密钥是否正确

## 🚀 运行完整Bot

测试通过后，可以运行完整Bot：

```bash
cd /home/lantern/src
./start_atomic_bot.sh
```

配置 `.env`:
```bash
# 选择要使用的交易所
EXCHANGES=Lighter,Backpack  # 或其他组合

# 交易参数
TRADING_SYMBOL=BTC
TRADING_SIZE=0.1
FUNDING_BUILD_THRESHOLD_APR=0.05  # 5% APR
FUNDING_CLOSE_THRESHOLD_APR=0.02  # 2% APR
MAX_POSITION=10
```

## 📊 理解输出

### Funding Rate解读

```
Raw Rate: 0.00005 (0.0050%)
Interval: 1 hours
Annual Rate: 43.80% APR
Daily Rate: 0.1200%
```

- **Raw Rate**: 单次结算费率（0.005% = 5个基点）
- **Interval**: 结算周期（Lighter是1小时，Binance是8小时）
- **Annual Rate**: 年化费率 = 原始费率 × (24/周期) × 365
- **Daily Rate**: 日化费率 = 原始费率 × (24/周期)

### Funding Spread解读

```
Funding Spread: 32.85% APR
✅ Potential arbitrage opportunity!
```

- **Spread > 5% APR**: 可能有套利机会
- **Spread < 2% APR**: 平仓阈值
- 费率差越大，套利潜在收益越高

## 🔍 调试技巧

### 查看详细日志

修改测试脚本，添加日志：

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 检查原始API响应

在测试脚本中打印原始数据：

```python
market = await queryer.get_market()
print(f"Raw market data: {vars(market)}")
```

### 单独测试组件

```python
# 只测试funding rate
funding = await queryer.get_funding_rate()
print(f"Funding: {funding}")

# 只测试市场数据
market = await queryer.get_market()
print(f"Market: {market}")
```

## 📝 测试检查清单

- [ ] `.env` 文件已创建并配置
- [ ] 依赖已安装（lighter-py等）
- [ ] 能连接到Lighter
- [ ] 能获取市场数据（价格）
- [ ] 能获取funding rate
- [ ] 能对比两个交易所
- [ ] 计算的费率差合理
- [ ] 完整Bot能运行一个周期

## 🎓 下一步

测试通过后：
1. 配置 `EXCHANGES` 选择交易所组合
2. 调整策略参数（阈值、仓位限制等）
3. 运行Bot并监控日志
4. 观察套利信号

---

有问题联系开发团队或查看：
- `PROJECT_STRUCTURE.md` - 项目结构
- `ATOMIC_MIGRATION_GUIDE.md` - 迁移指南
- `src/atomic/README.md` - 框架文档
