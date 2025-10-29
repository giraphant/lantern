# Position-Based Cycle Logic (基于仓位的循环逻辑)

## 核心改进

从**计数驱动**改为**仓位驱动**的逻辑。

### 旧逻辑（计数驱动）❌

```python
# 需要维护状态
iteration_count = 0
for i in range(BUILD_UP_ITERATIONS):
    iteration_count += 1
    place_order()
    # 如果程序崩溃，iteration_count丢失
```

**问题**：
- 需要维护iteration_count状态
- 程序重启后丢失进度
- 订单失败会导致计数与实际仓位不符

### 新逻辑（仓位驱动）✅

```python
# 无状态，直接读取仓位
while True:
    position = get_position_from_api()
    completed = position.lighter / ORDER_SIZE

    if completed >= TARGET_BUILDS:
        break  # 达到目标

    place_order()
    # 程序崩溃重启后，自动从当前仓位继续
```

**优势**：
- 无需维护状态
- 自动恢复（程序重启后识别当前进度）
- 仓位永远是真实的

## 实际例子

### 场景：目标建仓30次，每次0.1

```yaml
配置:
  SIZE: 0.1
  BUILD_UP_ITERATIONS: 30
  目标仓位: 3.0
```

### Case 1: 正常运行
```
启动 → Lighter仓位=0
第1次交易 → Lighter=0.1 → 进度: 1/30
第2次交易 → Lighter=0.2 → 进度: 2/30
...
第30次交易 → Lighter=3.0 → 进度: 30/30 ✓
进入HOLD阶段
```

### Case 2: 程序中途崩溃
```
运行15次后崩溃 → Lighter=1.5
重启程序：
  → 读取API: Lighter=1.5
  → 计算: 1.5/0.1 = 15次已完成
  → 日志: "Resuming from 15/30 (50%)"
  → 继续从第16次开始
```

### Case 3: 部分订单失败
```
目标30次，但第20次失败
  → Lighter=1.9（不是2.0）
  → 计算: 1.9/0.1 = 19次
  → 继续尝试，直到达到3.0
```

### Case 4: 最后一单的精确控制
```
当前Lighter=2.95，目标=3.0
  → 剩余: 3.0 - 2.95 = 0.05
  → 下单: min(0.1, 0.05) = 0.05
  → 精确达到目标
```

## 代码对比

### 建仓阶段

**旧代码**：
```python
for iteration in range(1, self.build_up_iterations + 1):
    self.logger.info(f"Build iteration {iteration}/{self.build_up_iterations}")
    place_order(self.order_quantity)
```

**新代码**：
```python
while True:
    position = await self.positions.get_positions()
    completed = int(position.lighter / self.order_quantity)

    if completed >= self.build_iterations:
        break

    remaining = target_position - abs(position.lighter)
    order_size = min(self.order_quantity, remaining)
    place_order(order_size)
```

### 平仓阶段

**旧代码**：
```python
close_iterations = int(abs(self.grvt_position) / self.order_quantity)
for iteration in range(close_iterations):
    place_close_order(self.order_quantity)
```

**新代码**：
```python
while abs(position.grvt) > 0.001:
    position = await self.positions.get_positions()
    quantity = min(self.order_quantity, abs(position.grvt))
    place_close_order(quantity)
```

## 为什么以Lighter为准？

1. **Lighter是固定的**：其他交易所可能更换
2. **更简单**：Lighter的仓位查询API更稳定
3. **业务逻辑**：Lighter是主要的积分/费率来源

## 状态恢复示例

程序可以在任何时候重启，自动识别当前状态：

```python
async def detect_current_state(position):
    """自动检测当前处于哪个阶段"""

    if abs(position.lighter) < 0.001:
        return "IDLE"  # 空仓

    builds = abs(position.lighter) / ORDER_SIZE

    if builds < TARGET_BUILDS:
        return f"BUILDING ({builds}/{TARGET_BUILDS})"

    if builds >= TARGET_BUILDS:
        if currently_in_hold_time():  # 基于时间戳
            return "HOLDING"
        else:
            return "READY_TO_WINDDOWN"
```

## 配置建议

```yaml
# 传统配置（保持兼容）
BUILD_UP_ITERATIONS: 30  # 目标建仓次数
SIZE: 0.1                # 每次订单大小

# 内部计算
目标仓位 = BUILD_UP_ITERATIONS * SIZE = 3.0

# 进度追踪
当前进度 = Lighter仓位 / SIZE
完成百分比 = (当前进度 / BUILD_UP_ITERATIONS) * 100
```

## 总结

这个改进让系统：
- **更健壮**：不怕崩溃和重启
- **更准确**：基于真实仓位，不是理论计数
- **更简单**：减少状态维护
- **更智能**：自动恢复和调整