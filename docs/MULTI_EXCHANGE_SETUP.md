# 多交易所支持配置指南

## 概述

HedgeBot v3现在支持配置任意交易所对进行对冲交易。不再限于GRVT和Lighter的硬编码组合。

## 支持的交易所

通过`ExchangeFactory`,当前支持以下交易所:

- **GRVT** - Gravity
- **LIGHTER** - Lighter
- **BINANCE** - Binance
- **BACKPACK** - Backpack
- **EDGEX** - EdgeX
- **PARADEX** - Paradex
- **ASTER** - Aster
- **APEX** - Apex
- **EXTENDED** - Extended

## 配置方式

### 环境变量

通过`.env`文件配置交易所:

```bash
# 交易所选择
EXCHANGE_A=GRVT          # 主交易所(使用做市单)
EXCHANGE_B=LIGHTER       # 对冲交易所(使用市价单)

# 交易参数
TRADING_SYMBOL=BNB
TRADING_SIZE=0.1
CYCLE_TARGET=5
CYCLE_HOLD_TIME=180
TRADING_DIRECTION=long   # long 或 short

# GRVT API配置 (如果EXCHANGE_A或EXCHANGE_B使用GRVT)
GRVT_API_KEY=your_api_key
GRVT_PRIVATE_KEY=your_private_key

# Lighter API配置 (如果EXCHANGE_A或EXCHANGE_B使用LIGHTER)
LIGHTER_PRIVATE_KEY=your_private_key

# Binance API配置 (如果EXCHANGE_A或EXCHANGE_B使用BINANCE)
BINANCE_API_KEY=your_api_key
BINANCE_API_SECRET=your_api_secret

# Backpack API配置 (如果EXCHANGE_A或EXCHANGE_B使用BACKPACK)
BACKPACK_PUBLIC_KEY=your_public_key
BACKPACK_SECRET_KEY=your_secret_key
```

## 使用示例

### 示例1: GRVT ⇄ Lighter (默认配置)

```bash
# .env
EXCHANGE_A=GRVT
EXCHANGE_B=LIGHTER
TRADING_SYMBOL=BNB
TRADING_SIZE=0.1

GRVT_API_KEY=xxx
GRVT_PRIVATE_KEY=xxx
LIGHTER_PRIVATE_KEY=xxx
```

### 示例2: GRVT ⇄ Binance

```bash
# .env
EXCHANGE_A=GRVT
EXCHANGE_B=BINANCE
TRADING_SYMBOL=BNB
TRADING_SIZE=0.1

GRVT_API_KEY=xxx
GRVT_PRIVATE_KEY=xxx
BINANCE_API_KEY=xxx
BINANCE_API_SECRET=xxx
```

### 示例3: Lighter ⇄ Binance

```bash
# .env
EXCHANGE_A=LIGHTER
EXCHANGE_B=BINANCE
TRADING_SYMBOL=BTC
TRADING_SIZE=0.001

LIGHTER_PRIVATE_KEY=xxx
BINANCE_API_KEY=xxx
BINANCE_API_SECRET=xxx
```

### 示例4: Backpack ⇄ Binance

```bash
# .env
EXCHANGE_A=BACKPACK
EXCHANGE_B=BINANCE
TRADING_SYMBOL=SOL
TRADING_SIZE=0.5

BACKPACK_PUBLIC_KEY=xxx
BACKPACK_SECRET_KEY=xxx
BINANCE_API_KEY=xxx
BINANCE_API_SECRET=xxx
```

## 交易所角色说明

### Exchange A (主交易所)
- 使用**做市单**(Maker Orders)
- 提供流动性,吃深度
- 等待订单成交后才执行对冲
- 通常选择手续费较低或有返佣的交易所

### Exchange B (对冲交易所)
- 使用**市价单**(Taker Orders)
- 立即成交以对冲风险
- 不等待订单成交
- 通常选择流动性好、滑点低的交易所

## 策略方向

### Long策略 (默认)
```bash
TRADING_DIRECTION=long
```
- **建仓阶段**: Exchange A买入 + Exchange B卖出
- **平仓阶段**: Exchange A卖出 + Exchange B买入
- 目标: 赚取资金费率差 + 交易返佣

### Short策略
```bash
TRADING_DIRECTION=short
```
- **建仓阶段**: Exchange A卖出 + Exchange B买入
- **平仓阶段**: Exchange A买入 + Exchange B卖出
- 目标: 赚取资金费率差 + 交易返佣

## 添加新交易所

如果你需要添加新的交易所支持:

1. 实现`BaseExchangeClient`接口:
   ```python
   # src/exchanges/my_exchange.py
   from exchanges.base import BaseExchangeClient

   class MyExchangeClient(BaseExchangeClient):
       def _validate_config(self):
           # 验证配置
           pass

       async def connect(self):
           # 连接交易所
           pass

       # ... 实现其他required方法
   ```

2. 在`ExchangeFactory`中注册:
   ```python
   # src/exchanges/factory.py
   _registered_exchanges = {
       # ... 现有交易所
       'myexchange': 'exchanges.my_exchange.MyExchangeClient',
   }
   ```

3. 在`hedge_bot_v3.py`的`_prepare_exchange_config`中添加配置逻辑:
   ```python
   elif exchange_name == "MYEXCHANGE":
       base_config.update({
           "api_key": os.getenv("MYEXCHANGE_API_KEY"),
           "api_secret": os.getenv("MYEXCHANGE_API_SECRET"),
       })
       if not all([base_config.get("api_key"), base_config.get("api_secret")]):
           raise ValueError("Missing MYEXCHANGE API keys")
   ```

## 兼容性说明

### 向后兼容
代码保持了向后兼容性,以下属性/方法仍然可用:

```python
# PositionState
position.grvt_position     # 等同于 position.exchange_a_position
position.lighter_position  # 等同于 position.exchange_b_position

# PendingOrdersInfo
pending.grvt_pending_count     # 等同于 pending.exchange_a_pending_count
pending.lighter_pending_count  # 等同于 pending.exchange_b_pending_count

# ExecutionResult (已更新,需要使用新字段名)
result.exchange_a_order_id   # 原: grvt_order_id
result.exchange_a_price      # 原: grvt_price
result.exchange_b_order_id   # 原: lighter_order_id
result.exchange_b_price      # 原: lighter_price
```

### 代码变更
如果你有自定义的代码依赖HedgeBot:
- `TradingExecutor`: 参数名改为`exchange_a_client`, `exchange_b_client`
- `ExecutionResult`: 字段名改为`exchange_a_*`, `exchange_b_*`
- `PositionState`: 使用新字段名`exchange_a_position`, `exchange_b_position`

## 运行示例

```bash
# 启动bot
cd src
python hedge_bot_v3.py

# 输出示例:
# 2024-11-01 12:00:00 - INFO: ✓ Initialized GRVT exchange client
# 2024-11-01 12:00:00 - INFO: ✓ Initialized BINANCE exchange client
# 2024-11-01 12:00:01 - INFO: Connecting to exchanges (GRVT & BINANCE)...
# 2024-11-01 12:00:02 - INFO: ✓ GRVT connected
# 2024-11-01 12:00:03 - INFO: ✓ BINANCE connected
```

## 注意事项

1. **API密钥安全**:
   - 不要将`.env`文件提交到git
   - 使用只读或限制权限的API密钥
   - 定期轮换密钥

2. **交易对一致性**:
   - 确保两个交易所都支持配置的`TRADING_SYMBOL`
   - 注意交易对格式可能不同(如BTC-USDC vs BTCUSDC)

3. **网络要求**:
   - 确保服务器能访问两个交易所的API
   - 建议使用低延迟网络环境
   - 考虑使用VPN或专线

4. **资金要求**:
   - 两个交易所都需要足够的保证金
   - 建议预留2-3倍的交易金额作为缓冲

5. **风险管理**:
   - 从小金额开始测试
   - 监控仓位不平衡
   - 设置合理的`CYCLE_TARGET`和`TRADING_SIZE`

## 故障排查

### 连接失败
```
Failed to initialize GRVT: Missing API keys
```
**解决**: 检查`.env`文件中对应交易所的API密钥配置

### 不支持的交易所
```
Unsupported exchange: MYEXCHANGE. Available exchanges: grvt, lighter, binance...
```
**解决**: 检查`EXCHANGE_A`/`EXCHANGE_B`拼写是否正确,或该交易所是否已注册

### 交易对不存在
```
Failed to place order: Invalid symbol
```
**解决**: 确认`TRADING_SYMBOL`在两个交易所都存在且格式正确

## 进一步开发

计划中的功能:
- [ ] 动态交易对映射(自动转换交易对格式)
- [ ] 多策略并行运行
- [ ] Web UI配置界面
- [ ] 实时监控Dashboard
- [ ] 交易报告和分析

## 参考资料

- [BaseExchangeClient接口文档](../src/exchanges/base.py)
- [ExchangeFactory实现](../src/exchanges/factory.py)
- [HedgeBot v3源码](../src/hedge_bot_v3.py)
- [Trading Executor源码](../src/hedge/trading_executor.py)
