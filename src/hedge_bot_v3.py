"""
对冲机器人V3 - 清晰解耦的架构。

架构：
├── SafetyChecker (纯函数 - 安全检查)
├── Rebalancer (纯函数 - 计算操作)
├── TradingExecutor (执行层 - 调用exchange)
└── HedgeBot (协调器 - 主循环)
"""

import asyncio
import logging
import os
import sys
from decimal import Decimal
from enum import Enum
from pathlib import Path
import dotenv

# 抑制冗余日志
logging.getLogger('urllib3').setLevel(logging.ERROR)
logging.getLogger('asyncio').setLevel(logging.ERROR)
logging.getLogger('pysdk').setLevel(logging.ERROR)

from exchanges.grvt import GrvtClient
from exchanges.lighter import LighterClient
from hedge.safety_checker import SafetyChecker, PositionState, SafetyAction
from hedge.rebalancer import Rebalancer, TradeAction
from hedge.trading_executor import TradingExecutor
from hedge.phase_detector import PhaseDetector, TradingPhase


class Config:
    """配置类"""
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class HedgeBotV3:
    """对冲机器人V3 - 清晰解耦的架构"""

    def __init__(self):
        self.logger = self._setup_logger()
        self.load_config()

        # 初始化交易所客户端
        self.grvt = self._init_grvt_client()
        self.lighter = self._init_lighter_client()

        # 初始化模块
        self.executor = TradingExecutor(self.grvt, self.lighter, self.logger)

    def _setup_logger(self):
        """设置日志"""
        logger = logging.getLogger('HedgeBotV3')
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
        self.symbol = os.getenv("TRADING_SYMBOL", "BNB")
        self.order_quantity = Decimal(os.getenv("TRADING_SIZE", "0.1"))
        self.target_cycles = int(os.getenv("CYCLE_TARGET", "5"))
        self.hold_time = int(os.getenv("CYCLE_HOLD_TIME", "180"))

        # 安全参数
        self.max_position_per_side = self.order_quantity * self.target_cycles * Decimal("2")
        self.max_total_position = self.order_quantity * self.target_cycles * Decimal("2")
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

    async def run(self):
        """主循环"""
        try:
            await self.connect()

            # 检查初始仓位
            position = await self.executor.get_positions()
            self.logger.info(f"Initial position: GRVT={position.grvt_position}, Lighter={position.lighter_position}")

            # 主循环 - 完全无状态，每次都从交易所获取真实状态
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

                # 根据安全检查结果执行对应操作（纯编排）
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
                    await asyncio.sleep(60)
                    continue

                # ========== 步骤3: 检查是否需要打平不平衡 ==========
                # 改为超过order_size才触发打平（因为GRVT可能有挂单未成交）
                rebalance_threshold = self.order_quantity

                if position.imbalance > rebalance_threshold:
                    # 需要打平，目标 = Lighter仓位（让两边完全对冲）
                    target_position = position.lighter_position

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
                            wait_for_fill=True,
                            fill_timeout=30
                        )

                        if not result.success:
                            self.logger.error(f"   Rebalance failed: {result.error}")

                        await asyncio.sleep(2)
                        continue  # 打平后重新开始，跳过阶段判断和正常交易

                # ========== 步骤4: 阶段判断 ==========
                last_order = await self.grvt.get_last_filled_order(
                    contract_id=self.grvt.config.contract_id
                )

                last_order_side = None
                last_order_time = None
                if last_order:
                    last_order_side, last_order_time = last_order

                phase_info = PhaseDetector.detect_phase(
                    position=position,
                    target_cycles=self.target_cycles,
                    order_size=self.order_quantity,
                    hold_time=self.hold_time,
                    last_order_side=last_order_side,
                    last_order_time=last_order_time
                )

                self.logger.debug(f"📍 Phase: {phase_info.phase.value} - {phase_info.reason}")

                # ========== 步骤5: 根据阶段执行对应操作 ==========
                if phase_info.phase == TradingPhase.BUILDING:
                    await self._handle_building_phase(position)

                elif phase_info.phase == TradingPhase.HOLDING:
                    # 持仓等待中，不执行交易
                    if phase_info.time_remaining:
                        self.logger.info(f"⏳ HOLDING: {phase_info.time_remaining}s remaining")
                    await asyncio.sleep(min(10, phase_info.time_remaining or 10))

                elif phase_info.phase == TradingPhase.WINDING_DOWN:
                    await self._handle_winddown_phase(position)

                # 短暂休息
                await asyncio.sleep(2)

        except KeyboardInterrupt:
            self.logger.info("\nShutting down...")
        except Exception as e:
            self.logger.error(f"Fatal error: {e}", exc_info=True)
        finally:
            await self.cleanup()

    async def _handle_building_phase(self, position: PositionState):
        """处理建仓阶段"""
        # 目标：达到target_cycles的仓位
        target_position = self.order_quantity * self.target_cycles

        # 使用Rebalancer计算如何达到目标
        instruction = Rebalancer.calculate_rebalance(
            current_position=position,
            target_total_position=target_position,
            order_size=self.order_quantity,
            tolerance=self.order_quantity * Decimal("0.1")
        )

        if instruction.action == TradeAction.HOLD:
            # 已达到目标，不需要操作
            return

        # 执行建仓操作
        self.logger.info(f"📈 BUILDING: {instruction.reason}")
        result = await self.executor.execute_trade(
            instruction.action,
            instruction.quantity,
            wait_for_fill=True,
            fill_timeout=30
        )

        if not result.success:
            self.logger.warning(f"   Trade failed: {result.error}, retrying in 5s...")
            await asyncio.sleep(5)

    async def _handle_winddown_phase(self, position: PositionState):
        """处理平仓阶段"""
        # 目标：回到0仓位
        target_position = Decimal(0)

        # 使用Rebalancer计算如何达到目标
        instruction = Rebalancer.calculate_rebalance(
            current_position=position,
            target_total_position=target_position,
            order_size=self.order_quantity,
            tolerance=self.order_quantity * Decimal("0.1")
        )

        if instruction.action == TradeAction.HOLD:
            # 已平仓完毕，不需要操作
            return

        # 执行平仓操作
        self.logger.info(f"📉 WINDING DOWN: {instruction.reason}")
        result = await self.executor.execute_trade(
            instruction.action,
            instruction.quantity,
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
    bot = HedgeBotV3()
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
