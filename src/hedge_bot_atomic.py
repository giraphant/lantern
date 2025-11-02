"""
资金费率套利机器人 - 基于Atomic框架重构版本

使用新的原子化架构，支持任意交易所组合
"""

import asyncio
import logging
import os
import sys
from decimal import Decimal
from pathlib import Path
import dotenv

# 抑制冗余日志
logging.getLogger('urllib3').setLevel(logging.ERROR)
logging.getLogger('asyncio').setLevel(logging.ERROR)
logging.getLogger('pysdk').setLevel(logging.ERROR)

# 导入原子化框架
from atomic import (
    Symbol,
    ArbitrageConfig,
    AtomicQueryer,
    AtomicTrader,
    ArbitrageOrchestrator,
    SimpleStrategyRunner
)

# 导入交易所适配器（保留原有实现）
from exchanges.grvt import GrvtClient
from exchanges.lighter import LighterClient
from exchanges.binance import BinanceClient
from exchanges.backpack import BackpackClient

# 导入通知工具
from helpers.pushover_notifier import PushoverNotifier
from helpers.telegram_interactive_bot import TelegramInteractiveBot


class Config:
    """配置类（兼容现有适配器）"""
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class AtomicHedgeBot:
    """
    基于Atomic框架的资金费率套利机器人

    优势：
    - 支持任意数量交易所
    - 自动发现最佳套利对
    - 零代码修改添加新交易所
    """

    def __init__(self):
        self.logger = self._setup_logger()
        self.load_config()

        # 初始化通知
        self.notifier = PushoverNotifier()
        self.telegram_bot = self._init_telegram_bot()

        # 将在run时初始化
        self.orchestrator = None
        self.exchange_clients = {}

    def _setup_logger(self):
        """设置日志"""
        logger = logging.getLogger('AtomicHedgeBot')
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter('%(asctime)s - %(levelname)s: %(message)s')
        )
        logger.addHandler(handler)
        return logger

    def load_config(self):
        """加载配置"""
        # 加载.env
        env_paths = [Path(".env"), Path("../.env"), Path("/app/.env")]
        for env_path in env_paths:
            if env_path.exists():
                dotenv.load_dotenv(env_path, override=True)
                break

        # 交易所配置（支持多个，逗号分隔）
        # 例如: EXCHANGES=GRVT,Lighter,Binance
        exchanges_str = os.getenv("EXCHANGES", "GRVT,Lighter")
        self.exchange_names = [e.strip() for e in exchanges_str.split(",")]
        self.logger.info(f"Configured exchanges: {self.exchange_names}")

        # 交易参数
        self.symbol_base = os.getenv("TRADING_SYMBOL", "BTC")
        self.symbol_quote = os.getenv("TRADING_QUOTE", "USDT")
        self.order_quantity = Decimal(os.getenv("TRADING_SIZE", "0.1"))

        # 策略配置
        self.config = ArbitrageConfig(
            build_threshold=Decimal(os.getenv("FUNDING_BUILD_THRESHOLD_APR", "0.05")),
            close_threshold=Decimal(os.getenv("FUNDING_CLOSE_THRESHOLD_APR", "0.02")),
            max_position=Decimal(os.getenv("MAX_POSITION", "10")),
            trade_size=self.order_quantity,
            max_position_per_exchange=Decimal(os.getenv("MAX_POSITION_PER_EXCHANGE", "15")),
            max_total_exposure=Decimal(os.getenv("MAX_TOTAL_EXPOSURE", "15")),
            max_imbalance=self.order_quantity * Decimal("3")
        )

        # 运行参数
        self.check_interval = int(os.getenv("FUNDING_CHECK_INTERVAL", "300"))

        self.logger.info(f"Strategy config: build={self.config.build_threshold:.2%}, "
                        f"close={self.config.close_threshold:.2%}, "
                        f"max_pos={self.config.max_position}")

    def _init_telegram_bot(self):
        """初始化Telegram Bot"""
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        enable_commands = os.getenv("TELEGRAM_ENABLE_COMMANDS", "true").lower() in ("true", "1", "yes")

        if not token or not chat_id:
            self.logger.info("Telegram Bot not configured (optional)")
            return None

        try:
            bot = TelegramInteractiveBot(token, chat_id, enable_commands=enable_commands)
            # TODO: 设置回调函数
            mode = "with commands" if enable_commands else "notification-only"
            self.logger.info(f"Telegram Bot initialized ({mode})")
            return bot
        except Exception as e:
            self.logger.error(f"Failed to initialize Telegram Bot: {e}")
            return None

    def _init_exchange_client(self, exchange_name: str):
        """
        初始化单个交易所客户端

        Args:
            exchange_name: 交易所名称 (GRVT, Lighter, Binance, etc.)

        Returns:
            BaseExchangeClient实例
        """
        exchange_name = exchange_name.upper()

        if exchange_name == "GRVT":
            config = Config(
                api_key=os.getenv("GRVT_API_KEY"),
                priv_key_file=os.getenv("GRVT_PRIVATE_KEY"),
                ticker=self.symbol_base,
                quantity=self.order_quantity,
                block_order_recreation=False,
                block_orders=False
            )
            return GrvtClient(config)

        elif exchange_name == "LIGHTER":
            config = Config(
                ticker=self.symbol_base,
                quantity=self.order_quantity,
                direction="",
                close_order_side=""
            )
            return LighterClient(config)

        elif exchange_name == "BINANCE":
            config = Config(
                ticker=self.symbol_base,
                quantity=self.order_quantity
            )
            return BinanceClient(config)

        elif exchange_name == "BACKPACK":
            config = Config(
                ticker=self.symbol_base,
                quantity=self.order_quantity
            )
            return BackpackClient(config)

        else:
            raise ValueError(f"Unsupported exchange: {exchange_name}")

    async def connect_exchanges(self):
        """连接所有配置的交易所"""
        self.logger.info("Connecting to exchanges...")

        for exchange_name in self.exchange_names:
            try:
                client = self._init_exchange_client(exchange_name)
                await client.connect()
                self.exchange_clients[exchange_name.lower()] = client
                self.logger.info(f"✓ {exchange_name} connected")
            except Exception as e:
                self.logger.error(f"✗ Failed to connect to {exchange_name}: {e}")
                # 继续连接其他交易所

        if len(self.exchange_clients) < 2:
            raise RuntimeError(f"Need at least 2 exchanges, got {len(self.exchange_clients)}")

        # 启动Telegram Bot
        if self.telegram_bot:
            await self.telegram_bot.start()
            self.logger.info("✓ Telegram Bot started")

    async def disconnect_exchanges(self):
        """断开所有交易所连接"""
        self.logger.info("Disconnecting from exchanges...")

        for exchange_name, client in self.exchange_clients.items():
            try:
                await client.disconnect()
                self.logger.info(f"✓ {exchange_name} disconnected")
            except Exception as e:
                self.logger.error(f"✗ Failed to disconnect from {exchange_name}: {e}")

    def build_orchestrator(self):
        """
        构建Atomic框架的编排器

        这里将所有交易所客户端转换为Atomic组件
        """
        symbol = Symbol(
            base=self.symbol_base,
            quote=self.symbol_quote,
            contract_type="PERP"
        )

        # 创建Queryers和Traders
        queryers = {}
        traders = {}

        for exchange_name, client in self.exchange_clients.items():
            queryers[exchange_name] = AtomicQueryer(client, symbol)
            traders[exchange_name] = AtomicTrader(client, symbol)

        # 创建编排器
        self.orchestrator = ArbitrageOrchestrator(
            queryers=queryers,
            traders=traders,
            config=self.config,
            symbol=symbol
        )

        self.logger.info(f"✓ Orchestrator built with {len(queryers)} exchanges")

    async def run(self):
        """主循环"""
        try:
            # 连接交易所
            await self.connect_exchanges()

            # 构建编排器
            self.build_orchestrator()

            # 使用SimpleStrategyRunner运行
            runner = SimpleStrategyRunner(
                orchestrator=self.orchestrator,
                interval=self.check_interval
            )

            self.logger.info("\n" + "=" * 60)
            self.logger.info("🚀 Atomic Hedge Bot Started")
            self.logger.info(f"   Exchanges: {list(self.exchange_clients.keys())}")
            self.logger.info(f"   Symbol: {self.symbol_base}-{self.symbol_quote}")
            self.logger.info(f"   Interval: {self.check_interval}s")
            self.logger.info("=" * 60 + "\n")

            # 发送启动通知
            await self.notifier.notify(
                message=f"Atomic Hedge Bot started\n"
                        f"Exchanges: {', '.join(self.exchange_clients.keys())}\n"
                        f"Symbol: {self.symbol_base}\n"
                        f"Build threshold: {self.config.build_threshold:.2%} APR",
                title="🚀 Bot Started"
            )

            # 运行策略
            await runner.start()

        except KeyboardInterrupt:
            self.logger.info("\nShutdown requested by user")

        except Exception as e:
            self.logger.error(f"Fatal error: {e}", exc_info=True)
            await self.notifier.notify_warning(
                message=f"Bot crashed: {str(e)}",
                title="❌ Fatal Error"
            )

        finally:
            # 清理
            await self.disconnect_exchanges()
            self.logger.info("Bot stopped")


async def main():
    """主函数"""
    bot = AtomicHedgeBot()
    await bot.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown by user")
