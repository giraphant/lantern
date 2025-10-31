"""
资金费率套利机器人 - 基于GRVT和Lighter之间的费率差进行套利。

策略逻辑：
1. 定期检查两个交易所的资金费率
2. 归一化为年化费率后计算费率差
3. 当费率差 > 阈值时建仓
4. 当费率差 < 阈值或仓位达上限时平仓
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

from exchanges.grvt import GrvtClient
from exchanges.lighter import LighterClient
from hedge.safety_checker import SafetyChecker, SafetyAction
from hedge.rebalancer import Rebalancer, TradeAction
from hedge.trading_executor import TradingExecutor
from hedge.funding_rate_normalizer import (
    FundingRateData,
    FundingRateNormalizer,
    FundingRateSpread
)
from hedge.funding_rate_checker import FundingRateChecker, FundingAction
from helpers.pushover_notifier import PushoverNotifier


class Config:
    """配置类"""
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class HedgeBotFunding:
    """资金费率套利机器人"""

    def __init__(self):
        self.logger = self._setup_logger()
        self.load_config()

        # 初始化交易所客户端
        self.grvt = self._init_grvt_client()
        self.lighter = self._init_lighter_client()

        # 初始化模块
        self.executor = TradingExecutor(self.grvt, self.lighter, self.logger)
        self.notifier = PushoverNotifier()

    def _setup_logger(self):
        """设置日志"""
        logger = logging.getLogger('HedgeBotFunding')
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s: %(message)s'))
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

        # API配置
        self.grvt_api_key = os.getenv("GRVT_API_KEY")
        self.grvt_private_key = os.getenv("GRVT_PRIVATE_KEY")
        self.lighter_private_key = os.getenv("LIGHTER_PRIVATE_KEY") or os.getenv("LIGHTER_API_PRIVATE_KEY")

        # 交易参数
        self.symbol = os.getenv("TRADING_SYMBOL", "BTC")
        self.order_quantity = Decimal(os.getenv("TRADING_SIZE", "0.1"))

        # 资金费率特定配置
        self.funding_build_threshold = Decimal(os.getenv("FUNDING_BUILD_THRESHOLD_APR", "0.05"))  # 5% APR
        self.funding_close_threshold = Decimal(os.getenv("FUNDING_CLOSE_THRESHOLD_APR", "0.02"))  # 2% APR
        self.max_position = Decimal(os.getenv("MAX_POSITION", "10"))
        self.check_interval = int(os.getenv("FUNDING_CHECK_INTERVAL", "300"))  # 5分钟

        # 安全参数
        self.max_position_per_side = self.max_position * Decimal("1.5")
        self.max_total_position = self.max_position * Decimal("1.5")
        self.max_imbalance = self.order_quantity * Decimal("3")

        if not all([self.grvt_api_key, self.grvt_private_key, self.lighter_private_key]):
            raise ValueError("Missing API keys")

        # 确保环境变量可用
        if not os.getenv("LIGHTER_PRIVATE_KEY"):
            os.environ["LIGHTER_PRIVATE_KEY"] = self.lighter_private_key

    def _init_grvt_client(self):
        """初始化GRVT客户端"""
        config = Config(
            api_key=self.grvt_api_key,
            priv_key_file=self.grvt_private_key,
            ticker=self.symbol,
            quantity=self.order_quantity,
            block_order_recreation=False,
            block_orders=False
        )
        return GrvtClient(config)

    def _init_lighter_client(self):
        """初始化Lighter客户端"""
        config = Config(
            ticker=self.symbol,
            quantity=self.order_quantity,
            direction="long",
            close_order_side="sell"
        )
        return LighterClient(config)

    async def connect(self):
        """连接交易所"""
        self.logger.info("Connecting to exchanges...")
        await self.grvt.connect()
        self.logger.info("✓ GRVT connected")

        await self.lighter.connect()
        self.logger.info("✓ Lighter connected")

    async def get_funding_spread(self) -> FundingRateSpread:
        """获取归一化的费率差"""
        # 获取GRVT费率和周期
        grvt_rate = await self.grvt.get_funding_rate(self.grvt.config.contract_id)
        grvt_interval = await self.grvt.get_funding_interval_hours(self.grvt.config.contract_id)

        # 获取Lighter费率和周期
        lighter_rate = await self.lighter.get_funding_rate(self.lighter.config.contract_id)
        lighter_interval = await self.lighter.get_funding_interval_hours(self.lighter.config.contract_id)

        # 创建费率数据
        grvt_data = FundingRateData(
            rate=grvt_rate,
            interval_hours=grvt_interval,
            exchange_name="GRVT"
        )

        lighter_data = FundingRateData(
            rate=lighter_rate,
            interval_hours=lighter_interval,
            exchange_name="Lighter"
        )

        # 计算归一化费率差
        return FundingRateNormalizer.calculate_spread(grvt_data, lighter_data)

    async def run(self):
        """主循环"""
        try:
            await self.connect()

            # 检查初始仓位
            position = await self.executor.get_positions()
            self.logger.info(f"Initial position: GRVT={position.grvt_position}, Lighter={position.lighter_position}")

            # 主循环
            while True:
                # ========== 步骤1: 获取真实状态 ==========
                position = await self.executor.get_positions()
                pending_orders = await self.executor.get_pending_orders()

                # ========== 步骤2: 安全检查 ==========
                safety_result = SafetyChecker.check_all(
                    position,
                    self.max_position_per_side,
                    self.max_total_position,
                    self.max_imbalance,
                    pending_orders=pending_orders,
                    max_pending_per_side=1
                )

                if safety_result.action == SafetyAction.CANCEL_ALL_ORDERS:
                    self.logger.warning(f"⚠️  {safety_result.reason}")
                    self.logger.warning("   Cancelling all orders...")
                    await self.executor.cancel_all_orders()
                    await asyncio.sleep(2)
                    continue

                elif safety_result.action == SafetyAction.PAUSE:
                    self.logger.error(f"❌ {safety_result.reason}")
                    self.logger.error(f"   Position: {position}")
                    self.logger.error("   Pausing for 60 seconds...")
                    await self.notifier.notify_warning(
                        message=f"{safety_result.reason}\\n\\nPosition:\\nGRVT: {position.grvt_position}\\nLighter: {position.lighter_position}\\nTotal: {position.total_position}\\n\\nBot paused for 60s",
                        title="⚠️ Safety Limit Triggered"
                    )
                    await asyncio.sleep(60)
                    continue

                # ========== 步骤3: 检查是否需要打平不平衡 ==========
                rebalance_threshold = self.order_quantity

                if position.imbalance > rebalance_threshold:
                    target_position = Decimal(0)
                    rebalance_instruction = Rebalancer.calculate_rebalance(
                        current_position=position,
                        target_total_position=target_position,
                        order_size=self.order_quantity,
                        tolerance=rebalance_threshold
                    )

                    if rebalance_instruction.action != TradeAction.HOLD:
                        self.logger.warning(f"⚖️  REBALANCING: Imbalance={position.imbalance}")
                        self.logger.warning(f"   {rebalance_instruction.reason}")

                        result = await self.executor.execute_trade(
                            rebalance_instruction.action,
                            rebalance_instruction.quantity,
                            wait_for_fill=False,
                            fill_timeout=30
                        )

                        if not result.success:
                            self.logger.error(f"   Rebalance failed: {result.error}")

                        await asyncio.sleep(2)
                        continue

                # ========== 步骤4: 获取资金费率 ==========
                spread = await self.get_funding_spread()

                # 记录费率信息
                funding_info = FundingRateNormalizer.format_rate_info(spread)
                self.logger.info(f"💰 {funding_info}")

                # ========== 步骤5: 检查套利机会 ==========
                check_result = FundingRateChecker.check_funding_opportunity(
                    spread=spread,
                    position=position,
                    build_threshold_apr=self.funding_build_threshold,
                    close_threshold_apr=self.funding_close_threshold,
                    max_position=self.max_position
                )

                self.logger.info(f"📊 Action: {check_result.action.value} | {check_result.reason}")

                # ========== 步骤6: 执行交易 ==========
                if check_result.action == FundingAction.BUILD:
                    await self._handle_building_phase(check_result.profitable_side)

                elif check_result.action == FundingAction.WINDDOWN:
                    await self._handle_winddown_phase(check_result.profitable_side)

                elif check_result.action == FundingAction.HOLD:
                    # 估算收益
                    if abs(position.total_position) > Decimal("0.1"):
                        daily_profit = FundingRateChecker.estimate_daily_profit(
                            spread=spread,
                            position_size=abs(position.total_position)
                        )
                        self.logger.info(f"💵 Estimated daily profit: ${daily_profit:.2f}")

                    # 等待下次检查
                    self.logger.info(f"⏳ Next check in {self.check_interval}s...")
                    await asyncio.sleep(self.check_interval)

        except KeyboardInterrupt:
            self.logger.info("\\nShutting down...")
        except Exception as e:
            self.logger.error(f"Fatal error: {e}", exc_info=True)
            await self.notifier.notify_critical(
                message=f"Funding bot crashed with error:\\n{str(e)}\\n\\nBot has stopped running!",
                title="🔴 Funding Bot Crashed"
            )
        finally:
            await self.cleanup()

    async def _handle_building_phase(self, profitable_side: str):
        """处理建仓阶段"""
        self.logger.info(f"📈 BUILDING {profitable_side.upper()} position: {self.order_quantity}")

        # 根据盈利方向选择交易动作
        if profitable_side == "long":
            # 做多GRVT
            action = TradeAction.BUILD_LONG
        else:
            # 做空GRVT
            action = TradeAction.CLOSE_LONG

        result = await self.executor.execute_trade(
            action=action,
            quantity=self.order_quantity,
            wait_for_fill=True,
            fill_timeout=30
        )

        if not result.success:
            self.logger.warning(f"   Trade failed: {result.error}, retrying in 5s...")
            await asyncio.sleep(5)

    async def _handle_winddown_phase(self, profitable_side: str):
        """处理平仓阶段"""
        self.logger.info(f"📉 WINDING DOWN {profitable_side.upper()} position: {self.order_quantity}")

        # 根据盈利方向选择平仓动作
        if profitable_side == "long":
            # 平多仓
            action = TradeAction.CLOSE_LONG
        else:
            # 平空仓
            action = TradeAction.BUILD_LONG

        result = await self.executor.execute_trade(
            action=action,
            quantity=self.order_quantity,
            wait_for_fill=True,
            fill_timeout=30
        )

        if not result.success:
            self.logger.warning(f"   Trade failed: {result.error}, retrying in 5s...")
            await asyncio.sleep(5)

    async def cleanup(self):
        """清理资源"""
        try:
            self.logger.info("Cleaning up...")
            await self.grvt.disconnect()
            await self.lighter.disconnect()
        except:
            pass


async def main():
    bot = HedgeBotFunding()
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
