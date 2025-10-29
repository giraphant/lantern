"""
Hedge Bot V3 - 使用新的服务架构。

采用分层设计：
- 服务层（HedgeService）：抽象的对冲操作
- 引擎层（TradingEngine）：业务逻辑和状态管理
- 交易所层：复用现有的交易所实现
"""

import asyncio
import logging
import os
import sys
from decimal import Decimal
from pathlib import Path

# 抑制冗余日志
logging.getLogger().setLevel(logging.WARNING)
logging.getLogger('root').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.ERROR)
logging.getLogger('urllib3.connectionpool').setLevel(logging.ERROR)
logging.getLogger('asyncio').setLevel(logging.ERROR)
logging.getLogger('asyncio.selector_events').setLevel(logging.ERROR)
logging.getLogger('pysdk').setLevel(logging.ERROR)

import dotenv

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from hedge.models import TradingConfig
from hedge.managers import SafetyManager
from hedge.services import GrvtLighterHedgeService
from hedge.core.trading_engine import TradingEngine
from exchanges.grvt import GrvtClient
from lighter.signer_client import SignerClient


class Config:
    """Simple config class for GRVT client compatibility."""
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class HedgeBotV3:
    """
    Hedge Bot V3 - 使用服务架构的主类。
    """

    def __init__(self, config: TradingConfig):
        self.config = config
        self.logger = self._setup_logger()
        self.engine = None

    def _setup_logger(self) -> logging.Logger:
        """设置日志记录器"""
        logger = logging.getLogger(f'hedge_bot_v3_{self.config.symbol}')
        logger.setLevel(logging.DEBUG)

        # 清除现有处理器
        logger.handlers.clear()

        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # 格式化器
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s: %(message)s'
        )
        console_handler.setFormatter(formatter)

        logger.addHandler(console_handler)

        return logger

    async def initialize(self) -> None:
        """初始化所有组件"""
        try:
            self.logger.info("=" * 50)
            self.logger.info("Initializing Hedge Bot V3...")
            self.logger.info(f"Symbol: {self.config.symbol}")
            self.logger.info(f"Order Size: {self.config.order_quantity}")
            self.logger.info(f"Target Cycles: {self.config.target_cycles}")
            self.logger.info(f"Max Position: {self.config.max_position}")
            self.logger.info(f"Rebalance Tolerance: {self.config.rebalance_tolerance}")
            self.logger.info("=" * 50)

            # 初始化GRVT客户端
            self.logger.info("Initializing GRVT client...")
            grvt_config = Config(
                api_key=self.config.grvt_api_key,
                priv_key_file=self.config.grvt_private_key,
                block_order_recreation=self.config.block_order_recreation,
                block_orders=self.config.block_orders
            )
            grvt_client = GrvtClient(grvt_config, self.logger)

            # 初始化Lighter客户端
            self.logger.info("Initializing Lighter client...")
            lighter_client = SignerClient(
                api_key=self.config.lighter_api_key,
                api_private_key=self.config.lighter_private_key,
                api_host=self.config.lighter_api_host
            )

            # 创建对冲服务
            self.logger.info("Creating hedge service...")
            hedge_service = GrvtLighterHedgeService(
                grvt_client=grvt_client,
                lighter_client=lighter_client,
                config=self.config,
                logger=self.logger
            )

            # 创建安全管理器
            self.logger.info("Creating safety manager...")
            safety_manager = SafetyManager(self.config, self.logger)

            # 创建交易引擎
            self.logger.info("Creating trading engine...")
            self.engine = TradingEngine(
                hedge_service=hedge_service,
                safety_manager=safety_manager,
                config=self.config,
                logger=self.logger
            )

            self.logger.info("Initialization complete!")

        except Exception as e:
            self.logger.error(f"Failed to initialize: {e}")
            raise

    async def run(self) -> None:
        """运行主循环"""
        try:
            if not self.engine:
                await self.initialize()

            self.logger.info("Starting trading engine...")
            await self.engine.start()

        except KeyboardInterrupt:
            self.logger.info("Received interrupt signal")
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """关闭机器人"""
        self.logger.info("Shutting down...")
        if self.engine:
            await self.engine.stop()
        self.logger.info("Shutdown complete")


def load_config() -> TradingConfig:
    """从环境变量加载配置"""
    # 尝试多个可能的.env文件位置
    env_paths = [
        Path(".env"),
        Path("../.env"),
        Path("/app/.env"),
    ]

    for env_path in env_paths:
        if env_path.exists():
            dotenv.load_dotenv(env_path, override=True)
            print(f"Loaded environment from {env_path}")
            break

    # 构建配置
    config = TradingConfig(
        # 基础配置
        symbol=os.getenv("SYMBOL", "BTC"),
        grvt_api_key=os.getenv("GRVT_API_KEY"),
        grvt_private_key=os.getenv("GRVT_PRIVATE_KEY"),
        lighter_api_key=os.getenv("LIGHTER_API_KEY"),
        lighter_private_key=os.getenv("LIGHTER_PRIVATE_KEY"),
        lighter_api_host=os.getenv("LIGHTER_API_HOST", "https://chain.lighter.xyz/api"),

        # 交易参数
        order_quantity=Decimal(os.getenv("SIZE", "0.3")),
        target_cycles=int(os.getenv("TARGET_CYCLES", "5")),
        spread_bps=int(os.getenv("SPREAD_BPS", "10")),
        cycle_interval=int(os.getenv("CYCLE_INTERVAL", "60")),
        order_timeout=int(os.getenv("ORDER_TIMEOUT", "30")),

        # 安全参数
        max_position=Decimal(os.getenv("MAX_POSITION", "10.0")),
        rebalance_tolerance=Decimal(os.getenv("REBALANCE_TOLERANCE", "0.5")),
        emergency_stop_loss=Decimal(os.getenv("EMERGENCY_STOP_LOSS", "5.0")),

        # 控制参数
        block_orders=os.getenv("BLOCK_ORDERS", "false").lower() == "true",
        block_order_recreation=os.getenv("BLOCK_ORDER_RECREATION", "false").lower() == "true",
    )

    # 验证必要参数
    if not all([
        config.grvt_api_key,
        config.grvt_private_key,
        config.lighter_api_key,
        config.lighter_private_key
    ]):
        raise ValueError("Missing required API keys")

    return config


async def main():
    """主函数"""
    try:
        config = load_config()
        bot = HedgeBotV3(config)
        await bot.run()
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())