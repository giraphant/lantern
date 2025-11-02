"""
原子化框架测试示例

演示如何使用新的原子化架构来运行套利策略
"""

import asyncio
import logging
import os
from decimal import Decimal
from pathlib import Path
import dotenv

# 导入原子化框架
from atomic import (
    Symbol,
    ArbitrageConfig,
    AtomicQueryer,
    AtomicTrader,
    ArbitrageOrchestrator,
    SimpleStrategyRunner
)

# 导入现有的交易所适配器
from exchanges.grvt import GrvtClient
from exchanges.lighter import LighterClient
from exchanges.binance import BinanceClient


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Config:
    """简单的配置类（兼容现有适配器）"""
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


async def main():
    """主函数：演示原子化框架的使用"""

    # ========== 步骤1: 加载环境变量 ==========
    logger.info("Loading configuration...")

    env_paths = [Path(".env"), Path("../.env"), Path("/app/.env")]
    for env_path in env_paths:
        if env_path.exists():
            dotenv.load_dotenv(env_path, override=True)
            break

    # ========== 步骤2: 定义交易参数 ==========
    symbol = Symbol(
        base="BTC",
        quote="USDT",
        contract_type="PERP"
    )

    config = ArbitrageConfig(
        build_threshold=Decimal("0.05"),      # 5% APR 建仓阈值
        close_threshold=Decimal("0.02"),      # 2% APR 平仓阈值
        max_position=Decimal("10"),           # 最大单边仓位
        trade_size=Decimal("0.1"),            # 每次交易大小
        max_imbalance=Decimal("0.3")          # 最大不平衡度
    )

    # ========== 步骤3: 初始化交易所客户端 ==========
    logger.info("Initializing exchange clients...")

    # GRVT
    grvt_config = Config(
        api_key=os.getenv("GRVT_API_KEY"),
        priv_key_file=os.getenv("GRVT_PRIVATE_KEY"),
        ticker="BTC",
        quantity=config.trade_size,
        block_order_recreation=False,
        block_orders=False
    )
    grvt_client = GrvtClient(grvt_config)

    # Lighter
    lighter_config = Config(
        ticker="BTC",
        quantity=config.trade_size,
        direction="",  # 将在交易时指定
        close_order_side=""
    )
    lighter_client = LighterClient(lighter_config)

    # 连接到交易所
    logger.info("Connecting to exchanges...")
    await grvt_client.connect()
    logger.info("✓ GRVT connected")

    await lighter_client.connect()
    logger.info("✓ Lighter connected")

    # ========== 步骤4: 创建原子化组件 ==========
    logger.info("Creating atomic components...")

    # 创建Queryer（查询器）
    queryers = {
        "grvt": AtomicQueryer(grvt_client, symbol),
        "lighter": AtomicQueryer(lighter_client, symbol)
    }

    # 创建Trader（交易器）
    traders = {
        "grvt": AtomicTrader(grvt_client, symbol),
        "lighter": AtomicTrader(lighter_client, symbol)
    }

    # ========== 步骤5: 创建编排器 ==========
    logger.info("Creating orchestrator...")

    orchestrator = ArbitrageOrchestrator(
        queryers=queryers,
        traders=traders,
        config=config,
        symbol=symbol
    )

    # ========== 步骤6: 测试单次运行 ==========
    logger.info("\n" + "=" * 60)
    logger.info("Testing single strategy cycle...")
    logger.info("=" * 60 + "\n")

    try:
        orders = await orchestrator.run_strategy_cycle()

        if orders:
            logger.info(f"\n✅ Executed {len(orders)} orders:")
            for order in orders:
                logger.info(f"  - {order}")
        else:
            logger.info("\n✅ Strategy cycle completed (no trades)")

    except Exception as e:
        logger.error(f"Error in strategy cycle: {e}", exc_info=True)

    # ========== 步骤7: 可选 - 运行持续策略 ==========
    # 取消下面的注释来运行持续策略
    """
    logger.info("\n" + "=" * 60)
    logger.info("Starting continuous strategy runner...")
    logger.info("=" * 60 + "\n")

    runner = SimpleStrategyRunner(
        orchestrator=orchestrator,
        interval=300  # 5分钟
    )

    try:
        await runner.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    """

    # ========== 清理 ==========
    logger.info("\nDisconnecting from exchanges...")
    await grvt_client.disconnect()
    await lighter_client.disconnect()
    logger.info("✓ Disconnected")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutdown by user")
